from flask import current_app as app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .. import login


class User(UserMixin):
    def __init__(self, id, email, full_name, address, balance, created_at):
        self.id = id
        self.email = email
        self.full_name = full_name
        self.address = address
        self.balance = balance
        self.created_at = created_at

    COLS = 'id, email, full_name, address, balance, created_at'

    @staticmethod
    def get_by_auth(email, password):
        rows = app.db.execute(f"""
SELECT password, {User.COLS}
FROM Users
WHERE email = :email
""", email=email)
        if not rows:
            return None
        if not check_password_hash(rows[0][0], password):
            return None
        return User(*rows[0][1:])

    @staticmethod
    def email_exists(email, exclude_id=None):
        rows = app.db.execute("""
SELECT id FROM Users
WHERE email = :email AND (:exclude_id IS NULL OR id <> :exclude_id)
""", email=email, exclude_id=exclude_id)
        return len(rows) > 0

    @staticmethod
    def register(email, password, full_name, address=''):
        rows = app.db.execute("""
INSERT INTO Users(email, password, full_name, address, balance)
VALUES(:email, :password, :full_name, :address, :balance)
RETURNING id
""", email=email, password=generate_password_hash(password),
            full_name=full_name, address=address,
            balance=app.config['STARTING_BALANCE'])
        return User.get(rows[0][0])

    @staticmethod
    @login.user_loader
    def get(id):
        rows = app.db.execute(f"""
SELECT {User.COLS}
FROM Users
WHERE id = :id
""", id=id)
        return User(*rows[0]) if rows else None

    @staticmethod
    def update_profile(id, email, full_name, address, password=None):
        if password:
            app.db.execute("""
UPDATE Users SET email = :email, full_name = :full_name, address = :address,
                 password = :password
WHERE id = :id
""", id=id, email=email, full_name=full_name, address=address,
                password=generate_password_hash(password))
        else:
            app.db.execute("""
UPDATE Users SET email = :email, full_name = :full_name, address = :address
WHERE id = :id
""", id=id, email=email, full_name=full_name, address=address)

    @staticmethod
    def adjust_balance(id, amount, kind):
        """Top up (positive) or withdraw (negative). The CHECK (balance >= 0)
        constraint makes an over-withdrawal fail atomically."""
        with app.db.transaction() as conn:
            app.db.execute_on(conn, """
UPDATE Users SET balance = balance + :amount WHERE id = :id
""", id=id, amount=amount)
            app.db.execute_on(conn, """
INSERT INTO BalanceTransactions(user_id, amount, kind)
VALUES(:id, :amount, :kind)
""", id=id, amount=amount, kind=kind)

    @staticmethod
    def transactions(id, limit=50):
        return app.db.execute("""
SELECT t.id, t.amount, t.kind, t.slip_id, t.created_at
FROM BalanceTransactions t
WHERE t.user_id = :id
ORDER BY t.created_at DESC, t.id DESC
LIMIT :limit
""", id=id, limit=limit)

    @staticmethod
    def public_summary(id):
        """Public profile: record and net winnings over settled slips, plus the
        user's book if they run one."""
        rows = app.db.execute("""
SELECT u.id, u.full_name, u.created_at,
       COUNT(s.id) FILTER (WHERE s.status = 'won')  AS wins,
       COUNT(s.id) FILTER (WHERE s.status = 'lost') AS losses,
       COUNT(s.id) FILTER (WHERE s.status = 'push') AS pushes,
       COUNT(s.id) FILTER (WHERE s.status = 'pending') AS pending,
       COALESCE(SUM(s.payout - s.stake) FILTER (WHERE s.status <> 'pending'), 0) AS net,
       b.id AS book_id, b.name AS book_name
FROM Users u
LEFT JOIN BetSlips s ON s.user_id = u.id
LEFT JOIN Books b ON b.owner_id = u.id
WHERE u.id = :id
GROUP BY u.id, b.id
""", id=id)
        return rows[0] if rows else None

    @staticmethod
    def leaderboard(limit=25):
        return app.db.execute("""
SELECT u.id, u.full_name,
       COUNT(s.id) FILTER (WHERE s.status = 'won')  AS wins,
       COUNT(s.id) FILTER (WHERE s.status = 'lost') AS losses,
       COALESCE(SUM(s.payout - s.stake), 0) AS net,
       COALESCE(SUM(s.stake), 0) AS wagered
FROM Users u
JOIN BetSlips s ON s.user_id = u.id AND s.status IN ('won', 'lost', 'push')
GROUP BY u.id
ORDER BY net DESC, wins DESC
LIMIT :limit
""", limit=limit)
