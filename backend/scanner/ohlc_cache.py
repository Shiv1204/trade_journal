"""Daily OHLC data cache with pre-computed indicators for backtest + live scan."""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from backend.database import SessionLocal
from backend.models import StockCache
from backend.backtest.indicators import rsi, sma, adx, atr

BATCH_SIZE = 50


def refresh_cache(symbols: list[str]) -> int:
    """Fetch 5 years of OHLC for all symbols, compute indicators, store in DB."""
    end = datetime.now()
    start = end - timedelta(days=1825)

    total_stored = 0
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = [s + ".NS" for s in symbols[i:i + BATCH_SIZE]]
        try:
            df = yf.download(
                batch,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                auto_adjust=True,
                progress=False,
                threads=True,
            )
        except Exception as e:
            print(f"[Cache] Batch {i} download failed: {e}")
            continue

        for j, sym in enumerate(symbols[i:i + BATCH_SIZE]):
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    stock_df = df.xs(sym + ".NS", axis=1, level=1).copy()
                except KeyError:
                    continue
            else:
                stock_df = df.iloc[:, [j * 5 + k for k in range(5)]].copy() if j * 5 + 4 < df.shape[1] else None
                if stock_df is None or stock_df.empty:
                    continue
                stock_df.columns = ["Open", "High", "Low", "Close", "Volume"]

            stock_df = stock_df.dropna(subset=["Close"])
            if len(stock_df) < 100:
                continue

            ind = _compute_indicators(stock_df)
            total_stored += _store_cached_rows(sym, ind)

        print(f"[Cache] Batch {i // BATCH_SIZE + 1}/{(len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE}: {sym} done")

    print(f"[Cache] Total rows stored: {total_stored}")
    return total_stored


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df["rsi_daily"] = rsi(df["Close"], 14)
    df["sma_20"] = sma(df["Close"], 20)
    df["sma_50"] = sma(df["Close"], 50)
    df["avg_volume_20d"] = sma(df["Volume"], 20)

    rsi_w = rsi(df["Close"].resample("W").last(), 14)
    df["rsi_weekly"] = rsi_w.reindex(df.index, method="ffill")

    rsi_m = rsi(df["Close"].resample("ME").last(), 14)
    df["rsi_monthly"] = rsi_m.reindex(df.index, method="ffill")

    adx_d = adx(df["High"], df["Low"], df["Close"], 14)
    df["adx"] = adx_d["adx"]
    df["plus_di"] = adx_d["plus_di"]
    df["minus_di"] = adx_d["minus_di"]
    df["atr"] = atr(df["High"], df["Low"], df["Close"], 14)

    return df


def _store_cached_rows(symbol: str, df: pd.DataFrame) -> int:
    db = SessionLocal()
    count = 0
    try:
        db.query(StockCache).filter(StockCache.symbol == symbol).delete()
        for idx, row in df.iterrows():
            db.add(StockCache(
                symbol=symbol,
                date=idx.to_pydatetime(),
                open=float(row.get("Open", 0) or 0),
                high=float(row.get("High", 0) or 0),
                low=float(row.get("Low", 0) or 0),
                close=float(row.get("Close", 0) or 0),
                volume=int(row.get("Volume", 0) or 0),
                rsi_daily=float(row["rsi_daily"]) if not pd.isna(row.get("rsi_daily")) else None,
                rsi_weekly=float(row["rsi_weekly"]) if not pd.isna(row.get("rsi_weekly")) else None,
                rsi_monthly=float(row["rsi_monthly"]) if not pd.isna(row.get("rsi_monthly")) else None,
                sma_20=float(row["sma_20"]) if not pd.isna(row.get("sma_20")) else None,
                sma_50=float(row["sma_50"]) if not pd.isna(row.get("sma_50")) else None,
                adx=float(row["adx"]) if not pd.isna(row.get("adx")) else None,
                plus_di=float(row["plus_di"]) if not pd.isna(row.get("plus_di")) else None,
                minus_di=float(row["minus_di"]) if not pd.isna(row.get("minus_di")) else None,
                avg_volume_20d=float(row["avg_volume_20d"]) if not pd.isna(row.get("avg_volume_20d")) else None,
                atr=float(row["atr"]) if not pd.isna(row.get("atr")) else None,
            ))
            count += 1
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Cache] Store error for {symbol}: {e}")
    finally:
        db.close()
    return count


def get_cached_row(symbol: str, date: datetime) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(StockCache).filter(
            StockCache.symbol == symbol,
            StockCache.date <= date.replace(hour=0, minute=0, second=0, microsecond=0),
        ).order_by(StockCache.date.desc()).first()
        if row:
            return {
                "close": row.close, "volume": row.volume,
                "rsi_daily": row.rsi_daily, "rsi_weekly": row.rsi_weekly,
                "rsi_monthly": row.rsi_monthly, "sma_20": row.sma_20,
                "sma_50": row.sma_50, "adx": row.adx,
                "plus_di": row.plus_di, "minus_di": row.minus_di,
                "avg_volume_20d": row.avg_volume_20d,
                "atr": row.atr,
            }
    finally:
        db.close()
    return None


def get_cached_history(symbol: str, days: int = 365) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=days)
    db = SessionLocal()
    try:
        rows = db.query(StockCache).filter(
            StockCache.symbol == symbol,
            StockCache.date >= cutoff,
        ).order_by(StockCache.date.asc()).all()
        return [
            {
                "date": r.date, "close": r.close, "volume": r.volume,
                "rsi_daily": r.rsi_daily, "rsi_weekly": r.rsi_weekly,
                "rsi_monthly": r.rsi_monthly, "sma_20": r.sma_20,
                "sma_50": r.sma_50, "adx": r.adx,
                "plus_di": r.plus_di, "minus_di": r.minus_di,
                "avg_volume_20d": r.avg_volume_20d,
                "atr": r.atr,
            }
            for r in rows
        ]
    finally:
        db.close()
