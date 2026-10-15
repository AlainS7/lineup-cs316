"""Settlement: the scheduled join between pending legs and final games.

Step 1 grades every pending leg whose game is final, in one set-based SQL
UPDATE. Step 2 resolves every slip that no longer has pending legs, pays the
user, and records the transaction. Both run inside a single transaction so a
crash mid-way leaves nothing half-settled.
"""
from decimal import Decimal

from .odds import grade_slip

GRADE_LEGS_SQL = """
UPDATE SlipLegs sl
SET status = CASE l.market
        WHEN 'moneyline' THEN
            CASE WHEN g.home_score = g.away_score THEN 'push'
                 WHEN (l.side = 'home') = (g.home_score > g.away_score) THEN 'won'
                 ELSE 'lost' END
        WHEN 'spread' THEN
            CASE WHEN margin.v + sl.line_value = 0 THEN 'push'
                 WHEN margin.v + sl.line_value > 0 THEN 'won'
                 ELSE 'lost' END
        ELSE  -- total
            CASE WHEN g.home_score + g.away_score = sl.line_value THEN 'push'
                 WHEN (l.side = 'over') = (g.home_score + g.away_score > sl.line_value) THEN 'won'
                 ELSE 'lost' END
    END,
    settled_at = current_timestamp
FROM Lines l
JOIN Games g ON g.id = l.game_id
CROSS JOIN LATERAL (SELECT CASE WHEN l.side = 'home' THEN g.home_score - g.away_score
                                ELSE g.away_score - g.home_score END AS v) AS margin
WHERE sl.line_id = l.id AND sl.status = 'pending' AND g.status = 'final'
RETURNING sl.id, sl.slip_id, sl.status
"""

READY_SLIPS_SQL = """
SELECT s.id, s.user_id, s.stake,
       ARRAY_AGG(sl.status ORDER BY sl.id) AS leg_statuses,
       ARRAY_AGG(sl.odds_american ORDER BY sl.id) AS leg_odds
FROM BetSlips s
JOIN SlipLegs sl ON sl.slip_id = s.id
WHERE s.status = 'pending'
GROUP BY s.id
HAVING BOOL_AND(sl.status <> 'pending')
   OR BOOL_OR(sl.status = 'lost')     -- a lost leg loses the slip even if others are pending
"""


def settle(db):
    """Grade legs and resolve slips. Returns (legs_graded, slips_settled)."""
    with db.transaction() as conn:
        ex = lambda sql, **kw: db.execute_on(conn, sql, **kw)
        graded = ex(GRADE_LEGS_SQL)

        settled = 0
        for s in ex(READY_SLIPS_SQL):
            status, pay = grade_slip(s.leg_statuses, s.leg_odds, s.stake)
            if status == 'pending':
                continue
            ex("""
UPDATE BetSlips SET status = :status, payout = :payout, settled_at = current_timestamp
WHERE id = :id
""", id=s.id, status=status, payout=pay)
            if status == 'lost':
                # Remaining pending legs of a lost parlay are moot: void them.
                ex("""
UPDATE SlipLegs SET status = 'void', settled_at = current_timestamp
WHERE slip_id = :id AND status = 'pending'
""", id=s.id)
            if pay and pay > 0:
                ex("UPDATE Users SET balance = balance + :p WHERE id = :u", p=pay, u=s.user_id)
                ex("""
INSERT INTO BalanceTransactions(user_id, amount, kind, slip_id)
VALUES(:u, :p, :kind, :sid)
""", u=s.user_id, p=pay, kind='payout' if status == 'won' else 'refund', sid=s.id)
            settled += 1
        return len(graded), settled
