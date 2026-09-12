import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import DATABASE_URL

logger = logging.getLogger("diary")

_engine = None
SessionLocal = None
DB_IS_SQLITE = False


def init_db() -> None:
    """Подключается к PostgreSQL, а если он недоступен — к SQLite (для разработки)."""
    global _engine, SessionLocal, DB_IS_SQLITE
    connection_url = DATABASE_URL
    kwargs = {}

    if connection_url.startswith("sqlite"):
        DB_IS_SQLITE = True
        kwargs["connect_args"] = {"check_same_thread": False}
        logger.info("Используется SQLite: %s", connection_url)
    else:
        try:
            _engine = create_engine(connection_url, pool_pre_ping=True)
            with _engine.connect():
                pass
            DB_IS_SQLITE = False
            logger.info("Подключено к PostgreSQL")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "PostgreSQL недоступен (%s). Переключаюсь на SQLite для разработки.",
                exc,
            )
            DB_IS_SQLITE = True
            connection_url = "sqlite:///./college_diary.db"
            kwargs["connect_args"] = {"check_same_thread": False}
            _engine = None
            logger.info("Используется SQLite: %s", connection_url)

    if _engine is None:
        _engine = create_engine(connection_url, **kwargs)

    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()