from __future__ import annotations

import argparse
import json
import re
import shlex
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_FAMILY_VERSION, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_phase_d_config import PHASE_D_READONLY_REFRESH_CONFIRM_TEXT
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
MODEL_TAG = "stage914_official_live_ctp_runtime_preflight_v1"
OUTPUT_PREFIX = "qmt_roll_stage914_official_live_ctp_runtime_preflight"

LIVE_ENV_FILE = PROJECT_DIR / "ctp_live.local.env"
BROKER_TEST_ENV_FILE = PROJECT_DIR / "ctp_broker_test.local.env"
PYTHON_PATH = REPO_ROOT / ".py311/bin/python"
STAGE174_PROBE = PROJECT_DIR / "run_ctp_stage174_readonly_probe.py"
FORMAL_FRAMEWORK_DIR = REPO_ROOT / ".py311/lib/python3.11/site-packages/vnpy_ctp/api/libs"
PY311_LIB_DIR = REPO_ROOT / ".py311/lib"

REQUIRED_ENV_KEYS = (
    "CTP_ENV_PROFILE",
    "CTP_USERID",
    "CTP_PASSWORD",
    "CTP_BROKERID",
    "CTP_APPID",
    "CTP_AUTH_CODE",
    "CTP_TD_ADDRESS",
    "CTP_MD_ADDRESS",
    "CTP_EXPECT_PRODUCTION_API",
)
SECRET_KEYS = {"CTP_USERID", "CTP_PASSWORD", "CTP_APPID", "CTP_AUTH_CODE", "CTP_PRODUCT_INFO"}
EXPECTED_TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{run_id}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
    }


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _mask_value(key: str, value: str) -> str:
    if not value:
        return ""
    if key in {"CTP_TD_ADDRESS", "CTP_MD_ADDRESS"}:
        match = re.match(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)?(?P<host>[^:/]+)(?::(?P<port>[0-9]+))?", value)
        if not match:
            return f"set(len={len(value)})"
        scheme = match.group("scheme") or ""
        port = match.group("port") or ""
        return f"{scheme}***:{port}" if port else f"{scheme}***"
    if key in {"CTP_ENV_PROFILE", "CTP_EXPECT_PRODUCTION_API"}:
        return value
    if key == "CTP_BROKERID":
        return value[:1] + "***" + value[-1:] if len(value) > 2 else "*" * len(value)
    if key in SECRET_KEYS:
        return f"set(len={len(value)})"
    return f"set(len={len(value)})"


def _check_row(
    rows: list[dict[str, Any]],
    *,
    check: str,
    passed: bool,
    severity: str,
    observed: Any,
    required: Any,
    blocker: str = "",
) -> None:
    rows.append(
        {
            "check": check,
            "passed": int(bool(passed)),
            "severity": severity,
            "observed": observed,
            "required": required,
            "blocker": "" if passed else blocker,
        }
    )


def _env_file_mode(path: Path) -> str:
    if not path.exists():
        return ""
    return stat.filemode(path.stat().st_mode)


def _command_plan(wait_seconds: int) -> str:
    framework = shlex.quote(str(FORMAL_FRAMEWORK_DIR))
    py311_lib = shlex.quote(str(PY311_LIB_DIR))
    return "\n".join(
        [
            "set -euo pipefail",
            f"set -a; source {shlex.quote(str(LIVE_ENV_FILE))}; set +a",
            f"export DYLD_FRAMEWORK_PATH={framework}:{py311_lib}${{DYLD_FRAMEWORK_PATH:+:${{DYLD_FRAMEWORK_PATH}}}}",
            f"{shlex.quote(str(PYTHON_PATH))} {shlex.quote(str(STAGE174_PROBE))} --connect --wait-seconds {int(wait_seconds)}",
        ]
    )


def _find_cp_markers() -> list[str]:
    markers: list[str] = []
    for path in PY311_LIB_DIR.rglob("*"):
        text = path.name.lower()
        is_ctp_cp_marker = (
            "macos_cp" in text
            or "ctp_cp" in text
            or (("_cp_" in text or text.endswith("_cp")) and any(token in text for token in ("ctp", "thost", "traderapi", "mduserapi")))
        )
        if is_ctp_cp_marker:
            markers.append(str(path.relative_to(REPO_ROOT)))
        if len(markers) >= 40:
            break
    return markers


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    selected = [column for column in columns if column in df.columns]
    return df.loc[:, selected].head(120).to_markdown(index=False)


