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
