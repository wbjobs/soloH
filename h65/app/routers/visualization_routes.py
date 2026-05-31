from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.auction.auction_service import AuctionService
from app.auction.bidder import AuctionState, BidderState, AuctionItem
from app.visualization.plots import AuctionVisualizer

router = APIRouter(prefix="/visualization", tags=["visualization"])


@router.get("/auctions/{auction_id}")
def get_auction_visualization(
    auction_id: int,
    save_to_disk: bool = Query(True, description="Save plots to static directory"),
    db: Session = Depends(get_db)
):
    service = AuctionService(db)
    db_auction = service.get_auction(auction_id)
    if not db_auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    if not db_auction.is_completed and not db_auction.round_records:
        raise HTTPException(status_code=400, detail="Auction has not started yet")

    state = service._build_auction_state(db_auction)

    for db_item in db_auction.items:
        item = state.get_item(db_item.id)
        if item:
            item.final_winner = db_item.winner_id
            item.final_price = db_item.final_price
            if db_auction.is_completed and db_item.final_price:
                item.current_price = db_item.final_price

    for db_bidder in db_auction.bidders:
        bidder = state.get_bidder(db_bidder.id)
        if bidder:
            bidder.total_payment = db_bidder.total_payment
            bidder.total_value = db_bidder.total_value
            bidder.activity_score = db_bidder.activity_score
            won_items = [item.id for item in db_auction.items if item.winner_id == db_bidder.id]
            bidder.current_bundle = won_items

    visualizer = AuctionVisualizer(state)
    plots = visualizer.generate_all_plots(save_to_disk=save_to_disk)
    interactive_data = visualizer.generate_interactive_data()

    return {
        "auction_id": auction_id,
        "plots": {
            "price_path": f"/static/price_path.png" if save_to_disk else plots["price_path"],
            "excess_demand": f"/static/excess_demand.png" if save_to_disk else plots["excess_demand"],
            "allocation": f"/static/allocation.png" if save_to_disk else plots["allocation"],
            "revenue_efficiency": f"/static/revenue_efficiency.png" if save_to_disk else plots["revenue_efficiency"],
            "bidder_utility": f"/static/bidder_utility.png" if save_to_disk else plots["bidder_utility"],
            "bids_per_round": f"/static/bids_per_round.png" if save_to_disk else plots["bids_per_round"],
            "price_convergence": f"/static/price_convergence.png" if save_to_disk else plots["price_convergence"],
        },
        "plot_data": plots,
        "interactive_data": interactive_data
    }


@router.get("/auctions/{auction_id}/price-path")
def get_price_path_data(auction_id: int, db: Session = Depends(get_db)):
    service = AuctionService(db)
    db_auction = service.get_auction(auction_id)
    if not db_auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    round_records = sorted(db_auction.round_records, key=lambda r: r.round_number)

    price_data = []
    for rr in round_records:
        price_data.append({
            "round": rr.round_number,
            "phase": rr.phase,
            "prices": {str(k): v for k, v in rr.prices.items()},
            "excess_demand": {str(k): v for k, v in rr.excess_demand.items()},
            "bids_count": rr.bids_count
        })

    items = []
    for item in db_auction.items:
        items.append({
            "id": item.id,
            "name": item.name,
            "final_price": item.final_price,
            "winner": item.winner_id
        })

    return {
        "auction_id": auction_id,
        "auction_type": db_auction.auction_type,
        "items": items,
        "price_data": price_data,
        "total_rounds": len(round_records)
    }


@router.post("/auctions/{auction_id}/regenerate-plots")
def regenerate_plots(auction_id: int, db: Session = Depends(get_db)):
    service = AuctionService(db)
    db_auction = service.get_auction(auction_id)
    if not db_auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    result = service.run_auction(auction_id)
    return {
        "message": "Plots regenerated successfully",
        "plots": result.get("plots", {})
    }
