import { useState, useRef } from 'react'
import SearchBar from '../components/SearchBar'
import ResultsPanel from '../components/ResultsPanel'
import SaveItemModal from '../components/SaveItemModal'
import './Research.css'

export default function Research() {
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [saveModal, setSaveModal] = useState(null)
  const [toast, setToast] = useState(null)
  const [fallbackState, setFallbackState] = useState(null) // {step, originalQuery}
  const [barcode, setBarcode] = useState('')
  const [barcodeLoading, setBarcodeLoading] = useState(false)
  const [barcodeError, setBarcodeError] = useState(null)
  const [manualPrice, setManualPrice] = useState({ note: '', price: '' })
  const barcodeRef = useRef(null)

  function showToast(msg, type = 'success') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3500)
  }

  async function handleSearch(params, isFallback = false) {
    setLoading(true)
    setError(null)
    if (!isFallback) setFallbackState(null)

    try {
      const resp = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      if (!resp.ok) throw new Error(`Search failed: ${resp.status}`)
      const data = await resp.json()

      if (data.stats.count_90d === 0 && !isFallback) {
        // Auto-broaden: drop last word if query has >2 words
        const words = params.query.trim().split(/\s+/)
        if (words.length > 2) {
          setFallbackState({ step: 'broadened', originalQuery: params.query })
          const broadened = words.slice(0, -1).join(' ')
          setResults(data) // show empty result first
          await handleSearch({ ...params, query: broadened }, true)
          return
        }
        setFallbackState({ step: 'manual', originalQuery: params.query })
      } else if (isFallback && data.stats.count_90d === 0) {
        setFallbackState({ step: 'manual', originalQuery: fallbackState?.originalQuery || params.query })
      } else {
        setFallbackState(null)
      }

      setResults(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleBarcodeLookup() {
    const upc = barcode.trim()
    if (!upc) return
    setBarcodeLoading(true)
    setBarcodeError(null)
    try {
      const resp = await fetch('/api/identify/barcode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upc }),
      })
      const data = await resp.json()
      if (data.found && data.name) {
        setBarcode('')
        handleSearch({ query: data.name, category: null, days_back: 90 })
        showToast(`Barcode identified: "${data.name}"`)
      } else {
        setBarcodeError('Barcode not found in database. Try searching by name.')
      }
    } catch {
      setBarcodeError('Lookup failed.')
    } finally {
      setBarcodeLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Research</h1>
          <p>Search eBay sold listings to find real resell values</p>
        </div>
      </div>

      <div className="research-layout">
        <div className="search-section">

          {/* Main search */}
          <SearchBar onSearch={p => handleSearch(p)} loading={loading} />

          {/* Barcode row */}
          <div className="barcode-row">
            <span className="barcode-label">Have a barcode?</span>
            <div className="barcode-input-wrap">
              <input
                ref={barcodeRef}
                type="text"
                className="barcode-input"
                placeholder="Scan or type UPC…"
                value={barcode}
                onChange={e => setBarcode(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleBarcodeLookup()}
              />
              <button
                className="btn-secondary barcode-btn"
                onClick={handleBarcodeLookup}
                disabled={!barcode.trim() || barcodeLoading}
              >
                {barcodeLoading ? <span className="spinner" style={{width:14,height:14}} /> : 'Lookup'}
              </button>
            </div>
            {barcodeError && <span className="barcode-error">{barcodeError}</span>}
          </div>

          {loading && (
            <div className="search-loading">
              <span className="spinner" />
              <span>Searching eBay sold listings…</span>
            </div>
          )}

          {error && (
            <div className="search-error card">
              <strong>Search failed:</strong> {error}
            </div>
          )}

          {/* Fallback chain callouts */}
          {!loading && fallbackState?.step === 'broadened' && (
            <div className="fallback-banner">
              <span className="fallback-icon">↩</span>
              No results for exact query — showing broadened search results below.
              <button className="btn-ghost" style={{fontSize:11}} onClick={() => setFallbackState(null)}>dismiss</button>
            </div>
          )}

          {!loading && fallbackState?.step === 'manual' && (
            <div className="card manual-entry">
              <div className="manual-title">No Market Data — Log Your Own Estimate</div>
              <div className="manual-fields">
                <input
                  type="number"
                  placeholder="Estimated price ($)"
                  value={manualPrice.price}
                  onChange={e => setManualPrice(p => ({ ...p, price: e.target.value }))}
                  style={{ width: 160 }}
                />
                <input
                  type="text"
                  placeholder="Research notes (where you looked, comparable items…)"
                  value={manualPrice.note}
                  onChange={e => setManualPrice(p => ({ ...p, note: e.target.value }))}
                  style={{ flex: 1 }}
                />
                <button
                  className="btn-primary"
                  onClick={() => {
                    setSaveModal({
                      query: fallbackState.originalQuery,
                      prefill: { my_asking_price: manualPrice.price, notes: manualPrice.note },
                    })
                    setFallbackState(null)
                  }}
                >
                  Save to Inventory
                </button>
              </div>
            </div>
          )}

          {!loading && results && fallbackState?.step !== 'manual' && (
            <ResultsPanel
              results={results}
              onSaveToInventory={(q, r) => setSaveModal({ query: q, results: r })}
            />
          )}

          {!loading && !results && !error && (
            <div className="search-hint card">
              <div className="hint-examples">
                <div className="hint-title">Try searching for:</div>
                <div className="hint-chips">
                  {[
                    'Malibu Barbie 1971',
                    'Barbie Ponytail #1 1959',
                    'Bubble Cut Barbie',
                    'Francie doll 1966',
                    'Monopoly 1961',
                    'Clue board game 1972',
                    'Stratego vintage',
                    'Axis & Allies 1984',
                  ].map(ex => (
                    <button
                      key={ex}
                      className="hint-chip"
                      onClick={() => handleSearch({ query: ex, category: null, days_back: 90 })}
                    >
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {saveModal && (
        <SaveItemModal
          query={saveModal.query}
          prefill={saveModal.prefill}
          onClose={() => setSaveModal(null)}
          onSaved={item => {
            setSaveModal(null)
            showToast(`"${item.name}" saved to inventory`)
          }}
        />
      )}

      {toast && (
        <div className="toast-container">
          <div className={`toast toast-${toast.type}`}>{toast.msg}</div>
        </div>
      )}
    </div>
  )
}
