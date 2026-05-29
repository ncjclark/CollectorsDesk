"""
Etsy API service — active vintage listings.

Etsy is valuable because:
- Large community of dedicated vintage Barbie/doll sellers
- Prices reflect true collector market (often higher than casual eBay buyers)
- Active listings show current asking prices across many specialist sellers

Setup: get a free API key at https://developers.etsy.com/
Add ETSY_API_KEY to .env

Mock mode auto-enables when ETSY_API_KEY is empty.
"""

import asyncio
import random
import httpx
from config import settings


async def search_etsy_listings(query: str, max_results: int = 50) -> list[dict]:
    if not settings.etsy_api_key:
        return _mock_etsy(query)
    return await _real_etsy(query, max_results)


def _mock_etsy(query: str) -> list[dict]:
    q = query.lower()
    rng = random.Random((hash(q) + 42) % (2**32))

    # Etsy prices tend to be 15–40% higher than eBay — collector premium
    if any(k in q for k in ["ponytail", "#1", "1959", "1960", "1961"]):
        base, spread = 380, 200
    elif any(k in q for k in ["bubblecut", "bubble cut", "francie", "stacey"]):
        base, spread = 95, 60
    elif any(k in q for k in ["malibu", "mod", "twist"]):
        base, spread = 65, 40
    elif any(k in q for k in ["barbie", "doll", "mattel", "ken", "skipper"]):
        base, spread = 42, 30
    else:
        base, spread = 35, 25

    count = rng.randint(8, 28)
    conditions = ["NRFB", "Mint", "Excellent", "Very Good", "Good", "Fair"]
    cond_weights = [0.05, 0.10, 0.25, 0.30, 0.20, 0.10]
    cond_multipliers = {"NRFB": 1.8, "Mint": 1.4, "Excellent": 1.1, "Very Good": 0.9, "Good": 0.7, "Fair": 0.45}

    results = []
    shops = ["VintageDollHouse", "CollectorsCorner", "RetroToybox", "DollMemories",
             "ClassicBarbieFan", "VintageMattelShop", "DollsAndDreams", "TimeCapsuleToys"]

    for i in range(count):
        cond = rng.choices(conditions, weights=cond_weights, k=1)[0]
        mult = cond_multipliers[cond]
        price = max(4.99, round((base + rng.uniform(-spread * 0.4, spread * 0.7)) * mult, 2))
        shop = rng.choice(shops)

        results.append({
            "title": f"{query.title()} — {cond} Condition — Vintage Collectible",
            "price": price,
            "condition": cond,
            "url": f"https://www.etsy.com/listing/mock-{abs(hash(query+str(i))) % 9999999:07d}",
            "image_url": None,
            "shop_name": shop,
            "currency": "USD",
            "listing_type": "active",
        })

    return sorted(results, key=lambda x: x["price"])


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
