"""Command-line jobs: `flask db-init`, `flask ingest`, `flask settle`,
`flask finalize`. In production ingest+settle would run on a schedule
(cron); for the demo they are invoked by hand."""
import os
import subprocess
from pathlib import Path

import click
from flask import current_app

from .ingest import ingest as run_ingest
from .settlement import settle as run_settle

DB_DIR = Path(__file__).resolve().parent.parent / 'db'


def register_cli(app):
    @app.cli.command('db-init')
    def db_init():
        """Drop and recreate the database from db/create.sql + db/load.sql."""
        name = app.config['DB_NAME']
        env = dict(os.environ,
                   PGHOST=app.config['DB_HOST'], PGPORT=str(app.config['DB_PORT']),
                   PGUSER=app.config['DB_USER'], PGPASSWORD=app.config['DB_PASSWORD'])
        app.db.engine.dispose()
        subprocess.run(['dropdb', '--if-exists', name], env=env, check=True)
        subprocess.run(['createdb', name], env=env, check=True)
        for f in ('create.sql', 'load.sql'):
            subprocess.run(['psql', '-v', 'ON_ERROR_STOP=1', '-q', '-d', name, '-f', f],
                           cwd=DB_DIR, env=env, check=True)
        click.echo(f'database {name} created and seeded')

    @app.cli.command('ingest')
    def ingest():
        """Pull games, scores and consensus lines from ESPN."""
        counts = run_ingest(current_app.db, current_app.config['HOUSE_BOOK_NAME'], log=click.echo)
        click.echo(f"upserted {counts['games']} games ({counts['finals']} final), "
                   f"posted {counts['lines']} new lines")

    @app.cli.command('settle')
    def settle():
        """Grade pending legs on final games and pay out resolved slips."""
        legs, slips = run_settle(current_app.db)
        click.echo(f'graded {legs} legs, settled {slips} slips')

    @app.cli.command('finalize')
    @click.argument('game_id', type=int)
    @click.argument('home_score', type=int)
    @click.argument('away_score', type=int)
    def finalize(game_id, home_score, away_score):
        """Record a final score by hand (demo helper), then settle."""
        from .models.game import Game
        Game.set_final(game_id, home_score, away_score)
        current_app.db.execute("""
UPDATE Lines SET is_open = FALSE, updated_at = current_timestamp WHERE game_id = :g
""", g=game_id)
        legs, slips = run_settle(current_app.db)
        click.echo(f'game {game_id} final {home_score}-{away_score}; graded {legs} legs, settled {slips} slips')
