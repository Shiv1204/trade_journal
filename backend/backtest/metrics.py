import numpy as np
from backend.models import BacktestRun, BacktestTrade


def get_run_summary(run: BacktestRun) -> dict:
    return {
        "id": run.id,
        "scanner_name": run.scanner_name,
        "start_date": run.start_date.isoformat() if run.start_date else None,
        "end_date": run.end_date.isoformat() if run.end_date else None,
        "total_trades": run.total_trades,
        "winning_trades": run.winning_trades,
        "losing_trades": run.losing_trades,
        "win_rate": run.win_rate,
        "total_pnl": run.total_pnl,
        "avg_profit": run.avg_profit,
        "avg_loss": run.avg_loss,
        "max_drawdown": run.max_drawdown,
        "sharpe_ratio": run.sharpe_ratio,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def get_trades_by_exit_reason(trades: list[BacktestTrade]) -> dict:
    reasons = {}
    for t in trades:
        reason = t.exit_reason.value if t.exit_reason else "unknown"
        if reason not in reasons:
            reasons[reason] = {"count": 0, "total_pnl": 0, "trades": []}
        reasons[reason]["count"] += 1
        reasons[reason]["total_pnl"] += (t.profit_loss or 0)
        reasons[reason]["trades"].append({
            "symbol": t.symbol,
            "pnl_pct": t.pnl_pct,
            "profit_loss": t.profit_loss,
        })
    return reasons


def get_monthly_breakdown(trades: list[BacktestTrade]) -> list[dict]:
    monthly = {}
    for t in trades:
        if not t.exit_date:
            continue
        key = t.exit_date.strftime("%Y-%m")
        if key not in monthly:
            monthly[key] = {"month": key, "trades": 0, "pnl": 0, "wins": 0, "losses": 0}
        monthly[key]["trades"] += 1
        monthly[key]["pnl"] += (t.profit_loss or 0)
        if (t.profit_loss or 0) > 0:
            monthly[key]["wins"] += 1
        else:
            monthly[key]["losses"] += 1
    result = sorted(monthly.values(), key=lambda x: x["month"])
    for r in result:
        r["win_rate"] = round(r["wins"] / r["trades"] * 100, 1) if r["trades"] else 0
    return result
