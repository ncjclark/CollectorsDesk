import { useState } from 'react'
import './SaveItemModal.css'

const CONDITIONS = ['sealed', 'complete', 'incomplete', 'loose', 'damaged']
const CATEGORIES = [
  { value: 'barbie', label: 'Barbie / Dolls' },
  { value: 'board_game', label: 'Board Game' },
]

export default function SaveItemModal({ query, prefill = {}, onClose, onSaved }) {
  const [form, setForm] = useState({
    name: query || '',
    ...prefill,
    category: '',
    year: '',
    model_number: '',
    condition: '',
    quantity: 1,
    my_asking_price: '',
    notes: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  function set(field, val) {
    setForm(f => ({ ...f, [field]: val }))
  }

  async function handleSave() {
    if (!form.name.trim()) return
    setSaving(true)
    setError(null)
    try {
      const payload = {
        ...form,
        year: form.year ? parseInt(form.year) : null,
        quantity: parseInt(form.quantity) || 1,
        my_asking_price: form.my_asking_price ? parseFloat(form.my_asking_price) : null,
      }
      const resp = await fetch('/api/inventory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!resp.ok) throw new Error('Save failed')
      const item = await resp.json()
      onSaved(item)
    } catch (e) {
      setError('Failed to save. Try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <div className="modal-header">
          <h2>Save to Inventory</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="field-row">
            <label>Name *</label>
            <input
              type="text"
              value={form.name}
              onChange={e => set('name', e.target.value)}
              placeholder="Full item name"
              autoFocus
            />
          </div>

          <div className="field-row-2">
            <div className="field-row">
              <label>Category</label>
              <select value={form.category} onChange={e => set('category', e.target.value)}>
                <option value="">— select —</option>
                {CATEGORIES.map(c => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="field-row">
              <label>Year</label>
              <input
                type="number"
                value={form.year}
                onChange={e => set('year', e.target.value)}
                placeholder="e.g. 1972"
                min="1900" max="2030"
              />
            </div>
          </div>

          <div className="field-row-2">
            <div className="field-row">
              <label>Condition</label>
              <select value={form.condition} onChange={e => set('condition', e.target.value)}>
                <option value="">— select —</option>
                {CONDITIONS.map(c => (
                  <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                ))}
              </select>
            </div>
            <div className="field-row">
              <label>Quantity</label>
              <input
                type="number"
                value={form.quantity}
                onChange={e => set('quantity', e.target.value)}
                min="1"
              />
            </div>
          </div>

          <div className="field-row-2">
            <div className="field-row">
              <label>Model / Stock #</label>
              <input
                type="text"
                value={form.model_number}
                onChange={e => set('model_number', e.target.value)}
                placeholder="Optional"
              />
            </div>
            <div className="field-row">
              <label>Asking Price ($)</label>
              <input
                type="number"
                value={form.my_asking_price}
                onChange={e => set('my_asking_price', e.target.value)}
                placeholder="Optional"
                min="0" step="0.01"
              />
            </div>
          </div>

          <div className="field-row">
            <label>Notes</label>
            <textarea
              value={form.notes}
              onChange={e => set('notes', e.target.value)}
              placeholder="Condition details, accessories, provenance..."
              rows={3}
            />
          </div>

          {error && <div className="modal-error">{error}</div>}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={!form.name.trim() || saving}
          >
            {saving ? <span className="spinner" /> : 'Save to Inventory'}
          </button>
        </div>
      </div>
    </div>
  )
}
