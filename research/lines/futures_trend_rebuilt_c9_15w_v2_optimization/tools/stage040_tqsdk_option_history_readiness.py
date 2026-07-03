from __future__ import annotations

from datetime import date, datetime
from contextlib import redirect_stderr, redirect_stdout
import importlib
import importlib.metadata
from io import StringIO
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage040"
MODEL_TAG = "stage040_tqsdk_option_history_readiness_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage040_tqsdk_option_history_readiness"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage040_tqsdk_option_history_readiness"
STAGES_DIR = LINE_DIR / "stages"

MODULE_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_audit_{MODEL_TAG}.csv"
CREDENTIAL_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_credential_audit_{MODEL_TAG}.csv"
PROBE_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_plan_{MODEL_TAG}.csv"
PERMISSION_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_permission_probe_{MODEL_TAG}.csv"
READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
DATA_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

ENABLE_NETWORK_PROBE = os.getenv("STAGE040_ENABLE_NETWORK_PROBE", "0").strip() == "1"
NETWORK_PROBE_SYMBOL = os.getenv("STAGE040_NETWORK_PROBE_SYMBOL", "CZCE.SR901").strip()
NETWORK_PROBE_START = os.getenv("STAGE040_NETWORK_PROBE_START", "2018-01-02").strip()
NETWORK_PROBE_END = os.getenv("STAGE040_NETWORK_PROBE_END", "2018-01-03").strip()
NETWORK_PROBE_DUR_SEC = int(os.getenv("STAGE040_NETWORK_PROBE_DUR_SEC", "86400"))

TQSDK_ENV_FILE_CANDIDATES = (
    PROJECT_DIR / "tqsdk.local.env",
    PROJECT_DIR / "official_live_tqsdk.local.env",
    PROJECT_DIR / "ctp_live.local.env",
    PROJECT_DIR / ".env",
)

TQSDK_CREDENTIAL_KEYS = (
    "TQSDK_ACCOUNT",
    "TQSDK_PASSWORD",
    "TQSDK_USER",
    "TQSDK_PASS",
    "TQ_USERNAME",
    "TQ_PASSWORD",
    "TQ_USER",
    "TQAUTH_USER",
    "TQAUTH_PASSWORD",
)

TQSDK_CREDENTIAL_PAIRS = (
    ("TQSDK_ACCOUNT", "TQSDK_PASSWORD"),
    ("TQSDK_USER", "TQSDK_PASS"),
    ("TQ_USERNAME", "TQ_PASSWORD"),
    ("TQ_USER", "TQ_PASSWORD"),
    ("TQAUTH_USER", "TQAUTH_PASSWORD"),
)

TARGET_OPTION_PRODUCTS = (
    "SA.CZCE",
    "si.GFEX",
    "FG.CZCE",
    "MA.CZCE",
    "OI.CZCE",
    "jm.DCE",
    "AP.CZCE",
    "rb.SHFE",
    "fu.SHFE",
    "SM.CZCE",
    "ru.SHFE",
    "SH.CZCE",
    "lh.DCE",
    "jd.DCE",
)

