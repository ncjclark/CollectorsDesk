"""
eBay service — scrapes eBay's public search pages, no API key required.

Mode selection (checked in order):
  1. EBAY_MOCK_MODE=true  → always use generated mock data (for offline dev)
  2. EBAY_APP_ID set      → use official eBay API
  3. (default)            → scrape eBay public search pages
"""

import asyncio
import base64
import json
import os
import re
import random
import statistics
from datetime import datetime, timedelta
from typing import Optional
import httpx
from bs4 import BeautifulSoup

from config import settings

# ---------------------------------------------------------------------------
# Public interface (same shape whether mock or real)
# ---------------------------------------------------------------------------

async def search_sold_listings(
    query: str,
    days_back: int = 90,
    max_results: int = 100,
) -> list[dict]:
    """Return a list of sold eBay listings for the query."""
    if _use_mock():
        return _mock_sold_listings(query, days_back)
    if _use_api():
        return await _real_sold_listings(query, days_back, max_results)
    return await _scrape_sold_listings(query, max_results)


async def search_active_listings(
    query: str,
    max_results: int = 50,
) -> list[dict]:
    """Return a list of active (currently for sale) eBay listings."""
    if _use_mock():
        return _mock_active_listings(query)
    if _use_api():
        return await _real_active_listings(query, max_results)
    return await _scrape_active_listings(query, max_results)


async def search_unsold_listings(
    query: str,
    days_back: int = 90,
    max_results: int = 50,
) -> list[dict]:
    """Return completed eBay listings that did NOT sell — shows price ceiling."""
    if _use_mock():
        return _mock_unsold_listings(query, days_back)
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
    """Compute summary stats from a list of sold listings."""
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
            end_time = now - timedelta(days=random.randint(1, days_back))

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
# Mock implementation
# ---------------------------------------------------------------------------

def _use_mock() -> bool:
    return os.environ.get("EBAY_MOCK_MODE", "").lower() == "true"

def _use_api() -> bool:
    return bool(settings.ebay_app_id)


# Realistic seed data keyed by keywords in the search query
_BARBIE_SEEDS = {
    "malibu":        {"base": 45,  "spread": 30,  "label": "Malibu Barbie"},
    "ponytail":      {"base": 280, "spread": 150, "label": "Barbie #1 Ponytail"},
    "twist n turn":  {"base": 55,  "spread": 35,  "label": "Twist 'N Turn Barbie"},
    "bubblecut":     {"base": 65,  "spread": 40,  "label": "Bubble Cut Barbie"},
    "bubble cut":    {"base": 65,  "spread": 40,  "label": "Bubble Cut Barbie"},
    "mod":           {"base": 40,  "spread": 25,  "label": "Mod Era Barbie"},
    "holiday":       {"base": 35,  "spread": 20,  "label": "Holiday Barbie"},
    "ken":           {"base": 22,  "spread": 15,  "label": "Ken Doll"},
    "skipper":       {"base": 30,  "spread": 20,  "label": "Skipper"},
    "superstar":     {"base": 18,  "spread": 12,  "label": "Superstar Barbie"},
    "total hair":    {"base": 25,  "spread": 15,  "label": "Total Hair Barbie"},
    "stacey":        {"base": 75,  "spread": 50,  "label": "Stacey Doll"},
    "francie":       {"base": 90,  "spread": 60,  "label": "Francie Doll"},
    "tuesday taylor":{"base": 45,  "spread": 30,  "label": "Tuesday Taylor"},
    "barbie":        {"base": 28,  "spread": 20,  "label": "Vintage Barbie"},
}

