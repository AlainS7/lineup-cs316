from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DecimalField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length, NumberRange, Optional

from .models.user import User
from .models.book import Book
from .models.slip import Slip

bp = Blueprint('users', __name__)


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.get_by_auth(form.email.data, form.password.data)
        if user is None:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('users.login'))
        login_user(user)
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('index.index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


class RegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=255)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repeat Password',
                              validators=[DataRequired(), EqualTo('password', 'Passwords must match.')])
    submit = SubmitField('Register')

    def validate_email(self, email):
        if User.email_exists(email.data):
            raise ValidationError('An account with that email already exists.')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        User.register(form.email.data, form.password.data, form.full_name.data or '')
        flash('Account created. You can log in now.', 'success')
        return redirect(url_for('users.login'))
    return render_template('register.html', title='Register', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index.index'))


class ProfileForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=255)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('New Password (leave blank to keep)', validators=[Optional(), Length(min=6)])
    password2 = PasswordField('Repeat New Password', validators=[EqualTo('password', 'Passwords must match.')])
    submit = SubmitField('Save')

    def validate_email(self, email):
        if User.email_exists(email.data, exclude_id=current_user.id):
            raise ValidationError('Another account already uses that email.')


class FundsForm(FlaskForm):
    amount = DecimalField('Amount', places=2, validators=[DataRequired(), NumberRange(min=0.01, max=1_000_000)])
    topup = SubmitField('Top up')
    withdraw = SubmitField('Withdraw')


@bp.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    form = ProfileForm(obj=current_user)
    funds = FundsForm()
    if 'submit' in request.form and form.validate_on_submit():
        User.update_profile(current_user.id, form.email.data, form.full_name.data,
                            form.password.data or None)
        flash('Profile updated.', 'success')
        return redirect(url_for('users.account'))
    if ('topup' in request.form or 'withdraw' in request.form) and funds.validate_on_submit():
        amount = Decimal(funds.amount.data)
        if funds.withdraw.data:
            if amount > Decimal(current_user.balance):
                flash('You cannot withdraw more than your balance.', 'danger')
                return redirect(url_for('users.account'))
            User.adjust_balance(current_user.id, -amount, 'withdraw')
            flash(f'Withdrew ${amount:,.2f}.', 'success')
        else:
            User.adjust_balance(current_user.id, amount, 'topup')
            flash(f'Added ${amount:,.2f} to your balance.', 'success')
        return redirect(url_for('users.account'))
    return render_template('account.html', form=form, funds=funds,
                           transactions=User.transactions(current_user.id),
                           book=Book.get_by_owner(current_user.id),
                           recent=Slip.history(current_user.id, limit=5))


@bp.route('/users/<int:id>')
def public_profile(id):
    summary = User.public_summary(id)
    if summary is None:
        return render_template('404.html'), 404
    return render_template('public_user.html', u=summary)
