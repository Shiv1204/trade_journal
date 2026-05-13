import { useEffect, useState } from 'react'
import { api, ScannerData } from './api'

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
      await new Promise(r => setTimeout(r, 3000))
      load()
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
          {running ? 'Running...' : 'Run Scanners'}
        </button>
      </div>

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <div className="text-sm text-gray-500">{data.scanner_1.name}</div>
              <div className="text-2xl font-bold text-blue-600">{data.scanner_1.count}</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <div className="text-sm text-gray-500">{data.scanner_2.name}</div>
              <div className="text-2xl font-bold text-purple-600">{data.scanner_2.count}</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow text-center">
              <div className="text-sm text-gray-500">Duplicates (Trade)</div>
              <div className="text-2xl font-bold text-green-600">{data.dedup.count_both}</div>
            </div>
          </div>

          {data.dedup.trade_entries.length > 0 && (
            <div className="bg-white rounded-lg shadow">
              <div className="px-4 py-3 border-b bg-green-50">
                <h3 className="font-semibold text-green-800">
                  Trade Entries ({data.dedup.trade_entries.length} stocks in both scanners)
                </h3>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium text-gray-600">Symbol</th>
                    <th className="text-right px-4 py-2 font-medium text-gray-600">Price (S1)</th>
                    <th className="text-right px-4 py-2 font-medium text-gray-600">Price (S2)</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.dedup.trade_entries.map((entry) => (
                    <tr key={entry.symbol} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium">{entry.symbol}</td>
                      <td className="px-4 py-2 text-right">${entry.price_1?.toFixed(2) ?? '-'}</td>
                      <td className="px-4 py-2 text-right">${entry.price_2?.toFixed(2) ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white rounded-lg shadow">
              <div className="px-4 py-3 border-b">
                <h3 className="font-semibold text-blue-800">Only in {data.scanner_1.name}</h3>
                <span className="text-xs text-gray-500">{data.dedup.count_only_1} stocks</span>
              </div>
              <div className="max-h-48 overflow-y-auto p-2">
                {data.dedup.only_in_scanner_1.map((s) => (
                  <span key={s} className="inline-block px-2 py-1 m-1 bg-blue-50 text-blue-700 rounded text-xs font-medium">
                    {s}
                  </span>
                ))}
              </div>
            </div>
            <div className="bg-white rounded-lg shadow">
              <div className="px-4 py-3 border-b">
                <h3 className="font-semibold text-purple-800">Only in {data.scanner_2.name}</h3>
                <span className="text-xs text-gray-500">{data.dedup.count_only_2} stocks</span>
              </div>
              <div className="max-h-48 overflow-y-auto p-2">
                {data.dedup.only_in_scanner_2.map((s) => (
                  <span key={s} className="inline-block px-2 py-1 m-1 bg-purple-50 text-purple-700 rounded text-xs font-medium">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
