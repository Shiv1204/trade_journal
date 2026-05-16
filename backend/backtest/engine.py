import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import BacktestRun, BacktestTrade, ExitReason
from backend.scanner.replicator import SCANNER_FUNCTIONS
from backend.config import STOP_LOSS_PCT, TARGET_PCT, MAX_HOLDING_DAYS, CAPITAL_PER_TRADE

NSE_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "KOTAKBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "WIPRO.NS",
    "LT.NS", "HCLTECH.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ASIANPAINT.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "ULTRACEMCO.NS", "BAJAJFINSV.NS", "HINDUNILVR.NS",
    "TECHM.NS", "NESTLEIND.NS", "M&M.NS", "JSWSTEEL.NS", "TATASTEEL.NS",
    "COALINDIA.NS", "BRITANNIA.NS", "GRASIM.NS", "EICHERMOT.NS",
    "DRREDDY.NS", "DIVISLAB.NS", "SBILIFE.NS", "HDFCLIFE.NS",
    "ADANIPORTS.NS", "CIPLA.NS", "HINDALCO.NS", "APOLLOHOSP.NS",
    "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "UPL.NS", "SHREECEM.NS",
    "INDUSINDBK.NS", "TATACONSUM.NS", "BPCL.NS", "IOC.NS", "GAIL.NS",
]


def fetch_stock_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date, auto_adjust=True)
    if df.empty:
        return df
    df.columns = [col.replace(" ", "_") for col in df.columns]
    df["Market_Cap"] = 999999.0
    try:
        info = ticker.info
        mc = info.get("marketCap", np.nan)
        if mc and mc > 0:
            df["Market_Cap"] = mc / 1e7
    except Exception:
        pass
    return df


def run_backtest_for_symbol(
    symbol: str, df_full: pd.DataFrame, scanner_func, start_date: datetime, end_date: datetime,
    capital_per_trade: int = 100000,
) -> list[dict]:
    df = df_full.copy()
    df = df.sort_index()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    if len(df) < 200:
        return []

    signal = scanner_func(df)
    trades = []
    in_position = False
    entry_row = None
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)

    for i in range(len(df)):
        idx = df.index[i]
        if idx < start_ts:
            continue
        if idx > end_ts:
            break

        if not in_position:
            if i < len(signal) and signal.iloc[i]:
                entry_row = df.iloc[i]
                in_position = True
        else:
            row = df.iloc[i]
            entry_price = entry_row["Close"]
            current_price = row["Close"]
            high_price = row["High"]
            low_price = row["Low"]

            if entry_price == 0:
                in_position = False
                continue

            high_pnl_pct = ((high_price - entry_price) / entry_price) * 100
            low_pnl_pct = ((low_price - entry_price) / entry_price) * 100

            days_held = (idx - entry_row.name).days
            exit_reason = None

            if low_pnl_pct <= -STOP_LOSS_PCT:
                exit_price = entry_price * (1 - STOP_LOSS_PCT / 100)
                exit_reason = ExitReason.STOP_LOSS
            elif high_pnl_pct >= TARGET_PCT:
                exit_price = entry_price * (1 + TARGET_PCT / 100)
                exit_reason = ExitReason.TARGET
            elif days_held >= MAX_HOLDING_DAYS:
                exit_price = current_price
                exit_reason = ExitReason.TIME_EXIT

            if exit_reason:
                actual_pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                quantity = int(capital_per_trade / entry_price)
                actual_pnl = (exit_price - entry_price) * quantity
                trades.append({
                    "symbol": symbol,
                    "entry_date": entry_row.name.to_pydatetime(),
                    "exit_date": idx.to_pydatetime(),
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "quantity": quantity,
                    "profit_loss": round(actual_pnl, 2),
                    "pnl_pct": round(actual_pnl_pct, 2),
                    "exit_reason": exit_reason,
                    "days_held": days_held,
                })
                in_position = False

    return trades


def run_backtest(
    scanner_name: str,
    start_date: datetime,
    end_date: datetime,
    symbols: list[str] | None = None,
    capital_per_trade: int = 100000,
    db: Session | None = None,
) -> BacktestRun:
    if symbols is None:
        symbols = NSE_SYMBOLS

    scanner_func = SCANNER_FUNCTIONS[scanner_name]
    all_trades: list[dict] = []
    total_symbols = len(symbols)
    fetch_start = (start_date - timedelta(days=1460)).strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    for sym_idx, symbol in enumerate(symbols):
        print(f"[{sym_idx+1}/{total_symbols}] Fetching {symbol}...")
        df = fetch_stock_data(symbol, fetch_start, end_str)
        if df.empty:
            continue
        symbol_trades = run_backtest_for_symbol(symbol, df, scanner_func, start_date, end_date, capital_per_trade=capital_per_trade)
        all_trades.extend(symbol_trades)
        print(f"  -> {len(symbol_trades)} trades")

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        total = len(all_trades)
        winning = [t for t in all_trades if t["profit_loss"] > 0]
        losing = [t for t in all_trades if t["profit_loss"] <= 0]
        win_rate = len(winning) / total * 100 if total > 0 else 0
        total_pnl = sum(t["profit_loss"] for t in all_trades)
        avg_profit = sum(t["profit_loss"] for t in winning) / len(winning) if winning else 0
        avg_loss = sum(t["profit_loss"] for t in losing) / len(losing) if losing else 0

        equity_curve = []
        running_pnl = 0
        peak = 0
        max_dd = 0
        returns = []
        for t in all_trades:
            running_pnl += t["profit_loss"]
            returns.append(t["pnl_pct"])
            equity_curve.append(running_pnl)
            peak = max(peak, running_pnl)
            dd = (peak - running_pnl) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)

        sharpe = 0
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252)

        run = BacktestRun(
            scanner_name=scanner_name,
            start_date=start_date,
            end_date=end_date,
            total_trades=total,
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=round(win_rate, 2),
            total_pnl=round(total_pnl, 2),
            avg_profit=round(avg_profit, 2),
            avg_loss=round(avg_loss, 2),
            max_drawdown=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 2),
        )
        db.add(run)
        db.flush()

        for t in all_trades:
            bt_trade = BacktestTrade(
                backtest_run_id=run.id,
                symbol=t["symbol"],
                entry_date=t["entry_date"],
                exit_date=t["exit_date"],
                entry_price=t["entry_price"],
                exit_price=t["exit_price"],
                quantity=t["quantity"],
                profit_loss=t["profit_loss"],
                pnl_pct=t["pnl_pct"],
                exit_reason=t["exit_reason"],
            )
            db.add(bt_trade)

        db.commit()
        db.refresh(run)
        return run
    finally:
        if close_db:
            db.close()
