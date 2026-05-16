import { useEffect, useState } from 'react'
import { api, ScannerData, DedupEntry } from './api'

function rsiColor(val: number | null): string {
  if (val == null) return 'text-gray-400'
  if (val >= 70) return 'text-red-600'
  if (val >= 50) return 'text-green-600'
  return 'text-orange-500'
}

function formatVolume(v: number | null): string {
  if (v == null) return '-'
  if (v >= 10000000) return (v / 10000000).toFixed(1) + 'Cr'
  if (v >= 100000) return (v / 100000).toFixed(1) + 'L'
  if (v >= 1000) return (v / 1000).toFixed(1) + 'K'
  return v.toString()
}

export default function ScannerView({ kiteConnected, onConnectKite }: { kiteConnected: boolean; onConnectKite: () => void }) {
  const [data, setData] = useState<ScannerData | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [tradeModal, setTradeModal] = useState<{ open: boolean; entry: DedupEntry | null }>({ open: false, entry: null })
  const [tradeCapital, setTradeCapital] = useState(100000)
  const [executing, setExecuting] = useState(false)
  const [tradeResult, setTradeResult] = useState<string | null>(null)
  const [availableFunds, setAvailableFunds] = useState<number | null>(null)

  const load = () => {
    setLoading(true)
    api.getLatestScanner()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const handleRun = async () => {
    setRunning(true)
    try {
      await api.runScanner()
      await new Promise(r => setTimeout(r, 15000))
      await load()
    } catch (e) {
      console.error(e)
    }
    setRunning(false)
  }

  const fetchFunds = async () => {
    try {
      const m = await api.getKiteMargins()
      setAvailableFunds(m.available_cash ?? 0)
    } catch {
      setAvailableFunds(null)
    }
  }

  const openTradeModal = async (entry: DedupEntry) => {
    if (!kiteConnected) {
      onConnectKite()
      return
    }
    setTradeResult(null)
    setTradeModal({ open: true, entry })
    await fetchFunds()
  }

  const price = tradeModal.entry?.price_1 || tradeModal.entry?.price_2 || 0
  const tradeQty = price > 0 ? Math.max(1, Math.floor(tradeCapital / price)) : 1
  const totalCapital = price * tradeQty

  const handleExecuteTrade = async () => {
    if (!tradeModal.entry) return
    const entry = tradeModal.entry
    const p = entry.price_1 || entry.price_2 || 0
    if (p <= 0) return

    if (availableFunds !== null && totalCapital > availableFunds) {
      setTradeResult(`Insufficient funds. Required: ₹${totalCapital.toFixed(2)}, Available: ₹${availableFunds.toFixed(2)}`)
      return
    }

    setExecuting(true)
    try {
      const resp = await api.executeTrade({
        symbol: entry.symbol,
        price: p,
        capital_per_trade: tradeCapital,
        scanner_name: data?.scanner_1?.name || '',
      })
      setTradeResult(`Trade #${resp.trade_id} opened — ${resp.symbol} x${resp.quantity} @ ₹${resp.entry_price}`)
      setTimeout(() => {
        setTradeModal({ open: false, entry: null })
        setTradeResult(null)
      }, 3000)
    } catch (e: any) {
      setTradeResult(`Error: ${e.message}`)
    }
    setExecuting(false)
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Loading scanner data...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Scanner Comparison</h2>
        <div className="flex items-center gap-3">
          {kiteConnected ? (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium">
              Kite Connected
            </span>
          ) : (
            <button onClick={onConnectKite} className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded-full font-medium hover:bg-red-200">
              Connect Kite
            </button>
          )}
          <button
            onClick={handleRun}
            disabled={running}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            {running ? 'Running Scanners...' : 'Run Scanners'}
          </button>
        </div>
      </div>

      {!data || (data.scanner_1.count === 0 && data.scanner_2.count === 0) ? (
        <div className="text-center py-12 text-gray-500">
          No scanner data yet. Click "Run Scanners" to fetch results.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <div className="text-sm text-gray-500">{data.scanner_1.name}</div>
              <div className="text-2xl font-bold text-blue-600">{data.scanner_1.count}</div>
              <div className="text-xs text-gray-400">stocks found</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <div className="text-sm text-gray-500">{data.scanner_2.name}</div>
              <div className="text-2xl font-bold text-purple-600">{data.scanner_2.count}</div>
              <div className="text-xs text-gray-400">stocks found</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <div className="text-sm text-gray-500">Common (Duplicates)</div>
              <div className="text-2xl font-bold text-green-600">{data.dedup.count_both}</div>
              <div className="text-xs text-gray-400">in both scanners</div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow">
              <div className="px-4 py-3 border-b bg-blue-50">
                <h3 className="font-semibold text-blue-800">
                  Scanner 1: {data.scanner_1.name}
                  <span className="ml-2 text-sm font-normal text-blue-600">({data.scanner_1.count} stocks)</span>
                </h3>
              </div>
              <div className="max-h-96 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">#</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Symbol</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600">Price</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600">Chg%</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600">Volume</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600">Daily RSI</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600">Weekly RSI</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {data.scanner_1.results.length === 0 ? (
                      <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No results</td></tr>
                    ) : (
                      data.scanner_1.results.map((r, i) => (
                        <tr key={`s1-${r.symbol}-${i}`} className="hover:bg-blue-50">
                          <td className="px-3 py-1.5 text-gray-400 text-xs">{i + 1}</td>
                          <td className="px-3 py-1.5 font-medium">{r.symbol}</td>
                          <td className="px-3 py-1.5 text-right font-mono">{r.price != null ? `₹${r.price.toFixed(2)}` : '-'}</td>
                          <td className={`px-3 py-1.5 text-right ${(r.change_pct ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>{r.change_pct != null ? `${r.change_pct.toFixed(2)}%` : '-'}</td>
                          <td className="px-3 py-1.5 text-right text-gray-500">{formatVolume(r.volume)}</td>
                          <td className={`px-3 py-1.5 text-right font-medium ${rsiColor(r.daily_rsi)}`}>{r.daily_rsi != null ? r.daily_rsi.toFixed(1) : '-'}</td>
                          <td className={`px-3 py-1.5 text-right font-medium ${rsiColor(r.weekly_rsi)}`}>{r.weekly_rsi != null ? r.weekly_rsi.toFixed(1) : '-'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow">
              <div className="px-4 py-3 border-b bg-purple-50">
                <h3 className="font-semibold text-purple-800">
                  Scanner 2: {data.scanner_2.name}
                  <span className="ml-2 text-sm font-normal text-purple-600">({data.scanner_2.count} stocks)</span>
                </h3>
              </div>
              <div className="max-h-96 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">#</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Symbol</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600">Price</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600">Chg%</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600">Volume</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600">Daily RSI</th>
                      <th className="text-right px-3 py-2 font-medium text-gray-600">Weekly RSI</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {data.scanner_2.results.length === 0 ? (
                      <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No results</td></tr>
                    ) : (
                      data.scanner_2.results.map((r, i) => (
                        <tr key={`s2-${r.symbol}-${i}`} className="hover:bg-purple-50">
                          <td className="px-3 py-1.5 text-gray-400 text-xs">{i + 1}</td>
                          <td className="px-3 py-1.5 font-medium">{r.symbol}</td>
                          <td className="px-3 py-1.5 text-right font-mono">{r.price != null ? `₹${r.price.toFixed(2)}` : '-'}</td>
                          <td className={`px-3 py-1.5 text-right ${(r.change_pct ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>{r.change_pct != null ? `${r.change_pct.toFixed(2)}%` : '-'}</td>
                          <td className="px-3 py-1.5 text-right text-gray-500">{formatVolume(r.volume)}</td>
                          <td className={`px-3 py-1.5 text-right font-medium ${rsiColor(r.daily_rsi)}`}>{r.daily_rsi != null ? r.daily_rsi.toFixed(1) : '-'}</td>
                          <td className={`px-3 py-1.5 text-right font-medium ${rsiColor(r.weekly_rsi)}`}>{r.weekly_rsi != null ? r.weekly_rsi.toFixed(1) : '-'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow">
            <div className="px-4 py-3 border-b bg-green-50">
              <h3 className="font-semibold text-green-800">
                Duplicate Results (Present in Both Scanners)
                <span className="ml-2 text-sm font-normal text-green-600">({data.dedup.count_both} stocks)</span>
              </h3>
            </div>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="text-left px-2 py-2 font-medium text-gray-600">#</th>
                    <th className="text-left px-2 py-2 font-medium text-gray-600">Symbol</th>
                    <th className="text-right px-2 py-2 font-medium text-gray-600">Price S1</th>
                    <th className="text-right px-2 py-2 font-medium text-gray-600">Price S2</th>
                    <th className="text-right px-2 py-2 font-medium text-gray-600">Daily RSI</th>
                    <th className="text-right px-2 py-2 font-medium text-gray-600">Weekly RSI</th>
                    <th className="text-center px-2 py-2 font-medium text-gray-600">Score</th>
                    <th className="text-center px-2 py-2 font-medium text-gray-600">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.dedup.trade_entries.length === 0 ? (
                    <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No duplicates found</td></tr>
                  ) : (
                    data.dedup.trade_entries.map((entry, i) => (
                      <tr key={`dup-${entry.symbol}`} className="hover:bg-green-50">
                        <td className="px-2 py-1.5 text-gray-400 text-xs">{i + 1}</td>
                        <td className="px-2 py-1.5 font-medium">{entry.symbol}</td>
                        <td className="px-2 py-1.5 text-right font-mono">{entry.price_1 != null ? `₹${entry.price_1.toFixed(2)}` : '-'}</td>
                        <td className="px-2 py-1.5 text-right font-mono">{entry.price_2 != null ? `₹${entry.price_2.toFixed(2)}` : '-'}</td>
                        <td className="px-2 py-1.5 text-right">
                          <span className={rsiColor(entry.daily_rsi_1)}>{entry.daily_rsi_1 != null ? entry.daily_rsi_1.toFixed(1) : '-'}</span>
                          {' / '}
                          <span className={rsiColor(entry.daily_rsi_2)}>{entry.daily_rsi_2 != null ? entry.daily_rsi_2.toFixed(1) : '-'}</span>
                        </td>
                        <td className="px-2 py-1.5 text-right">
                          <span className={rsiColor(entry.weekly_rsi_1)}>{entry.weekly_rsi_1 != null ? entry.weekly_rsi_1.toFixed(1) : '-'}</span>
                          {' / '}
                          <span className={rsiColor(entry.weekly_rsi_2)}>{entry.weekly_rsi_2 != null ? entry.weekly_rsi_2.toFixed(1) : '-'}</span>
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                            entry.grade === 'A' ? 'bg-green-100 text-green-700' :
                            entry.grade === 'B' ? 'bg-blue-100 text-blue-700' :
                            entry.grade === 'C' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-gray-100 text-gray-600'
                          }`} title={entry.reasons?.join(', ') || ''}>
                            {entry.grade} ({entry.score})
                          </span>
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <button
                            onClick={() => openTradeModal(entry)}
                            className={`px-2 py-1 rounded text-xs font-medium ${
                              kiteConnected
                                ? 'bg-green-600 text-white hover:bg-green-700'
                                : 'bg-gray-300 text-gray-600'
                            }`}
                          >
                            Trade
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tradeModal.open && tradeModal.entry && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setTradeModal({ open: false, entry: null })}>
          <div className="bg-white rounded-lg shadow-xl w-96 p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900">Execute Trade</h3>
              <button onClick={() => setTradeModal({ open: false, entry: null })} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
            </div>

            {tradeResult ? (
              <div className={`text-sm p-3 rounded ${tradeResult.startsWith('Trade') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                {tradeResult}
              </div>
            ) : (
              <>
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Symbol</span>
                    <span className="font-bold text-gray-900">{tradeModal.entry.symbol}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Price</span>
                    <span className="font-mono">₹{(tradeModal.entry.price_1 || tradeModal.entry.price_2 || 0).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm items-center">
                    <span className="text-gray-500">Capital</span>
                    <input
                      type="number"
                      value={tradeCapital}
                      min={1000}
                      step={1000}
                      onChange={(e) => setTradeCapital(Math.max(1000, parseInt(e.target.value) || 1000))}
                      className="w-28 border rounded px-2 py-1 text-right text-sm"
                    />
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Quantity</span>
                    <span className="font-mono">{tradeQty} shares</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Total</span>
                    <span className="font-mono">₹{totalCapital.toFixed(2)}</span>
                  </div>
                  {availableFunds !== null && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Available Funds</span>
                      <span className={`font-mono ${availableFunds >= totalCapital ? 'text-green-600' : 'text-red-600'}`}>
                        ₹{availableFunds.toFixed(2)}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Product</span>
                    <span>CNC</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Exchange</span>
                    <span>NSE</span>
                  </div>
                  <hr />
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">SL @ -3%</span>
                    <span className="text-red-600 font-mono">₹{((tradeModal.entry.price_1 || tradeModal.entry.price_2 || 0) * 0.97).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Target @ +6%</span>
                    <span className="text-green-600 font-mono">₹{((tradeModal.entry.price_1 || tradeModal.entry.price_2 || 0) * 1.06).toFixed(2)}</span>
                  </div>
                </div>

                <div className="flex gap-2 pt-2">
                  <button onClick={() => setTradeModal({ open: false, entry: null })} className="flex-1 px-3 py-2 border rounded-md text-sm text-gray-600 hover:bg-gray-50">
                    Cancel
                  </button>
                  <button
                    onClick={handleExecuteTrade}
                    disabled={executing || (availableFunds !== null && totalCapital > availableFunds)}
                    className="flex-1 px-3 py-2 bg-green-600 text-white rounded-md text-sm hover:bg-green-700 disabled:opacity-50 font-medium"
                  >
                    {executing ? 'Placing...' : 'Execute Trade'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
