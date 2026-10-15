from flask import current_app as app


class Book:
    @staticmethod
    def get_by_owner(user_id):
        rows = app.db.execute("""
SELECT id, owner_id, name, default_exposure_limit, created_at
FROM Books WHERE owner_id = :user_id
""", user_id=user_id)
        return rows[0] if rows else None

    @staticmethod
    def get(id):
        rows = app.db.execute("""
SELECT b.id, b.owner_id, b.name, b.default_exposure_limit, b.created_at, u.full_name AS owner_name
FROM Books b JOIN Users u ON u.id = b.owner_id
WHERE b.id = :id
""", id=id)
        return rows[0] if rows else None

    @staticmethod
    def name_exists(name):
        return len(app.db.execute("SELECT 1 FROM Books WHERE name = :name", name=name)) > 0

    @staticmethod
    def create(owner_id, name, default_exposure_limit):
        rows = app.db.execute("""
INSERT INTO Books(owner_id, name, default_exposure_limit)
VALUES(:owner_id, :name, :limit)
RETURNING id
""", owner_id=owner_id, name=name, limit=default_exposure_limit)
        return rows[0][0]

    @staticmethod
    def update(id, name, default_exposure_limit):
        app.db.execute("""
UPDATE Books SET name = :name, default_exposure_limit = :limit WHERE id = :id
""", id=id, name=name, limit=default_exposure_limit)

    @staticmethod
    def lines(book_id, include_closed=True):
        """The book's lines with live exposure, soonest game first."""
        return app.db.execute("""
SELECT l.id, l.market, l.side, l.line_value, l.odds_american, l.exposure_limit,
       l.is_open, l.posted_at,
       g.id AS game_id, g.home_team, g.away_team, g.home_abbr, g.away_abbr,
       g.start_time, g.status AS game_status, g.home_score, g.away_score,
       e.exposure, e.pending_slips
FROM Lines l
JOIN Games g ON g.id = l.game_id
JOIN LineExposure e ON e.line_id = l.id
WHERE l.book_id = :book_id AND (:include_closed OR l.is_open)
ORDER BY (g.status = 'final'), g.start_time, g.id,
         CASE l.market WHEN 'moneyline' THEN 0 WHEN 'spread' THEN 1 ELSE 2 END, l.side
""", book_id=book_id, include_closed=include_closed)

    @staticmethod
    def pnl(book_id):
        """Settled profit/loss from the book's perspective, from every leg
        placed against its lines. Parlay stakes are attributed to the book
        of each leg in full, which is the conservative choice."""
        rows = app.db.execute("""
SELECT COUNT(DISTINCT s.id) AS slips,
       COALESCE(SUM(s.stake)  FILTER (WHERE s.status = 'lost'), 0) AS collected,
       COALESCE(SUM(s.payout - s.stake) FILTER (WHERE s.status = 'won'), 0) AS paid_out,
       COALESCE(SUM(s.potential_payout - s.stake) FILTER (WHERE s.status = 'pending'), 0) AS at_risk
FROM Lines l
JOIN SlipLegs sl ON sl.line_id = l.id
JOIN BetSlips s ON s.id = sl.slip_id
WHERE l.book_id = :book_id
""", book_id=book_id)
        return rows[0]

    @staticmethod
    def recent_action(book_id, limit=25):
        """Slips placed against this book's lines, most recent first."""
        return app.db.execute("""
SELECT DISTINCT s.id, s.kind, s.stake, s.potential_payout, s.status, s.placed_at,
       u.id AS user_id, u.full_name
FROM BetSlips s
JOIN Users u ON u.id = s.user_id
JOIN SlipLegs sl ON sl.slip_id = s.id
JOIN Lines l ON l.id = sl.line_id
WHERE l.book_id = :book_id
ORDER BY s.placed_at DESC, s.id DESC
LIMIT :limit
""", book_id=book_id, limit=limit)
