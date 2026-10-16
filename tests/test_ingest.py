"""Parser tests for the ESPN ingest job.

The fixture is a trimmed real response from
  .../football/nfl/scoreboard?dates=20261018  (one scheduled game)
plus one final game from 20261012, so the parsers are exercised against the
shape ESPN actually returns rather than one we invented.
"""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.ingest import fetch_scoreboard, parse_event, parse_odds

EVENTS = json.loads((Path(__file__).parent / 'fixtures' / 'espn_nfl.json').read_text())['events']
SCHEDULED, FINAL = EVENTS[0], EVENTS[1]


def test_parse_scheduled_event():
    game, odds = parse_event(SCHEDULED)
    assert game['external_id'] == '401872996'
    assert game['home_abbr'] == 'JAX' and game['away_abbr'] == 'HOU'
    assert game['status'] == 'scheduled'
    # A game that has not been played has no score, even though ESPN sends "0".
    assert game['home_score'] is None and game['away_score'] is None
    assert odds


def test_parse_final_event_keeps_scores():
    game, _ = parse_event(FINAL)
    assert game['status'] == 'final'
    assert isinstance(game['home_score'], int)
    assert isinstance(game['away_score'], int)


def test_spread_sides_are_mirrored():
    """'JAX -2.5' with JAX at home must give home -2.5 and away +2.5."""
    _, odds = parse_event(SCHEDULED)
    spreads = {side: value for market, side, value, _ in odds if market == 'spread'}
    assert spreads['home'] == Decimal('-2.5')
    assert spreads['away'] == Decimal('2.5')
    assert spreads['home'] == -spreads['away']


def test_total_has_both_sides_at_the_same_number():
    _, odds = parse_event(SCHEDULED)
    totals = {side: value for market, side, value, _ in odds if market == 'total'}
    assert totals['over'] == totals['under'] == Decimal('42.5')


def test_missing_prices_default_to_minus_110():
    """ESPN often sends a spread and total with no price attached."""
    _, odds = parse_event(SCHEDULED)
    assert all(price == -110 for *_, price in odds)


def test_moneyline_needs_both_sides():
    game = {'home_abbr': 'JAX', 'away_abbr': 'HOU'}
    both = parse_odds([{'homeTeamOdds': {'moneyLine': -150},
                        'awayTeamOdds': {'moneyLine': 130}}], game)
    assert sorted((s, p) for m, s, _, p in both if m == 'moneyline') == [('away', 130), ('home', -150)]
    # Only one side priced: skip it rather than invent the other.
    one = parse_odds([{'homeTeamOdds': {'moneyLine': -150}, 'awayTeamOdds': {}}], game)
    assert not [o for o in one if o[0] == 'moneyline']


def test_unknown_favourite_abbreviation_is_skipped():
    """If the abbr in 'details' matches neither team, no spread is posted."""
    game = {'home_abbr': 'JAX', 'away_abbr': 'HOU'}
    odds = parse_odds([{'details': 'XYZ -2.5', 'overUnder': 42.5}], game)
    assert not [o for o in odds if o[0] == 'spread']
    assert [o for o in odds if o[0] == 'total']  # the total still comes through


@pytest.mark.parametrize('raw', [50, -50, 0])
def test_invalid_american_odds_are_clamped(raw):
    """Lines.odds_american requires |odds| >= 100; anything else becomes -110."""
    game = {'home_abbr': 'JAX', 'away_abbr': 'HOU'}
    odds = parse_odds([{'overUnder': 42.5, 'overOdds': raw, 'underOdds': raw}], game)
    assert all(price == -110 for *_, price in odds)


def test_no_odds_block_returns_no_lines():
    assert parse_odds([], {'home_abbr': 'JAX', 'away_abbr': 'HOU'}) == []


def test_fetch_scoreboard_dedupes_across_days():
    """The window is one request per day and a game can appear on two of
    them; each event must still be returned once."""
    calls = []

    class FakeSession:
        def get(self, url, params=None, timeout=None):
            calls.append(params['dates'])
            return FakeResponse()

    class FakeResponse:
        @staticmethod
        def raise_for_status():
            pass

        @staticmethod
        def json():
            return {'events': EVENTS}

    events = fetch_scoreboard('football/nfl', days_back=1, days_ahead=1, session=FakeSession())
    assert len(calls) == 3                      # today-1, today, today+1
    assert [e['id'] for e in events] == ['401872996', '401872994']
