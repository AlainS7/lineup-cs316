"""Generate the seed CSVs in db/data/.

Run from the project root with the venv active:  python db/gen_seed.py
Produces a handful of users, two books, a slate of NFL/NBA games (some already
final so settlement has something to do), consensus lines, and a few placed
bets. Settled bets on final games are pre-graded so the leaderboard and
balance history have content on first load.
"""

import csv
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from werkzeug.security import generate_password_hash  # noqa: E402
from app.odds import american_to_decimal, parlay_decimal, payout, grade_leg, grade_slip  # noqa: E402

OUT = Path(__file__).resolve().parent / "data"
OUT.mkdir(exist_ok=True)
NOW = datetime.now(timezone.utc).replace(microsecond=0)
PASSWORD = generate_password_hash("password")  # every seed account uses "password"


def write(name, header, rows):
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])
    print(f"{name}: {len(rows)} rows")


def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S+00")


# ---- Users -------------------------------------------------------------
users = [
    # id, email, password, full_name, balance, created_at
    (
        1,
        "house@lineup.local",
        PASSWORD,
        "Line-up House",
        Decimal("0.00"),
        NOW - timedelta(days=30),
    ),
    (
        2,
        "alain@duke.edu",
        PASSWORD,
        "Alain Soto",
        Decimal("1000.00"),
        NOW - timedelta(days=20),
    ),
    (
        3,
        "maya@duke.edu",
        PASSWORD,
        "Maya Chen",
        Decimal("1000.00"),
        NOW - timedelta(days=18),
    ),
    (
        4,
        "jordan@duke.edu",
        PASSWORD,
        "Jordan Patel",
        Decimal("1000.00"),
        NOW - timedelta(days=15),
    ),
    (
        5,
        "sam@duke.edu",
        PASSWORD,
        "Sam Okafor",
        Decimal("1000.00"),
        NOW - timedelta(days=10),
    ),
    (
        6,
        "riley@duke.edu",
        PASSWORD,
        "Riley Brooks",
        Decimal("1000.00"),
        NOW - timedelta(days=5),
    ),
]
balances = {u[0]: u[4] for u in users}

# ---- Sports -------------------------------------------------------------
sports = [
    (1, "nfl", "NFL", "football/nfl"),
    (2, "nba", "NBA", "basketball/nba"),
    (3, "ncaaf", "College Football", "football/college-football"),
]

# ---- Games --------------------------------------------------------------
# Final games (past), then upcoming ones. external_id uses a seed- prefix so
# the ingest job never collides with them.
D = lambda days, hour: (NOW + timedelta(days=days)).replace(
    hour=hour, minute=0, second=0
)
games = [
    # id, sport_id, external_id, home, away, home_abbr, away_abbr, start, status, hs, as, updated_at
    (
        1,
        1,
        "seed-1",
        "Philadelphia Eagles",
        "Dallas Cowboys",
        "PHI",
        "DAL",
        D(-4, 20),
        "final",
        27,
        20,
        NOW,
    ),
    (
        2,
        1,
        "seed-2",
        "Kansas City Chiefs",
        "Baltimore Ravens",
        "KC",
        "BAL",
        D(-3, 20),
        "final",
        17,
        24,
        NOW,
    ),
    (
        3,
        2,
        "seed-3",
        "Boston Celtics",
        "Miami Heat",
        "BOS",
        "MIA",
        D(-2, 23),
        "final",
        112,
        101,
        NOW,
    ),
    (
        4,
        2,
        "seed-4",
        "Los Angeles Lakers",
        "Denver Nuggets",
        "LAL",
        "DEN",
        D(-1, 2),
        "final",
        105,
        110,
        NOW,
    ),
    (
        5,
        1,
        "seed-5",
        "Denver Broncos",
        "Seattle Seahawks",
        "DEN",
        "SEA",
        D(2, 0),
        "scheduled",
        None,
        None,
        NOW,
    ),
    (
        6,
        1,
        "seed-6",
        "Jacksonville Jaguars",
        "Houston Texans",
        "JAX",
        "HOU",
        D(4, 17),
        "scheduled",
        None,
        None,
        NOW,
    ),
    (
        7,
        1,
        "seed-7",
        "Atlanta Falcons",
        "Chicago Bears",
        "ATL",
        "CHI",
        D(4, 17),
        "scheduled",
        None,
        None,
        NOW,
    ),
    (
        8,
        1,
        "seed-8",
        "San Francisco 49ers",
        "Green Bay Packers",
        "SF",
        "GB",
        D(4, 20),
        "scheduled",
        None,
        None,
        NOW,
    ),
    (
        9,
        2,
        "seed-9",
        "Golden State Warriors",
        "Phoenix Suns",
        "GS",
        "PHX",
        D(1, 2),
        "scheduled",
        None,
        None,
        NOW,
    ),
    (
        10,
        2,
        "seed-10",
        "New York Knicks",
        "Milwaukee Bucks",
        "NY",
        "MIL",
        D(3, 23),
        "scheduled",
        None,
        None,
        NOW,
    ),
    (
        11,
        2,
        "seed-11",
        "Oklahoma City Thunder",
        "Dallas Mavericks",
        "OKC",
        "DAL",
        D(5, 0),
        "scheduled",
        None,
        None,
        NOW,
    ),
    (
        12,
        3,
        "seed-12",
        "Duke Blue Devils",
        "North Carolina Tar Heels",
        "DUKE",
        "UNC",
        D(6, 19),
        "scheduled",
        None,
        None,
        NOW,
    ),
]
game_by_id = {g[0]: g for g in games}

