from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from app.core.database import Base


class Auction(Base):
    __tablename__ = "auctions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    auction_type = Column(String(50), nullable=False)
    status = Column(String(50), default="created")
    description = Column(Text, nullable=True)

    min_price = Column(Float, default=10.0)
    max_price = Column(Float, default=1000.0)
    bid_increment = Column(Float, default=5.0)
    max_rounds = Column(Integer, default=100)
    activity_rule = Column(Boolean, default=True)

    current_round = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)

    config = Column(JSON, default={})

    created_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    items = relationship("Item", back_populates="auction", cascade="all, delete-orphan")
    bidders = relationship("Bidder", back_populates="auction", cascade="all, delete-orphan")
    round_records = relationship("RoundRecord", back_populates="auction", cascade="all, delete-orphan")
    bids = relationship("Bid", back_populates="auction", cascade="all, delete-orphan")
    result = relationship("AuctionResult", back_populates="auction", uselist=False, cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    bandwidth = Column(Float, nullable=True)
    frequency_range = Column(String(100), nullable=True)
    reserve_price = Column(Float, default=0.0)
    final_price = Column(Float, nullable=True)
    final_winner = Column(Integer, nullable=True)
    winner_id = Column(Integer, ForeignKey("bidders.id"), nullable=True)

    created_at = Column(DateTime, default=func.now())

    auction = relationship("Auction", back_populates="items")
    valuations = relationship("Valuation", back_populates="item", cascade="all, delete-orphan")
    winner = relationship("Bidder", foreign_keys=[winner_id])


class Bidder(Base):
    __tablename__ = "bidders"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    name = Column(String(100), nullable=False)
    strategy_name = Column(String(100), default="truthful")
    strategy_params = Column(JSON, default={})
    budget = Column(Float, default=1e9)
    risk_aversion = Column(Float, default=0.5)

    activity_score = Column(Float, default=1.0)
    total_payment = Column(Float, default=0.0)
    total_value = Column(Float, default=0.0)

    created_at = Column(DateTime, default=func.now())

    auction = relationship("Auction", back_populates="bidders")
    valuations = relationship("Valuation", back_populates="bidder", cascade="all, delete-orphan")
    bids = relationship("Bid", back_populates="bidder", cascade="all, delete-orphan")
    won_items = relationship("Item", foreign_keys="[Item.winner_id]", back_populates="winner")


class Valuation(Base):
    __tablename__ = "valuations"

    id = Column(Integer, primary_key=True, index=True)
    bidder_id = Column(Integer, ForeignKey("bidders.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    base_value = Column(Float, nullable=False)
    complementary_values = Column(JSON, default={})
    substitute_values = Column(JSON, default={})

    created_at = Column(DateTime, default=func.now())

    bidder = relationship("Bidder", back_populates="valuations")
    item = relationship("Item", back_populates="valuations")


class Bid(Base):
    __tablename__ = "bids"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    bidder_id = Column(Integer, ForeignKey("bidders.id"), nullable=False)
    round_number = Column(Integer, nullable=False)

    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    bundle = Column(JSON, nullable=True)

    price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)
    is_valid = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())

    auction = relationship("Auction", back_populates="bids")
    bidder = relationship("Bidder", back_populates="bids")
    item = relationship("Item")


class RoundRecord(Base):
    __tablename__ = "round_records"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    round_number = Column(Integer, nullable=False)

    prices = Column(JSON, default={})
    excess_demand = Column(JSON, default={})
    provisional_allocation = Column(JSON, default={})
    bidder_activity = Column(JSON, default={})

    bids_count = Column(Integer, default=0)
    total_bid_amount = Column(Float, default=0.0)

    phase = Column(String(50), default="clock")
    created_at = Column(DateTime, default=func.now())

    auction = relationship("Auction", back_populates="round_records")


class AuctionResult(Base):
    __tablename__ = "auction_results"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)

    final_prices = Column(JSON, default={})
    final_allocation = Column(JSON, default={})
    total_revenue = Column(Float, default=0.0)
    efficiency = Column(Float, default=0.0)
    optimal_social_welfare = Column(Float, default=0.0)
    actual_social_welfare = Column(Float, default=0.0)

    bidder_payments = Column(JSON, default={})
    bidder_utilities = Column(JSON, default={})
    bidder_profits = Column(JSON, default={})

    final_round = Column(Integer, default=0)
    auction_duration_seconds = Column(Float, default=0.0)

    created_at = Column(DateTime, default=func.now())

    auction = relationship("Auction", back_populates="result")


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    author = Column(String(100), nullable=True)
    filename = Column(String(255), nullable=False)
    code_hash = Column(String(64), nullable=True)
    is_public = Column(Boolean, default=True)

    total_wins = Column(Integer, default=0)
    total_participations = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    average_profit = Column(Float, default=0.0)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Competition(Base):
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    auction_type = Column(String(50), nullable=False)
    status = Column(String(50), default="created")

    strategy_ids = Column(JSON, default=[])
    config = Column(JSON, default={})
    results = Column(JSON, default={})

    created_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class SecondaryListing(Base):
    __tablename__ = "secondary_listings"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(String(50), unique=True, nullable=False, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("bidders.id"), nullable=False)

    item_ids = Column(JSON, default=[])
    ask_price = Column(Float, nullable=False)
    min_bid_price = Column(Float, nullable=False)
    description = Column(Text, nullable=True)

    status = Column(String(50), default="active")
    current_highest_bid = Column(Float, nullable=True)
    current_highest_bidder = Column(Integer, ForeignKey("bidders.id"), nullable=True)

    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True)
    sold_at = Column(DateTime, nullable=True)

    seller = relationship("Bidder", foreign_keys=[seller_id])
    highest_bidder = relationship("Bidder", foreign_keys=[current_highest_bidder])
    bids = relationship("SecondaryBid", back_populates="listing", cascade="all, delete-orphan")


