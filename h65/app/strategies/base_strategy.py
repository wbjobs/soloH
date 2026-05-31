from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod

from app.auction.bidder import BidderState, AuctionState


class BaseStrategy(ABC):
    name: str = "base"
    description: str = "Base strategy class"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = params or {}

    @abstractmethod
    def decide_bid(
        self,
        bidder: BidderState,
        auction_state: AuctionState,
        round_number: int
    ) -> List[Dict[str, Any]]:
        pass

    def observe_history(
        self,
        bidder: BidderState,
        auction_state: AuctionState,
        round_number: int
    ):
        pass


class TruthfulStrategy(BaseStrategy):
    name = "truthful"
    description = "Bid truthfully based on valuation"

    def decide_bid(
        self,
        bidder: BidderState,
        auction_state: AuctionState,
        round_number: int
    ) -> List[Dict[str, Any]]:
        prices = auction_state.get_current_prices()
        bids = []

        max_items = int(bidder.activity_score * len(auction_state.items) + 0.5)
        max_items = max(1, max_items)

        demand_bundle = bidder.get_demand_set(prices, max_items)

        for item_id in demand_bundle:
            value = bidder.get_marginal_value(item_id, [x for x in demand_bundle if x != item_id])
            price = prices.get(item_id, 0.0)
            if value >= price * (1 - bidder.risk_aversion * 0.1):
                bids.append({
                    "item_id": item_id,
                    "price": min(value, price + auction_state.bid_increment),
                    "quantity": 1
                })

        return bids


class AggressiveStrategy(BaseStrategy):
    name = "aggressive"
    description = "Bid aggressively to win items"

    def decide_bid(
        self,
        bidder: BidderState,
        auction_state: AuctionState,
        round_number: int
    ) -> List[Dict[str, Any]]:
        prices = auction_state.get_current_prices()
        bids = []
        aggression_factor = self.params.get("aggression_factor", 1.3)

        max_items = int(bidder.activity_score * len(auction_state.items) + 0.5)
        max_items = max(1, max_items)

        demand_bundle = bidder.get_demand_set(prices, max_items)

        for item_id in demand_bundle:
            value = bidder.get_marginal_value(item_id, [x for x in demand_bundle if x != item_id])
            price = prices.get(item_id, 0.0)
            if value >= price:
                bid_price = min(
                    value * aggression_factor,
                    price + auction_state.bid_increment * 2
                )
                bid_price = min(bid_price, value)
                bids.append({
                    "item_id": item_id,
                    "price": bid_price,
                    "quantity": 1
                })

        return bids


class ConservativeStrategy(BaseStrategy):
    name = "conservative"
    description = "Bid conservatively, only when prices are low"

    def decide_bid(
        self,
        bidder: BidderState,
        auction_state: AuctionState,
        round_number: int
    ) -> List[Dict[str, Any]]:
        prices = auction_state.get_current_prices()
        bids = []
        margin = self.params.get("margin", 0.5)

        max_items = int(bidder.activity_score * len(auction_state.items) * 0.7 + 0.5)
        max_items = max(1, max_items)

        demand_bundle = bidder.get_demand_set(prices, max_items)

        for item_id in demand_bundle:
            value = bidder.get_marginal_value(item_id, [x for x in demand_bundle if x != item_id])
            price = prices.get(item_id, 0.0)
            if value >= price * (1 + margin):
                bids.append({
                    "item_id": item_id,
                    "price": price + auction_state.bid_increment,
                    "quantity": 1
                })

        return bids


class BundleStrategy(BaseStrategy):
    name = "bundle"
    description = "Focus on complementary item bundles"

    def decide_bid(
        self,
        bidder: BidderState,
        auction_state: AuctionState,
        round_number: int
    ) -> List[Dict[str, Any]]:
        prices = auction_state.get_current_prices()
        bids = []

        best_bundle = []
        best_utility = 0.0

        items = auction_state.get_all_item_ids()
        from itertools import combinations

        for r in range(1, min(4, len(items)) + 1):
            for bundle in combinations(items, r):
                bundle_list = list(bundle)
                value = bidder.get_value(bundle_list)
                cost = sum(prices.get(item, 0.0) for item in bundle_list)
                utility = value - cost

                if utility > best_utility + 1e-9:
                    best_utility = utility
                    best_bundle = bundle_list

        for item_id in best_bundle:
            value = bidder.get_marginal_value(item_id, [x for x in best_bundle if x != item_id])
            price = prices.get(item_id, 0.0)
            if value >= price:
                bids.append({
                    "item_id": item_id,
                    "price": price + auction_state.bid_increment,
                    "quantity": 1
                })

        return bids


