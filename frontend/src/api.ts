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
  scanner_1: { name: string; results: ScannerResult[]; count: number }
  scanner_2: { name: string; results: ScannerResult[]; count: number }
  dedup: {
    only_in_scanner_1: string[]
    only_in_scanner_2: string[]
    in_both: string[]
    trade_entries: DedupEntry[]
    count_only_1: number
    count_only_2: number
    count_both: number
  }
}

export interface ScannerResult {
  symbol: string
  price: number | null
  change_pct: number | null
  volume: number | null
  daily_rsi: number | null
  weekly_rsi: number | null
}

export interface DedupEntry {
  symbol: string
  price_1: number | null
  price_2: number | null
  change_pct_1: number | null
  change_pct_2: number | null
  volume_1: number | null
  volume_2: number | null
  daily_rsi_1: number | null
  daily_rsi_2: number | null
  weekly_rsi_1: number | null
  weekly_rsi_2: number | null
  score: number
  grade: string
  reasons: string[]
  backtest_win_rate: number | null
  backtest_trades: number
  backtest_total_pnl: number | null
  daily_rsi_avg: number | null
  weekly_rsi_avg: number | null
  avg_volume: number
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
  sl_pct: number | null
  target_pct: number | null
  max_hold_days: number | null
  capital_per_trade: number | null
  created_at: string
}

export interface BacktestDetail {
  summary: BacktestRun
  monthly_breakdown: { month: string; trades: number; pnl: number; wins: number; losses: number; win_rate: number }[]
  exit_reason_breakdown: Record<string, { count: number; total_pnl: number }>
  scanner_identified_at: string | null
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
    days_held: number | null
  }[]
}

export interface KiteStatus {
  connected: boolean
  user_name: string | null
}

export interface ExecuteTradeRequest {
  symbol: string
  price: number
  capital_per_trade: number
  scanner_name: string
}

export interface ExecuteTradeResponse {
  status: string
  trade_id: number
  symbol: string
  entry_price: number
  quantity: number
  capital_used: number
  kite_buy_order: { order_id: string } | null
  kite_sl_order: { order_id: string } | null
  sl_price: number
  target_price: number
}

export interface KiteMargins {
  available_cash: number
  live_balance: number
  net: number
}

export interface KiteHolding {
  symbol: string
  quantity: number
  avg_price: number
  last_price: number
  pnl: number
  product: string
  tracked: boolean
}

export interface KiteHoldingsResponse {
  holdings: KiteHolding[]
  count: number
  tracked_count: number
  untracked_count: number
}

export interface SyncResponse {
  status: string
  imported: number
  sl_orders_placed: number
  total_holdings: number
  errors: string[]
}

export interface PortfolioPosition {
  trade_id: number
  symbol: string
  qty: number
  entry: number
  ltp: number
  pnl: number
  pnl_pct: number
}

export interface PortfolioSummary {
  total_cost: number
  total_value: number
  total_pnl: number
  total_pnl_pct: number
  positions: PortfolioPosition[]
  is_market_open: boolean
}

export interface Alert {
  id: number
  created_at: string
  alert_type: string
  message: string
  symbol: string | null
  trade_id: number | null
}

export interface MarketStatus {
  is_open: boolean
  current_time: string
}

export const api = {
  health: () => get<{ status: string }>('/health'),
  runScanner: () => post<{ message: string }>('/scanner/run'),
  getLatestScanner: () => get<ScannerData>('/scanner/latest'),
  getTrades: (status?: string) => get<Trade[]>(`/trades${status ? `?status=${status}` : ''}`),
  getTradeSummary: () => get<TradeSummary>('/trades/summary'),
  runBacktest: (days: number, capital_per_trade: number, sl_pct: number, target_pct: number, max_hold_days: number) =>
    post<{ message: string }>(`/backtest/run?days=${days}&capital_per_trade=${capital_per_trade}&sl_pct=${sl_pct}&target_pct=${target_pct}&max_hold_days=${max_hold_days}`),
  runOptimization: (days: number, capital_per_trade: number) =>
    post<{ message: string }>(`/backtest/optimize?days=${days}&capital_per_trade=${capital_per_trade}`),
  getBacktestRuns: () => get<BacktestRun[]>('/backtest/runs'),
  getBacktestDetail: (id: number) => get<BacktestDetail>(`/backtest/runs/${id}`),
  checkPositions: () => post<{ message: string }>('/positions/check'),
  getKiteLoginUrl: () => get<{ login_url: string }>('/kite/login-url'),
  connectKite: (requestToken: string) => post<{ status: string; user_name: string }>('/kite/connect', { request_token: requestToken }),
  getKiteStatus: () => get<KiteStatus>('/kite/status'),
  kiteLogout: () => post<{ status: string }>('/kite/logout'),
  executeTrade: (req: ExecuteTradeRequest) => post<ExecuteTradeResponse>('/trades/execute', req),
  cancelTrade: (tradeId: number) => post<{ status: string; trade_id: number }>(`/trades/${tradeId}/cancel`),
  getKiteMargins: () => get<KiteMargins>('/kite/margins'),
  getKiteHoldings: () => get<KiteHoldingsResponse>('/kite/holdings'),
  syncKitePositions: () => post<SyncResponse>('/trades/sync'),
  getPortfolioSummary: () => get<PortfolioSummary>('/portfolio/summary'),
  getAlerts: (limit?: number) => get<Alert[]>(`/alerts${limit ? `?limit=${limit}` : ''}`),
  getMarketStatus: () => get<MarketStatus>('/market/status'),
}
