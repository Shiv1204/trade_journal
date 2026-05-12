import pyotp
from kiteconnect import KiteConnect
from datetime import datetime, timezone

from backend.config import (
    KITE_API_KEY, KITE_API_SECRET, KITE_USER_ID,
    KITE_PASSWORD, KITE_TOTP_KEY,
)


class KiteClient:
    def __init__(self):
        self.api_key = KITE_API_KEY
        self.api_secret = KITE_API_SECRET
        self.user_id = KITE_USER_ID
        self.password = KITE_PASSWORD
        self.totp_key = KITE_TOTP_KEY
        self.kite = None
        self.access_token = None

    def login(self) -> bool:
        if not all([self.api_key, self.api_secret, self.user_id, self.password, self.totp_key]):
            print("Kite credentials not configured")
            return False

        try:
            self.kite = KiteConnect(api_key=self.api_key)
            totp = pyotp.TOTP(self.totp_key).now()
            req_token = self.kite.login_url()
            print(f"Login URL: {req_token}")
            print("Kite login requires interactive OTP flow.")
            print("Set KITE_USER_ID, KITE_PASSWORD, KITE_TOTP_KEY in .env")
            return False
        except Exception as e:
            print(f"Kite login error: {e}")
            return False

    def place_market_order(self, symbol: str, quantity: int, transaction_type: str) -> dict | None:
        if not self.kite:
            print("Kite not logged in")
            return None
        try:
            order_id = self.kite.place_order(
                tradingsymbol=symbol,
                exchange="NSE",
                transaction_type=transaction_type,
                quantity=quantity,
                order_type="MARKET",
                product="CNC",
                variety="regular",
            )
            return {"order_id": order_id, "symbol": symbol, "quantity": quantity, "type": transaction_type}
        except Exception as e:
            print(f"Order placement error for {symbol}: {e}")
            return None

    def place_sl_order(self, symbol: str, quantity: int, sl_price: float) -> dict | None:
        if not self.kite:
            return None
        try:
            order_id = self.kite.place_order(
                tradingsymbol=symbol,
                exchange="NSE",
                transaction_type="SELL",
                quantity=quantity,
                order_type="SL",
                price=sl_price,
                trigger_price=sl_price,
                product="CNC",
                variety="regular",
            )
            return {"order_id": order_id, "symbol": symbol, "type": "SL"}
        except Exception as e:
            print(f"SL order error for {symbol}: {e}")
            return None

    def get_positions(self) -> list[dict]:
        if not self.kite:
            return []
        try:
            positions = self.kite.positions()
            return positions.get("day", [])
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []

    def get_holdings(self) -> list[dict]:
        if not self.kite:
            return []
        try:
            return self.kite.holdings()
        except Exception as e:
            print(f"Error fetching holdings: {e}")
            return []

    def get_historical_data(self, symbol: str, from_date: str, to_date: str, interval: str = "day") -> list:
        if not self.kite:
            return []
        try:
            data = self.kite.historical_data(
                instrument_token=self.kite.ltp(f"NSE:{symbol}"),
                from_date=from_date,
                to_date=to_date,
                interval=interval,
            )
            return data
        except Exception as e:
            print(f"Error fetching historical data for {symbol}: {e}")
            return []
