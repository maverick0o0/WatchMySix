#!/usr/bin/env bash
set -euo pipefail

WATCHMYSIX_HOME=${WATCHMYSIX_HOME:-/opt/watchmysix}
BACKEND_SCRIPT="$WATCHMYSIX_HOME/backend/scripts/prestart.sh"

if [[ -x "$BACKEND_SCRIPT" ]]; then
  echo "[entrypoint] Running startup checks and migrations"
  "$BACKEND_SCRIPT"
else
  echo "[entrypoint] Warning: backend prestart script not found at $BACKEND_SCRIPT" >&2
fi

# Launch backend API
UVICORN_CMD=(uvicorn backend.main:app --host 0.0.0.0 --port 8000)
"${UVICORN_CMD[@]}" &
BACKEND_PID=$!

terminate() {
  echo "[entrypoint] Shutting down services"
  if kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID"
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${NGINX_PID:-}" ]] && kill -0 "$NGINX_PID" 2>/dev/null; then
    kill "$NGINX_PID"
    wait "$NGINX_PID" 2>/dev/null || true
  fi
}

trap terminate SIGINT SIGTERM

# Launch NGINX in the foreground (daemon disabled)
nginx -g 'daemon off;' &
NGINX_PID=$!

# Wait for either process to exit
wait -n "$BACKEND_PID" "$NGINX_PID"
STATUS=$?
terminate
exit $STATUS
