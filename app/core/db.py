from sqlalchemy        import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm    import Session as SessionType, sessionmaker

from app.core.config import settings

database_url = URL.create(
    drivername = settings.DB_DIALECT
    , username = settings.DB_USER
    , password = settings.DB_PASS
    , host     = settings.DB_HOST
    , port     = int(settings.DB_PORT)
    , database = settings.DB_NAME
    , query    = {"sslmode": settings.DB_SSL}
)

engine = create_engine(
    database_url
    , pool_size     = 4
    , max_overflow  = 2
    , pool_timeout  = 15
    , pool_recycle  = 1800
    , pool_pre_ping = True
    , connect_args  = {"connect_timeout": 5}
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
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def getStaticSession() -> SessionType:
    """Return a standalone SQLAlchemy session (caller must close it)."""
    return Session()
