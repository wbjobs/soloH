from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from datetime import datetime
from collections import defaultdict
import numpy as np

from app.models.models import Competition as DBCompetition, Strategy as DBStrategy
from app.auction.auction_service import AuctionService
from app.auction.valuation_generator import ValuationGenerator
from app.strategies.strategy_manager import strategy_manager


class CompetitionService:
    def __init__(self, db: Session):
        self.db = db
        self.auction_service = AuctionService(db)
        self.valuation_generator = ValuationGenerator()

    def upload_strategy(self, name: str, code: str, author: Optional[str] = None,
                        description: Optional[str] = None, is_public: bool = True) -> DBStrategy:
        result = strategy_manager.upload_strategy(
            strategy_name=name,
            code=code,
            author=author,
            description=description,
            is_public=is_public
        )

        existing = self.db.query(DBStrategy).filter(DBStrategy.name == result["strategy_name"]).first()
        if existing:
            existing.code_hash = result["code_hash"]
            existing.description = description
            existing.author = author
            existing.is_public = is_public
            existing.filename = result["filename"]
            self.db.commit()
            self.db.refresh(existing)
            return existing

        db_strategy = DBStrategy(
            name=result["strategy_name"],
            description=description,
            author=author,
            filename=result["filename"],
            code_hash=result["code_hash"],
            is_public=is_public
        )
        self.db.add(db_strategy)
        self.db.commit()
        self.db.refresh(db_strategy)
        return db_strategy

    def list_strategies(self, include_builtin: bool = True) -> List[Dict[str, Any]]:
        strategies = strategy_manager.list_strategies(include_builtin=include_builtin)

        db_strategies = {s.name: s for s in self.db.query(DBStrategy).all()}

        result = []
        for s in strategies:
            db_s = db_strategies.get(s["name"])
            result.append({
                "name": s["name"],
                "description": s["description"],
                "is_builtin": s["is_builtin"],
                "code_hash": s.get("code_hash"),
                "class_name": s.get("class_name"),
                "id": db_s.id if db_s else None,
                "author": db_s.author if db_s else None,
                "total_wins": db_s.total_wins if db_s else 0,
                "total_participations": db_s.total_participations if db_s else 0,
                "win_rate": db_s.win_rate if db_s else 0.0,
                "average_profit": db_s.average_profit if db_s else 0.0,
                "is_public": db_s.is_public if db_s else s["is_builtin"]
            })

        return result

    def get_strategy(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        db_strategy = self.db.query(DBStrategy).filter(DBStrategy.id == strategy_id).first()
        if not db_strategy:
            return None

        code = strategy_manager.get_strategy_code(db_strategy.name)

        return {
            "id": db_strategy.id,
            "name": db_strategy.name,
            "description": db_strategy.description,
            "author": db_strategy.author,
            "filename": db_strategy.filename,
            "code_hash": db_strategy.code_hash,
            "is_public": db_strategy.is_public,
            "total_wins": db_strategy.total_wins,
            "total_participations": db_strategy.total_participations,
            "win_rate": db_strategy.win_rate,
            "average_profit": db_strategy.average_profit,
            "code": code,
            "created_at": db_strategy.created_at,
            "updated_at": db_strategy.updated_at
        }

    def delete_strategy(self, strategy_id: int) -> bool:
        db_strategy = self.db.query(DBStrategy).filter(DBStrategy.id == strategy_id).first()
        if not db_strategy:
            return False

        try:
            strategy_manager.delete_strategy(db_strategy.name)
        except ValueError:
            pass

        self.db.delete(db_strategy)
        self.db.commit()
        return True

    def create_competition(self, name: str, auction_type: str, strategy_ids: List[int],
                           config: Optional[Dict[str, Any]] = None,
                           description: Optional[str] = None) -> DBCompetition:
        db_strategies = self.db.query(DBStrategy).filter(DBStrategy.id.in_(strategy_ids)).all()
        if len(db_strategies) != len(strategy_ids):
            raise ValueError("Some strategies not found")

        db_competition = DBCompetition(
            name=name,
            description=description,
            auction_type=auction_type,
            status="created",
            strategy_ids=strategy_ids,
            config=config or {}
        )
        self.db.add(db_competition)
        self.db.commit()
        self.db.refresh(db_competition)
        return db_competition

    def run_competition(self, competition_id: int, num_rounds: int = 5,
                        verbose: bool = False) -> Dict[str, Any]:
        db_competition = self.db.query(DBCompetition).filter(DBCompetition.id == competition_id).first()
        if not db_competition:
            raise ValueError(f"Competition {competition_id} not found")

        db_strategies = self.db.query(DBStrategy).filter(
            DBStrategy.id.in_(db_competition.strategy_ids)
        ).all()

        if len(db_strategies) < 2:
            raise ValueError("Need at least 2 strategies for competition")

        db_competition.status = "running"
        db_competition.started_at = datetime.now()
        self.db.commit()

        strategy_names = {s.id: s.name for s in db_strategies}

        num_items = db_competition.config.get("num_items", 5)
        base_valuation_range = db_competition.config.get("base_value_range", (50.0, 500.0))

        all_results = []
        strategy_stats: Dict[int, Dict[str, Any]] = defaultdict(lambda: {
            "total_profit": 0.0,
            "total_utility": 0.0,
            "wins": 0,
            "items_won": 0,
            "auctions_won": 0
        })

        for round_idx in range(num_rounds):
            if verbose:
                print(f"Competition Round {round_idx + 1}/{num_rounds}")

            seed = round_idx * 1000 + hash(competition_id) % 1000

            auction_name = f"{db_competition.name}_Round_{round_idx + 1}"
            auction_data = type('AuctionCreate', (), {
                "name": auction_name,
                "auction_type": db_competition.auction_type,
                "description": f"Competition round {round_idx + 1}",
                "min_price": 10.0,
                "max_price": 1000.0,
                "bid_increment": 5.0,
                "max_rounds": 100,
                "activity_rule": True,
                "config": db_competition.config,
                "num_items": num_items,
                "num_bidders": len(db_strategies),
                "items": [],
                "bidders": []
            })()

            valuations = self.valuation_generator.generate_valuations(
                num_items, len(db_strategies), "random",
                base_value_range=base_valuation_range,
                complementary_density=0.3
            )

            bidders_data = []
            for i, db_strategy in enumerate(db_strategies):
                bidder_val = valuations[i]
                bidder_vals = []
                for item_idx in range(num_items):
                    base_value = bidder_val["base_values"].get(item_idx, 0)
                    comp_values = {}
                    for key, value in bidder_val["complementary_values"].items():
                        parts = key.split("_")
                        if len(parts) == 2 and (int(parts[0]) == item_idx or int(parts[1]) == item_idx):
                            comp_values[key] = value
                    bidder_vals.append({
                        "item_id": item_idx + 1,
                        "base_value": base_value,
                        "complementary_values": comp_values
                    })

                bidders_data.append({
                    "name": f"{db_strategy.name}_Bidder",
                    "strategy_name": db_strategy.name,
                    "budget": 1e9,
                    "risk_aversion": 0.5,
                    "valuations": bidder_vals
                })

            auction_data.bidders = bidders_data

            db_auction = self.auction_service.create_auction(auction_data, seed=seed)
            result = self.auction_service.run_auction(db_auction.id, verbose=verbose)

            analysis = result.get("analysis", {})
            bidder_details = analysis.get("bidder_metrics", {}).get("bidder_details", {})

            round_result = {
                "round": round_idx + 1,
                "auction_id": db_auction.id,
                "total_revenue": analysis.get("summary", {}).get("total_revenue", 0),
                "efficiency": analysis.get("summary", {}).get("efficiency", 0),
                "bidder_results": {}
            }

            auction_profits = {}
            for i, db_strategy in enumerate(db_strategies):
                bidder_id = db_auction.bidders[i].id
                bidder_result = bidder_details.get(bidder_id, {})
                profit = bidder_result.get("profit", 0)
                items_won = bidder_result.get("num_items_won", 0)

                auction_profits[db_strategy.id] = profit
                strategy_stats[db_strategy.id]["total_profit"] += profit
                strategy_stats[db_strategy.id]["total_utility"] += bidder_result.get("utility", 0)
                strategy_stats[db_strategy.id]["items_won"] += items_won
                if profit > 0:
                    strategy_stats[db_strategy.id]["wins"] += 1

                round_result["bidder_results"][db_strategy.id] = {
                    "strategy_name": db_strategy.name,
                    "profit": profit,
                    "utility": bidder_result.get("utility", 0),
                    "items_won": items_won,
                    "won_items": bidder_result.get("won_items", []),
                    "total_payment": bidder_result.get("total_payment", 0)
                }

            max_profit = max(auction_profits.values()) if auction_profits else 0
            for strategy_id, profit in auction_profits.items():
                if profit == max_profit and profit > 0:
                    strategy_stats[strategy_id]["auctions_won"] += 1

            all_results.append(round_result)

        rankings = []
        for strategy_id, stats in strategy_stats.items():
            avg_profit = stats["total_profit"] / num_rounds
            win_rate = stats["auctions_won"] / num_rounds

            rankings.append({
                "strategy_id": strategy_id,
                "strategy_name": strategy_names[strategy_id],
                "total_profit": round(stats["total_profit"], 2),
                "average_profit": round(avg_profit, 2),
                "total_utility": round(stats["total_utility"], 2),
                "auctions_won": stats["auctions_won"],
                "win_rate": round(win_rate, 4),
                "items_won": stats["items_won"],
                "positive_profit_rounds": stats["wins"]
            })

        rankings.sort(key=lambda x: x["total_profit"], reverse=True)

        for i, rank in enumerate(rankings):
            rank["rank"] = i + 1

        for rank in rankings:
            db_strategy = self.db.query(DBStrategy).filter(DBStrategy.id == rank["strategy_id"]).first()
            if db_strategy:
                db_strategy.total_participations += num_rounds
                db_strategy.total_wins += rank["auctions_won"]
                db_strategy.win_rate = db_strategy.total_wins / max(1, db_strategy.total_participations)
                old_avg = db_strategy.average_profit
                old_count = db_strategy.total_participations - num_rounds
                new_avg = (old_avg * old_count + rank["average_profit"] * num_rounds) / max(1, db_strategy.total_participations)
                db_strategy.average_profit = round(new_avg, 2)

        db_competition.status = "completed"
        db_competition.completed_at = datetime.now()
        db_competition.results = {
            "num_rounds": num_rounds,
            "round_results": all_results,
            "rankings": rankings,
            "strategy_stats": {str(k): v for k, v in strategy_stats.items()}
        }
        self.db.commit()
        self.db.refresh(db_competition)

        return {
            "competition_id": competition_id,
            "name": db_competition.name,
            "status": "completed",
            "num_rounds": num_rounds,
            "rankings": rankings,
            "round_results": all_results,
            "summary": {
                "winner": rankings[0] if rankings else None,
                "total_revenue": sum(r["total_revenue"] for r in all_results),
                "avg_efficiency": round(np.mean([r["efficiency"] for r in all_results]), 4)
            }
        }

    def list_competitions(self, skip: int = 0, limit: int = 100) -> List[DBCompetition]:
        return self.db.query(DBCompetition).order_by(DBCompetition.created_at.desc()).offset(skip).limit(limit).all()

    def get_competition(self, competition_id: int) -> Optional[DBCompetition]:
        return self.db.query(DBCompetition).filter(DBCompetition.id == competition_id).first()

    def delete_competition(self, competition_id: int) -> bool:
        db_competition = self.db.query(DBCompetition).filter(DBCompetition.id == competition_id).first()
        if db_competition:
            self.db.delete(db_competition)
            self.db.commit()
            return True
        return False
