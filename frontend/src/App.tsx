import { useState, useEffect, useCallback } from 'react'
import Dashboard from './Dashboard'
import TradeJournal from './TradeJournal'
import ScannerView from './ScannerView'
import BacktestView from './BacktestView'
import { api } from './api'

type Tab = 'dashboard' | 'scanner' | 'journal' | 'backtest'

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
  const [kiteConnected, setKiteConnected] = useState(false)
  const [kiteUser, setKiteUser] = useState<string | null>(null)
  const [connecting, setConnecting] = useState(false)

  const checkKiteStatus = useCallback(() => {
    api.getKiteStatus().then(s => {
      setKiteConnected(s.connected)
      setKiteUser(s.user_name)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    checkKiteStatus()
    const interval = setInterval(checkKiteStatus, 30000)
    const handleUrl = () => {
      const params = new URLSearchParams(window.location.search)
      const token = params.get('request_token')
      if (token) {
        setConnecting(true)
        api.connectKite(token)
          .then(() => {
            checkKiteStatus()
            window.history.replaceState({}, '', window.location.pathname)
          })
          .catch(console.error)
          .finally(() => setConnecting(false))
      }
    }
    handleUrl()
    return () => clearInterval(interval)
  }, [checkKiteStatus])

  const handleConnectKite = async () => {
    try {
      const { login_url } = await api.getKiteLoginUrl()
      window.open(login_url, '_blank')
    } catch (e) {
      console.error(e)
    }
  }

  const handleLogoutKite = async () => {
    try {
      await api.kiteLogout()
      setKiteConnected(false)
      setKiteUser(null)
    } catch (e) {
      console.error(e)
    }
  }

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
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-gray-900">Trade Journal</h1>
            {connecting ? (
              <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-1 rounded-full font-medium">
                Connecting...
              </span>
            ) : kiteConnected ? (
              <button onClick={handleLogoutKite} className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium hover:bg-green-200">
                Kite: {kiteUser || 'Connected'}
              </button>
            ) : (
              <button onClick={handleConnectKite} className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded-full font-medium hover:bg-red-200">
                Connect Kite
              </button>
            )}
          </div>
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
        {tab === 'dashboard' && <Dashboard kiteConnected={kiteConnected} />}
        {tab === 'scanner' && <ScannerView kiteConnected={kiteConnected} onConnectKite={handleConnectKite} />}
        {tab === 'journal' && <TradeJournal />}
        {tab === 'backtest' && <BacktestView />}
      </main>
    </div>
  )
}
