import { useState, useEffect } from 'react'
import './Settings.css'

const GROUP_ICONS = {
  'eBay API': '🛒',
  'AI (Photo Identification)': '🤖',
  'Additional Data Sources': '📊',
  'App Settings': '⚙️',
}

function FieldRow({ field, onSave }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const [showValue, setShowValue] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const displayValue = field.sensitive
    ? (showValue ? value || field.masked_value : field.masked_value)
    : (field.value ?? '')

  function startEdit() {
    // For option fields, default to first option if current value is blank
    const current = field.value ?? ''
    setValue(current || (field.options?.[0] ?? ''))
    setEditing(true)
    setSaved(false)
  }

  function cancel() {
    setEditing(false)
    setValue('')
    setSaved(false)
  }

  async function save() {
    setSaving(true)
    try {
      await onSave(field.key, value)
      setSaved(true)
      setEditing(false)
      setValue('')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={`field-row ${field.is_set ? 'field-set' : 'field-unset'}`}>
      <div className="field-meta">
        <div className="field-header">
          <span className="field-label">{field.label}</span>
          <span className={`field-status ${field.is_set ? 'status-set' : 'status-missing'}`}>
            {field.is_set ? '✓ Set' : '! Missing'}
          </span>
        </div>
        <p className="field-description">{field.description}</p>
        {field.setup_url && !field.is_set && (
          <a className="field-setup-link" href={field.setup_url} target="_blank" rel="noreferrer">
            Get API key →
          </a>
        )}
      </div>

      <div className="field-control">
        {editing ? (
          <div className="field-edit-row">
            {field.options ? (
              <select
                className="field-input"
                value={value}
                onChange={e => setValue(e.target.value)}
              >
                {field.options.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            ) : (
              <input
                className="field-input"
                type={field.sensitive && !showValue ? 'password' : 'text'}
                value={value}
                onChange={e => setValue(e.target.value)}
                placeholder={field.sensitive ? 'Paste new value…' : 'Enter value…'}
                autoFocus
                onKeyDown={e => {
                  if (e.key === 'Enter') save()
                  if (e.key === 'Escape') cancel()
                }}
              />
            )}
            <div className="field-edit-actions">
              <button className="btn btn-primary btn-sm" onClick={save} disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
              <button className="btn btn-sm" onClick={cancel}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="field-view-row">
            <span className="field-current-value">
              {field.is_set
                ? (field.sensitive ? (showValue ? field.masked_value : field.masked_value) : displayValue)
                : <span className="field-empty">Not set</span>
              }
            </span>
            <div className="field-view-actions">
              {field.sensitive && field.is_set && (
                <button className="btn btn-sm" onClick={() => setShowValue(v => !v)} title="Toggle visibility">
                  {showValue ? '🙈' : '👁'}
                </button>
              )}
              {saved && <span className="saved-flash">✓ Saved</span>}
              <button className="btn btn-sm" onClick={startEdit}>
                {field.is_set ? 'Update' : 'Set'}
              </button>
              {field.is_set && (
                <button
                  className="btn btn-sm btn-danger"
                  onClick={async () => {
                    if (confirm(`Clear ${field.label}?`)) {
                      setSaving(true)
                      try { await onSave(field.key, '') } finally { setSaving(false) }
                    }
                  }}
                  title="Clear this value"
                >
                  ✕
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Settings() {
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)

  async function load() {
    try {
      const r = await fetch('/api/config')
      if (!r.ok) throw new Error(await r.text())
      const data = await r.json()
      setGroups(data.groups)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function showToast(msg, type = 'success') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  async function handleSave(key, value) {
    const r = await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ updates: { [key]: value } }),
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }))
      showToast(err.detail || 'Save failed', 'error')
      throw new Error(err.detail)
    }
    showToast(value ? `${key} updated — live immediately` : `${key} cleared`)
    await load()
  }

  if (loading) return <div className="settings-loading">Loading config…</div>
  if (error) return <div className="settings-error">Error: {error}</div>

  const allSet = groups.flatMap(g => g.fields).filter(f => f.is_set).length
  const allTotal = groups.flatMap(g => g.fields).length

  return (
    <div className="settings-page">
      {toast && (
        <div className={`settings-toast ${toast.type}`}>
          {toast.msg}
        </div>
      )}

      <div className="settings-header">
        <div>
          <h1 className="settings-title">Settings</h1>
          <p className="settings-subtitle">
            API keys and preferences. Changes apply instantly — no restart needed.
          </p>
        </div>
        <div className="settings-status-summary">
          <span className={`config-progress ${allSet === allTotal ? 'all-set' : allSet > 0 ? 'partial' : 'none-set'}`}>
            {allSet}/{allTotal} configured
          </span>
        </div>
      </div>

      <div className="settings-groups">
        {groups.map(group => (
          <div key={group.name} className="settings-group">
            <div className="group-header">
              <span className="group-icon">{GROUP_ICONS[group.name] ?? '🔧'}</span>
              <span className="group-name">{group.name}</span>
              <span className="group-count">
                {group.fields.filter(f => f.is_set).length}/{group.fields.length}
              </span>
            </div>
            <div className="group-fields">
              {group.fields.map(field => (
                <FieldRow key={field.key} field={field} onSave={handleSave} />
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="settings-footer">
        <p>Changes are written to <code>.env</code> and applied live to the running server.</p>
      </div>
    </div>
  )
}
