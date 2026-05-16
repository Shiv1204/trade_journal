import { useEffect, useState } from 'react'
import { api, BacktestRun, BacktestDetail } from './api'

function exitBadge(reason: string | null) {
  if (!reason) return <span className="text-gray-400">-</span>
  if (reason === 'sl') return <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">SL Hit</span>
  if (reason === 'target') return <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">TGT Achieved</span>
  if (reason === 'time') return <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-700">Force Exit</span>
  return <span className="text-xs">{reason}</span>
}

export default function BacktestView() {
  const [runs, setRuns] = useState<BacktestRun[]>([])
  const [selectedRun, setSelectedRun] = useState<BacktestDetail | null>(null)
  const [running, setRunning] = useState(false)
  const [scannerName, setScannerName] = useState('Monthly RSI Above 50')
  const [days, setDays] = useState(365)
  const [capital, setCapital] = useState(100000)

  const loadRuns = () => {
    api.getBacktestRuns()
      .then(setRuns)
      .catch(console.error)
  }

  useEffect(() => { loadRuns() }, [])

  const handleRun = async () => {
    setRunning(true)
    try {
      await api.runBacktest(scannerName, days, capital)
      await new Promise(r => setTimeout(r, 3000))
      loadRuns()
    } catch (e) {
      console.error(e)
    }
    setRunning(false)
  }

  const handleSelect = async (id: number) => {
    try {
      const detail = await api.getBacktestDetail(id)
      setSelectedRun(detail)
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Backtesting</h2>

      <div className="bg-white p-4 rounded-lg shadow flex gap-4 items-end">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Scanner</label>
          <select
            value={scannerName}
            onChange={(e) => setScannerName(e.target.value)}
            className="border rounded-md px-3 py-2 text-sm"
          >
            <option value="Monthly RSI Above 50">Monthly RSI Above 50</option>
            <option value="Top Scanner Combo">Top Scanner Combo</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Days</label>
          <input
            type="number"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="border rounded-md px-3 py-2 text-sm w-24"
            min={30}
            max={730}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Capital Per Trade (Rs.)</label>
          <input
            type="number"
            value={capital}
            onChange={(e) => setCapital(Number(e.target.value))}
            className="border rounded-md px-3 py-2 text-sm w-32"
            min={1000}
            step={1000}
          />
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {running ? 'Running...' : 'Run Backtest'}
        </button>
      </div>

      {runs.length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-4 py-3 border-b">
            <h3 className="font-semibold">Previous Backtest Runs</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-600">Scanner</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600">Period</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Trades</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Win Rate</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Total P&L</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Max DD</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Sharpe</th>
                <th className="text-center px-4 py-2 font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {runs.map((run) => (
                <tr key={run.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2">{run.scanner_name}</td>
                  <td className="px-4 py-2 text-gray-500">
                    {new Date(run.start_date).toLocaleDateString()} - {new Date(run.end_date).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 text-right">{run.total_trades}</td>
                  <td className="px-4 py-2 text-right font-medium">{run.win_rate}%</td>
                  <td className={`px-4 py-2 text-right font-medium ${run.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ₹{run.total_pnl?.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right text-red-600">{run.max_drawdown}%</td>
                  <td className="px-4 py-2 text-right">{run.sharpe_ratio}</td>
                  <td className="px-4 py-2 text-center">
                    <button
                      onClick={() => handleSelect(run.id)}
                      className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedRun && (
        <div className="bg-white rounded-lg shadow p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">
              Run Details - {selectedRun.summary.scanner_name}
            </h3>
            {selectedRun.scanner_identified_at && (
              <span className="text-xs text-gray-500">
                Duplicates identified: {new Date(selectedRun.scanner_identified_at).toLocaleString()}
              </span>
            )}
          </div>

          <div className="grid grid-cols-4 gap-4">
            <div>
              <div className="text-xs text-gray-500">Total Trades</div>
              <div className="text-lg font-bold">{selectedRun.summary.total_trades}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Win Rate</div>
              <div className="text-lg font-bold text-green-600">{selectedRun.summary.win_rate}%</div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Total P&L</div>
              <div className={`text-lg font-bold ${selectedRun.summary.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ₹{selectedRun.summary.total_pnl?.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500">Sharpe Ratio</div>
              <div className="text-lg font-bold">{selectedRun.summary.sharpe_ratio}</div>
            </div>
          </div>

          {selectedRun.monthly_breakdown.length > 0 && (
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Monthly Breakdown</h4>
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Month</th>
                    <th className="text-right px-3 py-2 font-medium">Trades</th>
                    <th className="text-right px-3 py-2 font-medium">P&L</th>
                    <th className="text-right px-3 py-2 font-medium">Win Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {selectedRun.monthly_breakdown.map((m) => (
                    <tr key={m.month} className="hover:bg-gray-50">
                      <td className="px-3 py-2">{m.month}</td>
                      <td className="px-3 py-2 text-right">{m.trades}</td>
                      <td className={`px-3 py-2 text-right ${m.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        ₹{m.pnl.toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-right">{m.win_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div>
            <h4 className="font-medium text-gray-700 mb-3">Backtest Trades</h4>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">Symbol</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">Entry Date</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Entry Price</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">Exit Date</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Exit Price</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Days</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">P&L</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">P&L %</th>
                    <th className="text-center px-3 py-2 font-medium text-gray-600">Result</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {selectedRun.trades.length === 0 ? (
                    <tr><td colSpan={9} className="px-4 py-4 text-center text-gray-400">No trades generated</td></tr>
                  ) : (
                    selectedRun.trades.map((t, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-medium">{t.symbol}</td>
                        <td className="px-3 py-2 text-gray-500 text-xs">
                          {new Date(t.entry_date).toLocaleString()}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-xs">₹{t.entry_price.toFixed(2)}</td>
                        <td className="px-3 py-2 text-gray-500 text-xs">
                          {new Date(t.exit_date).toLocaleString()}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-xs">₹{t.exit_price.toFixed(2)}</td>
                        <td className="px-3 py-2 text-right">{t.days_held ?? '-'}</td>
                        <td className={`px-3 py-2 text-right font-medium ${t.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          ₹{t.profit_loss.toFixed(2)}
                        </td>
                        <td className={`px-3 py-2 text-right ${t.pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {t.pnl_pct.toFixed(2)}%
                        </td>
                        <td className="px-3 py-2 text-center">{exitBadge(t.exit_reason)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
