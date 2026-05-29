# ResellResearch Tool — Master Planning Document

> **This document is the single source of truth for all development.**
> Every Claude session — whether fresh, compacted, or restarted — should read this file first before writing a single line of code. All architectural decisions, API setup steps, database schemas, phase definitions, and constraints live here. Update this file as decisions change.

---

## Project Overview

A **localhost-only** web application for researching resell values of a personal collection of **300–1,000 Barbie dolls and board games**, primarily targeting eBay as the sales platform.

The tool helps price items accurately by surfacing real sold-listing data, price ranges by condition, supply/demand ratios, and handles obscure/niche items (small-batch, decades-old, collector-only) through a multi-step fallback chain.

**Owner:** Personal use only. No authentication, no deployment, no public access. Single user.

---

## Core Requirements

### Input Methods (all must be supported)
1. **Manual text search** — type the item name or description
2. **Barcode scan / UPC entry** — paste or type a barcode, auto-lookup product name
3. **Photo upload** — upload an image, AI identifies the item
4. **Bulk CSV import** — import a spreadsheet of items already catalogued
5. **Fallback chain for obscure items** — exact search → broadened search → AI photo ID → manual entry

### Key Data Points Per Item
- Last sold price + date on eBay
- Price range: min / avg / median / max from recent sales (30/60/90 day windows)
- How many are currently listed vs. how many sold (supply/demand ratio)
- Condition breakdown (how price varies: sealed, complete, incomplete, loose, damaged)
- Individual sold listing details (title, price, date, condition, eBay URL)

### Inventory Tracking
Full persistent inventory database. Track every item from "on shelf" → "listed" → "sold", including:
- Condition, quantity, asking price, notes, photos
- Research history (price snapshots over time to see trends)
- eBay listing URL, sold price, sold date

### Collection Size
300–1,000 items across Barbie dolls and board games.

---

## Tech Stack

| Layer | Technology | Reasoning |
|-------|-----------|-----------|
| Backend | Python 3.11+ / FastAPI | Fast async API, great ecosystem, easy localhost |
| Database | SQLite + SQLAlchemy ORM | Zero-config, single file, no server needed |
| Frontend | React 18 + Vite | Component model handles complex tables/filters well |
| HTTP client | httpx (async) | Async-native, works inside FastAPI |
| eBay sold data | eBay Finding API (`findCompletedItems`) | Official, free, returns real sold listing data |
| eBay active data | eBay Browse API | Official, free, returns current listings |
| AI identification | Claude API — `claude-sonnet-4-6` (vision) | Handles obscure items no barcode DB knows |
| Barcode lookup | UPCItemDB API (free tier) | 100 lookups/day free, no key required |
| Charts | Recharts (React library) | Simple, well-documented charting for React |

**No Docker.** Plain `venv` + `npm`. Keep it simple for a localhost tool.

---

## Directory Structure

```
ReasearchTool/
├── PLANNING.md                    ← THIS FILE — read before every session
├── .env                           ← API keys (never commit)
├── .env.example                   ← Template showing all required keys
├── start.sh                       ← Single script to launch both servers
├── backend/
│   ├── main.py                    ← FastAPI app entry point + CORS config
│   ├── database.py                ← SQLAlchemy engine, session, Base, models
│   ├── config.py                  ← Load .env vars, expose as Settings object
│   ├── requirements.txt
│   ├── routers/
│   │   ├── search.py              ← POST /api/search
│   │   ├── inventory.py           ← CRUD for inventory items
│   │   ├── identify.py            ← POST /api/identify/barcode and /photo
│   │   └── import_export.py       ← CSV import + export
│   ├── services/
│   │   ├── ebay.py                ← eBay API client (Finding + Browse APIs)
│   │   ├── barcode.py             ← UPCItemDB barcode lookup
│   │   └── ai_identify.py         ← Claude vision photo identification
│   └── models/
│       └── schemas.py             ← Pydantic request/response schemas
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js             ← Proxy /api/* → localhost:8000
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                ← Router setup (React Router)
│       ├── components/
│       │   ├── SearchBar.jsx      ← Text + barcode input, category selector
│       │   ├── ResultsPanel.jsx   ← Price summary cards + sold listing table
│       │   ├── InventoryTable.jsx ← Sortable/filterable inventory grid
│       │   ├── ItemDetail.jsx     ← Slide-out panel for single item
│       │   ├── PriceChart.jsx     ← Recharts line chart for price history
│       │   ├── PhotoUpload.jsx    ← Drag-drop upload + AI ID result
│       │   └── ImportModal.jsx    ← CSV drag-drop + preview before import
│       └── pages/
│           ├── Research.jsx       ← Main search/lookup page
│           ├── Inventory.jsx      ← Full inventory management
│           └── Dashboard.jsx      ← Stats overview + value summary
├── data/
│   └── inventory.db               ← SQLite file (auto-created on first run)
└── uploads/                       ← Local photo storage, organized by item ID
    └── {item_id}/
        └── photo_1.jpg
```

