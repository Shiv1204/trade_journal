const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

export interface Trade {
  id: number
  symbol: string
  entry_price: number
  exit_price: number | null
  quantity: number
  entry_date: string
  exit_date: string | null
  profit_loss: number | null
  pnl_pct: number | null
  status: 'open' | 'closed'
  exit_reason: string | null
  scanner_name: string | null
}

export interface TradeSummary {
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  total_pnl: number
  max_drawdown: number
  equity_curve: { date: string; pnl: number }[]
}

export interface ScannerData {
  scanner_1: { name: string; results: { symbol: string; price: number | null }[]; count: number }
  scanner_2: { name: string; results: { symbol: string; price: number | null }[]; count: number }
  dedup: {
    only_in_scanner_1: string[]
    only_in_scanner_2: string[]
    in_both: string[]
    trade_entries: { symbol: string; price_1: number | null; price_2: number | null }[]
    count_only_1: number
    count_only_2: number
    count_both: number
  }
}

export interface BacktestRun {
  id: number
  scanner_name: string
  start_date: string
  end_date: string
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  total_pnl: number
  avg_profit: number
  avg_loss: number
  max_drawdown: number
  sharpe_ratio: number
}

export interface BacktestDetail {
  summary: BacktestRun
  monthly_breakdown: { month: string; trades: number; pnl: number; wins: number; losses: number; win_rate: number }[]
  exit_reason_breakdown: Record<string, { count: number; total_pnl: number }>
  trades: {
    symbol: string
    entry_date: string
    exit_date: string
    entry_price: number
    exit_price: number
    quantity: number
    profit_loss: number
    pnl_pct: number
    exit_reason: string
  }[]
}

export const api = {
  health: () => get<{ status: string }>('/health'),
  runScanner: () => post<{ message: string }>('/scanner/run'),
  getLatestScanner: () => get<ScannerData>('/scanner/latest'),
  getTrades: (status?: string) => get<Trade[]>(`/trades${status ? `?status=${status}` : ''}`),
  getTradeSummary: () => get<TradeSummary>('/trades/summary'),
  runBacktest: (scanner_name: string, days: number) =>
    post<{ message: string }>(`/backtest/run?scanner_name=${encodeURIComponent(scanner_name)}&days=${days}`),
  getBacktestRuns: () => get<BacktestRun[]>('/backtest/runs'),
  getBacktestDetail: (id: number) => get<BacktestDetail>(`/backtest/runs/${id}`),
  checkPositions: () => post<{ message: string }>('/positions/check'),
}
