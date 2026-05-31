from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.market.secondary_market import secondary_market
from app.schemas.schemas import (
    SecondaryListingCreate,
    SecondaryListingSchema,
    SecondaryBidCreate,
    SecondaryBidSchema,
    SecondaryTradeSchema,
    RepackagedBundleCreate,
    RepackagedBundleSchema,
    BundleBidCreate,
    BundleBidSchema,
    MarketSummarySchema,
    BidderInventorySchema
)
from app.models import models

router = APIRouter(prefix="/api/secondary-market", tags=["二次交易市场"])


@router.post("/listings", response_model=SecondaryListingSchema)
async def create_listing(listing_data: SecondaryListingCreate, db: Session = Depends(get_db)):
    seller = db.query(models.Bidder).filter(
        models.Bidder.id == listing_data.seller_id,
        models.Bidder.auction_id == listing_data.auction_id
    ).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found in this auction")

    won_items = [item.id for item in seller.won_items if item.auction_id == listing_data.auction_id]
    for item_id in listing_data.item_ids:
        if item_id not in won_items:
            raise HTTPException(
                status_code=400,
                detail=f"Seller does not own item {item_id}"
            )

    active_listings = db.query(models.SecondaryListing).filter(
        models.SecondaryListing.auction_id == listing_data.auction_id,
        models.SecondaryListing.seller_id == listing_data.seller_id,
        models.SecondaryListing.status == "active"
    ).all()
    for active in active_listings:
        for item_id in listing_data.item_ids:
            if item_id in active.item_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Item {item_id} is already listed in another active listing"
                )

    listing = secondary_market.create_listing(
        auction_id=listing_data.auction_id,
        seller_id=listing_data.seller_id,
        item_ids=listing_data.item_ids,
        ask_price=listing_data.ask_price,
        min_bid_price=listing_data.min_bid_price,
        description=listing_data.description or "",
        duration_hours=listing_data.duration_hours
    )

    db_listing = models.SecondaryListing(
        listing_id=listing.listing_id,
        auction_id=listing.auction_id,
        seller_id=listing.seller_id,
        item_ids=listing.item_ids,
        ask_price=listing.ask_price,
        min_bid_price=listing.min_bid_price,
        description=listing.description,
        status=listing.status,
        expires_at=listing.expires_at
    )
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)

    return db_listing


