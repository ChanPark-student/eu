import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DEFAULT_POSTGRES_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/eu_ai_db"
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_POSTGRES_URL)
_is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
