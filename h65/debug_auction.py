#!/usr/bin/env python
from app.auction.valuation_generator import ValuationGenerator, create_items
from app.strategies.base_strategy import STRATEGY_REGISTRY, TruthfulStrategy
from app.auction.bidder import BidderState, AuctionState, AuctionItem
from app.auction.smr_auction import SMRAuction

# Create test data
vg = ValuationGenerator(seed=42)
valuations = vg.generate_valuations(3, 2, 'random', base_value_range=(50.0, 200.0))

print('=== 估值数据 ===')
for i, val in enumerate(valuations):
    print(f'Bidder {i}: base_values={val["base_values"]}')
    print(f'          complementary={val["complementary_values"]}')

# Create items using actual AuctionItem constructor
# First check what fields it has
print('\n=== AuctionItem 字段检查 ===')
import dataclasses
fields = [f.name for f in dataclasses.fields(AuctionItem)]
print(f'AuctionItem fields: {fields}')

items_data = create_items(3, seed=42)
items = []
for i, item in enumerate(items_data):
    items.append(AuctionItem(
        item_id=i,
        name=item['name'],
        bandwidth=float(item['bandwidth']),
        frequency_range=item['frequency_range'],
        reserve_price=float(item['reserve_price']),
        current_price=10.0,
        quantity=1
    ))

print('\n=== 竞标者创建 ===')
bidders = []
strategy_names = ['truthful', 'aggressive']
for i, val in enumerate(valuations):
    bidder = BidderState(
        bidder_id=i,
        name=f'Bidder {i}',
        base_values=val['base_values'],
        complementary_values=val['complementary_values'],
        budget=1000.0,
        risk_aversion=0.5,
        strategy_name=strategy_names[i],
        strategy_params={}
    )
    bidders.append(bidder)
    print(f'Bidder {i}: strategy={bidder.strategy_name}, activity_score={bidder.activity_score}')
    for item_id in range(3):
        v = bidder.get_individual_value(item_id)
        print(f'  Item {item_id}: value={v:.2f}')

print('\n=== 拍卖状态创建 ===')
state = AuctionState(
    auction_id=1,
    auction_type='smr',
    items=items,
    bidders=bidders,
    min_price=10.0,
    max_price=500.0,
    bid_increment=5.0,
    max_rounds=50,
    activity_rule=True
)
print(f'初始价格: {state.get_current_prices()}')

print('\n=== SMR拍卖初始化 ===')
smr = SMRAuction(state)
print('Bidder strategies:')
for bidder_id, strategy in smr.bidder_strategies.items():
    print(f'  Bidder {bidder_id}: {type(strategy).__name__}')

print('\n=== 测试单轮出价 ===')
state.current_round = 1
round_result = smr._run_round()
print(f'出价数量: {len(round_result["bids"])}')
print(f'出价详情: {round_result["bids"]}')
print(f'超额需求: {round_result["excess_demand"]}')
print(f'需求组合: {round_result["demanded_bundles"]}')

if len(round_result["bids"]) == 0:
    print('\n=== 调试: 为什么没有出价? ===')
    for bidder in state.bidders:
        print(f'\nBidder {bidder.bidder_id}:')
        print(f'  activity_score: {bidder.activity_score}')
        print(f'  检查: {bidder.activity_score < 0.1 and state.activity_rule}')

        strategy = smr.bidder_strategies[bidder.bidder_id]
        prices = state.get_current_prices()
        print(f'  当前价格: {prices}')

        max_items = int(bidder.activity_score * len(state.items) + 0.5)
        max_items = max(1, max_items)
        print(f'  max_items: {max_items}')

        demand = bidder.get_demand_set(prices, max_items)
        print(f'  需求集: {demand}')

        for item_id in demand:
            value = bidder.get_marginal_value(item_id, [x for x in demand if x != item_id])
            price = prices.get(item_id, 0.0)
            risk_factor = 1 - bidder.risk_aversion * 0.1
            threshold = price * risk_factor
            print(f'    Item {item_id}: value={value:.2f}, price={price}, threshold={threshold:.2f}, should_bid={value >= threshold}')

            bid_price = min(value, price + state.bid_increment)
            min_required = price + state.bid_increment * 0.9
            print(f'    出价: {bid_price:.2f}, 最低要求: {min_required:.2f}, 验证通过: {bid_price >= min_required}')
            print(f'    预算检查: {bidder.can_afford(bid_price)}')
