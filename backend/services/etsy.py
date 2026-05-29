"""
Etsy API service — active vintage listings.

Requires ETSY_API_KEY in .env (get a free key at developers.etsy.com).
Returns empty list until key is configured — Etsy tab will show setup prompt.
"""

import asyncio
import httpx
from config import settings


async def search_etsy_listings(query: str, max_results: int = 50) -> list[dict]:
    if not settings.etsy_api_key:
        return []
    return await _real_etsy(query, max_results)


async def _real_etsy(query: str, max_results: int) -> list[dict]:
    headers = {"x-api-key": settings.etsy_api_key}
    params = {
        "keywords": query,
        "limit": min(max_results, 100),
        "sort_on": "score",
        "sort_order": "desc",
    }

    # Retry with exponential backoff on 429 (rate limit)
    data = None
    for attempt in range(4):
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                "https://openapi.etsy.com/v3/application/listings/active",
                headers=headers,
                params=params,
            )

        if resp.status_code == 429:
            if attempt < 3:
                wait = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(wait)
                continue
            return []  # exhausted retries — return empty rather than crash

        resp.raise_for_status()
        data = resp.json()
        break

    if data is None:
        return []

    results = []
    for listing in data.get("results", []):
        try:
            price_obj = listing.get("price", {})
            # Etsy returns price as {amount: 4500, divisor: 100, currency_code: "USD"} → $45.00
            raw = price_obj.get("amount", 0)
            divisor = price_obj.get("divisor", 100) or 100
            price = round(raw / divisor, 2)

            results.append({
                "title": listing.get("title", ""),
                "price": price,
                "condition": None,  # Etsy doesn't standardize condition
                "url": listing.get("url", ""),
                "image_url": (listing.get("images") or [{}])[0].get("url_570xN"),
                "shop_name": listing.get("shop", {}).get("shop_name", ""),
                "currency": price_obj.get("currency_code", "USD"),
                "listing_type": "active",
            })
        except (KeyError, ZeroDivisionError):
            continue

    return results


def compute_etsy_stats(listings: list[dict]) -> dict:
    if not listings:
        return {"count": 0, "avg": None, "min": None, "max": None, "median": None}
    import statistics
    prices = [l["price"] for l in listings if l.get("price")]
    if not prices:
        return {"count": 0, "avg": None, "min": None, "max": None, "median": None}
    return {
        "count": len(prices),
        "avg": round(statistics.mean(prices), 2),
        "min": round(min(prices), 2),
        "max": round(max(prices), 2),
        "median": round(statistics.median(prices), 2),
        "note": "Active asking prices — not confirmed sales",
    }
