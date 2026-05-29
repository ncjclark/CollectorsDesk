import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db, InventoryItem, PriceResearchCache

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    items = db.query(InventoryItem).all()

    if not items:
        return {
            "totals": {"items": 0, "barbie": 0, "board_games": 0, "estimated_value": 0},
            "by_status": {},
            "revenue": {"total_sold_price": 0, "count_sold": 0, "avg_sale_price": 0},
            "condition_breakdown": {},
            "top_value_items": [],
            "needs_research": [],
            "category_breakdown": [],
            "monthly_revenue": [],
        }

    # Totals
    total = len(items)
    barbie_count = sum(1 for i in items if i.category == "barbie")
    game_count = sum(1 for i in items if i.category == "board_game")

    # Latest research per item
    research_map: dict[int, PriceResearchCache] = {}
    for item in items:
        rec = (
            db.query(PriceResearchCache)
            .filter(PriceResearchCache.linked_item_id == item.id)
            .order_by(PriceResearchCache.fetched_at.desc())
            .first()
        )
        if rec:
            research_map[item.id] = rec

    # Estimated value: sum of avg_sold_price for researched items; use asking price as fallback
    est_value = 0.0
    for item in items:
        if item.status == "sold":
            continue
        r = research_map.get(item.id)
        if r and r.avg_sold_price:
            est_value += r.avg_sold_price * (item.quantity or 1)
        elif item.my_asking_price:
            est_value += item.my_asking_price * (item.quantity or 1)

    # By status
    by_status: dict[str, int] = {}
    for item in items:
        s = item.status or "not_listed"
        by_status[s] = by_status.get(s, 0) + 1

    # Revenue (sold items)
    sold_items = [i for i in items if i.status == "sold" and i.sold_price]
    total_revenue = sum(i.sold_price for i in sold_items)
    avg_sale = (total_revenue / len(sold_items)) if sold_items else 0

    # Condition breakdown
    cond_breakdown: dict[str, int] = {}
    for item in items:
        c = item.condition or "unknown"
        cond_breakdown[c] = cond_breakdown.get(c, 0) + 1

    # Top 10 most valuable (by avg eBay price)
    valued = []
    for item in items:
        r = research_map.get(item.id)
        if r and r.avg_sold_price:
            valued.append({
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "condition": item.condition,
                "avg_sold_price": r.avg_sold_price,
                "my_asking_price": item.my_asking_price,
                "status": item.status,
            })
    top_value = sorted(valued, key=lambda x: x["avg_sold_price"], reverse=True)[:10]

    # Needs research: never researched OR last researched >30 days ago
    stale_cutoff = datetime.utcnow() - timedelta(days=30)
    needs_research = []
    for item in items:
        if item.status == "sold":
            continue
        if not item.last_research_date or item.last_research_date < stale_cutoff:
            needs_research.append({
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "last_research_date": item.last_research_date.isoformat() if item.last_research_date else None,
                "status": item.status,
            })
    needs_research = needs_research[:20]

    # Category breakdown for chart
    category_breakdown = [
        {"name": "Barbie / Dolls", "count": barbie_count},
        {"name": "Board Games", "count": game_count},
        {"name": "Other", "count": total - barbie_count - game_count},
    ]
    category_breakdown = [c for c in category_breakdown if c["count"] > 0]

    # Monthly revenue (last 6 months)
    monthly: dict[str, float] = {}
    for item in sold_items:
        if item.sold_date:
            key = item.sold_date.strftime("%b %Y")
            monthly[key] = monthly.get(key, 0) + (item.sold_price or 0)

    return {
        "totals": {
            "items": total,
            "barbie": barbie_count,
            "board_games": game_count,
            "estimated_value": round(est_value, 2),
        },
        "by_status": by_status,
        "revenue": {
            "total_sold_price": round(total_revenue, 2),
            "count_sold": len(sold_items),
            "avg_sale_price": round(avg_sale, 2),
        },
        "condition_breakdown": cond_breakdown,
        "top_value_items": top_value,
        "needs_research": needs_research,
        "category_breakdown": category_breakdown,
        "monthly_revenue": [{"month": k, "revenue": round(v, 2)} for k, v in monthly.items()],
    }
