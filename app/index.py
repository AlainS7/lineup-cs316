from flask import Blueprint, render_template, request

from .models.game import Game
from .models.user import User

bp = Blueprint('index', __name__)

PER_PAGE = 50


@bp.route('/')
def index():
    """Browse games: filter by sport, search by team, pick upcoming/final, sort."""
    sport = request.args.get('sport', '')
    q = request.args.get('q', '').strip()
    status = request.args.get('status', 'upcoming')
    sort = request.args.get('sort', 'time')
    # Unchecked by default: a scheduled game with no open line is not bettable.
    show_all = request.args.get('show_all') == '1'
    page = max(1, request.args.get('page', 1, type=int))
    # Fetch one extra row: if it comes back there is a next page, which
    # saves a second COUNT(*) over the same joins.
    games = Game.browse(sport=sport, q=q, status=status, sort=sort,
                        has_lines=not show_all,
                        limit=PER_PAGE + 1, offset=(page - 1) * PER_PAGE)
    has_next = len(games) > PER_PAGE
    games = games[:PER_PAGE]
    return render_template('index.html', games=games, sports=Game.sports(),
                           sport=sport, q=q, status=status, sort=sort,
                           show_all=show_all, page=page, has_next=has_next,
                           first=(page - 1) * PER_PAGE + 1)


@bp.route('/leaderboard')
def leaderboard():
    return render_template('leaderboard.html', rows=User.leaderboard())
