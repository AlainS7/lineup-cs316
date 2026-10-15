from flask import Flask
from flask_login import LoginManager
from flask_wtf import CSRFProtect

from config import Config
from .db import DB

login = LoginManager()
login.login_view = 'users.login'
login.login_message = 'Please log in to do that.'
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.db = DB(app)
    login.init_app(app)
    csrf.init_app(app)  # every POST form carries a CSRF token

    from .index import bp as index_bp
    app.register_blueprint(index_bp)

    from .users import bp as users_bp
    app.register_blueprint(users_bp)

    from .games import bp as games_bp
    app.register_blueprint(games_bp)

    from .slip import bp as slip_bp
    app.register_blueprint(slip_bp)

    from .bets import bp as bets_bp
    app.register_blueprint(bets_bp)

    from .books import bp as books_bp
    app.register_blueprint(books_bp)

    from .cli import register_cli
    register_cli(app)

    from .odds import american_to_decimal, format_american, format_line
    app.jinja_env.filters['decimal_odds'] = american_to_decimal
    app.jinja_env.filters['american'] = format_american
    app.jinja_env.filters['line'] = format_line

    from flask_login import current_user
    from .models.slip import Cart

    @app.context_processor
    def inject_cart_count():
        if current_user.is_authenticated:
            return {'cart_count': Cart.count(current_user.id)}
        return {'cart_count': 0}

    return app
