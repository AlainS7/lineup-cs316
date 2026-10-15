"""End-to-end flow against the seeded test database: register, log in,
browse, build a slip, place singles and a parlay, hit the exposure limit,
settle a game, and see the payout land."""
from decimal import Decimal

from conftest import login


def balance(app, email):
    return Decimal(app.db.execute("SELECT balance FROM Users WHERE email = :e", e=email)[0][0])


def line_id(app, game_id, book_name, market, side):
    return app.db.execute("""
SELECT l.id FROM Lines l JOIN Books b ON b.id = l.book_id
WHERE l.game_id = :g AND b.name = :b AND l.market = :m AND l.side = :s
""", g=game_id, b=book_name, m=market, s=side)[0][0]


def test_register_login_logout(client):
    r = client.post('/register', data={'full_name': 'Test User', 'email': 'test@duke.edu', 'address': '',
                                       'password': 'secret1', 'password2': 'secret1'}, follow_redirects=True)
    assert b'Account created' in r.data
    # Duplicate email is rejected.
    r = client.post('/register', data={'full_name': 'Dup', 'email': 'test@duke.edu', 'address': '',
                                       'password': 'secret1', 'password2': 'secret1'})
    assert b'already exists' in r.data
    # Wrong password fails, right one succeeds.
    r = login(client, 'test@duke.edu', 'nope')
    assert b'Invalid email or password' in r.data
    r = login(client, 'test@duke.edu', 'secret1')
    assert b'Test User' in r.data
    client.get('/logout')
    assert client.get('/bets').status_code == 302


def test_browse_and_search(client):
    assert client.get('/').status_code == 200
    r = client.get('/?sport=nba&q=knicks')
    assert b'New York Knicks' in r.data and b'Eagles' not in r.data
    r = client.get('/?status=final')
    assert b'Philadelphia Eagles' in r.data
    r = client.get("/?q=' OR 1=1 --")  # injection attempt is just a search string
    assert r.status_code == 200 and b'No games match' in r.data
    assert client.get('/games/5').status_code == 200
    assert client.get('/games/99999').status_code == 404


def test_place_singles_and_parlay(client, app):
    login(client, 'riley@duke.edu')
    start = balance(app, 'riley@duke.edu')
    l1 = line_id(app, 6, 'Consensus', 'spread', 'home')     # JAX -2.5 at -110
    l2 = line_id(app, 7, 'Consensus', 'moneyline', 'away')  # CHI ML at -138
    client.post(f'/lines/{l1}/add', data={'stake': '20'})
    client.post(f'/lines/{l2}/add', data={'stake': '30'})
    r = client.get('/slip')
    assert b'JAX -2.5' in r.data and b'CHI ML' in r.data

    r = client.post('/slip/place', data={'kind': 'single'}, follow_redirects=True)
    assert b'2 bets placed' in r.data
    assert balance(app, 'riley@duke.edu') == start - 50
    assert app.db.execute("SELECT COUNT(*) FROM CartItems WHERE user_id = 6")[0][0] == 0

    # Parlay on the same two lines.
    client.post(f'/lines/{l1}/add', data={'stake': '1'})
    client.post(f'/lines/{l2}/add', data={'stake': '1'})
    r = client.post('/slip/place', data={'kind': 'parlay', 'parlay_stake': '10'}, follow_redirects=True)
    assert b'Bet placed' in r.data
    slip = app.db.execute("""
SELECT kind, stake, potential_payout FROM BetSlips WHERE user_id = 6 ORDER BY id DESC LIMIT 1""")[0]
    assert slip.kind == 'parlay' and slip.stake == 10
    assert slip.potential_payout == Decimal('32.92')  # 10 * 1.909 * 1.7246
    assert balance(app, 'riley@duke.edu') == start - 60


def test_parlay_rejects_same_game(client, app):
    login(client, 'maya@duke.edu')
    l1 = line_id(app, 6, 'Consensus', 'spread', 'home')
    l2 = line_id(app, 6, 'Consensus', 'total', 'over')
    client.post(f'/lines/{l1}/add', data={'stake': '5'})
    client.post(f'/lines/{l2}/add', data={'stake': '5'})
    r = client.post('/slip/place', data={'kind': 'parlay', 'parlay_stake': '5'}, follow_redirects=True)
    assert b'two legs from the same game' in r.data
    client.post('/slip/clear')


def test_insufficient_balance(client, app):
    login(client, 'maya@duke.edu')
    l1 = line_id(app, 6, 'Consensus', 'spread', 'away')
    client.post(f'/lines/{l1}/add', data={'stake': '999999'})
    r = client.post('/slip/place', data={'kind': 'single'}, follow_redirects=True)
    assert b'Insufficient balance' in r.data
    client.post('/slip/clear')