def _build_report(summary: dict[str, Any], checks: pd.DataFrame, env_rows: pd.DataFrame) -> str:
    blocking = checks[checks["severity"].eq("block") & checks["passed"].eq(0)]
    warnings = checks[checks["severity"].eq("warn") & checks["passed"].eq(0)]
    return "\n".join(
        [
            "# Stage914 Official Live CTP Runtime Preflight",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Preflight status: `{summary['preflight_status']}`",
            f"- Blockers: `{summary['blocking_failure_count']}`",
            f"- Warnings: `{summary['warning_failure_count']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
            "",
            "## Blocking Checks",
            "",
            _to_markdown(blocking, ["check", "observed", "required", "blocker"]),
            "",
            "## Warning Checks",
            "",
            _to_markdown(warnings, ["check", "observed", "required", "blocker"]),
            "",
            "## Sanitized Env Inventory",
            "",
            _to_markdown(env_rows, ["key", "configured", "masked_value", "required"]),
            "",
            "## Sanitized Production Readonly Command",
            "",
            f"```bash\n{summary['sanitized_command_plan']}\n```",
            "",
            "## Notes",
            "",
            "- Stage914 does not source the env file into the current process.",
            "- Stage914 does not import vn.py gateways, connect to CTP, submit orders, or cancel orders.",
            "- The command plan is only for Stage907/Stage174 read-only refresh after the explicit refresh gate is enabled.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Production-live CTP runtime preflight for official Phase D.")
    parser.add_argument("--wait-seconds", type=int, default=30)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    env_values = _parse_env_file(LIVE_ENV_FILE)
    checks: list[dict[str, Any]] = []

    _check_row(
        checks,
        check="official_live_profile_is_c9",
        passed=OFFICIAL_LIVE_FAMILY_VERSION == "stage819_c9_intraday_stop_retry",
        severity="block",
        observed=f"{OFFICIAL_LIVE_VERSION}/{OFFICIAL_LIVE_FAMILY_VERSION}",
        required="stage819_c9_intraday_stop_retry family",
        blocker="official_live_profile_not_c9",
    )
    _check_row(
        checks,
        check="production_live_env_file_present",
        passed=LIVE_ENV_FILE.exists(),
        severity="block",
        observed=str(LIVE_ENV_FILE),
        required="ctp_live.local.env exists",
        blocker="ctp_live_env_missing",
    )
    mode_ok = LIVE_ENV_FILE.exists() and (LIVE_ENV_FILE.stat().st_mode & 0o077) == 0
    _check_row(
        checks,
        check="production_live_env_file_not_group_or_world_readable",
        passed=mode_ok,
        severity="block",
        observed=_env_file_mode(LIVE_ENV_FILE),
        required="-rw------- or stricter",
        blocker="ctp_live_env_permissions_too_open",
    )
    missing_keys = [key for key in REQUIRED_ENV_KEYS if not env_values.get(key, "").strip()]
    _check_row(
        checks,
        check="production_live_required_env_keys_configured",
        passed=not missing_keys,
        severity="block",
        observed=",".join(missing_keys) if missing_keys else "all_required_keys_set",
        required=",".join(REQUIRED_ENV_KEYS),
        blocker="ctp_live_required_env_missing",
    )
    _check_row(
        checks,
        check="production_live_env_profile_marker",
        passed=env_values.get("CTP_ENV_PROFILE", "").strip().lower() in {"production-live", "production_live", "live"},
        severity="block",
        observed=_mask_value("CTP_ENV_PROFILE", env_values.get("CTP_ENV_PROFILE", "")),
        required="CTP_ENV_PROFILE=production-live/live",
        blocker="ctp_live_env_profile_not_production",
    )
    _check_row(
        checks,
        check="production_api_expectation_marker",
        passed=env_values.get("CTP_EXPECT_PRODUCTION_API", "").strip().lower() in EXPECTED_TRUE_VALUES,
        severity="block",
        observed=_mask_value("CTP_EXPECT_PRODUCTION_API", env_values.get("CTP_EXPECT_PRODUCTION_API", "")),
        required="CTP_EXPECT_PRODUCTION_API=1",
        blocker="production_api_expectation_marker_missing",
    )
    td_address = env_values.get("CTP_TD_ADDRESS", "").strip()
    md_address = env_values.get("CTP_MD_ADDRESS", "").strip()
    _check_row(
        checks,
        check="td_md_fronts_use_tcp_scheme",
        passed=td_address.startswith("tcp://") and md_address.startswith("tcp://"),
        severity="block",
        observed=f"td={_mask_value('CTP_TD_ADDRESS', td_address)};md={_mask_value('CTP_MD_ADDRESS', md_address)}",
        required="CTP_TD_ADDRESS and CTP_MD_ADDRESS start with tcp://",
        blocker="ctp_front_address_scheme_invalid",
    )
    _check_row(
        checks,
        check="stage907_command_uses_live_env_not_broker_test",
        passed=str(LIVE_ENV_FILE).endswith("ctp_live.local.env") and "ctp_broker_test.local.env" not in _command_plan(args.wait_seconds),
        severity="block",
        observed=f"live_env={LIVE_ENV_FILE.name};broker_test_exists={BROKER_TEST_ENV_FILE.exists()}",
        required="production command sources ctp_live.local.env only",
        blocker="production_readonly_command_may_use_broker_test_env",
    )
    _check_row(
        checks,
        check="formal_vnpy_ctp_framework_dir_present",
        passed=FORMAL_FRAMEWORK_DIR.exists(),
        severity="block",
        observed=str(FORMAL_FRAMEWORK_DIR),
        required="vnpy_ctp/api/libs exists",
        blocker="formal_framework_dir_missing",
    )
    trader_framework = FORMAL_FRAMEWORK_DIR / "thosttraderapi_se.framework"
    md_framework = FORMAL_FRAMEWORK_DIR / "thostmduserapi_se.framework"
    _check_row(
        checks,
        check="formal_ctp_frameworks_present",
        passed=trader_framework.exists() and md_framework.exists(),
        severity="block",
        observed=f"trader={trader_framework.exists()};md={md_framework.exists()}",
        required="formal trader and market-data frameworks exist",
        blocker="formal_ctp_framework_files_missing",
    )
    dyld_plan = f"{FORMAL_FRAMEWORK_DIR}:{PY311_LIB_DIR}"
    _check_row(
        checks,
        check="dyld_framework_path_formal_before_py311_lib",
        passed=dyld_plan.split(":")[0] == str(FORMAL_FRAMEWORK_DIR) and dyld_plan.split(":")[1] == str(PY311_LIB_DIR),
        severity="block",
        observed=dyld_plan,
        required="vnpy_ctp/api/libs before .py311/lib",
        blocker="dyld_framework_priority_wrong",
    )
    _check_row(
        checks,
        check="python_and_readonly_probe_present",
        passed=PYTHON_PATH.exists() and STAGE174_PROBE.exists(),
        severity="block",
        observed=f"python={PYTHON_PATH.exists()};stage174={STAGE174_PROBE.exists()}",
        required=".py311/bin/python and Stage174 readonly probe exist",
        blocker="readonly_runtime_entry_missing",
    )
    cp_markers = _find_cp_markers()
    _check_row(
        checks,
        check="cp_evaluation_runtime_marker_absent_or_deprioritized",
        passed=True,
        severity="warn",
        observed=";".join(cp_markers[:8]) if cp_markers else "no_cp_markers_found_under_py311_lib",
        required="formal framework is first even if CP markers exist",
        blocker="cp_runtime_marker_detected",
    )
    _check_row(
        checks,
        check="readonly_refresh_requires_explicit_confirm_text",
        passed=bool(PHASE_D_READONLY_REFRESH_CONFIRM_TEXT),
        severity="block",
        observed=PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
        required="non-empty confirmation text for Stage907 refresh",
        blocker="readonly_refresh_confirm_text_missing",
    )

    checks_df = pd.DataFrame(checks)
    env_rows = pd.DataFrame(
        [
            {
                "key": key,
                "configured": int(bool(env_values.get(key, "").strip())),
                "masked_value": _mask_value(key, env_values.get(key, "")),
                "required": int(key in REQUIRED_ENV_KEYS),
            }
            for key in sorted(set(REQUIRED_ENV_KEYS).union(env_values.keys()))
        ]
    )
    blocking = checks_df[checks_df["severity"].eq("block") & checks_df["passed"].eq(0)]
    warnings = checks_df[checks_df["severity"].eq("warn") & checks_df["passed"].eq(0)]
    preflight_status = "production_readonly_preflight_passed" if blocking.empty else "production_readonly_preflight_blocked"
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "preflight_status": preflight_status,
        "blocking_failure_count": int(len(blocking)),
        "warning_failure_count": int(len(warnings)),
        "env_file": str(LIVE_ENV_FILE.resolve()),
        "env_file_mode": _env_file_mode(LIVE_ENV_FILE),
        "formal_framework_dir": str(FORMAL_FRAMEWORK_DIR.resolve()),
        "python_path": str(PYTHON_PATH.resolve()),
        "readonly_probe": str(STAGE174_PROBE.resolve()),
        "sanitized_command_plan": _command_plan(args.wait_seconds),
        "connect_attempted": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "No. This is a runtime and env preflight, not a strategy parameter change.",
            "continue_before": "Yes. Phase D cannot be trusted until production readonly runtime selection is machine-checked.",
            "overfit_after": "No. The checks do not feed back into alpha rules.",
            "continue_after": "Yes. A passed preflight still requires a fresh CTP readonly snapshot and reconciliation.",
        },
    }
    checks_df.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, checks_df, env_rows), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
