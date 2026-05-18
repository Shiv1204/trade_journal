from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, Query, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from backend.database import init_db, get_db, SessionLocal
from backend.models import Trade, TradeStatus, ExitReason, ScannerRun, ScannerResult
from backend.models import BacktestRun, BacktestTrade
from backend.scanner.scraper import scrape_both_scanners
from backend.scanner.dedup import find_duplicates
from backend.scanner.scorer import score_duplicate
from backend.scanner.universe import ensure_universe, build_universe_from_kite, get_universe_count, get_universe_symbols
from backend.scanner.ohlc_cache import refresh_cache
from backend.scanner.native_scanner import run_native_scan
from backend.backtest.engine import run_walk_forward_backtest, NSE_SYMBOLS
from backend.backtest.optimizer import run_parameter_sweep
from backend.backtest.metrics import get_run_summary, get_monthly_breakdown, get_trades_by_exit_reason
from backend.broker.position_manager import PositionManager
from backend.broker.kite_client import KiteClient
from backend.broker.kite_client import is_market_open
from backend.config import SCANNER_1_NAME, SCANNER_2_NAME, KITE_API_KEY, KITE_API_SECRET


kite_client = KiteClient()
position_manager = PositionManager()
position_manager.set_kite(kite_client)

scheduler = BackgroundScheduler()


def _scheduled_position_check():
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return
    hour = (now.hour + 5) % 24
    minute = now.minute + 30
    if minute >= 60:
        hour = (hour + 1) % 24
        minute -= 60
    ist_total = hour * 60 + minute
    if ist_total < 555 or ist_total > 930:
        return
    db = SessionLocal()
    try:
        position_manager.check_positions(db=db)
    except Exception as e:
        print(f"[Scheduler] Position check error: {e}")
    finally:
        db.close()


