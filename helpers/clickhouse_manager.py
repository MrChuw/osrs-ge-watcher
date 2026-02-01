from __future__ import annotations

import asyncio
import datetime
import logging
import os
from typing import TYPE_CHECKING, Any

from clickhouse_connect.driver import create_async_client
from clickhouse_connect.driver.asyncclient import AsyncClient, QueryResult

from .clickhouse_models import (
    AlchemyOpportunity,
    ItemMetadata,
    ItemRealtime2Status,
    ItemRealtimeStatus,
    ItemStats,
    PriceDropAlert,
    RawPriceStatus,
)

if TYPE_CHECKING:
    from ingester import Ingester
    from webserver import Application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ClickHouseManager")


class ClickHouseManager:
    def __init__(
        self,
        parent: Application | Ingester,
        host="localhost",
        port=8123,
        username="default",
        password="",
        database="osrs_db",
    ):
        self.parent: Application | Ingester = parent
        self.logger = parent.log
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.client: AsyncClient | None = None
        self._insert_queue = asyncio.Queue()
        self._worker_task = None

    async def _get_client(self) -> AsyncClient:
        if self.client is None:
            if self._worker_task is None:
                self._worker_task = asyncio.create_task(self._bg_insert_worker())

            await self._connect()
        return self.client

    async def _connect(self):
        while True:
            try:
                self.client = await create_async_client(
                    host=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    database=self.database,
                )
                self.logger.info("Successfully connected to ClickHouse.")
                break
            except Exception as e:
                self.logger.error(f"Failed to connect to ClickHouse: {e}. Trying again in 5s...")
                await asyncio.sleep(5)

    async def _bg_insert_worker(self):
        while True:
            table, data, cols = await self._insert_queue.get()

            success = False
            while not success:
                try:
                    client = await self._get_client()
                    await client.insert(table, data, column_names=cols)
                    success = True
                except Exception as e:
                    self.logger.error(f"Error inserting into {table}: {e}. Waiting for reconnection...")
                    self.client = None
                    await asyncio.sleep(2)

            self._insert_queue.task_done()

    async def close(self):
        if self._worker_task:
            self._worker_task.cancel()
        if self.client:
            await self.client.close()

    async def create_tables(self):
        client = await self._get_client()
        # region
        await client.command(
            """
            CREATE TABLE IF NOT EXISTS osrs_prices (
                item_id UInt16 CODEC(ZSTD(10)),
                high UInt32 CODEC(Delta, ZSTD(10)),
                low UInt32 CODEC(Delta, ZSTD(10)),
                highTime DateTime CODEC(DoubleDelta, ZSTD(10)),
                lowTime DateTime CODEC(DoubleDelta, ZSTD(10)),
                timestamp DateTime CODEC(DoubleDelta, ZSTD(10))
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (item_id, timestamp)
            TTL timestamp + INTERVAL 15 DAY RECOMPRESS CODEC(ZSTD(15));
        """
        )

        await client.command(
            """
            CREATE TABLE IF NOT EXISTS item_stats (
                item_id UInt32 CODEC(T64, ZSTD(1)),
                avg_high_price Int64 CODEC(Delta(8), ZSTD(6)),
                avg_low_price Int64 CODEC(Delta(8), ZSTD(6)),
                high_volume Int64 CODEC(Delta(8), ZSTD(6)),
                low_volume Int64 CODEC(Delta(8), ZSTD(6)),
                timestamp DateTime CODEC(DoubleDelta, ZSTD(6))
            ) ENGINE = MergeTree()
            ORDER BY (item_id, timestamp);
        """
        )

        await client.command(
            """
            CREATE TABLE IF NOT EXISTS item_metadata (
                id UInt32,
                name String CODEC(ZSTD(1)),
                examine String CODEC(ZSTD(1)),
                members Bool,
                lowalch Nullable(UInt32),
                highalch Nullable(UInt32),
                buy_limit Nullable(UInt32),
                value Nullable(UInt32),
                icon String CODEC(ZSTD(1)),
                updated_at DateTime DEFAULT now()
            ) ENGINE = ReplacingMergeTree(updated_at)
            ORDER BY id;
        """
        )

        await client.command(
            """
            CREATE TABLE IF NOT EXISTS hourly_item_summary (
                item_id UInt32 CODEC(T64, ZSTD(1)),
                hour DateTime CODEC(DoubleDelta, ZSTD(1)),
                total_high_vol AggregateFunction(sum, Int64) CODEC(ZSTD(1)),
                total_low_vol AggregateFunction(sum, Int64) CODEC(ZSTD(1)),
                avg_price_state AggregateFunction(avg, Int64) CODEC(ZSTD(1))
            ) ENGINE = AggregatingMergeTree()
            PARTITION BY toYYYYMM(hour)
            ORDER BY (item_id, hour);
            """
        )

        await client.command(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_item_summary
            TO hourly_item_summary
            AS SELECT
                item_id,
                toStartOfHour(timestamp) AS hour,
                sumState(high_volume) AS total_high_vol,
                sumState(low_volume) AS total_low_vol,
                avgState(avg_high_price) AS avg_price_state
            FROM item_stats
            WHERE avg_high_price <> -1
            GROUP BY item_id, hour;
        """
        )

        await client.command(
            """
                CREATE TABLE IF NOT EXISTS osrs_db.prices_summary_data
                (
                    item_id UInt16,  -- Atualizado para UInt16
                    latest_sell_price_state AggregateFunction(argMax, UInt32, DateTime), -- Atualizado para UInt32
                    avg_sell_price_24h_state AggregateFunction(avg, UInt32),
                    latest_buy_price_state AggregateFunction(argMax, UInt32, DateTime),
                    avg_buy_price_24h_state AggregateFunction(avg, UInt32)
                )
                ENGINE = AggregatingMergeTree()
                ORDER BY (item_id);
                """
        )

        await client.command(
            """
                CREATE MATERIALIZED VIEW IF NOT EXISTS osrs_db.mv_price_changes_monitor
                TO osrs_db.prices_summary_data
                AS
                SELECT
                    item_id,
                    argMaxState(high, timestamp) AS latest_sell_price_state,
                    avgState(high) AS avg_sell_price_24h_state,
                    argMaxState(low, timestamp) AS latest_buy_price_state,
                    avgState(low) AS avg_buy_price_24h_state
                FROM osrs_db.osrs_prices
                GROUP BY item_id;
                """
        )

        await client.command(
            """
                CREATE VIEW IF NOT EXISTS osrs_db.alerts_price_drops AS
                WITH aggregated_data AS (
                    SELECT
                        m.id AS item_id,
                        m.name,
                        m.members,
                        m.buy_limit,
                        -- Cast explícito para Int64 para permitir matemática segura
                        toInt64(argMaxMerge(p.latest_sell_price_state)) AS current_sell_price,
                        toInt64(argMaxMerge(p.latest_buy_price_state)) AS current_buy_price,
                        avgMerge(p.avg_sell_price_24h_state) AS avg_sell_24h,
                        avgMerge(p.avg_buy_price_24h_state) AS avg_buy_24h,
                        s.avg_high_price,
                        s.avg_low_price,
                        s.high_volume,
                        s.low_volume
                    FROM osrs_db.prices_summary_data AS p
                    JOIN osrs_db.item_metadata AS m ON p.item_id = m.id
                    LEFT JOIN (
                        SELECT * FROM osrs_db.item_stats ORDER BY item_id, timestamp DESC LIMIT 1 BY item_id
                    ) AS s ON p.item_id = s.item_id
                    GROUP BY
                        m.id, m.name, m.members, m.buy_limit,
                        s.avg_high_price, s.avg_low_price, s.high_volume, s.low_volume
                )
                SELECT
                    *,
                    if(avg_sell_24h > 0, ((current_sell_price - avg_sell_24h) / avg_sell_24h) * 100, 0) AS change_pct,
                    (high_volume + low_volume) AS total_volume
                FROM aggregated_data
                WHERE abs(change_pct) > 5;
                """
        )

        await client.command(
            """
                CREATE TABLE IF NOT EXISTS hourly_item_stats (
                    item_id UInt16,
                    hour DateTime CODEC(DoubleDelta, ZSTD(1)),
                    avg_high AggregateFunction(avg, UInt32) CODEC(ZSTD(1)),
                    max_high AggregateFunction(argMax, UInt32, DateTime) CODEC(ZSTD(1)),
                    min_low AggregateFunction(argMin, UInt32, DateTime) CODEC(ZSTD(1))
                ) ENGINE = AggregatingMergeTree()
                PARTITION BY toYYYYMM(hour)
                ORDER BY (item_id, hour);
                """
        )

        await client.command(
            """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_item_stats
                TO hourly_item_stats
                AS SELECT
                    item_id,
                    toStartOfHour(timestamp) AS hour,
                    avgState(high) AS avg_high,
                    argMaxState(high, timestamp) AS max_high,
                    argMinState(low, timestamp) AS min_low
                FROM osrs_prices
                GROUP BY item_id, hour;
                """
        )

        await client.command(
            """
                    CREATE TABLE IF NOT EXISTS osrs_db.market_flip_cache (
                        item_id UInt16 CODEC(T64, ZSTD(1)),
                        latest_high_state AggregateFunction(argMax, UInt32, DateTime) CODEC(ZSTD(1)),
                        last_update DateTime CODEC(DoubleDelta, ZSTD(1))
                    )
                    ENGINE = AggregatingMergeTree()
                    ORDER BY (item_id);
                    """
        )

        await client.command(
            """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS osrs_db.mv_market_flip_cache
                    TO osrs_db.market_flip_cache
                    AS SELECT
                        item_id,
                        argMaxState(high, timestamp) AS latest_high_state,
                        max(timestamp) AS last_update
                    FROM osrs_db.osrs_prices
                    GROUP BY item_id;
                    """
        )

        await client.command(
            """
                CREATE OR REPLACE VIEW osrs_db.view_potential_profit AS
                SELECT * FROM (
                    SELECT
                        m.id AS item_id,
                        m.name,
                        m.members,
                        m.buy_limit,
                        toInt64(argMaxMerge(c.latest_high_state)) AS current_price,
                        avgMerge(h.avg_price_state) AS avg_price_24h,
                        (sumMerge(h.total_high_vol) + sumMerge(h.total_low_vol)) AS volume_24h,
                        max(c.last_update) AS last_update,
                        (avg_price_24h - current_price) / nullIf(avg_price_24h, 0) * 100 AS discount_percent,
                        (avg_price_24h - current_price) * m.buy_limit AS potential_total_profit
                    FROM osrs_db.market_flip_cache c
                    JOIN osrs_db.item_metadata m ON c.item_id = m.id
                    JOIN osrs_db.hourly_item_summary h ON c.item_id = h.item_id
                    WHERE h.hour >= now() - INTERVAL 24 HOUR
                      AND m.buy_limit > 0
                    GROUP BY m.id, m.name, m.members, m.buy_limit
                ) AS sub
                WHERE current_price > 0
                  AND volume_24h > 100
                  AND potential_total_profit > 0
                """
        )

        # endregion
        await client.command(
            """
            CREATE OR REPLACE VIEW osrs_db.view_alchemy_opportunities AS
            SELECT
                *,
                toInt64(profit_per_high_alch_instant * min2(1200.0, buy_limit)) AS realistic_hourly_profit_high,
                toInt64(profit_per_low_alch_instant * min2(1200.0, buy_limit)) AS realistic_hourly_profit_low
            FROM (
                SELECT
                    id, name, members, buy_limit, highalch, lowalch,
                    insta_buy_price, slow_buy_price,
                    ifNull(selling_volume, 0) as selling_volume,
                    nature_price,
                    -- Cálculos de lucro precisam converter para Int64 para aceitar valores negativos
                    (toInt64(highalch) - (insta_buy_price + nature_price)) AS profit_per_high_alch_instant,
                    (profit_per_high_alch_instant * buy_limit) AS potential_total_profit_instant,
                    (toInt64(highalch) - (slow_buy_price + nature_price)) AS profit_per_high_alch_slow,
                    (profit_per_high_alch_slow * buy_limit) AS potential_total_profit_slow,
                    (profit_per_high_alch_instant * 1200) AS estimated_hourly_profit_high,

                    (toInt64(lowalch) - (insta_buy_price + nature_price)) AS profit_per_low_alch_instant,
                    (profit_per_low_alch_instant * buy_limit) AS potential_total_profit_low_instant,
                    (toInt64(lowalch) - (slow_buy_price + nature_price)) AS profit_per_low_alch_slow,
                    (profit_per_low_alch_slow * buy_limit) AS potential_total_profit_low_slow,
                    (profit_per_low_alch_instant * 1200) AS estimated_hourly_profit_low,

                    round(cast(profit_per_high_alch_instant / nullIf(insta_buy_price + nature_price, 0) * 100 AS Float64), 2) AS roi_high_alch_percent,
                    round(cast(profit_per_low_alch_instant / nullIf(insta_buy_price + nature_price, 0) * 100 AS Float64), 2) AS roi_low_alch_percent,

                    (insta_buy_price * buy_limit) AS cost_to_buy_limit_instant,
                    (slow_buy_price * buy_limit) AS cost_to_buy_limit_slow,
                    round(cast(buy_limit / 1200.0 AS Float64), 2) AS hours_to_process_limit,
                    now() AS updated_at
                FROM (
                    SELECT
                        m.id, m.name, m.members,
                        assumeNotNull(m.buy_limit) AS buy_limit,
                        assumeNotNull(m.highalch) AS highalch,
                        assumeNotNull(m.lowalch) AS lowalch,
                        -- Preços agora vêm como UInt32, convertendo para Int64 para segurança nos cálculos externos
                        toInt64(argMaxMerge(p.latest_sell_price_state)) AS insta_buy_price,
                        toInt64(argMaxMerge(p.latest_buy_price_state)) AS slow_buy_price,
                        any(s.low_volume) AS selling_volume,
                        (SELECT toInt64(argMaxMerge(latest_sell_price_state)) FROM osrs_db.prices_summary_data WHERE item_id = 561) AS nature_price
                    FROM osrs_db.item_metadata AS m
                    INNER JOIN osrs_db.prices_summary_data AS p ON m.id = p.item_id
                    LEFT JOIN (
                        SELECT item_id, low_volume
                        FROM osrs_db.item_stats
                        ORDER BY timestamp DESC
                        LIMIT 1 BY item_id
                    ) AS s ON m.id = s.item_id
                    WHERE m.highalch > 0
                    GROUP BY m.id, m.name, m.members, m.buy_limit, m.highalch, m.lowalch
                ) AS final_data
            );
            """  # NOQA: E501
        )

        await client.command(
            """
                    CREATE TABLE IF NOT EXISTS osrs_db.alchemy_opportunities_snapshot
                    (
                        id UInt16,
                        name String,
                        members Bool,
                        buy_limit Int64,
                        highalch Int64,
                        lowalch Int64,
                        insta_buy_price Int64,
                        slow_buy_price Int64,
                        selling_volume Int64,
                        nature_price Int64,
                        profit_per_high_alch_instant Int64,
                        profit_per_high_alch_slow Int64,
                        profit_per_low_alch_instant Int64,
                        profit_per_low_alch_slow Int64,
                        potential_total_profit_instant Int64,
                        potential_total_profit_slow Int64,
                        potential_total_profit_low_instant Int64,
                        potential_total_profit_low_slow Int64,
                        estimated_hourly_profit_high Int64,
                        estimated_hourly_profit_low Int64,
                        realistic_hourly_profit_high Int64, -- ADICIONADA
                        realistic_hourly_profit_low Int64,  -- ADICIONADA
                        roi_high_alch_percent Float64,
                        roi_low_alch_percent Float64,
                        cost_to_buy_limit_instant Int64,
                        cost_to_buy_limit_slow Int64,
                        hours_to_process_limit Float64,
                        updated_at DateTime DEFAULT now()
                    )
                    ENGINE = ReplacingMergeTree(updated_at)
                    PRIMARY KEY id
                    ORDER BY id;
                    """
        )

        await client.command(
            """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS osrs_db.mv_alchemy_opportunities_snapshot
                    TO osrs_db.alchemy_opportunities_snapshot
                    AS
                    SELECT
                        m.id                                                  AS id,
                        m.name                                                AS name,
                        m.members                                             AS members,
                        assumeNotNull(m.buy_limit)                            AS buy_limit,
                        toInt64(assumeNotNull(m.highalch))                    AS highalch,
                        toInt64(assumeNotNull(m.lowalch))                     AS lowalch,
                        toInt64(argMaxMerge(p.latest_sell_price_state))       AS insta_buy_price,
                        toInt64(argMaxMerge(p.latest_buy_price_state))        AS slow_buy_price,
                        coalesce(any(s.low_volume), 0)                        AS selling_volume,
                        toInt64((SELECT argMaxMerge(latest_sell_price_state) FROM osrs_db.prices_summary_data WHERE item_id = 561)) AS nature_price,
                        (toInt64(assumeNotNull(m.highalch)) - (toInt64(argMaxMerge(p.latest_sell_price_state)) + nature_price)) AS profit_per_high_alch_instant,
                        (toInt64(assumeNotNull(m.highalch)) - (toInt64(argMaxMerge(p.latest_buy_price_state)) + nature_price)) AS profit_per_high_alch_slow,
                        (toInt64(assumeNotNull(m.lowalch)) - (toInt64(argMaxMerge(p.latest_sell_price_state)) + nature_price)) AS profit_per_low_alch_instant,
                        (toInt64(assumeNotNull(m.lowalch)) - (toInt64(argMaxMerge(p.latest_buy_price_state)) + nature_price)) AS profit_per_low_alch_slow,
                        (profit_per_high_alch_instant * buy_limit) AS potential_total_profit_instant,
                        (profit_per_high_alch_slow * buy_limit) AS potential_total_profit_slow,
                        (profit_per_low_alch_instant * buy_limit) AS potential_total_profit_low_instant,
                        (profit_per_low_alch_slow * buy_limit) AS potential_total_profit_low_slow,
                        (profit_per_high_alch_instant * 1200) AS estimated_hourly_profit_high,
                        (profit_per_low_alch_instant * 1200) AS estimated_hourly_profit_low,
                        -- Colunas calculadas que faltavam na tabela:
                        toInt64(profit_per_high_alch_instant * min2(1200.0, toFloat64(buy_limit))) AS realistic_hourly_profit_high,
                        toInt64(profit_per_low_alch_instant * min2(1200.0, toFloat64(buy_limit))) AS realistic_hourly_profit_low,
                        round(cast(( (toFloat64(profit_per_high_alch_instant) ) / nullIf((insta_buy_price + nature_price), 0) * 100) AS Float64), 2) AS roi_high_alch_percent,
                        round(cast(( (toFloat64(profit_per_low_alch_instant) ) / nullIf((insta_buy_price + nature_price), 0) * 100) AS Float64), 2) AS roi_low_alch_percent,
                        (insta_buy_price * buy_limit) AS cost_to_buy_limit_instant,
                        (slow_buy_price * buy_limit) AS cost_to_buy_limit_slow,
                        round(cast(buy_limit / 1200.0 AS Float64), 2) AS hours_to_process_limit,
                        now() AS updated_at
                    FROM osrs_db.prices_summary_data AS p
                    JOIN osrs_db.item_metadata AS m ON p.item_id = m.id
                    LEFT JOIN (
                        SELECT item_id, low_volume
                        FROM osrs_db.item_stats
                        ORDER BY timestamp DESC
                        LIMIT 1 BY item_id
                    ) AS s ON p.item_id = s.item_id
                    WHERE m.highalch > 0
                    GROUP BY m.id, m.name, m.members, m.buy_limit, m.highalch, m.lowalch;
                    """  # NOQA: E501
        )

        await client.command(
            """
                CREATE TABLE IF NOT EXISTS osrs_db.item_realtime_aggregated (
                    item_id UInt16,
                    name String,
                    members UInt8,
                    buy_limit Nullable(Int64), -- Mantido Int64 pois metadata pode variar
                    latest_high_state AggregateFunction(argMax, UInt32, DateTime),
                    latest_low_state AggregateFunction(argMax, UInt32, DateTime),
                    avg_high_24h_state AggregateFunction(avg, UInt32),
                    high_volume SimpleAggregateFunction(max, Int64), -- Vindo de item_stats (Int64)
                    low_volume SimpleAggregateFunction(max, Int64),  -- Vindo de item_stats (Int64)
                    highalch Int64,
                    lowalch Int64,
                    value Int64,
                    updated_at SimpleAggregateFunction(max, DateTime)
                )
                ENGINE = AggregatingMergeTree()
                ORDER BY (item_id, name);
                """
        )

        await client.command(
            """
                CREATE MATERIALIZED VIEW IF NOT EXISTS osrs_db.mv_item_realtime_status
                TO osrs_db.item_realtime_aggregated
                AS
                SELECT
                    p.item_id AS item_id,
                    ifNull(m.name, 'Unknown') AS name,
                    ifNull(m.members, 0) AS members,
                    m.buy_limit AS buy_limit,
                    argMaxState(p.high, p.timestamp) AS latest_high_state,
                    argMaxState(p.low, p.timestamp) AS latest_low_state,
                    avgState(p.high) AS avg_high_24h_state,
                    ifNull(s.high_volume, 0) AS high_volume,
                    ifNull(s.low_volume, 0) AS low_volume,
                    ifNull(m.highalch, 0) AS highalch,
                    ifNull(m.lowalch, 0) AS lowalch,
                    ifNull(m.value, 0) AS value,
                    p.timestamp AS updated_at
                FROM osrs_db.osrs_prices AS p
                LEFT JOIN osrs_db.item_metadata AS m ON p.item_id = m.id
                LEFT JOIN (
                    SELECT item_id, high_volume, low_volume
                    FROM osrs_db.item_stats
                    ORDER BY timestamp DESC LIMIT 1 BY item_id
                ) AS s ON p.item_id = s.item_id
                GROUP BY
                    item_id, name, members, buy_limit,
                    highalch, lowalch, value,
                    high_volume, low_volume, updated_at;
                """
        )

        await client.command(
            """
                CREATE VIEW IF NOT EXISTS osrs_db.view_realtime_status AS
                SELECT
                    item_id,
                    name,
                    members,
                    buy_limit,
                    toInt64(argMaxMerge(latest_high_state)) AS current_sell_price, -- Casting
                    toInt64(argMaxMerge(latest_low_state)) AS current_buy_price,   -- Casting
                    if(current_sell_price >= 50,
                       if((current_sell_price * 0.02) > 5000000, 5000000, floor(current_sell_price * 0.02)),
                       0
                    ) AS ge_tax,
                    ((current_sell_price - ge_tax) - current_buy_price) AS margin,
                    (margin * buy_limit) AS potential_profit,
                    (current_sell_price * buy_limit) AS max_buy_cost_instant,
                    (current_buy_price * buy_limit) AS max_buy_cost_slow,
                    (highalch - current_buy_price) AS alch_profit,
                    if(current_buy_price > 0, (alch_profit / current_buy_price) * 100, 0) AS roi_alch_pct,
                    if(current_buy_price > 0, (margin / current_buy_price) * 100, 0) AS roi_margin_pct,
                    max(high_volume) AS sell_volume,
                    max(low_volume) AS buy_volume,
                    (sell_volume + buy_volume) AS total_volume,
                    avgMerge(avg_high_24h_state) AS avg_high_24h,
                    if(avg_high_24h > 0, ((current_sell_price - avg_high_24h) / avg_high_24h) * 100, 0) AS change_pct,
                    highalch,
                    lowalch,
                    value,
                    max(updated_at) AS updated_at
                FROM osrs_db.item_realtime_aggregated
                GROUP BY item_id, name, members, buy_limit, highalch, lowalch, value;
                """
        )

    # region
    async def insert_prices_bulk(self, prices: list):
        await self._insert_queue.put(
            (
                "osrs_prices",
                prices,
                ["item_id", "high", "low", "highTime", "lowTime", "timestamp"],
            )
        )

    async def insert_stats_bulk(self, stats: list):
        await self._insert_queue.put(
            (
                "item_stats",
                stats,
                [
                    "item_id",
                    "avg_high_price",
                    "avg_low_price",
                    "high_volume",
                    "low_volume",
                    "timestamp",
                ],
            )
        )

    async def update_item_metadata(self, items: list):
        await self._insert_queue.put(
            (
                "item_metadata",
                items,
                [
                    "id",
                    "name",
                    "examine",
                    "members",
                    "lowalch",
                    "highalch",
                    "buy_limit",
                    "value",
                    "icon",
                ],
            )
        )

    async def query_with_retry(self, query: str, parameters: dict | None) -> QueryResult:
        while True:
            try:
                client = await self._get_client()
                return await client.query(query, parameters=parameters)
            except Exception as e:
                self.logger.error(f"Error in query: {e}. Trying again...")
                self.client = None
                await asyncio.sleep(2)

    async def get_latest_prices(self) -> dict[str, int]:
        query = """
            SELECT item_id, high
            FROM osrs_prices
            ORDER BY item_id, timestamp DESC
            LIMIT 1 BY item_id
        """
        result = await self.query_with_retry(query, None)
        return {str(row[0]): row[1] for row in result.result_rows}

    async def get_all_metadata(self) -> dict[str, ItemMetadata]:
        result = await self.query_with_retry("SELECT * FROM item_metadata FINAL", None)
        cols = result.column_names
        return {
            str(r[cols.index("id")]): ItemMetadata(
                id=str(r[cols.index("id")]),
                name=r[cols.index("name")],
                examine=r[cols.index("examine")],
                members=bool(r[cols.index("members")]),
                lowalch=r[cols.index("lowalch")],
                highalch=r[cols.index("highalch")],
                buy_limit=r[cols.index("buy_limit")],
                value=r[cols.index("value")],
                icon=r[cols.index("icon")],
            )
            for r in result.result_rows
        }

    async def get_latest_5m_stats(self) -> dict[str, ItemStats]:
        query = """
            SELECT * FROM item_stats
            ORDER BY item_id, timestamp DESC
            LIMIT 1 BY item_id
        """
        result = await self.query_with_retry(query, None)
        cols = result.column_names
        return {
            str(r[cols.index("item_id")]): ItemStats(
                item_id=str(r[cols.index("item_id")]),
                avg_high_price=r[cols.index("avg_high_price")],
                avg_low_price=r[cols.index("avg_low_price")],
                high_volume=r[cols.index("high_volume")],
                low_volume=r[cols.index("low_volume")],
                timestamp=r[cols.index("timestamp")],
            )
            for r in result.result_rows
        }

    async def get_price_alerts(
        self,
        min_threshold: float | str,
        direction: str = "fall",
    ) -> list[PriceDropAlert]:
        if direction not in ["rise", "fall", "both"]:
            direction = "fall"

        if direction == "rise":
            direction_filter = "change_pct >= {threshold:Float64}"
        elif direction == "fall":
            direction_filter = "change_pct <= {threshold_neg:Float64}"
        else:
            direction_filter = "abs(change_pct) >= {threshold:Float64}"

        query = f"""
            SELECT *
            FROM osrs_db.alerts_price_drops
            WHERE {direction_filter}
            ORDER BY abs(change_pct) DESC
        """

        params = {
            "threshold": float(min_threshold),
            "threshold_neg": -abs(float(min_threshold)),
        }

        result = await self.query_with_retry(query, parameters=params)
        cols = result.column_names

        alerts = []
        for r in result.result_rows:
            change_val = r[cols.index("change_pct")] or 0
            current_sell = r[cols.index("current_sell_price")]
            avg_high_5m = r[cols.index("avg_high_price")]
            actual_direction = "rise" if change_val > 0 else "fall"
            is_dump = False
            if actual_direction == "fall" and avg_high_5m and avg_high_5m > 0:
                is_dump = current_sell < (avg_high_5m * 0.8)

            alerts.append(
                PriceDropAlert(
                    item_id=r[cols.index("item_id")],
                    name=r[cols.index("name")],
                    members=bool(r[cols.index("members")]),
                    buy_limit=r[cols.index("buy_limit")],
                    current_sell_price=current_sell,
                    current_buy_price=r[cols.index("current_buy_price")],
                    avg_sell_24h=r[cols.index("avg_sell_24h")],
                    avg_buy_24h=r[cols.index("avg_buy_24h")],
                    avg_high_5m=avg_high_5m,
                    avg_low_5m=r[cols.index("avg_low_price")],
                    high_volume_5m=r[cols.index("high_volume")] or 0,
                    low_volume_5m=r[cols.index("low_volume")] or 0,
                    total_volume_5m=r[cols.index("total_volume")] or 0,
                    change_pct=change_val,
                    direction=actual_direction,
                    is_dump=is_dump,
                )
            )
        return alerts

    async def get_item_realtime_status(self, item_id: str) -> ItemRealtimeStatus | None:
        query = """
            SELECT
                m.id AS item_id,
                m.name,
                m.highalch,
                m.lowalch,
                m.value,
                m.members,
                m.buy_limit,
                argMaxMerge(p.latest_sell_price_state) AS current_sell_price,
                argMaxMerge(p.latest_buy_price_state) AS current_buy_price,
                avgMerge(p.avg_sell_price_24h_state) AS avg_sell_24h,
                (m.highalch - current_buy_price) AS alch_profit,
                if(avg_sell_24h > 0, ((current_sell_price - avg_sell_24h) / avg_sell_24h) * 100, 0) AS change_pct
            FROM osrs_db.prices_summary_data p
            JOIN osrs_db.item_metadata m ON p.item_id = m.id
            WHERE m.id = {i:UInt32}
            GROUP BY m.id, m.name, m.members, m.buy_limit, m.highalch, m.lowalch, m.value
        """
        result = await self.query_with_retry(query, {"i": int(item_id)})
        if result.result_rows:
            data = dict(zip(result.column_names, result.result_rows[0], strict=False))
            return ItemRealtimeStatus(**data)
        return None

    async def get_items_realtime_status(self, item_id: str | int | None = None) -> list[ItemRealtimeStatus]:
        query = """
            SELECT
                m.id AS item_id,
                m.name,
                m.highalch,
                m.lowalch,
                m.value,
                m.members,
                m.buy_limit,
                argMaxMerge(p.latest_sell_price_state) AS current_sell_price,
                argMaxMerge(p.latest_buy_price_state) AS current_buy_price,
                avgMerge(p.avg_sell_price_24h_state) AS avg_sell_24h,
                (toInt64(m.highalch) - current_buy_price) AS alch_profit,
                if(avg_sell_24h > 0, ((current_sell_price - avg_sell_24h) / avg_sell_24h) * 100, 0) AS change_pct
            FROM osrs_db.prices_summary_data p
            JOIN osrs_db.item_metadata m ON p.item_id = m.id
        """
        params = {}
        if item_id is not None:
            query += " WHERE m.id = {i:UInt32}"
            params["i"] = int(item_id)

        query += """
            GROUP BY
                m.id, m.name, m.members, m.buy_limit,
                m.highalch, m.lowalch, m.value
        """
        result = await self.query_with_retry(query, params)
        return [ItemRealtimeStatus(**dict(zip(result.column_names, r, strict=False))) for r in result.result_rows]

    async def get_all_latest_raw_prices(self) -> list[RawPriceStatus]:
        query = """
            SELECT item_id, high as current_sell_price, low as current_buy_price
            FROM osrs_prices
            WHERE timestamp >= now() - INTERVAL 1 MINUTE
            ORDER BY item_id, timestamp DESC
            LIMIT 1 BY item_id
        """
        result = await self.query_with_retry(query, None)
        return [RawPriceStatus(**dict(zip(result.column_names, r, strict=False))) for r in result.result_rows]

    async def get_raw_current_prices(self) -> list[dict]:
        query = """
            SELECT
                item_id,
                high AS current_sell_price,
                low AS current_buy_price,
                timestamp
            FROM osrs_db.osrs_prices
            WHERE timestamp >= now() - INTERVAL 2 MINUTE
            ORDER BY item_id, timestamp DESC
            LIMIT 1 BY item_id
        """
        result = await self.query_with_retry(query, None)
        return [dict(zip(result.column_names, r, strict=False)) for r in result.result_rows]

    async def get_historical_prices(self, item_id: str, start_time: datetime.datetime, end_time: datetime.datetime):
        client = await self._get_client()
        duration_days = (end_time - start_time).days

        if duration_days <= 2:
            interval = "1 minute"
        elif duration_days <= 7:
            interval = "5 minute"
        elif duration_days <= 30:
            interval = "15 minute"
        else:
            interval = "1 hour"

        query = f"""
                SELECT
                    toUnixTimestamp64Milli(
                        CAST(toStartOfInterval(timestamp, INTERVAL {interval}), 'DateTime64(3)')
                    ) as ts,
                    round(avg(toFloat64(avg_high_price))) as sell,
                    round(avg(toFloat64(avg_low_price))) as buy,
                    sum(high_volume + low_volume) as volume
                FROM item_stats
                WHERE item_id = %(item_id)s AND timestamp BETWEEN %(start)s AND %(end)s
                GROUP BY ts
                ORDER BY ts ASC
            """

        params = {"item_id": int(item_id), "start": start_time, "end": end_time}
        result = await client.query(query, params)

        return [
            {
                "timestamp": row[0],
                "sell": round(row[1]) if row[1] is not None else 0,
                "buy": round(row[2]) if row[2] is not None else 0,
                "volume": int(row[3]) if row[3] is not None else 0,
            }
            for row in result.result_rows
        ]

    # endregion

    async def get_alchemy_opportunities(
        self,
        min_hourly_profit_high: int = 0,
        min_potential_profit_instant: int = 0,
        min_roi_high: float = 0.0,
        min_potential_profit_slow: int = 0,
        min_hourly_profit_low: int = 0,
        max_investment_instant: int | None = None,
        max_investment_slow: int | None = None,
        max_hours_to_process: float | None = None,
        min_selling_volume: int = 0,
        only_members: bool | None = None,
        limit: int | None = None,
        order_by: str = "estimated_hourly_profit_high",
        use_snapshot: bool = False,
    ) -> list[AlchemyOpportunity]:
        conditions = ["selling_volume != -1"]
        params = {}

        filter_map = [
            ("estimated_hourly_profit_high", ">=", min_hourly_profit_high, "min_h"),
            (
                "potential_total_profit_instant",
                ">=",
                min_potential_profit_instant,
                "min_p_inst",
            ),
            ("roi_high_alch_percent", ">=", min_roi_high, "roi_h"),
            (
                "potential_total_profit_slow",
                ">=",
                min_potential_profit_slow,
                "min_p_slow",
            ),
            ("estimated_hourly_profit_low", ">=", min_hourly_profit_low, "min_h_low"),
            ("selling_volume", ">=", min_selling_volume, "vol"),
        ]

        for col, op, val, p_name in filter_map:
            if val and val > 0:
                conditions.append(f"{col} {op} {{{p_name}:Float64}}")
                params[p_name] = val

        if max_investment_instant:
            conditions.append("cost_to_buy_limit_instant <= {cost_inst:Int64}")
            params["cost_inst"] = max_investment_instant

        if max_investment_slow:
            conditions.append("cost_to_buy_limit_slow <= {cost_slow:Int64}")
            params["cost_slow"] = max_investment_slow

        if max_hours_to_process:
            conditions.append("hours_to_process_limit <= {hours:Float64}")
            params["hours"] = max_hours_to_process

        if only_members is not None:
            conditions.append("members = {m:Bool}")
            params["m"] = only_members

        allowed_orders = [
            "estimated_hourly_profit_high",
            "potential_total_profit_instant",
            "roi_high_alch_percent",
            "hours_to_process_limit",
            "selling_volume",
            "potential_total_profit_slow",
            "estimated_hourly_profit_low",
            "roi_low_alch_percent",
        ]
        sort_col = order_by if order_by in allowed_orders else "estimated_hourly_profit_high"

        where_clause = " AND ".join(conditions)

        if use_snapshot:
            from_clause = "osrs_db.alchemy_opportunities_snapshot FINAL"
        else:
            from_clause = "osrs_db.view_alchemy_opportunities"

        query = f"""
                SELECT *
                FROM {from_clause}
                WHERE {where_clause}
                ORDER BY {sort_col} DESC
            """

        if limit:
            query += f" LIMIT {int(limit)}"

        result = await self.query_with_retry(query, params)
        cols = result.column_names

        return [AlchemyOpportunity(**dict(zip(cols, row, strict=False))) for row in result.result_rows]

    async def get_realtime_items(
        self,
        min_margin: int | None = None,
        min_roi_alch: float | None = None,
        min_roi_margin: float | None = None,
        min_alch_profit: int | None = None,
        min_total_volume: int | None = None,
        min_sell_volume: int | None = None,
        only_members: bool | None = None,
        min_buy_limit: int | None = None,
        min_change_pct: float | None = None,
        max_change_pct: float | None = None,
        order_by: str = "roi_margin_pct",
        limit: int | None = None,
        search_name: str | None = None,
    ) -> list[ItemRealtime2Status]:
        conditions = ["current_buy_price > 0"]
        params: dict[str, Any] = {}

        numeric_filters = [
            ("margin", ">=", min_margin, "mgn"),
            ("roi_alch_pct", ">=", min_roi_alch, "roi_a"),
            ("roi_margin_pct", ">=", min_roi_margin, "roi_m"),
            ("alch_profit", ">=", min_alch_profit, "prof_a"),
            ("buy_limit", ">=", min_buy_limit, "limit_b"),
            ("change_pct", ">=", min_change_pct, "chg_min"),
            ("change_pct", "<=", max_change_pct, "chg_max"),
            ("total_volume", ">=", min_total_volume, "vol_total"),
            ("sell_volume", ">=", min_sell_volume, "vol_sell"),
        ]

        for col, op, val, p_name in numeric_filters:
            if val is not None:
                conditions.append(f"{col} {op} {{{p_name}:Float64}}")
                params[p_name] = val

        if only_members is not None:
            conditions.append("members = {m:Bool}")
            params["m"] = only_members

        if search_name:
            conditions.append("name ILIKE {name:String}")
            params["name"] = f"%{search_name}%"

        allowed_orders = {
            "roi_alch_pct",
            "roi_margin_pct",
            "margin",
            "alch_profit",
            "change_pct",
            "current_buy_price",
            "updated_at",
            "buy_limit",
            "total_volume",
            "sell_volume",
            "buy_volume",
        }
        sort_col = order_by if order_by in allowed_orders else "roi_margin_pct"

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT *
            FROM osrs_db.view_realtime_status
            WHERE {where_clause}
            ORDER BY {sort_col} DESC
        """

        if limit:
            query += f" LIMIT {int(limit)}"

        result = await self.query_with_retry(query, params)

        return [ItemRealtime2Status.from_row(result.column_names, row) for row in result.result_rows]


def pre_checks():
    if not os.getenv("USER_AGENT"):
        return "No User agent configured, please add an email so the OSRS Wiki can contact you."
    if not os.getenv("DB_HOST"):
        return "Database host (DB_HOST) not configured."
    if not os.getenv("DB_PORT"):
        return "Database port (DB_PORT) not configured."
    if not os.getenv("DB_USERNAME"):
        return "Database username (DB_USERNAME) not configured."
    if not os.getenv("DB_PASSWORD"):
        return "Database password (DB_PASSWORD) not configured."
    if not os.getenv("DB_DATABASE"):
        return "Database name (DB_DATABASE) not configured."
    return None