class AdaptiveStrategy(BaseStrategy):
    name = "adaptive"
    description = "Adapt strategy based on competitor behavior"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params)
        self.competitor_history: Dict[int, List[Dict]] = {}
        self.round_count = 0

    def observe_history(
        self,
        bidder: BidderState,
        auction_state: AuctionState,
        round_number: int
    ):
        self.round_count = round_number
        if round_number > 0 and auction_state.round_history:
            last_round = auction_state.round_history[-1]
            for bid in last_round.bids:
                bidder_id = bid.get("bidder_id")
                if bidder_id != bidder.bidder_id:
                    if bidder_id not in self.competitor_history:
                        self.competitor_history[bidder_id] = []
                    self.competitor_history[bidder_id].append(bid)

    def decide_bid(
        self,
        bidder: BidderState,
        auction_state: AuctionState,
        round_number: int
    ) -> List[Dict[str, Any]]:
        self.observe_history(bidder, auction_state, round_number)

        prices = auction_state.get_current_prices()
        bids = []

        competitor_activity = self._estimate_competitor_activity()

        aggression = min(1.5, 1.0 + competitor_activity * 0.3)

        max_items = int(bidder.activity_score * len(auction_state.items) + 0.5)
        max_items = max(1, max_items)

        demand_bundle = bidder.get_demand_set(prices, max_items)

        for item_id in demand_bundle:
            value = bidder.get_marginal_value(item_id, [x for x in demand_bundle if x != item_id])
            price = prices.get(item_id, 0.0)

            competition = self._estimate_competition(item_id)
            bid_increment = auction_state.bid_increment * (1 + competition * 0.5)
            bid_price = min(value, price + bid_increment) * aggression
            bid_price = min(bid_price, value)

            if bid_price >= price and bidder.can_afford(bid_price):
                bids.append({
                    "item_id": item_id,
                    "price": bid_price,
                    "quantity": 1
                })

        return bids

    def _estimate_competitor_activity(self) -> float:
        if not self.competitor_history:
            return 0.5

        total_bids = sum(len(bids) for bids in self.competitor_history.values())
        avg_bids_per_round = total_bids / max(1, self.round_count)
        num_competitors = len(self.competitor_history)

        return min(1.0, avg_bids_per_round / max(1, num_competitors))

    def _estimate_competition(self, item_id: int) -> float:
        if not self.competitor_history:
            return 0.3

        total_bids_on_item = 0
        total_rounds = max(1, self.round_count)

        for bids in self.competitor_history.values():
            for bid in bids:
                if bid.get("item_id") == item_id:
                    total_bids_on_item += 1

        return min(1.0, total_bids_on_item / total_rounds)


class BundleBidStrategy(BaseStrategy):
    name = "bundle_bid"
    description = "Submit bundle bids (for CCA)"

    def decide_bid(
        self,
        bidder: BidderState,
        auction_state: AuctionState,
        round_number: int
    ) -> List[Dict[str, Any]]:
        prices = auction_state.get_current_prices()
        bids = []

        items = auction_state.get_all_item_ids()
        from itertools import combinations

        best_bundle = []
        best_utility = 0.0

        for r in range(1, min(len(items), 5) + 1):
            for bundle in combinations(items, r):
                bundle_list = list(bundle)
                value = bidder.get_value(bundle_list)
                cost = sum(prices.get(item, 0.0) for item in bundle_list)
                utility = value - cost

                if utility > best_utility + 1e-9:
                    best_utility = utility
                    best_bundle = bundle_list

        if best_bundle:
            bundle_value = bidder.get_value(best_bundle)
            bids.append({
                "bundle": {item_id: 1 for item_id in best_bundle},
                "price": bundle_value,
                "quantity": 1
            })

        return bids


STRATEGY_REGISTRY = {
    "truthful": TruthfulStrategy,
    "aggressive": AggressiveStrategy,
    "conservative": ConservativeStrategy,
    "bundle": BundleStrategy,
    "adaptive": AdaptiveStrategy,
    "bundle_bid": BundleBidStrategy,
}


def get_strategy(strategy_name: str, params: Optional[Dict[str, Any]] = None) -> BaseStrategy:
    if strategy_name in STRATEGY_REGISTRY:
        return STRATEGY_REGISTRY[strategy_name](params)
    raise ValueError(f"Unknown strategy: {strategy_name}")
