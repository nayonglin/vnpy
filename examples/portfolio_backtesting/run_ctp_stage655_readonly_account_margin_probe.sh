#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_PYTHON="${PROJECT_ROOT}/.py311/bin/python"
CTP_FRAMEWORK_DIR="${PROJECT_ROOT}/.py311/lib"
CTP_LIB_DIR="${PROJECT_ROOT}/.py311/lib/python3.11/site-packages/vnpy_ctp/api/libs"
LOCAL_ENV="${SCRIPT_DIR}/ctp_broker_test.local.env"

if [[ -f "${LOCAL_ENV}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${LOCAL_ENV}"
  set +a
fi

required_keys=(
  CTP_USERID
  CTP_PASSWORD
  CTP_BROKERID
  CTP_TD_ADDRESS
  CTP_APPID
  CTP_AUTH_CODE
)

missing_keys=()
for key in "${required_keys[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    missing_keys+=("${key}")
  fi
done

if (( ${#missing_keys[@]} > 0 )); then
  echo "Missing CTP broker test env: ${missing_keys[*]}" >&2
  echo "Copy ctp_broker_test.example.env to ctp_broker_test.local.env and fill it locally." >&2
  exit 2
fi

if [[ "${CTP_TD_ADDRESS}" != tcp://* ]]; then
  export CTP_TD_ADDRESS="tcp://${CTP_TD_ADDRESS}"
fi

export CTP_PRODUCT_INFO="${CTP_PRODUCT_INFO:-}"
export DYLD_FRAMEWORK_PATH="${CTP_FRAMEWORK_DIR}:${CTP_LIB_DIR}${DYLD_FRAMEWORK_PATH:+:${DYLD_FRAMEWORK_PATH}}"

exec "${VENV_PYTHON}" "${SCRIPT_DIR}/run_ctp_stage655_readonly_account_margin_probe.py" "$@"
