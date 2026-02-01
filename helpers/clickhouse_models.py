import datetime
from dataclasses import asdict, dataclass


@dataclass
class ItemMetadata:
    id: str
    name: str
    examine: str
    members: bool
    lowalch: int | None
    highalch: int | None
    buy_limit: int | None
    value: int | None
    icon: str


@dataclass
class OSRSPrice:
    item_id: str
    high: int
    low: int
    high_time: datetime.datetime
    low_time: datetime.datetime
    timestamp: datetime.datetime


@dataclass
class ItemStats:
    item_id: str
    avg_high_price: int
    avg_low_price: int
    high_volume: int
    low_volume: int
    timestamp: datetime.datetime


@dataclass
class PriceDropAlert:
    item_id: int
    name: str
    members: bool
    buy_limit: int | None
    current_sell_price: int
    current_buy_price: int
    avg_sell_24h: float
    avg_buy_24h: float
    change_pct: float
    avg_high_5m: int | None
    avg_low_5m: int | None
    high_volume_5m: int
    low_volume_5m: int
    total_volume_5m: int
    direction: str | None
    is_dump: bool | None

    def to_dict(self):
        return asdict(self)


@dataclass
class ItemRealtimeStatus:
    item_id: int
    name: str
    members: bool
    buy_limit: int | None
    current_sell_price: int
    current_buy_price: int
    avg_sell_24h: float
    change_pct: float
    highalch: int
    lowalch: int
    alch_profit: float
    value: int

    def to_dict(self):
        return asdict(self)


@dataclass
class RawPriceStatus:
    item_id: int
    current_sell_price: int
    current_buy_price: int
    timestamp: datetime.datetime | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class AlchemyOpportunity:
    id: int
    name: str
    members: bool
    buy_limit: int
    highalch: int
    lowalch: int
    insta_buy_price: int
    slow_buy_price: int
    selling_volume: int
    nature_price: int

    # High Alch Metrics
    profit_per_high_alch_instant: int
    potential_total_profit_instant: int
    profit_per_high_alch_slow: int
    potential_total_profit_slow: int
    estimated_hourly_profit_high: int
    realistic_hourly_profit_high: int

    # Low Alch Metrics
    profit_per_low_alch_instant: int
    potential_total_profit_low_instant: int
    profit_per_low_alch_slow: int
    potential_total_profit_low_slow: int
    estimated_hourly_profit_low: int
    realistic_hourly_profit_low: int

    # ROI & Logistics
    roi_high_alch_percent: float
    roi_low_alch_percent: float
    cost_to_buy_limit_instant: int
    cost_to_buy_limit_slow: int
    hours_to_process_limit: float

    updated_at: datetime.datetime

    def to_dict(self):
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                data[key] = value.isoformat()
        return data


@dataclass
class ItemRealtime2Status:
    item_id: int
    name: str
    members: bool
    buy_limit: int | None

    # Prices and Margins
    current_sell_price: int
    current_buy_price: int
    ge_tax: int
    margin: int
    potential_profit: int
    max_buy_cost_instant: int
    max_buy_cost_slow: int

    # Volume
    sell_volume: int
    buy_volume: int
    total_volume: int

    # Profits e ROI
    alch_profit: float
    roi_alch_pct: float
    roi_margin_pct: float

    # Metadata and History
    avg_high_24h: float
    change_pct: float

    # Alch and Store Values
    highalch: int
    lowalch: int
    value: int

    updated_at: datetime.datetime

    def to_dict(self):
        data = asdict(self)
        if isinstance(self.updated_at, datetime.datetime):
            data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_row(cls, column_names, row):
        return cls(**dict(zip(column_names, row, strict=False)))
