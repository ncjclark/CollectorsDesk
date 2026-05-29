import { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts'
import './ItemDetail.css'

const CONDITIONS = ['sealed', 'complete', 'incomplete', 'loose', 'damaged']
const STATUSES = [
  { value: 'not_listed', label: 'Not Listed' },
  { value: 'listed', label: 'Listed' },
  { value: 'sold', label: 'Sold' },
  { value: 'hold', label: 'On Hold' },
]
const CATEGORIES = [
  { value: 'barbie', label: 'Barbie / Dolls' },
  { value: 'board_game', label: 'Board Game' },
]

const HAIR_CONDITIONS = ['mint', 'good', 'frizzy', 'cut', 'rooted issues']
const ACCESSORY_OPTIONS = ['original outfit', 'shoes', 'accessories', 'stand', 'box', 'booklet']

function fmt(val) {
  if (val == null) return '—'
  return '$' + Number(val).toFixed(2)
}

function fmtDate(isoStr) {
  if (!isoStr) return '—'
  return new Date(isoStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function ItemDetail({ itemId, onClose, onUpdated, onDeleted }) {
  const [item, setItem] = useState(null)
  const [loading, setLoading] = useState(true)
  const [researching, setResearching] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [edits, setEdits] = useState({})
  const [dirty, setDirty] = useState(false)
  const [researchMsg, setResearchMsg] = useState(null)
  const [listing, setListing] = useState(null)
  const [listingLoading, setListingLoading] = useState(false)
  const [showBarbieFields, setShowBarbieFields] = useState(false)
  const [barbieDetails, setBarbieDetails] = useState({ hair: '', clothes: '', accessories: [], box: '' })
  const [copied, setCopied] = useState(null)

  useEffect(() => {
    loadItem()
  }, [itemId])

  async function loadItem() {
    setLoading(true)
    try {
      const resp = await fetch(`/api/inventory/${itemId}`)
      if (!resp.ok) throw new Error('Not found')
      const data = await resp.json()
      setItem(data)
      setEdits({})
      setDirty(false)
    } finally {
      setLoading(false)
    }
  }

  function set(field, val) {
    setEdits(e => ({ ...e, [field]: val }))
    setDirty(true)
  }

  function val(field) {
    return field in edits ? edits[field] : (item?.[field] ?? '')
  }

  async function handleSave() {
    if (!dirty) return
    setSaving(true)
    try {
      const payload = { ...edits }
      if (payload.year !== undefined) payload.year = payload.year ? parseInt(payload.year) : null
      if (payload.quantity !== undefined) payload.quantity = parseInt(payload.quantity) || 1
      if (payload.my_asking_price !== undefined)
        payload.my_asking_price = payload.my_asking_price ? parseFloat(payload.my_asking_price) : null
      if (payload.sold_price !== undefined)
        payload.sold_price = payload.sold_price ? parseFloat(payload.sold_price) : null

      const resp = await fetch(`/api/inventory/${itemId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) throw new Error('Save failed')
      const updated = await resp.json()
      setItem(updated)
      setEdits({})
      setDirty(false)
      onUpdated?.(updated)
    } finally {
      setSaving(false)
    }
  }

  async function handleResearch() {
    setResearching(true)
    setResearchMsg(null)
    try {
      const resp = await fetch(`/api/inventory/${itemId}/research`, { method: 'POST' })
      if (!resp.ok) throw new Error('Research failed')
      const result = await resp.json()
      setResearchMsg(result.message)
      await loadItem()
      onUpdated?.({ id: itemId })
    } finally {
      setResearching(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await fetch(`/api/inventory/${itemId}`, { method: 'DELETE' })
      onDeleted?.(itemId)
    } finally {
      setDeleting(false)
    }
  }

  async function handleGenerateListing() {
    setListingLoading(true)
    setListing(null)
    try {
      const resp = await fetch(`/api/inventory/${itemId}/generate-listing`, { method: 'POST' })
      if (!resp.ok) throw new Error('Failed')
      setListing(await resp.json())
    } finally {
      setListingLoading(false)
    }
  }

  function copyText(text, key) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key)
      setTimeout(() => setCopied(null), 1800)
    })
  }

  if (loading) {
    return (
      <div className="item-detail">
        <div className="detail-loading"><span className="spinner" /> Loading…</div>
      </div>
    )
  }

  if (!item) return null

  const research = item.research
  const statusVal = val('status') || item.status

  return (
    <div className="item-detail">
      <div className="detail-header">
        <div className="detail-title-row">
          <h2 className="detail-name">{item.name}</h2>
          <button className="detail-close" onClick={onClose}>×</button>
        </div>
        <div className="detail-meta">
          {item.category && (
            <span className={`tag tag-${item.category}`}>
              {item.category === 'barbie' ? 'Barbie' : 'Board Game'}
            </span>
          )}
          {item.year && <span className="meta-year">{item.year}</span>}
          <span className={`tag tag-${statusVal.replace('_', '')}`}>
            {STATUSES.find(s => s.value === statusVal)?.label || statusVal}
          </span>
        </div>
      </div>

      {/* Research summary */}
      {research && (
        <div className="detail-research card">
          <div className="research-row">
            <div className="research-stat">
              <div className="research-val">{fmt(research.avg_sold_price)}</div>
              <div className="research-lbl">avg sold</div>
            </div>
            <div className="research-stat">
              <div className="research-val">{fmt(research.min_sold_price)}</div>
              <div className="research-lbl">low</div>
            </div>
            <div className="research-stat">
              <div className="research-val">{fmt(research.max_sold_price)}</div>
              <div className="research-lbl">high</div>
            </div>
            <div className="research-stat">
              <div className="research-val">{research.sold_count_30d ?? '—'}</div>
              <div className="research-lbl">sold 30d</div>
            </div>
            <div className="research-stat" style={{marginLeft:'auto'}}>
              <div className="research-val" style={{fontSize:12}}>{fmtDate(research.last_sold_date)}</div>
              <div className="research-lbl">last sold</div>
            </div>
          </div>
          <div className="research-footer">
            <span className="research-source">
              Source: {research.source} · updated {fmtDate(research.fetched_at)}
            </span>
          </div>
        </div>
      )}

      {!research && (
        <div className="detail-no-research card">
          No price research yet.
        </div>
      )}

      <button
        className="btn-secondary research-btn"
        onClick={handleResearch}
        disabled={researching}
      >
        {researching ? <><span className="spinner" /> Researching…</> : '↻ Re-research Prices'}
      </button>
      {researchMsg && <div className="research-msg">{researchMsg}</div>}

      {/* Editable fields */}
      <div className="detail-fields">
        <div className="field-group">
          <label>Name</label>
          <input type="text" value={val('name')} onChange={e => set('name', e.target.value)} />
        </div>

        <div className="field-row-2">
          <div className="field-group">
            <label>Category</label>
            <select value={val('category')} onChange={e => set('category', e.target.value)}>
              <option value="">— select —</option>
              {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label>Year</label>
            <input type="number" value={val('year')} onChange={e => set('year', e.target.value)} placeholder="e.g. 1972" />
          </div>
        </div>

        <div className="field-row-2">
          <div className="field-group">
            <label>Condition</label>
            <select value={val('condition')} onChange={e => set('condition', e.target.value)}>
              <option value="">— select —</option>
              {CONDITIONS.map(c => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label>Quantity</label>
            <input type="number" value={val('quantity')} onChange={e => set('quantity', e.target.value)} min="1" />
          </div>
        </div>

        <div className="field-row-2">
          <div className="field-group">
            <label>Model / Stock #</label>
            <input type="text" value={val('model_number')} onChange={e => set('model_number', e.target.value)} placeholder="Optional" />
          </div>
          <div className="field-group">
            <label>Asking Price ($)</label>
            <input type="number" value={val('my_asking_price')} onChange={e => set('my_asking_price', e.target.value)} placeholder="Your price" step="0.01" min="0" />
          </div>
        </div>

        <div className="field-group">
          <label>Status</label>
          <select value={val('status')} onChange={e => set('status', e.target.value)}>
            {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>

        {statusVal === 'listed' && (
          <div className="field-group">
            <label>eBay Listing URL</label>
            <input type="url" value={val('ebay_listing_url')} onChange={e => set('ebay_listing_url', e.target.value)} placeholder="https://ebay.com/itm/..." />
          </div>
        )}

        {statusVal === 'sold' && (
          <div className="field-row-2">
            <div className="field-group">
              <label>Sold Price ($)</label>
              <input type="number" value={val('sold_price')} onChange={e => set('sold_price', e.target.value)} step="0.01" min="0" />
            </div>
            <div className="field-group">
              <label>Sold Date</label>
              <input type="date" value={val('sold_date') ? val('sold_date').split('T')[0] : ''} onChange={e => set('sold_date', e.target.value)} />
            </div>
          </div>
        )}

        <div className="field-group">
          <label>Notes</label>
          <textarea value={val('notes')} onChange={e => set('notes', e.target.value)} placeholder="Condition details, accessories, provenance…" rows={3} />
        </div>
      </div>

      {/* Barbie-specific condition fields */}
      {(val('category') === 'barbie' || item?.category === 'barbie') && (
        <div className="barbie-section">
          <button
            className="barbie-section-toggle"
            onClick={() => setShowBarbieFields(v => !v)}
          >
            🎀 Barbie Condition Details {showBarbieFields ? '▲' : '▼'}
          </button>
          {showBarbieFields && (
            <div className="barbie-fields">
              <div className="field-row-2">
                <div className="field-group">
                  <label>Hair Condition</label>
                  <select value={barbieDetails.hair} onChange={e => setBarbieDetails(d => ({ ...d, hair: e.target.value }))}>
                    <option value="">— select —</option>
                    {HAIR_CONDITIONS.map(h => <option key={h} value={h}>{h.charAt(0).toUpperCase() + h.slice(1)}</option>)}
                  </select>
                </div>
                <div className="field-group">
                  <label>Original Clothes</label>
                  <select value={barbieDetails.clothes} onChange={e => setBarbieDetails(d => ({ ...d, clothes: e.target.value }))}>
                    <option value="">— select —</option>
                    <option value="yes">Yes — original outfit</option>
                    <option value="partial">Partial</option>
                    <option value="no">No outfit</option>
                    <option value="replacement">Replacement outfit</option>
                  </select>
                </div>
              </div>
              <div className="field-group">
                <label>Accessories Present</label>
                <div className="accessory-chips">
                  {ACCESSORY_OPTIONS.map(a => (
                    <button
                      key={a}
                      className={`accessory-chip ${barbieDetails.accessories.includes(a) ? 'active' : ''}`}
                      onClick={() => setBarbieDetails(d => ({
                        ...d,
                        accessories: d.accessories.includes(a)
                          ? d.accessories.filter(x => x !== a)
                          : [...d.accessories, a],
                      }))}
                    >
                      {a}
                    </button>
                  ))}
                </div>
              </div>
              <div className="field-group">
                <label>Box Condition</label>
                <select value={barbieDetails.box} onChange={e => setBarbieDetails(d => ({ ...d, box: e.target.value }))}>
                  <option value="">— select —</option>
                  <option value="none">No box</option>
                  <option value="fair">Box — fair</option>
                  <option value="good">Box — good</option>
                  <option value="mint">Box — mint / near mint</option>
                </select>
              </div>
            </div>
          )}
        </div>
      )}

      {/* eBay listing generator */}
      <div className="listing-section">
        <button
          className="btn-secondary listing-gen-btn"
          onClick={handleGenerateListing}
          disabled={listingLoading}
        >
          {listingLoading ? <><span className="spinner" style={{width:13,height:13}} /> Generating…</> : '🏷 Generate eBay Listing'}
        </button>

        {listing && (
          <div className="listing-result">
            <div className="listing-field">
              <div className="listing-field-label">
                Title <span className="char-count">{listing.title?.length}/80 chars</span>
              </div>
              <div className="listing-field-value">{listing.title}</div>
              <button className="copy-btn" onClick={() => copyText(listing.title, 'title')}>
                {copied === 'title' ? '✓ Copied' : 'Copy'}
              </button>
            </div>
            <div className="listing-field">
              <div className="listing-field-label">Condition Description</div>
              <div className="listing-field-value">{listing.condition_description}</div>
              <button className="copy-btn" onClick={() => copyText(listing.condition_description, 'desc')}>
                {copied === 'desc' ? '✓ Copied' : 'Copy'}
              </button>
            </div>
            {listing.suggested_price && (() => {
              const price = listing.suggested_price
              const ebayFee = price * 0.1325 + 0.30
              const netProfit = price - ebayFee
              return (
                <div className="listing-price-row">
                  <div className="listing-price-main">
                    <span className="listing-price-val">${price.toFixed(2)}</span>
                    <span className="listing-price-note">{listing.price_note}</span>
                    {listing.research_range && (
                      <span className="listing-range">eBay range: {listing.research_range}</span>
                    )}
                  </div>
                  <div className="fee-breakdown">
                    <div className="fee-row">
                      <span className="fee-label">eBay fee (13.25% + $0.30)</span>
                      <span className="fee-val fee-deduct">−${ebayFee.toFixed(2)}</span>
                    </div>
                    <div className="fee-row fee-net-row">
                      <span className="fee-label">You receive</span>
                      <span className="fee-val fee-net">${netProfit.toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              )
            })()}
          </div>
        )}
      </div>

      {/* Save / delete */}
      <div className="detail-actions">
        {!confirmDelete ? (
          <>
            <button className="btn-danger" onClick={() => setConfirmDelete(true)}>Delete</button>
            <button className="btn-primary" onClick={handleSave} disabled={!dirty || saving}>
              {saving ? <span className="spinner" /> : 'Save Changes'}
            </button>
          </>
        ) : (
          <>
            <span style={{fontSize:13, color:'var(--text-muted)'}}>Are you sure?</span>
            <button className="btn-secondary" onClick={() => setConfirmDelete(false)}>Cancel</button>
            <button className="btn-danger" onClick={handleDelete} disabled={deleting}>
              {deleting ? <span className="spinner" /> : 'Confirm Delete'}
            </button>
          </>
        )}
      </div>

      {/* Research history + trend chart */}
      {item.research_history?.length > 1 && (
        <div className="detail-history">
          <div className="history-title">Price History</div>

          {item.research_history.length >= 2 && (() => {
            const chartData = [...item.research_history]
              .filter(r => r.avg_sold_price != null)
              .reverse()
              .map(r => ({
                date: new Date(r.fetched_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                price: r.avg_sold_price,
              }))

            if (chartData.length < 2) return null

            const prices = chartData.map(d => d.price)
            const yMin = Math.floor(Math.min(...prices) * 0.9)
            const yMax = Math.ceil(Math.max(...prices) * 1.1)

            return (
              <div className="price-trend-chart">
                <ResponsiveContainer width="100%" height={140}>
                  <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[yMin, yMax]}
                      tickFormatter={v => `$${v}`}
                      tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                      width={48}
                    />
                    <Tooltip
                      formatter={v => [`$${Number(v).toFixed(2)}`, 'Avg sold']}
                      contentStyle={{
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border)',
                        borderRadius: 6,
                        fontSize: 12,
                      }}
                      labelStyle={{ color: 'var(--text-muted)', marginBottom: 2 }}
                      itemStyle={{ color: 'var(--text)' }}
                    />
                    <Line
                      type="monotone"
                      dataKey="price"
                      stroke="#6c8ef5"
                      strokeWidth={2}
                      dot={{ fill: '#6c8ef5', r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )
          })()}

          <table className="history-table">
            <thead>
              <tr><th>Date</th><th>Avg Price</th><th>Sold 30d</th></tr>
            </thead>
            <tbody>
              {item.research_history.map((r, i) => (
                <tr key={i}>
                  <td>{fmtDate(r.fetched_at)}</td>
                  <td>{fmt(r.avg_sold_price)}</td>
                  <td>{r.sold_count_30d ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