---

## Database Schema

### Table: `inventory_items`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| name | TEXT NOT NULL | Item name (user-entered or AI-identified) |
| category | TEXT | `barbie` or `board_game` |
| year | INTEGER | Manufacture/release year |
| model_number | TEXT | Barbie stock # or game edition identifier |
| barcode | TEXT | UPC if available |
| condition | TEXT | `sealed` / `complete` / `incomplete` / `loose` / `damaged` |
| quantity | INTEGER DEFAULT 1 | How many you have |
| my_asking_price | REAL | Price you've decided to list at |
| last_research_date | DATETIME | When you last ran a price lookup for this item |
| status | TEXT DEFAULT 'not_listed' | `not_listed` / `listed` / `sold` / `hold` |
| ebay_listing_url | TEXT | Link to your active eBay listing |
| sold_price | REAL | Actual price it sold for |
| sold_date | DATETIME | When it sold |
| notes | TEXT | Free-text notes (condition details, provenance, etc.) |
| photo_path | TEXT | Path to primary local photo (relative to uploads/) |
| created_at | DATETIME | Auto-set on insert |
| updated_at | DATETIME | Auto-set on update |

### Table: `price_research_cache`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| search_query | TEXT NOT NULL | The normalized search term |
| category | TEXT | `barbie` / `board_game` |
| fetched_at | DATETIME | When this data was fetched |
| cache_ttl_hours | INTEGER DEFAULT 24 | How long to consider this fresh |
| avg_sold_price | REAL | |
| min_sold_price | REAL | |
| max_sold_price | REAL | |
| median_sold_price | REAL | |
| sold_count_30d | INTEGER | # of sales in last 30 days |
| sold_count_60d | INTEGER | # of sales in last 60 days |
| sold_count_90d | INTEGER | # of sales in last 90 days |
| active_listing_count | INTEGER | Current listings on eBay right now |
| condition_breakdown | JSON | `{"sealed": 95.00, "complete": 45.00, "loose": 12.00}` |
| last_sold_date | DATETIME | Date of most recent completed sale |
| raw_sold_listings | JSON | Array of `{title, price, date, condition, url, image_url}` |
| source | TEXT | `ebay` / `pricecharting` / `manual` |
| linked_item_id | INTEGER | FK → inventory_items (nullable) |

### Table: `search_history`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| query | TEXT | Raw search string |
| category | TEXT | |
| searched_at | DATETIME | |
| result_count | INTEGER | # of sold listings found |
| avg_price | REAL | Avg price from this search |
| linked_item_id | INTEGER | FK → inventory_items (if user saved it) |

---

## API Keys Required

### 1. eBay Developer Account — FREE

**Setup steps:**
1. Go to https://developer.ebay.com/
2. Sign in with your regular eBay account (same login)
3. In the top nav, go to **My Account → Application Access Keys**
4. Click **Create a keyset** — environment: **Production**
5. Name it anything (e.g. "ResellResearch")
6. You'll receive three values — copy all three into `.env`:
   - `EBAY_APP_ID` (also called **Client ID**)
   - `EBAY_CERT_ID` (also called **Client Secret**)
   - `EBAY_DEV_ID`
