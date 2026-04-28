from typing import Generator

from sqlalchemy import create_engine
try:
    from sqlalchemy.orm import Session, declarative_base, sessionmaker
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base  # type: ignore
    from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import settings

Base = declarative_base()


connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