SOURCE_LINKS = {
    "tqsdk_intro": "https://doc.shinnytech.com/tqsdk/latest/intro.html",
    "tqsdk_professional": "https://doc.shinnytech.com/tqsdk/latest/profession.html",
    "tqsdk_data_downloader": "https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html",
    "tqsdk_github": "https://github.com/shinnytech/tqsdk-python",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        if np.isnan(result) or np.isinf(result):
            return None
        return result
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _read_env_file_keys(path: Path) -> dict[str, bool]:
    if not path.exists() or not path.is_file():
        return {}
    found: dict[str, bool] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, raw_value = stripped.split("=", 1)
            key = key.strip()
            value = raw_value.strip().strip("'\"")
            if key in TQSDK_CREDENTIAL_KEYS:
                found[key] = bool(value)
    except OSError:
        return {}
    return found


def detect_tqsdk_credentials(
    env: dict[str, str] | None = None,
    env_file_paths: list[Path] | tuple[Path, ...] | None = None,
) -> pd.DataFrame:
    """Audit credential presence without exposing any credential value."""
    source_env = dict(os.environ if env is None else env)
    paths = TQSDK_ENV_FILE_CANDIDATES if env_file_paths is None else tuple(env_file_paths)
    rows: list[dict[str, Any]] = []

    for key in TQSDK_CREDENTIAL_KEYS:
        present = bool(str(source_env.get(key, "")).strip())
        rows.append(
            {
                "credential_key": key,
                "source_type": "environment",
                "source_path": "",
                "source_exists": True,
                "present": present,
                "redacted_value": "<present>" if present else "",
            }
        )

    for path in paths:
        file_keys = _read_env_file_keys(Path(path))
        for key in TQSDK_CREDENTIAL_KEYS:
            present = bool(file_keys.get(key, False))
            rows.append(
                {
                    "credential_key": key,
                    "source_type": "env_file",
                    "source_path": str(path),
                    "source_exists": Path(path).exists(),
                    "present": present,
                    "redacted_value": "<present>" if present else "",
                }
            )
    return pd.DataFrame(rows)


def credential_pair_available(credential_audit: pd.DataFrame) -> bool:
    if credential_audit.empty:
        return False
    present_keys = set(credential_audit.loc[credential_audit["present"].astype(bool), "credential_key"].astype(str))
    return any(user_key in present_keys and password_key in present_keys for user_key, password_key in TQSDK_CREDENTIAL_PAIRS)


def inspect_tqsdk_module() -> dict[str, Any]:
    result: dict[str, Any] = {
        "module_importable": False,
        "module_version": "",
        "module_file": "",
        "has_tqapi": False,
        "has_tqauth": False,
        "has_tqsim": False,
        "has_data_downloader": False,
        "import_error_type": "",
        "import_error_message": "",
    }
    try:
        captured_stdout = StringIO()
        captured_stderr = StringIO()
        with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
            module = importlib.import_module("tqsdk")
        result["module_importable"] = True
        result["module_file"] = str(getattr(module, "__file__", ""))
        try:
            result["module_version"] = importlib.metadata.version("tqsdk")
        except importlib.metadata.PackageNotFoundError:
            result["module_version"] = str(getattr(module, "__version__", ""))
        result["has_tqapi"] = hasattr(module, "TqApi")
        result["has_tqauth"] = hasattr(module, "TqAuth")
        result["has_tqsim"] = hasattr(module, "TqSim")
        try:
            with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
                tools_module = importlib.import_module("tqsdk.tools")
            result["has_data_downloader"] = hasattr(tools_module, "DataDownloader")
        except Exception as exc:
            result["import_error_type"] = type(exc).__name__
            result["import_error_message"] = str(exc)[:300]
        captured = "\n".join(
            item.strip() for item in (captured_stdout.getvalue(), captured_stderr.getvalue()) if item.strip()
        )
        result["import_notice_captured"] = bool(captured)
    except Exception as exc:
        result["import_error_type"] = type(exc).__name__
        result["import_error_message"] = str(exc)[:300]
    return result


def build_probe_plan() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product in TARGET_OPTION_PRODUCTS:
        exchange = product.split(".")[-1]
        root = product.split(".")[0]
        rows.append(
            {
                "target_product": product,
                "exchange": exchange,
                "root_symbol": root,
                "probe_role": "authorized_vendor_history_chain_candidate",
                "sample_symbol_hint": f"{exchange}.{root} option contracts via TqSdk symbol discovery",
                "required_start": "2018-01-01",
                "required_end": "2026-06-29",
                "required_frequency": "daily_or_finer",
                "network_probe_default_enabled": ENABLE_NETWORK_PROBE,
            }
        )
    return pd.DataFrame(rows)


def build_permission_probe(credential_audit: pd.DataFrame, module_info: dict[str, Any]) -> dict[str, Any]:
    has_module = _as_bool(module_info.get("module_importable")) and _as_bool(module_info.get("has_data_downloader"))
    has_credentials = credential_pair_available(credential_audit)
    base = {
        "network_probe_enabled": bool(ENABLE_NETWORK_PROBE),
        "permission_probe_symbol": NETWORK_PROBE_SYMBOL,
        "permission_probe_start": NETWORK_PROBE_START,
        "permission_probe_end": NETWORK_PROBE_END,
        "permission_probe_dur_sec": NETWORK_PROBE_DUR_SEC,
        "permission_probe_status": "",
        "download_probe_rows": 0,
        "download_probe_file_created": False,
        "error_type": "",
        "error_message": "",
    }
    if not has_module:
        base["permission_probe_status"] = "skipped_module_not_ready"
        return base
    if not has_credentials:
        base["permission_probe_status"] = "skipped_no_credentials"
        return base
    if not ENABLE_NETWORK_PROBE:
        base["permission_probe_status"] = "skipped_by_default"
        return base

    # This block is deliberately opt-in only. It uses TqSim and TqAuth for a tiny
    # historical data download probe, never a real trading account.
    try:
        user, password = _load_first_env_credential_pair()
        if not user or not password:
            base["permission_probe_status"] = "skipped_credentials_not_in_environment"
            return base
        from tqsdk import TqApi, TqAuth, TqSim
        from tqsdk.tools import DataDownloader

        csv_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tiny_permission_probe_{MODEL_TAG}.csv"
        api = TqApi(TqSim(), auth=TqAuth(user, password))
        task = DataDownloader(
            api,
            symbol_list=NETWORK_PROBE_SYMBOL,
            dur_sec=NETWORK_PROBE_DUR_SEC,
            start_dt=date.fromisoformat(NETWORK_PROBE_START),
            end_dt=date.fromisoformat(NETWORK_PROBE_END),
            csv_file_name=str(csv_path),
        )
        while not task.is_finished():
            api.wait_update()
        api.close()
        if csv_path.exists():
            base["download_probe_rows"] = max(0, sum(1 for _ in csv_path.open(encoding="utf-8", errors="ignore")) - 1)
            base["download_probe_file_created"] = True
        base["permission_probe_status"] = "download_probe_success"
        return base
    except Exception as exc:
        base["permission_probe_status"] = "download_probe_failed"
        base["error_type"] = type(exc).__name__
        base["error_message"] = str(exc)[:300]
        return base


def _load_first_env_credential_pair() -> tuple[str, str]:
    for user_key, password_key in TQSDK_CREDENTIAL_PAIRS:
        user = os.environ.get(user_key, "").strip()
        password = os.environ.get(password_key, "").strip()
        if user and password:
            return user, password
    return "", ""


def classify_tqsdk_readiness(
    module_info: dict[str, Any],
    credential_audit: pd.DataFrame,
    permission_probe: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    has_module = _as_bool(module_info.get("module_importable"))
    has_required_classes = all(
        _as_bool(module_info.get(key))
        for key in ("has_tqapi", "has_tqauth", "has_tqsim", "has_data_downloader")
    )
    has_credentials = credential_pair_available(credential_audit)
    probe_status = str(permission_probe.get("permission_probe_status", ""))

    if not has_module:
        readiness_status = "tqsdk_module_missing"
        reasons.append("tqsdk_module_not_importable")
    elif not has_required_classes:
        readiness_status = "tqsdk_components_missing"
        for key in ("has_tqapi", "has_tqauth", "has_tqsim", "has_data_downloader"):
            if not _as_bool(module_info.get(key)):
                reasons.append(f"missing_{key}")
    elif not has_credentials:
        readiness_status = "installed_but_credentials_missing_no_download_probe"
        reasons.append("tqauth_credentials_missing")
    elif probe_status == "download_probe_success":
        readiness_status = "permission_probe_success_not_pit_ready"
        reasons.append("download_permission_small_probe_only")
        reasons.append("full_option_chain_coverage_not_verified")
        reasons.append("publish_timestamp_not_verified")
        reasons.append("continuous_calendar_not_verified")
    elif probe_status == "download_probe_failed":
        readiness_status = "credentials_present_professional_permission_denied_or_failed"
        reasons.append("download_probe_failed_or_permission_denied")
        if permission_probe.get("error_type"):
            reasons.append(str(permission_probe["error_type"]))
    else:
        readiness_status = "credentials_present_permission_unverified"
        reasons.append("professional_downloader_permission_unverified")
        reasons.append(probe_status or "permission_probe_not_run")

    schema_ready = bool(
        readiness_status == "permission_probe_success_not_pit_ready"
        and _as_bool(permission_probe.get("full_history_coverage_passed", False))
        and _as_bool(permission_probe.get("publish_timestamp_verified", False))
        and _as_bool(permission_probe.get("continuous_calendar_verified", False))
        and _as_bool(permission_probe.get("option_chain_fields_verified", False))
    )
    return {
        "source_name": "tqsdk_data_downloader",
        "module_importable": has_module,
        "module_version": str(module_info.get("module_version", "")),
        "has_tqapi": _as_bool(module_info.get("has_tqapi", False)),
        "has_tqauth": _as_bool(module_info.get("has_tqauth", False)),
        "has_tqsim": _as_bool(module_info.get("has_tqsim", False)),
        "has_data_downloader": _as_bool(module_info.get("has_data_downloader", False)),
        "credential_pair_present": bool(has_credentials),
        "permission_probe_status": probe_status,
        "readiness_status": readiness_status,
        "schema_ready_source": bool(schema_ready),
        "rule_candidate_allowed": bool(schema_ready),
        "blocking_reasons": ",".join(list(dict.fromkeys(reasons))),
    }


def build_data_contract() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "contract_id": "tqsdk_commodity_option_chain_history",
                "required_access": "TqAuth account with professional DataDownloader permission; credentials must stay local and redacted in outputs",
                "required_products": ",".join(TARGET_OPTION_PRODUCTS),
                "required_coverage": "2018-01-01 through 2026-06-29 for listed option chains or documented listing-date starts",
                "required_fields": "option_contract,underlying_product,exchange,trade_date,expiry,strike,call_put,open,high,low,close,settlement,volume,open_interest,delta_or_iv_if_available",
                "required_pit_checks": "raw_file_hash,request_parameter_hash,publish_or_exchange_timestamp,no_future_publish_time,continuous_calendar_by_product,contract_listing_calendar",
                "required_repro_checks": "frozen_symbol_discovery_snapshot,download_manifest,per_file_sha256,parser_version_hash,row_count_by_product_date",
                "forbidden_shortcut": "do_not_use_installed_module_or_credentials_as_signal; do_not_treat_one_successful_download_as_ai_feature",
            }
        ]
    )