# ---- Books --------------------------------------------------------------
books = [
    # id, owner_id, name, default_exposure_limit, created_at
    (1, 1, "Consensus", Decimal("5000.00"), NOW - timedelta(days=30)),
    (2, 2, "Blue Devil Book", Decimal("500.00"), NOW - timedelta(days=14)),
]

# ---- Lines --------------------------------------------------------------
# (game_id, book_id, home spread, total, home ML, away ML). Spread/total at -110.
line_specs = [
    (1, 1, Decimal("-3.5"), Decimal("47.5"), -170, 145),
    (2, 1, Decimal("-2.5"), Decimal("45.5"), -135, 115),
    (3, 1, Decimal("-6.5"), Decimal("215.5"), -260, 210),
    (4, 1, Decimal("1.5"), Decimal("228.5"), 105, -125),
    (5, 1, Decimal("2.5"), Decimal("40.5"), 120, -140),
    (6, 1, Decimal("-2.5"), Decimal("42.5"), -135, 115),
    (7, 1, Decimal("2.5"), Decimal("50.5"), 118, -138),
    (8, 1, Decimal("-1.5"), Decimal("44.5"), -120, 100),
    (9, 1, Decimal("-4.5"), Decimal("230.5"), -190, 160),
    (10, 1, Decimal("-1.5"), Decimal("221.5"), -115, -105),
    (11, 1, Decimal("-7.5"), Decimal("233.5"), -320, 260),
    (12, 1, Decimal("-9.5"), Decimal("54.5"), -400, 310),
    # The student book shades some of the same games.
    (5, 2, Decimal("3.0"), Decimal("41.0"), 125, -135),
    (8, 2, Decimal("-2.5"), None, -125, 105),
    (12, 2, Decimal("-10.5"), Decimal("55.5"), -380, 300),
    (3, 2, Decimal("-5.5"), Decimal("214.5"), -240, 200),
]
lines = []
lid = 0
for game_id, book_id, spread, total, hml, aml in line_specs:
    limit = next(b[3] for b in books if b[0] == book_id)
    posted = game_by_id[game_id][7] - timedelta(days=3)
    is_open = game_by_id[game_id][8] == "scheduled"
    specs = [
        ("moneyline", "home", None, hml),
        ("moneyline", "away", None, aml),
        ("spread", "home", spread, -110),
        ("spread", "away", -spread, -110),
    ]
    if total is not None:
        specs += [("total", "over", total, -110), ("total", "under", total, -110)]
    for market, side, value, odds in specs:
        lid += 1
        lines.append(
            (
                lid,
                game_id,
                book_id,
                market,
                side,
                value,
                odds,
                limit,
                is_open,
                posted,
                posted,
            )
        )
line_by_id = {l[0]: l for l in lines}


def find_line(game_id, book_id, market, side):
    return next(
        l
        for l in lines
        if l[1] == game_id and l[2] == book_id and l[3] == market and l[4] == side
    )