def _scheduled_native_scan():
    if not is_market_open():
        return
    try:
        result = run_native_scan(kite_client=kite_client)
        print(f"[Scheduler] Native scan: {result.get('passed', 0)}/{result.get('total_scanned', 0)} passed")
    except Exception as e:
        print(f"[Scheduler] Native scan error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.add_job(_scheduled_position_check, "interval", minutes=5, id="position_check")
    scheduler.add_job(_scheduled_native_scan, "interval", minutes=5, id="native_scan")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Trade Journal API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/scanner/run")
def run_scanner(background_tasks: BackgroundTasks):
    def _scrape_and_store():
        db = SessionLocal()
        try:
            data = scrape_both_scanners()
            for scanner_key in ["scanner_1", "scanner_2"]:
                scanner = data[scanner_key]
                run = ScannerRun(
                    scanner_name=scanner["name"],
                    stock_count=scanner["count"],
                )
                db.add(run)
                db.flush()
                for r in scanner["results"]:
                    result = ScannerResult(
                        run_id=run.id,
                        symbol=r["symbol"],
                        price=r["price"],
                        scanner_name=scanner["name"],
                        change_pct=r.get("change_pct"),
                        volume=r.get("volume"),
                        daily_rsi=r.get("daily_rsi"),
                        weekly_rsi=r.get("weekly_rsi"),
                    )
                    db.add(result)
            db.commit()
        except Exception as e:
            print(f"[Scanner Error] {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
        finally:
            db.close()

    background_tasks.add_task(_scrape_and_store)
    return {"message": "Scanner run started in background"}


@app.post("/api/scanner/native/run")
def run_native_scanner():
    result = run_native_scan(kite_client=kite_client)
    return result


@app.post("/api/scanner/cache/refresh")
def refresh_ohlc_cache(background_tasks: BackgroundTasks):
    def _refresh():
        symbols = get_universe_symbols()
        if not symbols:
            symbols = ensure_universe()
        count = refresh_cache(symbols)
        print(f"[Cache] Refreshed: {count} rows for {len(symbols)} stocks")
    background_tasks.add_task(_refresh)
    return {"message": "Cache refresh started", "universe_size": len(get_universe_symbols())}


@app.post("/api/scanner/universe/build")
def build_universe():
    count = build_universe_from_kite()
    if count == 0:
        from backend.scanner.universe import _static_fallback
        _static_fallback()
        count = get_universe_count()
    return {"message": f"Universe built: {count} stocks"}


@app.get("/api/scanner/universe")
def get_universe():
    return {"count": get_universe_count(), "symbols": get_universe_symbols()[:50]}


@app.get("/api/scanner/native/latest")
def get_latest_native_results(db: Session = Depends(get_db)):
    run = db.query(ScannerRun).filter(
        ScannerRun.scanner_name == "Native 7-Factor"
    ).order_by(ScannerRun.id.desc()).first()
    if not run:
        return {"scanner_name": "Native 7-Factor", "results": [], "total_scanned": 0, "passed": 0}
    results = db.query(ScannerResult).filter(ScannerResult.run_id == run.id).all()
    return {
        "scanner_name": "Native 7-Factor",
        "run_at": run.run_at.isoformat() if run.run_at else None,
        "total_scanned": get_universe_count(),
        "passed": len(results),
        "results": [
            {"symbol": r.symbol, "price": r.price, "volume": r.volume,
             "daily_rsi": r.daily_rsi, "weekly_rsi": r.weekly_rsi}
            for r in results
        ],
    }


@app.get("/api/scanner/latest")
def get_latest_scanner_results(db: Session = Depends(get_db)):
    run_1 = db.query(ScannerRun).filter(ScannerRun.scanner_name == SCANNER_1_NAME).order_by(ScannerRun.id.desc()).first()
    run_2 = db.query(ScannerRun).filter(ScannerRun.scanner_name == SCANNER_2_NAME).order_by(ScannerRun.id.desc()).first()

    def format_results(run):
        if not run:
            return []
        results = db.query(ScannerResult).filter(ScannerResult.run_id == run.id).all()
        return [{"symbol": r.symbol, "price": r.price, "change_pct": r.change_pct,
                 "volume": r.volume, "daily_rsi": r.daily_rsi, "weekly_rsi": r.weekly_rsi} for r in results]

    scanner_1_results = format_results(run_1)
    scanner_2_results = format_results(run_2)

    dedup = find_duplicates(scanner_1_results, scanner_2_results)

    bt_trades: list = []
    try:
        latest_bt = db.query(BacktestRun).filter(
            BacktestRun.scanner_name == SCANNER_1_NAME
        ).order_by(BacktestRun.id.desc()).first()
        if latest_bt:
            bt_trades = db.query(BacktestTrade).filter(
                BacktestTrade.backtest_run_id == latest_bt.id
            ).all()
    except Exception:
        pass

    scored_entries = []
    for entry in dedup.get("trade_entries", []):
        scored = score_duplicate(entry, bt_trades)
        entry.update(scored)
        scored_entries.append(entry)

    scored_entries.sort(key=lambda e: e.get("score", 0), reverse=True)

    return {
        "scanner_1": {"name": SCANNER_1_NAME, "results": scanner_1_results, "count": len(scanner_1_results)},
        "scanner_2": {"name": SCANNER_2_NAME, "results": scanner_2_results, "count": len(scanner_2_results)},
        "dedup": {**dedup, "trade_entries": scored_entries},
    }


@app.get("/api/trades")
def get_trades(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Trade)
    if status:
        if status == "open":
            query = query.filter(Trade.status == TradeStatus.OPEN)
        elif status == "closed":
            query = query.filter(Trade.status == TradeStatus.CLOSED)
    trades = query.order_by(Trade.entry_date.desc()).all()
    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "entry_date": t.entry_date.isoformat() if t.entry_date else None,
            "exit_date": t.exit_date.isoformat() if t.exit_date else None,
            "profit_loss": t.profit_loss,
            "pnl_pct": t.pnl_pct,
            "status": t.status.value if t.status else None,
            "exit_reason": t.exit_reason.value if t.exit_reason else None,
            "scanner_name": t.scanner_name,
        }
        for t in trades
    ]


