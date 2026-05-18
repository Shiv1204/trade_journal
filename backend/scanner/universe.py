"""Build and manage the NSE 500 cash stock universe."""
import json
import requests
import itertools
from pathlib import Path
from datetime import datetime, timezone
from backend.database import SessionLocal
from backend.models import StockUniverse
from io import StringIO
import csv


def build_universe_from_kite() -> int:
    """Download Kite instruments master, filter for NSE cash > 150."""
    try:
        resp = requests.get("https://api.kite.trade/instruments", timeout=30)
        if resp.status_code != 200:
            raise Exception(f"Instruments fetch failed: {resp.status_code}")
    except Exception as e:
        print(f"[Universe] Kite instruments failed: {e}")
        return 0

    reader = csv.DictReader(StringIO(resp.text))
    db = SessionLocal()
    count = 0
    try:
        db.query(StockUniverse).delete()
        for row in reader:
            segment = row.get("segment", "")
            name = row.get("name", "")
            exch = row.get("exchange", "")
            sym = row.get("tradingsymbol", "")
            price = float(row.get("last_price", 0) or 0)

            if exch != "NSE" or segment != "EQ":
                continue

            name_lower = name.lower() if name else ""

            skip_keywords = [
                "nifty", "bank", "sensex", "etf", "gold", "silver",
                "liquid", "bees", "niftybee", "juniorbees", "bankbees",
                "cpse", "infra", "itbees", "m100", "mid150", "nv20",
                "consum", "pharma", "auto", "fin", "metal", "energy",
                "sbin", "itbees", "setfnn50", "mon100", "mazd",
                "sgb", "g-sec", "triparty", "govt", "state",
                "development", "loan", "bond", "debenture",
                "nv20i", "li", "mid", "small", "next50",
            ]

            if any(kw in name_lower for kw in skip_keywords):
                continue

            if price <= 150:
                continue

            db.add(StockUniverse(
                symbol=sym.strip().upper(),
                name=name.strip(),
                last_price=price,
                updated_at=datetime.now(timezone.utc),
            ))
            count += 1

        db.commit()
        print(f"[Universe] Built: {count} stocks (Kite instruments)")
    except Exception as e:
        print(f"[Universe] Build error: {e}")
        db.rollback()
        count = 0
    finally:
        db.close()

    return count


def get_universe_symbols() -> list[str]:
    db = SessionLocal()
    try:
        stocks = db.query(StockUniverse).all()
        return [s.symbol for s in stocks]
    finally:
        db.close()


def get_universe_count() -> int:
    db = SessionLocal()
    try:
        return db.query(StockUniverse).count()
    finally:
        db.close()


def ensure_universe() -> list[str]:
    symbols = get_universe_symbols()
    if not symbols:
        count = build_universe_from_kite()
        if count == 0:
            print("[Universe] Using NSE 100 fallback")
            return _static_fallback()
        symbols = get_universe_symbols()
    return symbols


_NSE_FALLBACK = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "KOTAKBANK",
    "SBIN", "BHARTIARTL", "ITC", "WIPRO", "LT", "HCLTECH", "AXISBANK",
    "BAJFINANCE", "MARUTI", "SUNPHARMA", "TITAN", "ASIANPAINT", "NTPC",
    "ONGC", "POWERGRID", "ULTRACEMCO", "TECHM", "M&M", "JSWSTEEL",
    "TATASTEEL", "COALINDIA", "DIVISLAB", "DRREDDY", "HINDALCO",
    "ADANIPORTS", "CIPLA", "HDFCLIFE", "SBILIFE", "INDUSINDBK",
    "TATACONSUM", "BPCL", "IOC", "BAJAJ-AUTO", "HEROMOTOCO",
    "NESTLEIND", "BRITANNIA", "EICHERMOT", "GRASIM", "BAJAJFINSV",
    "HINDUNILVR", "APOLLOHOSP", "UPL", "GAIL", "SHREECEM",
    "TATAMOTORS", "HAL", "BEL", "ADANIENT", "TRENT", "ZOMATO",
    "IRFC", "VBL", "DMART", "SIEMENS", "PIDILITIND", "ABB",
    "MOTHERSON", "PFC", "VARUNBEVER", "TVSMOTOR", "CANBK",
    "GODREJCP", "RECLTD", "CHOLAFIN", "VEDL", "DLF", "IRCTC",
    "ABCAPITAL", "BHEL", "SRF", "HAVELLS", "ICICIGI", "BANKBARODA",
    "BIOCON", "TORNTPHARM", "INDIGO", "BOSCHLTD", "DABUR", "BERGEPAINT",
    "LUPIN", "MARICO", "COLPAL", "AMBUJACEM", "PIIND", "MCDOWELL-N",
    "NAUKRI", "JINDALSTEL", "ICICIPRULI", "AUROPHARMA", "ALKEM",
    "MPHASIS", "LTTS", "PERSISTENT", "PAGEIND", "BHARATFORG",
]


def _static_fallback():
    db = SessionLocal()
    try:
        for sym in _NSE_FALLBACK:
            db.add(StockUniverse(
                symbol=sym.strip().upper(),
                name=sym,
                last_price=0,
                updated_at=datetime.now(timezone.utc),
            ))
        db.commit()
    finally:
        db.close()
    return _NSE_FALLBACK


def fetch_kite_universe(kite_client) -> int:
    """Alternative: use an authenticated KiteClient to get instruments."""
    try:
        data = kite_client._api_get("/instruments")
        text = json.dumps(data.get("data", data)) if isinstance(data, dict) else data
        reader = csv.DictReader(StringIO(text))
    except Exception as e:
        print(f"[Universe] Kite instrument fetch failed: {e}")
        return 0

    db = SessionLocal()
    count = 0
    try:
        db.query(StockUniverse).delete()
        for row in reader:
            if row.get("exchange") != "NSE" or row.get("segment") != "EQ":
                continue
            price = float(row.get("last_price", 0) or 0)
            if price <= 150:
                continue
            symbol = row.get("tradingsymbol", "").strip().upper()
            if not symbol:
                continue
            db.add(StockUniverse(
                symbol=symbol,
                name=row.get("name", "").strip(),
                last_price=price,
                updated_at=datetime.now(timezone.utc),
            ))
            count += 1
        db.commit()
        print(f"[Universe] Built from Kite: {count} stocks")
    except Exception as e:
        db.rollback()
        print(f"[Universe] Error: {e}")
    finally:
        db.close()
    return count
