from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import (
    AuctionCreate, Auction, AuctionDetail, AuctionStateResponse,
    BidRequest, Bid, RoundRecord, AuctionResult
)
from app.auction.auction_service import AuctionService

router = APIRouter(prefix="/auctions", tags=["auctions"])


@router.post("", response_model=Auction, status_code=201)
def create_auction(
    auction_data: AuctionCreate,
    seed: Optional[int] = Query(None, description="Random seed for reproducibility"),
    db: Session = Depends(get_db)
):
    service = AuctionService(db)
    try:
        auction = service.create_auction(auction_data, seed=seed)
        return auction
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[Auction])
def list_auctions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    service = AuctionService(db)
    return service.list_auctions(skip=skip, limit=limit)


@router.get("/{auction_id}", response_model=AuctionDetail)
def get_auction(auction_id: int, db: Session = Depends(get_db)):
    service = AuctionService(db)
    auction = service.get_auction(auction_id)
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    return auction


@router.delete("/{auction_id}")
def delete_auction(auction_id: int, db: Session = Depends(get_db)):
    service = AuctionService(db)
    if not service.delete_auction(auction_id):
        raise HTTPException(status_code=404, detail="Auction not found")
    return {"message": "Auction deleted successfully"}


@router.post("/{auction_id}/run")
def run_auction(
    auction_id: int,
    verbose: bool = Query(False, description="Print progress to console"),
    db: Session = Depends(get_db)
):
    service = AuctionService(db)
    try:
        result = service.run_auction(auction_id, verbose=verbose)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{auction_id}/step")
def step_auction(auction_id: int, db: Session = Depends(get_db)):
    service = AuctionService(db)
    try:
        result = service.step_auction(auction_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{auction_id}/state", response_model=AuctionStateResponse)
def get_auction_state(auction_id: int, db: Session = Depends(get_db)):
    service = AuctionService(db)
    try:
        state = service.get_auction_state(auction_id)
        auction = service.get_auction(auction_id)
        if not auction:
            raise HTTPException(status_code=404, detail="Auction not found")

        round_records = sorted(auction.round_records, key=lambda r: r.round_number)
        bids = sorted(auction.bids, key=lambda b: (b.round_number, b.bidder_id))

        return AuctionStateResponse(
            auction_id=auction_id,
            status=state["status"],
            current_round=state["current_round"],
            is_completed=state["is_completed"],
            prices=state["prices"],
            provisional_allocation=state["provisional_allocation"],
            excess_demand=state["excess_demand"],
            round_records=round_records,
            bids=bids,
            result=auction.result
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{auction_id}/rounds", response_model=List[RoundRecord])
def get_round_records(
    auction_id: int,
    db: Session = Depends(get_db)
):
    service = AuctionService(db)
    auction = service.get_auction(auction_id)
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    return sorted(auction.round_records, key=lambda r: r.round_number)


@router.get("/{auction_id}/bids", response_model=List[Bid])
def get_bids(
    auction_id: int,
    round_number: Optional[int] = Query(None, description="Filter by round number"),
    bidder_id: Optional[int] = Query(None, description="Filter by bidder ID"),
    db: Session = Depends(get_db)
):
    service = AuctionService(db)
    auction = service.get_auction(auction_id)
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    bids = auction.bids
    if round_number is not None:
        bids = [b for b in bids if b.round_number == round_number]
    if bidder_id is not None:
        bids = [b for b in bids if b.bidder_id == bidder_id]

    return sorted(bids, key=lambda b: (b.round_number, b.bidder_id))


@router.get("/{auction_id}/result")
def get_auction_result(auction_id: int, db: Session = Depends(get_db)):
    service = AuctionService(db)
    auction = service.get_auction(auction_id)
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    if not auction.is_completed:
        raise HTTPException(status_code=400, detail="Auction not completed yet")

    try:
        result = service.run_auction(auction_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{auction_id}/bids")
def submit_bid(
    auction_id: int,
    bid_request: BidRequest,
    db: Session = Depends(get_db)
):
    from app.models.models import Bid as DBBid

    service = AuctionService(db)
    auction = service.get_auction(auction_id)
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    if auction.is_completed:
        raise HTTPException(status_code=400, detail="Auction already completed")

    bids_created = []
    for bid_data in bid_request.bids:
        db_bid = DBBid(
            auction_id=auction_id,
            bidder_id=bid_request.bidder_id,
            round_number=bid_request.round_number,
            item_id=bid_data.item_id,
            bundle=bid_data.bundle,
            price=bid_data.price,
            quantity=bid_data.quantity,
            is_valid=True
        )
        db.add(db_bid)
        bids_created.append(db_bid)

    db.commit()
    for bid in bids_created:
        db.refresh(bid)

    return {"message": "Bids submitted successfully", "bids": bids_created}
