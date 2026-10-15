from alembic import context
from gef.db import Base, engine
from gef import models

target_metadata = Base.metadata
if context.is_offline_mode():
    from gef.config import settings
    context.configure(url=settings().database_url, target_metadata=target_metadata, literal_binds=True, dialect_opts={'paramstyle':'named'})
    with context.begin_transaction(): context.run_migrations()
else:
    with engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction(): context.run_migrations()
