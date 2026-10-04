"""Database connection configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine


def create_database_engine() -> Engine:
    """Create a connection pool using environment settings.

    Run local commands from the repository root to load its .env file.
    Existing environment variables take precedence.
    """
    load_dotenv(Path.cwd() / ".env", override=False)

    required = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]

    if missing:
        raise ValueError(
            "Missing database settings: " + ", ".join(missing)
        )

    port = int(os.getenv("POSTGRES_PORT", "5433"))

    if not 1 <= port <= 65535:
        raise ValueError("POSTGRES_PORT must be between 1 and 65535")

    url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=port,
        database=os.environ["POSTGRES_DB"],
    )

    return create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )