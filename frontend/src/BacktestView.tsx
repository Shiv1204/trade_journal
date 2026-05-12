import { useEffect, useState } from 'react'
import { api, BacktestRun, BacktestDetail } from './api'

export default function BacktestView() {
  const [runs, setRuns] = useState<BacktestRun[]>([])
  const [selectedRun, setSelectedRun] = useState<BacktestDetail | null>(null)
  const [running, setRunning] = useState(false)
  const [scannerName, setScannerName] = useState('Monthly RSI Above 50')
  const [days, setDays] = useState(365)

  const loadRuns = () => {
    api.getBacktestRuns()
      .then(setRuns)
      .catch(console.error)
  }

  useEffect(() => { loadRuns() }, [])

  const handleRun = async () => {
    setRunning(true)
    try {
      await api.runBacktest(scannerName, days)
      setTimeout(loadRuns, 1000)
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
                    ${run.total_pnl?.toFixed(2)}
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
          <h3 className="text-lg font-semibold">
            Run Details - {selectedRun.summary.scanner_name}
          </h3>

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
                ${selectedRun.summary.total_pnl?.toFixed(2)}
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
                        ${m.pnl.toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-right">{m.win_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {selectedRun.trades.length > 0 && (
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Trades</h4>
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">Symbol</th>
                      <th className="text-left px-3 py-2 font-medium">Entry</th>
                      <th className="text-left px-3 py-2 font-medium">Exit</th>
                      <th className="text-right px-3 py-2 font-medium">P&L</th>
                      <th className="text-right px-3 py-2 font-medium">P&L %</th>
                      <th className="text-center px-3 py-2 font-medium">Exit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {selectedRun.trades.map((t, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-medium">{t.symbol}</td>
                        <td className="px-3 py-2 text-gray-500">{new Date(t.entry_date).toLocaleDateString()}</td>
                        <td className="px-3 py-2 text-gray-500">{new Date(t.exit_date).toLocaleDateString()}</td>
                        <td className={`px-3 py-2 text-right ${t.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          ${t.profit_loss.toFixed(2)}
                        </td>
                        <td className={`px-3 py-2 text-right ${t.pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {t.pnl_pct.toFixed(2)}%
                        </td>
                        <td className="px-3 py-2 text-center text-xs">{t.exit_reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
