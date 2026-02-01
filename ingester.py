import asyncio
import datetime
import os
import time
from datetime import timedelta

import aiohttp
from dotenv import load_dotenv
from loguru import logger

from helpers import ClickHouseManager, pre_checks

load_dotenv()

API_BASE = "https://prices.runescape.wiki/api/v1/osrs"
HEADERS = {"User-Agent": f"OSRS-GE-Watcher/1.0 (Osrs-GE-Watcher; {os.getenv("USER_AGENT")})"}

if error := pre_checks():
    print(error)
    exit(1)


class Ingester:
    def __init__(self):
        self.db: ClickHouseManager | None = None
        self.session: aiohttp.ClientSession | None = None
        self.log = logger

    async def setup(self):
        self.db = ClickHouseManager(
            parent=self,
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            username=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_DATABASE"),
        )
        await self.db.create_tables()
        self.session = aiohttp.ClientSession(headers=HEADERS)

    async def sync_mapping(self):
        while True:
            async with self.session.get(f"{API_BASE}/mapping") as r:
                if r.status == 200:
                    data = await r.json()
                    items = [
                        [
                            int(i["id"]),
                            i.get("name"),
                            i.get("examine"),
                            i.get("members", False),
                            i.get("lowalch"),
                            i.get("highalch"),
                            i.get("limit"),
                            i.get("value"),
                            i.get("icon"),
                        ]
                        for i in data
                    ]
                    await self.db.update_item_metadata(items)
                    self.log.info(f"Updated mapping: {len(items)} items.")
            await asyncio.sleep(timedelta(days=5).total_seconds())

    async def fetch_latest(self):
        while True:
            try:
                async with self.session.get(f"{API_BASE}/latest") as r:
                    if r.status == 200:
                        data: dict[str, dict] = (await r.json()).get("data", {})
                        now = datetime.datetime.now(datetime.UTC)
                        to_save = []
                        to_save.extend(
                            [
                                int(item_id),
                                p.get("high") if p.get("high") is not None else 0,
                                p.get("low") if p.get("low") is not None else 0,
                                (
                                    datetime.datetime.fromtimestamp(p["highTime"], datetime.UTC)
                                    if p.get("highTime")
                                    else now
                                ),
                                (
                                    datetime.datetime.fromtimestamp(p["lowTime"], datetime.UTC)
                                    if p.get("lowTime")
                                    else now
                                ),
                                now,
                            ]
                            for item_id, p in data.items()
                        )
                        await self.db.insert_prices_bulk(to_save)
                        self.log.info(f"{len(to_save)} prices saved.")
            except Exception as e:
                self.log.error(f"Erro Latest: {e}")
            await asyncio.sleep(20)

    async def fetch_5m_stats(self):
        last_ts = 0
        while True:
            target_ts = (int(time.time()) // 300 * 300) - 300
            if target_ts > last_ts:
                try:
                    async with self.session.get(f"{API_BASE}/5m", params={"timestamp": target_ts}) as r:
                        if r.status == 200:
                            data = (await r.json()).get("data", {})
                            ts_dt = datetime.datetime.fromtimestamp(target_ts, datetime.UTC)
                            to_save = [
                                [
                                    int(i_id),
                                    info.get("avgHighPrice") or -1,
                                    info.get("avgLowPrice") or -1,
                                    info.get("highPriceVolume") or -1,
                                    info.get("lowPriceVolume") or -1,
                                    ts_dt,
                                ]
                                for i_id, info in data.items()
                            ]
                            await self.db.insert_stats_bulk(to_save)
                            last_ts = target_ts
                            self.log.info(f"Stats 5m saved for TS {target_ts}")
                except Exception as e:
                    self.log.error(f"❌ Erro 5m: {e}")
            await asyncio.sleep(30)

    async def run(self):
        try:
            await self.setup()
            await asyncio.gather(self.fetch_latest(), self.fetch_5m_stats(), self.sync_mapping())
        except Exception as e:
            self.log.error(e)
            await self.db.close()


if __name__ == "__main__":
    asyncio.run(Ingester().run())
