from sqlalchemy import URL, Engine, create_engine

from verity.config import ApplicationSettings


def createDatabaseEngine(
    applicationSettings: ApplicationSettings,
) -> Engine:
    databaseUrl = URL.create(
        drivername="postgresql+psycopg",
        username=applicationSettings.postgresUsername,
        password=applicationSettings.postgresPassword.get_secret_value(),
        host=applicationSettings.postgresHost,
        port=applicationSettings.postgresPort,
        database=applicationSettings.postgresDatabase,
    )

    return create_engine(
        databaseUrl,
        pool_pre_ping=True,
        pool_timeout=5,
        connect_args={"connect_timeout": 5},
    )