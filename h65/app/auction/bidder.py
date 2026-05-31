from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np
from itertools import combinations

from app.auction.valuation_generator import ValuationGenerator


@dataclass
class BidderState:
    bidder_id: int
    name: str
    budget: float
    risk_aversion: float
    strategy_name: str
    strategy_params: Dict[str, Any] = field(default_factory=dict)

    base_values: Dict[int, float] = field(default_factory=dict)
    complementary_values: Dict[str, float] = field(default_factory=dict)
    substitute_values: Dict[str, float] = field(default_factory=dict)

    activity_score: float = 1.0
    current_bundle: List[int] = field(default_factory=list)
    total_payment: float = 0.0
    total_value: float = 0.0

    history_bids: List[Dict] = field(default_factory=list)
    history_allocation: List[List[int]] = field(default_factory=list)

    valuation_generator: ValuationGenerator = field(default_factory=ValuationGenerator)

    def get_value(self, bundle: List[int]) -> float:
        return self.valuation_generator.compute_bundle_value(
            bundle, self.base_values, self.complementary_values, self.substitute_values
        )

    def get_marginal_value(self, item: int, current_bundle: List[int]) -> float:
        return self.valuation_generator.compute_marginal_value(
            item, current_bundle, self.base_values, self.complementary_values, self.substitute_values
        )

    def get_individual_value(self, item: int) -> float:
        return self.base_values.get(item, 0.0)

    def get_demand_set(
        self,
        prices: Dict[int, float],
        max_items: Optional[int] = None
    ) -> List[int]:
        item_ids = sorted(prices.keys())
        num_items = len(item_ids)
        best_bundle = []
        best_utility = 0.0

        if max_items is None:
            max_items = num_items

        for r in range(1, min(max_items, num_items) + 1):
            for idx_bundle in combinations(range(num_items), r):
                bundle_list = [item_ids[i] for i in idx_bundle]
                value = self.get_value(bundle_list)
                cost = sum(prices.get(item, 0.0) for item in bundle_list)
                utility = value - cost

                if utility > best_utility + 1e-9:
                    best_utility = utility
                    best_bundle = bundle_list

        return best_bundle

    def update_activity(self, desired_bundle: List[int], activity_rule_weight: float = 0.8):
        if not desired_bundle:
            self.activity_score *= activity_rule_weight
        else:
            self.activity_score = min(1.0, self.activity_score + (1 - activity_rule_weight))
        self.activity_score = max(0.1, self.activity_score)

    def record_bid(self, round_number: int, bids: List[Dict]):
        self.history_bids.append({
            "round": round_number,
            "bids": bids
        })

    def record_allocation(self, allocation: List[int]):
        self.history_allocation.append(allocation)

    def get_utility(self) -> float:
        return self.total_value - self.total_payment

    def can_afford(self, cost: float) -> bool:
        return (self.budget - self.total_payment) >= cost


@dataclass
class AuctionItem:
    item_id: int
    name: str
    reserve_price: float
    bandwidth: Optional[float] = None
    frequency_range: Optional[str] = None
    current_price: float = 0.0
    provisional_winner: Optional[int] = None
    final_winner: Optional[int] = None
    final_price: Optional[float] = None


@dataclass
class RoundInfo:
    round_number: int
    phase: str
    prices: Dict[int, float]
    excess_demand: Dict[int, float]
    provisional_allocation: Dict[int, List[int]]
    bids: List[Dict]
    bidder_activity: Dict[int, float]
    bids_count: int = 0
    total_bid_amount: float = 0.0
    timestamp: float = 0.0


class AuctionState:
    def __init__(
        self,
        auction_id: int,
        auction_type: str,
        items: List[AuctionItem],
        bidders: List[BidderState],
        min_price: float = 10.0,
        max_price: float = 1000.0,
        bid_increment: float = 5.0,
        max_rounds: int = 100,
        activity_rule: bool = True,
        config: Optional[Dict] = None
    ):
        self.auction_id = auction_id
        self.auction_type = auction_type
        self.items = items
        self.bidders = bidders
        self.min_price = min_price
        self.max_price = max_price
        self.bid_increment = bid_increment
        self.max_rounds = max_rounds
        self.activity_rule = activity_rule
        self.config = config or {}

        self.current_round = 0
        self.phase = "clock"
        self.is_completed = False
        self.status = "created"

        self.round_history: List[RoundInfo] = []
        self.bid_history: List[Dict] = []

        for item in self.items:
            item.current_price = self.min_price

        self.item_map = {item.item_id: item for item in self.items}
        self.bidder_map = {bidder.bidder_id: bidder for bidder in self.bidders}

    def get_current_prices(self) -> Dict[int, float]:
        return {item.item_id: item.current_price for item in self.items}

    def get_excess_demand(self, demanded_bundles: Dict[int, List[int]]) -> Dict[int, float]:
        demand_counts: Dict[int, int] = {item.item_id: 0 for item in self.items}

        for bidder_id, bundle in demanded_bundles.items():
            for item_id in bundle:
                demand_counts[item_id] = demand_counts.get(item_id, 0) + 1

        excess_demand = {}
        for item_id, demand in demand_counts.items():
            excess_demand[item_id] = demand - 1

        return excess_demand

    def record_round(
        self,
        prices: Dict[int, float],
        excess_demand: Dict[int, float],
        provisional_allocation: Dict[int, List[int]],
        bids: List[Dict],
        bidder_activity: Dict[int, float]
    ):
        total_amount = sum(bid.get("price", 0) for bid in bids)
        round_info = RoundInfo(
            round_number=self.current_round,
            phase=self.phase,
            prices=prices.copy(),
            excess_demand=excess_demand.copy(),
            provisional_allocation={k: v.copy() for k, v in provisional_allocation.items()},
            bids=bids.copy(),
            bidder_activity=bidder_activity.copy(),
            bids_count=len(bids),
            total_bid_amount=total_amount
        )
        self.round_history.append(round_info)

    def update_prices(self, excess_demand: Dict[int, float]):
        for item_id, excess in excess_demand.items():
            if excess > 0:
                increment = self.bid_increment * (1 + excess / len(self.bidders))
                self.item_map[item_id].current_price = min(
                    self.max_price,
                    self.item_map[item_id].current_price + increment
                )

    def get_item(self, item_id: int) -> Optional[AuctionItem]:
        return self.item_map.get(item_id)

    def get_bidder(self, bidder_id: int) -> Optional[BidderState]:
        return self.bidder_map.get(bidder_id)

    def get_all_item_ids(self) -> List[int]:
        return [item.item_id for item in self.items]

    def get_all_bidder_ids(self) -> List[int]:
        return [bidder.bidder_id for bidder in self.bidders]
