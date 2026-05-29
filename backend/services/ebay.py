"""
eBay service — scrapes eBay's public search pages, no API key required.

Mode selection (checked in order):
  1. EBAY_APP_ID set → use official eBay API
  2. (default)       → scrape eBay public search pages using headless Chrome
"""

import asyncio
import base64
import os
import re
import statistics
from datetime import datetime, timedelta
import httpx

from config import settings


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def search_sold_listings(
    query: str,
    days_back: int = 90,
    max_results: int = 100,
) -> list[dict]:
    if _use_api():
        return await _real_sold_listings(query, days_back, max_results)
    return await _scrape_sold_listings(query, max_results)


async def search_active_listings(
    query: str,
    max_results: int = 50,
) -> list[dict]:
    if _use_api():
        return await _real_active_listings(query, max_results)
    return await _scrape_active_listings(query, max_results)


async def search_unsold_listings(
    query: str,
    days_back: int = 90,
    max_results: int = 50,
) -> list[dict]:
    if _use_api():
        return await _real_unsold_listings(query, days_back, max_results)
    return await _scrape_unsold_listings(query, max_results)


def compute_unsold_stats(listings: list[dict]) -> dict:
    if not listings:
        return {"count": 0, "avg": None, "min": None, "max": None}
    prices = [l["price"] for l in listings if l.get("price")]
    if not prices:
        return {"count": 0, "avg": None, "min": None, "max": None}
    return {
        "count": len(prices),
        "avg": round(statistics.mean(prices), 2),
        "min": round(min(prices), 2),
        "max": round(max(prices), 2),
    }


def compute_price_stats(sold_listings: list[dict], days_back: int = 90) -> dict:
    if not sold_listings:
        return {
            "avg": None, "min": None, "max": None, "median": None,
            "count_30d": 0, "count_60d": 0, "count_90d": 0,
            "condition_breakdown": {}, "last_sold_date": None,
        }

    now = datetime.utcnow()
    prices = []
    count_30 = count_60 = count_90 = 0
    cond_prices: dict[str, list[float]] = {}

    for item in sold_listings:
        price = item.get("price", 0)
        end_time_str = item.get("end_time", "")
        try:
            end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00").replace("+00:00", ""))
        except Exception:
            end_time = now - timedelta(days=1)

        days_ago = (now - end_time).days
        if days_ago <= 90:
            prices.append(price)
            count_90 += 1
        if days_ago <= 60:
            count_60 += 1
        if days_ago <= 30:
            count_30 += 1

        cond = item.get("condition", "Unknown") or "Unknown"
        cond_prices.setdefault(cond, []).append(price)

    if not prices:
        prices = [item.get("price", 0) for item in sold_listings]

    condition_breakdown = {
        cond: round(statistics.mean(vals), 2)
        for cond, vals in cond_prices.items()
    }

    sorted_dates = sorted(
        [item.get("end_time", "") for item in sold_listings],
        reverse=True,
    )

    return {
        "avg": round(statistics.mean(prices), 2) if prices else None,
        "min": round(min(prices), 2) if prices else None,
        "max": round(max(prices), 2) if prices else None,
        "median": round(statistics.median(prices), 2) if prices else None,
        "count_30d": count_30,
        "count_60d": count_60,
        "count_90d": count_90,
        "condition_breakdown": condition_breakdown,
        "last_sold_date": sorted_dates[0] if sorted_dates else None,
    }


# ---------------------------------------------------------------------------
# Scraper implementation (default — no API key needed)
# ---------------------------------------------------------------------------

def _use_api() -> bool:
    return bool(settings.ebay_app_id)


def _parse_ebay_date(text: str) -> str | None:
    if not text:
        return None
    text = re.sub(r'^(Sold|Ended?)\s*', '', text.strip(), flags=re.IGNORECASE).strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return None


# JavaScript run inside the live browser DOM to extract listing cards
_EBAY_JS_EXTRACT = """(unsoldOnly) => {
    const cards = document.querySelectorAll("li.s-card");
    const results = [];
    for (const card of cards) {
        const titleEl = card.querySelector("[class*=title]") || card.querySelector("h3");
        if (!titleEl) continue;
        const title = titleEl.textContent.trim().replace(/^New Listing\\s*/i, "");
        if (!title || title.toLowerCase() === "shop on ebay") continue;

        const priceEl = card.querySelector("[class*=price]");
        if (!priceEl) continue;
        const priceMatch = priceEl.textContent.trim().match(/\\$([0-9,]+\\.?\\d*)/);
        if (!priceMatch) continue;
        const price = parseFloat(priceMatch[1].replace(/,/g, ""));
        if (!price) continue;

        const linkEl = card.querySelector("a[href*='ebay.com/itm']");
        const url = linkEl ? linkEl.href : "";

        const fullText = card.innerText || "";
        const soldMatch = fullText.match(/^(Sold|Ended)\\s+([A-Za-z]+ \\d+,? \\d{4})/m);
        const isSold = soldMatch && soldMatch[1].toLowerCase() === "sold";
        const dateStr = soldMatch ? soldMatch[2] : null;

        if (unsoldOnly && isSold) continue;
        if (!unsoldOnly && soldMatch && !isSold) continue;

        const condMatch = fullText.match(/Pre-Owned|Brand New|Open Box|For Parts|Refurbished|Used|Not Specified/i);
        const condition = condMatch ? condMatch[0] : "Used";

        results.push({ title, price, url, condition, dateStr });
    }
    return results;
}"""


