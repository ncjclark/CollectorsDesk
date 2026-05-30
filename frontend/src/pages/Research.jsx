import { useState, useRef } from 'react'
import SearchBar from '../components/SearchBar'
import ResultsPanel from '../components/ResultsPanel'
import SaveItemModal from '../components/SaveItemModal'
import './Research.css'

const SOURCE_LABELS = {
  upcitemdb: 'UPCitemDB',
  openfoodfacts: 'Open Food Facts',
}

const BARBIE_KEYWORDS = ['barbie', 'skipper', 'midge', 'christie', 'francie', 'ken doll', 'mattel doll']
const BOARD_GAME_KEYWORDS = ['monopoly', 'clue', 'cluedo', 'scrabble', 'risk', 'sorry', 'battleship',
  'operation', 'trivial pursuit', 'stratego', 'board game', 'yahtzee', 'boggle', 'parcheesi',
  'checkers', 'chess', 'connect four', 'mastermind', 'othello', 'backgammon', 'aggravation']

function buildPrefill(query, results) {
  const q = query.toLowerCase()
  const bgg = results?.sources?.bgg
  const stats = results?.stats || {}

  // Category detection
  let category = ''
  if (bgg?.found) {
    category = 'board_game'
  } else if (BARBIE_KEYWORDS.some(k => q.includes(k))) {
    category = 'barbie'
  } else if (BOARD_GAME_KEYWORDS.some(k => q.includes(k))) {
    category = 'board_game'
  }

  // Year — prefer BGG's authoritative year, else parse from query string
  let year = ''
  if (bgg?.year) {
    year = bgg.year
  } else {
    const m = query.match(/\b(19[0-9]{2}|20[0-2][0-9])\b/)
    if (m) year = m[1]
  }

  // Suggested asking price — median is more robust than avg for skewed markets
  let my_asking_price = ''
  if (stats.median) {
    my_asking_price = stats.median.toFixed(2)
  } else if (stats.avg) {
    my_asking_price = stats.avg.toFixed(2)
  }

  // Model number — BGG game ID as a hint for board games
  let model_number = ''
  if (bgg?.game_id) {
    model_number = `BGG-${bgg.game_id}`
  }

  return { category, year, my_asking_price, model_number }
}

export default function Research() {
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [saveModal, setSaveModal] = useState(null)
  const [toast, setToast] = useState(null)
  const [fallbackState, setFallbackState] = useState(null) // {step, originalQuery}
  const [lastSearchParams, setLastSearchParams] = useState(null)
  const [barcode, setBarcode] = useState('')
  const [barcodeLoading, setBarcodeLoading] = useState(false)
  const [barcodeError, setBarcodeError] = useState(null)
  const [barcodeSource, setBarcodeSource] = useState(null) // { name, source }
  const [manualPrice, setManualPrice] = useState({ note: '', price: '' })
  const barcodeRef = useRef(null)

  function showToast(msg, type = 'success') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3500)
  }

  async function handleSearch(params, isFallback = false) {
    setLoading(true)
    setError(null)
    if (!isFallback) {
      setFallbackState(null)
      setBarcodeSource(null)
    }

    try {
      if (!isFallback) setLastSearchParams(params)
      const resp = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days_back: 90, ...params }),
      })
      if (!resp.ok) throw new Error(`Search failed: ${resp.status}`)
      const data = await resp.json()

      // Only auto-broaden when every source is empty — don't fire a second
      // request just because eBay is 0 while Etsy/Heritage/BGG has data.
      const noDataAnywhere = data.stats.count_90d === 0
        && !(data.sources?.etsy?.count > 0)
        && !(data.sources?.heritage?.count > 0)
        && !data.sources?.bgg?.found

      if (noDataAnywhere && !isFallback) {
        const words = params.query.trim().split(/\s+/)
        if (words.length > 2) {
          setFallbackState({ step: 'broadened', originalQuery: params.query })
          const broadened = words.slice(0, -1).join(' ')
          setResults(data)
          await handleSearch({ ...params, query: broadened }, true)
          return
        }
        setFallbackState({ step: 'manual', originalQuery: params.query })
      } else if (isFallback && noDataAnywhere) {
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
        setBarcodeSource({ name: data.name, source: data.source, model: data.model_number })
        // Append model/stock number to query when available — helps Etsy matching
        const query = data.model_number
          ? `${data.name} #${data.model_number}`
          : data.name
        handleSearch({ query, category: null, days_back: 90 })
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
          {barcodeSource && (
            <div className="barcode-source-row">
              <span className="barcode-source-label">Identified as</span>
              <span className="barcode-source-name">"{barcodeSource.name}"</span>
              {barcodeSource.model && (
                <span className="barcode-source-model">#{barcodeSource.model}</span>
              )}
              <span className="barcode-source-via">
                via {SOURCE_LABELS[barcodeSource.source] || barcodeSource.source}
              </span>
            </div>
          )}

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
              onSaveToInventory={(q, r) => {
                const prefill = buildPrefill(q, r)
                setSaveModal({ query: q, results: r, prefill })
              }}
              onForceRefresh={lastSearchParams
                ? () => handleSearch({ ...lastSearchParams, force_refresh: true })
                : null}
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
