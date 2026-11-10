from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session

DATABASE_URL = "sqlite:///./daylight.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    previous_autocommit = dbapi_connection.autocommit
    dbapi_connection.autocommit = True

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

    dbapi_connection.autocommit = previous_autocommit


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session