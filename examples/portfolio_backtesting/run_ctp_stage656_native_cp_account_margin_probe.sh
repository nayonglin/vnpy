#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_PYTHON="${PROJECT_ROOT}/.py311/bin/python"
OUTPUT_DIR="${SCRIPT_DIR}/backtest_outputs"
MODEL_TAG="stage656_native_cp_account_margin_probe_v1"
OUTPUT_PREFIX="qmt_roll_stage656_native_cp_account_margin_probe"
RAW_LOG="${OUTPUT_DIR}/${OUTPUT_PREFIX}_raw_${MODEL_TAG}.log"
DEFAULT_CP_SDK_DIR="${PROJECT_ROOT}/.py311/lib"
DEFAULT_COLLECTOR_DYLIB="/Users/bytedance/Downloads/sfit_tst_1.0_20250325_7643_MacOS/Mac_tst_1.0/信息采集模块/MacDataCollect.framework/MacDataCollect"

mkdir -p "${OUTPUT_DIR}"

export CTP_MAC_CP_SDK_DIR="${CTP_MAC_CP_SDK_DIR:-${DEFAULT_CP_SDK_DIR}}"
export CTP_SYSTEM_INFO_SOURCE="${CTP_SYSTEM_INFO_SOURCE:-collector_api}"
export CTP_SYSTEM_INFO_DYLIB="${CTP_SYSTEM_INFO_DYLIB:-${DEFAULT_COLLECTOR_DYLIB}}"
export CTP_NATIVE_REQUIRE_SYSTEM_INFO="${CTP_NATIVE_REQUIRE_SYSTEM_INFO:-1}"
export CTP_NATIVE_TD_WAIT_SECONDS="${CTP_NATIVE_TD_WAIT_SECONDS:-35}"

if [[ ! -f "${CTP_SYSTEM_INFO_DYLIB}" ]]; then
  echo "Missing CTP_SYSTEM_INFO_DYLIB=${CTP_SYSTEM_INFO_DYLIB}" >&2
  exit 2
fi

set +e
"${SCRIPT_DIR}/run_ctp_stage278_native_cpp_td_login_probe.sh" 2>&1 | tee "${RAW_LOG}"
native_code=${PIPESTATUS[0]}
set -e

"${VENV_PYTHON}" "${SCRIPT_DIR}/parse_ctp_stage656_native_cp_account_margin_probe.py" \
  --raw-log "${RAW_LOG}" \
  --native-exit-code "${native_code}"
