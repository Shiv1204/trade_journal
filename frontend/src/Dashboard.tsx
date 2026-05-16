import { useEffect, useState } from 'react'
import { api, TradeSummary, KiteHoldingsResponse, SyncResponse } from './api'

export default function Dashboard({ kiteConnected }: { kiteConnected: boolean }) {
  const [summary, setSummary] = useState<TradeSummary | null>(null)
  const [holdings, setHoldings] = useState<KiteHoldingsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<SyncResponse | null>(null)

  useEffect(() => {
    api.getTradeSummary()
      .then(setSummary)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (kiteConnected) {
      api.getKiteHoldings()
        .then(setHoldings)
        .catch(console.error)
    } else {
      setHoldings(null)
    }
  }, [kiteConnected])

  const handleSync = async () => {
    setSyncing(true)
    setSyncResult(null)
    try {
      const result = await api.syncKitePositions()
      setSyncResult(result)
      api.getTradeSummary().then(setSummary).catch(console.error)
      api.getKiteHoldings().then(setHoldings).catch(console.error)
    } catch (e: any) {
      console.error(e)
    }
    setSyncing(false)
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading dashboard...</div>

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Trades" value={summary?.total_trades ?? 0} />
        <StatCard label="Win Rate" value={`${summary?.win_rate ?? 0}%`} color="text-green-600" />
        <StatCard label="Total P&L" value={`₹${summary?.total_pnl?.toFixed(2) ?? '0.00'}`} color={summary?.total_pnl && summary.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'} />
        <StatCard label="Max Drawdown" value={`${summary?.max_drawdown?.toFixed(1) ?? 0}%`} color="text-red-600" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Winning Trades" value={summary?.winning_trades ?? 0} color="text-green-600" />
        <StatCard label="Losing Trades" value={summary?.losing_trades ?? 0} color="text-red-600" />
      </div>

      {holdings && (
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-3">Kite Holdings</h3>
          <div className="flex items-center gap-4 mb-3">
            <span className="text-sm text-gray-500">
              {holdings.count} holdings &middot; {holdings.tracked_count} tracked &middot; {holdings.untracked_count} untracked
            </span>
            {holdings.untracked_count > 0 && (
              <button
                onClick={handleSync}
                disabled={syncing}
                className="px-3 py-1.5 bg-orange-500 text-white rounded-md text-sm hover:bg-orange-600 disabled:opacity-50"
              >
                {syncing ? 'Syncing...' : `Sync ${holdings.untracked_count} Positions`}
              </button>
            )}
          </div>
          {syncResult && (
            <div className={`text-sm p-2 rounded mb-3 ${syncResult.imported > 0 ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-600'}`}>
              Imported {syncResult.imported} positions, placed {syncResult.sl_orders_placed} SL orders.
              {syncResult.errors.length > 0 && ` (${syncResult.errors.length} errors)`}
            </div>
          )}
          <div className="max-h-48 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-gray-600">Symbol</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Qty</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Avg Price</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">LTP</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">P&L</th>
                  <th className="text-center px-3 py-2 font-medium text-gray-600">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {holdings.holdings.map((h, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium">{h.symbol}</td>
                    <td className="px-3 py-2 text-right">{h.quantity}</td>
                    <td className="px-3 py-2 text-right font-mono text-xs">₹{h.avg_price.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right font-mono text-xs">₹{h.last_price.toFixed(2)}</td>
                    <td className={`px-3 py-2 text-right font-medium ${h.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      ₹{h.pnl.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {h.tracked ? (
                        <span className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-700">Tracked</span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-xs bg-orange-100 text-orange-700">Untracked</span>
                      )}
                    </td>
                  </tr>
                ))}
                {holdings.holdings.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-4 text-center text-gray-400">No holdings in Kite</td>
                  </tr>
                )}
              </tbody>
            </table>
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