def make_stage040_decision(readiness: pd.DataFrame) -> dict[str, Any]:
    schema_ready_count = int(readiness["schema_ready_source"].astype(bool).sum()) if not readiness.empty else 0
    credential_pairs = (
        int(readiness["credential_pair_present"].astype(bool).sum())
        if not readiness.empty and "credential_pair_present" in readiness.columns
        else 0
    )
    if schema_ready_count > 0:
        decision = "stage040_tqsdk_option_history_schema_ready_needs_readonly_signal_spec"
        best_next_direction = "freeze_tqsdk_option_history_manifest_then_run_readonly_iv_skew_signal_audit"
    elif credential_pairs > 0:
        decision = "stage040_tqsdk_option_history_not_ready_permission_or_pit_contract_unverified"
        best_next_direction = "run_explicit_small_permission_probe_then_full_manifest_hash_calendar"
    else:
        decision = "stage040_tqsdk_option_history_not_ready_credentials_or_permission_required"
        best_next_direction = "obtain_or_configure_tqsdk_professional_credentials_or_switch_vendor_source"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "schema_ready_source_count": schema_ready_count,
        "credential_pair_present_count": credential_pairs,
        "immediate_strategy_candidate_count": 0,
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "ab_triggered": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "network_probe_enabled": bool(ENABLE_NETWORK_PROBE),
        "source_links": SOURCE_LINKS,
        "external_research_judgment": (
            "TqSdk 官方文档和 GitHub 说明其行情网关提供历史数据能力；DataDownloader 明确支持期货、期权、股票历史数据，"
            "但属于专业版功能并依赖 TqAuth。我的判断是：TqSdk 可以作为 Stage039 后的合理 vendor 路线，"
            "但本机必须先证明专业版权限、全量期权链覆盖、发布时间/hash/连续日历，不能把安装状态或凭证存在当作 AI 特征。"
        ),
        "overfit_reflection_before": "否。本阶段只审计授权数据源可得性，不做收益回测、不调阈值、不选品种方向。",
        "overfit_reflection_after": "否。输出仍停在数据合同和权限 readiness，没有把单次探针或安装状态交易化。",
        "continue_value_before": "有。Stage039 已证 DCE 公共端点不可恢复，授权 vendor 是期权路线继续前必须确认的现实路径。",
        "continue_value_after": "有但前提明确：只有拿到权限并冻结 manifest/hash/日历后，才值得进入 IV/skew 只读信号审计。",
    }


