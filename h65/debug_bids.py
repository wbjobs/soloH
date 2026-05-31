#!/usr/bin/env python
from app.auction.valuation_generator import ValuationGenerator, create_items
from app.strategies.base_strategy import STRATEGY_REGISTRY
from app.auction.bidder import BidderState, AuctionState, AuctionItem

vg = ValuationGenerator(seed=42)
valuations = vg.generate_valuations(3, 2, 'random', base_value_range=(50.0, 200.0))

print('Valuations:')
for i, val in enumerate(valuations):
    print(f'  Bidder {i}: base_values={val["base_values"]}, complementary={val["complementary_values"]}')

items_data = create_items(3, seed=42)
items = []
for i, item in enumerate(items_data):
    items.append(AuctionItem(
        item_id=i,
        name=item['name'],
        description=item['description'],
        bandwidth=item['bandwidth'],
        frequency_range=item['frequency_range'],
        reserve_price=item['reserve_price'],
        current_price=10.0,
        quantity=1
    ))

bidders = []
for i, val in enumerate(valuations):
    bidder = BidderState(
        bidder_id=i,
        name=f'Bidder {i}',
        base_values=val['base_values'],
        complementary_values=val['complementary_values'],
        budget=1000.0,
        risk_aversion=0.5
    )
    strategy = STRATEGY_REGISTRY['truthful']()
    bidder.strategy = strategy
    bidder.strategy_instance = strategy
    bidders.append(bidder)

for bidder in bidders:
    print(f'\nBidder {bidder.bidder_id}:')
    for item_id in range(3):
        value = bidder.get_individual_value(item_id)
        price = 10.0
        print(f'  Item {item_id}: value={value:.2f}, price={price}, should_bid={value > price}')

    prices = {0: 10.0, 1: 10.0, 2: 10.0}
    demand = bidder.get_demand_set(prices)
    print(f'  Demand set: {demand}')

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

print('\n=== Testing Strategy Decision ===')
for bidder in bidders:
    strategy = bidder.strategy_instance
    bids = strategy.decide_bid(bidder, state, 1)
    print(f'Bidder {bidder.bidder_id} bids: {bids}')
