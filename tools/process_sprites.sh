#!/usr/bin/env bash
# Clean + register Carl's sprite PNGs. Sets up a local venv on first run
# (Homebrew python is externally-managed, so we don't touch the system env).
#
#   ./tools/process_sprites.sh --in raw/ --out sprites/ --size 360
#
# Put ChatGPT's exported PNGs in raw/ first; cleaned sprites land in sprites/,
# with sprites/_preview.png to eyeball registration.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"

if [ ! -x "$VENV/bin/python" ]; then
  echo "Setting up sprite-tools venv (one time)…"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet Pillow numpy
fi

exec "$VENV/bin/python" "$DIR/process_sprites.py" "$@"
