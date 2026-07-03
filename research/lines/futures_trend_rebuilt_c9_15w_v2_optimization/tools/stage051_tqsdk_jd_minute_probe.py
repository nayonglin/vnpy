from __future__ import annotations

from datetime import datetime, timedelta
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import time
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from vnpy.trader.setting import SETTINGS


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage051"
MODEL_TAG = "stage051_tqsdk_jd_minute_probe_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage051_tqsdk_jd_minute_probe"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage051_tqsdk_jd_minute_probe"
RAW_DIR = OUTPUT_DIR / "raw_tqsdk_probe"
STAGES_DIR = LINE_DIR / "stages"

STAGE050_OUTPUT_DIR = LINE_DIR / "outputs" / "stage050_jd_true_carry_data_manifest"
STAGE050_PREFIX = "rebuilt_c9_v2_stage050_jd_true_carry_data_manifest"
STAGE050_TAG = "stage050_jd_true_carry_data_manifest_v1"
MINUTE_GAP_MANIFEST_PATH = STAGE050_OUTPUT_DIR / f"{STAGE050_PREFIX}_minute_gap_manifest_{STAGE050_TAG}.csv"

MODULE_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_audit_{MODEL_TAG}.csv"
CREDENTIAL_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_credential_audit_{MODEL_TAG}.csv"
PROBE_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_plan_{MODEL_TAG}.csv"
PROBE_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_status_{MODEL_TAG}.csv"
PROBE_BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_bars_{MODEL_TAG}.csv"
READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage051_tqsdk_jd_minute_probe.md"

CHINA_TZ = ZoneInfo("Asia/Shanghai")
ENABLE_NETWORK_PROBE = os.getenv("STAGE051_ENABLE_NETWORK_PROBE", "0").strip() == "1"
MAX_SYMBOLS = int(os.getenv("STAGE051_MAX_SYMBOLS", "1"))
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE051_MAX_SECONDS_PER_SYMBOL", "60"))
PROBE_START_TIME = os.getenv("STAGE051_PROBE_START_TIME", "21:00:00").strip()
PROBE_END_NEXT_DAY_TIME = os.getenv("STAGE051_PROBE_END_NEXT_DAY_TIME", "09:10:00").strip()

