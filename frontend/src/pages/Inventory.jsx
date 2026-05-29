import { useState, useEffect, useCallback } from 'react'
import ItemDetail from '../components/ItemDetail'
import SaveItemModal from '../components/SaveItemModal'
import ImportModal from '../components/ImportModal'
import './Inventory.css'

const STATUS_LABELS = {
  not_listed: 'Not Listed',
  listed: 'Listed',
  sold: 'Sold',
  hold: 'On Hold',
}

function fmt(val) {
  if (val == null) return '—'
  return '$' + Number(val).toFixed(2)
}

function fmtDate(isoStr) {
  if (!isoStr) return '—'
  return new Date(isoStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function Inventory() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [showImportModal, setShowImportModal] = useState(false)
  const [toast, setToast] = useState(null)
  // Filters
  const [search, setSearch] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterCondition, setFilterCondition] = useState('')
  const [sortBy, setSortBy] = useState('created_at')
  const [sortDir, setSortDir] = useState('desc')

  const loadItems = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (filterCategory) params.set('category', filterCategory)
      if (filterStatus) params.set('status', filterStatus)
      if (filterCondition) params.set('condition', filterCondition)
      params.set('sort_by', sortBy)
      params.set('sort_dir', sortDir)

      const resp = await fetch(`/api/inventory?${params}`)
      const data = await resp.json()
      setItems(data)
    } finally {
      setLoading(false)
    }
  }, [search, filterCategory, filterStatus, filterCondition, sortBy, sortDir])

  useEffect(() => { loadItems() }, [loadItems])

  function showToast(msg, type = 'success') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3500)
  }

  async function handleExport() {
    const resp = await fetch('/api/export/csv')
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `inventory_${new Date().toISOString().slice(0,10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  function handleSort(col) {
    if (sortBy === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortDir('desc')
    }
  }

  function SortIcon({ col }) {
    if (sortBy !== col) return <span style={{ color: 'var(--border)' }}>⇅</span>
    return <span style={{ color: 'var(--accent)' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  const statusCounts = items.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1
    return acc
  }, {})

  return (
    <div className="page inventory-page">
      <div className="inv-header">
        <div>
          <h1>Inventory</h1>
          <p>Track your collection from shelf to sold</p>
        </div>
        <div className="inv-header-actions">
          <button className="btn-ghost" onClick={handleExport} title="Export CSV">↓ Export CSV</button>
          <button className="btn-secondary" onClick={() => setShowImportModal(true)}>↑ Import CSV</button>
          <button className="btn-primary" onClick={() => setShowAddModal(true)}>+ Add Item</button>
        </div>
      </div>

      {/* Status summary bar */}
      {items.length > 0 && (
        <div className="status-bar">
          <button
            className={`status-bar-chip ${filterStatus === '' ? 'active' : ''}`}
            onClick={() => setFilterStatus('')}
          >
            All <span className="chip-count">{items.length}</span>
          </button>
          {Object.entries(STATUS_LABELS).map(([val, label]) => (
            statusCounts[val] ? (
              <button
                key={val}
                className={`status-bar-chip status-bar-${val} ${filterStatus === val ? 'active' : ''}`}
                onClick={() => setFilterStatus(filterStatus === val ? '' : val)}
              >
                {label} <span className="chip-count">{statusCounts[val]}</span>
              </button>
            ) : null
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="inv-filters">
        <input
          type="text"
          placeholder="Search by name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="filter-search"
        />
        <select value={filterCategory} onChange={e => setFilterCategory(e.target.value)} className="filter-select">
          <option value="">All Categories</option>
          <option value="barbie">Barbie / Dolls</option>
          <option value="board_game">Board Games</option>
        </select>
        <select value={filterCondition} onChange={e => setFilterCondition(e.target.value)} className="filter-select">
          <option value="">All Conditions</option>
          {['sealed','complete','incomplete','loose','damaged'].map(c => (
            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
          ))}
        </select>
      </div>

      <div className={`inv-layout ${selectedId ? 'with-panel' : ''}`}>
        {/* Table */}
        <div className="inv-table-wrap">
          {loading ? (
            <div className="inv-loading"><span className="spinner" /> Loading inventory…</div>
          ) : items.length === 0 ? (
            <div className="empty-state card">
              <h3>{search || filterCategory || filterStatus || filterCondition ? 'No items match your filters' : 'No items yet'}</h3>
              <p>
                {search || filterCategory || filterStatus || filterCondition
                  ? 'Try adjusting or clearing the filters.'
                  : 'Search for an item on the Research tab and click "Save to Inventory", or click "+ Add Item".'}
              </p>
            </div>
          ) : (
            <table className="inv-table">
              <thead>
                <tr>
                  <th onClick={() => handleSort('name')} className="sortable">
                    Name <SortIcon col="name" />
                  </th>
                  <th>Category</th>
                  <th onClick={() => handleSort('condition')} className="sortable">
                    Condition <SortIcon col="condition" />
                  </th>
                  <th onClick={() => handleSort('my_asking_price')} className="sortable">
                    Asking <SortIcon col="my_asking_price" />
                  </th>
                  <th>eBay Avg</th>
                  <th onClick={() => handleSort('last_research_date')} className="sortable">
                    Researched <SortIcon col="last_research_date" />
                  </th>
                  <th onClick={() => handleSort('status')} className="sortable">
                    Status <SortIcon col="status" />
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr
                    key={item.id}
                    className={selectedId === item.id ? 'selected' : ''}
                    onClick={() => setSelectedId(item.id === selectedId ? null : item.id)}
                  >
                    <td className="item-name-cell">
                      <div className="item-name">{item.name}</div>
                      {item.year && <div className="item-year">{item.year}</div>}
                    </td>
                    <td>
                      {item.category && (
                        <span className={`tag tag-${item.category}`}>
                          {item.category === 'barbie' ? 'Barbie' : 'Board Game'}
                        </span>
                      )}
                    </td>
                    <td>
                      {item.condition ? (
                        <span className="cond-pill">
                          {item.condition.charAt(0).toUpperCase() + item.condition.slice(1)}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="price-cell">{fmt(item.my_asking_price)}</td>
                    <td className="price-cell ebay-price">
                      {fmt(item.research?.avg_sold_price)}
                    </td>
                    <td className="date-cell">
                      {item.last_research_date ? fmtDate(item.last_research_date) : (
                        <span className="no-research">never</span>
                      )}
                    </td>
                    <td>
                      <span className={`tag tag-${item.status}`}>
                        {STATUS_LABELS[item.status] || item.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail panel */}
        {selectedId && (
          <div className="detail-panel">
            <ItemDetail
              itemId={selectedId}
              onClose={() => setSelectedId(null)}
              onUpdated={() => {
                loadItems()
                showToast('Item updated')
              }}
              onDeleted={() => {
                setSelectedId(null)
                loadItems()
                showToast('Item deleted')
              }}
            />
          </div>
        )}
      </div>

      {showImportModal && (
        <ImportModal
          onClose={() => setShowImportModal(false)}
          onImported={(count) => {
            setShowImportModal(false)
            loadItems()
            showToast(`${count} items imported`)
          }}
        />
      )}

      {showAddModal && (
        <SaveItemModal
          query=""
          onClose={() => setShowAddModal(false)}
          onSaved={(item) => {
            setShowAddModal(false)
            loadItems()
            showToast(`"${item.name}" added`)
            setSelectedId(item.id)
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
