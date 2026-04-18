#!/usr/bin/env bash
set -euo pipefail

API_URL="http://127.0.0.1:8000/v1/models"
API_KEY="local-token"
SCREEN_NAME="gemma_pp"
LOG_FILE="/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/dx_bench/results/med42_70b_watch.log"

RUN_CMD="cd /vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/dx_bench && /vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python run_dataset_suite.py --model m42-health/Llama3-Med42-70B --backend openai_http --api-base-url http://127.0.0.1:8000/v1 --api-key local-token --batch-size 18 --request-timeout-s 600 --empty-completion-retries 2"

echo "[$(date -Is)] watcher started" >> "$LOG_FILE"

until curl -fsS -H "Authorization: Bearer ${API_KEY}" "$API_URL" >/dev/null 2>&1; do
  echo "[$(date -Is)] server not ready yet" >> "$LOG_FILE"
  sleep 30
done

echo "[$(date -Is)] server ready, launching pipeline in screen ${SCREEN_NAME}" >> "$LOG_FILE"
screen -S "$SCREEN_NAME" -X stuff "$(printf '%s\n' "$RUN_CMD")"
echo "[$(date -Is)] command sent to ${SCREEN_NAME}" >> "$LOG_FILE"
