import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Callable

from backend.database import SessionLocal
from backend.models import BacktestRun, BacktestTrade, ExitReason
from backend.backtest.indicators import rsi, sma, adx, atr
from backend.config import MIN_CLOSE, MIN_MARKET_CAP


def _precompute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_index()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    rsi_m = rsi(df["Close"].resample("ME").last(), 14)
    df["rsi_monthly"] = rsi_m.reindex(df.index, method="ffill")

    rsi_w = rsi(df["Close"].resample("W").last(), 14)
    df["rsi_weekly"] = rsi_w.reindex(df.index, method="ffill")

    df["sma_50"] = sma(df["Close"], 50)

    df["rsi_daily"] = rsi(df["Close"], 14)
    df["sma_20"] = sma(df["Close"], 20)

    adx_data = adx(df["High"], df["Low"], df["Close"], 14)
    df["adx"] = adx_data["adx"]
    df["plus_di"] = adx_data["plus_di"]
    df["minus_di"] = adx_data["minus_di"]
    df["avg_volume_20d"] = df["Volume"].rolling(20).mean()
    df["atr"] = atr(df["High"], df["Low"], df["Close"], 14)

    return df


def _native_filter_signal(ind: pd.DataFrame, idx: int) -> bool:
    """7-factor native filter — tight: RSI>55, ADX>30, Vol>1.5x avg"""
    try:
        close = ind["Close"].iloc[idx]
        vol = ind["Volume"].iloc[idx]
        rsi_m = ind["rsi_monthly"].iloc[idx]
        rsi_w = ind["rsi_weekly"].iloc[idx]
        rsi_d = ind["rsi_daily"].iloc[idx]
        sma_20 = ind["sma_20"].iloc[idx]
        sma_50 = ind["sma_50"].iloc[idx]
        adx_val = ind["adx"].iloc[idx]
        plus_di = ind["plus_di"].iloc[idx]
        minus_di = ind["minus_di"].iloc[idx]
        avg_vol = ind["avg_volume_20d"].iloc[idx] if "avg_volume_20d" in ind.columns else 0

        if close <= 150:
            return False
        if pd.isna(rsi_m) or pd.isna(rsi_w) or pd.isna(sma_20) or pd.isna(sma_50):
            return False
        if pd.isna(adx_val) or pd.isna(plus_di) or pd.isna(minus_di):
            return False

        return bool(
            rsi_m > 50
            and rsi_w > 50
            and 45 <= (rsi_d or 0) <= 70
            and close > sma_20
            and close > sma_50
            and adx_val > 20
            and plus_di > minus_di
            and avg_vol > 0
            and vol > 1.2 * avg_vol
        )
    except (IndexError, KeyError):
        return False


def _get_atr_sl_target(ind: pd.DataFrame, idx: int, sl_pct: float, target_pct: float):
    """Dynamic SL/Target based on ATR. If ATR available, use 1.5x ATR for SL, 3x for target."""
    close = ind["Close"].iloc[idx]
    atr_val = 0
    if "atr" in ind.columns:
        atr_val = ind["atr"].iloc[idx]
    if pd.notna(atr_val) and atr_val > 0 and close > 0:
        sl_price = close - (atr_val * 1.5)
        target_price = close + (atr_val * 3.0)
        sl = max(sl_pct, ((close - sl_price) / close) * 100)
        tp = max(target_pct, ((target_price - close) / close) * 100)
        return sl, tp
    return sl_pct, target_pct


