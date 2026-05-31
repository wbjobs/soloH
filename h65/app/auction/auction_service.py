from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import time
import asyncio

from app.models.models import (
    Auction as DBAuction, Item as DBItem, Bidder as DBBidder,
    Valuation as DBValuation, Bid as DBBid, RoundRecord as DBRoundRecord,
    AuctionResult as DBAuctionResult
)
from app.schemas.schemas import AuctionCreate
from app.auction.bidder import AuctionState, BidderState, AuctionItem
from app.auction.valuation_generator import ValuationGenerator, create_items
from app.auction.smr_auction import SMRAuction
from app.auction.cca_auction import CCAAuction
from app.auction.result_analyzer import ResultAnalyzer
from app.visualization.plots import AuctionVisualizer
from app.realtime.websocket_manager import websocket_manager


class AuctionService:
    running_auctions: Dict[int, Any] = {}

    def __init__(self, db: Session):
        self.db = db
        self.valuation_generator = ValuationGenerator()

    def create_auction(self, auction_data: AuctionCreate, seed: Optional[int] = None) -> DBAuction:
        if seed is not None:
            self.valuation_generator = ValuationGenerator(seed=seed)

        config = auction_data.config.copy()
        config["pricing_rule"] = auction_data.pricing_rule
        config["reserve_strategy"] = auction_data.reserve_strategy
        config["reserve_price_multiplier"] = auction_data.reserve_price_multiplier

        effective_min_price = auction_data.min_price
        if auction_data.reserve_strategy == "public":
            effective_min_price = auction_data.min_price

        db_auction = DBAuction(
            name=auction_data.name,
            auction_type=auction_data.auction_type,
            description=auction_data.description,
            min_price=effective_min_price,
            max_price=auction_data.max_price,
            bid_increment=auction_data.bid_increment,
            max_rounds=auction_data.max_rounds,
            activity_rule=auction_data.activity_rule,
            config=config,
            status="created"
        )
        self.db.add(db_auction)
        self.db.flush()

        items_data = auction_data.items
        generated_items = None
        if not items_data and auction_data.num_items:
            generated_items = create_items(auction_data.num_items, seed)
            items_data = [
                {"name": item["name"], "description": item.get("description"),
                 "bandwidth": item.get("bandwidth"), "frequency_range": item.get("frequency_range"),
                 "reserve_price": item.get("reserve_price", 0)}
                for item in generated_items
            ]

        reserve_multiplier = auction_data.reserve_price_multiplier

        for i, item_data in enumerate(items_data):
            reserve_price = item_data.get("reserve_price", 0)

            if reserve_multiplier > 0 and not item_data.get("reserve_price") is None:
                if generated_items and i < len(generated_items):
                    base_val = generated_items[i].get("base_value", 0)
                else:
                    base_val = auction_data.min_price * 5
                reserve_price = base_val * reserve_multiplier

            if auction_data.reserve_strategy == "public":
                if reserve_price > 0:
                    item_min_price = max(auction_data.min_price, reserve_price)
                else:
                    item_min_price = auction_data.min_price
            else:
                item_min_price = auction_data.min_price

            db_item = DBItem(
                auction_id=db_auction.id,
                name=item_data["name"],
                description=item_data.get("description"),
                bandwidth=item_data.get("bandwidth"),
                frequency_range=item_data.get("frequency_range"),
                reserve_price=reserve_price
            )
            self.db.add(db_item)

        self.db.flush()

        item_ids = [item.id for item in db_auction.items]
        num_items = len(items_data)
        idx_to_id = {i: item_ids[i] for i in range(num_items)}

        bidders_data = auction_data.bidders
        if not bidders_data and auction_data.num_bidders:
            if auction_data.bidder_strategies:
                strategies = auction_data.bidder_strategies
            else:
                strategies = ["truthful", "aggressive", "conservative", "bundle", "adaptive"]
            bidders_data = []
            for i in range(auction_data.num_bidders):
                bidders_data.append({
                    "name": f"Bidder_{i+1}",
                    "strategy_name": strategies[i % len(strategies)],
                    "budget": 1e9,
                    "risk_aversion": 0.5
                })

        num_bidders = len(bidders_data)

        valuations_data = []
        if any(b.get("valuations") for b in bidders_data):
            for i, bidder_data in enumerate(bidders_data):
                vals = bidder_data.get("valuations", [])
                valuations_data.append({
                    "base_values": {v.item_id: v.base_value for v in vals},
                    "complementary_values": {k: v for v in vals for k, v in v.complementary_values.items()},
                    "substitute_values": {k: v for v in vals for k, v in getattr(v, 'substitute_values', {}).items()}
                })
        else:
            valuation_model = auction_data.valuation_model or "random"
            valuation_params = auction_data.valuation_params or {}

            valuations_data = self.valuation_generator.generate_valuations(
                num_items, num_bidders, valuation_model, **valuation_params
            )

        for i, bidder_data in enumerate(bidders_data):
            db_bidder = DBBidder(
                auction_id=db_auction.id,
                name=bidder_data["name"],
                strategy_name=bidder_data.get("strategy_name", "truthful"),
                strategy_params=bidder_data.get("strategy_params", {}),
                budget=bidder_data.get("budget", 1e9),
                risk_aversion=bidder_data.get("risk_aversion", 0.5)
            )
            self.db.add(db_bidder)
            self.db.flush()

            bidder_vals = valuations_data[i]
            for item_idx in range(num_items):
                actual_item_id = idx_to_id[item_idx]
                base_value = bidder_vals["base_values"].get(item_idx, 0)

                comp_values = {}
                for key, value in bidder_vals.get("complementary_values", {}).items():
                    parts = key.split("_")
                    if len(parts) == 2:
                        idx_i, idx_j = int(parts[0]), int(parts[1])
                        if idx_i == item_idx or idx_j == item_idx:
                            if idx_i in idx_to_id and idx_j in idx_to_id:
                                new_key = f"{idx_to_id[idx_i]}_{idx_to_id[idx_j]}"
                                comp_values[new_key] = value

                sub_values = {}
                for key, value in bidder_vals.get("substitute_values", {}).items():
                    parts = key.split("_")
                    if len(parts) == 2:
                        idx_i, idx_j = int(parts[0]), int(parts[1])
                        if idx_i == item_idx or idx_j == item_idx:
                            if idx_i in idx_to_id and idx_j in idx_to_id:
                                new_key = f"{idx_to_id[idx_i]}_{idx_to_id[idx_j]}"
                                sub_values[new_key] = value

                db_valuation = DBValuation(
                    bidder_id=db_bidder.id,
                    item_id=actual_item_id,
                    base_value=base_value,
                    complementary_values=comp_values,
                    substitute_values=sub_values
                )
                self.db.add(db_valuation)

        self.db.commit()
        self.db.refresh(db_auction)
        return db_auction

    def _build_auction_state(self, db_auction: DBAuction) -> AuctionState:
        items = []
        for db_item in db_auction.items:
            item = AuctionItem(
                item_id=db_item.id,
                name=db_item.name,
                reserve_price=db_item.reserve_price,
                bandwidth=db_item.bandwidth,
                frequency_range=db_item.frequency_range,
                current_price=db_auction.min_price
            )
            items.append(item)

        bidders = []
        for db_bidder in db_auction.bidders:
            base_values = {}
            complementary_values = {}
            substitute_values = {}
            for val in db_bidder.valuations:
                base_values[val.item_id] = val.base_value
                if val.complementary_values:
                    complementary_values.update(val.complementary_values)
                if hasattr(val, 'substitute_values') and val.substitute_values:
                    substitute_values.update(val.substitute_values)

            bidder = BidderState(
                bidder_id=db_bidder.id,
                name=db_bidder.name,
                budget=db_bidder.budget,
                risk_aversion=db_bidder.risk_aversion,
                strategy_name=db_bidder.strategy_name,
                strategy_params=db_bidder.strategy_params,
                base_values=base_values,
                complementary_values=complementary_values,
                substitute_values=substitute_values,
                activity_score=db_bidder.activity_score
            )
            bidders.append(bidder)

        state = AuctionState(
            auction_id=db_auction.id,
            auction_type=db_auction.auction_type,
            items=items,
            bidders=bidders,
            min_price=db_auction.min_price,
            max_price=db_auction.max_price,
            bid_increment=db_auction.bid_increment,
            max_rounds=db_auction.max_rounds,
            activity_rule=db_auction.activity_rule,
            config=db_auction.config
        )

        state.current_round = db_auction.current_round or 0
        state.is_completed = db_auction.is_completed or False
        state.status = db_auction.status or "created"

        if db_auction.round_records:
            from app.auction.bidder import RoundInfo
            sorted_records = sorted(db_auction.round_records, key=lambda r: r.round_number)

            round_bids = {}
            for db_bid in db_auction.bids:
                rn = db_bid.round_number
                if rn not in round_bids:
                    round_bids[rn] = []
                round_bids[rn].append({
                    "bidder_id": db_bid.bidder_id,
                    "item_id": db_bid.item_id,
                    "bundle": db_bid.bundle,
                    "price": db_bid.price,
                    "quantity": db_bid.quantity,
                    "is_valid": db_bid.is_valid
                })

            for db_round in sorted_records:
                rn = db_round.round_number
                bids_for_round = round_bids.get(rn, [])
                round_info = RoundInfo(
                    round_number=rn,
                    prices=db_round.prices,
                    excess_demand=db_round.excess_demand,
                    provisional_allocation=db_round.provisional_allocation,
                    bidder_activity=db_round.bidder_activity,
                    bids=bids_for_round,
                    bids_count=db_round.bids_count or 0,
                    total_bid_amount=db_round.total_bid_amount or 0.0,
                    phase=db_round.phase or "clock"
                )
                state.round_history.append(round_info)

            latest_round = sorted_records[-1]
            state.phase = latest_round.phase or "clock"

            for item in state.items:
                item_id_str = str(item.item_id)
                if item_id_str in latest_round.prices:
                    item.current_price = latest_round.prices[item_id_str]
                elif item.item_id in latest_round.prices:
                    item.current_price = latest_round.prices[item.item_id]

        if db_auction.bids:
            for db_bid in db_auction.bids:
                state.bid_history.append({
                    "bid_id": db_bid.id,
                    "bidder_id": db_bid.bidder_id,
                    "item_id": db_bid.item_id,
                    "bundle": db_bid.bundle,
                    "price": db_bid.price,
                    "quantity": db_bid.quantity,
                    "round_number": db_bid.round_number,
                    "is_valid": db_bid.is_valid,
                    "created_at": db_bid.created_at
                })

        for db_bidder in db_auction.bidders:
            bidder_state = state.get_bidder(db_bidder.id)
            if bidder_state:
                bidder_state.activity_score = db_bidder.activity_score

        return state

    def run_auction(self, auction_id: int, verbose: bool = False) -> Dict[str, Any]:
        db_auction = self.db.query(DBAuction).filter(DBAuction.id == auction_id).first()
        if not db_auction:
            raise ValueError(f"Auction {auction_id} not found")

        if db_auction.status == "completed":
            return self._get_existing_result(db_auction)

        state = self._build_auction_state(db_auction)

        if db_auction.auction_type == "smr":
            auction = SMRAuction(state)
        elif db_auction.auction_type == "cca":
            auction = CCAAuction(state)
        else:
            raise ValueError(f"Unknown auction type: {db_auction.auction_type}")

        db_auction.status = "running"
        db_auction.started_at = datetime.now()
        self.db.commit()

        start_time = time.time()
        result = auction.run(verbose=verbose)
        duration = time.time() - start_time

        self._save_round_records(db_auction, state)
        self._save_bids(db_auction, state)
        self._save_final_results(db_auction, state, result, duration)

        db_auction.status = "completed"
        db_auction.is_completed = True
        db_auction.completed_at = datetime.now()
        db_auction.current_round = state.current_round
        self.db.commit()

        analyzer = ResultAnalyzer(state)
        analysis = analyzer.generate_summary_report()

        visualizer = AuctionVisualizer(state)
        plots = visualizer.generate_all_plots(save_to_disk=True)

        return {
            "auction_id": auction_id,
            "result": result,
            "analysis": analysis,
            "plots": {k: f"/static/{k}.png" for k in plots.keys()}
        }

    def step_auction(self, auction_id: int) -> Dict[str, Any]:
        db_auction = self.db.query(DBAuction).filter(DBAuction.id == auction_id).first()
        if not db_auction:
            raise ValueError(f"Auction {auction_id} not found")

        if db_auction.status == "completed":
            return {"status": "completed", "message": "Auction already finished"}

        if auction_id not in self.running_auctions:
            state = self._build_auction_state(db_auction)

            if db_auction.auction_type == "smr":
                auction = SMRAuction(state)
            elif db_auction.auction_type == "cca":
                auction = CCAAuction(state)
            else:
                raise ValueError(f"Unknown auction type: {db_auction.auction_type}")

            if db_auction.status == "created":
                db_auction.status = "running"
                db_auction.started_at = datetime.now()
                self.db.commit()

            self.running_auctions[auction_id] = (auction, state)
        else:
            auction, state = self.running_auctions[auction_id]

        if db_auction.status == "created":
            db_auction.status = "running"
            db_auction.started_at = datetime.now()
            self.db.commit()
            self._broadcast_auction_start(auction_id, state)

        step_result = auction.step()

        if step_result.get("round_completed", False):
            self._broadcast_round_update(auction_id, state)

        if step_result.get("is_complete", False):
            self._broadcast_auction_end(auction_id, step_result.get("result", {}))
            self._save_round_records(db_auction, state)
            self._save_bids(db_auction, state)

            result = step_result.get("result", {})
            duration = (datetime.now() - db_auction.started_at).total_seconds() if db_auction.started_at else 0
            self._save_final_results(db_auction, state, result, duration)

            db_auction.status = "completed"
            db_auction.is_completed = True
            db_auction.completed_at = datetime.now()
            db_auction.current_round = state.current_round
            self.db.commit()

            del self.running_auctions[auction_id]

            analyzer = ResultAnalyzer(state)
            analysis = analyzer.generate_summary_report()

            visualizer = AuctionVisualizer(state)
            plots = visualizer.generate_all_plots(save_to_disk=True)

            return {
                "status": "completed",
                "result": result,
                "analysis": analysis,
                "plots": {k: f"/static/{k}.png" for k in plots.keys()}
            }

        self._save_round_records(db_auction, state)
        self._save_bids(db_auction, state)
        db_auction.current_round = state.current_round
        self.db.commit()

        return step_result

    def _save_round_records(self, db_auction: DBAuction, state: AuctionState):
        existing_rounds = {rr.round_number for rr in db_auction.round_records}

        for round_info in state.round_history:
            if round_info.round_number in existing_rounds:
                continue

            db_round = DBRoundRecord(
                auction_id=db_auction.id,
                round_number=round_info.round_number,
                prices=round_info.prices,
                excess_demand=round_info.excess_demand,
                provisional_allocation=round_info.provisional_allocation,
                bidder_activity=round_info.bidder_activity,
                bids_count=len(round_info.bids),
                total_bid_amount=sum(b.get("price", 0) for b in round_info.bids),
                phase=round_info.phase
            )
            self.db.add(db_round)

    def _save_bids(self, db_auction: DBAuction, state: AuctionState):
        existing_bids = set()
        for db_bid in db_auction.bids:
            key = (db_bid.bidder_id, db_bid.round_number, db_bid.item_id or 0,
                   str(db_bid.bundle) if db_bid.bundle else "")
            existing_bids.add(key)

        for round_info in state.round_history:
            for bid in round_info.bids:
                item_id = bid.get("item_id")
                bundle = bid.get("bundle")
                key = (bid["bidder_id"], bid["round_number"],
                       item_id or 0, str(bundle) if bundle else "")

                if key in existing_bids:
                    continue

                db_bid = DBBid(
                    auction_id=db_auction.id,
                    bidder_id=bid["bidder_id"],
                    round_number=bid["round_number"],
                    item_id=item_id,
                    bundle=bundle,
                    price=bid["price"],
                    quantity=bid.get("quantity", 1),
                    is_valid=True
                )
                self.db.add(db_bid)

    def _save_final_results(self, db_auction: DBAuction, state: AuctionState,
                            result: Dict[str, Any], duration: float):
        analyzer = ResultAnalyzer(state)
        metrics = analyzer.compute_all_metrics()

        final_allocation = {}
        final_prices = {}
        for item in state.items:
            if item.final_winner is not None:
                winner_id = str(item.final_winner)
                if winner_id not in final_allocation:
                    final_allocation[winner_id] = []
                final_allocation[winner_id].append(item.item_id)
                final_prices[str(item.item_id)] = item.final_price

        for item in state.items:
            db_item = self.db.query(DBItem).filter(DBItem.id == item.item_id).first()
            if db_item:
                db_item.final_winner = item.final_winner
                db_item.final_price = item.final_price
                if item.final_winner is not None:
                    db_item.winner_id = int(item.final_winner)

        bidder_payments = {}
        bidder_utilities = {}
        bidder_profits = {}

        for bidder in state.bidders:
            db_bidder = self.db.query(DBBidder).filter(DBBidder.id == bidder.bidder_id).first()
            if db_bidder:
                db_bidder.total_payment = bidder.total_payment
                db_bidder.total_value = bidder.total_value
                db_bidder.activity_score = bidder.activity_score

            bidder_payments[str(bidder.bidder_id)] = bidder.total_payment
            bidder_utilities[str(bidder.bidder_id)] = bidder.get_utility()
            bidder_profits[str(bidder.bidder_id)] = bidder.get_utility()

        db_result = DBAuctionResult(
            auction_id=db_auction.id,
            final_prices=final_prices,
            final_allocation=final_allocation,
            total_revenue=metrics["revenue_metrics"]["total_revenue"],
            efficiency=metrics["efficiency_metrics"]["efficiency"],
            optimal_social_welfare=metrics["efficiency_metrics"]["optimal_social_welfare"],
            actual_social_welfare=metrics["efficiency_metrics"]["actual_social_welfare"],
            bidder_payments=bidder_payments,
            bidder_utilities=bidder_utilities,
            bidder_profits=bidder_profits,
            final_round=state.current_round,
            auction_duration_seconds=duration
        )
        self.db.add(db_result)

    def _get_existing_result(self, db_auction: DBAuction) -> Dict[str, Any]:
        state = self._build_auction_state(db_auction)

        for db_item in db_auction.items:
            item = state.get_item(db_item.id)
            if item:
                item.final_winner = db_item.final_winner
                item.final_price = db_item.final_price
                item.current_price = db_item.final_price or db_auction.min_price

        for db_bidder in db_auction.bidders:
            bidder = state.get_bidder(db_bidder.id)
            if bidder:
                bidder.total_payment = db_bidder.total_payment
                bidder.total_value = db_bidder.total_value
                bidder.activity_score = db_bidder.activity_score
                won_items = [item.id for item in db_auction.items if item.final_winner == db_bidder.id]
                bidder.current_bundle = won_items

        analyzer = ResultAnalyzer(state)
        analysis = analyzer.generate_summary_report()

        visualizer = AuctionVisualizer(state)
        plots = visualizer.generate_all_plots(save_to_disk=True)

        result_data = {
            "auction_id": db_auction.id,
            "auction_type": db_auction.auction_type,
            "final_round": db_auction.current_round,
            "final_prices": {str(item.id): item.final_price for item in db_auction.items},
            "bidder_results": analysis["bidder_metrics"]["bidder_details"]
        }

        if db_auction.result:
            result_data["total_revenue"] = db_auction.result.total_revenue
            result_data["efficiency"] = db_auction.result.efficiency
            result_data["duration_seconds"] = db_auction.result.auction_duration_seconds

        return {
            "auction_id": db_auction.id,
            "result": result_data,
            "analysis": analysis,
            "plots": {k: f"/static/{k}.png" for k in plots.keys()}
        }

    def get_auction_state(self, auction_id: int) -> Dict[str, Any]:
        db_auction = self.db.query(DBAuction).filter(DBAuction.id == auction_id).first()
        if not db_auction:
            raise ValueError(f"Auction {auction_id} not found")

        prices = {}
        provisional_allocation = {}
        excess_demand = {}

        if db_auction.round_records:
            latest_round = max(db_auction.round_records, key=lambda r: r.round_number)
            prices = latest_round.prices
            provisional_allocation = latest_round.provisional_allocation
            excess_demand = latest_round.excess_demand

        return {
            "auction_id": auction_id,
            "status": db_auction.status,
            "current_round": db_auction.current_round,
            "is_completed": db_auction.is_completed,
            "prices": prices,
            "provisional_allocation": provisional_allocation,
            "excess_demand": excess_demand
        }

    def list_auctions(self, skip: int = 0, limit: int = 100) -> List[DBAuction]:
        return self.db.query(DBAuction).order_by(DBAuction.created_at.desc()).offset(skip).limit(limit).all()

    def get_auction(self, auction_id: int) -> Optional[DBAuction]:
        return self.db.query(DBAuction).filter(DBAuction.id == auction_id).first()

    def delete_auction(self, auction_id: int) -> bool:
        db_auction = self.db.query(DBAuction).filter(DBAuction.id == auction_id).first()
        if db_auction:
            if auction_id in self.running_auctions:
                del self.running_auctions[auction_id]
            self.db.delete(db_auction)
            self.db.commit()
            return True
        return False

    def _broadcast_auction_start(self, auction_id: int, state: AuctionState):
        try:
            auction_info = {
                "auction_id": auction_id,
                "auction_type": state.auction_type,
                "num_items": len(state.items),
                "num_bidders": len(state.bidders),
                "items": [{"item_id": i.item_id, "name": i.name} for i in state.items],
                "bidders": [{"bidder_id": b.bidder_id, "name": b.name} for b in state.bidders]
            }
            asyncio.run(websocket_manager.broadcast_auction_start(auction_id, auction_info))
        except Exception as e:
            pass

    def _broadcast_round_update(self, auction_id: int, state: AuctionState):
        try:
            if state.round_history:
                latest = state.round_history[-1]
                round_data = {
                    "round_number": latest.round_number,
                    "prices": latest.prices,
                    "excess_demand": latest.excess_demand,
                    "provisional_allocation": latest.provisional_allocation,
                    "bids_count": latest.bids_count,
                    "total_bid_amount": latest.total_bid_amount,
                    "bidder_activity": latest.bidder_activity,
                    "phase": latest.phase
                }
                asyncio.run(websocket_manager.broadcast_round_update(auction_id, round_data))
        except Exception as e:
            pass

    def _broadcast_auction_end(self, auction_id: int, result: Dict[str, Any]):
        try:
            asyncio.run(websocket_manager.broadcast_auction_end(auction_id, result))
        except Exception as e:
            pass

    def _broadcast_bid_submitted(self, auction_id: int, bid_data: Dict[str, Any]):
        try:
            asyncio.run(websocket_manager.broadcast_bid_submitted(auction_id, bid_data))
        except Exception as e:
            pass