class SecondaryBid(Base):
    __tablename__ = "secondary_bids"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(String(50), ForeignKey("secondary_listings.listing_id"), nullable=False)
    bidder_id = Column(Integer, ForeignKey("bidders.id"), nullable=False)
    price = Column(Float, nullable=False)
    is_valid = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())

    listing = relationship("SecondaryListing", back_populates="bids")
    bidder = relationship("Bidder")


class SecondaryTrade(Base):
    __tablename__ = "secondary_trades"

    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(String(50), unique=True, nullable=False, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("bidders.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("bidders.id"), nullable=False)

    item_ids = Column(JSON, default=[])
    price = Column(Float, nullable=False)
    trade_type = Column(String(50), default="listing")

    created_at = Column(DateTime, default=func.now())

    seller = relationship("Bidder", foreign_keys=[seller_id])
    buyer = relationship("Bidder", foreign_keys=[buyer_id])


class RepackagedBundle(Base):
    __tablename__ = "repackaged_bundles"

    id = Column(Integer, primary_key=True, index=True)
    bundle_id = Column(String(50), unique=True, nullable=False, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("bidders.id"), nullable=False)

    item_ids = Column(JSON, default=[])
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    reserve_price = Column(Float, nullable=False)

    status = Column(String(50), default="active")
    current_highest_bid = Column(Float, nullable=True)
    current_highest_bidder = Column(Integer, ForeignKey("bidders.id"), nullable=True)

    created_at = Column(DateTime, default=func.now())
    finalized_at = Column(DateTime, nullable=True)

    creator = relationship("Bidder", foreign_keys=[creator_id])
    bids = relationship("BundleBid", back_populates="bundle", cascade="all, delete-orphan")


class BundleBid(Base):
    __tablename__ = "bundle_bids"

    id = Column(Integer, primary_key=True, index=True)
    bundle_id = Column(String(50), ForeignKey("repackaged_bundles.bundle_id"), nullable=False)
    bidder_id = Column(Integer, ForeignKey("bidders.id"), nullable=False)
    price = Column(Float, nullable=False)
    is_valid = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())

    bundle = relationship("RepackagedBundle", back_populates="bids")
    bidder = relationship("Bidder")


class MarketPowerReport(Base):
    __tablename__ = "market_power_reports"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)

    hhi_index = Column(Float, default=0.0)
    concentration_level = Column(String(50))
    overall_risk_level = Column(String(50))

    market_power_scores = Column(JSON, default={})
    winning_shares = Column(JSON, default={})
    collusion_risks = Column(JSON, default=[])
    suspicious_patterns = Column(JSON, default=[])

    created_at = Column(DateTime, default=func.now())
