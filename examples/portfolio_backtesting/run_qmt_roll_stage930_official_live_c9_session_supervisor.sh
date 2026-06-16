#!/usr/bin/env bash
set -uo pipefail

PROJECT_DIR="/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting"
REPO_ROOT="/Users/bytedance/Desktop/person/vnpy"
PYTHON_PATH="${REPO_ROOT}/.py311/bin/python"
DAEMON_SCRIPT="${PROJECT_DIR}/run_qmt_roll_stage930_official_live_c9_session_daemon.py"
LOG_DIR="${PROJECT_DIR}/backtest_outputs"
mkdir -p "${LOG_DIR}"

max_restarts="${STAGE930_SUPERVISOR_MAX_RESTARTS:-3}"
restart_delay="${STAGE930_SUPERVISOR_RESTART_DELAY_SECONDS:-15}"
duration_seconds=0
args=("$@")

for ((idx = 0; idx < ${#args[@]}; idx++)); do
  if [[ "${args[$idx]}" == "--duration-seconds" && $((idx + 1)) -lt ${#args[@]} ]]; then
    duration_seconds="${args[$((idx + 1))]}"
    duration_index=$((idx + 1))
  fi
done

started_epoch="$(date +%s)"
deadline_epoch=0
if [[ "${duration_seconds}" =~ ^[0-9]+$ && "${duration_seconds}" -gt 0 ]]; then
  deadline_epoch=$((started_epoch + duration_seconds))
fi

restart_count=0
while true; do
  if [[ "${deadline_epoch}" -gt 0 ]]; then
    now_epoch="$(date +%s)"
    remaining=$((deadline_epoch - now_epoch))
    if [[ "${remaining}" -le 0 ]]; then
      echo "Stage930 supervisor deadline reached; exiting."
      exit 0
    fi
    if [[ -n "${duration_index:-}" ]]; then
      args[$duration_index]="${remaining}"
    fi
  fi

  echo "Stage930 supervisor starting daemon at $(date '+%Y-%m-%d %H:%M:%S'), restart_count=${restart_count}"
  "${PYTHON_PATH}" "${DAEMON_SCRIPT}" "${args[@]}"
  exit_code=$?
  echo "Stage930 daemon exited at $(date '+%Y-%m-%d %H:%M:%S'), exit_code=${exit_code}"

  if [[ "${exit_code}" -eq 0 ]]; then
    exit 0
  fi
  restart_count=$((restart_count + 1))
  if [[ "${max_restarts}" =~ ^[0-9]+$ && "${max_restarts}" -gt 0 && "${restart_count}" -gt "${max_restarts}" ]]; then
    echo "Stage930 supervisor max restarts exceeded: ${max_restarts}"
    exit "${exit_code}"
  fi
  sleep "${restart_delay}"
done
