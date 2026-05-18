"""Native scanner: 7-factor swing trading filter, no Chartink dependency."""

from datetime import datetime, timezone
from backend.database import SessionLocal
from backend.models import ScannerRun, ScannerResult, StockCache
from backend.scanner.universe import get_universe_symbols
from backend.scanner.ohlc_cache import get_cached_row
from backend.broker.kite_client import is_market_open


def _apply_filter(cached: dict, live_price: float, live_volume: float) -> tuple[bool, str, dict]:
    rsi_d = cached.get("rsi_daily")
    rsi_w = cached.get("rsi_weekly")
    rsi_m = cached.get("rsi_monthly")
    sma_20 = cached.get("sma_20")
    sma_50 = cached.get("sma_50")
    adx_val = cached.get("adx")
    plus_di = cached.get("plus_di")
    minus_di = cached.get("minus_di")
    avg_vol = cached.get("avg_volume_20d")
    atr_val = cached.get("atr")
    cached_close = cached.get("close") or 0

    if live_price <= 0:
        return False, "no_price", {}

    checks = {}
    reasons = []

    checks["price_filter"] = live_price > 150
    if not checks["price_filter"]:
        return False, "low_price", checks

    checks["volume_filter"] = live_volume > 100000
    if not checks["volume_filter"]:
        return False, "low_volume", checks

    checks["monthly_rsi"] = rsi_m is not None and rsi_m > 50
    if checks["monthly_rsi"]:
        reasons.append(f"MRsi:{rsi_m:.0f}")

    checks["weekly_rsi"] = rsi_w is not None and rsi_w > 50
    if checks["weekly_rsi"]:
        reasons.append(f"WRsi:{rsi_w:.0f}")

    checks["daily_rsi_zone"] = rsi_d is not None and 45 <= rsi_d <= 70
    if checks["daily_rsi_zone"]:
        reasons.append(f"DRsi:{rsi_d:.0f}")

    checks["above_sma20"] = sma_20 is not None and live_price > sma_20
    checks["above_sma50"] = sma_50 is not None and live_price > sma_50
    if checks["above_sma20"] and checks["above_sma50"]:
        reasons.append(">MA")

    checks["adx_strength"] = adx_val is not None and adx_val > 20
    checks["di_bullish"] = plus_di is not None and minus_di is not None and plus_di > minus_di
    if checks["adx_strength"] and checks["di_bullish"]:
        reasons.append(f"ADX:{adx_val:.0f}")

    checks["volume_surge"] = avg_vol is not None and avg_vol > 0 and live_volume > 1.2 * avg_vol
    if checks["volume_surge"]:
        reasons.append("VolSrg")

    passed = all([
        checks["price_filter"],
        checks["monthly_rsi"],
        checks["weekly_rsi"],
        checks["daily_rsi_zone"],
        checks["above_sma20"],
        checks["above_sma50"],
        checks["adx_strength"],
        checks["di_bullish"],
        checks["volume_surge"],
    ])

    if passed:
        return True, "passed", {
            "daily_rsi": round(rsi_d, 1) if rsi_d else None,
            "weekly_rsi": round(rsi_w, 1) if rsi_w else None,
            "monthly_rsi": round(rsi_m, 1) if rsi_m else None,
            "adx": round(adx_val, 1) if adx_val else None,
            "sma_20": round(sma_20, 2) if sma_20 else None,
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "plus_di": round(plus_di, 1) if plus_di else None,
            "minus_di": round(minus_di, 1) if minus_di else None,
            "atr": round(atr_val, 2) if atr_val else None,
            "reasons": reasons,
        }
    else:
        failed = [k for k, v in checks.items() if not v]
        return False, f"failed:{','.join(failed)}", checks


def run_native_scan(kite_client=None) -> dict:
    """Run native scanner on universe stocks. Uses Kite LTP if connected."""
    symbols = get_universe_symbols()
    if not symbols:
        return {"error": "No universe. Run POST /api/scanner/universe/build", "results": [], "total_scanned": 0}

    live_prices: dict[str, float] = {}
    live_volumes: dict[str, float] = {}

    if kite_client and kite_client.connected and is_market_open():
        try:
            quotes = kite_client.get_ltp(symbols[:1000])
            live_prices = {s: quotes.get(s, 0) for s in symbols}
        except Exception as e:
            print(f"[NativeScan] Kite LTP batch error: {e}")

    if not live_prices:
        try:
            import yfinance as yf
            for chunk in [symbols[i:i + 50] for i in range(0, min(len(symbols), 200), 50)]:
                ns_chunk = [s + ".NS" for s in chunk]
                tickers = yf.Tickers(" ".join(ns_chunk))
                for sym in chunk:
                    try:
                        t = tickers.tickers.get(sym + ".NS")
                        if t and t.fast_info:
                            live_prices[sym] = float(getattr(t.fast_info, "last_price", 0) or 0)
                            live_volumes[sym] = float(getattr(t.fast_info, "last_volume", 0) or 0)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[NativeScan] yfinance fallback error: {e}")

    passed_stocks = []
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        scan_run = ScannerRun(
            scanner_name="Native 7-Factor",
            run_at=now,
        )
        db.add(scan_run)
        db.flush()

        for symbol in symbols:
            price = live_prices.get(symbol, 0)
            volume = live_volumes.get(symbol, 0)

            raw = get_cached_row(symbol, now)
            if not raw:
                continue

            if price <= 0:
                price = raw.get("close", 0)
            if volume <= 0:
                volume = raw.get("volume", 0)

            passed, status, info = _apply_filter(raw, price, volume)
            if passed:
                entry = {
                    "symbol": symbol,
                    "price": price,
                    "change_pct": None,
                    "volume": volume,
                    "daily_rsi": info.get("daily_rsi"),
                    "weekly_rsi": info.get("weekly_rsi"),
                    "monthly_rsi": info.get("monthly_rsi"),
                    "adx": info.get("adx"),
                    "reasons": info.get("reasons", []),
                }
                passed_stocks.append(entry)

                db.add(ScannerResult(
                    run_id=scan_run.id,
                    symbol=symbol,
                    price=price,
                    scanner_name="Native 7-Factor",
                    change_pct=None,
                    volume=volume,
                    daily_rsi=info.get("daily_rsi"),
                    weekly_rsi=info.get("weekly_rsi"),
                ))

        scan_run.stock_count = len(passed_stocks)
        db.commit()

        return {
            "scanner_name": "Native 7-Factor",
            "run_at": now.isoformat(),
            "total_scanned": len(symbols),
            "passed": len(passed_stocks),
            "results": passed_stocks,
        }
    except Exception as e:
        db.rollback()
        print(f"[NativeScan] Error: {e}")
        return {"error": str(e), "results": [], "total_scanned": 0}
    finally:
        db.close()


def native_filter_signal(cached_row: dict) -> bool:
    """Signal check for backtest integration. Uses cached data only."""
    rsi_d = cached_row.get("rsi_daily")
    rsi_w = cached_row.get("rsi_weekly")
    rsi_m = cached_row.get("rsi_monthly")
    sma_20 = cached_row.get("sma_20")
    sma_50 = cached_row.get("sma_50")
    adx_val = cached_row.get("adx")
    plus_di = cached_row.get("plus_di")
    minus_di = cached_row.get("minus_di")
    close = cached_row.get("close") or 0
    vol = cached_row.get("volume") or 0
    avg_vol = cached_row.get("avg_volume_20d") or 0

    if close <= 150:
        return False

    if rsi_m is None or rsi_w is None or sma_50 is None or sma_20 is None:
        return False
    if adx_val is None or plus_di is None or minus_di is None:
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