# ---- Bets ---------------------------------------------------------------
# (user_id, kind, stake, [(game_id, book_id, market, side), ...], placed days ago)
bet_specs = [
    (3, "single", Decimal("50"), [(1, 1, "spread", "home")], 5),
    (3, "single", Decimal("25"), [(2, 1, "moneyline", "away")], 4),
    (4, "single", Decimal("100"), [(1, 1, "moneyline", "away")], 5),
    (
        4,
        "parlay",
        Decimal("20"),
        [(1, 1, "spread", "home"), (3, 2, "moneyline", "home")],
        4,
    ),
    (5, "single", Decimal("40"), [(3, 1, "total", "over")], 3),
    (
        5,
        "parlay",
        Decimal("10"),
        [(2, 1, "spread", "home"), (4, 1, "moneyline", "away")],
        3,
    ),
    (6, "single", Decimal("75"), [(4, 1, "spread", "home")], 2),
    # Pending bets on upcoming games.
    (3, "single", Decimal("30"), [(5, 1, "spread", "away")], 1),
    (
        4,
        "parlay",
        Decimal("15"),
        [
            (5, 2, "moneyline", "home"),
            (9, 1, "spread", "home"),
            (12, 1, "total", "under"),
        ],
        1,
    ),
    (5, "single", Decimal("60"), [(12, 2, "moneyline", "away")], 0),
    (6, "single", Decimal("20"), [(8, 2, "spread", "home")], 0),
    (2, "single", Decimal("45"), [(9, 1, "moneyline", "away")], 0),
]
slips, legs, txns = [], [], []
sid = legid = tid = 0
for user_id, kind, stake, picks, days_ago in bet_specs:
    sid += 1
    placed = NOW - timedelta(days=days_ago, hours=3)
    chosen = [find_line(*p) for p in picks]
    dec = parlay_decimal([l[6] for l in chosen])
    pot = payout(stake, dec)
    leg_rows, leg_statuses, leg_odds = [], [], []
    all_final = all(game_by_id[l[1]][8] == "final" for l in chosen)
    for l in chosen:
        legid += 1
        g = game_by_id[l[1]]
        st = grade_leg(l[3], l[4], l[5], g[9], g[10]) if g[8] == "final" else "pending"
        leg_rows.append(
            [legid, sid, l[0], l[6], l[5], st, g[11] if st != "pending" else None]
        )
        leg_statuses.append(st)
        leg_odds.append(l[6])
    status, pay = grade_slip(leg_statuses, leg_odds, stake)
    if status == "lost":
        for r in leg_rows:
            if r[5] == "pending":
                r[5], r[6] = "void", NOW
    settled_at = NOW if status != "pending" else None
    slips.append((sid, user_id, kind, stake, pot, pay, status, placed, settled_at))
    legs.extend(leg_rows)
    balances[user_id] -= stake
    tid += 1
    txns.append((tid, user_id, -stake, "stake", sid, placed))
    if pay and pay > 0:
        balances[user_id] += pay
        tid += 1
        txns.append(
            (tid, user_id, pay, "payout" if status == "won" else "refund", sid, NOW)
        )

# Opening top-ups so balance history explains the starting 1000.
for u in users[1:]:
    tid += 1
    txns.append((tid, u[0], Decimal("1000.00"), "topup", None, u[5]))
txns.sort(key=lambda t: (t[5], t[0]))
txns = [(i + 1,) + t[1:] for i, t in enumerate(txns)]

# A couple of cart items so the slip page is not empty for the demo user.
cart = [
    (2, find_line(5, 1, "spread", "home")[0], Decimal("25.00"), NOW),
    (2, find_line(10, 1, "moneyline", "home")[0], Decimal("10.00"), NOW),
]

write(
    "Users",
    ["id", "email", "password", "full_name", "balance", "created_at"],
    [
        (u[0], u[1], u[2], u[3], f"{balances[u[0]]:.2f}", ts(u[5]))
        for u in users
    ],
)
write("Sports", ["id", "key", "name", "espn_path"], sports)
write(
    "Games",
    [
        "id",
        "sport_id",
        "external_id",
        "home_team",
        "away_team",
        "home_abbr",
        "away_abbr",
        "start_time",
        "status",
        "home_score",
        "away_score",
        "updated_at",
    ],
    [g[:7] + (ts(g[7]), g[8], g[9], g[10], ts(g[11])) for g in games],
)
write(
    "Books",
    ["id", "owner_id", "name", "default_exposure_limit", "created_at"],
    [b[:4] + (ts(b[4]),) for b in books],
)
write(
    "Lines",
    [
        "id",
        "game_id",
        "book_id",
        "market",
        "side",
        "line_value",
        "odds_american",
        "exposure_limit",
        "is_open",
        "posted_at",
        "updated_at",
    ],
    [l[:9] + (ts(l[9]), ts(l[10])) for l in lines],
)
write(
    "BetSlips",
    [
        "id",
        "user_id",
        "kind",
        "stake",
        "potential_payout",
        "payout",
        "status",
        "placed_at",
        "settled_at",
    ],
    [
        (s[0], s[1], s[2], s[3], s[4], s[5], s[6], ts(s[7]), ts(s[8]) if s[8] else None)
        for s in slips
    ],
)
write(
    "SlipLegs",
    ["id", "slip_id", "line_id", "odds_american", "line_value", "status", "settled_at"],
    [(r[0], r[1], r[2], r[3], r[4], r[5], ts(r[6]) if r[6] else None) for r in legs],
)
write(
    "BalanceTransactions",
    ["id", "user_id", "amount", "kind", "slip_id", "created_at"],
    [(t[0], t[1], t[2], t[3], t[4], ts(t[5])) for t in txns],
)
write(
    "CartItems",
    ["user_id", "line_id", "stake", "added_at"],
    [(c[0], c[1], c[2], ts(c[3])) for c in cart],
)
