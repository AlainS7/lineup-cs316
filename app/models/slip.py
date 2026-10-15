"""Bet slip: the persistent cart (CartItems) and placed bets (BetSlips)."""
from decimal import Decimal

from flask import current_app as app

from ..odds import american_to_decimal, parlay_decimal, payout


class SlipError(Exception):
    """Raised when a slip cannot be placed; the message is shown to the user."""


class Cart:
    @staticmethod
    def items(user_id):
        """Cart items with the current state of each line, so the page can
        warn if a line closed or its game started since it was added."""
        return app.db.execute("""
SELECT c.line_id, c.stake, c.added_at,
       l.market, l.side, l.line_value, l.odds_american, l.is_open, l.exposure_limit,
       b.name AS book_name,
       g.id AS game_id, g.home_team, g.away_team, g.home_abbr, g.away_abbr,
       g.start_time, g.status AS game_status,
       e.exposure
FROM CartItems c
JOIN Lines l ON l.id = c.line_id
JOIN Books b ON b.id = l.book_id
JOIN Games g ON g.id = l.game_id
JOIN LineExposure e ON e.line_id = l.id
WHERE c.user_id = :user_id
ORDER BY c.added_at, c.line_id
""", user_id=user_id)

    @staticmethod
    def count(user_id):
        return app.db.execute("SELECT COUNT(*) FROM CartItems WHERE user_id = :u", u=user_id)[0][0]

    @staticmethod
    def add(user_id, line_id, stake):
        app.db.execute("""
INSERT INTO CartItems(user_id, line_id, stake) VALUES(:u, :l, :s)
ON CONFLICT (user_id, line_id) DO UPDATE SET stake = EXCLUDED.stake
""", u=user_id, l=line_id, s=stake)

    @staticmethod
    def set_stake(user_id, line_id, stake):
        app.db.execute("""
UPDATE CartItems SET stake = :s WHERE user_id = :u AND line_id = :l
""", u=user_id, l=line_id, s=stake)

    @staticmethod
    def remove(user_id, line_id):
        app.db.execute("DELETE FROM CartItems WHERE user_id = :u AND line_id = :l", u=user_id, l=line_id)

    @staticmethod
    def clear(user_id):
        app.db.execute("DELETE FROM CartItems WHERE user_id = :u", u=user_id)


