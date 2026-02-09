#!/usr/bin/env bash
set -euo pipefail

OWNER="smit-darji"
REPO="knit-project-argocd"
WORKFLOW_FILE="update-image.yaml"
BRANCH="Master"

: "${GH_TOKEN:?GH_TOKEN not set}"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <service> <tag>"
  exit 1
fi

SERVICE="$1"
TAG="$2"

echo "▶ Dispatching workflow for service=${SERVICE}, tag=${TAG}"

# ---- Dispatch workflow ----
curl -s -X POST \
  -H "Authorization: Bearer ${GH_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches" \
  -d "{\"ref\":\"${BRANCH}\",\"inputs\":{\"service\":\"${SERVICE}\",\"tag\":\"${TAG}\"}}"

echo "⏳ Waiting for workflow run to register..."
sleep 6

# ---- Get latest run id ----
RUN_ID=$(curl -s \
  -H "Authorization: Bearer ${GH_TOKEN}" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/runs?branch=${BRANCH}&per_page=1" \
  | jq -r '.workflow_runs[0].id')

if [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]]; then
  echo "❌ Could not find workflow run"
  exit 1
fi

RUN_URL="https://github.com/${OWNER}/${REPO}/actions/runs/${RUN_ID}"

echo "🔗 Workflow URL: ${RUN_URL}"
echo "🔎 Run ID: ${RUN_ID}"

# ---- Poll status ----
while true; do
  RESP=$(curl -s \
    -H "Authorization: Bearer ${GH_TOKEN}" \
    "https://api.github.com/repos/${OWNER}/${REPO}/actions/runs/${RUN_ID}")

  STATUS=$(echo "$RESP" | jq -r '.status')
  CONCLUSION=$(echo "$RESP" | jq -r '.conclusion')

  echo "⏱ Status: ${STATUS} | ${RUN_URL}"

  if [[ "$STATUS" == "completed" ]]; then
    echo "🏁 Conclusion: ${CONCLUSION}"
    echo "🔗 Final URL: ${RUN_URL}"
    [[ "$CONCLUSION" == "success" ]] && exit 0 || exit 1
  fi

  sleep 8
done