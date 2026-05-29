from fastapi import APIRouter, HTTPException

from models.schemas import BarcodeRequest, BarcodeResponse
from services.barcode import lookup_barcode

router = APIRouter(prefix="/api/identify", tags=["identify"])


@router.post("/barcode", response_model=BarcodeResponse)
async def barcode_lookup(req: BarcodeRequest):
    if not req.upc or not req.upc.strip():
        raise HTTPException(400, "UPC is required")
    result = await lookup_barcode(req.upc.strip())
    return BarcodeResponse(**result) if result.get("found") else BarcodeResponse(found=False)
