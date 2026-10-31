from collections.abc import Generator

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session


def getDatabaseSession(
    request: Request,
) -> Generator[Session, None, None]:
    databaseEngine: Engine = request.app.state.databaseEngine

    with Session(
        bind=databaseEngine,
        expire_on_commit=False,
    ) as databaseSession:
        yield databaseSession