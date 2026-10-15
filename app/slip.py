from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required

from .models.slip import Cart, Slip, SlipError
from .odds import american_to_decimal, parlay_decimal, payout

bp = Blueprint('slip', __name__)


def _money(value):
    try:
        return Decimal(value).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError):
        return None


@bp.route('/slip')
@login_required
def view():
    items = Cart.items(current_user.id)
    singles_total = sum((Decimal(it.stake) for it in items), Decimal(0))
    singles_payout = sum((payout(it.stake, american_to_decimal(it.odds_american)) for it in items), Decimal(0))
    games = [it.game_id for it in items]
    parlay_ok = len(items) >= 2 and len(set(games)) == len(games)
    parlay_dec = parlay_decimal([it.odds_american for it in items]) if items else Decimal(1)
    parlay_stake = _money(request.args.get('parlay_stake', '10')) or Decimal('10.00')
    problems = [it for it in items
                if not it.is_open or it.game_status != 'scheduled']
    return render_template('slip.html', items=items, singles_total=singles_total,
                           singles_payout=singles_payout, parlay_ok=parlay_ok,
                           parlay_dec=parlay_dec, parlay_stake=parlay_stake,
                           parlay_payout=payout(parlay_stake, parlay_dec),
                           problems=problems, n_games=len(set(games)))


@bp.route('/slip/update', methods=['POST'])
@login_required
def update():
    """Change stakes for every item in one submit."""
    for key, val in request.form.items():
        if key.startswith('stake_'):
            line_id = int(key[len('stake_'):])
            stake = _money(val)
            if stake is None or stake <= 0:
                flash('Stakes must be positive amounts.', 'danger')
                return redirect(url_for('slip.view'))
            Cart.set_stake(current_user.id, line_id, stake)
    flash('Slip updated.', 'success')
    return redirect(url_for('slip.view'))


@bp.route('/slip/remove/<int:line_id>', methods=['POST'])
@login_required
def remove(line_id):
    Cart.remove(current_user.id, line_id)
    return redirect(url_for('slip.view'))


@bp.route('/slip/clear', methods=['POST'])
@login_required
def clear():
    Cart.clear(current_user.id)
    return redirect(url_for('slip.view'))


@bp.route('/slip/place', methods=['POST'])
@login_required
def place():
    kind = request.form.get('kind', 'single')
    parlay_stake = _money(request.form.get('parlay_stake')) if kind == 'parlay' else None
    try:
        ids = Slip.place(current_user.id, kind, parlay_stake)
    except SlipError as e:
        flash(str(e), 'danger')
        return redirect(url_for('slip.view'))
    if len(ids) == 1:
        flash('Bet placed.', 'success')
        return redirect(url_for('bets.detail', id=ids[0]))
    flash(f'{len(ids)} bets placed.', 'success')
    return redirect(url_for('bets.history'))