7. You do NOT need to register a RuName or OAuth redirect URI for this tool (we use client credentials only)
8. Optionally also create a **Sandbox** keyset for testing — set `EBAY_ENVIRONMENT=sandbox` in `.env`

**Which eBay APIs are used:**
- **Finding API** (`findCompletedItems` with `soldItemsOnly=true`) → sold listing history — uses `EBAY_APP_ID` only
- **Browse API** (`/buy/browse/v1/item_summary/search`) → active listings — requires OAuth client credentials token, uses `EBAY_APP_ID` + `EBAY_CERT_ID`

### 2. Anthropic API (Claude) — for photo identification

**Setup steps:**
1. Go to https://console.anthropic.com/
2. Create or log into your account
3. Navigate to **API Keys** → **Create Key**
4. Copy the key into `.env` as `ANTHROPIC_API_KEY`
5. Usage: send photo + prompt to `claude-sonnet-4-6` (vision model) to identify obscure items
6. Cost: fractions of a cent per image lookup — negligible for personal use

### 3. Barcode Lookup — FREE, no key needed

- Primary: `https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}`
  - Free tier: 100 lookups/day, no registration
- Fallback: Open Food Facts (mostly food, sometimes toys)
- Final fallback: if no match, show "not found" and let user enter manually

---

## Environment Variables Template

Create a file called `.env` in the project root (copy from `.env.example`):

```env
# eBay API (from developer.ebay.com → My Account → Application Access Keys)
EBAY_APP_ID=
EBAY_CERT_ID=
EBAY_DEV_ID=
EBAY_ENVIRONMENT=production

# Anthropic API (from console.anthropic.com → API Keys)
ANTHROPIC_API_KEY=

# App config (safe to leave as defaults)
DATABASE_URL=sqlite:///./data/inventory.db
UPLOAD_DIR=./uploads
RESEARCH_CACHE_TTL_HOURS=24
MAX_EBAY_RESULTS=100
```

---

## eBay API Reference

### Finding API — Sold Listings (most important endpoint)

```
GET https://svcs.ebay.com/services/search/FindingService/v1
  ?OPERATION-NAME=findCompletedItems
  &SERVICE-VERSION=1.0.0
  &SECURITY-APPNAME={EBAY_APP_ID}
  &RESPONSE-DATA-FORMAT=JSON
  &keywords={url_encoded_query}
  &itemFilter(0).name=SoldItemsOnly
  &itemFilter(0).value=true
  &itemFilter(1).name=ListingType
  &itemFilter(1).value=AuctionWithBIN
  &itemFilter(1).value(1)=FixedPrice
  &itemFilter(1).value(2)=Auction
  &paginationInput.entriesPerPage=100
  &sortOrder=EndTimeSoonest
```

Sandbox base URL: `https://svcs.sandbox.ebay.com/services/search/FindingService/v1`

### Browse API — Active Listings (OAuth required)

**Step 1: Get OAuth token**
```
POST https://api.ebay.com/identity/v1/oauth2/token
Authorization: Basic base64({EBAY_APP_ID}:{EBAY_CERT_ID})
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope
```

**Step 2: Search**
```
GET https://api.ebay.com/buy/browse/v1/item_summary/search
  ?q={encoded_query}
  &filter=buyingOptions:{FIXED_PRICE|AUCTION}
  &limit=50
Authorization: Bearer {access_token}
```

Token expires in 2 hours — cache it and refresh when expired.

---

## How to Start Development (Every Session)

### First-time setup
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env
# Open .env and fill in your API keys

