from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required

from .models.game import Game
from .models.line import Line
from .models.slip import Cart

bp = Blueprint('games', __name__)


@bp.route('/games/<int:id>')
def detail(id):
    game = Game.get(id)
    if game is None:
        return render_template('404.html'), 404
    lines = Game.lines(id)
    in_cart = set()
    if current_user.is_authenticated:
        in_cart = {it.line_id for it in Cart.items(current_user.id)}
    # Group: market -> side -> [lines from each book]
    grouped = {}
    for l in lines:
        grouped.setdefault(l.market, {}).setdefault(l.side, []).append(l)
    return render_template('game.html', game=game, grouped=grouped, in_cart=in_cart)


@bp.route('/lines/<int:line_id>/add', methods=['POST'])
@login_required
def add_to_slip(line_id):
    """Add a line to the user's bet slip with a stake."""
    line = Line.get(line_id)
    if line is None:
        flash('That line does not exist.', 'danger')
        return redirect(url_for('index.index'))
    try:
        stake = Decimal(request.form.get('stake', '10')).quantize(Decimal('0.01'))
    except InvalidOperation:
        stake = Decimal(0)
    if stake <= 0:
        flash('Stake must be a positive amount.', 'danger')
    elif not line.is_open or line.game_status != 'scheduled':
        flash('That line is no longer open for betting.', 'warning')
    else:
        Cart.add(current_user.id, line_id, stake)
        flash('Added to your bet slip.', 'success')
    return redirect(request.referrer or url_for('games.detail', id=line.game_id))
