import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

KITE_API_KEY = os.getenv("KITE_API_KEY")
KITE_API_SECRET = os.getenv("KITE_API_SECRET")
KITE_USER_ID = os.getenv("KITE_USER_ID")
KITE_PASSWORD = os.getenv("KITE_PASSWORD")
KITE_TOTP_KEY = os.getenv("KITE_TOTP_KEY")

DB_PATH = "sqlite:///trade_journal.db"

STOP_LOSS_PCT = 2.0
TARGET_PCT = 5.0
MAX_HOLDING_DAYS = 10
CAPITAL_PER_TRADE = 50000

SCANNER_1_URL = "https://chartink.com/screener/copy-monthly-rsi-above-50-3672"
SCANNER_2_URL = "https://chartink.com/screener/top-scanner-combo"
SCANNER_1_NAME = "Monthly RSI Above 50"
SCANNER_2_NAME = "Top Scanner Combo"

BACKTEST_CASH_SEGMENT = True
MIN_MARKET_CAP = 500
MIN_VOLUME = 200000
MIN_CLOSE = 100
