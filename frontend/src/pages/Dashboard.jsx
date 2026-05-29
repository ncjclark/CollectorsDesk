import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, LineChart, Line
} from 'recharts'
import './Dashboard.css'

function fmt(val) {
  if (val == null || val === 0) return '$0'
  if (val >= 1000) return '$' + (val / 1000).toFixed(1) + 'k'
  return '$' + Number(val).toFixed(2)
}

function fmtDate(isoStr) {
  if (!isoStr) return 'Never'
  const d = new Date(isoStr)
  const days = Math.floor((Date.now() - d.getTime()) / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 30) return `${days}d ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const STATUS_COLORS = {
  not_listed: '#4a5180',
  listed: '#f5c542',
  sold: '#3ecf8e',
  hold: '#ff9800',
}

const COND_COLORS = ['#6c8ef5', '#3ecf8e', '#f5c542', '#ff9800', '#ef5350']

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <div className="tt-label">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="tt-val" style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' && p.name?.includes('$') ? fmt(p.value) : p.value}
        </div>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    fetch('/api/dashboard/stats')
      .then(r => r.json())
      .then(d => { setStats(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="page">
        <div className="page-header"><div><h1>Dashboard</h1></div></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-muted)' }}>
          <span className="spinner" /> Loading stats…
        </div>
      </div>
    )
  }

  if (!stats || stats.totals.items === 0) {
    return (
      <div className="page">
        <div className="page-header"><div>
          <h1>Dashboard</h1>
          <p>Collection value, progress, and items needing attention</p>
        </div></div>
        <div className="card empty-state">
          <h3>No inventory yet</h3>
          <p>Add items via the Inventory tab or import a CSV to see your dashboard stats.</p>
          <button className="btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/inventory')}>
            Go to Inventory →
          </button>
        </div>
      </div>
    )
  }

  const { totals, by_status, revenue, condition_breakdown,
          top_value_items, needs_research, category_breakdown, monthly_revenue } = stats

  const statusChartData = Object.entries(by_status).map(([k, v]) => ({
    name: { not_listed: 'Not Listed', listed: 'Listed', sold: 'Sold', hold: 'On Hold' }[k] || k,
    count: v,
    key: k,
  }))

  const condChartData = Object.entries(condition_breakdown).map(([k, v]) => ({
    name: k.charAt(0).toUpperCase() + k.slice(1),
    count: v,
  }))

  const researchPct = totals.items > 0
    ? Math.round(((totals.items - needs_research.length) / totals.items) * 100)
    : 0

  return (
    <div className="page dash-page">
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Collection overview as of today</p>
        </div>
        <button className="btn-secondary" onClick={() => window.location.reload()}>↻ Refresh</button>
      </div>

      {/* Stat cards */}
      <div className="stat-cards">
        <div className="stat-card">
          <div className="stat-label">Total Items</div>
          <div className="stat-value">{totals.items}</div>
          <div className="stat-sub">
            {totals.barbie} Barbie · {totals.board_games} Games
          </div>
        </div>
        <div className="stat-card stat-card-green">
          <div className="stat-label">Est. Collection Value</div>
          <div className="stat-value">{fmt(totals.estimated_value)}</div>
          <div className="stat-sub">Based on eBay avg prices</div>
        </div>
        <div className="stat-card stat-card-yellow">
          <div className="stat-label">Total Revenue</div>
          <div className="stat-value">{fmt(revenue.total_sold_price)}</div>
          <div className="stat-sub">{revenue.count_sold} items sold · avg {fmt(revenue.avg_sale_price)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Research Coverage</div>
          <div className="stat-value">{researchPct}%</div>
          <div className="stat-sub">
            {needs_research.length} item{needs_research.length !== 1 ? 's' : ''} need research
          </div>
          <div className="coverage-bar">
            <div className="coverage-fill" style={{ width: `${researchPct}%` }} />
          </div>
        </div>
      </div>

      {/* Charts row */}
      <div className="charts-row">
        <div className="card chart-card">
          <div className="chart-title">Items by Status</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={statusChartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {statusChartData.map((entry) => (
                  <Cell key={entry.key} fill={STATUS_COLORS[entry.key] || 'var(--accent)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card chart-card">
          <div className="chart-title">Items by Condition</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={condChartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {condChartData.map((_, i) => (
                  <Cell key={i} fill={COND_COLORS[i % COND_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {monthly_revenue?.length > 0 && (
          <div className="card chart-card">
            <div className="chart-title">Monthly Revenue</div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={monthly_revenue} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} />
                <Tooltip content={<CustomTooltip />} />
                <Line
                  type="monotone" dataKey="revenue" name="$Revenue"
                  stroke="var(--green)" strokeWidth={2} dot={{ r: 3, fill: 'var(--green)' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Top value items */}
      {top_value_items.length > 0 && (
        <div className="card dash-table-card">
          <div className="dash-table-title">Top 10 Most Valuable Items</div>
          <table className="dash-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Category</th>
                <th>Condition</th>
                <th>eBay Avg</th>
                <th>Your Price</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {top_value_items.map((item, i) => (
                <tr
                  key={item.id}
                  className="clickable-row"
                  onClick={() => navigate(`/inventory?select=${item.id}`)}
                >
                  <td className="rank-cell">{i + 1}</td>
                  <td className="item-name-cell"><div className="item-name">{item.name}</div></td>
                  <td>
                    {item.category && (
                      <span className={`tag tag-${item.category}`}>
                        {item.category === 'barbie' ? 'Barbie' : 'Board Game'}
                      </span>
                    )}
                  </td>
                  <td>
                    {item.condition && (
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        {item.condition.charAt(0).toUpperCase() + item.condition.slice(1)}
                      </span>
                    )}
                  </td>
                  <td className="price-cell green">{fmt(item.avg_sold_price)}</td>
                  <td className="price-cell">{fmt(item.my_asking_price)}</td>
                  <td>
                    <span className={`tag tag-${item.status}`}>
                      {item.status?.replace('_', ' ')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Needs research */}
      {needs_research.length > 0 && (
        <div className="card dash-table-card">
          <div className="dash-table-title">
            Needs Research
            <span className="dash-table-sub"> — {needs_research.length} item{needs_research.length !== 1 ? 's' : ''} never researched or stale (&gt;30 days)</span>
          </div>
          <table className="dash-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Category</th>
                <th>Status</th>
                <th>Last Researched</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {needs_research.map(item => (
                <tr key={item.id}>
                  <td><div className="item-name">{item.name}</div></td>
                  <td>
                    {item.category && (
                      <span className={`tag tag-${item.category}`}>
                        {item.category === 'barbie' ? 'Barbie' : 'Board Game'}
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={`tag tag-${item.status}`}>{item.status?.replace('_', ' ')}</span>
                  </td>
                  <td style={{ fontSize: 12, color: item.last_research_date ? 'var(--yellow)' : 'var(--red)' }}>
                    {fmtDate(item.last_research_date)}
                  </td>
                  <td>
                    <button
                      className="btn-ghost"
                      style={{ fontSize: 11 }}
                      onClick={() => navigate('/inventory')}
                    >
                      View →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
