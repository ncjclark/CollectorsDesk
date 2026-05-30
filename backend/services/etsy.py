"""
Etsy service — active vintage listings.

When ETSY_API_KEY is set, uses the official API.
Otherwise falls back to a Playwright scraper (rate-limit-friendly:
one page per query, 24h cache prevents repeat scrapes).
"""

import asyncio
import httpx
from config import settings


async def search_etsy_listings(query: str, max_results: int = 50) -> list[dict]:
    if settings.etsy_api_key:
        return await _real_etsy(query, max_results)
    return await _scrape_etsy(query)


# ---------------------------------------------------------------------------
# Official API (used when ETSY_API_KEY is configured)
# ---------------------------------------------------------------------------

async def _real_etsy(query: str, max_results: int) -> list[dict]:
    headers = {"x-api-key": settings.etsy_api_key}
    params = {
        "keywords": query,
        "limit": min(max_results, 100),
        "sort_on": "score",
        "sort_order": "desc",
    }

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
                await asyncio.sleep(2 ** attempt)
                continue
            return []

        resp.raise_for_status()
        data = resp.json()
        break

    if data is None:
        return []

    results = []
    for listing in data.get("results", []):
        try:
            price_obj = listing.get("price", {})
            raw = price_obj.get("amount", 0)
            divisor = price_obj.get("divisor", 100) or 100
            price = round(raw / divisor, 2)

            results.append({
                "title": listing.get("title", ""),
                "price": price,
                "condition": None,
                "url": listing.get("url", ""),
                "image_url": (listing.get("images") or [{}])[0].get("url_570xN"),
                "shop_name": listing.get("shop", {}).get("shop_name", ""),
                "currency": price_obj.get("currency_code", "USD"),
                "listing_type": "active",
            })
        except (KeyError, ZeroDivisionError):
            continue

    return results


# ---------------------------------------------------------------------------
# Playwright scraper fallback
# ---------------------------------------------------------------------------

_ETSY_JS_EXTRACT = """() => {
    function listingId(href) {
        const parts = href.split('/listing/');
        return parts.length < 2 ? null : parts[1].split('/')[0].split('?')[0];
    }

    const results = [];
    const seenIds = new Set();

    // Each card is a div.listing-link — Etsy's search grid card wrapper
    const cards = document.querySelectorAll('div.listing-link');

    for (const card of cards) {
        const linkEl = card.querySelector("a[href*='/listing/']");
        if (!linkEl) continue;
        const id = listingId(linkEl.href);
        if (!id || seenIds.has(id)) continue;

        // Price: div.n-listing-card__price contains the display price
        const priceEl = (
            card.querySelector('div.n-listing-card__price') ||
            card.querySelector('p.lc-price')
        );
        if (!priceEl) continue;
        const priceText = priceEl.textContent.trim();
        const priceMatch = priceText.match(/([\\d,]+\\.?\\d*)/);
        if (!priceMatch) continue;
        const price = parseFloat(priceMatch[1].replace(/,/g, ''));
        if (!price || price <= 0) continue;

        const titleEl = card.querySelector('h3') || card.querySelector('h2');
        const title = titleEl ? titleEl.textContent.trim() : '';
        if (!title || title.length < 5) continue;

        seenIds.add(id);
        results.push({ title, price, url: 'https://www.etsy.com/listing/' + id });
        if (results.length >= 48) break;
    }

    return results;
}"""


async def _scrape_etsy(query: str) -> list[dict]:
    try:
        return await _do_scrape(query)
    except Exception:
        return []


async def _do_scrape(query: str) -> list[dict]:
    from playwright.async_api import async_playwright
    from urllib.parse import quote_plus

    search_url = f"https://www.etsy.com/search?q={quote_plus(query)}"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()

        # Warmup: visit homepage to get session cookies
        await page.goto("https://www.etsy.com", wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)

        await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(5)

        raw = await page.evaluate(_ETSY_JS_EXTRACT)
        await browser.close()

    results = []
    for item in raw:
        try:
            price = float(item["price"])
            if price <= 0:
                continue
            results.append({
                "title": item["title"][:200],
                "price": round(price, 2),
                "condition": None,
                "url": item["url"],
                "image_url": None,
                "shop_name": "",
                "currency": "USD",
                "listing_type": "active",
            })
        except (KeyError, ValueError, TypeError):
            continue

    return results


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

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
