#!/usr/bin/env bash
# Reminder check for today's draft. Safe to run repeatedly (for example at 10:00 and 12:00): it sends nothing if the report is
# already approved, nothing before the threshold, and never sends the same level twice.
#   after 2 hours   -> reminder to the approver
#   after 4 hours   -> escalation (headline only) to the configured escalation contact
# Needs the SAME out/ folder (audit log and draft) as the morning run, so run it on the same machine.
# Settings: OUT_DIR, AS_OF_DATE, NOTIFY_CONFIG, NOTIFY_VIA (email|slack|both), SEND_EMAIL=1 to really send.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PYTHON:-python3}"
OUT="${OUT_DIR:-out}"
AS_OF="${AS_OF_DATE:-$(date +%F)}"
DRAFT="$OUT/status_${AS_OF}_DRAFT.md"
[[ -f "$DRAFT" ]] || { echo "no draft for $AS_OF in $OUT; nothing to remind about"; exit 0; }
SEND=(); [[ "${SEND_EMAIL:-0}" == "1" ]] && SEND=(--send)
"$PY" -m modules.m01_status_agent.notify remind --draft "$DRAFT" \
  --config "${NOTIFY_CONFIG:-config/stakeholders.json}" --via "${NOTIFY_VIA:-email}" --out "$OUT" ${SEND[@]+"${SEND[@]}"}