# Frontend
cd ../frontend
npm install
```

### Starting the app every day
```bash
# Terminal 1 — Backend (from /backend directory)
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend (from /frontend directory)
npm run dev
```

Open browser to: **http://localhost:5173**

### Single-script start (Phase 7)
Once `start.sh` is created in Phase 7, just run: `./start.sh`

---

## Phase-by-Phase Implementation Plan

---

### PHASE 1 — Project Setup & Infrastructure
**Goal:** Running skeleton. Backend starts, frontend loads, database initializes, both talk to each other.

**Status:** Not started

**Tasks:**
- [ ] Create full directory structure (backend/, frontend/, data/, uploads/)
- [ ] Create `backend/requirements.txt`:
  ```
  fastapi>=0.110.0
  uvicorn[standard]>=0.29.0
  sqlalchemy>=2.0.0
  httpx>=0.27.0
  python-dotenv>=1.0.0
  python-multipart>=0.0.9
  anthropic>=0.26.0
  pydantic>=2.0.0
  ```
- [ ] Create `backend/config.py` — loads `.env` via pydantic-settings or python-dotenv
- [ ] Create `backend/database.py` — SQLAlchemy engine, Base, SessionLocal, all three table models
- [ ] Create `backend/main.py` — FastAPI app, CORS (`allow_origins=["http://localhost:5173"]`), include routers, create DB tables on startup
- [ ] Create `GET /api/health` endpoint returning `{"status": "ok", "db": "connected"}`
- [ ] Create `.env.example` with all keys and descriptions
- [ ] Scaffold React + Vite: `npm create vite@latest frontend -- --template react`
- [ ] Configure `vite.config.js` proxy: `/api` → `http://localhost:8000`
- [ ] Create basic `App.jsx` with navigation tabs (Research / Inventory / Dashboard)
- [ ] Verify health check: React page fetches `/api/health` and displays "Connected"

**Completion test:** `uvicorn main:app --reload` starts with no errors. `npm run dev` loads a page that shows "Connected to backend."

---

### PHASE 2 — eBay Integration & Core Search
**Goal:** Type a name, get real eBay sold data back.

**Status:** Not started

**Tasks:**
- [ ] Implement `backend/services/ebay.py`:
  - `get_oauth_token()` — fetches Browse API token, caches it in memory with expiry
  - `search_sold_listings(query, days_back=90, max_results=100)` → calls Finding API, returns list of `{title, price, end_time, condition, url, image_url}`
  - `search_active_listings(query, max_results=50)` → calls Browse API, returns list of current listings
  - `compute_price_stats(sold_listings)` → returns `{avg, min, max, median, count_30d, count_60d, count_90d, condition_breakdown, last_sold_date}`
- [ ] Implement `backend/routers/search.py`:
  - `POST /api/search` — body: `{query: str, category: str, days_back: int}`
  - Check cache first: if `price_research_cache` has a fresh record for this query (within TTL), return it with `from_cache: true`
  - Otherwise: fetch from eBay, compute stats, store in cache, return fresh data
  - Response shape:
    ```json
    {
      "query": "...",
      "from_cache": false,
      "fetched_at": "...",
      "stats": { "avg": 0, "min": 0, "max": 0, "median": 0, "count_30d": 0 },
      "active_listing_count": 0,
      "condition_breakdown": {},
      "last_sold_date": "...",
      "sold_listings": [{ "title": "", "price": 0, "end_time": "", "condition": "", "url": "", "image_url": "" }]
    }
    ```
- [ ] Implement `frontend/src/components/SearchBar.jsx`:
  - Text input for item name
  - Category dropdown: All / Barbie / Board Game
  - Days back selector: 30 / 60 / 90 days
  - Search button + Enter key support
  - Shows recent searches below (from localStorage)
- [ ] Implement `frontend/src/components/ResultsPanel.jsx`:
  - Price summary cards: Avg Sold / Min / Max / Median
  - Sales velocity: "X sold in last 30 days, Y currently listed"
  - Demand indicator: ratio of sold:listed (High / Medium / Low demand)
  - Condition breakdown table
  - Scrollable table of individual sold listings with clickable eBay links
  - "Save to Inventory" button
  - Cache indicator: shows "Cached X hours ago" or "Live data"
- [ ] Add loading spinner, empty state ("No sales found — try a broader search"), and error state
- [ ] Test with: "Malibu Barbie 1971", "1959 Barbie ponytail", "Clue board game 1972", "Monopoly 1935"

