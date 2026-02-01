from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, Query

if TYPE_CHECKING:
    from helpers import ClickHouseManager, ConnectionManager
    from webserver import Application


class ApiManager:
    def __init__(self, parent: Application):
        self.parent: Application = parent
        self.manager: ConnectionManager = parent.manager
        self.db: ClickHouseManager = parent.db
        self.api_router = APIRouter(prefix="/api")

    def setup_routes(self):
        self.api_router.add_api_route("/history/{item_id}", self.get_history, methods=["GET"])

    async def get_history(self, item_id: str, interval: str = Query(None), date: str = Query(None)):
        end_time = datetime.now(UTC)
        if date:
            start_time = datetime.strptime(date, "%Y-%m-%d")
            end_time = start_time.replace(hour=23, minute=59, second=59)
        elif interval == "1d":
            start_time = end_time - timedelta(days=1)
        elif interval == "1w":
            start_time = end_time - timedelta(days=7)
        elif interval == "1mo":
            start_time = end_time - timedelta(days=30)
        elif interval == "1y":
            start_time = end_time - timedelta(days=365)
        elif interval == "all":
            start_time = end_time - timedelta(days=1000)
        elif interval == "live_buffer":
            start_time = end_time - timedelta(hours=3)
        else:
            start_time = end_time - timedelta(hours=24)
        return await self.db.get_historical_prices(item_id, start_time, end_time)
