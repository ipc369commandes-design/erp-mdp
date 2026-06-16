from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# dossier backend/data
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DB_PATH = BASE_DIR / "data" / "erp.db"

# Créer le dossier data s'il n'existe pas
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

# ✅ FIX : Augmentation du timeout SQLite à 30 secondes pour éviter les blocages de concurrence
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30}
)

# ✅ FIX : Événement d'écoute SQLAlchemy pour forcer le mode WAL (Write-Ahead Logging)
# Cela permet d'exécuter des lectures et écritures en parallèle sur SQLite sans verrous
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()
print(f"DATABASE: {DB_PATH}")


def init_db():
    """Créer toutes les tables définies dans Base"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency pour injecter la session DB dans les routes FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()