from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import uuid


@dataclass
class SecondaryMarketListing:
    listing_id: str
    auction_id: int
    seller_id: int
    item_ids: List[int]
    ask_price: float
    min_bid_price: float
    description: str
    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    current_highest_bid: Optional[float] = None
    current_highest_bidder: Optional[int] = None
    bids: List[Dict] = field(default_factory=list)


@dataclass
class SecondaryMarketTrade:
    trade_id: str
    auction_id: int
    item_ids: List[int]
    seller_id: int
    buyer_id: int
    price: float
    trade_type: str
    created_at: datetime


@dataclass
class RepackagedBundle:
    bundle_id: str
    auction_id: int
    creator_id: int
    item_ids: List[int]
    name: str
    description: str
    reserve_price: float
    status: str
    created_at: datetime
    bids: List[Dict] = field(default_factory=list)
    current_highest_bid: Optional[float] = None
    current_highest_bidder: Optional[int] = None


class SecondaryMarket:
    def __init__(self):
        self.listings: Dict[str, SecondaryMarketListing] = {}
        self.trades: Dict[str, SecondaryMarketTrade] = {}
        self.repackaged_bundles: Dict[str, RepackagedBundle] = {}
        self.active_bids: Dict[str, List[Dict]] = defaultdict(list)

    def create_listing(self, auction_id: int, seller_id: int, item_ids: List[int],
                       ask_price: float, min_bid_price: Optional[float] = None,
                       description: str = "", duration_hours: int = 72) -> SecondaryMarketListing:
        listing_id = f"list_{uuid.uuid4().hex[:12]}"
        now = datetime.now()

        listing = SecondaryMarketListing(
            listing_id=listing_id,
            auction_id=auction_id,
            seller_id=seller_id,
            item_ids=item_ids.copy(),
            ask_price=ask_price,
            min_bid_price=min_bid_price or ask_price * 0.8,
            description=description,
            status="active",
            created_at=now,
            expires_at=datetime.fromtimestamp(now.timestamp() + duration_hours * 3600)
        )

        self.listings[listing_id] = listing
        return listing

    def place_listing_bid(self, listing_id: str, bidder_id: int, bid_price: float) -> Dict[str, Any]:
        listing = self.listings.get(listing_id)
        if not listing:
            return {"success": False, "message": "Listing not found"}

        if listing.status != "active":
            return {"success": False, "message": "Listing is not active"}

        if listing.expires_at and datetime.now() > listing.expires_at:
            listing.status = "expired"
            return {"success": False, "message": "Listing has expired"}

        if bid_price < listing.min_bid_price:
            return {"success": False,
                    "message": f"Bid price must be at least ${listing.min_bid_price:.2f}"}

        if listing.current_highest_bid and bid_price <= listing.current_highest_bid:
            return {"success": False,
                    "message": f"Bid price must exceed current highest bid of ${listing.current_highest_bid:.2f}"}

        bid = {
            "bidder_id": bidder_id,
            "price": bid_price,
            "timestamp": datetime.now()
        }
        listing.bids.append(bid)
        listing.current_highest_bid = bid_price
        listing.current_highest_bidder = bidder_id

        return {"success": True, "message": "Bid placed successfully", "bid": bid}

    def accept_offer(self, listing_id: str) -> Dict[str, Any]:
        listing = self.listings.get(listing_id)
        if not listing:
            return {"success": False, "message": "Listing not found"}

        if listing.status != "active":
            return {"success": False, "message": "Listing is not active"}

        if not listing.current_highest_bidder:
            return {"success": False, "message": "No bids to accept"}

        trade = self._execute_trade(
            auction_id=listing.auction_id,
            item_ids=listing.item_ids,
            seller_id=listing.seller_id,
            buyer_id=listing.current_highest_bidder,
            price=listing.current_highest_bid,
            trade_type="listing"
        )

        listing.status = "sold"
        return {"success": True, "message": "Trade executed", "trade": trade}

    def buy_now(self, listing_id: str, buyer_id: int) -> Dict[str, Any]:
        listing = self.listings.get(listing_id)
        if not listing:
            return {"success": False, "message": "Listing not found"}

        if listing.status != "active":
            return {"success": False, "message": "Listing is not active"}

        if listing.expires_at and datetime.now() > listing.expires_at:
            listing.status = "expired"
            return {"success": False, "message": "Listing has expired"}

        trade = self._execute_trade(
            auction_id=listing.auction_id,
            item_ids=listing.item_ids,
            seller_id=listing.seller_id,
            buyer_id=buyer_id,
            price=listing.ask_price,
            trade_type="buy_now"
        )

        listing.status = "sold"
        return {"success": True, "message": "Purchase successful", "trade": trade}

    def create_repackaged_bundle(self, auction_id: int, creator_id: int, item_ids: List[int],
                                 name: str, description: str,
                                 reserve_price: float) -> RepackagedBundle:
        bundle_id = f"bundle_{uuid.uuid4().hex[:12]}"

        bundle = RepackagedBundle(
            bundle_id=bundle_id,
            auction_id=auction_id,
            creator_id=creator_id,
            item_ids=item_ids.copy(),
            name=name,
            description=description,
            reserve_price=reserve_price,
            status="active",
            created_at=datetime.now()
        )

        self.repackaged_bundles[bundle_id] = bundle
        return bundle

    def place_bundle_bid(self, bundle_id: str, bidder_id: int, bid_price: float) -> Dict[str, Any]:
        bundle = self.repackaged_bundles.get(bundle_id)
        if not bundle:
            return {"success": False, "message": "Bundle not found"}

        if bundle.status != "active":
            return {"success": False, "message": "Bundle auction is not active"}

        if bid_price < bundle.reserve_price:
            return {"success": False,
                    "message": f"Bid must meet reserve price of ${bundle.reserve_price:.2f}"}

        if bundle.current_highest_bid and bid_price <= bundle.current_highest_bid:
            return {"success": False,
                    "message": f"Bid must exceed current highest bid of ${bundle.current_highest_bid:.2f}"}

        bid = {
            "bidder_id": bidder_id,
            "price": bid_price,
            "timestamp": datetime.now()
        }
        bundle.bids.append(bid)
        bundle.current_highest_bid = bid_price
        bundle.current_highest_bidder = bidder_id

        return {"success": True, "message": "Bid placed successfully"}

    def finalize_bundle_auction(self, bundle_id: str) -> Dict[str, Any]:
        bundle = self.repackaged_bundles.get(bundle_id)
        if not bundle:
            return {"success": False, "message": "Bundle not found"}

        if bundle.status != "active":
            return {"success": False, "message": "Bundle auction already finalized"}

        if not bundle.current_highest_bidder:
            bundle.status = "unsold"
            return {"success": False, "message": "No valid bids received"}

        trade = self._execute_trade(
            auction_id=bundle.auction_id,
            item_ids=bundle.item_ids,
            seller_id=bundle.creator_id,
            buyer_id=bundle.current_highest_bidder,
            price=bundle.current_highest_bid,
            trade_type="bundle"
        )

        bundle.status = "sold"
        return {"success": True, "message": "Bundle auction finalized", "trade": trade}

    def _execute_trade(self, auction_id: int, item_ids: List[int],
                       seller_id: int, buyer_id: int, price: float,
                       trade_type: str) -> SecondaryMarketTrade:
        trade_id = f"trade_{uuid.uuid4().hex[:12]}"

        trade = SecondaryMarketTrade(
            trade_id=trade_id,
            auction_id=auction_id,
            item_ids=item_ids.copy(),
            seller_id=seller_id,
            buyer_id=buyer_id,
            price=price,
            trade_type=trade_type,
            created_at=datetime.now()
        )

        self.trades[trade_id] = trade
        return trade

    def get_auction_listings(self, auction_id: int) -> List[SecondaryMarketListing]:
        return [l for l in self.listings.values() if l.auction_id == auction_id]

    def get_auction_trades(self, auction_id: int) -> List[SecondaryMarketTrade]:
        return [t for t in self.trades.values() if t.auction_id == auction_id]

    def get_auction_bundles(self, auction_id: int) -> List[RepackagedBundle]:
        return [b for b in self.repackaged_bundles.values() if b.auction_id == auction_id]

    def get_seller_listings(self, seller_id: int) -> List[SecondaryMarketListing]:
        return [l for l in self.listings.values() if l.seller_id == seller_id]

    def get_buyer_trades(self, buyer_id: int) -> List[SecondaryMarketTrade]:
        return [t for t in self.trades.values() if t.buyer_id == buyer_id]

    def cancel_listing(self, listing_id: str) -> Dict[str, Any]:
        listing = self.listings.get(listing_id)
        if not listing:
            return {"success": False, "message": "Listing not found"}

        if listing.status != "active":
            return {"success": False, "message": "Only active listings can be cancelled"}

        listing.status = "cancelled"
        return {"success": True, "message": "Listing cancelled"}

    def get_market_summary(self, auction_id: int) -> Dict[str, Any]:
        listings = self.get_auction_listings(auction_id)
        trades = self.get_auction_trades(auction_id)
        bundles = self.get_auction_bundles(auction_id)

        active_listings = [l for l in listings if l.status == "active"]
        total_trade_volume = sum(t.price for t in trades)
        avg_trade_price = total_trade_volume / len(trades) if trades else 0.0

        return {
            "auction_id": auction_id,
            "total_listings": len(listings),
            "active_listings": len(active_listings),
            "total_trades": len(trades),
            "total_trade_volume": round(total_trade_volume, 2),
            "average_trade_price": round(avg_trade_price, 2),
            "repackaged_bundles": len(bundles),
            "active_bundles": len([b for b in bundles if b.status == "active"]),
            "items_in_market": len(set(i for l in active_listings for i in l.item_ids)),
            "recent_trades": sorted(trades, key=lambda t: t.created_at, reverse=True)[:10]
        }

    def get_bidder_inventory(self, auction_id: int, bidder_id: int,
                             won_items: List[int]) -> Dict[str, Any]:
        purchased_items = []
        sold_items = []

        for trade in self.get_auction_trades(auction_id):
            if trade.buyer_id == bidder_id:
                purchased_items.extend(trade.item_ids)
            if trade.seller_id == bidder_id:
                sold_items.extend(trade.item_ids)

        current_inventory = [i for i in won_items if i not in sold_items]
        current_inventory.extend(purchased_items)

        active_listings = [l for l in self.get_seller_listings(bidder_id)
                          if l.auction_id == auction_id and l.status == "active"]

        return {
            "bidder_id": bidder_id,
            "original_won_items": won_items,
            "purchased_items": purchased_items,
            "sold_items": sold_items,
            "current_inventory": current_inventory,
            "active_listings": active_listings,
            "purchase_history": [t for t in self.get_buyer_trades(bidder_id)
                                if t.auction_id == auction_id]
        }


secondary_market = SecondaryMarket()
