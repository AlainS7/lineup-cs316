"""Integration tests run against a throwaway database named lineup_test,
created from db/create.sql + load.sql using the PG* environment variables."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEST_DB = "lineup_test"


@pytest.fixture(scope="session")
def app():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".flaskenv")
    os.environ["DB_NAME"] = TEST_DB
    os.environ.pop("SQLALCHEMY_DATABASE_URI", None)

    env = dict(os.environ)
    subprocess.run(["dropdb", "--if-exists", TEST_DB], env=env, check=True)
    subprocess.run(["createdb", TEST_DB], env=env, check=True)
    for f in ("create.sql", "load.sql"):
        subprocess.run(
            ["psql", "-v", "ON_ERROR_STOP=1", "-q", "-d", TEST_DB, "-f", f],
            cwd=ROOT / "db",
            env=env,
            check=True,
        )

    import importlib
    import config

    importlib.reload(config)
    from app import create_app

    application = create_app(config.Config)
    application.config["WTF_CSRF_ENABLED"] = False
    application.config["TESTING"] = True

    # Keep upcoming test games in the future regardless of today's date.
    application.db.execute("""
        UPDATE Games
        SET start_time = CURRENT_TIMESTAMP + INTERVAL '7 days'
        WHERE status = 'scheduled'
    """)

    yield application
    application.db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email, password="password"):
    return client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=True
    )
