import { useState, useEffect, useRef } from 'react'
import './SearchBar.css'

const CATEGORIES = [
  { value: '', label: 'All Categories' },
  { value: 'barbie', label: 'Barbie / Dolls' },
  { value: 'board_game', label: 'Board Games' },
]

const DAYS_OPTIONS = [
  { value: 30, label: '30 days' },
  { value: 60, label: '60 days' },
  { value: 90, label: '90 days' },
]

export default function SearchBar({ onSearch, loading }) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [daysBack, setDaysBack] = useState(90)
  const [history, setHistory] = useState([])
  const [showHistory, setShowHistory] = useState(false)
  const inputRef = useRef(null)
  const containerRef = useRef(null)

  useEffect(() => {
    const stored = localStorage.getItem('searchHistory')
    if (stored) setHistory(JSON.parse(stored))
  }, [])

  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setShowHistory(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Global keyboard shortcut: '/' to focus search
  useEffect(() => {
    const handler = (e) => {
      if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  function handleSubmit(q = query) {
    const trimmed = q.trim()
    if (!trimmed || loading) return

    // Save to localStorage history
    const updated = [trimmed, ...history.filter(h => h !== trimmed)].slice(0, 15)
    setHistory(updated)
    localStorage.setItem('searchHistory', JSON.stringify(updated))
    setShowHistory(false)

    onSearch({ query: trimmed, category: category || null, days_back: daysBack })
  }

  function handleKey(e) {
    if (e.key === 'Enter') handleSubmit()
    if (e.key === 'Escape') { setShowHistory(false); inputRef.current?.blur() }
  }

  function clearHistory() {
    setHistory([])
    localStorage.removeItem('searchHistory')
  }

  return (
    <div className="search-bar-wrapper" ref={containerRef}>
      <div className="search-row">
        <div className="search-input-wrap">
          <span className="search-icon">⌕</span>
          <input
            ref={inputRef}
            type="text"
            className="search-input"
            placeholder='Search by name, e.g. "Malibu Barbie 1971" or "Clue 1972"'
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKey}
            onFocus={() => history.length > 0 && setShowHistory(true)}
            autoComplete="off"
          />
          {query && (
            <button
              className="search-clear"
              onClick={() => { setQuery(''); inputRef.current?.focus() }}
              title="Clear"
            >×</button>
          )}
        </div>

        <select
          className="search-select"
          value={category}
          onChange={e => setCategory(e.target.value)}
        >
          {CATEGORIES.map(c => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>

        <select
          className="search-select search-select-sm"
          value={daysBack}
          onChange={e => setDaysBack(Number(e.target.value))}
        >
          {DAYS_OPTIONS.map(d => (
            <option key={d.value} value={d.value}>{d.label}</option>
          ))}
        </select>

        <button
          className="btn-primary search-btn"
          onClick={() => handleSubmit()}
          disabled={!query.trim() || loading}
        >
          {loading ? <span className="spinner" /> : 'Search'}
        </button>
      </div>

      {showHistory && history.length > 0 && (
        <div className="search-history">
          <div className="history-header">
            <span>Recent searches</span>
            <button className="btn-ghost" onClick={clearHistory} style={{fontSize:11}}>Clear</button>
          </div>
          {history.map(h => (
            <button
              key={h}
              className="history-item"
              onClick={() => { setQuery(h); handleSubmit(h) }}
            >
              <span className="history-icon">↩</span>
              {h}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
