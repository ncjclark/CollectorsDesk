import { useState, useEffect } from 'react'
import { BrowserRouter, NavLink, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import Research from './pages/Research'
import Inventory from './pages/Inventory'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import './App.css'

function KeyboardShortcuts() {
  const navigate = useNavigate()
  useEffect(() => {
    const handler = (e) => {
      if (document.activeElement.tagName === 'INPUT' ||
          document.activeElement.tagName === 'TEXTAREA' ||
          document.activeElement.tagName === 'SELECT') return
      if (e.key === 'r') navigate('/research')
      if (e.key === 'i') navigate('/inventory')
      if (e.key === 'd') navigate('/dashboard')
      if (e.key === 's') navigate('/settings')
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [navigate])
  return null
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem('darkMode') !== 'false'  // default dark
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light')
    localStorage.setItem('darkMode', darkMode)
  }, [darkMode])

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'error', db: 'unreachable' }))
  }, [])

  return (
    <BrowserRouter>
      <KeyboardShortcuts />
      <div className="app-shell">
        <nav className="navbar">
          <div className="navbar-brand">
            <span className="brand-icon">🔍</span>
            <span className="brand-name">ResellResearch</span>
          </div>
          <div className="navbar-links">
            <NavLink to="/research" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Research
            </NavLink>
            <NavLink to="/inventory" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Inventory
            </NavLink>
            <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Dashboard
            </NavLink>
            <NavLink to="/settings" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Settings
            </NavLink>
          </div>
          <div className="navbar-status">
            <button
              className="dark-mode-toggle"
              onClick={() => setDarkMode(v => !v)}
              title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {darkMode ? '☀' : '🌙'}
            </button>
            {health && (
              <span
                className={`status-dot ${health.db === 'connected' ? 'ok' : 'err'}`}
                title={`DB: ${health.db} | eBay: ${health.ebay_configured ? '✓' : '✗ not configured'} | Etsy: ${health.etsy_configured ? '✓' : '✗ not configured'}`}
              >
                {health.db === 'connected' ? '● Connected' : '● DB Error'}
              </span>
            )}
          </div>
        </nav>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/research" replace />} />
            <Route path="/research" element={<Research />} />
            <Route path="/inventory" element={<Inventory />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
