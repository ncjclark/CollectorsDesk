import httpx


async def lookup_barcode(upc: str) -> dict:
    """Look up a UPC barcode. Returns product info or {found: False}."""
    upc = upc.strip().lstrip("0") or upc.strip()

    # Try UPCItemDB (free, no key, 100/day)
    result = await _try_upcitemdb(upc)
    if result:
        return result

    # Fallback: Open Food Facts (free, no key)
    result = await _try_openfoodfacts(upc)
    if result:
        return result

    return {"found": False}


async def _try_upcitemdb(upc: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                "https://api.upcitemdb.com/prod/trial/lookup",
                params={"upc": upc},
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return None
            item = items[0]
            return {
                "found": True,
                "name": item.get("title") or item.get("brand", ""),
                "brand": item.get("brand", ""),
                "description": item.get("description", ""),
                "category": item.get("category", ""),
                "source": "upcitemdb",
            }
    except Exception:
        return None


async def _try_openfoodfacts(upc: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                f"https://world.openfoodfacts.org/api/v0/product/{upc}.json",
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("status") != 1:
                return None
            product = data.get("product", {})
            name = product.get("product_name") or product.get("brands", "")
            if not name:
                return None
            return {
                "found": True,
                "name": name,
                "brand": product.get("brands", ""),
                "description": product.get("generic_name", ""),
                "category": product.get("categories", ""),
                "source": "openfoodfacts",
            }
    except Exception:
        return None
