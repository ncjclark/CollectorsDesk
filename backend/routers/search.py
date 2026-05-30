import asyncio
import json
import statistics
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, PriceResearchCache, SearchHistory
from models.schemas import SearchRequest, SearchResponse, PriceStats, SoldListing
from services.ebay import (
    search_sold_listings, search_active_listings, search_unsold_listings,
    compute_price_stats, compute_unsold_stats, ScraperBlocked as EbayBlocked,
)
from services.etsy import search_etsy_listings, compute_etsy_stats, ScraperBlocked as EtsyBlocked
from services.heritage import search_heritage, compute_heritage_stats
from services.bgg import search_bgg

router = APIRouter(prefix="/api/search", tags=["search"])


def _normalize_query(q: str) -> str:
    return " ".join(q.strip().lower().split())


def _clean_query_for_search(q: str) -> str:
    """
    Strip barcode-name noise that confuses eBay/Etsy:
    - Text inside parentheses, e.g. "(angel of peace)" → "angel of peace"
    - "by: brand" / "by brand" attribution fragments
    - Separator punctuation: dashes, colons, slashes used as separators
    - Preserve #NNNN model/stock numbers — Etsy sellers use them
    - Truncate to 80 chars so eBay doesn't reject the query
    """
    import re
    q = q.strip()
    # Protect model numbers like #24240 before stripping punctuation
    q = re.sub(r'#(\d+)', r'MODEL\1', q)
    # Unwrap parentheses — keep the content, drop the parens
    q = re.sub(r'\(([^)]*)\)', r' \1 ', q)
    # Remove "by: something" or "by something" attribution at end
    q = re.sub(r'\bby\s*:?\s*\w[\w\s]*$', '', q, flags=re.IGNORECASE)
    # Remove standalone punctuation used as separators
    q = re.sub(r'\s[-–—/|]\s', ' ', q)
    # Remove remaining special chars (but not digits already labeled)
    q = re.sub(r'[:\'"&]', ' ', q)
    # Restore model numbers
    q = re.sub(r'MODEL(\d+)', r'#\1', q)
    # Collapse whitespace
    q = ' '.join(q.split())
    # Truncate to ~80 chars at a word boundary
    if len(q) > 80:
        q = q[:80].rsplit(' ', 1)[0]
    return q.strip()


def _extract_model_number(text: str) -> str | None:
    """Pull a catalog/stock number like #24240 from a barcode product name."""
    import re
    m = re.search(r'#(\d{4,6})', text)
    return m.group(1) if m else None


_STOP = {
    'the','a','an','and','or','of','in','on','at','to','for','with','by',
    'from','as','is','was','are','were','be','been','this','that','it',
    'its','i','my','your','has','have','had','not','but','so','if',
}

def _etsy_relevance_filter(listings: list[dict], query: str) -> list[dict]:
    """Drop Etsy listings whose titles share less than 40% of query keywords."""
    import re
    def tokens(text: str) -> set:
        return {w for w in re.findall(r'[a-z0-9]+', text.lower())
                if w not in _STOP and len(w) > 2}

    q_tokens = tokens(query)
    if len(q_tokens) < 2:
        return listings  # query too short to filter reliably

    result = []
    for listing in listings:
        title_tokens = tokens(listing.get('title', ''))
        overlap = q_tokens & title_tokens
        if len(overlap) / len(q_tokens) >= 0.4:
            result.append(listing)
    return result


def _get_cached(db: Session, query: str, ttl_hours: int) -> PriceResearchCache | None:
    cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
    return (
        db.query(PriceResearchCache)
        .filter(
            PriceResearchCache.search_query == query,
            PriceResearchCache.fetched_at >= cutoff,
        )
        .order_by(PriceResearchCache.fetched_at.desc())
        .first()
    )


def _build_response(record: PriceResearchCache, from_cache: bool, source_errors: dict | None = None) -> dict:
    raw = json.loads(record.raw_sold_listings or "[]")
    cond = json.loads(record.condition_breakdown or "{}")
    sources = json.loads(record.sources_data or "{}") if record.sources_data else {}

    return {
        "query": record.search_query,
        "from_cache": from_cache,
        "fetched_at": record.fetched_at.isoformat() if record.fetched_at else None,
        "stats": {
            "avg": record.avg_sold_price,
            "min": record.min_sold_price,
            "max": record.max_sold_price,
            "median": record.median_sold_price,
            "count_30d": record.sold_count_30d or 0,
            "count_60d": record.sold_count_60d or 0,
            "count_90d": record.sold_count_90d or 0,
        },
        "active_listing_count": record.active_listing_count or 0,
        "condition_breakdown": cond,
        "last_sold_date": record.last_sold_date.isoformat() if record.last_sold_date else None,
        "sold_listings": raw[:100],
        "sources": sources,
        "combined": _build_combined(record, sources),
        "source_errors": source_errors or {},
    }


