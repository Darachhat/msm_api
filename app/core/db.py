from sqlalchemy     import create_engine
from sqlalchemy.orm import Session as SessionType, sessionmaker

from app.core.config import settings

engine = create_engine(
    f"{settings.DB_DIALECT}://{settings.DB_USER}:{settings.DB_PASS}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?sslmode={settings.DB_SSL}"
    , pool_size     = 10
    , max_overflow  = 5
    , pool_timeout  = 10
    , pool_recycle  = 1800
    , pool_pre_ping = True
    , echo          = False
)

Session = sessionmaker(
    bind         = engine
    , autocommit = False
    , autoflush  = False
)


def getSession():
    session = Session()
    try:
        yield session
    finally:
        session.close()


def getStaticSession() -> SessionType:
    """Return a standalone SQLAlchemy session (caller must close it)."""
    return Session()
