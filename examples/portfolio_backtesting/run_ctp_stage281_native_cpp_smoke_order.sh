#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_ENV="${SCRIPT_DIR}/ctp_broker_test.local.env"
DEFAULT_SDK_DIR="/private/tmp/simnow_mac_cp_sdk/TraderapiMduserapi_6.7.7_CP_MacOS/TraderapiMduserapi_6.7.7_CP_MacOS测评版"
DEFAULT_DATA_COLLECT_TOOL="/private/tmp/stage279_data_collect_mac/DataCollectforMacOS"
BUILD_DIR="/private/tmp/stage281_native_cpp_smoke_order_build"
BIN="${BUILD_DIR}/stage281_native_cpp_smoke_order"

if [[ -f "${LOCAL_ENV}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${LOCAL_ENV}"
  set +a
fi

export CTP_MAC_CP_SDK_DIR="${CTP_MAC_CP_SDK_DIR:-${DEFAULT_SDK_DIR}}"
export CTP_DATA_COLLECT_TOOL="${CTP_DATA_COLLECT_TOOL:-${DEFAULT_DATA_COLLECT_TOOL}}"

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
  echo "Missing CTP native smoke env: ${missing_keys[*]}" >&2
  exit 2
fi

if [[ ! -f "${CTP_MAC_CP_SDK_DIR}/thosttraderapi_se.framework/Versions/A/thosttraderapi_se" ]]; then
  echo "Missing thosttraderapi_se.framework under CTP_MAC_CP_SDK_DIR=${CTP_MAC_CP_SDK_DIR}" >&2
  exit 2
fi

if [[ "${CTP_TD_ADDRESS}" != tcp://* ]]; then
  export CTP_TD_ADDRESS="tcp://${CTP_TD_ADDRESS}"
fi

if [[ "${CTP_USE_DATACOLLECT_TEXT_FALLBACK:-0}" == "1" && -z "${CTP_CLIENT_SYSTEM_INFO:-}" && -x "${CTP_DATA_COLLECT_TOOL}" ]]; then
  collect_output="$("${CTP_DATA_COLLECT_TOOL}")"
  collect_data="$(printf '%s\n' "${collect_output}" | perl -ne 'if (/CollectData\s*=\s*\[(.*)\]/) { print $1 }' | tail -1)"
  if [[ -n "${collect_data}" ]]; then
    export CTP_CLIENT_SYSTEM_INFO="${collect_data}"
    echo "CTP_CLIENT_SYSTEM_INFO=set(len=${#CTP_CLIENT_SYSTEM_INFO})"
  else
    echo "CTP_CLIENT_SYSTEM_INFO=missing_from_data_collect_output" >&2
  fi
fi

export CTP_NATIVE_SMOKE_MODE="${CTP_NATIVE_SMOKE_MODE:-dry-run}"
export CTP_NATIVE_SMOKE_INSTRUMENT="${CTP_NATIVE_SMOKE_INSTRUMENT:-MA609}"
export CTP_NATIVE_SMOKE_EXCHANGE="${CTP_NATIVE_SMOKE_EXCHANGE:-CZCE}"
export CTP_NATIVE_SMOKE_DIRECTION="${CTP_NATIVE_SMOKE_DIRECTION:-buy}"
export CTP_NATIVE_SMOKE_PRICE="${CTP_NATIVE_SMOKE_PRICE:-1.0}"
export CTP_NATIVE_SMOKE_VOLUME="${CTP_NATIVE_SMOKE_VOLUME:-1}"

mkdir -p "${BUILD_DIR}"

clang++ -std=c++17 \
  -I"${CTP_MAC_CP_SDK_DIR}/thosttraderapi_se.framework/Versions/A/Headers" \
  -I"${SCRIPT_DIR}" \
  -F"${CTP_MAC_CP_SDK_DIR}" \
  -framework thosttraderapi_se \
  "${SCRIPT_DIR}/run_ctp_stage281_native_cpp_smoke_order.cpp" \
  -o "${BIN}"

export DYLD_FRAMEWORK_PATH="${CTP_MAC_CP_SDK_DIR}${DYLD_FRAMEWORK_PATH:+:${DYLD_FRAMEWORK_PATH}}"
exec "${BIN}"
