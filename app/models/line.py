from flask import current_app as app


class Line:
    @staticmethod
    def get(id):
        rows = app.db.execute("""
SELECT l.id, l.game_id, l.book_id, l.market, l.side, l.line_value, l.odds_american,
       l.exposure_limit, l.is_open, b.name AS book_name,
       g.home_team, g.away_team, g.home_abbr, g.away_abbr, g.start_time, g.status AS game_status,
       e.exposure, e.pending_slips
FROM Lines l
JOIN Books b ON b.id = l.book_id
JOIN Games g ON g.id = l.game_id
JOIN LineExposure e ON e.line_id = l.id
WHERE l.id = :id
""", id=id)
        return rows[0] if rows else None

    @staticmethod
    def exists(game_id, book_id, market, side):
        return len(app.db.execute("""
SELECT 1 FROM Lines
WHERE game_id = :game_id AND book_id = :book_id AND market = :market AND side = :side
""", game_id=game_id, book_id=book_id, market=market, side=side)) > 0

    @staticmethod
    def create(game_id, book_id, market, side, line_value, odds_american, exposure_limit):
        rows = app.db.execute("""
INSERT INTO Lines(game_id, book_id, market, side, line_value, odds_american, exposure_limit)
VALUES(:game_id, :book_id, :market, :side, :line_value, :odds, :limit)
RETURNING id
""", game_id=game_id, book_id=book_id, market=market, side=side,
            line_value=line_value, odds=odds_american, limit=exposure_limit)
        return rows[0][0]

    @staticmethod
    def update(id, line_value, odds_american, exposure_limit, is_open):
        """Editing a line never touches SlipLegs: bets already placed keep the
        odds they locked in."""
        app.db.execute("""
UPDATE Lines SET line_value = :line_value, odds_american = :odds,
                 exposure_limit = :limit, is_open = :is_open,
                 updated_at = current_timestamp
WHERE id = :id
""", id=id, line_value=line_value, odds=odds_american, limit=exposure_limit, is_open=is_open)

    @staticmethod
    def set_open(id, is_open):
        app.db.execute("""
UPDATE Lines SET is_open = :is_open, updated_at = current_timestamp WHERE id = :id
""", id=id, is_open=is_open)

    @staticmethod
    def delete_if_unused(id):
        """A line with no legs against it can be removed outright; otherwise
        the book should close it instead. Returns True if deleted."""
        with app.db.transaction() as conn:
            if app.db.execute_on(conn, "SELECT 1 FROM SlipLegs WHERE line_id = :id LIMIT 1", id=id):
                return False
            app.db.execute_on(conn, "DELETE FROM CartItems WHERE line_id = :id", id=id)
            app.db.execute_on(conn, "DELETE FROM Lines WHERE id = :id", id=id)
            return True