@app.get("/api/trades/summary")
def get_trade_summary(db: Session = Depends(get_db)):
    trades = db.query(Trade).filter(Trade.status == TradeStatus.CLOSED).all()
    total = len(trades)
    winning = [t for t in trades if (t.profit_loss or 0) > 0]
    losing = [t for t in trades if (t.profit_loss or 0) <= 0]
    total_pnl = sum((t.profit_loss or 0) for t in trades)
    win_rate = (len(winning) / total * 100) if total > 0 else 0

    equity_curve = []
    running = 0
    peak = 0
    max_dd = 0
    for t in trades:
        running += (t.profit_loss or 0)
        peak = max(peak, running)
        dd = (peak - running) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
        equity_curve.append({"date": t.exit_date.isoformat() if t.exit_date else "", "pnl": running})

    return {
        "total_trades": total,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "max_drawdown": round(max_dd, 2),
        "equity_curve": equity_curve,
    }


@app.post("/api/backtest/run")
def start_backtest(
    background_tasks: BackgroundTasks,
    days: int = Query(365),
    capital_per_trade: int = Query(100000),
    sl_pct: float = Query(3.0),
    target_pct: float = Query(6.0),
    max_hold_days: int = Query(10),
):
    backtest_symbols: list[str] = []
    seen: set[str] = set()
    try:
        universe_syms = get_universe_symbols()
        if universe_syms:
            seen = set(universe_syms)
            backtest_symbols = [s + ".NS" for s in universe_syms]
    except Exception:
        pass

    if not backtest_symbols:
        try:
            db_temp = SessionLocal()
            for name in [SCANNER_1_NAME, SCANNER_2_NAME]:
                latest_run = db_temp.query(ScannerRun).filter(
                    ScannerRun.scanner_name == name
                ).order_by(ScannerRun.id.desc()).first()
                if latest_run:
                    results = db_temp.query(ScannerResult).filter(
                        ScannerResult.run_id == latest_run.id
                    ).all()
                    for r in results:
                        sym = r.symbol.strip().upper()
                        if sym and sym not in seen:
                            seen.add(sym)
                            backtest_symbols.append(sym + ".NS")
            db_temp.close()
        except Exception as e:
            print(f"[Backtest] Scanner symbol error: {e}")

    if not backtest_symbols:
        backtest_symbols = NSE_SYMBOLS[:10]

    def _run():
        db = SessionLocal()
        try:
            print(f"[Backtest] WF on {len(backtest_symbols)} stocks: SL={sl_pct}% TGT={target_pct}% MAX={max_hold_days}d")
            trades, summary = run_walk_forward_backtest(
                symbols=backtest_symbols,
                backtest_days=days,
                capital_per_trade=capital_per_trade,
                sl_pct=sl_pct,
                target_pct=target_pct,
                max_hold_days=max_hold_days,
            )
            run = BacktestRun(
                scanner_name="Walk-Forward Combined",
                start_date=datetime.now() - timedelta(days=days),
                end_date=datetime.now(),
                total_trades=summary["total_trades"],
                winning_trades=summary["winning_trades"],
                losing_trades=summary["losing_trades"],
                win_rate=summary["win_rate"],
                total_pnl=summary["total_pnl"],
                avg_profit=summary["avg_profit"],
                avg_loss=summary["avg_loss"],
                max_drawdown=summary["max_drawdown"],
                sharpe_ratio=summary["sharpe_ratio"],
                sl_pct=sl_pct,
                target_pct=target_pct,
                max_hold_days=max_hold_days,
                capital_per_trade=capital_per_trade,
            )
            db.add(run)
            db.flush()
            for t in trades:
                bt = BacktestTrade(
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
                db.add(bt)
            db.commit()
            print(f"[Backtest] Saved run {run.id}: {summary['total_trades']} trades, {summary['win_rate']}% win")
        except Exception as e:
            print(f"[Backtest Error] {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()

    background_tasks.add_task(_run)
    return {
        "message": "Backtest started",
        "params": f"SL={sl_pct}% TGT={target_pct}% MAX={max_hold_days}d",
        "symbols_count": len(backtest_symbols),
    }


@app.post("/api/backtest/optimize")
def start_optimization(
    background_tasks: BackgroundTasks,
    days: int = Query(365),
    capital_per_trade: int = Query(100000),
):
    backtest_symbols: list[str] = []
    seen: set[str] = set()
    try:
        universe_syms = get_universe_symbols()
        if universe_syms:
            seen = set(universe_syms)
            backtest_symbols = [s + ".NS" for s in universe_syms]
    except Exception:
        pass

    if not backtest_symbols:
        try:
            db_temp = SessionLocal()
            for name in [SCANNER_1_NAME, SCANNER_2_NAME]:
                latest_run = db_temp.query(ScannerRun).filter(
                    ScannerRun.scanner_name == name
                ).order_by(ScannerRun.id.desc()).first()
                if latest_run:
                    results = db_temp.query(ScannerResult).filter(
                        ScannerResult.run_id == latest_run.id
                    ).all()
                    for r in results:
                        sym = r.symbol.strip().upper()
                        if sym and sym not in seen:
                            seen.add(sym)
                            backtest_symbols.append(sym + ".NS")
            db_temp.close()
        except Exception as e:
            print(f"[Opt] Failed to get scanner symbols: {e}")

    if not backtest_symbols:
        backtest_symbols = NSE_SYMBOLS[:10]

    def _run():
        db = SessionLocal()
        try:
            print(f"[Opt] Sweeping SL[2-5] TGT[4-10] MAX[7-21] on {len(backtest_symbols)} stocks")
            results = run_parameter_sweep(
                symbols=backtest_symbols,
                backtest_days=days,
                capital_per_trade=capital_per_trade,
                sl_range=(2.0, 5.0, 1.0),
                target_range=(4.0, 10.0, 2.0),
                max_hold_range=(7, 21, 7),
            )
            for r in results:
                run = BacktestRun(
                    scanner_name="Optimization",
                    start_date=datetime.now() - timedelta(days=days),
                    end_date=datetime.now(),
                    total_trades=r["total_trades"],
                    winning_trades=r["winning_trades"],
                    losing_trades=r["losing_trades"],
                    win_rate=r["win_rate"],
                    total_pnl=r["total_pnl"],
                    avg_profit=r["avg_profit"],
                    avg_loss=r["avg_loss"],
                    max_drawdown=r["max_drawdown"],
                    sharpe_ratio=r["sharpe_ratio"],
                    sl_pct=r["sl_pct"],
                    target_pct=r["target_pct"],
                    max_hold_days=r["max_hold_days"],
                    capital_per_trade=r["capital_per_trade"],
                )
                db.add(run)
            db.commit()
            print(f"[Opt] Saved {len(results)} optimization runs")
        except Exception as e:
            print(f"[Opt Error] {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()

    background_tasks.add_task(_run)
    return {"message": "Optimization started", "symbols_count": len(backtest_symbols)}


@app.get("/api/backtest/runs")
def get_backtest_runs(db: Session = Depends(get_db)):
    runs = db.query(BacktestRun).order_by(BacktestRun.id.desc()).all()
    return [get_run_summary(r) for r in runs]


@app.get("/api/backtest/runs/{run_id}")
def get_backtest_run_detail(run_id: int, db: Session = Depends(get_db)):
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        return JSONResponse(status_code=404, content={"error": "Backtest run not found"})
    trades = db.query(BacktestTrade).filter(BacktestTrade.backtest_run_id == run_id).all()
    monthly = get_monthly_breakdown(trades)
    by_reason = get_trades_by_exit_reason(trades)

    latest_scanner = db.query(ScannerRun).order_by(ScannerRun.id.desc()).first()
    scanner_identified_at = latest_scanner.run_at.isoformat() if latest_scanner else None

    return {
        "summary": get_run_summary(run),
        "monthly_breakdown": monthly,
        "exit_reason_breakdown": by_reason,
        "scanner_identified_at": scanner_identified_at,
        "trades": [
            {
                "symbol": t.symbol,
                "entry_date": t.entry_date.isoformat() if t.entry_date else None,
                "exit_date": t.exit_date.isoformat() if t.exit_date else None,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "profit_loss": t.profit_loss,
                "pnl_pct": t.pnl_pct,
                "exit_reason": t.exit_reason.value if t.exit_reason else None,
                "days_held": (t.exit_date - t.entry_date).days if t.exit_date and t.entry_date else None,
            }
            for t in trades
        ],
    }


@app.get("/api/kite/callback")
def kite_callback(request_token: str = Query(...), status: str = Query("success")):
    if status != "success":
        return HTMLResponse("<h2>Login failed</h2><p>Kite login was unsuccessful.</p>", status_code=400)
    try:
        session = kite_client.generate_session(request_token)
        return HTMLResponse(f"""
        <html><head><title>Kite Connected</title></head><body>
        <h2>Kite Connected</h2><p>Logged in as {session.get('user_name', 'Unknown')}.</p>
        <p>You can close this window and return to the Trade Journal.</p>
        <script>window.close();</script>
        </body></html>
        """)
    except Exception as e:
        return HTMLResponse(f"<h2>Connection failed</h2><p>{e}</p>", status_code=400)


@app.get("/api/market/status")
def market_status():
    return {
        "is_open": is_market_open(),
        "current_time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/kite/login-url")
def get_kite_login_url():
    url = kite_client.get_login_url()
    return {"login_url": url}


@app.post("/api/kite/connect")
def connect_kite(body: dict = Body(...)):
    request_token = body.get("request_token")
    if not request_token:
        return JSONResponse(status_code=400, content={"error": "request_token required"})
    try:
        session = kite_client.generate_session(request_token)
        return {"status": "connected", "user_name": session.get("user_name")}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.get("/api/kite/status")
def get_kite_status():
    return {
        "connected": kite_client.connected,
        "user_name": kite_client.user_name,
    }


@app.post("/api/kite/logout")
def logout_kite():
    kite_client.logout()
    return {"status": "disconnected"}


@app.post("/api/trades/execute")
def execute_trade(body: dict = Body(...)):
    if not is_market_open():
        return JSONResponse(status_code=400, content={
            "error": "Market is closed. Trading hours: 9:15 AM - 3:30 PM IST, Mon-Fri"
        })

    symbol = body.get("symbol", "").strip().upper()
    price = body.get("price")
    capital_per_trade = int(body.get("capital_per_trade", 100000))
    scanner_name = body.get("scanner_name", "")

    if not symbol or not price:
        return JSONResponse(status_code=400, content={"error": "symbol and price required"})

    entry_price = float(price)
    if entry_price <= 0:
        return JSONResponse(status_code=400, content={"error": "invalid price"})

    sl_pct = 3.0
    quantity = int(capital_per_trade / entry_price)

    from backend.config import MAX_POSITIONS, RISK_PCT_PER_TRADE, DAILY_LOSS_LIMIT_PCT
    db = SessionLocal()
    try:
        open_count = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).count()
        if open_count >= MAX_POSITIONS:
            db.close()
            return JSONResponse(status_code=400, content={
                "error": f"Max {MAX_POSITIONS} concurrent positions. Close some trades first."
            })

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_closed = db.query(Trade).filter(
            Trade.status == TradeStatus.CLOSED,
            Trade.exit_date >= today_start,
        ).all()
        today_loss = sum(abs(t.profit_loss or 0) for t in today_closed if (t.profit_loss or 0) < 0)
        if kite_client.connected:
            try:
                margins = kite_client._api_get("/user/margins/equity")
                available = float(margins.get("data", {}).get("available", {}).get("live_balance", 0))
                if available > 0 and today_loss > 0:
                    daily_loss_pct = (today_loss / available) * 100
                    if daily_loss_pct >= DAILY_LOSS_LIMIT_PCT:
                        db.close()
                        return JSONResponse(status_code=400, content={
                            "error": f"Daily loss limit ({DAILY_LOSS_LIMIT_PCT}%) reached. Today: {today_loss:.0f} loss."
                        })
                if available > 0:
                    risk_amount = available * (RISK_PCT_PER_TRADE / 100)
                    risk_per_share = entry_price * (sl_pct / 100)
                    risk_qty = int(risk_amount / risk_per_share) if risk_per_share > 0 else 1
                    if risk_qty >= 1:
                        quantity = risk_qty
            except Exception:
                pass

        if quantity < 1:
            db.close()
            return JSONResponse(status_code=400, content={"error": f"capital {capital_per_trade} too low for price {entry_price}"})

        buy_order = None
        sl_order = None
        if kite_client.connected:
            try:
                buy_order = kite_client.place_market_order(symbol, quantity, "BUY")
                if buy_order:
                    print(f"[Trade] BUY {symbol} x{quantity}: {buy_order['order_id']}")
                else:
                    print(f"[Trade] BUY failed for {symbol}, saving trade record anyway")
            except Exception as e:
                print(f"[Trade] BUY order error: {e}")

            if buy_order:
                try:
                    sl_price = round(entry_price * (1 - 3 / 100), 2)
                    sl_order = kite_client.place_sl_order(symbol, quantity, sl_price)
                    if sl_order:
                        print(f"[Trade] SL order for {symbol}: {sl_order['order_id']}")
                except Exception as e:
                    print(f"[Trade] SL order error: {e}")

        trade = Trade(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            entry_date=datetime.now(timezone.utc),
            status=TradeStatus.OPEN,
            scanner_name=scanner_name,
            kite_order_id=buy_order["order_id"] if buy_order else None,
            kite_sl_order_id=sl_order["order_id"] if sl_order else None,
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

        try:
            from backend.models import Alert
            alert = Alert(
                alert_type="entry",
                message=f"{symbol} BOUGHT x{quantity} @ ₹{entry_price} | SL: ₹{round(entry_price * 0.97, 2)}",
                trade_id=trade.id,
                symbol=symbol,
            )
            db.add(alert)
            db.commit()
        except Exception:
            pass

        return {
            "status": "trade_opened",
            "trade_id": trade.id,
            "symbol": symbol,
            "entry_price": entry_price,
            "quantity": quantity,
            "capital_used": round(entry_price * quantity, 2),
            "kite_buy_order": buy_order,
            "kite_sl_order": sl_order,
            "sl_price": round(entry_price * (1 - 3 / 100), 2),
            "target_price": round(entry_price * (1 + 6 / 100), 2),
        }
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        db.close()


@app.get("/api/kite/margins")
def get_kite_margins():
    if not kite_client.connected:
        return JSONResponse(status_code=400, content={"error": "Kite not connected"})
    try:
        import requests
        resp = requests.get(
            "https://api.kite.trade/user/margins/equity",
            headers=kite_client._headers(),
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "success":
            return JSONResponse(status_code=500, content={"error": "Failed to fetch margins"})
        equity = data["data"]
        return {
            "available_cash": equity.get("available", {}).get("cash", 0),
            "live_balance": equity.get("available", {}).get("live_balance", 0),
            "net": equity.get("net", 0),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/kite/holdings")
def get_kite_holdings_summary():
    if not kite_client.connected:
        return JSONResponse(status_code=400, content={"error": "Kite not connected"})
    try:
        holdings = kite_client.get_holdings()
        db = SessionLocal()
        try:
            open_trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()
            tracked_symbols = {t.symbol.upper() for t in open_trades}
        finally:
            db.close()

        parsed = []
        for h in holdings:
            sym = (h.get("tradingsymbol") or "").strip().upper()
            parsed.append({
                "symbol": sym,
                "quantity": h.get("quantity", 0),
                "avg_price": h.get("average_price", 0),
                "last_price": h.get("last_price", 0),
                "pnl": h.get("pnl", 0),
                "product": h.get("product", ""),
                "tracked": sym in tracked_symbols,
            })
        return {
            "holdings": parsed,
            "count": len(parsed),
            "tracked_count": sum(1 for p in parsed if p["tracked"]),
            "untracked_count": sum(1 for p in parsed if not p["tracked"]),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/trades/{trade_id}/cancel")
def cancel_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        return JSONResponse(status_code=404, content={"error": "Trade not found"})
    if trade.status != TradeStatus.OPEN:
        return JSONResponse(status_code=400, content={"error": "Only open trades can be cancelled"})

    if is_market_open():
        try:
            if kite_client.connected:
                kite_client.place_market_order(trade.symbol, trade.quantity, "SELL")
                if trade.kite_sl_order_id:
                    kite_client.cancel_order(trade.kite_sl_order_id)
        except Exception as e:
            print(f"[Cancel] Kite exit order error: {e}")

    trade.status = TradeStatus.CLOSED
    trade.exit_date = datetime.now(timezone.utc)
    trade.exit_reason = ExitReason.MANUAL
    trade.exit_price = trade.entry_price
    trade.profit_loss = 0
    trade.pnl_pct = 0
    db.commit()

    return {"status": "cancelled", "trade_id": trade.id}


@app.post("/api/positions/check")
def check_positions(background_tasks: BackgroundTasks):
    def _check():
        db = SessionLocal()
        try:
            position_manager.check_positions(db=db)
        finally:
            db.close()

    background_tasks.add_task(_check)
    return {"message": "Position check started"}


@app.get("/api/portfolio/summary")
def portfolio_summary():
    open_trades = []
    total_cost = 0.0
    total_value = 0.0
    total_pnl = 0.0

    db = SessionLocal()
    try:
        open_trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()
        if not open_trades:
            return {"total_cost": 0, "total_value": 0, "total_pnl": 0, "positions": [], "is_market_open": is_market_open()}

        symbols = list({t.symbol for t in open_trades})
        ltp_map = {}
        if kite_client.connected:
            try:
                ltp_map = kite_client.get_ltp(symbols)
            except Exception:
                pass

        positions = []
        for t in open_trades:
            cost = t.entry_price * t.quantity
            ltp = ltp_map.get(t.symbol, t.entry_price)
            current_val = ltp * t.quantity
            pnl = current_val - cost
            pnl_pct = ((ltp - t.entry_price) / t.entry_price) * 100 if t.entry_price > 0 else 0
            total_cost += cost
            total_value += current_val
            total_pnl += pnl
            positions.append({
                "trade_id": t.id,
                "symbol": t.symbol,
                "qty": t.quantity,
                "entry": round(t.entry_price, 2),
                "ltp": round(ltp, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })

        return {
            "total_cost": round(total_cost, 2),
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round((total_pnl / total_cost) * 100, 2) if total_cost > 0 else 0,
            "positions": positions,
            "is_market_open": is_market_open(),
        }
    finally:
        db.close()


@app.get("/api/alerts")
def get_alerts(limit: int = 20, db: Session = Depends(get_db)):
    from backend.models import Alert
    alerts = db.query(Alert).order_by(Alert.id.desc()).limit(limit).all()
    return [
        {
            "id": a.id,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "alert_type": a.alert_type,
            "message": a.message,
            "symbol": a.symbol,
            "trade_id": a.trade_id,
        }
        for a in alerts
    ]


frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        index_path = frontend_dist / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return JSONResponse(status_code=404, content={"error": "Not found"})
