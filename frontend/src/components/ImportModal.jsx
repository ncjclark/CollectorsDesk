import { useState, useRef } from 'react'
import './ImportModal.css'

export default function ImportModal({ onClose, onImported }) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)   // array of row objects
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  function handleFile(f) {
    if (!f) return
    if (!f.name.endsWith('.csv')) {
      setError('Please select a .csv file.')
      return
    }
    setFile(f)
    setError(null)
    setResult(null)

    // Parse locally for preview
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target.result
      const lines = text.split('\n').filter(l => l.trim())
      if (lines.length < 2) { setPreview([]); return }
      const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
      const rows = lines.slice(1, 11).map(line => {
        const vals = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''))
        return Object.fromEntries(headers.map((h, i) => [h, vals[i] || '']))
      })
      setPreview({ headers, rows, total: lines.length - 1 })
    }
    reader.readAsText(f)
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  async function handleImport() {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch('/api/import/csv', { method: 'POST', body: form })
      if (!resp.ok) throw new Error('Import failed')
      const data = await resp.json()
      setResult(data)
      onImported(data.imported)
    } catch (e) {
      setError('Import failed. Check your CSV format and try again.')
    } finally {
      setUploading(false)
    }
  }

  async function downloadTemplate() {
    const resp = await fetch('/api/import/template')
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'inventory_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="import-box">
        <div className="modal-header">
          <h2>Import from CSV</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="import-body">
          {!result ? (
            <>
              <div className="import-top">
                <p className="import-hint">
                  Import a spreadsheet of items. Use our template for the correct column format.
                </p>
                <button className="btn-secondary template-btn" onClick={downloadTemplate}>
                  ↓ Download Template
                </button>
              </div>

              {!file ? (
                <div
                  className={`drop-zone ${dragging ? 'dragging' : ''}`}
                  onDragOver={e => { e.preventDefault(); setDragging(true) }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={onDrop}
                  onClick={() => inputRef.current?.click()}
                >
                  <div className="drop-icon">📄</div>
                  <div className="drop-text">Drop your CSV here or click to browse</div>
                  <div className="drop-sub">name, category, year, condition, quantity, notes…</div>
                  <input
                    ref={inputRef}
                    type="file"
                    accept=".csv"
                    style={{ display: 'none' }}
                    onChange={e => handleFile(e.target.files[0])}
                  />
                </div>
              ) : (
                <div className="file-selected">
                  <span className="file-icon">📄</span>
                  <span className="file-name">{file.name}</span>
                  <button className="btn-ghost" onClick={() => { setFile(null); setPreview(null) }} style={{fontSize:11}}>
                    Change
                  </button>
                </div>
              )}

              {preview && preview.rows?.length > 0 && (
                <div className="preview-section">
                  <div className="preview-header">
                    Preview — {preview.total} item{preview.total !== 1 ? 's' : ''} in file
                    {preview.total > 10 && ' (showing first 10)'}
                  </div>
                  <div className="preview-table-wrap">
                    <table className="preview-table">
                      <thead>
                        <tr>
                          {preview.headers.slice(0, 6).map(h => <th key={h}>{h}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {preview.rows.map((row, i) => (
                          <tr key={i}>
                            {preview.headers.slice(0, 6).map(h => (
                              <td key={h} title={row[h]}>{row[h] || '—'}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {error && <div className="modal-error">{error}</div>}
            </>
          ) : (
            <div className="import-result">
              <div className="result-success">
                <span className="result-icon">✓</span>
                <div>
                  <div className="result-count">{result.imported} items imported</div>
                  {result.skipped?.length > 0 && (
                    <div className="result-skipped">{result.skipped.length} rows skipped</div>
                  )}
                </div>
              </div>

              {result.skipped?.length > 0 && (
                <div className="skipped-list">
                  <div className="skipped-header">Skipped rows:</div>
                  {result.skipped.map((s, i) => (
                    <div key={i} className="skipped-row">
                      <span className="skipped-row-num">Row {s.row}</span>
                      <span className="skipped-reason">{s.reason}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          {!result ? (
            <>
              <button className="btn-secondary" onClick={onClose}>Cancel</button>
              <button
                className="btn-primary"
                onClick={handleImport}
                disabled={!file || uploading}
              >
                {uploading
                  ? <><span className="spinner" style={{width:14,height:14}} /> Importing…</>
                  : `Import ${preview?.total ? preview.total + ' items' : ''}`}
              </button>
            </>
          ) : (
            <button className="btn-primary" onClick={onClose}>Done</button>
          )}
        </div>
      </div>
    </div>
  )
}
