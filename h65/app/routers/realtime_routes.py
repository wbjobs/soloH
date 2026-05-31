from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, Body
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging

from app.core.database import get_db
from app.realtime.websocket_manager import websocket_manager
from app.models import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/realtime", tags=["实时推送"])


@router.websocket("/ws/auction/{auction_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    auction_id: int,
    bidder_id: Optional[int] = Query(None),
    is_admin: bool = Query(False),
    db: Session = Depends(get_db)
):
    auction = db.query(models.Auction).filter(models.Auction.id == auction_id).first()
    if not auction:
        await websocket.close(code=1008, reason=f"Auction {auction_id} not found")
        return

    try:
        await websocket_manager.connect(
            websocket, auction_id,
            bidder_id=bidder_id,
            is_admin=is_admin
        )

        current_round = db.query(models.RoundRecord).filter(
            models.RoundRecord.auction_id == auction_id,
            models.RoundRecord.round_number == auction.current_round
        ).first()

        if current_round:
            round_data = {
                "round_number": current_round.round_number,
                "prices": current_round.prices,
                "excess_demand": current_round.excess_demand,
                "provisional_allocation": current_round.provisional_allocation,
                "bids_count": current_round.bids_count,
                "total_bid_amount": current_round.total_bid_amount,
                "phase": current_round.phase
            }
            await websocket_manager.send_personalized_update(
                auction_id, bidder_id, "current_state", round_data
            )

        while True:
            try:
                data = await websocket.receive_json()
                await handle_client_message(auction_id, bidder_id, data, db)
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket_manager.send_personalized_update(
                    auction_id, bidder_id, "error",
                    {"message": "Invalid JSON format"}
                )
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket_manager.send_personalized_update(
                    auction_id, bidder_id, "error",
                    {"message": str(e)}
                )

    finally:
        await websocket_manager.disconnect(
            websocket, auction_id,
            bidder_id=bidder_id,
            is_admin=is_admin
        )


async def handle_client_message(auction_id: int, bidder_id: Optional[int],
                                data: dict, db: Session):
    message_type = data.get("type", "")

    if message_type == "ping":
        if bidder_id is not None:
            await websocket_manager.send_personalized_update(
                auction_id, bidder_id, "pong",
                {"timestamp": data.get("timestamp")}
            )

    elif message_type == "request_state":
        round_number = data.get("round_number")
        if round_number:
            round_record = db.query(models.RoundRecord).filter(
                models.RoundRecord.auction_id == auction_id,
                models.RoundRecord.round_number == round_number
            ).first()
            if round_record:
                state_data = {
                    "round_number": round_record.round_number,
                    "prices": round_record.prices,
                    "excess_demand": round_record.excess_demand,
                    "provisional_allocation": round_record.provisional_allocation,
                    "bids_count": round_record.bids_count,
                    "total_bid_amount": round_record.total_bid_amount
                }
                if bidder_id is not None:
                    await websocket_manager.send_personalized_update(
                        auction_id, bidder_id, "state_response", state_data
                    )

    elif message_type == "subscribe_bidder":
        target_bidder_id = data.get("bidder_id")
        if bidder_id and bidder_id == target_bidder_id:
            await websocket_manager.send_personalized_update(
                auction_id, bidder_id, "subscription_confirmed",
                {"bidder_id": bidder_id, "message": "Personal feed active"}
            )

    elif message_type == "chat":
        if bidder_id is not None:
            chat_message = {
                "bidder_id": bidder_id,
                "message": data.get("message", ""),
                "timestamp": data.get("timestamp")
            }
            await websocket_manager.broadcast_to_auction(
                auction_id, {
                    "type": "chat_message",
                    "auction_id": auction_id,
                    "data": chat_message
                }
            )


@router.get("/auction/{auction_id}/connections")
async def get_connection_stats(auction_id: int):
    return {
        "auction_id": auction_id,
        "total_connections": websocket_manager.get_connection_count(auction_id),
        "bidder_connections": websocket_manager.get_bidder_count(auction_id),
        "admin_connections": websocket_manager.get_admin_count()
    }


@router.post("/auction/{auction_id}/broadcast")
async def broadcast_message(auction_id: int, message: dict):
    await websocket_manager.broadcast_to_auction(auction_id, message)
    return {"success": True, "message": "Broadcast sent"}


@router.post("/auction/{auction_id}/notify-bidder/{bidder_id}")
async def send_bidder_notification(auction_id: int, bidder_id: int,
                                   update_type: str = Body(..., embed=True),
                                   data: dict = Body(..., embed=True)):
    await websocket_manager.send_personalized_update(auction_id, bidder_id, update_type, data)
    return {"success": True, "message": "Notification sent"}


@router.post("/auction/{auction_id}/broadcast-round")
async def broadcast_round_update(auction_id: int, round_data: dict):
    await websocket_manager.broadcast_round_update(auction_id, round_data)
    return {"success": True}


@router.post("/auction/{auction_id}/broadcast-bid")
async def broadcast_bid_submitted(auction_id: int, bid_data: dict):
    await websocket_manager.broadcast_bid_submitted(auction_id, bid_data)
    return {"success": True}


@router.post("/auction/{auction_id}/broadcast-auction-start")
async def broadcast_auction_start(auction_id: int, auction_info: dict):
    await websocket_manager.broadcast_auction_start(auction_id, auction_info)
    return {"success": True}


@router.post("/auction/{auction_id}/broadcast-auction-end")
async def broadcast_auction_end(auction_id: int, results: dict):
    await websocket_manager.broadcast_auction_end(auction_id, results)
    return {"success": True}


@router.post("/auction/{auction_id}/notify-outbid")
async def notify_outbid(auction_id: int, bidder_id: int,
                        item_id: int, new_price: float):
    await websocket_manager.send_outbid_notification(auction_id, bidder_id, item_id, new_price)
    return {"success": True}


@router.post("/auction/{auction_id}/notify-activity")
async def notify_activity(auction_id: int, bidder_id: int, message: str):
    await websocket_manager.send_activity_reminder(auction_id, bidder_id, message)
    return {"success": True}


@router.post("/auction/{auction_id}/ping")
async def ping_auction_clients(auction_id: int):
    await websocket_manager.ping_clients(auction_id)
    return {"success": True,
            "connection_count": websocket_manager.get_connection_count(auction_id)}
