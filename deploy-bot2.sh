#!/usr/bin/env bash
set -euo pipefail

# Second instance of the exact same app/code, used purely for an A/B
# comparison: this instance's config.json sets "rotation_enabled": false,
# so a full portfolio simply skips a new buy instead of rotating out a
# technically-weak holding — compare its paper-trading performance against
# the production instance (deploy.sh, rotation on) over a couple of weeks.
# Separate container, separate port (:8082), separate /data volume, and a
# separate .env pointing at its own dedicated Alpaca paper account (never
# share credentials with production or the local-dev account — see PLAN.md
# "Incident: local run executed a real unwanted trade").
source "$(dirname "${BASH_SOURCE[0]}")/deploy_common.sh"

deploy_instance \
  REMOTE_DIR="/opt/mytradebot2" \
  IMAGE_NAME="mytradebot2-app" \
  CONTAINER_NAME="mytradebot2" \
  HOST_PORT="8082"
