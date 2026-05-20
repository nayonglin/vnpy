#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_ENV="${SCRIPT_DIR}/ctp_broker_test.local.env"
VENV_PYTHON="${SCRIPT_DIR}/../../.py311/bin/python"
DEFAULT_SDK_DIR="/private/tmp/simnow_mac_cp_sdk/TraderapiMduserapi_6.7.7_CP_MacOS/TraderapiMduserapi_6.7.7_CP_MacOS测评版"

if [[ -f "${LOCAL_ENV}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${LOCAL_ENV}"
  set +a
fi

export CTP_MAC_CP_SDK_DIR="${CTP_MAC_CP_SDK_DIR:-${DEFAULT_SDK_DIR}}"

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
  echo "Missing CTP TD-only env: ${missing_keys[*]}" >&2
  exit 2
fi

if [[ ! -f "${CTP_MAC_CP_SDK_DIR}/thosttraderapi_se.framework/Versions/A/thosttraderapi_se" ]]; then
  echo "Missing thosttraderapi_se.framework under CTP_MAC_CP_SDK_DIR=${CTP_MAC_CP_SDK_DIR}" >&2
  exit 2
fi

if [[ "${CTP_TD_ADDRESS}" != tcp://* ]]; then
  export CTP_TD_ADDRESS="tcp://${CTP_TD_ADDRESS}"
fi

export CTP_PRODUCT_INFO="${CTP_PRODUCT_INFO:-}"
export DYLD_FRAMEWORK_PATH="${CTP_MAC_CP_SDK_DIR}${DYLD_FRAMEWORK_PATH:+:${DYLD_FRAMEWORK_PATH}}"

exec "${VENV_PYTHON}" "${SCRIPT_DIR}/run_ctp_stage273_cp_mac_td_only_probe.py"
