from sqlalchemy import create_engine, text


class DB:
    """Thin wrapper over a SQLAlchemy engine. All SQL in the project goes
    through text() with named parameters, which is what protects against SQL
    injection: user input is never concatenated into a query string."""

    def __init__(self, app):
        self.engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])

    def execute(self, sqlstr, **kwargs):
        """Run one statement in its own transaction and return the rows (an
        empty list for statements that return nothing)."""
        with self.engine.begin() as conn:
            return self.execute_on(conn, sqlstr, **kwargs)

    @staticmethod
    def execute_on(conn, sqlstr, **kwargs):
        """Run a statement on an existing connection/transaction."""
        result = conn.execute(text(sqlstr), kwargs)
        return result.fetchall() if result.returns_rows else []

    def transaction(self):
        """Context manager yielding a connection inside a transaction; use
        with execute_on for multi-statement operations such as placing a bet
        slip or settling results."""
        return self.engine.begin()
