from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.config import DB_PATH

engine = create_engine(DB_PATH, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def init_db():
    import backend.models
    Base.metadata.create_all(bind=engine)
    _migrate()

def _migrate():
    inspector = inspect(engine)
    if "trades" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("trades")}
        with engine.connect() as conn:
            for col_name in ["kite_order_id", "kite_sl_order_id"]:
                if col_name not in cols:
                    conn.execute(text(f"ALTER TABLE trades ADD COLUMN {col_name} VARCHAR(50)"))
                    conn.commit()
    if "backtest_runs" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("backtest_runs")}
        with engine.connect() as conn:
            for col_name, col_type in [
                ("sl_pct", "FLOAT"),
                ("target_pct", "FLOAT"),
                ("max_hold_days", "INTEGER"),
                ("capital_per_trade", "FLOAT"),
            ]:
                if col_name not in cols:
                    conn.execute(text(f"ALTER TABLE backtest_runs ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
    if "alerts" not in inspector.get_table_names():
        from backend.models import Alert
        Alert.__table__.create(bind=engine)
    if "stock_universe" not in inspector.get_table_names():
        from backend.models import StockUniverse
        StockUniverse.__table__.create(bind=engine)
    if "stock_cache" not in inspector.get_table_names():
        from backend.models import StockCache
        StockCache.__table__.create(bind=engine)
    if "stock_cache" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("stock_cache")}
        with engine.connect() as conn:
            if "atr" not in cols:
                conn.execute(text("ALTER TABLE stock_cache ADD COLUMN atr FLOAT"))
                conn.commit()
    if "stock_universe" in inspector.get_table_names():
        from backend.models import StockUniverse
        db = SessionLocal()
        try:
            count = db.query(StockUniverse).count()
            if count == 0:
                print("[DB] Universe empty — build on startup or call /api/scanner/universe/build")
        finally:
            db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
