import { useState } from 'react'
import Dashboard from './Dashboard'
import TradeJournal from './TradeJournal'
import ScannerView from './ScannerView'
import BacktestView from './BacktestView'

type Tab = 'dashboard' | 'scanner' | 'journal' | 'backtest'

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard')

  const tabs: { key: Tab; label: string }[] = [
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'scanner', label: 'Scanner' },
    { key: 'journal', label: 'Trade Journal' },
    { key: 'backtest', label: 'Backtest' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">Trade Journal</h1>
          <nav className="flex gap-1">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  tab === t.key
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {tab === 'dashboard' && <Dashboard />}
        {tab === 'scanner' && <ScannerView />}
        {tab === 'journal' && <TradeJournal />}
        {tab === 'backtest' && <BacktestView />}
      </main>
    </div>
  )
}
