import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

# Ensure the data directory exists
Path("./data").mkdir(exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode for better concurrent read performance
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, index=True)          # barbie | board_game
    year = Column(Integer)
    model_number = Column(String)
    barcode = Column(String)
    condition = Column(String)                     # sealed|complete|incomplete|loose|damaged
    quantity = Column(Integer, default=1)
    my_asking_price = Column(Float)
    last_research_date = Column(DateTime)
    status = Column(String, default="not_listed", index=True)  # not_listed|listed|sold|hold
    ebay_listing_url = Column(String)
    sold_price = Column(Float)
    sold_date = Column(DateTime)
    notes = Column(Text)
    photo_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PriceResearchCache(Base):
    __tablename__ = "price_research_cache"

    id = Column(Integer, primary_key=True, index=True)
    search_query = Column(String, nullable=False, index=True)
    category = Column(String)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    cache_ttl_hours = Column(Integer, default=24)
    avg_sold_price = Column(Float)
    min_sold_price = Column(Float)
    max_sold_price = Column(Float)
    median_sold_price = Column(Float)
    sold_count_30d = Column(Integer, default=0)
    sold_count_60d = Column(Integer, default=0)
    sold_count_90d = Column(Integer, default=0)
    active_listing_count = Column(Integer, default=0)
    condition_breakdown = Column(Text)             # JSON string
    last_sold_date = Column(DateTime)
    raw_sold_listings = Column(Text)               # JSON string — eBay sold listings
    source = Column(String, default="ebay")
    linked_item_id = Column(Integer, index=True)   # FK → inventory_items (soft)
    sources_data = Column(Text)                    # JSON — per-source breakdown {etsy,heritage,bgg}


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, nullable=False)
    category = Column(String)
    searched_at = Column(DateTime, default=datetime.utcnow)
    result_count = Column(Integer, default=0)
    avg_price = Column(Float)
    linked_item_id = Column(Integer)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    Base.metadata.create_all(bind=engine)
    # Add new columns to existing DB if they don't exist (safe migration)
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("price_research_cache")}
    with engine.connect() as conn:
        if "sources_data" not in cols:
            conn.execute(text("ALTER TABLE price_research_cache ADD COLUMN sources_data TEXT"))
            conn.commit()
