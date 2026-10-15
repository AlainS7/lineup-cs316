"""Pull schedules, scores and consensus odds from ESPN's public scoreboard
API and upsert them into Games / Lines.

Endpoint (no key required):
  https://site.api.espn.com/apis/site/v2/sports/{espn_path}/scoreboard?dates=YYYYMMDD-YYYYMMDD
"""
import re
from datetime import date, timedelta
from decimal import Decimal

import requests

ESPN_URL = 'https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard'

STATUS_MAP = {
    'STATUS_SCHEDULED': 'scheduled',
    'STATUS_IN_PROGRESS': 'in_progress',
    'STATUS_HALFTIME': 'in_progress',
    'STATUS_END_PERIOD': 'in_progress',
    'STATUS_DELAYED': 'in_progress',
    'STATUS_FINAL': 'final',
    'STATUS_FINAL_OT': 'final',
    'STATUS_POSTPONED': 'postponed',
    'STATUS_CANCELED': 'postponed',
}


def fetch_scoreboard(espn_path, days_back=3, days_ahead=7, session=None):
    """Events for every day in [today-days_back, today+days_ahead]. ESPN
    rejects date ranges on this endpoint, so it is one request per day."""
    events, seen = [], set()
    for offset in range(-days_back, days_ahead + 1):
        day = date.today() + timedelta(days=offset)
        resp = (session or requests).get(ESPN_URL.format(path=espn_path),
                                         params={'dates': f'{day:%Y%m%d}'}, timeout=20)
        resp.raise_for_status()
        for event in resp.json().get('events', []):
            if event['id'] not in seen:
                seen.add(event['id'])
                events.append(event)
    return events


def parse_event(event):
    """Flatten one ESPN event into the Games columns plus any odds."""
    comp = event['competitions'][0]
    teams = {t['homeAway']: t for t in comp['competitors']}
    home, away = teams['home'], teams['away']
    status = STATUS_MAP.get(comp['status']['type']['name'], 'scheduled')
    game = {
        'external_id': str(event['id']),
        'home_team': home['team']['displayName'],
        'away_team': away['team']['displayName'],
        'home_abbr': home['team']['abbreviation'],
        'away_abbr': away['team']['abbreviation'],
        'start_time': event['date'],
        'status': status,
        'home_score': int(home['score']) if status == 'final' and home.get('score') not in (None, '') else None,
        'away_score': int(away['score']) if status == 'final' and away.get('score') not in (None, '') else None,
    }
    return game, parse_odds(comp.get('odds') or [], game)


def parse_odds(odds_list, game):
    """ESPN gives a consensus spread like 'SEA -2.5' plus an over/under and
    sometimes moneylines. Return a list of (market, side, line_value, odds)."""
    if not odds_list:
        return []
    o = odds_list[0]
    lines = []
    details = o.get('details') or ''
    m = re.match(r'^([A-Z]{2,5})\s+([+-]?\d+(?:\.\d+)?)$', details.strip())
    if m:
        fav, pts = m.group(1), Decimal(m.group(2))
        fav_side = 'home' if fav == game['home_abbr'] else 'away' if fav == game['away_abbr'] else None
        if fav_side:
            home_val = pts if fav_side == 'home' else -pts
            home_odds = (o.get('homeTeamOdds') or {}).get('spreadOdds') or -110
            away_odds = (o.get('awayTeamOdds') or {}).get('spreadOdds') or -110
            lines.append(('spread', 'home', home_val, int(home_odds)))
            lines.append(('spread', 'away', -home_val, int(away_odds)))
    ou = o.get('overUnder')
    if ou:
        lines.append(('total', 'over', Decimal(str(ou)), int(o.get('overOdds') or -110)))
        lines.append(('total', 'under', Decimal(str(ou)), int(o.get('underOdds') or -110)))
    hml = (o.get('homeTeamOdds') or {}).get('moneyLine')
    aml = (o.get('awayTeamOdds') or {}).get('moneyLine')
    if hml and aml:
        lines.append(('moneyline', 'home', None, int(hml)))
        lines.append(('moneyline', 'away', None, int(aml)))
    # ESPN occasionally reports even money as 100/-100 variants; clamp to valid American odds.
    return [(mk, sd, lv, od if abs(od) >= 100 else -110) for mk, sd, lv, od in lines]


def ingest(db, house_book_name, session=None, log=print):
    """Upsert every game in the window for every sport with an espn_path, and
    post consensus lines under the house book for games that have none yet.
    Returns a dict of counts."""
    counts = {'games': 0, 'finals': 0, 'lines': 0}
    sports = db.execute("SELECT id, key, espn_path FROM Sports WHERE espn_path IS NOT NULL")
    house = db.execute("SELECT id, default_exposure_limit FROM Books WHERE name = :n", n=house_book_name)
    house_id = house[0].id if house else None
    house_limit = house[0].default_exposure_limit if house else None

    for sport in sports:
        try:
            events = fetch_scoreboard(sport.espn_path, session=session)
        except Exception as e:  # network problems should not kill the other sports
            log(f'{sport.key}: fetch failed: {e}')
            continue
        with db.transaction() as conn:
            ex = lambda sql, **kw: db.execute_on(conn, sql, **kw)
            for event in events:
                game, odds = parse_event(event)
                row = ex("""
INSERT INTO Games(sport_id, external_id, home_team, away_team, home_abbr, away_abbr,
                  start_time, status, home_score, away_score)
VALUES(:sport_id, :external_id, :home_team, :away_team, :home_abbr, :away_abbr,
       :start_time, :status, :home_score, :away_score)
ON CONFLICT (external_id) DO UPDATE
    SET start_time = EXCLUDED.start_time, status = EXCLUDED.status,
        home_score = EXCLUDED.home_score, away_score = EXCLUDED.away_score,
        updated_at = current_timestamp
RETURNING id, status
""", sport_id=sport.id, **game)[0]
                counts['games'] += 1
                if row.status == 'final':
                    counts['finals'] += 1
                if house_id and game['status'] == 'scheduled':
                    for market, side, line_value, od in odds:
                        inserted = ex("""
INSERT INTO Lines(game_id, book_id, market, side, line_value, odds_american, exposure_limit)
VALUES(:game_id, :book_id, :market, :side, :line_value, :odds, :limit)
ON CONFLICT (game_id, book_id, market, side) DO NOTHING
RETURNING id
""", game_id=row.id, book_id=house_id, market=market, side=side,
                            line_value=line_value, odds=od, limit=house_limit)
                        counts['lines'] += len(inserted)
            # Lines on games that started can no longer be bet.
            ex("""
UPDATE Lines l SET is_open = FALSE, updated_at = current_timestamp
FROM Games g
WHERE g.id = l.game_id AND l.is_open
  AND (g.status <> 'scheduled' OR g.start_time <= current_timestamp)
""")
        log(f"{sport.key}: {len(events)} events")
    return counts
