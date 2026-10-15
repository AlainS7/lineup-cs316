from flask import Blueprint, render_template, request, abort
from flask_login import current_user, login_required

from .models.slip import Slip

bp = Blueprint('bets', __name__)


@bp.route('/bets')
@login_required
def history():
    status = request.args.get('status') or None
    if status not in (None, 'pending', 'won', 'lost', 'push', 'void'):
        status = None
    return render_template('bets.html', slips=Slip.history(current_user.id, status=status), status=status)


@bp.route('/bets/<int:id>')
@login_required
def detail(id):
    slip = Slip.get(id)
    if slip is None or slip.user_id != current_user.id:
        abort(404)
    return render_template('bet_detail.html', slip=slip, legs=Slip.legs(id))