@router.get("/auction/{auction_id}/listings", response_model=List[SecondaryListingSchema])
async def get_auction_listings(auction_id: int, status: str = "active", db: Session = Depends(get_db)):
    auction = db.query(models.Auction).filter(models.Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    query = db.query(models.SecondaryListing).filter(
        models.SecondaryListing.auction_id == auction_id
    )
    if status != "all":
        query = query.filter(models.SecondaryListing.status == status)

    return query.order_by(models.SecondaryListing.created_at.desc()).all()


@router.get("/listings/{listing_id}", response_model=SecondaryListingSchema)
async def get_listing(listing_id: str, db: Session = Depends(get_db)):
    listing = db.query(models.SecondaryListing).filter(
        models.SecondaryListing.listing_id == listing_id
    ).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@router.post("/listings/{listing_id}/bids", response_model=SecondaryBidSchema)
async def place_listing_bid(listing_id: str, bid_data: SecondaryBidCreate, db: Session = Depends(get_db)):
    listing = db.query(models.SecondaryListing).filter(
        models.SecondaryListing.listing_id == listing_id
    ).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.status != "active":
        raise HTTPException(status_code=400, detail="Listing is not active")

    result = secondary_market.place_listing_bid(listing_id, bid_data.bidder_id, bid_data.price)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    db_bid = models.SecondaryBid(
        listing_id=listing_id,
        bidder_id=bid_data.bidder_id,
        price=bid_data.price
    )
    db.add(db_bid)

    listing.current_highest_bid = bid_data.price
    listing.current_highest_bidder = bid_data.bidder_id

    db.commit()
    db.refresh(db_bid)

    return db_bid


@router.post("/listings/{listing_id}/accept")
async def accept_listing_offer(listing_id: str, db: Session = Depends(get_db)):
    listing = db.query(models.SecondaryListing).filter(
        models.SecondaryListing.listing_id == listing_id
    ).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    result = secondary_market.accept_offer(listing_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    trade = result["trade"]
    db_trade = models.SecondaryTrade(
        trade_id=trade.trade_id,
        auction_id=trade.auction_id,
        seller_id=trade.seller_id,
        buyer_id=trade.buyer_id,
        item_ids=trade.item_ids,
        price=trade.price,
        trade_type=trade.trade_type
    )
    db.add(db_trade)
    listing.status = "sold"
    listing.sold_at = trade.created_at
    db.commit()
    db.refresh(db_trade)

    return {"success": True, "trade_id": trade.trade_id, "trade": db_trade}


@router.post("/listings/{listing_id}/buy-now")
async def buy_now(listing_id: str, bidder_id: int, db: Session = Depends(get_db)):
    listing = db.query(models.SecondaryListing).filter(
        models.SecondaryListing.listing_id == listing_id
    ).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    result = secondary_market.buy_now(listing_id, bidder_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    trade = result["trade"]
    db_trade = models.SecondaryTrade(
        trade_id=trade.trade_id,
        auction_id=trade.auction_id,
        seller_id=trade.seller_id,
        buyer_id=trade.buyer_id,
        item_ids=trade.item_ids,
        price=trade.price,
        trade_type=trade.trade_type
    )
    db.add(db_trade)
    listing.status = "sold"
    listing.sold_at = trade.created_at
    db.commit()
    db.refresh(db_trade)

    return {"success": True, "trade_id": trade.trade_id, "trade": db_trade}


@router.post("/listings/{listing_id}/cancel")
async def cancel_listing(listing_id: str, db: Session = Depends(get_db)):
    listing = db.query(models.SecondaryListing).filter(
        models.SecondaryListing.listing_id == listing_id
    ).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    result = secondary_market.cancel_listing(listing_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    listing.status = "cancelled"
    db.commit()

    return result


@router.post("/bundles", response_model=RepackagedBundleSchema)
async def create_repackaged_bundle(bundle_data: RepackagedBundleCreate, db: Session = Depends(get_db)):
    creator = db.query(models.Bidder).filter(
        models.Bidder.id == bundle_data.creator_id,
        models.Bidder.auction_id == bundle_data.auction_id
    ).first()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found in this auction")

    won_items = [item.id for item in creator.won_items if item.auction_id == bundle_data.auction_id]
    for item_id in bundle_data.item_ids:
        if item_id not in won_items:
            raise HTTPException(
                status_code=400,
                detail=f"Creator does not own item {item_id}"
            )

    bundle = secondary_market.create_repackaged_bundle(
        auction_id=bundle_data.auction_id,
        creator_id=bundle_data.creator_id,
        item_ids=bundle_data.item_ids,
        name=bundle_data.name,
        description=bundle_data.description or "",
        reserve_price=bundle_data.reserve_price
    )

    db_bundle = models.RepackagedBundle(
        bundle_id=bundle.bundle_id,
        auction_id=bundle.auction_id,
        creator_id=bundle.creator_id,
        item_ids=bundle.item_ids,
        name=bundle.name,
        description=bundle.description,
        reserve_price=bundle.reserve_price,
        status=bundle.status
    )
    db.add(db_bundle)
    db.commit()
    db.refresh(db_bundle)

    return db_bundle


@router.get("/auction/{auction_id}/bundles", response_model=List[RepackagedBundleSchema])
async def get_auction_bundles(auction_id: int, status: str = "active", db: Session = Depends(get_db)):
    auction = db.query(models.Auction).filter(models.Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    query = db.query(models.RepackagedBundle).filter(
        models.RepackagedBundle.auction_id == auction_id
    )
    if status != "all":
        query = query.filter(models.RepackagedBundle.status == status)

    return query.order_by(models.RepackagedBundle.created_at.desc()).all()


@router.get("/bundles/{bundle_id}", response_model=RepackagedBundleSchema)
async def get_bundle(bundle_id: str, db: Session = Depends(get_db)):
    bundle = db.query(models.RepackagedBundle).filter(
        models.RepackagedBundle.bundle_id == bundle_id
    ).first()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    return bundle


@router.post("/bundles/{bundle_id}/bids", response_model=BundleBidSchema)
async def place_bundle_bid(bundle_id: str, bid_data: BundleBidCreate, db: Session = Depends(get_db)):
    bundle = db.query(models.RepackagedBundle).filter(
        models.RepackagedBundle.bundle_id == bundle_id
    ).first()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    if bundle.status != "active":
        raise HTTPException(status_code=400, detail="Bundle auction is not active")

    result = secondary_market.place_bundle_bid(bundle_id, bid_data.bidder_id, bid_data.price)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    db_bid = models.BundleBid(
        bundle_id=bundle_id,
        bidder_id=bid_data.bidder_id,
        price=bid_data.price
    )
    db.add(db_bid)

    bundle.current_highest_bid = bid_data.price
    bundle.current_highest_bidder = bid_data.bidder_id

    db.commit()
    db.refresh(db_bid)

    return db_bid


@router.post("/bundles/{bundle_id}/finalize")
async def finalize_bundle_auction(bundle_id: str, db: Session = Depends(get_db)):
    bundle = db.query(models.RepackagedBundle).filter(
        models.RepackagedBundle.bundle_id == bundle_id
    ).first()
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    result = secondary_market.finalize_bundle_auction(bundle_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    trade = result["trade"]
    db_trade = models.SecondaryTrade(
        trade_id=trade.trade_id,
        auction_id=trade.auction_id,
        seller_id=trade.seller_id,
        buyer_id=trade.buyer_id,
        item_ids=trade.item_ids,
        price=trade.price,
        trade_type=trade.trade_type
    )
    db.add(db_trade)
    bundle.status = "sold"
    bundle.finalized_at = trade.created_at
    db.commit()
    db.refresh(db_trade)

    return {"success": True, "trade_id": trade.trade_id, "trade": db_trade}


@router.get("/auction/{auction_id}/summary", response_model=MarketSummarySchema)
async def get_market_summary(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(models.Auction).filter(models.Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    summary = secondary_market.get_market_summary(auction_id)

    db_trades = db.query(models.SecondaryTrade).filter(
        models.SecondaryTrade.auction_id == auction_id
    ).order_by(models.SecondaryTrade.created_at.desc()).limit(10).all()

    summary["recent_trades"] = db_trades

    return summary


@router.get("/auction/{auction_id}/bidder/{bidder_id}/inventory", response_model=BidderInventorySchema)
async def get_bidder_inventory(auction_id: int, bidder_id: int, db: Session = Depends(get_db)):
    bidder = db.query(models.Bidder).filter(
        models.Bidder.id == bidder_id,
        models.Bidder.auction_id == auction_id
    ).first()
    if not bidder:
        raise HTTPException(status_code=404, detail="Bidder not found in this auction")

    won_items = [item.id for item in bidder.won_items if item.auction_id == auction_id]
    inventory = secondary_market.get_bidder_inventory(auction_id, bidder_id, won_items)

    active_listings = db.query(models.SecondaryListing).filter(
        models.SecondaryListing.auction_id == auction_id,
        models.SecondaryListing.seller_id == bidder_id,
        models.SecondaryListing.status == "active"
    ).all()

    purchase_history = db.query(models.SecondaryTrade).filter(
        models.SecondaryTrade.auction_id == auction_id,
        models.SecondaryTrade.buyer_id == bidder_id
    ).all()

    inventory["active_listings"] = active_listings
    inventory["purchase_history"] = purchase_history

    return inventory


@router.get("/auction/{auction_id}/trades", response_model=List[SecondaryTradeSchema])
async def get_auction_trades(auction_id: int, db: Session = Depends(get_db)):
    auction = db.query(models.Auction).filter(models.Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    trades = db.query(models.SecondaryTrade).filter(
        models.SecondaryTrade.auction_id == auction_id
    ).order_by(models.SecondaryTrade.created_at.desc()).all()

    return trades
