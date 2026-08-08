from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# ENGINE: the core connection to Postgres, built from DATABASE_URL.
engine = create_engine(settings.database_url)

# SESSION: one "conversation" with the database.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# BASE: the parent class every model (table definition) will inherit from.
Base = declarative_base()

from contextlib import contextmanager


@contextmanager
def get_session():
    """Open a session, commit on success, roll back on error, always close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()