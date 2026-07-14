#!/usr/bin/env bash
set -uo pipefail

PROJECT_DIR="${STAGE930_PROJECT_DIR:-/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting}"
REPO_ROOT="${STAGE930_REPO_ROOT:-/Users/bytedance/Desktop/person/vnpy}"
PYTHON_PATH="${STAGE930_PYTHON_PATH:-${REPO_ROOT}/.py311/bin/python}"
DAEMON_SCRIPT="${STAGE930_DAEMON_SCRIPT:-${PROJECT_DIR}/run_qmt_roll_stage930_official_live_c9_session_daemon.py}"
LOG_DIR="${STAGE930_LOG_DIR:-${PROJECT_DIR}/backtest_outputs}"
mkdir -p "${LOG_DIR}"

max_restarts="${STAGE930_SUPERVISOR_MAX_RESTARTS:-3}"
restart_delay="${STAGE930_SUPERVISOR_RESTART_DELAY_SECONDS:-15}"
duration_seconds=0
args=("$@")
termination_requested=0
termination_exit_code=0
active_pid=""
active_kind=""
active_exit_code=0

forward_signal() {
  local signal_name="$1"
  termination_requested=1
  if [[ "${signal_name}" == "INT" ]]; then
    termination_exit_code=130
  else
    termination_exit_code=143
  fi
  if [[ -n "${active_pid}" ]] && kill -0 "${active_pid}" 2>/dev/null; then
    echo "Stage930 supervisor forwarding ${signal_name} to ${active_kind:-child} pid=${active_pid}"
    kill -s "${signal_name}" "${active_pid}" 2>/dev/null || true
  fi
}

wait_for_active_child() {
  local pid="$1"
  while true; do
    wait "${pid}"
    active_exit_code=$?
    if ! kill -0 "${pid}" 2>/dev/null; then
      break
    fi
  done
}

exit_if_terminated() {
  if [[ "${termination_requested}" -eq 1 ]]; then
    echo "Stage930 supervisor termination requested; child reaped, no restart."
    exit "${termination_exit_code}"
  fi
}

trap 'forward_signal TERM' TERM
trap 'forward_signal INT' INT

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
  exit_if_terminated
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
  if [[ "${#args[@]}" -gt 0 ]]; then
    "${PYTHON_PATH}" "${DAEMON_SCRIPT}" "${args[@]}" &
  else
    "${PYTHON_PATH}" "${DAEMON_SCRIPT}" &
  fi
  active_pid=$!
  active_kind="daemon"
  if [[ "${termination_requested}" -eq 1 ]]; then
    kill -s TERM "${active_pid}" 2>/dev/null || true
  fi
  wait_for_active_child "${active_pid}"
  exit_code="${active_exit_code}"
  active_pid=""
  active_kind=""
  echo "Stage930 daemon exited at $(date '+%Y-%m-%d %H:%M:%S'), exit_code=${exit_code}"
  exit_if_terminated

  if [[ "${exit_code}" -eq 0 ]]; then
    exit 0
  fi
  restart_count=$((restart_count + 1))
  if [[ "${max_restarts}" =~ ^[0-9]+$ && "${max_restarts}" -gt 0 && "${restart_count}" -gt "${max_restarts}" ]]; then
    echo "Stage930 supervisor max restarts exceeded: ${max_restarts}"
    exit "${exit_code}"
  fi
  exit_if_terminated
  sleep "${restart_delay}" &
  active_pid=$!
  active_kind="restart_delay"
  if [[ "${termination_requested}" -eq 1 ]]; then
    kill -s TERM "${active_pid}" 2>/dev/null || true
  fi
  wait_for_active_child "${active_pid}"
  active_pid=""
  active_kind=""
  exit_if_terminated
done
