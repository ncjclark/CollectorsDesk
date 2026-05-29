import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db, InventoryItem, PriceResearchCache
from models.schemas import InventoryItemCreate, InventoryItemUpdate, InventoryItemOut
from services.ebay import search_sold_listings, search_active_listings, compute_price_stats

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def _item_to_dict(item: InventoryItem, research: PriceResearchCache | None = None) -> dict:
    d = {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "year": item.year,
        "model_number": item.model_number,
        "barcode": item.barcode,
        "condition": item.condition,
        "quantity": item.quantity,
        "my_asking_price": item.my_asking_price,
        "last_research_date": item.last_research_date.isoformat() if item.last_research_date else None,
        "status": item.status,
        "ebay_listing_url": item.ebay_listing_url,
        "sold_price": item.sold_price,
        "sold_date": item.sold_date.isoformat() if item.sold_date else None,
        "notes": item.notes,
        "photo_path": item.photo_path,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
    if research:
        d["research"] = {
            "avg_sold_price": research.avg_sold_price,
            "min_sold_price": research.min_sold_price,
            "max_sold_price": research.max_sold_price,
            "median_sold_price": research.median_sold_price,
            "sold_count_30d": research.sold_count_30d,
            "active_listing_count": research.active_listing_count,
            "last_sold_date": research.last_sold_date.isoformat() if research.last_sold_date else None,
            "fetched_at": research.fetched_at.isoformat() if research.fetched_at else None,
            "condition_breakdown": json.loads(research.condition_breakdown or "{}"),
            "source": research.source,
        }
    return d


def _latest_research(db: Session, item_id: int) -> PriceResearchCache | None:
    return (
        db.query(PriceResearchCache)
        .filter(PriceResearchCache.linked_item_id == item_id)
        .order_by(PriceResearchCache.fetched_at.desc())
        .first()
    )


@router.get("")
def list_items(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    condition: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
):
    q = db.query(InventoryItem)
    if category:
        q = q.filter(InventoryItem.category == category)
    if status:
        q = q.filter(InventoryItem.status == status)
    if condition:
        q = q.filter(InventoryItem.condition == condition)
    if search:
        q = q.filter(InventoryItem.name.ilike(f"%{search}%"))

    col = getattr(InventoryItem, sort_by, InventoryItem.created_at)
    q = q.order_by(col.desc() if sort_dir == "desc" else col.asc())

    items = q.all()
    result = []
    for item in items:
        research = _latest_research(db, item.id)
        result.append(_item_to_dict(item, research))
    return result


@router.post("", status_code=201)
def create_item(body: InventoryItemCreate, db: Session = Depends(get_db)):
    item = InventoryItem(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_to_dict(item)


@router.get("/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    research = _latest_research(db, item_id)
    # Also attach all research history
    all_research = (
        db.query(PriceResearchCache)
        .filter(PriceResearchCache.linked_item_id == item_id)
        .order_by(PriceResearchCache.fetched_at.desc())
        .all()
    )
    d = _item_to_dict(item, research)
    d["research_history"] = [
        {
            "fetched_at": r.fetched_at.isoformat(),
            "avg_sold_price": r.avg_sold_price,
            "sold_count_30d": r.sold_count_30d,
            "source": r.source,
        }
        for r in all_research
    ]
    return d


@router.put("/{item_id}")
def update_item(item_id: int, body: InventoryItemUpdate, db: Session = Depends(get_db)):
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    item.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(item)
    research = _latest_research(db, item_id)
    return _item_to_dict(item, research)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    # Remove linked research cache records
    db.query(PriceResearchCache).filter(
        PriceResearchCache.linked_item_id == item_id
    ).delete()
    db.delete(item)
    db.commit()


@router.post("/{item_id}/research")
async def research_item(item_id: int, db: Session = Depends(get_db)):
    """Run a fresh eBay search for this item and attach the result."""
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    query = item.name
    sold_listings = await search_sold_listings(query, days_back=90)
    active_listings = await search_active_listings(query)
    stats = compute_price_stats(sold_listings, 90)

    last_sold_dt = None
    if stats.get("last_sold_date"):
        try:
            last_sold_dt = datetime.fromisoformat(
                stats["last_sold_date"].replace("Z", "").split("+")[0]
            )
        except Exception:
            pass

    record = PriceResearchCache(
        search_query=query.lower().strip(),
        category=item.category,
        fetched_at=datetime.utcnow(),
        avg_sold_price=stats["avg"],
        min_sold_price=stats["min"],
        max_sold_price=stats["max"],
        median_sold_price=stats["median"],
        sold_count_30d=stats["count_30d"],
        sold_count_60d=stats["count_60d"],
        sold_count_90d=stats["count_90d"],
        active_listing_count=len(active_listings),
        condition_breakdown=json.dumps(stats["condition_breakdown"]),
        last_sold_date=last_sold_dt,
        raw_sold_listings=json.dumps(sold_listings),
        source="mock" if not bool(__import__("config").settings.ebay_app_id) else "ebay",
        linked_item_id=item_id,
    )
    db.add(record)
    item.last_research_date = datetime.utcnow()
    db.commit()
    db.refresh(record)

    return {
        "message": f"Research complete — {stats['count_90d']} sold listings found",
        "stats": stats,
        "active_listing_count": len(active_listings),
    }


@router.post("/{item_id}/generate-listing")
def generate_listing(item_id: int, db: Session = Depends(get_db)):
    """Generate a suggested eBay listing title, description, and price."""
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    research = (
        db.query(PriceResearchCache)
        .filter(PriceResearchCache.linked_item_id == item_id)
        .order_by(PriceResearchCache.fetched_at.desc())
        .first()
    )

    # Build title (eBay recommends 60–80 chars, keyword-rich)
    parts = []
    if item.category == "barbie":
        parts.append("Vintage")
    parts.append(item.name)
    if item.year:
        parts.append(str(item.year))
    if item.model_number:
        parts.append(item.model_number)
    if item.condition:
        cond_map = {
            "sealed": "NRFB",
            "complete": "Complete",
            "incomplete": "Incomplete",
            "loose": "Loose",
            "damaged": "As-Is",
        }
        parts.append(cond_map.get(item.condition, item.condition.title()))
    if item.category == "barbie":
        parts.append("Mattel Doll Collectible")
    elif item.category == "board_game":
        parts.append("Board Game Vintage")

    title = " ".join(parts)
    if len(title) > 80:
        title = title[:77] + "..."

    # Condition description
    cond_desc = {
        "sealed": "Never removed from box (NRFB). Original factory seal intact.",
        "complete": "Complete with all original pieces and accessories. Plays perfectly.",
        "incomplete": "Incomplete — some pieces missing. See notes for details.",
        "loose": "Loose item, no box. Good displayable condition.",
        "damaged": "Sold as-is for parts or restoration. See photos for condition.",
    }.get(item.condition or "", "See photos for full condition details.")

    if item.notes:
        cond_desc += f" {item.notes}"

    # Suggested price
    suggested_price = None
    price_note = ""
    if item.my_asking_price:
        suggested_price = item.my_asking_price
        price_note = "Based on your asking price."
    elif research and research.avg_sold_price:
        # Price slightly below avg to move quickly
        suggested_price = round(research.avg_sold_price * 0.95, 2)
        price_note = f"Based on eBay avg of ${research.avg_sold_price:.2f} (priced 5% below avg for faster sale)."

    return {
        "title": title,
        "condition_description": cond_desc,
        "suggested_price": suggested_price,
        "price_note": price_note,
        "research_avg": research.avg_sold_price if research else None,
        "research_range": f"${research.min_sold_price:.2f}–${research.max_sold_price:.2f}" if research and research.min_sold_price else None,
    }