def _build_combined(record: PriceResearchCache, sources: dict) -> dict:
    """Aggregate a cross-source price consensus."""
    all_prices = []
    source_summaries = []

    # eBay sold (highest reliability)
    if record.avg_sold_price:
        all_prices.append(("ebay_sold", record.avg_sold_price, 1.0))
        source_summaries.append({
            "source": "eBay Sold",
            "type": "sold",
            "avg": record.avg_sold_price,
            "count": record.sold_count_90d or 0,
            "reliability": "high",
        })

    # Etsy (asking prices, collector premium)
    etsy = sources.get("etsy", {})
    if etsy.get("avg"):
        all_prices.append(("etsy", etsy["avg"], 0.6))  # lower weight — asking not sold
        source_summaries.append({
            "source": "Etsy",
            "type": "asking",
            "avg": etsy["avg"],
            "count": etsy.get("count", 0),
            "reliability": "medium",
            "note": "Asking prices",
        })

    # Heritage (auction realized — premium market)
    heritage = sources.get("heritage", {})
    if heritage.get("avg"):
        all_prices.append(("heritage", heritage["avg"], 0.8))
        source_summaries.append({
            "source": "Heritage Auctions",
            "type": "auction_realized",
            "avg": heritage["avg"],
            "count": heritage.get("count", 0),
            "reliability": "high",
            "note": "Auction results — collector/premium market",
        })

    # BGG marketplace (asking prices, board games only)
    bgg = sources.get("bgg") or {}
    bgg_mkt = bgg.get("marketplace_stats", {}) if bgg.get("found") else {}
    if bgg_mkt.get("avg"):
        all_prices.append(("bgg", bgg_mkt["avg"], 0.6))
        source_summaries.append({
            "source": "BGG Marketplace",
            "type": "asking",
            "avg": bgg_mkt["avg"],
            "count": bgg_mkt.get("count", 0),
            "reliability": "medium",
            "note": "BGG marketplace asking prices",
        })

    if not all_prices:
        return {"consensus_price": None, "price_range": None, "sources": source_summaries}

    # Weighted consensus
    total_weight = sum(w for _, _, w in all_prices)
    consensus = sum(p * w for _, p, w in all_prices) / total_weight

    all_avgs = [p for _, p, _ in all_prices]
    price_range = {
        "low": round(min(all_avgs) * 0.85, 2),   # 15% below lowest source avg
        "high": round(max(all_avgs) * 1.10, 2),  # 10% above highest source avg
    }

    return {
        "consensus_price": round(consensus, 2),
        "price_range": price_range,
        "source_count": len(all_prices),
        "sources": source_summaries,
    }