_GAME_SEEDS = {
    "monopoly":      {"base": 22,  "spread": 18,  "label": "Monopoly"},
    "clue":          {"base": 18,  "spread": 12,  "label": "Clue"},
    "scrabble":      {"base": 15,  "spread": 10,  "label": "Scrabble"},
    "sorry":         {"base": 20,  "spread": 14,  "label": "Sorry!"},
    "risk":          {"base": 25,  "spread": 18,  "label": "Risk"},
    "life":          {"base": 18,  "spread": 12,  "label": "Game of Life"},
    "candyland":     {"base": 16,  "spread": 10,  "label": "Candy Land"},
    "chutes":        {"base": 14,  "spread": 8,   "label": "Chutes and Ladders"},
    "operation":     {"base": 22,  "spread": 15,  "label": "Operation"},
    "battleship":    {"base": 20,  "spread": 12,  "label": "Battleship"},
    "trivial":       {"base": 18,  "spread": 10,  "label": "Trivial Pursuit"},
    "stratego":      {"base": 30,  "spread": 20,  "label": "Stratego"},
    "axis":          {"base": 45,  "spread": 30,  "label": "Axis & Allies"},
    "dungeon":       {"base": 80,  "spread": 60,  "label": "Dungeons & Dragons"},
}

_CONDITIONS = ["New", "Like New", "Very Good", "Good", "Acceptable"]
_COND_WEIGHTS = [0.05, 0.15, 0.30, 0.35, 0.15]
_COND_MULTIPLIERS = {
    "New": 1.6, "Like New": 1.3, "Very Good": 1.0,
    "Good": 0.75, "Acceptable": 0.45,
}


def _resolve_seed(query: str) -> dict:
    q = query.lower()
    seeds = _BARBIE_SEEDS if any(k in q for k in ["barbie", "ken", "skipper", "francie", "stacey", "malibu", "mod", "bubblecut", "ponytail", "superstar", "holiday"]) else {}
    seeds = {**seeds, **_GAME_SEEDS}

    for keyword, seed in {**_BARBIE_SEEDS, **_GAME_SEEDS}.items():
        if keyword in q:
            return seed

    # Generic fallback based on whether query looks like barbie or game
    if any(w in q for w in ["barbie", "doll", "mattel", "ken", "skipper"]):
        return {"base": 28, "spread": 20, "label": query.title()}
    return {"base": 20, "spread": 15, "label": query.title()}


def _mock_sold_listings(query: str, days_back: int) -> list[dict]:
    seed = _resolve_seed(query)
    rng = random.Random(hash(query.lower()) % (2**32))  # deterministic per query
    count = rng.randint(12, 45)
    now = datetime.utcnow()
    results = []

    for i in range(count):
        cond = rng.choices(_CONDITIONS, weights=_COND_WEIGHTS, k=1)[0]
        multiplier = _COND_MULTIPLIERS[cond]
        base_price = seed["base"] * multiplier
        noise = rng.uniform(-seed["spread"] * 0.4, seed["spread"] * 0.6) * multiplier
        price = max(1.99, round(base_price + noise, 2))
        days_ago = rng.randint(1, days_back)
        end_time = now - timedelta(days=days_ago, hours=rng.randint(0, 23))

        results.append({
            "title": f"{seed['label']} — {cond} — vintage collectible",
            "price": price,
            "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "condition": cond,
            "url": f"https://www.ebay.com/itm/mock-{abs(hash(query+str(i))) % 9999999:07d}",
            "image_url": None,
        })

    results.sort(key=lambda x: x["end_time"], reverse=True)
    return results


def _mock_active_listings(query: str) -> list[dict]:
    seed = _resolve_seed(query)
    rng = random.Random((hash(query.lower()) + 1) % (2**32))
    count = rng.randint(5, 25)
    results = []

    for i in range(count):
        cond = rng.choices(_CONDITIONS, weights=_COND_WEIGHTS, k=1)[0]
        multiplier = _COND_MULTIPLIERS[cond]
        price = max(1.99, round(seed["base"] * multiplier * rng.uniform(0.8, 1.4), 2))

        results.append({
            "title": f"{seed['label']} — {cond}",
            "price": price,
            "condition": cond,
            "url": f"https://www.ebay.com/itm/active-mock-{abs(hash(query+str(i))) % 9999999:07d}",
            "image_url": None,
            "watch_count": rng.randint(0, 54),
        })

    return results


