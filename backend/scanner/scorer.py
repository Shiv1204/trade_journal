from backend.models import BacktestTrade, ExitReason
from backend.config import MIN_CLOSE


def score_duplicate(
    entry: dict,
    backtest_trades: list[BacktestTrade],
) -> dict:
    symbol = entry.get("symbol", "")
    daily_rsi_1 = entry.get("daily_rsi_1")
    daily_rsi_2 = entry.get("daily_rsi_2")
    weekly_rsi_1 = entry.get("weekly_rsi_1")
    weekly_rsi_2 = entry.get("weekly_rsi_2")
    volume_1 = entry.get("volume_1") or 0
    volume_2 = entry.get("volume_2") or 0

    score = 50
    reasons: list[str] = []

    bt = [t for t in backtest_trades if t.symbol == symbol]
    if bt:
        wins = [t for t in bt if t.profit_loss and t.profit_loss > 0]
        win_rate = len(wins) / len(bt) * 100 if bt else 0
        total_pnl = sum(t.profit_loss or 0 for t in bt)

        if win_rate >= 60:
            score += 15
            reasons.append(f"{win_rate:.0f}% backtest win rate")
        elif win_rate >= 40:
            score += 5
            reasons.append(f"{win_rate:.0f}% backtest win rate")
        elif win_rate < 30:
            score -= 10
            reasons.append(f"Low backtest win rate ({win_rate:.0f}%)")

        if total_pnl > 0:
            score += 10
            reasons.append(f"Positive backtest P&L")
        elif total_pnl < 0:
            score -= 5

        avg_pnl_pct = sum(t.pnl_pct or 0 for t in bt) / len(bt) if bt else 0
        if avg_pnl_pct > 2:
            score += 10
            reasons.append("High avg return per trade")
        elif avg_pnl_pct < -1:
            score -= 10
    else:
        score -= 5
        reasons.append("No backtest data")

    avg_daily_rsi = None
    rsi_vals = [v for v in [daily_rsi_1, daily_rsi_2] if v is not None]
    if rsi_vals:
        avg_daily_rsi = sum(rsi_vals) / len(rsi_vals)
        if avg_daily_rsi is not None:
            if 50 <= avg_daily_rsi <= 60:
                score += 15
                reasons.append(f"Daily RSI {avg_daily_rsi:.1f} (sweet spot)")
            elif 40 <= avg_daily_rsi <= 70:
                score += 5
                reasons.append(f"Daily RSI {avg_daily_rsi:.1f} (moderate)")
            elif avg_daily_rsi >= 80:
                score -= 15
                reasons.append(f"Daily RSI {avg_daily_rsi:.1f} (overbought)")
            elif avg_daily_rsi <= 30:
                score -= 10
                reasons.append(f"Daily RSI {avg_daily_rsi:.1f} (oversold)")

    avg_weekly_rsi = None
    rsi_w_vals = [v for v in [weekly_rsi_1, weekly_rsi_2] if v is not None]
    if rsi_w_vals:
        avg_weekly_rsi = sum(rsi_w_vals) / len(rsi_w_vals)
        if avg_weekly_rsi is not None:
            if 50 <= avg_weekly_rsi <= 65:
                score += 10
                reasons.append(f"Weekly RSI {avg_weekly_rsi:.1f} (uptrend)")
            elif avg_weekly_rsi > 75:
                score -= 10
                reasons.append(f"Weekly RSI {avg_weekly_rsi:.1f} (extended)")

    avg_vol = (volume_1 + volume_2) / 2 if volume_1 and volume_2 else (volume_1 or volume_2)
    if avg_vol >= 500000:
        score += 10
        reasons.append("High liquidity")
    elif avg_vol < 100000:
        score -= 10
        reasons.append("Low liquidity")

    grade = "A" if score >= 75 else "B" if score >= 60 else "C" if score >= 40 else "D"

    return {
        "symbol": symbol,
        "score": max(0, min(100, score)),
        "grade": grade,
        "reasons": reasons,
        "backtest_win_rate": round(len([t for t in bt if t.profit_loss and t.profit_loss > 0]) / len(bt) * 100, 1) if bt else None,
        "backtest_trades": len(bt),
        "backtest_total_pnl": round(sum(t.profit_loss or 0 for t in bt), 2) if bt else None,
        "daily_rsi_avg": round(avg_daily_rsi, 1) if avg_daily_rsi is not None else None,
        "weekly_rsi_avg": round(avg_weekly_rsi, 1) if avg_weekly_rsi is not None else None,
        "avg_volume": avg_vol,
    }
