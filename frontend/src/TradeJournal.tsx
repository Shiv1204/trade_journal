import { useEffect, useState } from 'react'
import { api, Trade } from './api'

export default function TradeJournal() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [filter, setFilter] = useState<string>('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadTrades()
  }, [filter])

  const loadTrades = () => {
    setLoading(true)
    const status = filter === 'all' ? undefined : filter
    api.getTrades(status)
      .then(setTrades)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  const totalPnl = trades.reduce((sum, t) => sum + (t.profit_loss ?? 0), 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Trade Journal</h2>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">
            Total P&L: <span className={`font-bold ${totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${totalPnl.toFixed(2)}
            </span>
          </span>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="border rounded-md px-3 py-1.5 text-sm"
          >
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
          </select>
          <button
            onClick={loadTrades}
            className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading trades...</div>
      ) : trades.length === 0 ? (
        <div className="text-center py-12 text-gray-500">No trades found</div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Symbol</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Entry</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Exit</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Qty</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Entry Price</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Exit Price</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">P&L</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">P&L %</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600">Exit Reason</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600">Scanner</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {trades.map((trade) => (
                <tr key={trade.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{trade.symbol}</td>
                  <td className="px-4 py-3 text-gray-500">{new Date(trade.entry_date).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {trade.exit_date ? new Date(trade.exit_date).toLocaleDateString() : '-'}
                  </td>
                  <td className="px-4 py-3 text-right">{trade.quantity}</td>
                  <td className="px-4 py-3 text-right">${trade.entry_price?.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right">{trade.exit_price ? `$${trade.exit_price.toFixed(2)}` : '-'}</td>
                  <td className={`px-4 py-3 text-right font-medium ${(trade.profit_loss ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ${trade.profit_loss?.toFixed(2) ?? '0.00'}
                  </td>
                  <td className={`px-4 py-3 text-right ${(trade.pnl_pct ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {trade.pnl_pct?.toFixed(2)}%
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      trade.status === 'open' ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'
                    }`}>
                      {trade.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center text-xs">{trade.exit_reason ?? '-'}</td>
                  <td className="px-4 py-3 text-center text-xs text-gray-500">{trade.scanner_name ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