@router.post("")
async def search(req: SearchRequest, db: Session = Depends(get_db)):
    normalized = _normalize_query(req.query)
    # Also clean the query to remove barcode-name noise before searching
    search_query = _clean_query_for_search(normalized)

    if not req.force_refresh:
        cached = _get_cached(db, search_query, ttl_hours=24)
        if cached:
            _log_history(db, search_query, req.category, cached.sold_count_90d or 0, cached.avg_sold_price)
            return _build_response(cached, from_cache=True)

    # Use cleaned query for all downstream API/scraper calls
    normalized = search_query

    import config as cfg

    async def _disabled_list(): return []
    async def _disabled_dict(): return {}

    # Fetch all sources concurrently — skip disabled sources entirely
    (ebay_sold, ebay_active, ebay_unsold,
     etsy_listings, heritage_results, bgg_result) = await asyncio.gather(
        search_sold_listings(normalized, req.days_back),
        search_active_listings(normalized),
        search_unsold_listings(normalized, req.days_back),
        search_etsy_listings(normalized) if cfg.settings.etsy_enabled else _disabled_list(),
        search_heritage(normalized) if cfg.settings.heritage_enabled else _disabled_list(),
        search_bgg(normalized) if cfg.settings.bgg_enabled else _disabled_dict(),
        return_exceptions=True,
    )

    # Detect rate-limiting / bot-detection per source; pull diagnostics
    source_errors: dict[str, str] = {}
    ebay_debug: dict = {}

    if isinstance(ebay_sold, EbayBlocked):
        source_errors["ebay"] = "rate_limited"
        ebay_debug = ebay_sold.debug
    elif isinstance(ebay_active, EbayBlocked) or isinstance(ebay_unsold, EbayBlocked):
        source_errors["ebay"] = "rate_limited"
    elif not isinstance(ebay_sold, list):
        source_errors["ebay"] = "error"
        ebay_debug = {"exception": str(ebay_sold)}
    else:
        ebay_debug = getattr(ebay_sold, "_ebay_diag", {})

    if isinstance(etsy_listings, EtsyBlocked):
        source_errors["etsy"] = "rate_limited"
    elif not isinstance(etsy_listings, list):
        source_errors["etsy"] = "error"

    # Fall back to empty lists for any failed source
    ebay_sold        = ebay_sold        if isinstance(ebay_sold, list) else []
    ebay_active      = ebay_active      if isinstance(ebay_active, list) else []
    ebay_unsold      = ebay_unsold      if isinstance(ebay_unsold, list) else []
    etsy_listings    = etsy_listings    if isinstance(etsy_listings, list) else []
    heritage_results = heritage_results if isinstance(heritage_results, list) else []
    bgg_result       = bgg_result       if isinstance(bgg_result, dict) else {}

    etsy_listings = _etsy_relevance_filter(etsy_listings, normalized)

    ebay_stats = compute_price_stats(ebay_sold, req.days_back)
    etsy_stats = compute_etsy_stats(etsy_listings)
    heritage_stats = compute_heritage_stats(heritage_results)
    unsold_stats = compute_unsold_stats(ebay_unsold)

    # Watch count summary for active listings
    total_watches = sum(l.get("watch_count", 0) for l in ebay_active)
    top_watched = sorted(
        [l for l in ebay_active if l.get("watch_count", 0) > 0],
        key=lambda x: x.get("watch_count", 0),
        reverse=True,
    )[:5]

    sources_data = {
        "etsy": {
            **etsy_stats,
            "listings": etsy_listings[:50],
            "configured": bool(__import__("config").settings.etsy_api_key),
        },
        "heritage": {
            **heritage_stats,
            "listings": heritage_results[:30],
        },
        "bgg": bgg_result if bgg_result.get("found") else None,
        "ebay_unsold": {
            **unsold_stats,
            "listings": ebay_unsold[:30],
        },
        "ebay_active": {
            "count": len(ebay_active),
            "total_watches": total_watches,
            "avg_watches": round(total_watches / len(ebay_active), 1) if ebay_active else 0,
            "top_watched": top_watched,
        },
        "ebay_debug": ebay_debug,
    }

    last_sold_dt = None
    if ebay_stats.get("last_sold_date"):
        try:
            last_sold_dt = datetime.fromisoformat(
                ebay_stats["last_sold_date"].replace("Z", "").split("+")[0]
            )
        except Exception:
            pass

    record = PriceResearchCache(
        search_query=normalized,
        category=req.category,
        fetched_at=datetime.utcnow(),
        avg_sold_price=ebay_stats["avg"],
        min_sold_price=ebay_stats["min"],
        max_sold_price=ebay_stats["max"],
        median_sold_price=ebay_stats["median"],
        sold_count_30d=ebay_stats["count_30d"],
        sold_count_60d=ebay_stats["count_60d"],
        sold_count_90d=ebay_stats["count_90d"],
        active_listing_count=len(ebay_active),
        condition_breakdown=json.dumps(ebay_stats["condition_breakdown"]),
        last_sold_date=last_sold_dt,
        raw_sold_listings=json.dumps(ebay_sold),
        source="ebay",
        sources_data=json.dumps(sources_data),
    )

    # Don't cache when eBay was blocked — a retry should hit live data
    if "ebay" not in source_errors:
        db.add(record)
        db.commit()
        db.refresh(record)
        _log_history(db, normalized, req.category, ebay_stats["count_90d"], ebay_stats["avg"])

    return _build_response(record, from_cache=False, source_errors=source_errors)


def _log_history(db: Session, query: str, category: str | None, count: int, avg: float | None):
    db.add(SearchHistory(query=query, category=category, result_count=count, avg_price=avg))
    db.commit()


@router.get("/history")
def get_history(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(SearchHistory)
        .order_by(SearchHistory.searched_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "query": r.query,
            "category": r.category,
            "searched_at": r.searched_at.isoformat(),
            "result_count": r.result_count,
            "avg_price": r.avg_price,
        }
        for r in rows
    ]
