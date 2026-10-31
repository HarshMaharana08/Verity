from logging.config import fileConfig
from pathlib import Path

from alembic import context

from verity.config import ApplicationSettings
from verity.database import createDatabaseEngine
from verity.models import DatabaseBase


alembicConfiguration = context.config

if alembicConfiguration.config_file_name is not None:
    fileConfig(alembicConfiguration.config_file_name)

repositoryRoot = Path(__file__).resolve().parents[2]

applicationSettings = ApplicationSettings(
    _env_file=repositoryRoot / ".env",
    _env_file_encoding="utf-8",
)

targetMetadata = DatabaseBase.metadata


def runMigrationsOffline() -> None:
    databaseEngine = createDatabaseEngine(applicationSettings)

    try:
        context.configure(
            url=databaseEngine.url,
            target_metadata=targetMetadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()
    finally:
        databaseEngine.dispose()


def runMigrationsOnline() -> None:
    databaseEngine = createDatabaseEngine(applicationSettings)

    try:
        with databaseEngine.connect() as databaseConnection:
            context.configure(
                connection=databaseConnection,
                target_metadata=targetMetadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        databaseEngine.dispose()


if context.is_offline_mode():
    runMigrationsOffline()
else:
    runMigrationsOnline()