def run_walk_forward_backtest(
    symbols: list[str],
    backtest_days: int,
    capital_per_trade: float,
    sl_pct: float,
    target_pct: float,
    max_hold_days: int,
) -> tuple[list[dict], dict]:

    end_date = datetime.now()
    start_date = end_date - timedelta(days=backtest_days)
    fetch_start = start_date - timedelta(days=1095)

    print(f"[WF] Fetching data from {fetch_start.date()} to {end_date.date()}")

    indicators: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(
                start=fetch_start.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                auto_adjust=True,
            )
            if df.empty or len(df) < 200:
                continue
            df.columns = [c.replace(" ", "_") for c in df.columns]
            df["Market_Cap"] = 999999.0
            ind = _precompute_indicators(df)
            indicators[sym] = ind
        except Exception as e:
            print(f"[WF] Skip {sym}: {e}")

    bt_mask = (indicators[list(indicators.keys())[0]].index >= pd.Timestamp(start_date)) if indicators else None
    if bt_mask is None:
        return [], {}

    all_trades: list[dict] = []
    active_positions: dict[str, dict] = {}

    first_sym = list(indicators.keys())[0]
    all_days = indicators[first_sym].index

    for i in range(len(all_days)):
        day = all_days[i]
        if day < pd.Timestamp(start_date):
            continue
        if day > pd.Timestamp(end_date):
            break

        for sym in list(active_positions.keys()):
            pos = active_positions[sym]
            if sym not in indicators:
                continue
            df = indicators[sym]
            day_idx = df.index.get_loc(day) if day in df.index else None
            if day_idx is None:
                continue

            row = df.iloc[day_idx]
            current_price = row["Close"]
            entry_price = pos["entry_price"]
            if entry_price <= 0:
                del active_positions[sym]
                continue

            days_held = (day - pd.Timestamp(pos["entry_date"])).days
            high = row["High"]
            low = row["Low"]
            high_pct = ((high - entry_price) / entry_price) * 100
            low_pct = ((low - entry_price) / entry_price) * 100

            exit_reason = None
            exit_price = current_price

            eff_sl, eff_tp = _get_atr_sl_target(df, day_idx, sl_pct, target_pct)

            if low_pct <= -eff_sl:
                exit_price = entry_price * (1 - eff_sl / 100)
                exit_reason = ExitReason.STOP_LOSS
            elif high_pct >= eff_tp:
                exit_price = entry_price * (1 + eff_tp / 100)
                exit_reason = ExitReason.TARGET
            elif days_held >= max_hold_days:
                exit_price = current_price
                exit_reason = ExitReason.TIME_EXIT

            if exit_reason:
                qty = pos["quantity"]
                pnl = (exit_price - entry_price) * qty
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                all_trades.append({
                    "symbol": sym,
                    "entry_date": pos["entry_date"],
                    "exit_date": day,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "quantity": qty,
                    "profit_loss": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "exit_reason": exit_reason,
                    "days_held": days_held,
                })
                del active_positions[sym]

        for sym in symbols:
            if sym in active_positions:
                continue
            if sym not in indicators:
                continue
            df = indicators[sym]
            day_idx = df.index.get_loc(day) if day in df.index else None
            if day_idx is None:
                continue

            if _native_filter_signal(df, day_idx):
                entry_price = float(df["Close"].iloc[day_idx])
                if entry_price <= 0:
                    continue

                quantity = int(capital_per_trade / entry_price)
                if quantity < 1:
                    continue

                active_positions[sym] = {
                    "entry_date": day,
                    "entry_price": entry_price,
                    "quantity": quantity,
                }

    for sym, pos in active_positions.items():
        df = indicators.get(sym)
        if df is None or df.empty:
            continue
        last_price = float(df["Close"].iloc[-1])
        days_held = (df.index[-1] - pd.Timestamp(pos["entry_date"])).days
        pnl = (last_price - pos["entry_price"]) * pos["quantity"]
        pnl_pct = ((last_price - pos["entry_price"]) / pos["entry_price"]) * 100
        all_trades.append({
            "symbol": sym,
            "entry_date": pos["entry_date"],
            "exit_date": df.index[-1],
            "entry_price": round(pos["entry_price"], 2),
            "exit_price": round(last_price, 2),
            "quantity": pos["quantity"],
            "profit_loss": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "exit_reason": ExitReason.TIME_EXIT,
            "days_held": days_held,
        })

    total = len(all_trades)
    winning = [t for t in all_trades if t["profit_loss"] > 0]
    losing = [t for t in all_trades if t["profit_loss"] <= 0]
    win_rate = len(winning) / total * 100 if total > 0 else 0
    total_pnl = sum(t["profit_loss"] for t in all_trades)
    avg_profit = sum(t["profit_loss"] for t in winning) / len(winning) if winning else 0
    avg_loss = sum(t["profit_loss"] for t in losing) / len(losing) if losing else 0

    running_pnl = 0
    peak = 0
    max_dd = 0
    returns = []
    for t in all_trades:
        running_pnl += t["profit_loss"]
        returns.append(t["pnl_pct"])
        peak = max(peak, running_pnl)
        dd = (peak - running_pnl) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)

    sharpe = 0
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252)

    summary = {
        "total_trades": total,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_profit": round(avg_profit, 2),
        "avg_loss": round(avg_loss, 2),
        "max_drawdown": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sl_pct": sl_pct,
        "target_pct": target_pct,
        "max_hold_days": max_hold_days,
        "capital_per_trade": capital_per_trade,
    }

    return all_trades, summary


NSE_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "KOTAKBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "WIPRO.NS",
    "LT.NS", "HCLTECH.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ASIANPAINT.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "ULTRACEMCO.NS", "TECHM.NS", "M&M.NS", "JSWSTEEL.NS",
    "TATASTEEL.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", "HINDALCO.NS",
    "ADANIPORTS.NS", "CIPLA.NS", "HDFCLIFE.NS", "SBILIFE.NS", "INDUSINDBK.NS",
    "TATACONSUM.NS", "BPCL.NS", "IOC.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS",
    "NESTLEIND.NS", "BRITANNIA.NS", "EICHERMOT.NS", "GRASIM.NS", "BAJAJFINSV.NS",
    "HINDUNILVR.NS", "APOLLOHOSP.NS", "UPL.NS", "GAIL.NS", "SHREECEM.NS",
]
