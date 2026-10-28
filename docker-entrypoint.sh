#!/bin/bash
set -e

mkdir -p "$MYTRADEBOT_DATA_DIR"

# Seed config.json into the persistent volume on first run only — never
# overwrite it on later deploys, since that's where the dashboard's live
# edits (symbols, slots, schedule) actually live.
if [ ! -f "$MYTRADEBOT_DATA_DIR/config.json" ]; then
    cp /app/config.default.json "$MYTRADEBOT_DATA_DIR/config.json"
fi

# The scheduled bot runs as a subprocess of this uvicorn process (see
# web/api/scheduler.py), so it inherits this process's environment — no
# separate env-propagation step needed.
exec uvicorn web.api.main:app --host 0.0.0.0 --port "${PORT:-8081}"
