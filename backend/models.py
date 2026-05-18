from sqlalchemy import Column, Integer, Float, String, DateTime, Enum as SAEnum
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from backend.database import Base

class TradeStatus(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"

class ExitReason(enum.Enum):
    STOP_LOSS = "sl"
    TARGET = "target"
    TIME_EXIT = "time"
    MANUAL = "manual"

class ScannerRun(Base):
    __tablename__ = "scanner_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scanner_name = Column(String(100), nullable=False)
    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    stock_count = Column(Integer, default=0)

    results = relationship("ScannerResult", back_populates="run", cascade="all, delete-orphan")

class ScannerResult(Base):
    __tablename__ = "scanner_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("scanner_runs.id"), nullable=False)
    symbol = Column(String(50), nullable=False)
    price = Column(Float, nullable=True)
    scanner_name = Column(String(100), nullable=False)
    change_pct = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    daily_rsi = Column(Float, nullable=True)
    weekly_rsi = Column(Float, nullable=True)

    run = relationship("ScannerRun", back_populates="results")

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)
    entry_date = Column(DateTime, nullable=False)
    exit_date = Column(DateTime, nullable=True)
    profit_loss = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    status = Column(SAEnum(TradeStatus), default=TradeStatus.OPEN)
    exit_reason = Column(SAEnum(ExitReason), nullable=True)
    scanner_name = Column(String(100), nullable=True)
    kite_order_id = Column(String(50), nullable=True)
    kite_sl_order_id = Column(String(50), nullable=True)

class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scanner_name = Column(String(100), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)
    total_pnl = Column(Float, nullable=True)
    avg_profit = Column(Float, nullable=True)
    avg_loss = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    sl_pct = Column(Float, nullable=True)
    target_pct = Column(Float, nullable=True)
    max_hold_days = Column(Integer, nullable=True)
    capital_per_trade = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    trades = relationship("BacktestTrade", back_populates="run", cascade="all, delete-orphan")

class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    backtest_run_id = Column(Integer, ForeignKey("backtest_runs.id"), nullable=False)
    symbol = Column(String(50), nullable=False)
    entry_date = Column(DateTime, nullable=False)
    exit_date = Column(DateTime, nullable=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)
    profit_loss = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    exit_reason = Column(SAEnum(ExitReason), nullable=True)

    run = relationship("BacktestRun", back_populates="trades")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    alert_type = Column(String(30), nullable=False)
    message = Column(String(500), nullable=False)
    trade_id = Column(Integer, nullable=True)
    symbol = Column(String(50), nullable=True)


class StockUniverse(Base):
    __tablename__ = "stock_universe"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=True)
    last_price = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class StockCache(Base):
    __tablename__ = "stock_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    date = Column(DateTime, nullable=False)
    open = Column(Float, default=0)
    high = Column(Float, default=0)
    low = Column(Float, default=0)
    close = Column(Float, default=0)
    volume = Column(Integer, default=0)
    rsi_daily = Column(Float, nullable=True)
    rsi_weekly = Column(Float, nullable=True)
    rsi_monthly = Column(Float, nullable=True)
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    adx = Column(Float, nullable=True)
    plus_di = Column(Float, nullable=True)
    minus_di = Column(Float, nullable=True)
    avg_volume_20d = Column(Float, nullable=True)
    atr = Column(Float, nullable=True)
