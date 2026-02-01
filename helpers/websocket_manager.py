import asyncio
from collections import defaultdict
from contextlib import suppress

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.channels = defaultdict(lambda: defaultdict(set))
        self._conditions = defaultdict(asyncio.Condition)
        self._counts = defaultdict(int)

    async def connect(self, websocket: WebSocket, category: str, item_id: str = "all", **filters):
        await websocket.accept()
        filter_key = frozenset(sorted(filters.items()))

        async with self._conditions[category]:
            self.channels[category][item_id].add((websocket, filter_key))
            self._counts[category] += 1
            self._conditions[category].notify_all()

    def disconnect(self, websocket: WebSocket, category: str, item_id: str = "all"):
        if category not in self.channels or item_id not in self.channels[category]:
            return
        current_conns = self.channels[category][item_id]
        updated_conns = {conn for conn in current_conns if conn[0] != websocket}
        removed_count = len(current_conns) - len(updated_conns)

        if removed_count > 0:
            self.channels[category][item_id] = updated_conns
            self._counts[category] -= removed_count
            if not self.channels[category][item_id]:
                del self.channels[category][item_id]

    async def wait_for_category(self, category: str):
        cond = self._conditions[category]
        async with cond:
            while self._counts[category] <= 0:
                # print(f"💤 Monitor {category} in standby...")
                await cond.wait()

    def _should_send(self, category: str, data: dict, filters: dict) -> bool:  # NOQA
        if category == "alchemy":
            if (val := filters.get("min_hourly_profit")) and data.get("estimated_hourly_profit_high", 0) < val:
                return False
            if (val := filters.get("min_hourly_low")) and data.get("estimated_hourly_profit_low", 0) < val:
                return False
            if (val := filters.get("min_roi")) and data.get("roi_high_alch_percent", 0) < val:
                return False
            if (val := filters.get("min_pot_slow")) and data.get("potential_total_profit_slow", 0) < val:
                return False
            if (val := filters.get("min_volume")) and data.get("selling_volume", 0) < val:
                return False
            if filters.get("only_members") is True and not data.get("members"):
                return False
            if (val := filters.get("max_investment")) and data.get("cost_to_buy_limit_instant", 0) > val:
                return False
            if (val := filters.get("max_investment_slow")) and data.get("cost_to_buy_limit_slow", 0) > val:
                return False
            if (val := filters.get("max_hours")) and data.get("hours_to_process_limit", 0) > val:
                return False

        elif category == "alerts":
            change_pct = data.get("change_pct", 0)
            threshold = filters.get("threshold", 0)
            direction = filters.get("direction", "both")
            if abs(change_pct) < threshold:
                return False
            curr_dir = "rise" if change_pct > 0 else "fall"
            if direction not in ["both", curr_dir]:
                return False

        elif category == "realtime":
            return True

        return True

    async def broadcast(self, category: str, item_id: str, data: dict, type_name: str):
        # sourcery skip: remove-unnecessary-cast
        data["type"] = type_name
        targets = ["all", str(item_id)]

        for group_id in targets:
            if group_id not in self.channels[category]:
                continue

            for ws, filter_key in self.channels[category][group_id]:
                filters_dict = dict(filter_key)
                if not self._should_send(category, data, filters_dict):
                    continue
                with suppress(Exception):
                    await ws.send_json(data)
