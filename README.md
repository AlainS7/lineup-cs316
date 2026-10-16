# Line-up: a fixed-odds sports prediction market

CompSci 316 open project. Users bet virtual currency against posted lines on
real upcoming games; outcomes settle automatically once real results come in.
Built on Flask + PostgreSQL following the Mini-Amazon skeleton architecture.

| Mini-Amazon role                     | Line-up equivalent                                            |
| ------------------------------------ | ------------------------------------------------------------- |
| Users (accounts, balance, purchases) | Users (accounts, balance, bet history)                        |
| Products / categories                | Games (grouped by sport) and Lines (the bettable prices)      |
| Cart / Order                         | Bet slip (`CartItems`) / placed bets (`BetSlips`, `SlipLegs`) |
| Sellers / inventory                  | Books (post lines, set exposure limits)                       |

## Setup

Everything runs inside the course container. From the `container` directory on
your laptop, with Docker Desktop running:

```bash
docker compose start                        # `docker compose up -d` the first time
docker compose exec -it ubuntu bash --login
```

Inside the container (it already sets `PGHOST`, `PGUSER` and `PGPASSWORD`; the
container image has no `python3-venv`, so packages go in the user site):

```bash
cd ~/shared/container/proj/line-up
pip3 install --user --break-system-packages -r requirements.txt   # first time only
export PATH=$HOME/.local/bin:$PATH
flask db-init                                    # creates the `lineup` database and loads db/data/*.csv
python3 -m pytest tests -q -p no:cacheprovider   # should report 29 passed
./lineup.sh                                      # dev server; open http://localhost:8080 on the laptop
```

Seed accounts all use the password `password`: `alain@duke.edu` (also runs "Blue
Devil Book"), `maya@duke.edu`, `jordan@duke.edu`, `sam@duke.edu`,
`riley@duke.edu`. `house@lineup.local` owns the "Consensus" book that the ingest
job posts ESPN lines under.

Running on a laptop instead of in the container: create a venv with
`python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`,
create `.env` in this directory with `PGHOST=localhost`,
`PGPORT=<output of docker compose port postgres 5432>`, `PGUSER`, `PGPASSWORD`,
then the same commands (use `./lineup.sh 8081` since Docker holds 8080).

## Jobs

```bash
flask ingest                 # pull games, scores and consensus lines from ESPN (last 3 days .. next 7)
flask settle                 # grade pending legs on final games, pay out resolved slips
flask finalize 5 24 20       # demo helper: mark game 5 final (home 24, away 20) and settle
flask db-init                # wipe and reseed
python -m pytest tests       # unit tests for odds math + end-to-end flow on a throwaway lineup_test DB
```

In production `ingest` then `settle` would run from cron every few minutes.

## Layout

```text
app/__init__.py      app factory, blueprints, Jinja filters
app/db.py            SQLAlchemy engine wrapper; all SQL uses text() + named params (no injection)
app/odds.py          American/decimal conversion, parlay math, leg + slip grading
app/settlement.py    set-based SQL that grades legs, then resolves and pays slips
app/ingest.py        ESPN scoreboard client; upserts Games, posts house Lines
app/cli.py           flask db-init / ingest / settle / finalize
app/models/          user.py game.py line.py book.py slip.py (Cart + Slip.place)
app/index.py         browse + leaderboard          (Markets role)
app/users.py         register/login/account/public (Users role)
app/games.py         game detail, add line to slip (Markets role)
app/slip.py bets.py  bet slip, place, history       (Bet Slip role)
app/books.py         book dashboard, post/edit lines (Books role)
app/templates/       Bootstrap 5 pages
db/create.sql        schema + LineExposure view     db/load.sql  seed loader
db/gen_seed.py       regenerates db/data/*.csv      tests/       pytest suite
```

## Key rules

- Odds and line values are copied onto `SlipLegs` at placement, so a book
  editing a line never changes a bet already made.
- A line's exposure = sum over pending slips containing it of (potential payout
  − stake). `Slip.place` locks the lines (`SELECT ... FOR UPDATE`), checks
  balance, open/started state, parlay validity (2+ legs, distinct games), and
  exposure limits, all in one transaction, then charges the balance and empties
  the slip.
- Parlays pay stake × product of decimal odds; a pushed leg drops out; any lost
  leg loses the slip and voids its other legs.
- Settlement grades every pending leg on a final game with one
  `UPDATE ... FROM`, then resolves slips with no pending legs and credits
  payouts.
