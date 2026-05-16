from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Trade, TradeStatus, ExitReason
from backend.config import STOP_LOSS_PCT, TARGET_PCT, MAX_HOLDING_DAYS
from backend.config import TRAIL_BREAKEVEN_PCT, TRAIL_TRIGGER_PCT, TRAIL_STEP_PCT
from backend.broker.kite_client import is_market_open


class PositionManager:
    def __init__(self):
        self.kite_client = None

    def set_kite(self, kite_client):
        self.kite_client = kite_client

    def check_positions(self, db: Session | None = None) -> list[dict]:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        alerts = []
        try:
            open_trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()
            if not open_trades:
                return alerts

            symbols = list({t.symbol for t in open_trades})
            ltp_map = self._get_ltp_batch(symbols)

            self._manage_sl_orders(open_trades, db)

            for trade in open_trades:
                db.refresh(trade)
                if trade.status != TradeStatus.OPEN:
                    continue
                alert = self._evaluate_trade(trade, ltp_map, db)
                if alert:
                    alerts.append(alert)
        finally:
            if close_db:
                db.close()

        return alerts

    def _manage_sl_orders(self, open_trades: list, db: Session):
        if not self.kite_client or not self.kite_client.connected:
            return
        if not is_market_open():
            return

        try:
            kite_orders = self.kite_client.get_orders()
            kite_order_map = {o.get("order_id", ""): o for o in kite_orders}
        except Exception as e:
            print(f"[PM] Failed to fetch Kite orders: {e}")
            return

        for trade in open_trades:
            sl_id = trade.kite_sl_order_id
            if sl_id and sl_id in kite_order_map:
                sl_order = kite_order_map[sl_id]
                status = sl_order.get("status", "")
                if status == "COMPLETE":
                    print(f"[PM] SL order filled for {trade.symbol}")
                    trade.status = TradeStatus.CLOSED
                    trade.exit_reason = ExitReason.STOP_LOSS
                    trade.exit_price = float(sl_order.get("average_price", trade.entry_price * (1 - STOP_LOSS_PCT / 100)))
                    trade.exit_date = sl_order.get("exchange_update_timestamp") or datetime.now(timezone.utc)
                    if trade.exit_price and trade.entry_price:
                        pnl_pct = ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100
                        trade.pnl_pct = round(pnl_pct, 2)
                        trade.profit_loss = round((trade.exit_price - trade.entry_price) * trade.quantity, 2)
                    from backend.models import Alert
                    alert = Alert(
                        alert_type="sl",
                        message=f"{trade.symbol} SL filled | P&L: ₹{trade.profit_loss:.0f} ({trade.pnl_pct:.1f}%)",
                        trade_id=trade.id,
                        symbol=trade.symbol,
                    )
                    db.add(alert)
                    db.commit()
                    continue
                elif status in ("CANCELLED", "REJECTED", "TRIGGER_PENDING"):
                    sl_price = round(trade.entry_price * (1 - STOP_LOSS_PCT / 100), 2)
                    try:
                        new_sl = self.kite_client.place_sl_order(trade.symbol, trade.quantity, sl_price)
                        if new_sl:
                            trade.kite_sl_order_id = new_sl["order_id"]
                            db.commit()
                            print(f"[PM] Replaced SL order for {trade.symbol}: {new_sl['order_id']}")
                    except Exception as e:
                        print(f"[PM] SL replace error for {trade.symbol}: {e}")
            elif not sl_id and is_market_open():
                sl_price = round(trade.entry_price * (1 - STOP_LOSS_PCT / 100), 2)
                try:
                    new_sl = self.kite_client.place_sl_order(trade.symbol, trade.quantity, sl_price)
                    if new_sl:
                        trade.kite_sl_order_id = new_sl["order_id"]
                        db.commit()
                        print(f"[PM] Placed SL order for {trade.symbol}: {new_sl['order_id']}")
                except Exception as e:
                    print(f"[PM] SL placement error for {trade.symbol}: {e}")

        ltp_map = {}
        symbols = list({t.symbol for t in open_trades})
        if self.kite_client and self.kite_client.connected:
            try:
                ltp_map = self.kite_client.get_ltp(symbols)
            except Exception:
                pass
        if not ltp_map:
            for t in open_trades:
                ltp = self._get_ltp_fallback(t.symbol)
                if ltp:
                    ltp_map[t.symbol] = ltp

        for trade in open_trades:
            sl_id = trade.kite_sl_order_id
            if not sl_id or sl_id not in kite_order_map or trade.status != TradeStatus.OPEN:
                continue
            sl_order = kite_order_map[sl_id]
            status = sl_order.get("status", "")
            if status not in ("OPEN", "TRIGGER_PENDING"):
                continue

            current_price = ltp_map.get(trade.symbol)
            if not current_price or current_price <= 0 or not trade.entry_price:
                continue

            pnl_pct = ((current_price - trade.entry_price) / trade.entry_price) * 100
            current_sl_price = float(sl_order.get("trigger_price", 0))
            new_sl_price = None

            if pnl_pct >= TRAIL_TRIGGER_PCT:
                new_sl_price = current_price * (1 - TRAIL_STEP_PCT / 100)
            elif pnl_pct >= TRAIL_BREAKEVEN_PCT:
                new_sl_price = max(trade.entry_price, current_price * (1 - TRAIL_STEP_PCT / 100))

            if new_sl_price and new_sl_price > current_sl_price + 0.5:
                try:
                    self.kite_client.cancel_order(sl_id)
                    new_sl = self.kite_client.place_sl_order(trade.symbol, trade.quantity, round(new_sl_price, 2))
                    if new_sl:
                        trade.kite_sl_order_id = new_sl["order_id"]
                        db.commit()
                        print(f"[PM] Trailed SL for {trade.symbol}: {current_sl_price:.1f} -> {new_sl_price:.1f}")
                except Exception as e:
                    print(f"[PM] Trailing SL error for {trade.symbol}: {e}")

    def _get_ltp_batch(self, symbols: list[str]) -> dict[str, float]:
        if self.kite_client and self.kite_client.connected:
            try:
                return self.kite_client.get_ltp(symbols)
            except Exception as e:
                print(f"Kite LTP batch error: {e}")

        result = {}
        for symbol in symbols:
            ltp = self._get_ltp_fallback(symbol)
            if ltp is not None:
                result[symbol] = ltp
        return result

    def _evaluate_trade(self, trade: Trade, ltp_map: dict[str, float], db: Session) -> dict | None:
        current_price = ltp_map.get(trade.symbol)
        if current_price is None or current_price <= 0:
            return None

        entry_price = trade.entry_price
        if entry_price == 0:
            return None

        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        entry_date_aware = trade.entry_date
        if entry_date_aware.tzinfo is None:
            from datetime import timezone as tz
            entry_date_aware = entry_date_aware.replace(tzinfo=tz.utc)
        days_held = (datetime.now(timezone.utc) - entry_date_aware).days

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
            exit_reason = ExitReason.TIME_EXIT
            exit_price = current_price

        if should_exit and trade.id:
            if self.kite_client and self.kite_client.connected:
                try:
                    order = self.kite_client.place_market_order(
                        trade.symbol, trade.quantity, "SELL"
                    )
                    if order:
                        print(f"[Exit] Placed SELL order for {trade.symbol}: {order['order_id']}")
                    else:
                        print(f"[Exit] Failed to place SELL order for {trade.symbol}, exiting anyway")
                except Exception as e:
                    print(f"[Exit] Kite order error for {trade.symbol}: {e}")

            actual_pnl = (exit_price - entry_price) * trade.quantity
            actual_pnl_pct = ((exit_price - entry_price) / entry_price) * 100

            trade.status = TradeStatus.CLOSED
            trade.exit_price = round(exit_price, 2)
            trade.exit_date = datetime.now(timezone.utc)
            trade.profit_loss = round(actual_pnl, 2)
            trade.pnl_pct = round(actual_pnl_pct, 2)
            trade.exit_reason = exit_reason
            db.commit()

            from backend.models import Alert
            reason_label = exit_reason.value if exit_reason else "unknown"
            alert = Alert(
                alert_type=reason_label,
                message=f"{trade.symbol} exited: {reason_label.upper()} | P&L: ₹{trade.profit_loss:.0f} ({trade.pnl_pct:.1f}%)",
                trade_id=trade.id,
                symbol=trade.symbol,
            )
            db.add(alert)
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
