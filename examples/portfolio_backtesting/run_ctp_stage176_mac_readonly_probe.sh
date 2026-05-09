#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENV_PYTHON="${PROJECT_ROOT}/.py311/bin/python"
CTP_LIB_DIR="${PROJECT_ROOT}/.py311/lib/python3.11/site-packages/vnpy_ctp/api/libs"

export DYLD_FRAMEWORK_PATH="${CTP_LIB_DIR}${DYLD_FRAMEWORK_PATH:+:${DYLD_FRAMEWORK_PATH}}"

exec "${VENV_PYTHON}" "${SCRIPT_DIR}/run_ctp_stage174_readonly_probe.py" "$@"
