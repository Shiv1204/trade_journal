import { useEffect, useState } from 'react'
import { api, TradeSummary } from './api'

export default function Dashboard() {
  const [summary, setSummary] = useState<TradeSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getTradeSummary()
      .then(setSummary)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Loading dashboard...</div>

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Trades" value={summary?.total_trades ?? 0} />
        <StatCard label="Win Rate" value={`${summary?.win_rate ?? 0}%`} color="text-green-600" />
        <StatCard label="Total P&L" value={`$${summary?.total_pnl?.toFixed(2) ?? '0.00'}`} color={summary?.total_pnl && summary.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'} />
        <StatCard label="Max Drawdown" value={`${summary?.max_drawdown?.toFixed(1) ?? 0}%`} color="text-red-600" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Winning Trades" value={summary?.winning_trades ?? 0} color="text-green-600" />
        <StatCard label="Losing Trades" value={summary?.losing_trades ?? 0} color="text-red-600" />
      </div>

      {summary && summary.equity_curve.length > 0 && (
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-3">Equity Curve</h3>
          <div className="h-48 flex items-end gap-1">
            {summary.equity_curve.map((point, i) => {
              const maxPnl = Math.max(...summary.equity_curve.map(p => p.pnl), 1)
              const minPnl = Math.min(...summary.equity_curve.map(p => p.pnl), 0)
              const range = maxPnl - minPnl || 1
              const height = ((point.pnl - minPnl) / range) * 100
              return (
                <div
                  key={i}
                  className="flex-1 bg-blue-500 rounded-t transition-all hover:bg-blue-600 relative group"
                  style={{ height: `${Math.max(height, 2)}%` }}
                  title={`${point.date}: $${point.pnl.toFixed(2)}`}
                />
              )
            })}
          </div>
        </div>
      )}

      <div className="bg-white p-4 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-2">Quick Actions</h3>
        <div className="flex gap-3">
          <button
            onClick={() => api.runScanner().catch(console.error)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
          >
            Run Scanner
          </button>
          <button
            onClick={() => api.checkPositions().catch(console.error)}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
          >
            Check Positions
          </button>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-white p-4 rounded-lg shadow">
      <div className="text-sm text-gray-500">{label}</div>
      <div className={`text-2xl font-bold ${color ?? 'text-gray-900'}`}>{value}</div>
    </div>
  )
}