**Completion test:** Search returns real eBay data, price cards populate, sold listings table shows real titles and prices with working links.

---

### PHASE 3 — Inventory Database
**Goal:** Save researched items to a persistent inventory; track full lifecycle from shelf to sold.

**Status:** Not started

**Tasks:**
- [ ] Implement `backend/routers/inventory.py`:
  - `GET /api/inventory` — returns all items; query params: `category`, `status`, `condition`, `search` (name filter)
  - `POST /api/inventory` — create new item
  - `GET /api/inventory/{id}` — single item + its research cache records
  - `PUT /api/inventory/{id}` — update any fields
  - `DELETE /api/inventory/{id}` — delete item (and its uploads)
  - `POST /api/inventory/{id}/research` — fresh eBay search for this item, save to cache, update `last_research_date`
- [ ] Implement `backend/models/schemas.py` — Pydantic models for all request/response shapes
- [ ] Add "Save to Inventory" flow in frontend:
  - Clicking the button on Results panel opens a small form
  - Pre-fills name from search query
  - User sets: condition, quantity, notes
  - On save: POST to `/api/inventory`, show success toast
- [ ] Implement `frontend/src/pages/Inventory.jsx`:
  - Full-width sortable table: Name | Category | Condition | Asking Price | Avg eBay Price | Last Researched | Status
  - Click column header to sort
  - Filter bar: Category / Status / Condition dropdowns
  - Search box to filter by name
  - Click any row to open `ItemDetail` panel
  - "Add Item" button for manual entry without searching first
- [ ] Implement `frontend/src/components/ItemDetail.jsx` (slide-out right panel):
  - All fields editable inline (click to edit)
  - Price research summary block: avg/min/max, last sold date, last researched date
  - "Re-research" button → triggers fresh eBay lookup, updates display
  - Status dropdown with clear lifecycle labels
  - When setting status to "sold": prompts for sold price and date
  - Link to eBay listing URL (if set)
  - Research history accordion: past price snapshots with dates
  - Photo display area (placeholder for Phase 4)
  - Delete button (with confirmation)
- [ ] Research history: every call to `/api/inventory/{id}/research` appends a record to `price_research_cache` with `linked_item_id` set — this builds price history over time

**Completion test:** Add an item from search results, find it in the Inventory tab, edit its condition, mark it sold with a price. Verify data persists after restarting the backend.

---

### PHASE 4 — Advanced Input: Barcode & Photo Identification
**Goal:** Multiple entry paths, especially for obscure items with no obvious search term.

**Status:** Not started

**Tasks:**
- [ ] Implement `backend/services/barcode.py`:
  - `lookup_barcode(upc: str)` → calls `https://api.upcitemdb.com/prod/trial/lookup?upc={upc}`
  - Returns `{found: bool, name: str, brand: str, description: str}` or `{found: false}`
  - If UPCItemDB fails or returns nothing: try Open Food Facts as secondary
- [ ] Implement `backend/services/ai_identify.py`:
  - `identify_item(image_bytes: bytes, category_hint: str)` → sends to Claude claude-sonnet-4-6 vision
  - System prompt: "You are an expert authenticator and appraiser specializing in vintage Mattel Barbie dolls and classic board games. Identify the item in this image as precisely as possible."
  - User prompt: "Identify this {category_hint}. Provide: (1) full official product name, (2) approximate year or year range, (3) manufacturer, (4) model or stock number if visible, (5) edition or variant details (e.g. hair color, outfit, special edition name), (6) your confidence level (high/medium/low), (7) suggested eBay search query to find comparable sold listings. Reply in JSON only."
  - Parse JSON response, return structured result
- [ ] Implement `backend/routers/identify.py`:
  - `POST /api/identify/barcode` — body: `{upc: str}` → returns product name or not-found
  - `POST /api/identify/photo` — multipart upload, saves to `uploads/temp/`, calls `ai_identify`, returns result
- [ ] Update `frontend/src/components/SearchBar.jsx`:
  - Add barcode input toggle: click icon to switch to barcode mode
  - In barcode mode: numeric input with scan icon; on submit, calls `/api/identify/barcode`, auto-populates name field
