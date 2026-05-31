from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


class AuctionType(str, Enum):
    SMR = "smr"
    CCA = "cca"


class AuctionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    bandwidth: Optional[float] = None
    frequency_range: Optional[str] = None
    reserve_price: float = Field(default=0.0, ge=0)


class ItemCreate(ItemBase):
    pass


class Item(ItemBase):
    id: int
    auction_id: int
    final_price: Optional[float] = None
    winner_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ValuationBase(BaseModel):
    base_value: float = Field(..., gt=0)
    complementary_values: Dict[str, float] = Field(default_factory=dict)
    substitute_values: Dict[str, float] = Field(default_factory=dict)


class ValuationCreate(ValuationBase):
    item_id: int


class Valuation(ValuationBase):
    id: int
    bidder_id: int
    item_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BidderBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    strategy_name: str = "truthful"
    strategy_params: Dict[str, Any] = Field(default_factory=dict)
    budget: float = Field(default=1e9, gt=0)
    risk_aversion: float = Field(default=0.5, ge=0, le=1)


class BidderCreate(BidderBase):
    valuations: List[ValuationCreate] = Field(default_factory=list)
    valuation_model: Optional[str] = "random"
    valuation_params: Dict[str, Any] = Field(default_factory=dict)


class Bidder(BidderBase):
    id: int
    auction_id: int
    activity_score: float = 1.0
    total_payment: float = 0.0
    total_value: float = 0.0
    valuations: List[Valuation] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


class AuctionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    auction_type: AuctionType = AuctionType.SMR
    description: Optional[str] = None
    min_price: float = Field(default=10.0, gt=0)
    max_price: float = Field(default=1000.0, gt=0)
    bid_increment: float = Field(default=5.0, gt=0)
    max_rounds: int = Field(default=100, gt=0)
    activity_rule: bool = True
    pricing_rule: str = Field(default="core_selecting", description="Pricing rule: first_price, second_price, vcg, core_selecting")
    reserve_strategy: str = Field(default="public", description="Reserve price strategy: public, dynamic, secret")
    reserve_price_multiplier: float = Field(default=0.0, description="Reserve price as fraction of mean valuation (0 = no reserve)")
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('max_price')
    def max_price_gt_min(cls, v, values):
        if v <= values.data.get('min_price', 0):
            raise ValueError('max_price must be greater than min_price')
        return v

    @field_validator('pricing_rule')
    def validate_pricing_rule(cls, v):
        valid_rules = ["first_price", "second_price", "vcg", "core_selecting"]
        if v not in valid_rules:
            raise ValueError(f"pricing_rule must be one of {valid_rules}")
        return v

    @field_validator('reserve_strategy')
    def validate_reserve_strategy(cls, v):
        valid_strategies = ["public", "dynamic", "secret"]
        if v not in valid_strategies:
            raise ValueError(f"reserve_strategy must be one of {valid_strategies}")
        return v


class AuctionCreate(AuctionBase):
    items: List[ItemCreate] = Field(default_factory=list)
    bidders: List[BidderCreate] = Field(default_factory=list)
    num_items: Optional[int] = None
    num_bidders: Optional[int] = None
    bidder_strategies: Optional[List[str]] = None
    valuation_model: Optional[str] = None
    valuation_params: Optional[Dict[str, Any]] = None


class Auction(AuctionBase):
    id: int
    status: str = "created"
    current_round: int = 0
    is_completed: bool = False
    items: List[Item] = Field(default_factory=list)
    bidders: List[Bidder] = Field(default_factory=list)
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BidBase(BaseModel):
    bidder_id: int
    item_id: Optional[int] = None
    bundle: Optional[Dict[int, int]] = None
    price: float = Field(..., gt=0)
    quantity: int = Field(default=1, gt=0)


class BidCreate(BidBase):
    round_number: int


class Bid(BidBase):
    id: int
    auction_id: int
    round_number: int
    is_valid: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class RoundRecordBase(BaseModel):
    round_number: int
    prices: Dict[int, float] = Field(default_factory=dict)
    excess_demand: Dict[int, float] = Field(default_factory=dict)
    provisional_allocation: Dict[int, List[int]] = Field(default_factory=dict)
    bidder_activity: Dict[int, float] = Field(default_factory=dict)
    bids_count: int = 0
    total_bid_amount: float = 0.0
    phase: str = "clock"


class RoundRecord(RoundRecordBase):
    id: int
    auction_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AuctionResultBase(BaseModel):
    final_prices: Dict[int, float] = Field(default_factory=dict)
    final_allocation: Dict[int, List[int]] = Field(default_factory=dict)
    total_revenue: float = 0.0
    efficiency: float = 0.0
    optimal_social_welfare: float = 0.0
    actual_social_welfare: float = 0.0
    bidder_payments: Dict[int, float] = Field(default_factory=dict)
    bidder_utilities: Dict[int, float] = Field(default_factory=dict)
    bidder_profits: Dict[int, float] = Field(default_factory=dict)
    final_round: int = 0
    auction_duration_seconds: float = 0.0


class AuctionResult(AuctionResultBase):
    id: int
    auction_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AuctionDetail(Auction):
    bids: List[Bid] = Field(default_factory=list)
    round_records: List[RoundRecord] = Field(default_factory=list)
    result: Optional[AuctionResult] = None


class StrategyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    author: Optional[str] = None
    is_public: bool = True


class StrategyCreate(StrategyBase):
    code: str


class Strategy(StrategyBase):
    id: int
    filename: str
    code_hash: Optional[str] = None
    total_wins: int = 0
    total_participations: int = 0
    win_rate: float = 0.0
    average_profit: float = 0.0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StrategyResponse(Strategy):
    code: Optional[str] = None


class CompetitionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    auction_type: AuctionType = AuctionType.SMR
    strategy_ids: List[int] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)


class CompetitionCreate(CompetitionBase):
    num_rounds: int = Field(default=1, gt=0)


class Competition(CompetitionBase):
    id: int
    status: str = "created"
    results: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BidRequest(BaseModel):
    bidder_id: int
    round_number: int
    bids: List[BidBase]


class AuctionStateResponse(BaseModel):
    auction_id: int
    status: str
    current_round: int
    is_completed: bool
    prices: Dict[int, float]
    provisional_allocation: Dict[int, List[int]]
    excess_demand: Dict[int, float]
    round_records: List[RoundRecord]
    bids: List[Bid]
    result: Optional[AuctionResult] = None


class StrategyUploadResponse(BaseModel):
    strategy_id: int
    name: str
    message: str


class CompetitionResultResponse(BaseModel):
    competition_id: int
    status: str
    results: Dict[str, Any]
    rankings: List[Dict[str, Any]]


class CollusionRiskSchema(BaseModel):
    bidder_pair: List[int]
    risk_score: float
    risk_level: str
    evidence: List[str]


class MarketPowerAnalysisSchema(BaseModel):
    hhi_index: float
    concentration_level: str
    collusion_risks: List[CollusionRiskSchema]
    market_power_scores: Dict[int, float]
    winning_bidder_shares: Dict[int, float]
    suspicious_patterns: List[str]
    overall_risk_level: str


class MarketPowerReportSchema(BaseModel):
    id: int
    auction_id: int
    hhi_index: float
    concentration_level: Optional[str] = None
    overall_risk_level: Optional[str] = None
    market_power_scores: Dict[int, float] = Field(default_factory=dict)
    winning_shares: Dict[int, float] = Field(default_factory=dict)
    collusion_risks: List[Dict[str, Any]] = Field(default_factory=list)
    suspicious_patterns: List[str] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


class SecondaryListingBase(BaseModel):
    auction_id: int
    seller_id: int
    item_ids: List[int]
    ask_price: float = Field(..., gt=0)
    min_bid_price: Optional[float] = None
    description: Optional[str] = None
    duration_hours: int = Field(default=72, gt=0)


class SecondaryListingCreate(SecondaryListingBase):
    pass


class SecondaryListingSchema(BaseModel):
    id: int
    listing_id: str
    auction_id: int
    seller_id: int
    item_ids: List[int]
    ask_price: float
    min_bid_price: float
    description: Optional[str] = None
    status: str
    current_highest_bid: Optional[float] = None
    current_highest_bidder: Optional[int] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SecondaryBidBase(BaseModel):
    listing_id: str
    bidder_id: int
    price: float = Field(..., gt=0)


class SecondaryBidCreate(SecondaryBidBase):
    pass


class SecondaryBidSchema(BaseModel):
    id: int
    listing_id: str
    bidder_id: int
    price: float
    is_valid: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SecondaryTradeSchema(BaseModel):
    id: int
    trade_id: str
    auction_id: int
    seller_id: int
    buyer_id: int
    item_ids: List[int]
    price: float
    trade_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class RepackagedBundleBase(BaseModel):
    auction_id: int
    creator_id: int
    item_ids: List[int]
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    reserve_price: float = Field(..., gt=0)


class RepackagedBundleCreate(RepackagedBundleBase):
    pass


class RepackagedBundleSchema(BaseModel):
    id: int
    bundle_id: str
    auction_id: int
    creator_id: int
    item_ids: List[int]
    name: str
    description: Optional[str] = None
    reserve_price: float
    status: str
    current_highest_bid: Optional[float] = None
    current_highest_bidder: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BundleBidBase(BaseModel):
    bundle_id: str
    bidder_id: int
    price: float = Field(..., gt=0)


class BundleBidCreate(BundleBidBase):
    pass


class BundleBidSchema(BaseModel):
    id: int
    bundle_id: str
    bidder_id: int
    price: float
    is_valid: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MarketSummarySchema(BaseModel):
    auction_id: int
    total_listings: int
    active_listings: int
    total_trades: int
    total_trade_volume: float
    average_trade_price: float
    repackaged_bundles: int
    active_bundles: int
    items_in_market: int
    recent_trades: List[SecondaryTradeSchema]


class BidderInventorySchema(BaseModel):
    bidder_id: int
    original_won_items: List[int]
    purchased_items: List[int]
    sold_items: List[int]
    current_inventory: List[int]
    active_listings: List[SecondaryListingSchema]
    purchase_history: List[SecondaryTradeSchema]


class WebSocketMessage(BaseModel):
    type: str
    auction_id: int
    timestamp: str
    data: Dict[str, Any]
