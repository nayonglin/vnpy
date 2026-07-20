#!/usr/bin/env bash
set -uo pipefail

PROJECT_DIR="${STAGE930_PROJECT_DIR:-/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting}"
REPO_ROOT="${STAGE930_REPO_ROOT:-/Users/bytedance/Desktop/person/vnpy}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="${STAGE930_PYTHON_PATH:-${REPO_ROOT}/.py311/bin/python}"
DAEMON_SCRIPT="${STAGE930_DAEMON_SCRIPT:-${PROJECT_DIR}/run_qmt_roll_stage930_official_live_c9_session_daemon.py}"
CHILD_HELPER="${STAGE930_SUPERVISOR_CHILD_HELPER:-${SCRIPT_DIR}/run_qmt_roll_stage930_supervisor_child.py}"
LOG_DIR="${STAGE930_LOG_DIR:-${PROJECT_DIR}/backtest_outputs}"
mkdir -p "${LOG_DIR}"

max_restarts="${STAGE930_SUPERVISOR_MAX_RESTARTS:-3}"
restart_delay="${STAGE930_SUPERVISOR_RESTART_DELAY_SECONDS:-15}"
term_timeout="${STAGE930_SUPERVISOR_TERM_TIMEOUT_SECONDS:-5}"
kill_wait="${STAGE930_SUPERVISOR_KILL_WAIT_SECONDS:-5}"
pgid_handshake_attempts="${STAGE930_SUPERVISOR_PGID_HANDSHAKE_ATTEMPTS:-100}"
duration_seconds=0
args=("$@")
termination_requested=0
termination_exit_code=0
active_pid=""
active_pgid=""
active_exit_code=0

group_alive() {
  local pgid="$1"
  kill -0 -- "-${pgid}" 2>/dev/null
}

wait_for_group_exit() {
  local pgid="$1"
  local timeout="$2"
  local deadline
  deadline="$(${PYTHON_PATH} -S -c 'import sys,time; print(time.monotonic() + float(sys.argv[1]))' "${timeout}")"
  while group_alive "${pgid}"; do
    if "${PYTHON_PATH}" -S -c 'import sys,time; raise SystemExit(0 if time.monotonic() >= float(sys.argv[1]) else 1)' "${deadline}"; then
      return 1
    fi
    sleep 0.05
  done
  return 0
}

terminate_active_group() {
  local signal_name="$1"
  if [[ -z "${active_pid}" || -z "${active_pgid}" ]]; then
    return 0
  fi
  if [[ ! "${active_pid}" =~ ^[0-9]+$ || ! "${active_pgid}" =~ ^[0-9]+$ || "${active_pid}" != "${active_pgid}" ]]; then
    echo "Stage930 supervisor refusing unknown PGID identity pid=${active_pid} pgid=${active_pgid:-missing}"
    kill -s KILL "${active_pid}" 2>/dev/null || true
    return 2
  fi
  if ! group_alive "${active_pgid}"; then
    return 0
  fi
  echo "Stage930 supervisor forwarding ${signal_name} to PGID=${active_pgid}"
  kill -s "${signal_name}" -- "-${active_pgid}" 2>/dev/null || true
  if wait_for_group_exit "${active_pgid}" "${term_timeout}"; then
    return 0
  fi
  echo "Stage930 supervisor escalating PGID=${active_pgid} to KILL"
  kill -s KILL -- "-${active_pgid}" 2>/dev/null || true
  if ! wait_for_group_exit "${active_pgid}" "${kill_wait}"; then
    echo "Stage930 supervisor PGID=${active_pgid} survived KILL wait"
    return 2
  fi
}

forward_signal() {
  local signal_name="$1"
  termination_requested=1
  if [[ "${signal_name}" == "INT" ]]; then
    termination_exit_code=130
  else
    termination_exit_code=143
  fi
  terminate_active_group "${signal_name}" || true
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

interruptible_restart_delay() {
  local deadline
  deadline="$(${PYTHON_PATH} -S -c 'import sys,time; print(time.monotonic() + float(sys.argv[1]))' "${restart_delay}")"
  while true; do
    exit_if_terminated
    if "${PYTHON_PATH}" -S -c 'import sys,time; raise SystemExit(0 if time.monotonic() >= float(sys.argv[1]) else 1)' "${deadline}"; then
      return 0
    fi
    sleep 0.05
  done
}

trap 'forward_signal TERM' TERM
trap 'forward_signal INT' INT

if [[ ! "${pgid_handshake_attempts}" =~ ^[0-9]+$ || "${pgid_handshake_attempts}" -le 0 ]]; then
  echo "Stage930 supervisor invalid PGID handshake attempts: ${pgid_handshake_attempts}"
  exit 2
fi

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
    "${PYTHON_PATH}" -S "${CHILD_HELPER}" "${PYTHON_PATH}" "${DAEMON_SCRIPT}" "${args[@]}" &
  else
    "${PYTHON_PATH}" -S "${CHILD_HELPER}" "${PYTHON_PATH}" "${DAEMON_SCRIPT}" &
  fi
  active_pid=$!
  active_pgid=""
  for ((attempt = 0; attempt < pgid_handshake_attempts; attempt++)); do
    candidate_pgid="$(ps -o pgid= -p "${active_pid}" 2>/dev/null | tr -d '[:space:]')"
    if [[ "${candidate_pgid}" == "${active_pid}" ]]; then
      active_pgid="${candidate_pgid}"
      break
    fi
    if ! kill -0 "${active_pid}" 2>/dev/null; then
      break
    fi
    sleep 0.05
  done
  if [[ "${active_pgid}" != "${active_pid}" ]]; then
    echo "Stage930 supervisor child failed PGID handshake pid=${active_pid} pgid=${active_pgid:-missing}"
    kill -s KILL "${active_pid}" 2>/dev/null || true
    wait "${active_pid}" 2>/dev/null || true
    active_pid=""
    active_pgid=""
    exit 2
  fi
  if [[ "${termination_requested}" -eq 1 ]]; then
    terminate_active_group TERM || true
  fi
  wait_for_active_child "${active_pid}"
  exit_code="${active_exit_code}"
  active_pid=""
  active_pgid=""
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
  interruptible_restart_delay
done
