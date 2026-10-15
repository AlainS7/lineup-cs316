#!/bin/bash
# Start the Line-up dev server. Inside the course container use port 8080
# (forwarded to your laptop); on a laptop where Docker already holds 8080,
# pass another port: ./lineup.sh 8081
cd "$(dirname "$0")"
# Activate ./.venv only if it is usable from this machine (a venv created on
# the laptop does not run inside the container, and vice versa).
if [ -z "$VIRTUAL_ENV" ] && [ -x .venv/bin/python ] && .venv/bin/python -c '' 2>/dev/null; then
  source .venv/bin/activate
fi
export PATH="$HOME/.local/bin:$PATH"
exec flask run --host 0.0.0.0 --port "${1:-8080}"
