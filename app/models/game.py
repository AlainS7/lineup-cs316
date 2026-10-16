from flask import current_app as app


class Game:
    SORTS = {
        'time': 'g.start_time ASC, g.id',
        'time_desc': 'g.start_time DESC, g.id',
        'sport': 's.name, g.start_time, g.id',
        'lines': 'line_count DESC, g.start_time, g.id',
    }

    @staticmethod
    def sports():
        return app.db.execute("SELECT id, key, name FROM Sports ORDER BY name")

    @staticmethod
    def browse(sport=None, q=None, status='upcoming', sort='time', limit=100, offset=0,
               has_lines=True):
        """Game list for the home page. status: upcoming | final | all.
        Each row carries the number of open lines and the best (highest)
        moneyline odds on each team across all books. has_lines drops
        scheduled games with nothing left to bet on; games that already
        started are kept either way, since their lines are always closed."""
        order = Game.SORTS.get(sort, Game.SORTS['time'])
        status_clause = {
            'upcoming': "AND g.status IN ('scheduled', 'in_progress')",
            'final': "AND g.status = 'final'",
            'all': '',
        }.get(status, '')
        return app.db.execute(f"""
SELECT g.id, s.key AS sport_key, s.name AS sport, g.home_team, g.away_team,
       g.home_abbr, g.away_abbr, g.start_time, g.status, g.home_score, g.away_score,
       COUNT(l.id) FILTER (WHERE l.is_open) AS line_count,
       MAX(l.odds_american) FILTER (WHERE l.market = 'moneyline' AND l.side = 'home' AND l.is_open) AS home_ml,
       MAX(l.odds_american) FILTER (WHERE l.market = 'moneyline' AND l.side = 'away' AND l.is_open) AS away_ml,
       COUNT(DISTINCT l.book_id) AS book_count
FROM Games g
JOIN Sports s ON s.id = g.sport_id
LEFT JOIN Lines l ON l.game_id = g.id
WHERE (:sport IS NULL OR s.key = :sport)
  AND (:q IS NULL OR g.home_team ILIKE '%' || :q || '%' OR g.away_team ILIKE '%' || :q || '%'
       OR g.home_abbr ILIKE '%' || :q || '%' OR g.away_abbr ILIKE '%' || :q || '%')
  {status_clause}
GROUP BY g.id, s.id
HAVING NOT :has_lines OR g.status <> 'scheduled'
    OR COUNT(l.id) FILTER (WHERE l.is_open) > 0
ORDER BY {order}
LIMIT :limit OFFSET :offset
""", sport=sport or None, q=q or None, limit=limit, offset=offset,
             has_lines=has_lines)

    @staticmethod
    def get(id):
        rows = app.db.execute("""
SELECT g.id, s.key AS sport_key, s.name AS sport, g.home_team, g.away_team,
       g.home_abbr, g.away_abbr, g.start_time, g.status, g.home_score, g.away_score,
       g.external_id
FROM Games g JOIN Sports s ON s.id = g.sport_id
WHERE g.id = :id
""", id=id)
        return rows[0] if rows else None

    @staticmethod
    def lines(game_id):
        """All lines on a game with each book's name and current exposure,
        grouped by market then side so the template can lay them out."""
        return app.db.execute("""
SELECT l.id, l.market, l.side, l.line_value, l.odds_american, l.exposure_limit,
       l.is_open, b.id AS book_id, b.name AS book_name,
       e.exposure, e.pending_slips
FROM Lines l
JOIN Books b ON b.id = l.book_id
JOIN LineExposure e ON e.line_id = l.id
WHERE l.game_id = :game_id
ORDER BY CASE l.market WHEN 'moneyline' THEN 0 WHEN 'spread' THEN 1 ELSE 2 END,
         CASE l.side WHEN 'away' THEN 0 WHEN 'home' THEN 1 WHEN 'over' THEN 2 ELSE 3 END,
         l.odds_american DESC, b.name
""", game_id=game_id)

    @staticmethod
    def upcoming_for_book(limit=50):
        """Games a book can still post lines on."""
        return app.db.execute("""
SELECT g.id, s.name AS sport, g.home_team, g.away_team, g.home_abbr, g.away_abbr, g.start_time
FROM Games g JOIN Sports s ON s.id = g.sport_id
WHERE g.status = 'scheduled' AND g.start_time > current_timestamp
ORDER BY g.start_time
LIMIT :limit
""", limit=limit)

    @staticmethod
    def set_final(game_id, home_score, away_score):
        """Manually record a final score (used for demos and tests; the
        ingest job does the same from live API data)."""
        app.db.execute("""
UPDATE Games SET status = 'final', home_score = :h, away_score = :a,
                 updated_at = current_timestamp
WHERE id = :id
""", id=game_id, h=home_score, a=away_score)
