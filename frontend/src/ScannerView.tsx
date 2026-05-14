import { useEffect, useState } from 'react'
import { api, ScannerData } from './api'

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

export default function ScannerView() {
  const [data, setData] = useState<ScannerData | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  const load = () => {
    setLoading(true)
    api.getLatestScanner()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

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

  if (loading) return <div className="text-center py-12 text-gray-500">Loading scanner data...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Scanner Comparison</h2>
        <button
          onClick={handleRun}
          disabled={running}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {running ? 'Running Scanners...' : 'Run Scanners'}
        </button>
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
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-gray-400">No results</td>
                      </tr>
                    ) : (
                      data.scanner_1.results.map((r, i) => (
                        <tr key={`s1-${r.symbol}-${i}`} className="hover:bg-blue-50">
                          <td className="px-3 py-1.5 text-gray-400 text-xs">{i + 1}</td>
                          <td className="px-3 py-1.5 font-medium">{r.symbol}</td>
                          <td className="px-3 py-1.5 text-right font-mono">
                            {r.price != null ? `₹${r.price.toFixed(2)}` : '-'}
                          </td>
                          <td className={`px-3 py-1.5 text-right ${(r.change_pct ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {r.change_pct != null ? `${r.change_pct.toFixed(2)}%` : '-'}
                          </td>
                          <td className="px-3 py-1.5 text-right text-gray-500">{formatVolume(r.volume)}</td>
                          <td className={`px-3 py-1.5 text-right font-medium ${rsiColor(r.daily_rsi)}`}>
                            {r.daily_rsi != null ? r.daily_rsi.toFixed(1) : '-'}
                          </td>
                          <td className={`px-3 py-1.5 text-right font-medium ${rsiColor(r.weekly_rsi)}`}>
                            {r.weekly_rsi != null ? r.weekly_rsi.toFixed(1) : '-'}
                          </td>
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
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-gray-400">No results</td>
                      </tr>
                    ) : (
                      data.scanner_2.results.map((r, i) => (
                        <tr key={`s2-${r.symbol}-${i}`} className="hover:bg-purple-50">
                          <td className="px-3 py-1.5 text-gray-400 text-xs">{i + 1}</td>
                          <td className="px-3 py-1.5 font-medium">{r.symbol}</td>
                          <td className="px-3 py-1.5 text-right font-mono">
                            {r.price != null ? `₹${r.price.toFixed(2)}` : '-'}
                          </td>
                          <td className={`px-3 py-1.5 text-right ${(r.change_pct ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {r.change_pct != null ? `${r.change_pct.toFixed(2)}%` : '-'}
                          </td>
                          <td className="px-3 py-1.5 text-right text-gray-500">{formatVolume(r.volume)}</td>
                          <td className={`px-3 py-1.5 text-right font-medium ${rsiColor(r.daily_rsi)}`}>
                            {r.daily_rsi != null ? r.daily_rsi.toFixed(1) : '-'}
                          </td>
                          <td className={`px-3 py-1.5 text-right font-medium ${rsiColor(r.weekly_rsi)}`}>
                            {r.weekly_rsi != null ? r.weekly_rsi.toFixed(1) : '-'}
                          </td>
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
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.dedup.trade_entries.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-gray-400">No duplicates found</td>
                    </tr>
                  ) : (
                    data.dedup.trade_entries.map((entry, i) => (
                      <tr key={`dup-${entry.symbol}`} className="hover:bg-green-50">
                        <td className="px-2 py-1.5 text-gray-400 text-xs">{i + 1}</td>
                        <td className="px-2 py-1.5 font-medium">{entry.symbol}</td>
                        <td className="px-2 py-1.5 text-right font-mono">
                          {entry.price_1 != null ? `₹${entry.price_1.toFixed(2)}` : '-'}
                        </td>
                        <td className="px-2 py-1.5 text-right font-mono">
                          {entry.price_2 != null ? `₹${entry.price_2.toFixed(2)}` : '-'}
                        </td>
                        <td className="px-2 py-1.5 text-right">
                          <span className={rsiColor(entry.daily_rsi_1)}>
                            {entry.daily_rsi_1 != null ? entry.daily_rsi_1.toFixed(1) : '-'}
                          </span>
                          {' / '}
                          <span className={rsiColor(entry.daily_rsi_2)}>
                            {entry.daily_rsi_2 != null ? entry.daily_rsi_2.toFixed(1) : '-'}
                          </span>
                        </td>
                        <td className="px-2 py-1.5 text-right">
                          <span className={rsiColor(entry.weekly_rsi_1)}>
                            {entry.weekly_rsi_1 != null ? entry.weekly_rsi_1.toFixed(1) : '-'}
                          </span>
                          {' / '}
                          <span className={rsiColor(entry.weekly_rsi_2)}>
                            {entry.weekly_rsi_2 != null ? entry.weekly_rsi_2.toFixed(1) : '-'}
                          </span>
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
    </div>
  )
}
