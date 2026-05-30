import { useState } from 'react'
import './ResultsPanel.css'

function Tip({ text, left }) {
  return (
    <span
      className={`tip-icon${left ? ' tip-left' : ''}`}
      data-tip={text}
      aria-label={text}
    >?</span>
  )
}

function fmt(val) {
  if (val == null) return '—'
  return '$' + Number(val).toFixed(2)
}

function demandLabel(sold30, active) {
  if (!sold30 && !active) return null
  if (!active) return { label: 'High Demand', cls: 'demand-high' }
  const ratio = sold30 / active
  if (ratio >= 2)   return { label: 'High Demand',   cls: 'demand-high' }
  if (ratio >= 0.5) return { label: 'Medium Demand', cls: 'demand-med' }
  return { label: 'Low Demand', cls: 'demand-low' }
}

function spreadLabel(pct) {
  if (pct > 150) return { label: 'volatile', cls: 'spread-volatile', tip: 'Condition matters a lot — price carefully' }
  if (pct > 75)  return { label: 'moderate', cls: 'spread-moderate', tip: 'Moderate variation — condition still important' }
  return { label: 'stable', cls: 'spread-stable', tip: 'Settled market — price near the average' }
}

function conditionMultiplier(breakdown) {
  const entries = Object.entries(breakdown).filter(([, v]) => v > 0)
  if (entries.length < 2) return null
  const sorted = [...entries].sort((a, b) => a[1] - b[1])
  const [lowName, lowVal] = sorted[0]
  const [highName, highVal] = sorted[sorted.length - 1]
  const mult = (highVal / lowVal).toFixed(1)
  return { mult, highName, lowName }
}

