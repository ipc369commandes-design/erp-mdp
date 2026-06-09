from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# dossier backend/data
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DB_PATH = BASE_DIR / "data" / "erp.db"

# Créer le dossier data s'il n'existe pas
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

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
