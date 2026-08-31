from logging.config import fileConfig
import os
from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не задан")

# The project uses psycopg v3, not psycopg2. SQLAlchemy otherwise defaults
# to the psycopg2 dialect for a plain postgresql:// URL.
def _sqlalchemy_url(url: str) -> str:
    # Always force SQLAlchemy onto psycopg v3. This prevents the plain
    # postgresql:// dialect from selecting psycopg2 on Railway.
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"): ]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"): ]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url[len("postgresql+psycopg2://"): ]
    return url

SQLALCHEMY_URL = _sqlalchemy_url(DATABASE_URL)
config.set_main_option("sqlalchemy.url", SQLALCHEMY_URL.replace("%", "%%"))
target_metadata = None

def run_migrations_offline():
    context.configure(
        url=SQLALCHEMY_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
