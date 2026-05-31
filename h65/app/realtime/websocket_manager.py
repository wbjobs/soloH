from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.bidder_connections: Dict[int, Dict[int, WebSocket]] = {}
        self.admin_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, auction_id: int,
                      bidder_id: Optional[int] = None,
                      is_admin: bool = False):
        await websocket.accept()
        async with self._lock:
            if auction_id not in self.active_connections:
                self.active_connections[auction_id] = []
            self.active_connections[auction_id].append(websocket)

            if is_admin:
                self.admin_connections.add(websocket)
                logger.info(f"Admin connected to auction {auction_id}")
            elif bidder_id is not None:
                if auction_id not in self.bidder_connections:
                    self.bidder_connections[auction_id] = {}
                self.bidder_connections[auction_id][bidder_id] = websocket
                logger.info(f"Bidder {bidder_id} connected to auction {auction_id}")

            await self._send_to_websocket(websocket, {
                "type": "connection_established",
                "auction_id": auction_id,
                "bidder_id": bidder_id,
                "timestamp": datetime.now().isoformat(),
                "message": "Connected to auction real-time feed"
            })

    async def disconnect(self, websocket: WebSocket, auction_id: int,
                        bidder_id: Optional[int] = None,
                        is_admin: bool = False):
        async with self._lock:
            if auction_id in self.active_connections:
                if websocket in self.active_connections[auction_id]:
                    self.active_connections[auction_id].remove(websocket)
                if not self.active_connections[auction_id]:
                    del self.active_connections[auction_id]

            if is_admin and websocket in self.admin_connections:
                self.admin_connections.remove(websocket)

            if bidder_id is not None and auction_id in self.bidder_connections:
                if bidder_id in self.bidder_connections[auction_id]:
                    del self.bidder_connections[auction_id][bidder_id]
                if not self.bidder_connections[auction_id]:
                    del self.bidder_connections[auction_id]

        logger.info(f"Connection closed for auction {auction_id}")

    async def broadcast_round_update(self, auction_id: int, round_data: Dict[str, Any]):
        message = {
            "type": "round_update",
            "auction_id": auction_id,
            "timestamp": datetime.now().isoformat(),
            "data": round_data
        }
        await self.broadcast_to_auction(auction_id, message)
        await self.broadcast_to_admins(message)
        logger.info(f"Broadcast round {round_data.get('round_number')} for auction {auction_id}")

    async def broadcast_bid_submitted(self, auction_id: int, bid_data: Dict[str, Any]):
        message = {
            "type": "bid_submitted",
            "auction_id": auction_id,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "bidder_id": bid_data.get("bidder_id"),
                "round_number": bid_data.get("round_number"),
                "item_count": bid_data.get("item_count", 0),
                "total_amount": bid_data.get("total_amount", 0)
            }
        }
        await self.broadcast_to_auction(auction_id, message)
        await self.broadcast_to_admins(message)

    async def broadcast_price_update(self, auction_id: int, price_data: Dict[str, Any]):
        message = {
            "type": "price_update",
            "auction_id": auction_id,
            "timestamp": datetime.now().isoformat(),
            "data": price_data
        }
        await self.broadcast_to_auction(auction_id, message)

    async def broadcast_allocation_update(self, auction_id: int, allocation_data: Dict[str, Any]):
        message = {
            "type": "allocation_update",
            "auction_id": auction_id,
            "timestamp": datetime.now().isoformat(),
            "data": allocation_data
        }
        await self.broadcast_to_auction(auction_id, message)

    async def broadcast_auction_start(self, auction_id: int, auction_info: Dict[str, Any]):
        message = {
            "type": "auction_start",
            "auction_id": auction_id,
            "timestamp": datetime.now().isoformat(),
            "data": auction_info
        }
        await self.broadcast_to_auction(auction_id, message)

    async def broadcast_auction_end(self, auction_id: int, results: Dict[str, Any]):
        message = {
            "type": "auction_end",
            "auction_id": auction_id,
            "timestamp": datetime.now().isoformat(),
            "data": results
        }
        await self.broadcast_to_auction(auction_id, message)
        await self.broadcast_to_admins(message)

    async def broadcast_secondary_market_update(self, auction_id: int, update_data: Dict[str, Any]):
        message = {
            "type": "secondary_market_update",
            "auction_id": auction_id,
            "timestamp": datetime.now().isoformat(),
            "data": update_data
        }
        await self.broadcast_to_auction(auction_id, message)

    async def send_personalized_update(self, auction_id: int, bidder_id: int,
                                       update_type: str, data: Dict[str, Any]):
        async with self._lock:
            if (auction_id in self.bidder_connections and
                bidder_id in self.bidder_connections[auction_id]):
                websocket = self.bidder_connections[auction_id][bidder_id]
                message = {
                    "type": update_type,
                    "auction_id": auction_id,
                    "bidder_id": bidder_id,
                    "timestamp": datetime.now().isoformat(),
                    "data": data
                }
                await self._send_to_websocket(websocket, message)

    async def send_activity_reminder(self, auction_id: int, bidder_id: int,
                                     message: str):
        await self.send_personalized_update(
            auction_id, bidder_id, "activity_reminder",
            {"message": message}
        )

    async def send_outbid_notification(self, auction_id: int, bidder_id: int,
                                       item_id: int, new_price: float):
        await self.send_personalized_update(
            auction_id, bidder_id, "outbid_notification",
            {
                "item_id": item_id,
                "new_price": new_price,
                "message": f"您对物品 {item_id} 的出价已被超过，新价格: ${new_price:.2f}"
            }
        )

    async def broadcast_to_auction(self, auction_id: int, message: Dict[str, Any]):
        async with self._lock:
            if auction_id in self.active_connections:
                disconnected = []
                for websocket in self.active_connections[auction_id]:
                    try:
                        await self._send_to_websocket(websocket, message)
                    except RuntimeError:
                        disconnected.append(websocket)
                    except Exception as e:
                        logger.error(f"Error sending to websocket: {e}")
                        disconnected.append(websocket)

                for ws in disconnected:
                    if ws in self.active_connections[auction_id]:
                        self.active_connections[auction_id].remove(ws)

    async def broadcast_to_admins(self, message: Dict[str, Any]):
        async with self._lock:
            disconnected = []
            for websocket in self.admin_connections:
                try:
                    await self._send_to_websocket(websocket, message)
                except Exception as e:
                    logger.error(f"Error sending to admin: {e}")
                    disconnected.append(websocket)

            for ws in disconnected:
                self.admin_connections.discard(ws)

    async def _send_to_websocket(self, websocket: WebSocket, message: Dict[str, Any]):
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            raise RuntimeError("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            raise RuntimeError(f"Send failed: {e}")

    def get_connection_count(self, auction_id: int) -> int:
        return len(self.active_connections.get(auction_id, []))

    def get_bidder_count(self, auction_id: int) -> int:
        return len(self.bidder_connections.get(auction_id, {}))

    def get_admin_count(self) -> int:
        return len(self.admin_connections)

    async def ping_clients(self, auction_id: Optional[int] = None):
        ping_message = {
            "type": "ping",
            "timestamp": datetime.now().isoformat()
        }
        if auction_id:
            await self.broadcast_to_auction(auction_id, ping_message)
        else:
            for aid in list(self.active_connections.keys()):
                await self.broadcast_to_auction(aid, ping_message)


websocket_manager = WebSocketManager()
