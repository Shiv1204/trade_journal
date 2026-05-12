from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.database import init_db, get_db, SessionLocal
from backend.models import Trade, TradeStatus, ScannerRun, ScannerResult
from backend.models import BacktestRun, BacktestTrade
from backend.scanner.scraper import scrape_both_scanners
from backend.scanner.dedup import find_duplicates
from backend.backtest.engine import run_backtest, NSE_SYMBOLS
from backend.backtest.metrics import get_run_summary, get_monthly_breakdown, get_trades_by_exit_reason
from backend.broker.position_manager import PositionManager
from backend.config import SCANNER_1_NAME, SCANNER_2_NAME


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Trade Journal API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

position_manager = PositionManager()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/scanner/run")
def run_scanner(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    def _scrape_and_store():
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
                )
                db.add(result)
        db.commit()

    background_tasks.add_task(_scrape_and_store)
    return {"message": "Scanner run started in background"}


@app.get("/api/scanner/latest")
def get_latest_scanner_results(db: Session = Depends(get_db)):
    runs = db.query(ScannerRun).order_by(ScannerRun.id.desc()).limit(2).all()
    scanner_1_results = []
    scanner_2_results = []
    for run in runs:
        results = db.query(ScannerResult).filter(ScannerResult.run_id == run.id).all()
        formatted = [{"symbol": r.symbol, "price": r.price} for r in results]
        if run.scanner_name == SCANNER_1_NAME:
            scanner_1_results = formatted
        else:
            scanner_2_results = formatted

    dedup = find_duplicates(scanner_1_results, scanner_2_results)
    return {
        "scanner_1": {"name": SCANNER_1_NAME, "results": scanner_1_results, "count": len(scanner_1_results)},
        "scanner_2": {"name": SCANNER_2_NAME, "results": scanner_2_results, "count": len(scanner_2_results)},
        "dedup": dedup,
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
    scanner_name: str = Query(SCANNER_1_NAME),
    days: int = Query(365),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    def _run():
        run_backtest(scanner_name, start_date, end_date)

    background_tasks.add_task(_run)
    return {
        "message": "Backtest started",
        "scanner_name": scanner_name,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


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
    return {
        "summary": get_run_summary(run),
        "monthly_breakdown": monthly,
        "exit_reason_breakdown": by_reason,
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
            }
            for t in trades
        ],
    }


@app.post("/api/positions/check")
def check_positions(background_tasks: BackgroundTasks):
    def _check():
        position_manager.check_positions()

    background_tasks.add_task(_check)
    return {"message": "Position check started"}
