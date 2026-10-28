#!/usr/bin/env bash
set -euo pipefail

# Same EC2 box as tasty_trade (see that project's deploy.sh/CLAUDE.md) —
# already running nginx->Spring Boot on :80 and tasty_trade on :8000.
# This app uses :8081 (open that port in the EC2 security group first).
#
# Shared deploy logic lives in deploy_common.sh so this script and
# deploy-bot2.sh (the no-rotation A/B comparison instance, :8082) stay in
# sync — same image/code, different container name/port/data dir/.env.
source "$(dirname "${BASH_SOURCE[0]}")/deploy_common.sh"

deploy_instance \
  REMOTE_DIR="/opt/mytradebot" \
  IMAGE_NAME="mytradebot-app" \
  CONTAINER_NAME="mytradebot" \
  HOST_PORT="8081"
