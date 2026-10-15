"""Odds arithmetic shared by the bet slip, settlement, and templates.

All prices are stored as American odds (+150, -110). Payout math uses the
equivalent decimal odds, and a parlay's decimal odds are the product of its
legs' decimal odds.
"""
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal('0.01')


def american_to_decimal(odds):
    """+150 -> 2.5, -110 -> 1.909..."""
    odds = int(odds)
    if odds > 0:
        return Decimal(1) + Decimal(odds) / Decimal(100)
    return Decimal(1) + Decimal(100) / Decimal(-odds)


def parlay_decimal(odds_list):
    total = Decimal(1)
    for o in odds_list:
        total *= american_to_decimal(o)
    return total


def payout(stake, decimal_odds):
    """Total amount returned to the user (stake included) if the bet wins."""
    return (Decimal(stake) * decimal_odds).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def format_american(odds):
    odds = int(odds)
    return f'+{odds}' if odds > 0 else str(odds)


def format_line(market, side, line_value, home_abbr=None, away_abbr=None):
    """Human label for a line, e.g. 'DEN -2.5', 'Over 40.5', 'SEA ML'."""
    team = {'home': home_abbr, 'away': away_abbr}.get(side, side)
    if market == 'moneyline':
        return f'{team} ML'
    if market == 'spread':
        v = Decimal(line_value)
        sign = '+' if v > 0 else ''
        return f'{team} {sign}{v}'
    return f'{side.capitalize()} {Decimal(line_value)}'


def grade_leg(market, side, line_value, home_score, away_score):
    """Decide won/lost/push for one leg given a final score. Mirrors the SQL
    CASE expression in settlement.py; kept here for unit tests and display."""
    if market == 'moneyline':
        if home_score == away_score:
            return 'push'
        home_won = home_score > away_score
        return 'won' if (side == 'home') == home_won else 'lost'
    if market == 'spread':
        margin = home_score - away_score if side == 'home' else away_score - home_score
        adj = Decimal(margin) + Decimal(line_value)
        if adj == 0:
            return 'push'
        return 'won' if adj > 0 else 'lost'
    total = Decimal(home_score + away_score)
    if total == Decimal(line_value):
        return 'push'
    went_over = total > Decimal(line_value)
    return 'won' if (side == 'over') == went_over else 'lost'


def grade_slip(leg_statuses, leg_odds, stake):
    """Combine graded legs into a slip result.

    Returns (status, payout). Any lost leg loses the slip. Pushed legs drop
    out of a parlay (decimal odds 1). If every leg pushed the stake is
    refunded.
    """
    if any(s == 'lost' for s in leg_statuses):
        return 'lost', Decimal('0.00')
    if any(s == 'pending' for s in leg_statuses):
        return 'pending', None
    won_odds = [o for s, o in zip(leg_statuses, leg_odds) if s == 'won']
    if not won_odds:
        return 'push', Decimal(stake).quantize(TWO_PLACES)
    return 'won', payout(stake, parlay_decimal(won_odds))