- [ ] Create `frontend/src/components/PhotoUpload.jsx`:
  - Drag-and-drop zone or click to browse
  - Shows image preview after selection
  - On upload: shows loading spinner "Identifying item with AI..."
  - Shows AI result: name, year, confidence level
  - Fields are editable before confirming
  - "Search with this name" button triggers normal search flow
  - "This is wrong — let me edit" button makes all fields editable
- [ ] Implement **fallback chain logic** in `Research.jsx`:
  1. Search exact query → if 0 sold results:
  2. Auto-broaden: try dropping the last word, or searching just year + "barbie" → if still 0:
  3. Show "No results — try identifying with a photo" prompt with upload button → if AI identifies:
  4. Auto-search with AI-suggested query → if still 0:
  5. Show "No market data found" card with "Log manually" option that opens a form to set a manual price estimate + notes
- [ ] Save AI identification results: when user confirms, the AI-suggested name and model number are pre-filled in the "Save to Inventory" form

**Completion test:** Upload a Barbie doll photo of a known model; verify AI returns the correct name and year. Enter a barcode; verify it returns a product name or graceful "not found."

---

### PHASE 5 — Bulk CSV Import & Export
**Goal:** Import a large pre-catalogued list in one go; export inventory for backup or external use.

**Status:** Not started

**Tasks:**
- [ ] Define CSV column format:
  ```
  name,category,year,model_number,barcode,condition,quantity,notes
  ```
  - `category`: barbie or board_game
  - `condition`: sealed / complete / incomplete / loose / damaged
- [ ] Create downloadable CSV template file at `GET /api/import/template`
- [ ] Implement `backend/routers/import_export.py`:
  - `POST /api/import/csv` — multipart CSV upload; validate each row; bulk insert valid rows; return `{imported: N, skipped: [{row, reason}]}`
  - `GET /api/export/csv` — export full inventory as CSV download
  - `GET /api/export/csv?status=not_listed` — filtered export
- [ ] Implement `frontend/src/components/ImportModal.jsx`:
  - Drag-and-drop CSV upload zone
  - "Download Template" button
  - After upload: shows preview table of first 10 rows
  - Shows validation errors inline (red rows with reason)
  - "Import X items" confirm button
  - After import: shows results summary "Imported 347 items, 3 rows skipped"
- [ ] Add Import / Export buttons to the Inventory page header

**Completion test:** Create a CSV with 10+ test items including one invalid row. Import it, verify items appear in inventory, verify invalid row is reported. Export, verify CSV downloads with all columns.

---

### PHASE 6 — Dashboard & Analytics
**Goal:** Immediate high-level understanding of collection value, progress, and what needs attention.

**Status:** Not started

**Tasks:**
- [ ] Implement `GET /api/dashboard/stats` returning:
  ```json
  {
    "totals": { "items": 0, "barbie": 0, "board_games": 0, "estimated_value": 0 },
    "by_status": { "not_listed": 0, "listed": 0, "sold": 0, "hold": 0 },
    "revenue": { "total_sold_price": 0, "count_sold": 0 },
    "needs_research": [ list of items never researched or researched >30 days ago ],
    "top_value_items": [ top 10 by avg_sold_price ],
    "condition_breakdown": { "sealed": 0, "complete": 0, ... }
  }
  ```
- [ ] Implement `frontend/src/pages/Dashboard.jsx`:
  - Row of stat cards: Total Items | Est. Total Value | Items Sold | Revenue Earned
  - Bar chart (Recharts): Items by Status
  - Bar chart: Items by Condition
  - Table: Top 10 Most Valuable Items (name, avg eBay price, your asking price, status)
  - Table: Needs Attention — items never researched or stale >30 days (with "Research Now" link)
- [ ] Add price trend mini-chart to `ItemDetail`: if item has 3+ research snapshots, show a small line chart of avg price over time

**Completion test:** Dashboard loads with correct counts. After marking an item sold, revenue updates. Needs Attention list shows items with no research.

---

