import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# Dossier backend/data
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "erp.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ✅ FIX : Détection dynamique de la base de données (Postgres sur Render, SQLite en local)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Les plateformes comme Render fournissent des URLs commençant par 'postgres://'
    # mais SQLAlchemy exige impérativement la syntaxe moderne 'postgresql://' [1].
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    DATABASE_URL = f"sqlite:///{DB_PATH}"

# Configuration de l'engine selon le type de base de données
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    # Mode WAL pour SQLite local
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
else:
    # Configuration optimisée pour PostgreSQL en production
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=300
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()
print(f"DATABASE CONNECTED: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()