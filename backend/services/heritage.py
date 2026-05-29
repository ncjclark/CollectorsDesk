"""
Heritage Auctions — realized (sold) auction prices.

No API key needed — scrapes their public realized-price search.
Returns empty list if the scrape fails (Heritage sometimes blocks bots).
"""

import re
import httpx
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


async def search_heritage(query: str, max_results: int = 30) -> list[dict]:
    try:
        return await _scrape_heritage(query, max_results)
    except Exception:
        return []


async def _scrape_heritage(query: str, max_results: int) -> list[dict]:
    # Heritage realized prices search
    url = "https://www.ha.com/c/search-results.zx"
    params = {
        "Ntt": query,
        "N": "790+4294967021",   # all categories, realized prices
        "type": "1",
        "ic": "HC-SL-MainSearch",
    }

    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        headers=HEADERS,
    ) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return []
        html = resp.text

    soup = BeautifulSoup(html, "lxml")
    results = []

    # Heritage lot cards have various selectors depending on page version
    # Try multiple selector patterns
    lot_cards = (
        soup.select("div.lot-search-result") or
        soup.select("li.search-result-item") or
        soup.select("div[class*='lot-card']") or
        soup.select("div.item-result")
    )

    for card in lot_cards[:max_results]:
        try:
            title_el = (
                card.select_one("h3.item-title") or
                card.select_one("a.lot-title") or
                card.select_one("[class*='title'] a") or
                card.select_one("h3 a") or
                card.select_one("a[href*='/itm/']")
            )
            title = title_el.get_text(strip=True) if title_el else None
            if not title:
                continue

            link = title_el.get("href", "") if title_el else ""
            if link and not link.startswith("http"):
                link = "https://www.ha.com" + link

            # Price — look for realized/hammer price
            price_el = (
                card.select_one(".realized-price") or
                card.select_one("[class*='realized']") or
                card.select_one("[class*='price']") or
                card.select_one("span.price")
            )
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = _parse_price(price_text)
            if not price:
                continue

            # Date
            date_el = card.select_one("[class*='date']") or card.select_one("time")
            date_text = date_el.get_text(strip=True) if date_el else ""

            results.append({
                "title": title,
                "price": price,
                "sale_date": date_text,
                "url": link,
                "image_url": None,
                "auction_house": "Heritage Auctions",
                "listing_type": "auction_realized",
            })
        except Exception:
            continue

    return results


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    # Remove currency symbols, commas, spaces; handle ranges like "$1,200 - $1,500"
    text = text.split("-")[0].split("–")[0]
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def compute_heritage_stats(listings: list[dict]) -> dict:
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
        "note": "Auction realized prices — typically premium/collector market",
    }