def _write_report(
    module_audit: pd.DataFrame,
    credential_audit: pd.DataFrame,
    probe_plan: pd.DataFrame,
    permission_probe: pd.DataFrame,
    readiness: pd.DataFrame,
    data_contract: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    public_credential_view = credential_audit.copy()
    if not public_credential_view.empty:
        public_credential_view = public_credential_view[
            ["credential_key", "source_type", "source_path", "source_exists", "present", "redacted_value"]
        ]
    lines = [
        "# Stage040 TqSdk 期权历史链 readiness 审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：授权 vendor 数据源只读 readiness；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk 文档说明 DataDownloader 是专业版数据下载功能，支持期货、期权和股票历史数据。",
        "- TqSdk 专业版页进一步说明该能力需要专业版权限；TqApi 示例使用 `TqAuth` 做快期账户认证。",
        "- GitHub/官方介绍说明 TqSdk 有行情网关和历史数据体系，但这不是本机权限已经可用的证明。",
        "- 我的判断：TqSdk 是合理下一条 vendor 路线，但必须先过权限、全量覆盖、PIT 发布时间、hash 和连续日历合同。",
        "",
        "## Module audit",
        "",
        _md_table(module_audit),
        "",
        "## Credential audit（已脱敏）",
        "",
        _md_table(public_credential_view, max_rows=60),
        "",
        "## Probe plan",
        "",
        _md_table(probe_plan, max_rows=40),
        "",
        "## Permission probe",
        "",
        _md_table(permission_probe),
        "",
        "## Readiness",
        "",
        _md_table(readiness),
        "",
        "## Data contract",
        "",
        _md_table(data_contract),
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(
    module_audit: pd.DataFrame,
    credential_audit: pd.DataFrame,
    permission_probe: pd.DataFrame,
    readiness: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage040_tqsdk_option_history_readiness.md"
    credential_public = credential_audit[
        ["credential_key", "source_type", "source_path", "source_exists", "present", "redacted_value"]
    ].copy()
    text = f"""# Stage040 TqSdk 期权历史链 readiness 审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：授权 vendor 期权历史数据源 readiness；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 官方介绍、TqSdk 专业版文档、DataDownloader 文档、TqSdk GitHub。
- 我的判断：DataDownloader 覆盖期货/期权/股票历史数据，是 DCE 公共端点失败后的合理 vendor 路线；但它是专业版能力，必须用 `TqAuth` 证明权限，再冻结下载 manifest、hash、PIT 发布时间和连续日历，不能把“已安装/有凭证”直接当成交易特征。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage040_tqsdk_option_history_readiness.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage040_tqsdk_option_history_readiness.py`
- 新增参数：`STAGE040_ENABLE_NETWORK_PROBE={int(ENABLE_NETWORK_PROBE)}`、`STAGE040_NETWORK_PROBE_SYMBOL={NETWORK_PROBE_SYMBOL}`、`STAGE040_NETWORK_PROBE_START={NETWORK_PROBE_START}`、`STAGE040_NETWORK_PROBE_END={NETWORK_PROBE_END}`、`STAGE040_NETWORK_PROBE_DUR_SEC={NETWORK_PROBE_DUR_SEC}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_direction：`{decision['best_next_direction']}`
- schema_ready_source_count：`{decision['schema_ready_source_count']}`
- credential_pair_present_count：`{decision['credential_pair_present_count']}`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Module audit

{_md_table(module_audit)}

## Credential audit（已脱敏）

{_md_table(credential_public, max_rows=60)}

## Permission probe

{_md_table(permission_probe)}

## Readiness

{_md_table(readiness)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- module_audit：`{MODULE_AUDIT_PATH}`
- credential_audit：`{CREDENTIAL_AUDIT_PATH}`
- probe_plan：`{PROBE_PLAN_PATH}`
- permission_probe：`{PERMISSION_PROBE_PATH}`
- readiness：`{READINESS_PATH}`
- data_contract：`{DATA_CONTRACT_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    module_info = inspect_tqsdk_module()
    credential_audit = detect_tqsdk_credentials()
    probe_plan = build_probe_plan()
    permission_probe_dict = build_permission_probe(credential_audit, module_info)
    readiness_dict = classify_tqsdk_readiness(module_info, credential_audit, permission_probe_dict)
    module_audit = pd.DataFrame([module_info])
    permission_probe = pd.DataFrame([permission_probe_dict])
    readiness = pd.DataFrame([readiness_dict])
    data_contract = build_data_contract()
    decision = make_stage040_decision(readiness)
    _write_report(module_audit, credential_audit, probe_plan, permission_probe, readiness, data_contract, decision)
    stage_record = _write_stage_record(module_audit, credential_audit, permission_probe, readiness, decision)

    module_audit.to_csv(MODULE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    credential_audit.to_csv(CREDENTIAL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    probe_plan.to_csv(PROBE_PLAN_PATH, index=False, encoding="utf-8-sig")
    permission_probe.to_csv(PERMISSION_PROBE_PATH, index=False, encoding="utf-8-sig")
    readiness.to_csv(READINESS_PATH, index=False, encoding="utf-8-sig")
    data_contract.to_csv(DATA_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    decision["outputs"] = {
        "module_audit": str(MODULE_AUDIT_PATH),
        "credential_audit": str(CREDENTIAL_AUDIT_PATH),
        "probe_plan": str(PROBE_PLAN_PATH),
        "permission_probe": str(PERMISSION_PROBE_PATH),
        "readiness": str(READINESS_PATH),
        "data_contract": str(DATA_CONTRACT_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
        "stage_record": str(stage_record),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
