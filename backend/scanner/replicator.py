import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

from backend.backtest.indicators import rsi, sma, adx, highest
from backend.config import (
    SCANNER_1_NAME, SCANNER_2_NAME,
    MIN_MARKET_CAP, MIN_VOLUME, MIN_CLOSE,
)

def scanner_1_monthly_rsi_above_50(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    df = df.sort_index()

    df["rsi_monthly"] = rsi(df["Close"].resample("ME").last(), 14)
    df["rsi_monthly_1m_ago"] = df["rsi_monthly"].shift(1)
    df["rsi_monthly_2m_ago"] = df["rsi_monthly"].shift(2)
    df["rsi_monthly_3m_ago"] = df["rsi_monthly"].shift(3)

    df["rsi_weekly"] = rsi(df["Close"].resample("W").last(), 14)
    df["rsi_weekly"] = df["rsi_weekly"].reindex(df.index, method="ffill")

    cond = (
        (df["rsi_monthly"] > 50) &
        (df["rsi_monthly_1m_ago"] <= 50) &
        (df["rsi_monthly_1m_ago"] < 50) &
        (df["rsi_monthly_2m_ago"] < 50) &
        (df["rsi_monthly_3m_ago"] < 50) &
        (df["rsi_weekly"] >= 50)
    )

    daily_volume: pd.Series = df.get("Volume", pd.Series(0, index=df.index))
    daily_close: pd.Series = df["Close"]

    if "Market_Cap" in df.columns:
        cond &= (df["Market_Cap"] > MIN_MARKET_CAP)

    cond &= (daily_volume > MIN_VOLUME)
    cond &= (daily_close > MIN_CLOSE)

    return cond


def scanner_2_top_scanner_combo(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    df = df.sort_index()

    df["sma_20"] = sma(df["Close"], 20)
    df["sma_50"] = sma(df["Close"], 50)
    df["sma_200"] = sma(df["Close"], 200)

    adx_data = adx(df["High"], df["Low"], df["Close"], 14)
    df["adx"] = adx_data["adx"]
    df["plus_di"] = adx_data["plus_di"]
    df["minus_di"] = adx_data["minus_di"]

    df["high_20"] = highest(df["High"], 20)

    df["daily_change_pct"] = df["Close"].pct_change() * 100

    daily_volume: pd.Series = df.get("Volume", pd.Series(0, index=df.index))
    daily_close: pd.Series = df["Close"]

    cond = (
        (daily_close > df["sma_20"]) &
        (daily_close > df["sma_50"]) &
        (daily_close > df["sma_200"]) &
        (df["adx"] > 25) &
        (df["plus_di"] > df["minus_di"]) &
        (daily_close > df["high_20"].shift(1)) &
        (daily_close > MIN_CLOSE)
    )

    if "Market_Cap" in df.columns:
        cond &= (df["Market_Cap"] > MIN_MARKET_CAP)

    cond &= (daily_volume > MIN_VOLUME)
    cond &= (df["daily_change_pct"].abs() < 8)

    return cond


SCANNER_FUNCTIONS = {
    SCANNER_1_NAME: scanner_1_monthly_rsi_above_50,
    SCANNER_2_NAME: scanner_2_top_scanner_combo,
}