### PHASE 7 — Polish & Quality of Life
**Goal:** Fast, pleasant to use for daily repetitive work.

**Status:** Not started

**Tasks:**
- [ ] Keyboard shortcuts: Enter to search, Escape to close panel/modal, `i` to jump to Inventory, `r` to jump to Research
- [ ] Recent searches: last 10 searches shown as clickable chips below the search bar (persisted in localStorage)
- [ ] Batch re-research: checkbox multi-select in Inventory table, "Re-research selected" button — runs sequentially with 1s delay between calls to avoid rate limiting
- [ ] eBay listing helper: button in ItemDetail that generates a suggested eBay listing:
  - Title (60-char optimized for eBay SEO)
  - Condition description
  - Suggested price (based on recent sold data + your asking price)
  - Copy to clipboard
- [ ] Barbie-specific condition fields: additional structured fields on ItemDetail for dolls:
  - Hair condition (mint / good / frizzy / cut)
  - Original clothes (yes / partial / no)
  - Accessories present (list what's there)
  - Box condition (none / fair / good / mint)
- [ ] Photo management: attach multiple photos per item; stored in `uploads/{item_id}/`; displayed as thumbnail gallery in ItemDetail
- [ ] Dark mode toggle (CSS variables + localStorage preference)
- [ ] `start.sh` script: launches both backend and frontend in background, opens browser
  ```bash
  #!/bin/bash
  cd backend && source venv/bin/activate && uvicorn main:app --port 8000 &
  cd frontend && npm run dev &
  sleep 2 && open http://localhost:5173
  ```
- [ ] Graceful shutdown: `stop.sh` kills both processes

**Completion test:** Full workflow — upload CSV, search for obscure item with photo, save to inventory, mark sold, view dashboard showing updated revenue.

---

## Constraints & Decisions Log

| Decision | Reasoning |
|----------|-----------|
| No Docker | Localhost tool; plain venv + npm is simpler to run forever |
| SQLite over Postgres | Single user, no concurrent writes, zero-config. Can migrate to Postgres later if needed. |
| React over plain HTML/JS | The inventory table with sorting, filtering, inline editing, and slide-out panels is complex enough to need components |
| eBay Finding API over scraping | Scraping eBay violates ToS and breaks constantly; Finding API is free, official, reliable |
| Cache research results 24hr | eBay API has rate limits; caching avoids re-fetching the same item repeatedly in one session |
| Claude vision for photo ID | Handles long tail of obscure small-batch items that no barcode database knows |
| `claude-sonnet-4-6` for AI | Best balance of accuracy and cost for image understanding tasks |
| Fallback chain for obscure items | Many Barbies are small-batch collector items with no eBay comps; the tool must be honest about that and still let the user record manual estimates |
| Research history preserved | Price research snapshots are never overwritten — each re-research appends. This lets you see if values are trending up or down over time. |

---

## Current Phase Progress

```
Phase 1 — Setup & Infrastructure      [✓] COMPLETE
Phase 2 — eBay Search & Core Data     [✓] COMPLETE (mock mode — swap real eBay in ebay.py once API approved)
Phase 3 — Inventory Database          [✓] COMPLETE
Phase 4 — Barcode & Photo ID          [✓] COMPLETE (AI photo ID stubs gracefully until ANTHROPIC_API_KEY is set)
Phase 5 — Bulk CSV Import             [✓] COMPLETE
Phase 6 — Dashboard & Analytics       [✓] COMPLETE
Phase 7 — Polish                      [✓] COMPLETE
Phase 8 — Multi-source Research       [✓] COMPLETE (Etsy, Heritage Auctions, BoardGameGeek + consensus pricing)
```

Update this section as phases complete. Mark in-progress tasks with `[~]`.

---

## How to Use This Document in a New Claude Session

1. Start the session by saying: "Read PLANNING.md and continue development from the current phase."
2. Claude will read this file, see which phase is in progress, and pick up where you left off.
3. After completing a phase, ask Claude to update the **Current Phase Progress** section and mark tasks complete.
4. Never start a new chat without pointing to this file first.
