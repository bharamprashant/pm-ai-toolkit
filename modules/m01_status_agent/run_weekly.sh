#!/usr/bin/env bash
# Kept for older instructions. Same as run_scheduled.sh; the schedule (daily or weekly) is set in cron or CI.
exec "$(dirname "$0")/run_scheduled.sh" "$@"
