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
            if "kite_order_id" not in cols:
                conn.execute(text("ALTER TABLE trades ADD COLUMN kite_order_id VARCHAR(50)"))
                conn.commit()
            if "kite_sl_order_id" not in cols:
                conn.execute(text("ALTER TABLE trades ADD COLUMN kite_sl_order_id VARCHAR(50)"))
                conn.commit()
    if "alerts" not in inspector.get_table_names():
        from backend.models import Alert
        Alert.__table__.create(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
