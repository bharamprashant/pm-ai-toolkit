#!/usr/bin/env bash
# Local weekly run. Credentials must already be exported in the environment (see SETUP.md section 4).
set -euo pipefail
cd "$(dirname "$0")/../.."
python -m modules.m01_status_agent.run --jira-jql "${JIRA_JQL:?set JIRA_JQL}" --export out/jira.csv
python -m modules.m01_status_agent.run --input out/jira.csv --as-of "$(date +%F)" --program "${PROGRAM_NAME:-My Program}"
echo "Draft created. Review it, then run with --approve and your name."