SOURCE_LINKS = {
    "tqsdk_reference": "https://tqsdk-python.readthedocs.io/en/stable/reference/",
    "tqsdk_github": "https://github.com/shinnytech/tqsdk-python",
    "pbo_ssrn": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253",
    "managed_futures_century": "https://fairmodel.econ.yale.edu/ec439/hurst.pdf",
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
        if math.isnan(result) or math.isinf(result):
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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _probe_start_for_date(value: Any) -> pd.Timestamp:
    date_part = pd.Timestamp(value).date().isoformat()
    return pd.Timestamp(f"{date_part} {PROBE_START_TIME}")


def _probe_end_for_date(value: Any) -> pd.Timestamp:
    start_date = pd.Timestamp(value).date()
    next_date = start_date + timedelta(days=1)
    return pd.Timestamp(f"{next_date.isoformat()} {PROBE_END_NEXT_DAY_TIME}")


def build_probe_plan(minute_manifest: pd.DataFrame, max_symbols: int = 1) -> pd.DataFrame:
    data = minute_manifest.copy()
    data = data[data["product_vt_symbol"].astype(str).eq("jd.DCE")].copy()
    if data.empty:
        return pd.DataFrame(
            columns=[
                "contract_vt",
                "product_vt_symbol",
                "tq_symbol",
                "request_start_date",
                "request_end_date",
                "probe_start_datetime",
                "probe_end_datetime",
                "observed_price_rows",
                "priority",
            ]
        )
    data["request_start_ts"] = pd.to_datetime(data["request_start_date"], errors="coerce")
    data["request_end_ts"] = pd.to_datetime(data["request_end_date"], errors="coerce")
    data["observed_price_rows"] = pd.to_numeric(data["observed_price_rows"], errors="coerce").fillna(0).astype(int)
    data["priority_rank"] = np.where(data["priority"].astype(str).str.startswith("P0"), 0, 1)
    data = data.dropna(subset=["request_start_ts", "request_end_ts"]).copy()
    data = data.sort_values(
        ["priority_rank", "observed_price_rows", "request_start_ts", "contract_vt"],
        ascending=[True, True, False, True],
    )
    if max_symbols > 0:
        data = data.head(max_symbols).copy()
    data["tq_symbol"] = data["contract_vt"].map(to_tqsdk_symbol)
    data["probe_start_datetime"] = data["request_start_ts"].map(_probe_start_for_date).astype(str)
    data["probe_end_datetime"] = data["request_start_ts"].map(_probe_end_for_date).astype(str)
    columns = [
        "contract_vt",
        "product_vt_symbol",
        "tq_symbol",
        "request_start_date",
        "request_end_date",
        "probe_start_datetime",
        "probe_end_datetime",
        "observed_price_rows",
        "priority",
    ]
    return data[columns].reset_index(drop=True)


def inspect_tqsdk_module() -> dict[str, Any]:
    result: dict[str, Any] = {
        "module_importable": False,
        "module_version": "",
        "module_file": "",
        "has_tqapi": False,
        "has_tqauth": False,
        "has_tqsim": False,
        "has_tqbacktest": False,
        "import_error_type": "",
        "import_error": "",
    }
    try:
        module = importlib.import_module("tqsdk")
        result["module_importable"] = True
        result["module_file"] = str(getattr(module, "__file__", ""))
        try:
            result["module_version"] = importlib.metadata.version("tqsdk")
        except importlib.metadata.PackageNotFoundError:
            result["module_version"] = str(getattr(module, "__version__", ""))
        for attr in ("TqApi", "TqAuth", "TqSim", "TqBacktest"):
            result[f"has_{attr.lower()}"] = hasattr(module, attr)
    except Exception as exc:
        result["import_error_type"] = type(exc).__name__
        result["import_error"] = repr(exc)
    return result


def audit_tqsdk_credentials(env: dict[str, str] | None = None) -> dict[str, Any]:
    source_env = dict(os.environ if env is None else env)
    env_keys = (
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
    present_env_keys = [key for key in env_keys if str(source_env.get(key, "")).strip()]
    return {
        "settings_datafeed_username_present": bool(str(SETTINGS.get("datafeed.username", "")).strip()),
        "settings_datafeed_password_present": bool(str(SETTINGS.get("datafeed.password", "")).strip()),
        "environment_tqsdk_key_count": len(present_env_keys),
        "environment_tqsdk_keys_present": ",".join(present_env_keys),
        "credential_values_redacted": True,
    }


def _credential_present(credential_audit: dict[str, Any] | pd.DataFrame) -> bool:
    if isinstance(credential_audit, pd.DataFrame):
        if credential_audit.empty:
            return False
        row = credential_audit.iloc[0].to_dict()
    else:
        row = dict(credential_audit)
    return bool(row.get("settings_datafeed_username_present")) and bool(row.get("settings_datafeed_password_present"))


def classify_probe_readiness(
    module_audit: dict[str, Any],
    credential_audit: dict[str, Any] | pd.DataFrame,
    probe_plan: pd.DataFrame,
    network_enabled: bool,
) -> dict[str, Any]:
    missing_module = not bool(module_audit.get("module_importable"))
    missing_api = not all(bool(module_audit.get(key)) for key in ("has_tqapi", "has_tqauth", "has_tqsim"))
    missing_plan = probe_plan.empty
    missing_credentials = not _credential_present(credential_audit)
    if missing_module or missing_api:
        readiness = "blocked_tqsdk_module_incomplete"
    elif missing_credentials:
        readiness = "blocked_missing_tqsdk_credentials"
    elif missing_plan:
        readiness = "blocked_no_jd_minute_gap_plan"
    elif not network_enabled:
        readiness = "ready_but_network_probe_disabled"
    else:
        readiness = "ready_for_tqsdk_backtest_probe"
    return {
        "stage": STAGE,
        "readiness": readiness,
        "module_ready": not (missing_module or missing_api),
        "credentials_ready": not missing_credentials,
        "probe_plan_ready": not missing_plan,
        "network_probe_enabled": bool(network_enabled),
        "probe_plan_rows": int(len(probe_plan)),
    }


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(CHINA_TZ).tz_localize(None)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def run_tqsdk_backtest_probe(
    probe_plan: pd.DataFrame,
    username: str,
    password: str,
    max_seconds_per_symbol: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim

    status_rows: list[dict[str, Any]] = []
    bar_rows: list[dict[str, Any]] = []
    for row in probe_plan.itertuples(index=False):
        vt_symbol = str(row.contract_vt)
        tq_symbol = str(row.tq_symbol)
        start_dt = pd.Timestamp(row.probe_start_datetime).to_pydatetime()
        end_dt = pd.Timestamp(row.probe_end_datetime).to_pydatetime()
        raw_path = RAW_DIR / tq_symbol.split(".", 1)[0] / f"{tq_symbol.split('.', 1)[1]}_minute_probe.csv"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        started = time.time()
        seen_ids: set[int] = set()
        status = {
            "contract_vt": vt_symbol,
            "tq_symbol": tq_symbol,
            "probe_start_datetime": pd.Timestamp(start_dt),
            "probe_end_datetime": pd.Timestamp(end_dt),
            "status": "unknown",
            "rows": 0,
            "first_bar_datetime": "",
            "last_bar_datetime": "",
            "elapsed_seconds": 0.0,
            "raw_path": str(raw_path),
            "message": "",
        }
        symbol_bars: list[dict[str, Any]] = []
        api = None
        try:
            api = TqApi(TqSim(), backtest=TqBacktest(start_dt=start_dt, end_dt=end_dt), auth=TqAuth(username, password))
            klines = api.get_kline_serial(tq_symbol, duration_seconds=60, data_length=500)
            while True:
                if time.time() - started > max_seconds_per_symbol:
                    status["status"] = "timeout"
                    status["message"] = f"timeout_after_{max_seconds_per_symbol}s"
                    break
                try:
                    changed = api.wait_update(deadline=time.time() + 1.0)
                except BacktestFinished:
                    status["status"] = "extracted"
                    break
                if not changed:
                    continue
                for _, kline_row in klines.iterrows():
                    row_dict = kline_row.to_dict()
                    bar_id = int(row_dict.get("id", -1))
                    if bar_id in seen_ids:
                        continue
                    bar_dt = _normalize_tqsdk_datetime(row_dict.get("datetime"))
                    if pd.isna(bar_dt) or bar_dt < pd.Timestamp(start_dt) or bar_dt > pd.Timestamp(end_dt):
                        continue
                    seen_ids.add(bar_id)
                    symbol_bars.append(
                        {
                            "contract_vt": vt_symbol,
                            "tq_symbol": tq_symbol,
                            "bar_datetime": bar_dt,
                            "bar_id": bar_id,
                            "open": _safe_float(row_dict.get("open")),
                            "high": _safe_float(row_dict.get("high")),
                            "low": _safe_float(row_dict.get("low")),
                            "close": _safe_float(row_dict.get("close")),
                            "volume": _safe_float(row_dict.get("volume")),
                            "open_oi": _safe_float(row_dict.get("open_oi")),
                            "close_oi": _safe_float(row_dict.get("close_oi")),
                        }
                    )
        except Exception as exc:
            status["status"] = "failed"
            status["message"] = repr(exc)
        finally:
            if api is not None:
                api.close()
        bars = pd.DataFrame(symbol_bars)
        if not bars.empty:
            bars = bars.drop_duplicates(["contract_vt", "bar_datetime"]).sort_values(["contract_vt", "bar_datetime"])
            bars.to_csv(raw_path, index=False, encoding="utf-8-sig")
            status["first_bar_datetime"] = str(bars["bar_datetime"].iloc[0])
            status["last_bar_datetime"] = str(bars["bar_datetime"].iloc[-1])
        status["rows"] = int(len(bars))
        if status["status"] == "unknown":
            status["status"] = "extracted" if len(bars) else "empty"
        status["elapsed_seconds"] = round(time.time() - started, 2)
        status_rows.append(status)
        bar_rows.extend(bars.to_dict("records") if not bars.empty else [])
    return pd.DataFrame(status_rows), pd.DataFrame(bar_rows)


def make_decision(
    readiness: dict[str, Any],
    probe_status: pd.DataFrame,
    probe_plan: pd.DataFrame,
    module_audit: dict[str, Any],
    credential_audit: dict[str, Any],
) -> dict[str, Any]:
    success_rows = int((probe_status["rows"].fillna(0).astype(int) > 0).sum()) if not probe_status.empty else 0
    if readiness["readiness"] == "ready_for_tqsdk_backtest_probe" and success_rows > 0:
        decision = "stage051_tqsdk_jd_minute_probe_success_ready_for_limited_gap_download"
        minute_gap_download_ready = True
    elif readiness["readiness"] == "ready_but_network_probe_disabled":
        decision = "stage051_tqsdk_jd_minute_probe_readiness_only_network_disabled"
        minute_gap_download_ready = False
    else:
        decision = "stage051_tqsdk_jd_minute_probe_blocked_keep_stage050_manifest"
        minute_gap_download_ready = False
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "readiness": readiness["readiness"],
        "module_version": module_audit.get("module_version", ""),
        "settings_credentials_present": _credential_present(credential_audit),
        "network_probe_enabled": bool(readiness["network_probe_enabled"]),
        "probe_plan_rows": int(len(probe_plan)),
        "probe_status_rows": int(len(probe_status)),
        "probe_success_contract_count": success_rows,
        "minute_gap_download_ready": minute_gap_download_ready,
        "ready_for_true_ledger_replay": False,
        "remaining_blocker": "jd_contract_daily_margin_history" if minute_gap_download_ready else "jd_minute_gap_and_margin_history",
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine_run": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "formal_ab_triggered": False,
        "external_research_judgment": (
            "TqSdk 官方参考文档支持 TqBacktest/TqAuth/TqSim 与 K 线访问，GitHub README 也说明其覆盖历史数据、回测与交易开发；"
            "结合 managed futures 研究和 PBO 风险，本阶段只做数据可行性探针，不把短窗口探针变成策略参数。"
        ),
        "overfit_reflection_before": "否。本阶段只验证缺失数据源能否补齐，不根据收益调参。",
        "overfit_reflection_after": "否。即使分钟探针成功，也只是解除数据层阻塞；仍不创建交易规则。",
        "continue_value_before": "有。Stage050 已把 jd 分钟线列为 Stage208 真承载 P0 阻塞，探针能决定是否进入下载批次。",
        "continue_value_after": (
            "有。若探针成功，下一步补完整 41 个 jd 合约分钟线；若失败，继续转 vendor 或同源回放，避免本地救参。"
        ),
        "source_links": SOURCE_LINKS,
        "outputs": {
            "module_audit": str(MODULE_AUDIT_PATH),
            "credential_audit": str(CREDENTIAL_AUDIT_PATH),
            "probe_plan": str(PROBE_PLAN_PATH),
            "probe_status": str(PROBE_STATUS_PATH),
            "probe_bars": str(PROBE_BARS_PATH),
            "readiness": str(READINESS_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    readiness_frame: pd.DataFrame,
    probe_plan: pd.DataFrame,
    probe_status: pd.DataFrame,
    module_frame: pd.DataFrame,
    credential_frame: pd.DataFrame,
) -> None:
    lines = [
        "# Stage051 TqSdk jd 分钟线小窗口探针",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：数据源可行性探针；不回测收益，不改策略，不连接 CTP，不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk 官方参考文档列出 `TqApi/TqAuth/TqSim/TqBacktest/DataDownloader` 等模块；GitHub README 说明其覆盖历史数据、回测、模拟和实盘开发能力。",
        "- Managed futures 研究强调趋势系统的核心是跨市场分散与右尾捕获；PBO 文献提示不能在有限历史上反复筛选小参数。",
        "- 我的判断：当前不应继续扫 xsmom 或 AI 小阈值，应该先确认能否把 Stage050 的 jd 分钟数据补齐。",
        "",
        "## Readiness",
        "",
        _md_table(readiness_frame),
        "",
        "## Module Audit",
        "",
        _md_table(module_frame),
        "",
        "## Credential Audit",
        "",
        _md_table(credential_frame),
        "",
        "## Probe Plan",
        "",
        _md_table(probe_plan, max_rows=20),
        "",
        "## Probe Status",
        "",
        _md_table(probe_status, max_rows=20),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(
    decision: dict[str, Any],
    readiness_frame: pd.DataFrame,
    probe_plan: pd.DataFrame,
    probe_status: pd.DataFrame,
) -> None:
    text = f"""# Stage051 TqSdk jd 分钟线小窗口探针

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：数据源可行性探针；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 官方参考文档、TqSdk GitHub README、managed futures 研究、PBO 文献。
- 我的判断：当前目标不能靠继续扫可见字段小参数推进；若要复建 Stage208 级真承载，优先确认 TqSdk 是否能补 Stage050 的 jd 分钟缺口。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage051_tqsdk_jd_minute_probe.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage051_tqsdk_jd_minute_probe.py`
- 新增参数：`STAGE051_ENABLE_NETWORK_PROBE`、`STAGE051_MAX_SYMBOLS`、`STAGE051_MAX_SECONDS_PER_SYMBOL`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- readiness：`{decision['readiness']}`
- probe_plan_rows：`{decision['probe_plan_rows']}`
- probe_success_contract_count：`{decision['probe_success_contract_count']}`
- minute_gap_download_ready：`{decision['minute_gap_download_ready']}`
- ready_for_true_ledger_replay：`False`
- remaining_blocker：`{decision['remaining_blocker']}`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Readiness

{_md_table(readiness_frame)}

## Probe Plan

{_md_table(probe_plan, max_rows=20)}

## Probe Status

{_md_table(probe_status, max_rows=20)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- probe_plan：`{PROBE_PLAN_PATH}`
- probe_status：`{PROBE_STATUS_PATH}`
- probe_bars：`{PROBE_BARS_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    minute_manifest = _read_csv(MINUTE_GAP_MANIFEST_PATH)
    probe_plan = build_probe_plan(minute_manifest, max_symbols=MAX_SYMBOLS)
    module_audit = inspect_tqsdk_module()
    credential_audit = audit_tqsdk_credentials()
    readiness = classify_probe_readiness(module_audit, credential_audit, probe_plan, ENABLE_NETWORK_PROBE)

    probe_status = pd.DataFrame()
    probe_bars = pd.DataFrame()
    if readiness["readiness"] == "ready_for_tqsdk_backtest_probe":
        username = str(SETTINGS.get("datafeed.username", "")).strip()
        password = str(SETTINGS.get("datafeed.password", "")).strip()
        probe_status, probe_bars = run_tqsdk_backtest_probe(probe_plan, username, password, MAX_SECONDS_PER_SYMBOL)

    decision = make_decision(readiness, probe_status, probe_plan, module_audit, credential_audit)
    module_frame = pd.DataFrame([module_audit])
    credential_frame = pd.DataFrame([credential_audit])
    readiness_frame = pd.DataFrame([readiness])

    module_frame.to_csv(MODULE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    credential_frame.to_csv(CREDENTIAL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    readiness_frame.to_csv(READINESS_PATH, index=False, encoding="utf-8-sig")
    probe_plan.to_csv(PROBE_PLAN_PATH, index=False, encoding="utf-8-sig")
    probe_status.to_csv(PROBE_STATUS_PATH, index=False, encoding="utf-8-sig")
    probe_bars.to_csv(PROBE_BARS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, readiness_frame, probe_plan, probe_status, module_frame, credential_frame)
    _write_stage_record(decision, readiness_frame, probe_plan, probe_status)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
