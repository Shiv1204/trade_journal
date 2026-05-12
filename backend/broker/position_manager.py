from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Trade, TradeStatus, ExitReason
from backend.config import STOP_LOSS_PCT, TARGET_PCT, MAX_HOLDING_DAYS


class PositionManager:
    def __init__(self):
        self.kite = None

    def set_kite(self, kite_instance):
        self.kite = kite_instance

    def check_positions(self, db: Session | None = None) -> list[dict]:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        alerts = []
        try:
            open_trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()
            for trade in open_trades:
                alert = self._evaluate_trade(trade, db)
                if alert:
                    alerts.append(alert)
        finally:
            if close_db:
                db.close()

        return alerts

    def _evaluate_trade(self, trade: Trade, db: Session) -> dict | None:
        if not self.kite:
            ltp_data = self._get_ltp_fallback(trade.symbol)
        else:
            ltp_data = self._get_ltp_kite(trade.symbol)

        if ltp_data is None:
            return None

        current_price = ltp_data
        entry_price = trade.entry_price

        if entry_price == 0:
            return None

        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        days_held = (datetime.now(timezone.utc) - trade.entry_date).days

        should_exit = False
        exit_reason = None
        exit_price = current_price

        if pnl_pct <= -STOP_LOSS_PCT:
            should_exit = True
            exit_reason = ExitReason.STOP_LOSS
            exit_price = entry_price * (1 - STOP_LOSS_PCT / 100)
        elif pnl_pct >= TARGET_PCT:
            should_exit = True
            exit_reason = ExitReason.TARGET
            exit_price = entry_price * (1 + TARGET_PCT / 100)
        elif days_held >= MAX_HOLDING_DAYS:
            should_exit = True
            exit_reason = ExitReason.TIME

        if should_exit and trade.id:
            actual_pnl = (exit_price - entry_price) * trade.quantity
            actual_pnl_pct = ((exit_price - entry_price) / entry_price) * 100

            trade.status = TradeStatus.CLOSED
            trade.exit_price = round(exit_price, 2)
            trade.exit_date = datetime.now(timezone.utc)
            trade.profit_loss = round(actual_pnl, 2)
            trade.pnl_pct = round(actual_pnl_pct, 2)
            trade.exit_reason = exit_reason
            db.commit()

            return {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl_pct": round(actual_pnl_pct, 2),
                "profit_loss": round(actual_pnl, 2),
                "exit_reason": exit_reason.value,
                "days_held": days_held,
            }

        return None

    def _get_ltp_kite(self, symbol: str) -> float | None:
        try:
            ltp = self.kite.ltp(f"NSE:{symbol}")
            return ltp.get(f"NSE:{symbol}", {}).get("last_price")
        except Exception:
            return None

    def _get_ltp_fallback(self, symbol: str) -> float | None:
        import yfinance as yf
        try:
            ticker = yf.Ticker(symbol + ".NS")
            hist = ticker.history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception:
            pass
        return None
