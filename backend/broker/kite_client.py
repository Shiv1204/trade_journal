import hashlib
import json
import os
import time
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

from backend.config import (
    KITE_API_KEY, KITE_API_SECRET, KITE_USER_ID,
    KITE_PASSWORD, KITE_TOTP_KEY,
)

KITE_BASE = "https://api.kite.trade"
KITE_LOGIN = "https://kite.zerodha.com/connect/login"
SESSION_FILE = Path(__file__).resolve().parent.parent.parent / "kite_session.json"


def is_market_open() -> bool:
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    hour = now.hour
    minute = now.minute
    ist_hour = (hour + 5) % 24
    ist_minute = minute + 30
    if ist_minute >= 60:
        ist_hour = (ist_hour + 1) % 24
        ist_minute -= 60
    ist_total = ist_hour * 60 + ist_minute
    return 555 <= ist_total <= 930


class KiteClient:
    def __init__(self):
        self.api_key = KITE_API_KEY
        self.api_secret = KITE_API_SECRET
        self.user_id = KITE_USER_ID
        self.password = KITE_PASSWORD
        self.totp_key = KITE_TOTP_KEY
        self.access_token: str | None = None
        self.user_name: str | None = None
        self.connected = False
        self._load_session()

    def _load_session(self):
        if not SESSION_FILE.exists():
            return
        try:
            data = json.loads(SESSION_FILE.read_text())
            login_time = datetime.fromisoformat(data.get("login_time", ""))
            now = datetime.now(timezone.utc)
            if login_time.date() == now.date():
                self.access_token = data.get("access_token")
                self.user_name = data.get("user_name")
                self.connected = True
                print(f"[Kite] Restored session for {self.user_name}")
            else:
                print("[Kite] Stored session expired, need fresh login")
                SESSION_FILE.unlink(missing_ok=True)
        except Exception as e:
            print(f"[Kite] Failed to load session: {e}")

    def _save_session(self):
        try:
            SESSION_FILE.write_text(json.dumps({
                "access_token": self.access_token,
                "user_name": self.user_name,
                "login_time": datetime.now(timezone.utc).isoformat(),
            }))
        except Exception as e:
            print(f"[Kite] Failed to save session: {e}")

    def get_login_url(self, redirect_url: str = "http://localhost:8000/api/kite/callback") -> str:
        return f"{KITE_LOGIN}?v=3&api_key={self.api_key}"

    def generate_session(self, request_token: str) -> dict:
        checksum = hashlib.sha256(
            f"{self.api_key}{request_token}{self.api_secret}".encode()
        ).hexdigest()

        resp = requests.post(
            f"{KITE_BASE}/session/token",
            headers={"X-Kite-Version": "3"},
            data={
                "api_key": self.api_key,
                "request_token": request_token,
                "checksum": checksum,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("status") != "success":
            raise Exception(f"Session token exchange failed: {data}")

        session_data = data["data"]
        self.access_token = session_data["access_token"]
        self.user_name = session_data.get("user_name", "Unknown")
        self.connected = True
        self._save_session()
        return session_data

    def _headers(self) -> dict:
        return {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}",
        }

    def _ensure_connected(self):
        if not self.connected or not self.access_token:
            raise Exception("Kite not connected. Login first.")
        if not self._verify_token():
            self._invalidate_session()
            raise Exception("Kite session expired. Please login again.")

    def _api_get(self, path: str, params: dict | None = None, retries: int = 3) -> dict:
        last_err = None
        for attempt in range(retries):
            try:
                resp = requests.get(
                    f"{KITE_BASE}{path}",
                    headers=self._headers(),
                    params=params,
                    timeout=15,
                )
                if resp.status_code == 403:
                    self._invalidate_session()
                    raise Exception("Kite session expired")
                if resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                data = resp.json()
                if data.get("status") == "error":
                    raise Exception(data.get("message", "Kite API error"))
                return data
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    time.sleep(1 * (attempt + 1))
        raise last_err or Exception("Kite API request failed")

    def _api_post(self, path: str, data: dict, retries: int = 2) -> dict:
        last_err = None
        for attempt in range(retries):
            try:
                resp = requests.post(
                    f"{KITE_BASE}{path}",
                    headers=self._headers(),
                    data=data,
                    timeout=15,
                )
                if resp.status_code == 403:
                    self._invalidate_session()
                    raise Exception("Kite session expired")
                if resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                result = resp.json()
                if result.get("status") == "error":
                    raise Exception(result.get("message", "Kite API error"))
                return result
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    time.sleep(1 * (attempt + 1))
        raise last_err or Exception("Kite API request failed")

    def get_order_status(self, order_id: str) -> dict | None:
        self._ensure_connected()
        try:
            data = self._api_get("/orders/" + order_id)
            orders = data.get("data", [])
            return orders[0] if orders else None
        except Exception as e:
            print(f"[Kite] Order status error for {order_id}: {e}")
            return None

    def get_orders(self) -> list[dict]:
        self._ensure_connected()
        try:
            data = self._api_get("/orders")
            return data.get("data", [])
        except Exception as e:
            print(f"[Kite] Fetch orders error: {e}")
            return []

    def get_order_trades(self, order_id: str) -> list[dict]:
        self._ensure_connected()
        try:
            data = self._api_get(f"/orders/{order_id}/trades")
            return data.get("data", [])
        except Exception as e:
            print(f"[Kite] Order trades error for {order_id}: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        self._ensure_connected()
        try:
            self._api_post(f"/orders/regular/{order_id}", {})
            return True
        except Exception as e:
            print(f"[Kite] Cancel order error for {order_id}: {e}")
            return False

    def _verify_token(self) -> bool:
        try:
            resp = requests.get(
                f"{KITE_BASE}/user/profile",
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code == 403:
                print("[Kite] Token invalid (403), session expired")
                return False
            return resp.status_code == 200
        except Exception:
            return True

    def _invalidate_session(self):
        self.access_token = None
        self.user_name = None
        self.connected = False
        try:
            SESSION_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    def place_market_order(self, symbol: str, quantity: int, transaction_type: str) -> dict | None:
        self._ensure_connected()
        try:
            resp = requests.post(
                f"{KITE_BASE}/orders/regular",
                headers=self._headers(),
                data={
                    "tradingsymbol": symbol,
                    "exchange": "NSE",
                    "transaction_type": transaction_type,
                    "order_type": "MARKET",
                    "quantity": quantity,
                    "product": "CNC",
                    "validity": "DAY",
                },
                timeout=15,
            )
            data = resp.json()
            if data.get("status") != "success":
                print(f"Order failed: {data}")
                return None
            return {"order_id": data["data"]["order_id"], "symbol": symbol, "quantity": quantity, "type": transaction_type}
        except Exception as e:
            print(f"Order placement error for {symbol}: {e}")
            return None

    def place_limit_order(self, symbol: str, quantity: int, transaction_type: str, price: float) -> dict | None:
        self._ensure_connected()
        try:
            resp = requests.post(
                f"{KITE_BASE}/orders/regular",
                headers=self._headers(),
                data={
                    "tradingsymbol": symbol,
                    "exchange": "NSE",
                    "transaction_type": transaction_type,
                    "order_type": "LIMIT",
                    "quantity": quantity,
                    "price": price,
                    "product": "CNC",
                    "validity": "DAY",
                },
                timeout=15,
            )
            data = resp.json()
            if data.get("status") != "success":
                print(f"Order failed: {data}")
                return None
            return {"order_id": data["data"]["order_id"], "symbol": symbol, "quantity": quantity, "type": transaction_type}
        except Exception as e:
            print(f"Limit order error for {symbol}: {e}")
            return None

    def place_sl_order(self, symbol: str, quantity: int, sl_price: float) -> dict | None:
        self._ensure_connected()
        try:
            resp = requests.post(
                f"{KITE_BASE}/orders/regular",
                headers=self._headers(),
                data={
                    "tradingsymbol": symbol,
                    "exchange": "NSE",
                    "transaction_type": "SELL",
                    "order_type": "SL",
                    "quantity": quantity,
                    "price": round(sl_price, 2),
                    "trigger_price": round(sl_price, 2),
                    "product": "CNC",
                    "validity": "DAY",
                },
                timeout=15,
            )
            data = resp.json()
            if data.get("status") != "success":
                print(f"SL order failed: {data}")
                return None
            return {"order_id": data["data"]["order_id"], "symbol": symbol, "type": "SL"}
        except Exception as e:
            print(f"SL order error for {symbol}: {e}")
            return None

    def get_ltp(self, symbols: list[str]) -> dict[str, float]:
        self._ensure_connected()
        try:
            instruments = [f"NSE:{s}" for s in symbols]
            resp = requests.get(
                f"{KITE_BASE}/quote",
                headers=self._headers(),
                params={"i": instruments},
                timeout=10,
            )
            data = resp.json()
            if data.get("status") != "success":
                return {}
            result = {}
            for key, val in data.get("data", {}).items():
                symbol = key.replace("NSE:", "")
                result[symbol] = val.get("last_price", 0)
            return result
        except Exception as e:
            print(f"LTP fetch error: {e}")
            return {}

    def get_positions(self) -> list[dict]:
        self._ensure_connected()
        try:
            resp = requests.get(
                f"{KITE_BASE}/portfolio/positions",
                headers=self._headers(),
                timeout=10,
            )
            data = resp.json()
            if data.get("status") != "success":
                return []
            return data.get("data", {}).get("day", [])
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []

    def get_holdings(self) -> list[dict]:
        self._ensure_connected()
        try:
            resp = requests.get(
                f"{KITE_BASE}/portfolio/holdings",
                headers=self._headers(),
                timeout=10,
            )
            data = resp.json()
            if data.get("status") != "success":
                return []
            return data.get("data", [])
        except Exception as e:
            print(f"Error fetching holdings: {e}")
            return []

    def logout(self) -> bool:
        if not self.access_token:
            return True
        try:
            requests.delete(
                f"{KITE_BASE}/session/token",
                headers=self._headers(),
                params={"api_key": self.api_key, "access_token": self.access_token},
                timeout=10,
            )
        except Exception:
            pass
        self.access_token = None
        self.user_name = None
        self.connected = False
        try:
            SESSION_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return True
