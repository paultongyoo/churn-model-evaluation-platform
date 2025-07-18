#!/bin/bash
set -euo pipefail

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --workflow-file)
      WORKFLOW_FILE="$2"
      shift 2
      ;;
    --dns-name)
      DNS_NAME="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

if [[ -z "${ENV_FILE:-}" || -z "${WORKFLOW_FILE:-}" || -z "${DNS_NAME:-}" ]]; then
  echo "Usage: $0 --env-file PATH --workflow-file PATH --dns-name ALB_DNS"
  exit 1
fi

MAX_RETRIES=99999
SLEEP_SECONDS=5

ENV_VARS=("MLFLOW_TRACKING_URI" "PREFECT_API_URL" "EVIDENTLY_UI_URL")
PORTS=("5000" "4200" "8000")
PATHS=("/" "/api/health" "/")

echo "🔁 Checking services for readiness at DNS: $DNS_NAME"

for idx in "${!ENV_VARS[@]}"; do
  ENV_VAR="${ENV_VARS[$idx]}"
  PORT="${PORTS[$idx]}"
  PATH="${PATHS[$idx]}"
  URL="http://$DNS_NAME:$PORT$PATH"

  # Special handling for PREFECT_API_URL
  if [ "$ENV_VAR" = "PREFECT_API_URL" ]; then
    CLEAN_URL="http://$DNS_NAME:$PORT/api"
  else
    CLEAN_URL="http://$DNS_NAME:$PORT"
  fi

  echo "🌐 Waiting for $ENV_VAR at $URL..."

  i=1
  while [ "$i" -le "$MAX_RETRIES" ]; do
    HTTP_STATUS=$(/usr/bin/curl --silent --output /dev/null --write-out "%{http_code}" "$URL" || true)
    if [ "$HTTP_STATUS" -eq 200 ]; then
      echo "✅ $ENV_VAR is ready (HTTP 200)"
      break
    fi
    echo "⏳ Retry $i/$MAX_RETRIES: $ENV_VAR not ready (HTTP $HTTP_STATUS)..."
    /usr/bin/sleep "$SLEEP_SECONDS"
    i=$((i + 1))
  done

  if [ "$HTTP_STATUS" -ne 200 ]; then
    echo "❌ Timed out waiting for $ENV_VAR to become ready."
    exit 1
  fi

  if /usr/bin/grep -q "^$ENV_VAR=" "$ENV_FILE"; then
    /usr/bin/sed -i "s|^$ENV_VAR=.*|$ENV_VAR=$CLEAN_URL|" "$ENV_FILE"
  else
    echo "$ENV_VAR=$CLEAN_URL" >> "$ENV_FILE"
  fi

  echo "📝 Updated $ENV_FILE -> $ENV_VAR=$CLEAN_URL"

  # Save for updating workflow YAML
  if [ "$ENV_VAR" = "PREFECT_API_URL" ]; then
    PREFECT_API_URL="$CLEAN_URL"
  fi
done

# --- Update deploy-prefect.yml ---
if grep -q "PREFECT_API_URL:" "$WORKFLOW_FILE"; then
  sed -i "s|PREFECT_API_URL:.*|PREFECT_API_URL: $PREFECT_API_URL|" "$WORKFLOW_FILE"
  echo "📝 Updated PREFECT_API_URL in $WORKFLOW_FILE"
else
  echo "⚠️ WARNING: PREFECT_API_URL not found in $WORKFLOW_FILE"
fi

echo "✅ All services checked and files updated."
