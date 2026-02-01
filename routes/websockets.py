from __future__ import annotations

import os
from typing import TYPE_CHECKING

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from helpers import ClickHouseManager, ConnectionManager
    from webserver import Application


class WebsocketManager:
    def __init__(self, parent: Application):
        self.parent: Application = parent
        self.manager: ConnectionManager = parent.manager
        self.db: ClickHouseManager = parent.db
        self.ws_router = APIRouter(prefix="/ws")

    def setup_routes(self):
        self.ws_router.add_api_websocket_route("/alerts", self.websocket_alerts_unified)
        self.ws_router.add_api_websocket_route("/alerts/{item_id}", self.websocket_alerts_unified)
        self.ws_router.add_api_websocket_route("/price_table", self.websocket_price_table_item)
        self.ws_router.add_api_websocket_route("/realtime", self.websocket_realtime_item)
        self.ws_router.add_api_websocket_route("/realtime/{item_id}", self.websocket_realtime_item)
        self.ws_router.add_api_websocket_route("/alchemy", self.websocket_alchemy)
        self.ws_router.add_api_websocket_route("/alchemy/{item_id}", self.websocket_alchemy)

    async def websocket_alerts_unified(
        self,
        websocket: WebSocket,
        item_id: str = "all",
        threshold: float = Query(float(os.environ.get("DEFAULT_FALL_THRESHOLD", 20.0))),
        direction: str = Query("fall"),
        include_members: bool = Query(False),
    ):
        actual_threshold = max(threshold, float(os.environ.get("MIN_ALLOWED_THRESHOLD", 5.0)))
        should_include_members = True if item_id != "all" else include_members

        await self.manager.connect(
            websocket,
            category="alerts",
            item_id=item_id,
            threshold=actual_threshold,
            direction=direction,
        )

        try:
            raw_alerts = await self.db.get_price_alerts(min_threshold=actual_threshold, direction=direction)

            formatted_alerts = []
            volume_threshold = 100

            for alert in raw_alerts:
                if not should_include_members and alert.members:
                    continue
                if alert.total_volume_5m <= volume_threshold:
                    continue
                change_pct = alert.change_pct
                if (
                    (direction == "rise" and change_pct <= actual_threshold)
                    or (direction == "fall" and change_pct >= -actual_threshold)
                    or (direction == "both" and abs(change_pct) < actual_threshold)
                ):
                    continue

                formatted_alerts.append(alert)

            if item_id == "all":
                response = {
                    "type": "snapshot",
                    "direction_filter": direction,
                    "data": [a.to_dict() for a in formatted_alerts],
                }

            elif specific_item := [a.to_dict() for a in formatted_alerts if str(a.item_id) == item_id]:
                response = {
                    "type": "snapshot",
                    "message": f"Status atual para o item {item_id}",
                    "filter": {"threshold": actual_threshold, "direction": direction},
                    "data": specific_item[0],
                }
            else:
                response = {
                    "type": "info",
                    "message": f"O item {item_id} não atende aos critérios de alerta no momento.",
                    "item_id": item_id,
                }
            await websocket.send_json(response)

            while True:
                await websocket.receive_text()

        except WebSocketDisconnect:
            self.manager.disconnect(
                websocket,
                category="alerts",
                item_id=item_id,
            )

    async def websocket_price_table_item(self, websocket: WebSocket):
        await self.manager.connect(websocket, category="price_table", item_id="all")

        try:
            items_data = await self.db.get_realtime_items(None)
            if items_data:
                payload = [item.to_dict() for item in items_data]
                await websocket.send_json({"type": "snapshot", "data": payload})

            while True:
                await websocket.receive_text()

        except WebSocketDisconnect:
            self.manager.disconnect(websocket, category="price_table", item_id="all")

    async def websocket_realtime_item(self, websocket: WebSocket, item_id: str = "all"):
        await self.manager.connect(websocket, category="realtime", item_id=item_id)

        try:
            if item_id.isnumeric():
                item_data = await self.db.get_item_realtime_status(item_id)
                if item_data:
                    await websocket.send_json(
                        {
                            "type": "snapshot",
                            "data": item_data.to_dict(),
                        }
                    )
            elif item_id == "all" or not item_id:
                items_data = await self.db.get_items_realtime_status(None)
                if items_data:
                    payload = [item.to_dict() for item in items_data]
                    await websocket.send_json({"type": "snapshot", "data": payload})

            while True:
                await websocket.receive_text()

        except WebSocketDisconnect:
            self.manager.disconnect(websocket, category="realtime", item_id=item_id)

    async def websocket_alchemy(
        self,
        websocket: WebSocket,
        item_id: str = "all",
        min_hourly_profit: int = Query(0),
        min_roi: float = Query(0.0),
        min_volume: int = Query(0),
        min_pot_slow: int = Query(0),
        min_hourly_low: int = Query(0),
        max_investment: int | None = Query(None),
        max_investment_slow: int | None = Query(None),
        max_hours: float | None = Query(None),
        only_members: bool | None = Query(None),
    ):
        filters = {
            "min_hourly_profit": min_hourly_profit,
            "min_roi": min_roi,
            "min_volume": min_volume,
            "min_pot_slow": min_pot_slow,
            "min_hourly_low": min_hourly_low,
            "max_investment": max_investment,
            "max_investment_slow": max_investment_slow,
            "max_hours": max_hours,
            "only_members": only_members,
        }
        await self.manager.connect(websocket, category="alchemy", item_id=item_id, **filters)
        try:
            opps = await self.db.get_alchemy_opportunities(
                min_hourly_profit_high=min_hourly_profit,
                min_roi_high=min_roi,
                min_selling_volume=min_volume,
                min_potential_profit_slow=min_pot_slow,
                min_hourly_profit_low=min_hourly_low,
                max_investment_instant=max_investment,
                max_investment_slow=max_investment_slow,
                max_hours_to_process=max_hours,
                only_members=only_members,
                use_snapshot=True,
            )
            if item_id != "all":
                opps = [o for o in opps if str(o.id) == item_id]
            await websocket.send_json({"type": "snapshot", "data": [o.to_dict() for o in opps]})
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            self.manager.disconnect(websocket, "alchemy", item_id)
