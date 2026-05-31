from typing import List, Dict, Any
from app.strategies.base_strategy import BaseStrategy


class ExampleStrategy(BaseStrategy):
    """
    示例自定义策略。
    基于估值和价格的简单策略，当价值超过价格一定幅度时出价。
    """
    name = "example_strategy"
    description = "Example custom bidding strategy"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params)
        self.margin = self.params.get("margin", 0.15)  # 15% margin
        self.max_items = self.params.get("max_items", 3)

    def decide_bid(
        self,
        bidder,
        auction_state,
        round_number
    ) -> List[Dict[str, Any]]:
        prices = auction_state.get_current_prices()
        bids = []

        max_bid_items = int(bidder.activity_score * self.max_items + 0.5)
        max_bid_items = max(1, max_bid_items)

        demand_bundle = bidder.get_demand_set(prices, max_bid_items)

        for item_id in demand_bundle:
            value = bidder.get_marginal_value(
                item_id,
                [x for x in demand_bundle if x != item_id]
            )
            current_price = prices.get(item_id, 0.0)

            threshold = current_price * (1 + self.margin)
            if value >= threshold and bidder.can_afford(current_price + auction_state.bid_increment):
                bid_price = current_price + auction_state.bid_increment
                bid_price = min(bid_price, value * 0.95)  # 不超过估值的95%

                bids.append({
                    "item_id": item_id,
                    "price": round(bid_price, 2),
                    "quantity": 1
                })

        return bids

    def observe_history(
        self,
        bidder,
        auction_state,
        round_number
    ):
        """根据历史调整参数"""
        if round_number > 5:
            recent_rounds = auction_state.round_history[-5:]
            total_competitor_bids = sum(
                len(r.bids) for r in recent_rounds
            ) / 5

            if total_competitor_bids > len(auction_state.items) * 2:
                self.margin = max(0.05, self.margin - 0.01)
            elif total_competitor_bids < len(auction_state.items):
                self.margin = min(0.3, self.margin + 0.01)