async def _ebay_page(params: dict) -> list[dict]:
    """Load an eBay search page in real Chrome and extract listings from the live DOM."""
    from playwright.async_api import async_playwright
    from urllib.parse import urlencode

    unsold_only = params.pop("_unsold_only", False)
    url = "https://www.ebay.com/sch/i.html?" + urlencode(params)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()
        await page.goto("https://www.ebay.com", wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(1)
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(6)
        raw = await page.evaluate(_EBAY_JS_EXTRACT, unsold_only)
        await browser.close()

    now = datetime.utcnow()
    results = []
    for item in raw:
        end_time = _parse_ebay_date(item["dateStr"]) if item["dateStr"] else now.strftime("%Y-%m-%dT%H:%M:%S")
        results.append({
            "title": item["title"],
            "price": item["price"],
            "end_time": end_time,
            "condition": item["condition"],
            "url": item["url"],
            "image_url": None,
        })
    return results


async def _scrape_sold_listings(query: str, max_results: int) -> list[dict]:
    items = await _ebay_page({"_nkw": query, "LH_Sold": "1", "LH_Complete": "1", "_sacat": "0", "_ipg": "60"})
    return items[:max_results]


async def _scrape_active_listings(query: str, max_results: int) -> list[dict]:
    items = await _ebay_page({"_nkw": query, "_sacat": "0", "_ipg": "60"})
    for item in items:
        item.setdefault("watch_count", 0)
    return items[:max_results]


async def _scrape_unsold_listings(query: str, max_results: int) -> list[dict]:
    items = await _ebay_page({"_nkw": query, "LH_Complete": "1", "_sacat": "0", "_ipg": "60", "_unsold_only": True})
    return items[:max_results]


# ---------------------------------------------------------------------------
# Official eBay API (only used if EBAY_APP_ID is set in .env)
# ---------------------------------------------------------------------------

_oauth_cache: dict = {}


async def _get_oauth_token() -> str:
    global _oauth_cache
    now = datetime.utcnow()
    if _oauth_cache.get("token") and _oauth_cache.get("expires_at", now) > now:
        return _oauth_cache["token"]

    credentials = base64.b64encode(
        f"{settings.ebay_app_id}:{settings.ebay_cert_id}".encode()
    ).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.ebay_browse_base_url}/identity/v1/oauth2/token",
            headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

    _oauth_cache = {
        "token": data["access_token"],
        "expires_at": now + timedelta(seconds=data["expires_in"] - 60),
    }
    return _oauth_cache["token"]


async def _real_sold_listings(query: str, days_back: int, max_results: int) -> list[dict]:
    params = {
        "OPERATION-NAME": "findCompletedItems",
        "SERVICE-VERSION": "1.0.0",
        "SECURITY-APPNAME": settings.ebay_app_id,
        "RESPONSE-DATA-FORMAT": "JSON",
        "keywords": query,
        "itemFilter(0).name": "SoldItemsOnly",
        "itemFilter(0).value": "true",
        "paginationInput.entriesPerPage": str(min(max_results, 100)),
        "sortOrder": "EndTimeSoonest",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.ebay_finding_base_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

    items = (data.get("findCompletedItemsResponse", [{}])[0]
                 .get("searchResult", [{}])[0].get("item", []))
    results = []
    for item in items:
        try:
            selling = item.get("sellingStatus", [{}])[0]
            price = float(selling.get("currentPrice", [{}])[0].get("__value__", 0))
            results.append({
                "title": item.get("title", [""])[0],
                "price": price,
                "end_time": item.get("listingInfo", [{}])[0].get("endTime", [""])[0],
                "condition": item.get("condition", [{}])[0].get("conditionDisplayName", ["Unknown"])[0],
                "url": item.get("viewItemURL", [""])[0],
                "image_url": item.get("galleryURL", [None])[0],
            })
        except (IndexError, KeyError, ValueError):
            continue
    return results


async def _real_active_listings(query: str, max_results: int) -> list[dict]:
    token = await _get_oauth_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.ebay_browse_base_url}/buy/browse/v1/item_summary/search",
            params={"q": query, "limit": str(min(max_results, 200)), "fieldgroups": "EXTENDED"},
            headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("itemSummaries", []):
        try:
            results.append({
                "title": item.get("title", ""),
                "price": float(item.get("price", {}).get("value", 0)),
                "condition": item.get("condition", "Unknown"),
                "url": item.get("itemWebUrl", ""),
                "image_url": item.get("image", {}).get("imageUrl"),
                "watch_count": item.get("watchCount", 0),
            })
        except (KeyError, ValueError):
            continue
    return results


async def _real_unsold_listings(query: str, days_back: int, max_results: int) -> list[dict]:
    params = {
        "OPERATION-NAME": "findCompletedItems",
        "SERVICE-VERSION": "1.0.0",
        "SECURITY-APPNAME": settings.ebay_app_id,
        "RESPONSE-DATA-FORMAT": "JSON",
        "keywords": query,
        "paginationInput.entriesPerPage": str(min(max_results, 100)),
        "sortOrder": "EndTimeSoonest",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.ebay_finding_base_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

    items = (data.get("findCompletedItemsResponse", [{}])[0]
                 .get("searchResult", [{}])[0].get("item", []))
    results = []
    for item in items:
        try:
            selling = item.get("sellingStatus", [{}])[0]
            if selling.get("sellingState", [""])[0] == "EndedWithSales":
                continue
            results.append({
                "title": item.get("title", [""])[0],
                "price": float(selling.get("currentPrice", [{}])[0].get("__value__", 0)),
                "end_time": item.get("listingInfo", [{}])[0].get("endTime", [""])[0],
                "condition": item.get("condition", [{}])[0].get("conditionDisplayName", ["Unknown"])[0],
                "url": item.get("viewItemURL", [""])[0],
                "image_url": item.get("galleryURL", [None])[0],
            })
        except (IndexError, KeyError, ValueError):
            continue
    return results
