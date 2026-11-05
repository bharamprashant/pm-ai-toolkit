#!/usr/bin/env bash
# Scheduled run (daily or weekly, set by your cron/CI schedule):
#   pull data -> compute facts -> draft the report -> email the approver "draft ready for review".
# It NEVER approves a report and NEVER emails stakeholders. A named person approves, then runs `notify publish`.
#
# Settings (environment variables, set where the schedule runs, never in a file in the repo):
#   JIRA_JQL (+ JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN)   pull live from Jira, read-only
#   INPUT_CSV                                                 or use an existing CSV export instead
#   PROGRAM_NAME      title of the report (default "My Program")
#   USE_LIVE_MODEL=1  use the AI model (needs ANTHROPIC_API_KEY); default is the offline rules
#   SEND_EMAIL=1      really send the review request (needs SMTP_HOST, SMTP_FROM); default is a dry run
#   NOTIFY_CONFIG     path to the stakeholder config (default config/stakeholders.json)
#   OUT_DIR           output folder (default out)
#   AS_OF_DATE        report date, default today (use 2026-03-20 with the sample data)
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PYTHON:-python3}"
OUT="${OUT_DIR:-out}"
AS_OF="${AS_OF_DATE:-$(date +%F)}"   # AS_OF_DATE is for demos with the sample data

if [[ -n "${JIRA_JQL:-}" ]]; then
  "$PY" -m modules.m01_status_agent.run --jira-jql "$JIRA_JQL" --export "$OUT/jira.csv" --out "$OUT"
  INPUT="$OUT/jira.csv"
else
  INPUT="${INPUT_CSV:?set JIRA_JQL (live Jira) or INPUT_CSV (a CSV export)}"
fi

LIVE=(); [[ "${USE_LIVE_MODEL:-0}" == "1" ]] && LIVE=(--live)
"$PY" -m modules.m01_status_agent.run --input "$INPUT" --as-of "$AS_OF" \
  --program "${PROGRAM_NAME:-My Program}" --out "$OUT" ${LIVE[@]+"${LIVE[@]}"}

SEND=(); [[ "${SEND_EMAIL:-0}" == "1" ]] && SEND=(--send)
"$PY" -m modules.m01_status_agent.notify review-request \
  --draft "$OUT/status_${AS_OF}_DRAFT.md" --config "${NOTIFY_CONFIG:-config/stakeholders.json}" \
  --out "$OUT" ${SEND[@]+"${SEND[@]}"}

echo "Draft ready: $OUT/status_${AS_OF}_DRAFT.md"
echo "Next (a person): approve, then publish:"
echo "  $PY -m modules.m01_status_agent.run --approve $OUT/status_${AS_OF}_DRAFT.md --approver \"Your Name\""
echo "  $PY -m modules.m01_status_agent.notify publish --final $OUT/status_${AS_OF}_FINAL.md [--send]"
