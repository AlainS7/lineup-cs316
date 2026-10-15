from flask import Blueprint, render_template, request

from .models.game import Game
from .models.user import User

bp = Blueprint('index', __name__)


@bp.route('/')
def index():
    """Browse games: filter by sport, search by team, pick upcoming/final, sort."""
    sport = request.args.get('sport', '')
    q = request.args.get('q', '').strip()
    status = request.args.get('status', 'upcoming')
    sort = request.args.get('sort', 'time')
    games = Game.browse(sport=sport, q=q, status=status, sort=sort)
    return render_template('index.html', games=games, sports=Game.sports(),
                           sport=sport, q=q, status=status, sort=sort)


@bp.route('/leaderboard')
def leaderboard():
    return render_template('leaderboard.html', rows=User.leaderboard())
