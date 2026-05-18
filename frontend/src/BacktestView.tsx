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
  const [optimizing, setOptimizing] = useState(false)
  const [days, setDays] = useState(365)
  const [capital, setCapital] = useState(100000)
  const [slPct, setSlPct] = useState(3)
  const [targetPct, setTargetPct] = useState(6)
  const [maxHold, setMaxHold] = useState(10)
  const [showOpt, setShowOpt] = useState(false)

  const loadRuns = () => {
    api.getBacktestRuns()
      .then(setRuns)
      .catch(console.error)
  }

  useEffect(() => { loadRuns() }, [])

  const handleRun = async () => {
    setRunning(true)
    try {
      await api.runBacktest(days, capital, slPct, targetPct, maxHold)
      await new Promise(r => setTimeout(r, 5000))
      loadRuns()
    } catch (e) {
      console.error(e)
    }
    setRunning(false)
  }

  const handleOptimize = async () => {
    setOptimizing(true)
    try {
      await api.runOptimization(days, capital)
      await new Promise(r => setTimeout(r, 10000))
      loadRuns()
      setShowOpt(true)
    } catch (e) {
      console.error(e)
    }
    setOptimizing(false)
  }

  const handleSelect = async (id: number) => {
    try {
      const detail = await api.getBacktestDetail(id)
      setSelectedRun(detail)
    } catch (e) {
      console.error(e)
    }
  }

  const optRuns = runs.filter(r => r.scanner_name === 'Optimization').sort((a, b) => b.win_rate - a.win_rate)
  const normalRuns = runs.filter(r => r.scanner_name !== 'Optimization')

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Backtesting — Walk-Forward</h2>

      <div className="bg-white p-4 rounded-lg shadow flex gap-4 items-end flex-wrap">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Days</label>
          <input type="number" value={days} onChange={e => setDays(Number(e.target.value))}
            className="border rounded-md px-3 py-2 text-sm w-20" min={30} max={730} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Capital (₹)</label>
          <input type="number" value={capital} onChange={e => setCapital(Number(e.target.value))}
            className="border rounded-md px-3 py-2 text-sm w-28" min={1000} step={1000} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">SL %</label>
          <input type="number" value={slPct} onChange={e => setSlPct(Number(e.target.value))}
            className="border rounded-md px-3 py-2 text-sm w-16" min={1} max={10} step={0.5} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Target %</label>
          <input type="number" value={targetPct} onChange={e => setTargetPct(Number(e.target.value))}
            className="border rounded-md px-3 py-2 text-sm w-16" min={2} max={20} step={0.5} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Max Hold</label>
          <input type="number" value={maxHold} onChange={e => setMaxHold(Number(e.target.value))}
            className="border rounded-md px-3 py-2 text-sm w-16" min={3} max={30} />
        </div>
        <button onClick={handleRun} disabled={running}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm">
          {running ? 'Running...' : 'Run Backtest'}
        </button>
        <button onClick={handleOptimize} disabled={optimizing}
          className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 text-sm">
          {optimizing ? 'Optimizing...' : 'Optimize (Grid Search)'}
        </button>
      </div>

      {showOpt && optRuns.length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-4 py-3 border-b flex items-center justify-between">
            <h3 className="font-semibold text-purple-800">
              Optimization Results — Best Parameter Combinations
            </h3>
            <button onClick={() => setShowOpt(false)} className="text-gray-400 hover:text-gray-600 text-sm">Hide</button>
          </div>
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-gray-600">#</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-600">Params</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Trades</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Win Rate</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Total P&L</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Max DD</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Sharpe</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Avg Win</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Avg Loss</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {optRuns.map((r, i) => {
                  const params = `SL=${r.sl_pct}% TGT=${r.target_pct}% MAX=${r.max_hold_days}d`
                  const isBest = i === 0
                  return (
                    <tr key={r.id} className={`hover:bg-purple-50 ${isBest ? 'bg-green-50' : ''}`}>
                      <td className="px-3 py-2 text-xs text-gray-400">{i + 1}{isBest ? ' ★' : ''}</td>
                      <td className="px-3 py-2 font-mono text-xs">{params}</td>
                      <td className="px-3 py-2 text-right">{r.total_trades}</td>
                      <td className={`px-3 py-2 text-right font-bold ${r.win_rate >= 50 ? 'text-green-600' : 'text-red-600'}`}>
                        {r.win_rate}%
                      </td>
                      <td className={`px-3 py-2 text-right font-medium ${r.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        ₹{r.total_pnl.toFixed(0)}
                      </td>
                      <td className="px-3 py-2 text-right text-red-500">{r.max_drawdown}%</td>
                      <td className="px-3 py-2 text-right">{r.sharpe_ratio}</td>
                      <td className="px-3 py-2 text-right text-green-600">₹{r.avg_profit.toFixed(0)}</td>
                      <td className="px-3 py-2 text-right text-red-600">₹{r.avg_loss.toFixed(0)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {normalRuns.length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-4 py-3 border-b">
            <h3 className="font-semibold">Backtest Runs</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-600">Params</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Trades</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Win Rate</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Total P&L</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Max DD</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Sharpe</th>
                <th className="text-center px-4 py-2 font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {normalRuns.map(r => {
                const params = r.sl_pct != null
                  ? `SL=${r.sl_pct}% TGT=${r.target_pct}% MAX=${r.max_hold_days}d`
                  : r.scanner_name
                return (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-xs font-mono">{params}</td>
                    <td className="px-4 py-2 text-right">{r.total_trades}</td>
                    <td className={`px-4 py-2 text-right font-bold ${r.win_rate >= 50 ? 'text-green-600' : 'text-red-600'}`}>
                      {r.win_rate}%
                    </td>
                    <td className={`px-4 py-2 text-right font-medium ${r.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      ₹{r.total_pnl?.toFixed(0)}
                    </td>
                    <td className="px-4 py-2 text-right text-red-500">{r.max_drawdown}%</td>
                    <td className="px-4 py-2 text-right">{r.sharpe_ratio}</td>
                    <td className="px-4 py-2 text-center">
                      <button onClick={() => handleSelect(r.id)} className="text-blue-600 hover:text-blue-800 text-xs font-medium">
                        View
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {selectedRun && (
        <div className="bg-white rounded-lg shadow p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">
              Backtest Detail
              {selectedRun.summary.sl_pct != null && (
                <span className="ml-2 text-sm font-normal text-gray-500">
                  SL={selectedRun.summary.sl_pct}% TGT={selectedRun.summary.target_pct}% MAX={selectedRun.summary.max_hold_days}d
                </span>
              )}
            </h3>
            {selectedRun.scanner_identified_at && (
              <span className="text-xs text-gray-500">
                Scanner at: {new Date(selectedRun.scanner_identified_at).toLocaleString()}
              </span>
            )}
          </div>

          <div className="grid grid-cols-4 gap-4">
            <StatBox label="Total Trades" value={selectedRun.summary.total_trades} />
            <StatBox label="Win Rate" value={`${selectedRun.summary.win_rate}%`} color="text-green-600" />
            <StatBox label="Total P&L" value={`₹${selectedRun.summary.total_pnl?.toFixed(0)}`}
              color={selectedRun.summary.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'} />
            <StatBox label="Sharpe" value={selectedRun.summary.sharpe_ratio} />
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
                  {selectedRun.monthly_breakdown.map(m => (
                    <tr key={m.month} className="hover:bg-gray-50">
                      <td className="px-3 py-2">{m.month}</td>
                      <td className="px-3 py-2 text-right">{m.trades}</td>
                      <td className={`px-3 py-2 text-right ${m.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        ₹{m.pnl.toFixed(0)}
                      </td>
                      <td className="px-3 py-2 text-right">{m.win_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div>
            <h4 className="font-medium text-gray-700 mb-3">All Trades</h4>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">Symbol</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">Entry</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">Exit</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Entry ₹</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Exit ₹</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Qty</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Days</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">P&L</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">P&L %</th>
                    <th className="text-center px-3 py-2 font-medium text-gray-600">Result</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {selectedRun.trades.length === 0 ? (
                    <tr><td colSpan={10} className="px-4 py-4 text-center text-gray-400">No trades</td></tr>
                  ) : (
                    selectedRun.trades.map((t, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-medium">{t.symbol}</td>
                        <td className="px-3 py-2 text-gray-500 text-xs">{new Date(t.entry_date).toLocaleDateString()}</td>
                        <td className="px-3 py-2 text-gray-500 text-xs">{new Date(t.exit_date).toLocaleDateString()}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">₹{t.entry_price.toFixed(2)}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs">₹{t.exit_price.toFixed(2)}</td>
                        <td className="px-3 py-2 text-right">{t.quantity}</td>
                        <td className="px-3 py-2 text-right">{t.days_held ?? '-'}</td>
                        <td className={`px-3 py-2 text-right font-medium ${t.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          ₹{t.profit_loss.toFixed(0)}
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

function StatBox({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-lg font-bold ${color ?? ''}`}>{value}</div>
    </div>
  )
}
