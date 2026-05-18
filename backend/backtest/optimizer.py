from datetime import datetime, timedelta
from backend.backtest.engine import run_walk_forward_backtest


def run_parameter_sweep(
    symbols: list[str],
    backtest_days: int = 365,
    capital_per_trade: float = 100000,
    sl_range: tuple[float, float, float] = (2.0, 5.0, 1.0),
    target_range: tuple[float, float, float] = (4.0, 10.0, 2.0),
    max_hold_range: tuple[int, int, int] = (7, 21, 7),
) -> list[dict]:
    results = []

    sl = sl_range[0]
    while sl <= sl_range[1] + 0.01:
        tp = target_range[0]
        while tp <= target_range[1] + 0.01:
            mh = max_hold_range[0]
            while mh <= max_hold_range[1]:
                trades, summary = run_walk_forward_backtest(
                    symbols=symbols,
                    backtest_days=backtest_days,
                    capital_per_trade=capital_per_trade,
                    sl_pct=sl,
                    target_pct=tp,
                    max_hold_days=mh,
                )
                results.append({
                    **summary,
                    "trades": trades,
                    "params": f"SL={sl}% TGT={tp}% MAX={mh}d",
                })
                print(f"  [OPT] SL={sl}% TGT={tp}% MAX={mh}d  |  "
                      f"{summary['total_trades']} trades  win={summary['win_rate']}%  "
                      f"PNL=₹{summary['total_pnl']:.0f}  DD={summary['max_drawdown']}%")
                mh += max_hold_range[2]
            tp += target_range[2]
        sl += sl_range[2]

    results.sort(key=lambda r: (r["win_rate"], r["total_pnl"]), reverse=True)
    return results