def test_exposure_limit(client, app):
    """Blue Devil Book caps each line at $500 of liability and the seed
    already has $180 pending on UNC +300. A $200 bet would add $600, so it
    is rejected; $100 adds $300 (total 480) and is accepted."""
    login(client, 'maya@duke.edu')
    app.db.execute("UPDATE Users SET balance = 5000 WHERE email = 'maya@duke.edu'")
    lid = line_id(app, 12, 'Blue Devil Book', 'moneyline', 'away')  # UNC +300, limit 500
    client.post(f'/lines/{lid}/add', data={'stake': '200'})
    r = client.post('/slip/place', data={'kind': 'single'}, follow_redirects=True)
    assert b'exposure left on this line' in r.data
    assert app.db.execute("SELECT COUNT(*) FROM CartItems WHERE user_id = 3")[0][0] == 1  # still in slip

    client.post(f'/lines/{lid}/add', data={'stake': '100'})
    r = client.post('/slip/place', data={'kind': 'single'}, follow_redirects=True)
    assert b'Bet placed' in r.data
    exp = app.db.execute("SELECT exposure FROM LineExposure WHERE line_id = :l", l=lid)[0][0]
    assert exp == Decimal('480.00')


def test_closed_line_and_started_game(client, app):
    login(client, 'sam@duke.edu')
    lid = line_id(app, 1, 'Consensus', 'moneyline', 'home')  # final game, line closed
    r = client.post(f'/lines/{lid}/add', data={'stake': '10'}, follow_redirects=True)
    assert b'no longer open' in r.data
    # Sneak it into the cart directly, then try to place: still rejected.
    app.db.execute("INSERT INTO CartItems(user_id, line_id, stake) VALUES (5, :l, 10)", l=lid)
    r = client.post('/slip/place', data={'kind': 'single'}, follow_redirects=True)
    assert b'closed' in r.data
    client.post('/slip/clear')


def test_settlement_pays_out(client, app):
    """Finalize game 9 (GS vs PHX). Alain has PHX ML +160 for $45 (seed
    slip 12). If PHX wins he is paid 45 * 2.6 = 117."""
    from app.settlement import settle
    before = balance(app, 'alain@duke.edu')
    app.db.execute("UPDATE Games SET status = 'final', home_score = 100, away_score = 110 WHERE id = 9")
    legs, slips = settle(app.db)
    assert legs >= 1 and slips >= 1
    assert balance(app, 'alain@duke.edu') == before + Decimal('117.00')
    s = app.db.execute("SELECT status, payout FROM BetSlips WHERE id = 12")[0]
    assert s.status == 'won' and s.payout == Decimal('117.00')
    # Jordan's 3-leg parlay (slip 9) included GS -4.5: GS lost, so the parlay is lost
    # and its other legs are voided even though their games are not final.
    s = app.db.execute("SELECT status, payout FROM BetSlips WHERE id = 9")[0]
    assert s.status == 'lost' and s.payout == 0
    statuses = {r[0] for r in app.db.execute("SELECT status FROM SlipLegs WHERE slip_id = 9")}
    assert statuses == {'lost', 'void'}
    # Settling again is a no-op.
    assert settle(app.db) == (0, 0)
    # Leaderboard and transaction history reflect it.
    login(client, 'alain@duke.edu')
    r = client.get('/account')
    assert b'payout' in r.data
    assert client.get('/leaderboard').status_code == 200


def test_book_posts_and_edits_line(client, app):
    login(client, 'sam@duke.edu')
    r = client.post('/book/new', data={'name': 'Sam Book', 'default_exposure_limit': '250'}, follow_redirects=True)
    assert b'Your book is open' in r.data
    r = client.post('/book/lines/new', data={'game_id': 10, 'market': 'spread', 'side': 'home',
                                              'line_value': '-2.5', 'odds_american': '-105',
                                              'exposure_limit': '250', 'is_open': 'y'}, follow_redirects=True)
    assert b'Line posted' in r.data
    # Odds between -100 and +100 are invalid.
    r = client.post('/book/lines/new', data={'game_id': 10, 'market': 'moneyline', 'side': 'home',
                                              'line_value': '', 'odds_american': '50',
                                              'exposure_limit': '250', 'is_open': 'y'})
    assert b'at least +100' in r.data
    # Duplicate market/side is rejected.
    r = client.post('/book/lines/new', data={'game_id': 10, 'market': 'spread', 'side': 'home',
                                              'line_value': '-3.5', 'odds_american': '-110',
                                              'exposure_limit': '250', 'is_open': 'y'}, follow_redirects=True)
    assert b'already have a line' in r.data
    assert b'Sam Book' in client.get('/games/10').data
    assert client.get('/book').status_code == 200


def test_account_funds_and_profile(client, app):
    login(client, 'riley@duke.edu')
    start = balance(app, 'riley@duke.edu')
    client.post('/account', data={'amount': '100', 'topup': 'Top up'})
    assert balance(app, 'riley@duke.edu') == start + 100
    r = client.post('/account', data={'amount': '999999', 'withdraw': 'Withdraw'}, follow_redirects=True)
    assert b'cannot withdraw more' in r.data
    client.post('/account', data={'amount': '50', 'withdraw': 'Withdraw'})
    assert balance(app, 'riley@duke.edu') == start + 50
    # Cannot change email to one already in use.
    r = client.post('/account', data={'full_name': 'Riley B', 'email': 'maya@duke.edu', 'address': '',
                                      'password': '', 'password2': '', 'submit': 'Save'})
    assert b'already uses that email' in r.data
    r = client.post('/account', data={'full_name': 'Riley B', 'email': 'riley@duke.edu', 'address': 'Raleigh',
                                      'password': '', 'password2': '', 'submit': 'Save'}, follow_redirects=True)
    assert b'Profile updated' in r.data
