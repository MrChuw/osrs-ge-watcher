from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from .update_cache import UpdateTracker

if TYPE_CHECKING:
    from webserver import Application

    from .clickhouse_manager import ClickHouseManager
    from .websocket_manager import ConnectionManager


MIN_ALLOWED_THRESHOLD = float(os.getenv("MIN_ALLOWED_THRESHOLD", 5.0))
CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", 5))
CHECK_INTERVAL_RAW: int = int(os.getenv("CHECK_INTERVAL_RAW", 5))
TTL_FORCED_UPDATE: int = int(os.getenv("TTL_FORCED_UPDATE", 60))


class Monitors:
    def __init__(self, parent: Application):
        self.parent: Application = parent
        self.manager: ConnectionManager = parent.manager
        self.db: ClickHouseManager = parent.db
        self._tasks: list[asyncio.Task] = []

    async def start(self):
        self._tasks.append(asyncio.create_task(self.monitor_prices_loop(), name="monitor_prices_loop"))
        self._tasks.append(asyncio.create_task(self.monitor_price_table_loop(), name="monitor_price_table_loop"))
        self._tasks.append(asyncio.create_task(self.monitor_realtime_loop(), name="monitor_realtime_loop"))
        self._tasks.append(asyncio.create_task(self.monitor_alchemy_loop(), name="monitor_alchemy_loop"))

    async def stop(self):
        for task in self._tasks:
            task.cancel()

    async def monitor_prices_loop(self):
        tracker = UpdateTracker(ttl=TTL_FORCED_UPDATE)
        self.parent.log.info("Monitor de PRICES started...")
        while True:
            await self.manager.wait_for_category("alerts")
            try:
                raw_alerts = await self.db.get_price_alerts(min_threshold=MIN_ALLOWED_THRESHOLD, direction="both")
                for alert in raw_alerts:
                    if alert.total_volume_5m <= 100:
                        continue

                    if abs(alert.change_pct) < MIN_ALLOWED_THRESHOLD:
                        continue

                    item_id_str = str(alert.item_id)
                    state = alert.current_sell_price

                    if tracker.should_update(item_id_str, state):
                        await self.manager.broadcast(
                            category="alerts",
                            item_id=item_id_str,
                            data=alert.to_dict(),
                            type_name="price_alert",
                        )
            except Exception as e:
                self.parent.log.error(f"Erro in Monitor Prices: {e}")

            await asyncio.sleep(CHECK_INTERVAL)

    async def monitor_price_table_loop(self):
        tracker = UpdateTracker(ttl=TTL_FORCED_UPDATE / 4)
        self.parent.log.info("Monitor PRICE started...")
        while True:
            await self.manager.wait_for_category("price_table")
            try:
                updates = await self.db.get_realtime_items()

                for upm in updates:
                    item_id_str = str(upm.item_id)
                    state = upm.current_sell_price + upm.current_buy_price

                    if tracker.should_update(item_id_str, state):
                        await self.manager.broadcast(
                            category="price_table",
                            item_id=item_id_str,
                            data=upm.to_dict(),
                            type_name="price_update",
                        )

            except Exception as e:
                self.parent.log.error(f"Erro in Monitor Prices: {e}")

            await asyncio.sleep(CHECK_INTERVAL_RAW)

    async def monitor_realtime_loop(self):
        tracker = UpdateTracker(ttl=TTL_FORCED_UPDATE / 2)
        self.parent.log.info("Monitor REALTIME started...")
        while True:
            await self.manager.wait_for_category("realtime")
            try:
                updates = await self.db.get_all_latest_raw_prices()

                for upm in updates:
                    item_id_str = str(upm.item_id)
                    state = upm.current_sell_price + upm.current_buy_price

                    if tracker.should_update(item_id_str, state):
                        await self.manager.broadcast(
                            category="realtime",
                            item_id=item_id_str,
                            data=upm.to_dict(),
                            type_name="price_update",
                        )

            except Exception as e:
                self.parent.log.error(f"Erro in Monitor Realtime: {e}")

            await asyncio.sleep(CHECK_INTERVAL_RAW)

    async def monitor_alchemy_loop(self):
        tracker = UpdateTracker(ttl=TTL_FORCED_UPDATE)
        self.parent.log.info("Monitor ALCHEMY started...")
        while True:
            await self.manager.wait_for_category("alchemy")

            try:
                opportunities = await self.db.get_alchemy_opportunities()

                for opp in opportunities:
                    item_id_str = str(opp.id)
                    state = f"{opp.estimated_hourly_profit_high}-{opp.cost_to_buy_limit_instant}"

                    if tracker.should_update(item_id_str, state):
                        await self.manager.broadcast(
                            category="alchemy",
                            item_id=item_id_str,
                            data=opp.to_dict(),
                            type_name="alchemy_update",
                        )

            except Exception as e:
                self.parent.log.info(f"Erro in Monitor Alchemy: {e}")

            await asyncio.sleep(CHECK_INTERVAL_RAW)