def _mock_unsold_listings(query: str, days_back: int) -> list[dict]:
    """Listings priced above market that ended without a sale."""
    seed = _resolve_seed(query)
    rng = random.Random((hash(query.lower()) + 777) % (2**32))
    count = rng.randint(3, 14)
    now = datetime.utcnow()
    results = []

    for i in range(count):
        cond = rng.choices(_CONDITIONS, weights=_COND_WEIGHTS, k=1)[0]
        multiplier = _COND_MULTIPLIERS[cond]
        # Unsold items were overpriced — 20–80% above market
        price = max(5.99, round(seed["base"] * multiplier * rng.uniform(1.20, 1.80), 2))
        days_ago = rng.randint(1, days_back)
        end_time = now - timedelta(days=days_ago, hours=rng.randint(0, 23))

        results.append({
            "title": f"{seed['label']} — {cond}",
            "price": price,
            "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "condition": cond,
            "url": f"https://www.ebay.com/itm/unsold-mock-{abs(hash(query+str(i))) % 9999999:07d}",
            "image_url": None,
        })

    return sorted(results, key=lambda x: x["price"])


# ---------------------------------------------------------------------------
# Scraper implementation (default when no API key is configured)
# ---------------------------------------------------------------------------

_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def _parse_price(text: str) -> float | None:
    m = re.search(r'\$([0-9,]+\.?\d*)', text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _parse_ebay_date(text: str) -> str | None:
    text = re.sub(r'^(Sold|Ended?)\s*', '', text.strip(), flags=re.IGNORECASE).strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return None


_PLAYWRIGHT_BROWSER = None  # module-level reuse across searches in one process

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
        const priceText = priceEl.textContent.trim();
        const priceMatch = priceText.match(/\\$([0-9,]+\\.?\\d*)/);
        if (!priceMatch) continue;
        const price = parseFloat(priceMatch[1].replace(/,/g, ""));
        if (!price) continue;

        const linkEl = card.querySelector("a[href*='ebay.com/itm']");
        const url = linkEl ? linkEl.href : "";

        const fullText = card.innerText || "";
        // Sold/ended date is typically the first line
        const soldMatch = fullText.match(/^(Sold|Ended)\\s+([A-Za-z]+ \\d+,? \\d{4})/m);
        const isSold = soldMatch && soldMatch[1].toLowerCase() === "sold";
        const dateStr = soldMatch ? soldMatch[2] : null;

        if (unsoldOnly && isSold) continue;
        if (!unsoldOnly && soldMatch && !isSold) continue;  // skip unsold from sold search

        const condMatch = fullText.match(/Pre-Owned|Brand New|Open Box|For Parts|Refurbished|Used|Not Specified/i);
        const condition = condMatch ? condMatch[0] : "Used";

        results.push({ title, price, url, condition, dateStr });
    }
    return results;
}"""


async def _ebay_page(params: dict) -> list[dict]:
    """Launch headless Chrome, load eBay search, extract listings from live DOM."""
    from playwright.async_api import async_playwright
    from urllib.parse import urlencode

    url = "https://www.ebay.com/sch/i.html?" + urlencode(params)
    unsold_only = params.get("_unsold_only", False)

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
# Real eBay API implementation (activated when EBAY_APP_ID is set in .env)
# ---------------------------------------------------------------------------

_oauth_cache: dict = {}  # {token: str, expires_at: datetime}


async def _get_oauth_token() -> str:
    """Fetch or return cached Browse API OAuth token."""
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
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
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
        "itemFilter(1).name": "ListingType",
        "itemFilter(1).value": "AuctionWithBIN",
        "itemFilter(1).value(1)": "FixedPrice",
        "itemFilter(1).value(2)": "Auction",
        "paginationInput.entriesPerPage": str(min(max_results, 100)),
        "sortOrder": "EndTimeSoonest",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.ebay_finding_base_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

    items = (
        data.get("findCompletedItemsResponse", [{}])[0]
            .get("searchResult", [{}])[0]
            .get("item", [])
    )

    results = []
    for item in items:
        try:
            selling = item.get("sellingStatus", [{}])[0]
            price = float(selling.get("currentPrice", [{}])[0].get("__value__", 0))
            end_time = item.get("listingInfo", [{}])[0].get("endTime", [""])[0]
            condition = (
                item.get("condition", [{}])[0]
                    .get("conditionDisplayName", ["Unknown"])[0]
            )
            url = item.get("viewItemURL", [""])[0]
            title = item.get("title", [""])[0]
            image_url = item.get("galleryURL", [None])[0]

            results.append({
                "title": title,
                "price": price,
                "end_time": end_time,
                "condition": condition,
                "url": url,
                "image_url": image_url,
            })
        except (IndexError, KeyError, ValueError):
            continue

    return results


async def _real_active_listings(query: str, max_results: int) -> list[dict]:
    token = await _get_oauth_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.ebay_browse_base_url}/buy/browse/v1/item_summary/search",
            params={
                "q": query,
                "filter": "buyingOptions:{FIXED_PRICE|AUCTION}",
                "limit": str(min(max_results, 200)),
                "fieldgroups": "EXTENDED",  # needed to get watchCount
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("itemSummaries", []):
        try:
            price = float(item.get("price", {}).get("value", 0))
            results.append({
                "title": item.get("title", ""),
                "price": price,
                "condition": item.get("condition", "Unknown"),
                "url": item.get("itemWebUrl", ""),
                "image_url": item.get("image", {}).get("imageUrl"),
                "watch_count": item.get("watchCount", 0),
            })
        except (KeyError, ValueError):
            continue

    return results


async def _real_unsold_listings(query: str, days_back: int, max_results: int) -> list[dict]:
    """Fetch completed listings that did NOT sell."""
    params = {
        "OPERATION-NAME": "findCompletedItems",
        "SERVICE-VERSION": "1.0.0",
        "SECURITY-APPNAME": settings.ebay_app_id,
        "RESPONSE-DATA-FORMAT": "JSON",
        "keywords": query,
        # No SoldItemsOnly filter — gets all completed listings
        "itemFilter(0).name": "ListingType",
        "itemFilter(0).value": "AuctionWithBIN",
        "itemFilter(0).value(1)": "FixedPrice",
        "itemFilter(0).value(2)": "Auction",
        "paginationInput.entriesPerPage": str(min(max_results, 100)),
        "sortOrder": "EndTimeSoonest",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.ebay_finding_base_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

    items = (
        data.get("findCompletedItemsResponse", [{}])[0]
            .get("searchResult", [{}])[0]
            .get("item", [])
    )

    results = []
    for item in items:
        try:
            selling = item.get("sellingStatus", [{}])[0]
            state = selling.get("sellingState", [""])[0]
            # Only keep items that ended WITHOUT a sale
            if state in ("EndedWithSales",):
                continue
            price = float(selling.get("currentPrice", [{}])[0].get("__value__", 0))
            end_time = item.get("listingInfo", [{}])[0].get("endTime", [""])[0]
            condition = (
                item.get("condition", [{}])[0]
                    .get("conditionDisplayName", ["Unknown"])[0]
            )
            results.append({
                "title": item.get("title", [""])[0],
                "price": price,
                "end_time": end_time,
                "condition": condition,
                "url": item.get("viewItemURL", [""])[0],
                "image_url": item.get("galleryURL", [None])[0],
            })
        except (IndexError, KeyError, ValueError):
            continue

    return results
