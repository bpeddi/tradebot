#!/usr/bin/env bash
# Shared deploy logic for both mytradebot instances (production: deploy.sh,
# the no-rotation A/B comparison instance: deploy-bot2.sh). Not meant to be
# run directly — sourced by those two scripts, each of which calls
# deploy_instance with its own REMOTE_DIR/IMAGE_NAME/CONTAINER_NAME/
# HOST_PORT. Keeping the build/sync/run logic in one place means a fix here
# (e.g. a new --exclude) automatically applies to both instances instead of
# needing to be copy-pasted and kept in sync by hand.
set -euo pipefail

EC2_USER="ec2-user"
EC2_HOST="34.192.71.198"
EC2_KEY="C:/Users/balap/.ssh/strack.pem"

deploy_instance() {
  local REMOTE_DIR IMAGE_NAME CONTAINER_NAME HOST_PORT
  for arg in "$@"; do
    case "$arg" in
      REMOTE_DIR=*)     REMOTE_DIR="${arg#REMOTE_DIR=}" ;;
      IMAGE_NAME=*)     IMAGE_NAME="${arg#IMAGE_NAME=}" ;;
      CONTAINER_NAME=*) CONTAINER_NAME="${arg#CONTAINER_NAME=}" ;;
      HOST_PORT=*)      HOST_PORT="${arg#HOST_PORT=}" ;;
      *) echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
  done

  echo "==> [${CONTAINER_NAME}] Building frontend locally..."
  (cd "$(dirname "${BASH_SOURCE[0]}")/web/frontend" && npm run build)

  echo "==> [${CONTAINER_NAME}] Syncing code to EC2 (${REMOTE_DIR})..."
  ssh -i "${EC2_KEY}" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_HOST}" \
      "mkdir -p ${REMOTE_DIR} ${REMOTE_DIR}/data"
  tar --exclude='./.git' \
      --exclude='./.venv' \
      --exclude='./__pycache__' \
      --exclude='*.pyc' \
      --exclude='./.env' \
      --exclude='./trades.db' \
      --exclude='./state.json' \
      --exclude='./uvicorn.out.log' \
      --exclude='./uvicorn.err.log' \
      --exclude='./cron.log' \
      --exclude='./web/frontend/node_modules' \
      --exclude='./web/frontend/src' \
      -C "$(dirname "${BASH_SOURCE[0]}")" \
      -czf - . \
    | ssh -i "${EC2_KEY}" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_HOST}" \
        "tar -xzf - -C ${REMOTE_DIR}"

  echo "==> [${CONTAINER_NAME}] Building and restarting on EC2 (:${HOST_PORT})..."
  ssh -i "${EC2_KEY}" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_HOST}" \
      "REMOTE_DIR='${REMOTE_DIR}' IMAGE_NAME='${IMAGE_NAME}' CONTAINER_NAME='${CONTAINER_NAME}' HOST_PORT='${HOST_PORT}' bash -s" << 'REMOTE'
set -euo pipefail
cd "${REMOTE_DIR}"
DOCKER_BUILDKIT=0 docker build -t "${IMAGE_NAME}" .
docker stop "${CONTAINER_NAME}" 2>/dev/null || true
docker rm   "${CONTAINER_NAME}" 2>/dev/null || true
docker run -d \
  --name "${CONTAINER_NAME}" \
  --network=host \
  --security-opt seccomp=unconfined \
  --ulimit nproc=65535:65535 \
  --ulimit nofile=65535:65535 \
  -e PORT="${HOST_PORT}" \
  -v "${REMOTE_DIR}/data:/data" \
  --env-file "${REMOTE_DIR}/.env" \
  --restart unless-stopped \
  "${IMAGE_NAME}"
sleep 3
curl -sf "http://localhost:${HOST_PORT}/docs" > /dev/null && echo "Health check passed." || echo "WARNING: health check failed."
docker logs --tail 20 "${CONTAINER_NAME}"
REMOTE

  echo "==> [${CONTAINER_NAME}] Done. App at http://${EC2_HOST}:${HOST_PORT}"
}
