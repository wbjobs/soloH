from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import numpy as np
from itertools import combinations

from app.auction.bidder import BidderState, AuctionItem, AuctionState


class ResultAnalyzer:
    def __init__(self, auction_state: AuctionState):
        self.state = auction_state

    def compute_all_metrics(self) -> Dict[str, Any]:
        return {
            "price_metrics": self.compute_price_metrics(),
            "allocation_metrics": self.compute_allocation_metrics(),
            "efficiency_metrics": self.compute_efficiency_metrics(),
            "revenue_metrics": self.compute_revenue_metrics(),
            "bidder_metrics": self.compute_bidder_metrics(),
            "round_metrics": self.compute_round_metrics()
        }

    def compute_price_metrics(self) -> Dict[str, Any]:
        final_prices = {}
        price_paths = defaultdict(list)

        for item in self.state.items:
            final_prices[item.item_id] = round(item.final_price, 2) if item.final_price else 0.0

        for round_record in self.state.round_history:
            for item_id, price in round_record.prices.items():
                price_paths[int(item_id)].append(round(price, 2))

        price_values = list(final_prices.values())
        if price_values:
            return {
                "final_prices": final_prices,
                "price_paths": dict(price_paths),
                "avg_price": round(np.mean(price_values), 2),
                "median_price": round(np.median(price_values), 2),
                "min_price": round(min(price_values), 2),
                "max_price": round(max(price_values), 2),
                "std_price": round(np.std(price_values), 2),
                "total_price": round(sum(price_values), 2)
            }
        return {
            "final_prices": final_prices,
            "price_paths": dict(price_paths),
            "avg_price": 0,
            "median_price": 0,
            "min_price": 0,
            "max_price": 0,
            "std_price": 0,
            "total_price": 0
        }

    def compute_allocation_metrics(self) -> Dict[str, Any]:
        allocation: Dict[int, List[int]] = defaultdict(list)
        unallocated_items = []

        for item in self.state.items:
            if item.final_winner is not None:
                allocation[item.final_winner].append(item.item_id)
            else:
                unallocated_items.append(item.item_id)

        items_per_bidder = [len(items) for items in allocation.values()]

        return {
            "final_allocation": dict(allocation),
            "unallocated_items": unallocated_items,
            "num_allocated_items": sum(items_per_bidder),
            "num_unallocated_items": len(unallocated_items),
            "allocation_rate": round(
                sum(items_per_bidder) / max(1, len(self.state.items)), 3
            ),
            "avg_items_per_winner": round(np.mean(items_per_bidder), 2) if items_per_bidder else 0,
            "max_items_per_bidder": max(items_per_bidder) if items_per_bidder else 0,
            "num_winners": len(allocation)
        }

    def compute_efficiency_metrics(self) -> Dict[str, Any]:
        optimal_social_welfare, optimal_allocation = self._compute_optimal_allocation()

        actual_social_welfare = 0.0
        for bidder in self.state.bidders:
            won_items = [
                item.item_id for item in self.state.items
                if item.final_winner == bidder.bidder_id
            ]
            actual_social_welfare += bidder.get_value(won_items)

        efficiency = (
            actual_social_welfare / optimal_social_welfare
            if optimal_social_welfare > 0
            else 1.0
        )

        return {
            "optimal_social_welfare": round(optimal_social_welfare, 2),
            "actual_social_welfare": round(actual_social_welfare, 2),
            "efficiency": round(efficiency, 4),
            "efficiency_percentage": round(efficiency * 100, 2),
            "deadweight_loss": round(optimal_social_welfare - actual_social_welfare, 2),
            "optimal_allocation": optimal_allocation
        }

    def _compute_optimal_allocation(self) -> Tuple[float, Dict[int, List[int]]]:
        best_value = 0.0
        best_allocation: Dict[int, List[int]] = {}

        items = self.state.get_all_item_ids()
        bidder_ids = self.state.get_all_bidder_ids()

        def search(current_item_idx, allocation, current_value):
            nonlocal best_value, best_allocation

            if current_item_idx >= len(items):
                if current_value > best_value:
                    best_value = current_value
                    best_allocation = {k: v.copy() for k, v in allocation.items()}
                return

            item_id = items[current_item_idx]

            search(current_item_idx + 1, allocation, current_value)

            for bidder_id in bidder_ids:
                current_bundle = allocation.get(bidder_id, [])
                bidder = self.state.get_bidder(bidder_id)
                if bidder:
                    marginal_value = bidder.get_marginal_value(item_id, current_bundle)

                    if marginal_value > 0:
                        if bidder_id not in allocation:
                            allocation[bidder_id] = []
                        allocation[bidder_id].append(item_id)
                        search(current_item_idx + 1, allocation, current_value + marginal_value)
                        allocation[bidder_id].pop()
                        if not allocation[bidder_id]:
                            del allocation[bidder_id]

        search(0, {}, 0.0)
        return best_value, best_allocation

    def compute_revenue_metrics(self) -> Dict[str, Any]:
        total_revenue = 0.0
        reserve_prices = {}
        for item in self.state.items:
            reserve_prices[item.item_id] = item.reserve_price
            if item.final_price:
                total_revenue += item.final_price

        total_reserve = sum(reserve_prices.values())

        bidder_payments = {}
        for bidder in self.state.bidders:
            bidder_payments[bidder.bidder_id] = round(bidder.total_payment, 2)

        return {
            "total_revenue": round(total_revenue, 2),
            "total_reserve": round(total_reserve, 2),
            "revenue_over_reserve": round(total_revenue - total_reserve, 2),
            "revenue_reserve_ratio": round(total_revenue / max(1, total_reserve), 3),
            "bidder_payments": bidder_payments,
            "avg_price_over_reserve": round(
                np.mean([
                    (item.final_price / item.reserve_price if item.reserve_price > 0 else 1.0)
                    for item in self.state.items if item.final_price
                ]) if any(item.final_price for item in self.state.items) else 0,
                3
            )
        }

    def compute_bidder_metrics(self) -> Dict[str, Any]:
        bidder_results = {}

        for bidder in self.state.bidders:
            won_items = [
                item.item_id for item in self.state.items
                if item.final_winner == bidder.bidder_id
            ]
            bundle_value = bidder.get_value(won_items)
            payment = bidder.total_payment
            utility = bundle_value - payment

            total_valuation = sum(bidder.base_values.values())
            complementary_value = sum(bidder.complementary_values.values())

            bidder_results[bidder.bidder_id] = {
                "bidder_name": bidder.name,
                "strategy": bidder.strategy_name,
                "won_items": won_items,
                "num_items_won": len(won_items),
                "total_payment": round(payment, 2),
                "total_value": round(bundle_value, 2),
                "utility": round(utility, 2),
                "profit": round(utility, 2),
                "profit_margin": round(utility / max(1, bundle_value), 3) if bundle_value > 0 else 0,
                "base_value_total": round(total_valuation, 2),
                "complementary_value_total": round(complementary_value, 2),
                "activity_score": round(bidder.activity_score, 3),
                "bids_submitted": sum(
                    len(r.get("bids", [])) for r in bidder.history_bids
                ),
                "budget_utilization": round(payment / max(1, bidder.budget), 4)
            }

        utilities = [b["utility"] for b in bidder_results.values()]
        profits = [b["profit"] for b in bidder_results.values()]

        return {
            "bidder_details": bidder_results,
            "avg_utility": round(np.mean(utilities), 2) if utilities else 0,
            "avg_profit": round(np.mean(profits), 2) if profits else 0,
            "total_utility": round(sum(utilities), 2),
            "total_profit": round(sum(profits), 2),
            "max_profit": round(max(profits), 2) if profits else 0,
            "min_profit": round(min(profits), 2) if profits else 0,
            "profit_std": round(np.std(profits), 2) if profits else 0
        }

    def compute_round_metrics(self) -> Dict[str, Any]:
        if not self.state.round_history:
            return {
                "total_rounds": 0,
                "clock_rounds": 0,
                "supplementary_rounds": 0,
                "bids_per_round": [],
                "excess_demand_per_round": [],
                "price_volatility": 0,
                "convergence_speed": 0
            }

        bids_per_round = []
        excess_demand_per_round = []
        price_changes = []

        prev_prices = {item.item_id: self.state.min_price for item in self.state.items}

        for round_record in self.state.round_history:
            bids_per_round.append(round_record.bids_count)
            max_excess = max(round_record.excess_demand.values(), default=0)
            excess_demand_per_round.append(max_excess)

            change = 0
            for item_id, price in round_record.prices.items():
                change += abs(price - prev_prices.get(int(item_id), 0))
            price_changes.append(change)
            prev_prices = {int(k): v for k, v in round_record.prices.items()}

        clock_rounds = sum(1 for r in self.state.round_history if r.phase == "clock")
        supplementary_rounds = sum(1 for r in self.state.round_history if r.phase == "supplementary")

        zero_excess_round = next(
            (i for i, e in enumerate(excess_demand_per_round) if e <= 0),
            len(excess_demand_per_round)
        )

        return {
            "total_rounds": len(self.state.round_history),
            "clock_rounds": clock_rounds,
            "supplementary_rounds": supplementary_rounds,
            "bids_per_round": bids_per_round,
            "total_bids": sum(bids_per_round),
            "avg_bids_per_round": round(np.mean(bids_per_round), 2) if bids_per_round else 0,
            "excess_demand_per_round": excess_demand_per_round,
            "price_changes_per_round": price_changes,
            "price_volatility": round(np.std(price_changes), 2) if price_changes else 0,
            "convergence_round": zero_excess_round + 1,
            "convergence_speed": round(
                (zero_excess_round + 1) / max(1, len(self.state.round_history)), 3
            )
        }

    def generate_summary_report(self) -> Dict[str, Any]:
        metrics = self.compute_all_metrics()

        return {
            "auction_id": self.state.auction_id,
            "auction_type": self.state.auction_type,
            "status": self.state.status,
            "summary": {
                "total_revenue": metrics["revenue_metrics"]["total_revenue"],
                "efficiency": metrics["efficiency_metrics"]["efficiency"],
                "efficiency_percentage": metrics["efficiency_metrics"]["efficiency_percentage"],
                "num_items": len(self.state.items),
                "num_bidders": len(self.state.bidders),
                "num_winners": metrics["allocation_metrics"]["num_winners"],
                "total_rounds": metrics["round_metrics"]["total_rounds"],
                "allocation_rate": metrics["allocation_metrics"]["allocation_rate"],
                "avg_price": metrics["price_metrics"]["avg_price"],
                "social_welfare": metrics["efficiency_metrics"]["actual_social_welfare"],
                "deadweight_loss": metrics["efficiency_metrics"]["deadweight_loss"]
            },
            "detailed_metrics": metrics,
            "recommendations": self._generate_recommendations(metrics)
        }

    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        recommendations = []

        eff = metrics["efficiency_metrics"]["efficiency"]
        if eff < 0.9:
            recommendations.append(
                f"拍卖效率较低 ({eff*100:.1f}%)，考虑使用组合拍卖格式如CCA"
            )

        rev_ratio = metrics["revenue_metrics"]["revenue_reserve_ratio"]
        if rev_ratio < 1.2:
            recommendations.append(
                f"收益仅为保留价的 {rev_ratio*100:.1f}%，考虑提高起拍价或增加竞争"
            )

        alloc_rate = metrics["allocation_metrics"]["allocation_rate"]
        if alloc_rate < 0.8:
            recommendations.append(
                f"分配率较低 ({alloc_rate*100:.1f}%)，考虑降低起拍价"
            )

        if self.state.auction_type == "smr" and len(self.state.items) > 5:
            recommendations.append(
                "物品数量较多，互补效应明显，建议使用CCA拍卖格式"
            )

        if not recommendations:
            recommendations.append("拍卖表现良好，各项指标均在正常范围内")

        return recommendations
