from typing import List, Dict, Optional, Any, Tuple
import time
from collections import defaultdict

from app.auction.bidder import BidderState, AuctionItem, AuctionState
from app.strategies.strategy_manager import strategy_manager


class SMRAuction:
    def __init__(self, auction_state: AuctionState):
        self.state = auction_state
        self.bidder_strategies: Dict[int, Any] = {}
        self._initialize_strategies()

    def _initialize_strategies(self):
        for bidder in self.state.bidders:
            try:
                strategy = strategy_manager.get_strategy(
                    bidder.strategy_name,
                    bidder.strategy_params
                )
                self.bidder_strategies[bidder.bidder_id] = strategy
            except ValueError:
                from app.strategies.base_strategy import TruthfulStrategy
                self.bidder_strategies[bidder.bidder_id] = TruthfulStrategy()

    def run(self, verbose: bool = False) -> Dict[str, Any]:
        start_time = time.time()
        self.state.status = "running"

        if verbose:
            print(f"Starting SMR Auction with {len(self.state.items)} items and {len(self.state.bidders)} bidders")

        while not self._is_auction_complete():
            self.state.current_round += 1
            round_result = self._run_round()

            if verbose and self.state.current_round % 10 == 0:
                print(f"Round {self.state.current_round}: "
                      f"excess_demand={max(round_result['excess_demand'].values(), default=0):.1f}, "
                      f"bids={len(round_result['bids'])}")

            self._update_prices(round_result["excess_demand"])
            self._update_activity_scores(round_result["demanded_bundles"])

            self.state.record_round(
                prices=self.state.get_current_prices(),
                excess_demand=round_result["excess_demand"],
                provisional_allocation=round_result["provisional_allocation"],
                bids=round_result["bids"],
                bidder_activity=round_result["bidder_activity"]
            )

            if self.state.current_round >= self.state.max_rounds:
                break

        self._finalize_auction()
        self.state.status = "completed"
        self.state.is_completed = True

        duration = time.time() - start_time
        bidder_results = self._get_bidder_results()
        total_revenue = sum(br["total_payment"] for br in bidder_results.values())

        return {
            "auction_id": self.state.auction_id,
            "auction_type": "smr",
            "final_round": self.state.current_round,
            "duration_seconds": round(duration, 2),
            "final_prices": {item.item_id: round(item.current_price, 2) for item in self.state.items},
            "final_allocation": self._get_final_allocation(),
            "bidder_results": bidder_results,
            "total_revenue": round(total_revenue, 2),
            "pricing_rule": self.state.config.get("pricing_rule", "first_price")
        }

    def _run_round(self) -> Dict[str, Any]:
        bids = []
        demanded_bundles: Dict[int, List[int]] = {}
        bidder_activity: Dict[int, float] = {}

        for bidder in self.state.bidders:
            if bidder.activity_score < 0.1 and self.state.activity_rule:
                demanded_bundles[bidder.bidder_id] = []
                bidder_activity[bidder.bidder_id] = bidder.activity_score
                continue

            strategy = self.bidder_strategies[bidder.bidder_id]
            try:
                round_bids = strategy.decide_bid(
                    bidder, self.state, self.state.current_round
                )
            except Exception as e:
                print(f"Error in bidder {bidder.bidder_id} strategy: {e}")
                round_bids = []

            valid_bids = []
            bid_items = []
            for bid in round_bids:
                item_id = bid.get("item_id")
                price = bid.get("price", 0.0)

                if item_id is None:
                    continue

                item = self.state.get_item(item_id)
                if item is None:
                    continue

                current_price = self.state.get_current_prices().get(item_id, 0)
                if price < current_price + self.state.bid_increment * 0.9:
                    continue

                if not bidder.can_afford(price):
                    continue

                valid_bids.append({
                    "bidder_id": bidder.bidder_id,
                    "item_id": item_id,
                    "price": round(price, 2),
                    "quantity": bid.get("quantity", 1),
                    "round_number": self.state.current_round
                })
                bid_items.append(item_id)

            bids.extend(valid_bids)
            demanded_bundles[bidder.bidder_id] = bid_items
            bidder_activity[bidder.bidder_id] = bidder.activity_score

            bidder.record_bid(self.state.current_round, valid_bids)

        excess_demand = self.state.get_excess_demand(demanded_bundles)
        provisional_allocation = self._compute_provisional_allocation(bids)

        for bidder in self.state.bidders:
            allocation = provisional_allocation.get(bidder.bidder_id, [])
            bidder.record_allocation(allocation)

        return {
            "bids": bids,
            "demanded_bundles": demanded_bundles,
            "excess_demand": excess_demand,
            "provisional_allocation": provisional_allocation,
            "bidder_activity": bidder_activity
        }

    def _compute_provisional_allocation(self, bids: List[Dict]) -> Dict[int, List[int]]:
        item_high_bid: Dict[int, Tuple[int, float]] = {}

        for bid in bids:
            item_id = bid["item_id"]
            price = bid["price"]
            bidder_id = bid["bidder_id"]

            if item_id not in item_high_bid or price > item_high_bid[item_id][1]:
                item_high_bid[item_id] = (bidder_id, price)

        allocation: Dict[int, List[int]] = defaultdict(list)
        for item_id, (bidder_id, price) in item_high_bid.items():
            allocation[bidder_id].append(item_id)
            item = self.state.get_item(item_id)
            if item:
                item.provisional_winner = bidder_id

        return dict(allocation)

    def _update_prices(self, excess_demand: Dict[int, float]):
        bid_increment = self.state.bid_increment
        for item_id, excess in excess_demand.items():
            if excess > 0:
                item = self.state.get_item(item_id)
                if item:
                    price_adjustment = bid_increment * (1 + excess / len(self.state.bidders))
                    item.current_price = min(
                        self.state.max_price,
                        item.current_price + price_adjustment
                    )

    def _update_activity_scores(self, demanded_bundles: Dict[int, List[int]]):
        if not self.state.activity_rule:
            return

        activity_weight = self.state.config.get("activity_weight", 0.8)
        for bidder in self.state.bidders:
            bundle = demanded_bundles.get(bidder.bidder_id, [])
            bidder.update_activity(bundle, activity_weight)

    def _is_auction_complete(self) -> bool:
        if self.state.current_round == 0:
            return False

        if self.state.current_round >= self.state.max_rounds:
            return True

        if self.state.round_history:
            last_round = self.state.round_history[-1]
            max_excess = max(last_round.excess_demand.values(), default=0)
            if max_excess <= 0:
                consecutive_zero = sum(
                    1 for r in self.state.round_history[-3:]
                    if max(r.excess_demand.values(), default=0) <= 0
                )
                if consecutive_zero >= 3:
                    return True

        return False

    def _finalize_auction(self):
        item_all_bids: Dict[int, List[Tuple[int, float]]] = defaultdict(list)

        for round_record in self.state.round_history:
            for bid in round_record.bids:
                item_id = bid["item_id"]
                item_all_bids[item_id].append((bid["bidder_id"], bid["price"]))

        for item_id in item_all_bids:
            item_all_bids[item_id].sort(key=lambda x: x[1], reverse=True)

        pricing_rule = self.state.config.get("pricing_rule", "first_price")

        for item in self.state.items:
            bids = item_all_bids.get(item.item_id, [])
            if not bids:
                continue

            winner_id, first_price = bids[0]

            if pricing_rule == "second_price":
                other_bids = [b for b in bids if b[0] != winner_id]
                if other_bids:
                    payment_price = other_bids[0][1]
                else:
                    payment_price = max(item.reserve_price, first_price * 0.9)
            else:
                payment_price = first_price

            reserve_price = item.reserve_price if hasattr(item, 'reserve_price') else 0.0
            if payment_price < reserve_price:
                continue

            item.final_winner = winner_id
            item.final_price = round(payment_price, 2)

            bidder = self.state.get_bidder(winner_id)
            if bidder:
                bidder.total_payment += payment_price
                bidder.total_value += bidder.get_individual_value(item.item_id)
                bidder.current_bundle.append(item.item_id)

    def _get_final_allocation(self) -> Dict[int, List[int]]:
        allocation: Dict[int, List[int]] = defaultdict(list)
        for item in self.state.items:
            if item.final_winner is not None:
                allocation[item.final_winner].append(item.item_id)
        return dict(allocation)

    def _get_bidder_results(self) -> Dict[int, Dict[str, Any]]:
        results = {}
        for bidder in self.state.bidders:
            won_items = [
                item.item_id for item in self.state.items
                if item.final_winner == bidder.bidder_id
            ]
            bundle_value = bidder.get_value(won_items)

            results[bidder.bidder_id] = {
                "bidder_name": bidder.name,
                "strategy": bidder.strategy_name,
                "won_items": won_items,
                "total_payment": round(bidder.total_payment, 2),
                "total_value": round(bundle_value, 2),
                "utility": round(bundle_value - bidder.total_payment, 2),
                "profit": round(bundle_value - bidder.total_payment, 2),
                "activity_score": round(bidder.activity_score, 3)
            }
        return results

    def step(self) -> Dict[str, Any]:
        if self.state.is_completed:
            return {"status": "completed"}

        self.state.current_round += 1
        round_result = self._run_round()
        self._update_prices(round_result["excess_demand"])
        self._update_activity_scores(round_result["demanded_bundles"])

        self.state.record_round(
            prices=self.state.get_current_prices(),
            excess_demand=round_result["excess_demand"],
            provisional_allocation=round_result["provisional_allocation"],
            bids=round_result["bids"],
            bidder_activity=round_result["bidder_activity"]
        )

        is_complete = self._is_auction_complete() or self.state.current_round >= self.state.max_rounds

        if is_complete:
            self._finalize_auction()
            self.state.status = "completed"
            self.state.is_completed = True

        return {
            "round": self.state.current_round,
            "is_complete": is_complete,
            "round_completed": True,
            "prices": {k: round(v, 2) for k, v in self.state.get_current_prices().items()},
            "excess_demand": round_result["excess_demand"],
            "bids_count": len(round_result["bids"]),
            "provisional_allocation": round_result["provisional_allocation"]
        }
