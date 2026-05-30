from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


# ── Inventory ────────────────────────────────────────────────────────────────

class InventoryItemCreate(BaseModel):
    name: str
    category: Optional[str] = None
    year: Optional[int] = None
    model_number: Optional[str] = None
    barcode: Optional[str] = None
    condition: Optional[str] = None
    quantity: int = 1
    my_asking_price: Optional[float] = None
    status: str = "not_listed"
    ebay_listing_url: Optional[str] = None
    sold_price: Optional[float] = None
    sold_date: Optional[datetime] = None
    notes: Optional[str] = None


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    year: Optional[int] = None
    model_number: Optional[str] = None
    barcode: Optional[str] = None
    condition: Optional[str] = None
    quantity: Optional[int] = None
    my_asking_price: Optional[float] = None
    status: Optional[str] = None
    ebay_listing_url: Optional[str] = None
    sold_price: Optional[float] = None
    sold_date: Optional[datetime] = None
    notes: Optional[str] = None


class InventoryItemOut(BaseModel):
    id: int
    name: str
    category: Optional[str]
    year: Optional[int]
    model_number: Optional[str]
    barcode: Optional[str]
    condition: Optional[str]
    quantity: int
    my_asking_price: Optional[float]
    last_research_date: Optional[datetime]
    status: str
    ebay_listing_url: Optional[str]
    sold_price: Optional[float]
    sold_date: Optional[datetime]
    notes: Optional[str]
    photo_path: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Search / Research ────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    category: Optional[str] = None   # barbie | board_game | None = both
    days_back: int = 90
    force_refresh: bool = False


class SoldListing(BaseModel):
    title: str
    price: float
    end_time: Optional[str]
    condition: Optional[str]
    url: Optional[str]
    image_url: Optional[str]


class PriceStats(BaseModel):
    avg: Optional[float]
    min: Optional[float]
    max: Optional[float]
    median: Optional[float]
    count_30d: int
    count_60d: int
    count_90d: int


class SearchResponse(BaseModel):
    query: str
    from_cache: bool
    fetched_at: Optional[datetime]
    stats: PriceStats
    active_listing_count: int
    condition_breakdown: dict[str, Any]
    last_sold_date: Optional[str]
    sold_listings: list[SoldListing]


# ── Identification ────────────────────────────────────────────────────────────

class BarcodeRequest(BaseModel):
    upc: str


class BarcodeResponse(BaseModel):
    found: bool
    name: Optional[str] = None
    brand: Optional[str] = None
    description: Optional[str] = None
    model_number: Optional[str] = None
    source: Optional[str] = None


# ── Import / Export ──────────────────────────────────────────────────────────

class ImportResult(BaseModel):
    imported: int
    skipped: list[dict[str, Any]]


# ── Dashboard ────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    totals: dict[str, Any]
    by_status: dict[str, int]
    revenue: dict[str, Any]
    condition_breakdown: dict[str, int]
    top_value_items: list[dict[str, Any]]
    needs_research: list[dict[str, Any]]
