import os


class Config:
    """Flask configuration. Everything is read from the environment so the
    same code runs inside the course container (where PGHOST=postgres) and on
    a laptop (where the compose file maps Postgres to a random local port)."""

    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-change-me')

    DB_USER = os.environ.get('PGUSER', 'ubuntu')
    DB_PASSWORD = os.environ.get('PGPASSWORD', '')
    DB_HOST = os.environ.get('PGHOST', 'localhost')
    DB_PORT = os.environ.get('PGPORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'lineup')

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'SQLALCHEMY_DATABASE_URI',
        f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}',
    )

    # Starting virtual balance for a brand-new account.
    STARTING_BALANCE = 1000.00
    # Name of the house book that ingested ESPN lines are posted under.
    HOUSE_BOOK_NAME = 'Consensus'
