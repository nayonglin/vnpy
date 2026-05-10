#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_ENV="${SCRIPT_DIR}/ctp_simnow.local.env"

if [[ -f "${LOCAL_ENV}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${LOCAL_ENV}"
  set +a
fi

SIMNOW_FRONT="${SIMNOW_FRONT:-7x24}"

export CTP_BROKERID="${CTP_BROKERID:-9999}"
export CTP_APPID="${CTP_APPID:-simnow_client_test}"
export CTP_AUTH_CODE="${CTP_AUTH_CODE:-0000000000000000}"
export CTP_PRODUCT_INFO="${CTP_PRODUCT_INFO:-}"

case "${SIMNOW_FRONT}" in
  7x24)
    export CTP_TD_ADDRESS="${CTP_TD_ADDRESS:-tcp://182.254.243.31:40001}"
    export CTP_MD_ADDRESS="${CTP_MD_ADDRESS:-tcp://182.254.243.31:40011}"
    ;;
  trading)
    export CTP_TD_ADDRESS="${CTP_TD_ADDRESS:-tcp://182.254.243.31:30001}"
    export CTP_MD_ADDRESS="${CTP_MD_ADDRESS:-tcp://182.254.243.31:30011}"
    ;;
  trading2)
    export CTP_TD_ADDRESS="${CTP_TD_ADDRESS:-tcp://182.254.243.31:30002}"
    export CTP_MD_ADDRESS="${CTP_MD_ADDRESS:-tcp://182.254.243.31:30012}"
    ;;
  trading_mobile)
    export CTP_TD_ADDRESS="${CTP_TD_ADDRESS:-tcp://182.254.243.31:30003}"
    export CTP_MD_ADDRESS="${CTP_MD_ADDRESS:-tcp://182.254.243.31:30013}"
    ;;
  *)
    echo "Unknown SIMNOW_FRONT=${SIMNOW_FRONT}. Use 7x24, trading, trading2, or trading_mobile." >&2
    exit 2
    ;;
esac

exec "${SCRIPT_DIR}/run_ctp_stage176_mac_readonly_probe.sh" "$@"
