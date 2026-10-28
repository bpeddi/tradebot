# web/frontend/dist/ is pre-built locally before deploy (see deploy.sh)
#
# No apt-get here by design: the twice-daily schedule runs via an in-process
# asyncio scheduler (web/api/scheduler.py), not OS cron — avoids needing a
# cron daemon/package install, its environment-propagation quirks, and a
# host-specific Docker seccomp restriction that blocked installing packages
# via apt-get at build time on one EC2 target.
FROM python:3.12-slim AS runtime
WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY web/requirements.txt ./web/requirements.txt
RUN pip install --no-cache-dir --progress-bar off -r web/requirements.txt

COPY trading_bot.py ./
# Shipped only as a one-time seed for a fresh deploy's /data volume — the
# live config.json that the dashboard edits lives in /data, not here, so
# redeploys never clobber it.
COPY config.json ./config.default.json
COPY web/__init__.py ./web/__init__.py
COPY web/api/ ./web/api/
COPY web/frontend/dist/ ./web/frontend/dist/

COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV MYTRADEBOT_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1
ENV PORT=8081
EXPOSE 8081

ENTRYPOINT ["/entrypoint.sh"]
