from sqlalchemy import create_engine, URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings


def _build_engine():
    # Prefer individual DB_ vars to avoid URL-encoding issues with special chars in passwords.
    # Fall back to DATABASE_URL if the individual vars are not set.
    if settings.db_host and settings.db_name and settings.db_user and settings.db_password:
        url = URL.create(
            drivername="postgresql+psycopg2",
            username=settings.db_user,
            password=settings.db_password,  # SQLAlchemy handles encoding automatically
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
        )
        return create_engine(url)
    if settings.database_url:
        return create_engine(settings.database_url)
    raise RuntimeError(
        "Database not configured: set DB_HOST/DB_NAME/DB_USER/DB_PASSWORD "
        "or DATABASE_URL in environment."
    )


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