class Slip:
    @staticmethod
    def place(user_id, kind, parlay_stake=None):
        """Submit the user's cart as bets.

        kind='single': one BetSlip per cart item, each with its own stake.
        kind='parlay': one BetSlip whose legs are every cart item and whose
                       stake is parlay_stake; all legs must win.

        Everything happens in one transaction. The lines involved are locked
        with SELECT ... FOR UPDATE so two users betting the same line at once
        cannot both squeeze under the book's exposure limit. Odds and line
        values are copied onto SlipLegs so later edits by the book do not
        change what was locked in.
        """
        with app.db.transaction() as conn:
            ex = lambda sql, **kw: app.db.execute_on(conn, sql, **kw)

            user = ex("SELECT balance FROM Users WHERE id = :u FOR UPDATE", u=user_id)
            if not user:
                raise SlipError('Unknown user.')
            balance = Decimal(user[0][0])

            items = ex("""
SELECT c.line_id, c.stake, l.odds_american, l.line_value, l.is_open, l.exposure_limit,
       l.game_id, g.status AS game_status, g.start_time, g.home_abbr, g.away_abbr,
       l.market, l.side
FROM CartItems c
JOIN Lines l ON l.id = c.line_id
JOIN Games g ON g.id = l.game_id
WHERE c.user_id = :u
ORDER BY c.added_at, c.line_id
FOR UPDATE OF l
""", u=user_id)
            if not items:
                raise SlipError('Your bet slip is empty.')

            now = ex("SELECT current_timestamp")[0][0]
            for it in items:
                label = f'{it.home_abbr}/{it.away_abbr} {it.market} {it.side}'
                if not it.is_open:
                    raise SlipError(f'The line {label} is closed. Remove it from your slip.')
                if it.game_status != 'scheduled' or it.start_time <= now:
                    raise SlipError(f'The game for {label} has already started.')

            # Build the slips to insert: list of (stake, potential_payout, legs)
            if kind == 'parlay':
                if len(items) < 2:
                    raise SlipError('A parlay needs at least two legs.')
                games = [it.game_id for it in items]
                if len(set(games)) != len(games):
                    raise SlipError('A parlay cannot include two legs from the same game.')
                stake = Decimal(parlay_stake or 0)
                if stake <= 0:
                    raise SlipError('Enter a stake for the parlay.')
                dec = parlay_decimal([it.odds_american for it in items])
                slips = [(stake, payout(stake, dec), list(items))]
            elif kind == 'single':
                slips = []
                for it in items:
                    stake = Decimal(it.stake)
                    slips.append((stake, payout(stake, american_to_decimal(it.odds_american)), [it]))
            else:
                raise SlipError('Unknown slip type.')

            total_stake = sum(s[0] for s in slips)
            if total_stake > balance:
                raise SlipError(f'Insufficient balance: this slip needs ${total_stake:,.2f} '
                                f'but you have ${balance:,.2f}.')

            # Exposure check: current liability on each line + what these
            # slips would add must stay within the line's limit.
            added = {}
            for stake, pot, legs in slips:
                for it in legs:
                    added[it.line_id] = added.get(it.line_id, Decimal(0)) + (pot - stake)
            current = {r.line_id: Decimal(r.exposure) for r in ex("""
SELECT line_id, exposure FROM LineExposure WHERE line_id = ANY(:ids)
""", ids=list(added))}
            for it in items:
                if current.get(it.line_id, Decimal(0)) + added[it.line_id] > Decimal(it.exposure_limit):
                    room = Decimal(it.exposure_limit) - current.get(it.line_id, Decimal(0))
                    raise SlipError(
                        f'{it.home_abbr}/{it.away_abbr} {it.market} {it.side}: the book has only '
                        f'${max(room, 0):,.2f} of exposure left on this line. Lower your stake.')

            # All checks passed: write the slips, charge the balance, empty the cart.
            slip_ids = []
            for stake, pot, legs in slips:
                sid = ex("""
INSERT INTO BetSlips(user_id, kind, stake, potential_payout)
VALUES(:u, :kind, :stake, :pot) RETURNING id
""", u=user_id, kind=kind, stake=stake, pot=pot)[0][0]
                for it in legs:
                    ex("""
INSERT INTO SlipLegs(slip_id, line_id, odds_american, line_value)
VALUES(:sid, :line_id, :odds, :line_value)
""", sid=sid, line_id=it.line_id, odds=it.odds_american, line_value=it.line_value)
                ex("""
INSERT INTO BalanceTransactions(user_id, amount, kind, slip_id)
VALUES(:u, :amount, 'stake', :sid)
""", u=user_id, amount=-stake, sid=sid)
                slip_ids.append(sid)
            ex("UPDATE Users SET balance = balance - :t WHERE id = :u", t=total_stake, u=user_id)
            ex("DELETE FROM CartItems WHERE user_id = :u", u=user_id)
            return slip_ids

    @staticmethod
    def history(user_id, status=None, limit=100):
        """Bet history, newest first, with a one-line summary of each slip."""
        return app.db.execute("""
SELECT s.id, s.kind, s.stake, s.potential_payout, s.payout, s.status, s.placed_at, s.settled_at,
       COUNT(sl.id) AS legs,
       STRING_AGG(g.away_abbr || ' @ ' || g.home_abbr, ', ' ORDER BY g.start_time) AS games
FROM BetSlips s
JOIN SlipLegs sl ON sl.slip_id = s.id
JOIN Lines l ON l.id = sl.line_id
JOIN Games g ON g.id = l.game_id
WHERE s.user_id = :u AND (:status IS NULL OR s.status = :status)
GROUP BY s.id
ORDER BY s.placed_at DESC, s.id DESC
LIMIT :limit
""", u=user_id, status=status, limit=limit)

    @staticmethod
    def get(slip_id):
        rows = app.db.execute("""
SELECT s.id, s.user_id, s.kind, s.stake, s.potential_payout, s.payout, s.status,
       s.placed_at, s.settled_at, u.full_name
FROM BetSlips s JOIN Users u ON u.id = s.user_id
WHERE s.id = :id
""", id=slip_id)
        return rows[0] if rows else None

    @staticmethod
    def legs(slip_id):
        return app.db.execute("""
SELECT sl.id, sl.odds_american, sl.line_value, sl.status, sl.settled_at,
       l.id AS line_id, l.market, l.side, b.name AS book_name,
       g.id AS game_id, g.home_team, g.away_team, g.home_abbr, g.away_abbr,
       g.start_time, g.status AS game_status, g.home_score, g.away_score
FROM SlipLegs sl
JOIN Lines l ON l.id = sl.line_id
JOIN Books b ON b.id = l.book_id
JOIN Games g ON g.id = l.game_id
WHERE sl.slip_id = :id
ORDER BY g.start_time, sl.id
""", id=slip_id)