function timeAgo(isoStr) {
  if (!isoStr) return ''
  const diff = Date.now() - new Date(isoStr).getTime()
  const h = Math.floor(diff / 3600000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function fmtDate(isoStr) {
  if (!isoStr) return '—'
  return new Date(isoStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const SOURCE_NAMES = {
  ebay: 'eBay',
  etsy: 'Etsy',
  heritage: 'Heritage Auctions',
  bgg: 'BoardGameGeek',
}

const RELIABILITY_COLORS = {
  high: 'var(--green)',
  medium: 'var(--yellow)',
  low: 'var(--red)',
}

const SOURCE_ICONS = {
  'eBay Sold': '🛒',
  'Etsy': '🌿',
  'Heritage Auctions': '🏛',
  'BGG Marketplace': '🎲',
}

const TYPE_LABELS = {
  sold: 'Confirmed sold',
  asking: 'Asking prices',
  auction_realized: 'Auction realized',
}

export default function ResultsPanel({ results, onSaveToInventory }) {
  const [activeTab, setActiveTab] = useState('ebay')

  if (!results) return null

  const {
    query, from_cache, fetched_at, stats, active_listing_count,
    condition_breakdown, last_sold_date, sold_listings,
    sources = {}, combined = {}, source_errors = {},
  } = results

  const hasEbayData  = stats.count_90d > 0
  const hasEtsyData  = sources.etsy?.count > 0
  const hasHeritage  = sources.heritage?.count > 0
  const hasBgg       = sources.bgg?.found && sources.bgg?.marketplace_stats?.count > 0
  const anyData = hasEbayData || hasEtsyData || hasHeritage || hasBgg
  const demand = demandLabel(stats.count_30d, active_listing_count)

  // Derived insights
  const unsoldCount = sources.ebay_unsold?.count || 0
  const sellThrough = (stats.count_90d > 0 && unsoldCount > 0)
    ? Math.round(stats.count_90d / (stats.count_90d + unsoldCount) * 100)
    : null
  const daysToSell = stats.count_30d > 0
    ? Math.max(1, Math.round(30 / stats.count_30d))
    : null
  const priceSpreadPct = (stats.avg > 0 && stats.max != null && stats.min != null)
    ? Math.round((stats.max - stats.min) / stats.avg * 100)
    : null
  const spreadInfo = priceSpreadPct != null ? spreadLabel(priceSpreadPct) : null
  const condMult = condition_breakdown ? conditionMultiplier(condition_breakdown) : null
  const topWatched = sources.ebay_active?.top_watched?.filter(l => l.watch_count > 0) || []

  const tabs = [
    { key: 'ebay',          label: '🛒 eBay',          show: true },
    { key: 'etsy',          label: '🌿 Etsy',          show: hasEtsyData || sources.etsy },
    { key: 'heritage',      label: '🏛 Heritage',      show: hasHeritage || sources.heritage?.count >= 0 },
    { key: 'bgg', label: '🎲 BGG', show: sources.bgg },
  ].filter(t => t.show)

  return (
    <div className="results-panel">
      {/* Header */}
      <div className="results-header">
        <div className="results-title">
          <span className="results-query">"{query}"</span>
          {from_cache
            ? <span className="cache-badge">cached {timeAgo(fetched_at)}</span>
            : <span className="live-badge">live</span>}
        </div>
        {anyData && (
          <button className="btn-primary save-btn" onClick={() => onSaveToInventory(query, results)}>
            + Save to Inventory
          </button>
        )}
      </div>

      {/* Rate-limit / error banners */}
      {Object.entries(source_errors).map(([src, status]) => (
        <div key={src} className={`source-error-banner ${status}`}>
          <span className="source-error-icon">{status === 'rate_limited' ? '⏱' : '⚠'}</span>
          <span className="source-error-msg">
            {status === 'rate_limited'
              ? <><strong>{SOURCE_NAMES[src] || src}</strong> rate-limited this request — bot detection was triggered. Results may be incomplete. Wait a minute and search again to retry.</>
              : <><strong>{SOURCE_NAMES[src] || src}</strong> returned an error this search. Results may be incomplete.</>
            }
          </span>
        </div>
      ))}

      {!anyData ? (
        <div className="no-results card">
          <div className="no-results-icon">🔍</div>
          <h3>No data found across any source</h3>
          {source_errors.ebay === 'rate_limited'
            ? <p>eBay blocked this search. Wait 1–2 minutes and try again — the result won't be cached so a retry will hit live data.</p>
            : <p>Try fewer words or a broader search term.</p>
          }
        </div>
      ) : (
        <>
          {/* ── Combined consensus block ── */}
          {combined.consensus_price && (
            <div className="consensus-block">
              <div className="consensus-left">
                <div className="consensus-label">
                  Market Consensus
                  <span className="consensus-sources">{combined.source_count} source{combined.source_count !== 1 ? 's' : ''}</span>
                  <Tip text="Weighted price across all data sources. eBay sold counts most, asking prices count less. Use this as your starting point." />
                </div>
                <div className="consensus-price">{fmt(combined.consensus_price)}</div>
                {combined.price_range && (
                  <div className="consensus-range">
                    Range: {fmt(combined.price_range.low)} — {fmt(combined.price_range.high)}
                    <Tip text="Estimated realistic price range: 15% below the lowest source average to 10% above the highest." />
                  </div>
                )}
              </div>
              <div className="source-pills">
                {combined.sources?.map(s => (
                  <div key={s.source} className="source-pill">
                    <span className="pill-icon">{SOURCE_ICONS[s.source] || '📊'}</span>
                    <div className="pill-body">
                      <div className="pill-name">{s.source}</div>
                      <div className="pill-price">{fmt(s.avg)}</div>
                      <div className="pill-type">{TYPE_LABELS[s.type] || s.type}</div>
                    </div>
                    <div
                      className="pill-reliability"
                      style={{ background: RELIABILITY_COLORS[s.reliability] + '22',
                               color: RELIABILITY_COLORS[s.reliability],
                               border: `1px solid ${RELIABILITY_COLORS[s.reliability]}44` }}
                    >
                      {s.reliability}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Source tabs ── */}
          <div className="source-tabs">
            {tabs.map(t => (
              <button
                key={t.key}
                className={`source-tab ${activeTab === t.key ? 'active' : ''}`}
                onClick={() => setActiveTab(t.key)}
              >
                {t.label}
                {t.key === 'ebay' && stats.count_90d > 0 &&
                  <span className="tab-count">{stats.count_90d}</span>}
                {t.key === 'etsy' && sources.etsy?.count > 0 &&
                  <span className="tab-count">{sources.etsy.count}</span>}
                {t.key === 'heritage' && sources.heritage?.count > 0 &&
                  <span className="tab-count">{sources.heritage.count}</span>}
                {t.key === 'bgg' && sources.bgg?.marketplace_stats?.count > 0 &&
                  <span className="tab-count">{sources.bgg.marketplace_stats.count}</span>}
              </button>
            ))}
          </div>

          {/* ── eBay tab ── */}
          {activeTab === 'ebay' && (
            <div className="tab-content">
              {!hasEbayData ? (
                <EbayDebugPanel debug={sources.ebay_debug} errorStatus={source_errors.ebay} />
              ) : (
                <>
                  <div className="price-cards">
                    <div className="price-card">
                      <div className="price-card-label">Avg Sold <Tip text="Mean final sale price across all eBay sold listings in 90 days. Pulled up by high outliers." /></div>
                      <div className="price-card-value">{fmt(stats.avg)}</div>
                    </div>
                    <div className="price-card">
                      <div className="price-card-label">Median <Tip text="Middle sale price — half sold above, half below. More reliable than average when there are outliers." /></div>
                      <div className="price-card-value">{fmt(stats.median)}</div>
                    </div>
                    <div className="price-card price-card-min">
                      <div className="price-card-label">Low <Tip text="Lowest recorded sale in 90 days. Likely poor condition or a motivated seller — floor of the market." /></div>
                      <div className="price-card-value">{fmt(stats.min)}</div>
                    </div>
                    <div className="price-card price-card-max">
                      <div className="price-card-label">High <Tip text="Highest recorded sale in 90 days. Usually exceptional condition or a rare variant. Ceiling of the market." left /></div>
                      <div className="price-card-value">{fmt(stats.max)}</div>
                    </div>
                  </div>

                  <div className="market-row">
                    <div className="market-stat">
                      <span className="market-num">{stats.count_30d}</span>
                      <span className="market-lbl">sold 30d <Tip text="Listings sold in the last 30 days. Compare to sold 90d to see if demand is rising or falling." /></span>
                    </div>
                    <div className="market-stat">
                      <span className="market-num">{stats.count_60d}</span>
                      <span className="market-lbl">sold 60d <Tip text="Listings sold in the last 60 days." /></span>
                    </div>
                    <div className="market-stat">
                      <span className="market-num">{stats.count_90d}</span>
                      <span className="market-lbl">sold 90d <Tip text="Total sold in 90 days — the main sample size. Larger = more reliable pricing data." /></span>
                    </div>
                    <div className="market-stat">
                      <span className="market-num">{active_listing_count}</span>
                      <span className="market-lbl">active <Tip text="Current listings on eBay right now. High active + low sold = oversupplied market." /></span>
                    </div>
                    {sources.ebay_active?.total_watches > 0 && (
                      <div className="market-stat">
                        <span className="market-num watch-num">👁 {sources.ebay_active.total_watches}</span>
                        <span className="market-lbl">watchers <Tip text={`Total watchers across all active listings. Avg ${sources.ebay_active.avg_watches} per listing. High watcher counts signal real buyer interest.`} /></span>
                      </div>
                    )}
                    {demand && (
                      <div className={`demand-badge ${demand.cls}`}>
                        {demand.label}
                        <Tip text="Ratio of 30-day sales to active listings. High Demand = selling faster than supply. Low Demand = supply outpaces buyers." />
                      </div>
                    )}
                    <div className="market-stat" style={{ marginLeft: 'auto' }}>
                      <span className="market-lbl">last sold <Tip text="Date of the most recent confirmed eBay sale. If this is old, the market may be slow or seasonal." left /></span>
                      <span className="market-num" style={{ fontSize: 12 }}>{fmtDate(last_sold_date)}</span>
                    </div>
                  </div>

                  {/* Insights strip */}
                  {(sellThrough != null || daysToSell != null || spreadInfo != null) && (
                    <div className="insights-strip">
                      {sellThrough != null && (
                        <div className={`insight-chip ${sellThrough >= 70 ? 'insight-good' : sellThrough >= 40 ? 'insight-mid' : 'insight-bad'}`}>
                          <span className="insight-val">{sellThrough}%</span>
                          <span className="insight-lbl">
                            sell-through rate
                            <Tip text={`${sellThrough}% of all listings (sold + unsold) actually sold. ≥70% = strong market, 40–70% = normal, <40% = slow — lower your price or wait for a better season.`} />
                          </span>
                        </div>
                      )}
                      {daysToSell != null && (
                        <div className="insight-chip insight-neutral">
                          <span className="insight-val">~{daysToSell}d</span>
                          <span className="insight-lbl">
                            est. days to sell
                            <Tip text={`Based on ${stats.count_30d} sales in 30 days. At this rate, a new listing would sell in roughly ${daysToSell} day${daysToSell !== 1 ? 's' : ''}. Use for cash flow planning.`} />
                          </span>
                        </div>
                      )}
                      {spreadInfo != null && (
                        <div className={`insight-chip ${spreadInfo.cls}`}>
                          <span className="insight-val">{priceSpreadPct}% spread</span>
                          <span className="insight-lbl">
                            price volatility · {spreadInfo.label}
                            <Tip text={`(High − Low) ÷ Avg = ${priceSpreadPct}%. ${spreadInfo.tip}`} />
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {Object.keys(condition_breakdown).length > 0 && (
                    <div className="card condition-block">
                      <div className="section-title">
                        Avg Price by Condition
                        <Tip text="Average eBay sale price grouped by the condition listed. Use this to price your item based on its actual condition." />
                        {condMult && (
                          <span className="condition-mult">
                            {condMult.highName} is {condMult.mult}× {condMult.lowName}
                            <Tip text={`${condMult.highName} condition sells for ${condMult.mult}× the price of ${condMult.lowName}. Know your item's condition before pricing.`} />
                          </span>
                        )}
                      </div>
                      <div className="condition-grid">
                        {Object.entries(condition_breakdown)
                          .sort((a, b) => b[1] - a[1])
                          .map(([cond, avg]) => (
                            <div key={cond} className="condition-row">
                              <span className="condition-name">{cond}</span>
                              <div className="condition-bar-wrap">
                                <div className="condition-bar"
                                  style={{ width: `${Math.min(100, (avg / (stats.max || 1)) * 100)}%` }}
                                />
                              </div>
                              <span className="condition-price">{fmt(avg)}</span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                  {topWatched.length > 0 && (
                    <div className="card top-watched-card">
                      <div className="section-title">
                        Most Watched Active Listings
                        <span className="section-type-note">competition intel</span>
                        <Tip text="Current eBay listings with the most watchers. High watchers = real buyer interest. Check these prices — if they're not selling, buyers want a lower price." />
                      </div>
                      <div className="top-watched-list">
                        {topWatched.slice(0, 5).map((l, i) => (
                          <div key={i} className="watched-row">
                            <span className="watched-eyes">👁 {l.watch_count}</span>
                            <span className="watched-title">
                              {l.url
                                ? <a href={l.url} target="_blank" rel="noreferrer">{l.title}</a>
                                : l.title}
                            </span>
                            <span className="watched-price">{fmt(l.price)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <ListingsTable
                    listings={sold_listings}
                    cols={['title', 'condition', 'price', 'date']}
                    initialSort={{ col: 'date', dir: 'desc' }}
                  />

                  {sources.ebay_unsold?.count > 0 && (
                    <div className="card unsold-block">
                      <div className="section-title unsold-title">
                        ⚠ Didn't Sell
                        <span className="section-count">{sources.ebay_unsold.count}</span>
                        <span className="section-type-note">price ceiling</span>
                        <Tip text="Listings that expired without a sale. These set a price ceiling — if sellers couldn't move it at these prices, you probably can't either. Price below the unsold average." />
                      </div>
                      <div className="unsold-note">
                        {sources.ebay_unsold.count} listings averaged{' '}
                        <strong>{fmt(sources.ebay_unsold.avg)}</strong> and failed to sell.
                        Items priced above <strong>{fmt(sources.ebay_unsold.min)}</strong> are unlikely to move.
                      </div>
                      <ListingsTable
                        listings={sources.ebay_unsold.listings?.slice(0, 10) || []}
                        cols={['title', 'condition', 'price', 'date']}
                        typeLabel="Unsold"
                      />
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── Etsy tab ── */}
          {activeTab === 'etsy' && (
            <div className="tab-content">
              {!hasEtsyData ? (
                <div className="tab-empty">
                  {!sources.etsy?.configured
                    ? 'Add ETSY_API_KEY to your .env to enable Etsy listings (free at developers.etsy.com).'
                    : 'No Etsy listings found for this search.'}
                </div>
              ) : (
                <>
                  <div className="source-note">
                    These are <strong>active asking prices</strong> from Etsy vintage sellers —
                    not confirmed sales. Etsy collector prices are often higher than eBay.
                  </div>
                  <div className="price-cards">
                    <div className="price-card">
                      <div className="price-card-label">Avg Asking</div>
                      <div className="price-card-value">{fmt(sources.etsy.avg)}</div>
                    </div>
                    <div className="price-card">
                      <div className="price-card-label">Median</div>
                      <div className="price-card-value">{fmt(sources.etsy.median)}</div>
                    </div>
                    <div className="price-card price-card-min">
                      <div className="price-card-label">Low</div>
                      <div className="price-card-value">{fmt(sources.etsy.min)}</div>
                    </div>
                    <div className="price-card price-card-max">
                      <div className="price-card-label">High</div>
                      <div className="price-card-value">{fmt(sources.etsy.max)}</div>
                    </div>
                  </div>
                  <ListingsTable
                    listings={sources.etsy.listings || []}
                    cols={['title', 'price', 'shop']}
                    typeLabel="Active listing"
                  />
                </>
              )}
            </div>
          )}

          {/* ── Heritage tab ── */}
          {activeTab === 'heritage' && (
            <div className="tab-content">
              {!hasHeritage ? (
                <div className="tab-empty">
                  No Heritage auction results found. Heritage is most useful for rare, high-value, or NRFB items.
                </div>
              ) : (
                <>
                  <div className="source-note">
                    Heritage Auctions <strong>realized prices</strong> — what collectors paid at auction.
                    These represent the high end of the market for exceptional pieces.
                  </div>
                  <div className="price-cards">
                    <div className="price-card">
                      <div className="price-card-label">Avg Realized</div>
                      <div className="price-card-value">{fmt(sources.heritage.avg)}</div>
                    </div>
                    <div className="price-card">
                      <div className="price-card-label">Median</div>
                      <div className="price-card-value">{fmt(sources.heritage.median)}</div>
                    </div>
                    <div className="price-card price-card-min">
                      <div className="price-card-label">Low</div>
                      <div className="price-card-value">{fmt(sources.heritage.min)}</div>
                    </div>
                    <div className="price-card price-card-max">
                      <div className="price-card-label">High</div>
                      <div className="price-card-value">{fmt(sources.heritage.max)}</div>
                    </div>
                  </div>
                  <ListingsTable
                    listings={sources.heritage.listings || []}
                    cols={['title', 'price', 'date']}
                    typeLabel="Auction result"
                  />
                </>
              )}
            </div>
          )}

          {/* ── BGG tab ── */}
          {activeTab === 'bgg' && (
            <div className="tab-content">
              {!sources.bgg?.found ? (
                <div className="tab-empty">
                  BoardGameGeek data is only available for board game searches.
                  {sources.bgg && !sources.bgg.found && sources.bgg.reason &&
                    ` (${sources.bgg.reason})`}
                </div>
              ) : (
                <>
                  {/* Game info card */}
                  <div className="card bgg-info-card">
                    <div className="bgg-game-name">{sources.bgg.name}</div>
                    <div className="bgg-meta">
                      {sources.bgg.year && <span>Published: {sources.bgg.year}</span>}
                      {sources.bgg.avg_rating && (
                        <span>
                          BGG Rating: <strong>{sources.bgg.avg_rating}/10</strong>
                          {sources.bgg.num_ratings && ` (${sources.bgg.num_ratings.toLocaleString()} ratings)`}
                        </span>
                      )}
                      {sources.bgg.bgg_rank && (
                        <span>BGG Rank: <strong>#{sources.bgg.bgg_rank.toLocaleString()}</strong></span>
                      )}
                    </div>
                    {sources.bgg.description && (
                      <div className="bgg-description">{sources.bgg.description}</div>
                    )}
                  </div>

                  {hasBgg ? (
                    <>
                      <div className="source-note">
                        BGG Marketplace <strong>asking prices</strong> from board game collectors.
                      </div>
                      <div className="price-cards">
                        <div className="price-card">
                          <div className="price-card-label">Avg Asking</div>
                          <div className="price-card-value">{fmt(sources.bgg.marketplace_stats?.avg)}</div>
                        </div>
                        <div className="price-card">
                          <div className="price-card-label">Median</div>
                          <div className="price-card-value">{fmt(sources.bgg.marketplace_stats?.median)}</div>
                        </div>
                        <div className="price-card price-card-min">
                          <div className="price-card-label">Low</div>
                          <div className="price-card-value">{fmt(sources.bgg.marketplace_stats?.min)}</div>
                        </div>
                        <div className="price-card price-card-max">
                          <div className="price-card-label">High</div>
                          <div className="price-card-value">{fmt(sources.bgg.marketplace_stats?.max)}</div>
                        </div>
                      </div>
                      <ListingsTable
                        listings={sources.bgg.marketplace_listings || []}
                        cols={['title', 'condition', 'price']}
                        typeLabel="BGG listing"
                      />
                    </>
                  ) : (
                    <div className="tab-empty">No BGG marketplace listings found for this game.</div>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}


function sortListings(listings, col, dir) {
  if (!col) return listings
  return [...listings].sort((a, b) => {
    let av, bv
    if (col === 'price') {
      av = a.price ?? -Infinity
      bv = b.price ?? -Infinity
    } else if (col === 'date') {
      const parse = item => {
        const s = item.sale_date || item.end_time
        if (!s) return 0
        const d = new Date(s)
        return isNaN(d) ? 0 : d.getTime()
      }
      av = parse(a); bv = parse(b)
    } else if (col === 'condition') {
      av = (a.condition || '').toLowerCase()
      bv = (b.condition || '').toLowerCase()
    } else if (col === 'title') {
      av = (a.title || '').toLowerCase()
      bv = (b.title || '').toLowerCase()
    } else if (col === 'shop') {
      av = (a.shop_name || '').toLowerCase()
      bv = (b.shop_name || '').toLowerCase()
    } else {
      return 0
    }
    if (av < bv) return dir === 'asc' ? -1 : 1
    if (av > bv) return dir === 'asc' ? 1 : -1
    return 0
  })
}

function SortTh({ col, label, sortCol, sortDir, onSort }) {
  const active = sortCol === col
  return (
    <th className={`sortable-th ${active ? 'sort-active' : ''}`} onClick={() => onSort(col)}>
      {label}
      <span className="sort-arrow">
        {active ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ' ⇅'}
      </span>
    </th>
  )
}

function ListingsTable({ listings, cols, typeLabel, initialSort = null }) {
  const [sortCol, setSortCol] = useState(initialSort?.col || null)
  const [sortDir, setSortDir] = useState(initialSort?.dir || 'desc')
  const [showAll, setShowAll] = useState(false)

  if (!listings?.length) return null

  function handleSort(col) {
    if (sortCol === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(col)
      setSortDir(col === 'title' || col === 'condition' || col === 'shop' ? 'asc' : 'desc')
    }
    setShowAll(false)
  }

  const sorted = sortListings(listings, sortCol, sortDir)
  const visible = showAll ? sorted : sorted.slice(0, 20)
  const canShowMore = listings.length > 20

  const thProps = col => ({ col, sortCol, sortDir, onSort: handleSort })

  return (
    <div className="card sold-table-wrap">
      <div className="section-title">
        Listings
        <span className="section-count">{listings.length}</span>
        {typeLabel && <span className="section-type-note">{typeLabel}</span>}
      </div>
      <table className="sold-table">
        <thead>
          <tr>
            {cols.includes('title')     && <SortTh label="Title"     {...thProps('title')} />}
            {cols.includes('condition') && <SortTh label="Condition" {...thProps('condition')} />}
            {cols.includes('price')     && <SortTh label="Price"     {...thProps('price')} />}
            {cols.includes('date')      && <SortTh label="Date"      {...thProps('date')} />}
            {cols.includes('shop')      && <SortTh label="Shop"      {...thProps('shop')} />}
          </tr>
        </thead>
        <tbody>
          {visible.map((item, i) => (
            <tr key={i}>
              {cols.includes('title') && (
                <td className="listing-title">
                  {item.url
                    ? <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
                    : item.title}
                </td>
              )}
              {cols.includes('condition') && (
                <td><span className="cond-tag">{item.condition || '—'}</span></td>
              )}
              {cols.includes('price') && (
                <td className="listing-price">{fmt(item.price)}</td>
              )}
              {cols.includes('date') && (
                <td className="listing-date">{item.sale_date || fmtDate(item.end_time) || '—'}</td>
              )}
              {cols.includes('shop') && (
                <td className="listing-date">{item.shop_name || '—'}</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {canShowMore && (
        <button className="btn-ghost show-more" onClick={() => setShowAll(v => !v)}>
          {showAll ? 'Show fewer' : `Show all ${listings.length}`}
        </button>
      )}
    </div>
  )
}


function EbayDebugPanel({ debug, errorStatus }) {
  const [open, setOpen] = useState(false)

  const statusMsg = errorStatus === 'rate_limited'
    ? { icon: '⏱', text: 'eBay rate-limited this request. Wait 1–2 minutes and try again.', cls: 'warn' }
    : { icon: '🔍', text: 'No eBay sold listings found for this search.', cls: 'info' }

  return (
    <div className="ebay-debug-wrap">
      <div className={`tab-empty tab-empty-${statusMsg.cls}`}>
        {statusMsg.icon} {statusMsg.text}
      </div>
      {debug && Object.keys(debug).length > 0 && (
        <div className="ebay-debug-section">
          <button className="ebay-debug-toggle" onClick={() => setOpen(v => !v)}>
            {open ? '▾' : '▸'} Scraper diagnostics
          </button>
          {open && (
            <table className="ebay-debug-table">
              <tbody>
                {debug.page_title     != null && <tr><td>Page title</td><td>{debug.page_title}</td></tr>}
                {debug.final_url      != null && <tr><td>Final URL</td><td className="debug-url">{debug.final_url}</td></tr>}
                {debug.s_card_count   != null && <tr><td><code>li.s-card</code> count</td><td>{debug.s_card_count}</td></tr>}
                {debug.s_item_count   != null && <tr><td><code>li.s-item</code> count</td><td>{debug.s_item_count}</td></tr>}
                {debug.srp_li_count   != null && <tr><td>SRP <code>&lt;li&gt;</code> total</td><td>{debug.srp_li_count}</td></tr>}
                {debug.extracted_count!= null && <tr><td>Listings extracted</td><td>{debug.extracted_count}</td></tr>}
                {debug.no_results_element && <tr><td>No-results text</td><td>{debug.no_results_element}</td></tr>}
                {debug.body_snippet   != null && (
                  <tr><td>Page text (first 400 chars)</td><td className="debug-snippet">{debug.body_snippet}</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
