-- Line-up schema.
-- Mapping onto the Mini-Amazon reference architecture:
--   Users      -> Users (accounts, balance, bet history)
--   Products   -> Games + Lines (browsable markets)
--   Cart/Order -> CartItems (unsubmitted slip) + BetSlips/SlipLegs (placed bets)
--   Sellers    -> Books (post lines, own exposure limits)

CREATE TABLE Users (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    password    VARCHAR(255) NOT NULL,          -- werkzeug hash, never plaintext
    full_name   VARCHAR(255) NOT NULL,
    balance     NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
);

-- A sport is the "category" a game belongs to. espn_path is the path segment
-- used by the ingest job (e.g. football/nfl).
CREATE TABLE Sports (
    id          SERIAL PRIMARY KEY,
    key         VARCHAR(32) UNIQUE NOT NULL,
    name        VARCHAR(64) NOT NULL,
    espn_path   VARCHAR(64)
);

CREATE TABLE Games (
    id          SERIAL PRIMARY KEY,
    sport_id    INT NOT NULL REFERENCES Sports(id),
    external_id VARCHAR(32) UNIQUE,              -- id in the sports data API
    home_team   VARCHAR(64) NOT NULL,
    away_team   VARCHAR(64) NOT NULL,
    home_abbr   VARCHAR(8) NOT NULL,
    away_abbr   VARCHAR(8) NOT NULL,
    start_time  TIMESTAMPTZ NOT NULL,
    status      VARCHAR(16) NOT NULL DEFAULT 'scheduled'
                CHECK (status IN ('scheduled', 'in_progress', 'final', 'postponed')),
    home_score  INT,
    away_score  INT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    CHECK (status <> 'final' OR (home_score IS NOT NULL AND away_score IS NOT NULL))
);
CREATE INDEX Games_start_time ON Games(start_time);
CREATE INDEX Games_status ON Games(status);

-- A book is the Line-up equivalent of a seller: a user who posts lines.
CREATE TABLE Books (
    id                      SERIAL PRIMARY KEY,
    owner_id                INT UNIQUE NOT NULL REFERENCES Users(id),
    name                    VARCHAR(64) UNIQUE NOT NULL,
    default_exposure_limit  NUMERIC(12, 2) NOT NULL DEFAULT 1000 CHECK (default_exposure_limit >= 0),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
);

-- One line = one book's price on one side of one market for one game.
--   moneyline: line_value is NULL, side is home/away
--   spread:    line_value is the handicap applied to that side (home -2.5 / away +2.5)
--   total:     line_value is the total points, side is over/under
CREATE TABLE Lines (
    id              SERIAL PRIMARY KEY,
    game_id         INT NOT NULL REFERENCES Games(id),
    book_id         INT NOT NULL REFERENCES Books(id),
    market          VARCHAR(16) NOT NULL CHECK (market IN ('moneyline', 'spread', 'total')),
    side            VARCHAR(8)  NOT NULL CHECK (side IN ('home', 'away', 'over', 'under')),
    line_value      NUMERIC(6, 1),
    odds_american   INT NOT NULL CHECK (odds_american >= 100 OR odds_american <= -100),
    exposure_limit  NUMERIC(12, 2) NOT NULL CHECK (exposure_limit >= 0),
    is_open         BOOLEAN NOT NULL DEFAULT TRUE,
    posted_at       TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE (game_id, book_id, market, side),
    CHECK ((market = 'moneyline') = (line_value IS NULL)),
    CHECK ((market = 'total') = (side IN ('over', 'under')))
);
CREATE INDEX Lines_game ON Lines(game_id);
CREATE INDEX Lines_book ON Lines(book_id);

-- The persistent, unsubmitted bet slip ("cart"). One row per line per user.
CREATE TABLE CartItems (
    user_id     INT NOT NULL REFERENCES Users(id),
    line_id     INT NOT NULL REFERENCES Lines(id),
    stake       NUMERIC(12, 2) NOT NULL CHECK (stake > 0),
    added_at    TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (user_id, line_id)
);

-- A placed bet. A single has one leg; a parlay has 2+ legs that must all win.
CREATE TABLE BetSlips (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES Users(id),
    kind                VARCHAR(8) NOT NULL CHECK (kind IN ('single', 'parlay')),
    stake               NUMERIC(12, 2) NOT NULL CHECK (stake > 0),
    potential_payout    NUMERIC(12, 2) NOT NULL CHECK (potential_payout >= stake),
    payout              NUMERIC(12, 2),            -- actual amount returned at settlement
    status              VARCHAR(8) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'won', 'lost', 'push', 'void')),
    placed_at           TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    settled_at          TIMESTAMPTZ,
    CHECK ((status = 'pending') = (settled_at IS NULL))
);
CREATE INDEX BetSlips_user ON BetSlips(user_id, placed_at DESC);
CREATE INDEX BetSlips_status ON BetSlips(status);

-- The odds and line value are copied from Lines at placement time so a later
-- change by the book never changes what the user locked in.
CREATE TABLE SlipLegs (
    id              SERIAL PRIMARY KEY,
    slip_id         INT NOT NULL REFERENCES BetSlips(id),
    line_id         INT NOT NULL REFERENCES Lines(id),
    odds_american   INT NOT NULL,
    line_value      NUMERIC(6, 1),
    status          VARCHAR(8) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'won', 'lost', 'push', 'void')),
    settled_at      TIMESTAMPTZ,
    UNIQUE (slip_id, line_id)
);
CREATE INDEX SlipLegs_line ON SlipLegs(line_id);
CREATE INDEX SlipLegs_status ON SlipLegs(status);

-- Every change to a user's balance, for the account history page.
CREATE TABLE BalanceTransactions (
    id          SERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES Users(id),
    amount      NUMERIC(12, 2) NOT NULL,          -- signed: negative for stake/withdraw
    kind        VARCHAR(16) NOT NULL CHECK (kind IN ('topup', 'withdraw', 'stake', 'payout', 'refund')),
    slip_id     INT REFERENCES BetSlips(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
);
CREATE INDEX BalanceTransactions_user ON BalanceTransactions(user_id, created_at DESC);

-- Current liability of each line: the net profit the book would owe if every
-- pending slip containing the line won. Submission checks new liability
-- against Lines.exposure_limit using this definition.
CREATE VIEW LineExposure AS
SELECT l.id AS line_id,
       COALESCE(SUM(s.potential_payout - s.stake), 0) AS exposure,
       COUNT(s.id) AS pending_slips
FROM Lines l
LEFT JOIN SlipLegs sl ON sl.line_id = l.id AND sl.status = 'pending'
LEFT JOIN BetSlips s ON s.id = sl.slip_id AND s.status = 'pending'
GROUP BY l.id;
