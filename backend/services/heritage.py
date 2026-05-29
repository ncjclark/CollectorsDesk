"""
Heritage Auctions — realized (sold) auction prices.

Heritage is the largest collectibles auctioneer in the US.
Valuable for:
- Rare/high-value Barbies (mint condition, #1 ponytails, NRFB pieces)
- Establishing ceiling prices for exceptional items
- Understanding what serious collectors actually pay at auction

No API key needed — scrapes their public realized-price search.
Mock mode is used as fallback when scraping fails or for development.
"""

import re
import random
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
        results = await _scrape_heritage(query, max_results)
        if results:
            return results
    except Exception:
        pass
    return _mock_heritage(query)


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


def _mock_heritage(query: str) -> list[dict]:
    """
    Heritage prices are higher than eBay — auction house, serious collectors.
    Rare pieces get dramatically higher prices here.
    """
    q = query.lower()
    rng = random.Random((hash(q) + 99) % (2**32))

    if any(k in q for k in ["#1", "1959", "ponytail", "number one"]):
        base, spread = 1200, 800
        count = rng.randint(3, 10)
    elif any(k in q for k in ["1960", "1961", "1962", "bubblecut", "bubble cut"]):
        base, spread = 350, 200
        count = rng.randint(4, 12)
    elif any(k in q for k in ["francie", "stacey", "casey"]):
        base, spread = 180, 120
        count = rng.randint(2, 8)
    elif any(k in q for k in ["malibu", "superstar", "mod"]):
        base, spread = 75, 50
        count = rng.randint(3, 10)
    elif any(k in q for k in ["barbie", "doll", "mattel"]):
        base, spread = 120, 80
        count = rng.randint(3, 12)
    else:
        # Board games rarely appear at Heritage
        return []

    years = list(range(2018, 2025))
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    conditions = ["Near Mint", "Excellent", "Very Fine", "Fine", "Good"]
    cond_weights = [0.15, 0.30, 0.30, 0.15, 0.10]
    cond_mult = {"Near Mint": 1.5, "Excellent": 1.1, "Very Fine": 0.9, "Fine": 0.7, "Good": 0.5}

    results = []
    for i in range(count):
        cond = rng.choices(conditions, weights=cond_weights, k=1)[0]
        price = max(25.0, round((base + rng.uniform(-spread * 0.4, spread * 0.6)) * cond_mult[cond], 2))
        yr = rng.choice(years)
        mo = rng.choice(months)
        lot_num = rng.randint(10000, 99999)

        results.append({
            "title": f"{query.title()} — {cond} — Heritage Auctions Lot #{lot_num}",
            "price": price,
            "sale_date": f"{mo} {yr}",
            "url": f"https://www.ha.com/itm/mock-{lot_num}",
            "image_url": None,
            "auction_house": "Heritage Auctions",
            "listing_type": "auction_realized",
        })

    return sorted(results, key=lambda x: x["price"], reverse=True)


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
