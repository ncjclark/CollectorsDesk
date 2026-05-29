import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, InventoryItem

router = APIRouter(prefix="/api", tags=["import_export"])

CSV_COLUMNS = [
    "name", "category", "year", "model_number", "barcode",
    "condition", "quantity", "my_asking_price", "status", "notes",
]

VALID_CATEGORIES  = {"barbie", "board_game", ""}
VALID_CONDITIONS  = {"sealed", "complete", "incomplete", "loose", "damaged", ""}
VALID_STATUSES    = {"not_listed", "listed", "sold", "hold", ""}


@router.get("/import/template")
def download_template():
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    # Example rows
    writer.writerow({
        "name": "Malibu Barbie", "category": "barbie", "year": "1971",
        "model_number": "#1067", "barcode": "", "condition": "complete",
        "quantity": "1", "my_asking_price": "45.00", "status": "not_listed",
        "notes": "Original swimsuit, good hair",
    })
    writer.writerow({
        "name": "Monopoly", "category": "board_game", "year": "1961",
        "model_number": "", "barcode": "", "condition": "complete",
        "quantity": "1", "my_asking_price": "", "status": "not_listed",
        "notes": "All pieces present, box fair",
    })
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_template.csv"},
    )


@router.post("/import/csv")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # handles BOM from Excel
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    imported = 0
    skipped = []

    for i, row in enumerate(reader, start=2):  # start=2 because row 1 is header
        name = (row.get("name") or "").strip()
        if not name:
            skipped.append({"row": i, "reason": "Missing name", "data": dict(row)})
            continue

        category = (row.get("category") or "").strip().lower()
        if category not in VALID_CATEGORIES:
            skipped.append({"row": i, "reason": f"Invalid category '{category}' (use: barbie, board_game)", "data": dict(row)})
            continue

        condition = (row.get("condition") or "").strip().lower()
        if condition not in VALID_CONDITIONS:
            skipped.append({"row": i, "reason": f"Invalid condition '{condition}' (use: sealed, complete, incomplete, loose, damaged)", "data": dict(row)})
            continue

        status = (row.get("status") or "not_listed").strip().lower()
        if status not in VALID_STATUSES:
            status = "not_listed"

        year = None
        raw_year = (row.get("year") or "").strip()
        if raw_year:
            try:
                year = int(raw_year)
            except ValueError:
                skipped.append({"row": i, "reason": f"Invalid year '{raw_year}'", "data": dict(row)})
                continue

        quantity = 1
        raw_qty = (row.get("quantity") or "1").strip()
        if raw_qty:
            try:
                quantity = max(1, int(raw_qty))
            except ValueError:
                quantity = 1

        asking = None
        raw_price = (row.get("my_asking_price") or "").strip().lstrip("$")
        if raw_price:
            try:
                asking = float(raw_price)
            except ValueError:
                pass

        item = InventoryItem(
            name=name,
            category=category or None,
            year=year,
            model_number=(row.get("model_number") or "").strip() or None,
            barcode=(row.get("barcode") or "").strip() or None,
            condition=condition or None,
            quantity=quantity,
            my_asking_price=asking,
            status=status or "not_listed",
            notes=(row.get("notes") or "").strip() or None,
        )
        db.add(item)
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped}


@router.get("/export/csv")
def export_csv(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(InventoryItem)
    if status:
        q = q.filter(InventoryItem.status == status)
    if category:
        q = q.filter(InventoryItem.category == category)
    items = q.order_by(InventoryItem.name).all()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()

    for item in items:
        writer.writerow({
            "name": item.name or "",
            "category": item.category or "",
            "year": item.year or "",
            "model_number": item.model_number or "",
            "barcode": item.barcode or "",
            "condition": item.condition or "",
            "quantity": item.quantity or 1,
            "my_asking_price": item.my_asking_price or "",
            "status": item.status or "not_listed",
            "notes": item.notes or "",
        })

    output.seek(0)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    filename = f"inventory_{timestamp}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
