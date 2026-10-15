from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, DecimalField, IntegerField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError, Optional

from .models.book import Book
from .models.game import Game
from .models.line import Line

bp = Blueprint('books', __name__)


class BookForm(FlaskForm):
    name = StringField('Book name', validators=[DataRequired(), Length(min=2, max=64)])
    default_exposure_limit = DecimalField('Default exposure limit per line ($)', places=2,
                                          validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Save')


def validate_american(form, field):
    if field.data is not None and -100 < field.data < 100:
        raise ValidationError('American odds must be at least +100 or at most -100.')


class LineForm(FlaskForm):
    game_id = SelectField('Game', coerce=int, validators=[DataRequired()])
    market = SelectField('Market', choices=[('moneyline', 'Moneyline'), ('spread', 'Spread'), ('total', 'Total')])
    side = SelectField('Side', choices=[('home', 'Home'), ('away', 'Away'), ('over', 'Over'), ('under', 'Under')])
    line_value = DecimalField('Line value (spread handicap for this side, or total points)',
                              places=1, validators=[Optional()])
    odds_american = IntegerField('Odds (American, e.g. -110 or +150)',
                                 validators=[DataRequired(), validate_american])
    exposure_limit = DecimalField('Exposure limit ($)', places=2, validators=[DataRequired(), NumberRange(min=0)])
    is_open = BooleanField('Open for betting', default=True)
    submit = SubmitField('Save line')

    def validate_side(self, field):
        if self.market.data == 'total' and field.data not in ('over', 'under'):
            raise ValidationError('Totals use Over/Under.')
        if self.market.data != 'total' and field.data not in ('home', 'away'):
            raise ValidationError('Moneylines and spreads use Home/Away.')

    def validate_line_value(self, field):
        if self.market.data == 'moneyline' and field.data is not None:
            raise ValidationError('Moneylines have no line value.')
        if self.market.data != 'moneyline' and field.data is None:
            raise ValidationError('Spreads and totals need a line value.')


def _my_book_or_404():
    book = Book.get_by_owner(current_user.id)
    if book is None:
        abort(404)
    return book


@bp.route('/book')
@login_required
def dashboard():
    book = Book.get_by_owner(current_user.id)
    if book is None:
        return redirect(url_for('books.create'))
    return render_template('book_dashboard.html', book=book, lines=Book.lines(book.id),
                           pnl=Book.pnl(book.id), action=Book.recent_action(book.id))


@bp.route('/book/new', methods=['GET', 'POST'])
@login_required
def create():
    if Book.get_by_owner(current_user.id):
        return redirect(url_for('books.dashboard'))
    form = BookForm()
    if form.validate_on_submit():
        if Book.name_exists(form.name.data):
            flash('That book name is taken.', 'danger')
        else:
            Book.create(current_user.id, form.name.data, form.default_exposure_limit.data)
            flash('Your book is open. Post some lines!', 'success')
            return redirect(url_for('books.dashboard'))
    return render_template('book_form.html', form=form, title='Open a book')


@bp.route('/book/edit', methods=['GET', 'POST'])
@login_required
def edit():
    book = _my_book_or_404()
    form = BookForm(data={'name': book.name, 'default_exposure_limit': book.default_exposure_limit})
    if form.validate_on_submit():
        if form.name.data != book.name and Book.name_exists(form.name.data):
            flash('That book name is taken.', 'danger')
        else:
            Book.update(book.id, form.name.data, form.default_exposure_limit.data)
            flash('Book updated.', 'success')
            return redirect(url_for('books.dashboard'))
    return render_template('book_form.html', form=form, title='Edit book')


@bp.route('/book/lines/new', methods=['GET', 'POST'])
@login_required
def new_line():
    book = _my_book_or_404()
    form = LineForm()
    games = Game.upcoming_for_book()
    form.game_id.choices = [(g.id, f'{g.away_abbr} @ {g.home_abbr}  ({g.sport}, {g.start_time:%b %d %I:%M %p})')
                            for g in games]
    if request.method == 'GET':
        form.exposure_limit.data = book.default_exposure_limit
        if request.args.get('game_id', '').isdigit():
            form.game_id.data = int(request.args['game_id'])
    if form.validate_on_submit():
        if Line.exists(form.game_id.data, book.id, form.market.data, form.side.data):
            flash('You already have a line on that market and side. Edit it instead.', 'danger')
        else:
            Line.create(form.game_id.data, book.id, form.market.data, form.side.data,
                        form.line_value.data, form.odds_american.data, form.exposure_limit.data)
            flash('Line posted.', 'success')
            return redirect(url_for('books.dashboard'))
    return render_template('line_form.html', form=form, title='Post a line', line=None)


@bp.route('/book/lines/<int:line_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_line(line_id):
    book = _my_book_or_404()
    line = Line.get(line_id)
    if line is None or line.book_id != book.id:
        abort(404)
    form = LineForm(data={'game_id': line.game_id, 'market': line.market, 'side': line.side,
                          'line_value': line.line_value, 'odds_american': line.odds_american,
                          'exposure_limit': line.exposure_limit, 'is_open': line.is_open})
    form.game_id.choices = [(line.game_id, f'{line.away_abbr} @ {line.home_abbr}')]
    if form.validate_on_submit():
        Line.update(line.id, form.line_value.data, form.odds_american.data,
                    form.exposure_limit.data, form.is_open.data)
        flash('Line updated. Bets already placed keep their locked odds.', 'success')
        return redirect(url_for('books.dashboard'))
    return render_template('line_form.html', form=form, title='Edit line', line=line)


@bp.route('/book/lines/<int:line_id>/toggle', methods=['POST'])
@login_required
def toggle_line(line_id):
    book = _my_book_or_404()
    line = Line.get(line_id)
    if line is None or line.book_id != book.id:
        abort(404)
    Line.set_open(line.id, not line.is_open)
    return redirect(url_for('books.dashboard'))


@bp.route('/book/lines/<int:line_id>/delete', methods=['POST'])
@login_required
def delete_line(line_id):
    book = _my_book_or_404()
    line = Line.get(line_id)
    if line is None or line.book_id != book.id:
        abort(404)
    if Line.delete_if_unused(line.id):
        flash('Line removed.', 'success')
    else:
        flash('Bets have been placed on that line, so it can only be closed, not removed.', 'warning')
    return redirect(url_for('books.dashboard'))


@bp.route('/books/<int:id>')
def public(id):
    book = Book.get(id)
    if book is None:
        abort(404)
    return render_template('book_public.html', book=book, lines=Book.lines(book.id, include_closed=False))
