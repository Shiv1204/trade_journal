import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

from backend.backtest.indicators import rsi, sma, adx
from backend.config import (
    SCANNER_1_NAME, SCANNER_2_NAME,
    MIN_MARKET_CAP, MIN_CLOSE,
)

MIN_VOLUME_BACKTEST = 50000


def scanner_1_monthly_rsi_above_50(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    df = df.sort_index()

    rsi_monthly = rsi(df["Close"].resample("ME").last(), 14)
    df["rsi_monthly"] = rsi_monthly.reindex(df.index, method="ffill")

    rsi_weekly = rsi(df["Close"].resample("W").last(), 14)
    df["rsi_weekly"] = rsi_weekly.reindex(df.index, method="ffill")

    df["sma_50"] = sma(df["Close"], 50)

    cond_m = df["rsi_monthly"].notna() & (df["rsi_monthly"] > 50)
    cond_w = df["rsi_weekly"].notna() & (df["rsi_weekly"] >= 50)
    cond_trend = cond_w & (df["Close"] > df["sma_50"])

    cond = cond_m | cond_trend

    daily_volume: pd.Series = df.get("Volume", pd.Series(0, index=df.index))
    daily_close: pd.Series = df["Close"]

    if "Market_Cap" in df.columns:
        cond &= (df["Market_Cap"] > MIN_MARKET_CAP)

    cond &= (daily_volume > MIN_VOLUME_BACKTEST)
    cond &= (daily_close > MIN_CLOSE)

    return cond


def scanner_2_top_scanner_combo(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    df = df.sort_index()

    df["sma_50"] = sma(df["Close"], 50)

    adx_data = adx(df["High"], df["Low"], df["Close"], 14)
    df["adx"] = adx_data["adx"]
    df["plus_di"] = adx_data["plus_di"]
    df["minus_di"] = adx_data["minus_di"]

    daily_volume: pd.Series = df.get("Volume", pd.Series(0, index=df.index))
    daily_close: pd.Series = df["Close"]

    adx_valid = df["adx"].notna() & (df["adx"] > 20)
    cond_primary = (
        (daily_close > df["sma_50"]) &
        adx_valid &
        (df["plus_di"] > df["minus_di"])
    )

    cond_trend = daily_close > df["sma_50"]

    cond = cond_primary | cond_trend

    if "Market_Cap" in df.columns:
        cond &= (df["Market_Cap"] > MIN_MARKET_CAP)

    cond &= (daily_volume > MIN_VOLUME_BACKTEST)
    cond &= (daily_close > MIN_CLOSE)

    return cond


SCANNER_FUNCTIONS = {
    SCANNER_1_NAME: scanner_1_monthly_rsi_above_50,
    SCANNER_2_NAME: scanner_2_top_scanner_combo,
}
