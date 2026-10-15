from functools import lru_cache
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
from .config import settings
from .errors import AppError

class Base(DeclarativeBase):
    pass

@lru_cache
def engine():
    cfg = settings()
    problem = cfg.problem()
    if problem:
        raise AppError(problem, 503)
    url = cfg.database_url
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    kwargs = {'poolclass': NullPool, 'pool_pre_ping': True}
    if url.startswith('sqlite'):
        kwargs['connect_args'] = {'check_same_thread': False}
    else:
        kwargs['connect_args'] = {'connect_timeout': 5, 'options': '-c statement_timeout=10000'}
    obj = create_engine(url, **kwargs)
    if url.startswith('sqlite'):
        @event.listens_for(obj, 'connect')
        def sqlite_foreign_keys(connection, record):
            connection.execute('PRAGMA foreign_keys=ON')
    return obj

def new_session():
    return sessionmaker(bind=engine(), expire_on_commit=False)()

def get_db():
    with new_session() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise
