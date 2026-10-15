from decimal import Decimal

from app.odds import american_to_decimal, parlay_decimal, payout, grade_leg, grade_slip, format_line


def test_american_to_decimal():
    assert american_to_decimal(150) == Decimal('2.5')
    assert american_to_decimal(-200) == Decimal('1.5')
    assert american_to_decimal(100) == Decimal(2)


def test_parlay_and_payout():
    dec = parlay_decimal([-110, -110])
    assert payout(10, dec) == Decimal('36.45')
    assert payout(Decimal('25'), american_to_decimal(115)) == Decimal('53.75')


def test_grade_moneyline():
    assert grade_leg('moneyline', 'home', None, 27, 20) == 'won'
    assert grade_leg('moneyline', 'away', None, 27, 20) == 'lost'
    assert grade_leg('moneyline', 'home', None, 20, 20) == 'push'


def test_grade_spread():
    # Home favored by 3.5, wins by 7: covers. Away +3.5 loses.
    assert grade_leg('spread', 'home', Decimal('-3.5'), 27, 20) == 'won'
    assert grade_leg('spread', 'away', Decimal('3.5'), 27, 20) == 'lost'
    # Wins by exactly the number: push.
    assert grade_leg('spread', 'home', Decimal('-7'), 27, 20) == 'push'
    # Underdog loses by less than the spread: covers.
    assert grade_leg('spread', 'away', Decimal('7.5'), 27, 20) == 'won'


def test_grade_total():
    assert grade_leg('total', 'over', Decimal('47.5'), 27, 20) == 'lost'
    assert grade_leg('total', 'under', Decimal('47.5'), 27, 20) == 'won'
    assert grade_leg('total', 'over', Decimal('47'), 27, 20) == 'push'


def test_grade_slip():
    assert grade_slip(['won', 'won'], [-110, -110], 10) == ('won', Decimal('36.45'))
    assert grade_slip(['won', 'lost'], [-110, -110], 10) == ('lost', Decimal('0.00'))
    assert grade_slip(['won', 'pending'], [-110, -110], 10) == ('pending', None)
    assert grade_slip(['lost', 'pending'], [-110, -110], 10) == ('lost', Decimal('0.00'))
    # A pushed leg drops out of the parlay.
    assert grade_slip(['won', 'push'], [150, -110], 10) == ('won', Decimal('25.00'))
    assert grade_slip(['push'], [150], 10) == ('push', Decimal('10.00'))


def test_format_line():
    assert format_line('spread', 'home', Decimal('-2.5'), 'DEN', 'SEA') == 'DEN -2.5'
    assert format_line('spread', 'away', Decimal('2.5'), 'DEN', 'SEA') == 'SEA +2.5'
    assert format_line('total', 'over', Decimal('40.5')) == 'Over 40.5'
    assert format_line('moneyline', 'away', None, 'DEN', 'SEA') == 'SEA ML'
