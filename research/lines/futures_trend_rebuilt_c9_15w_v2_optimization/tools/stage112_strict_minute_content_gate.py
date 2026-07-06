from __future__ import annotations

from datetime import datetime, time
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage112"
MODEL_TAG = "stage112_strict_minute_content_gate_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage112_strict_minute_content_gate"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage112_strict_minute_content_gate"
STAGES_DIR = LINE_DIR / "stages"

STAGE052_SCRIPT = LINE_DIR / "tools" / "stage052_tqsdk_jd_minute_backfill.py"
STAGE091_DECISION_PATH = (
    LINE_DIR
    / "outputs"
    / "stage091_jd_margin_source_contract_matrix"
    / "rebuilt_c9_v2_stage091_jd_margin_source_contract_matrix_decision_stage091_jd_margin_source_contract_matrix_v1.json"
)

STRICT_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_strict_manifest_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

SOURCE_LINKS = {
    "vnpy_bardata": "https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py",
    "vnpy_bargenerator": "https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py",
    "tqsdk_market_data": "https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html",
}

JD_DAY_SESSION_TIMES = (
    [time(9, minute) for minute in range(60)]
    + [time(10, minute) for minute in range(15)]
    + [time(10, minute) for minute in range(30, 60)]
    + [time(11, minute) for minute in range(30)]
    + [time(13, minute) for minute in range(30, 60)]
    + [time(14, minute) for minute in range(60)]
)
EXPECTED_JD_DAY_ROWS = len(JD_DAY_SESSION_TIMES)


def _load_stage052():
    spec = importlib.util.spec_from_file_location("stage052_tqsdk_jd_minute_backfill", STAGE052_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE052_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return "" if pd.isna(value) else value.isoformat()
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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def build_strict_file_index(backfill_root: Path) -> tuple[dict[str, Path], dict[str, list[str]]]:
    candidates: dict[str, list[Path]] = {}
    for path in backfill_root.glob("*/*_minute_backtest.csv"):
        exchange = path.parent.name
        contract = path.name.replace("_completed_minute_backtest.csv", "").replace("_minute_backtest.csv", "")
        if contract:
            candidates.setdefault(f"{contract}.{exchange}", []).append(path)
    index: dict[str, Path] = {}
    conflicts: dict[str, list[str]] = {}
    for contract, paths in candidates.items():
        sorted_paths = sorted(paths)
        if len(sorted_paths) == 1:
            index[contract] = sorted_paths[0]
        else:
            conflicts[contract] = [str(path) for path in sorted_paths]
    return index, conflicts


def _safe_read_csv(path: Path) -> tuple[pd.DataFrame, str]:
    try:
        return pd.read_csv(path, encoding="utf-8-sig"), ""
    except Exception as exc:  # pragma: no cover
        return pd.DataFrame(), repr(exc)


def _safe_ts(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce")


def _jd_session_stats(data: pd.DataFrame) -> dict[str, Any]:
    if data.empty or "bar_datetime_ts" not in data.columns:
        return {
            "session_time_error_count": 0,
            "per_day_row_mismatch_count": 0,
            "first_trade_date_matches_request": False,
            "last_trade_date_matches_request": False,
        }
    expected_times = set(JD_DAY_SESSION_TIMES)
    times = data["bar_datetime_ts"].dt.time
    grouped = data.groupby(data["bar_datetime_ts"].dt.date).size()
    return {
        "session_time_error_count": int((~times.isin(expected_times)).sum()),
        "per_day_row_mismatch_count": int((grouped != EXPECTED_JD_DAY_ROWS).sum()),
        "min_day_rows": int(grouped.min()) if not grouped.empty else 0,
        "max_day_rows": int(grouped.max()) if not grouped.empty else 0,
    }


def _audit_one(row: Any, minute_path: Path | None, conflicts: dict[str, list[str]]) -> dict[str, Any]:
    contract = str(row.contract_vt)
    product = str(row.product_vt_symbol)
    request_start = _safe_ts(row.request_start_date)
    request_end = _safe_ts(row.request_end_date)
    observed_price_rows = int(pd.to_numeric(pd.Series([row.observed_price_rows]), errors="coerce").fillna(0).iloc[0])
    result: dict[str, Any] = {
        "contract_vt": contract,
        "product_vt_symbol": product,
        "priority": str(row.priority),
        "request_start_date": str(row.request_start_date),
        "request_end_date": str(row.request_end_date),
        "observed_price_rows": observed_price_rows,
        "minute_file_ready": minute_path is not None,
        "minute_file": str(minute_path) if minute_path is not None else "",
        "source_conflict_count": len(conflicts.get(contract, [])),
        "source_conflict_paths": "|".join(conflicts.get(contract, [])),
        "sha256": "",
        "read_error": "",
        "rows": 0,
        "expected_jd_day_rows": observed_price_rows * EXPECTED_JD_DAY_ROWS if product == "jd.DCE" else 0,
        "unique_vt_symbol_count": 0,
        "first_bar_datetime": "",
        "last_bar_datetime": "",
        "unique_trade_dates": 0,
        "ohlc_null_count": 0,
        "volume_null_count": 0,
        "oi_null_count": 0,
        "duplicate_key_count": 0,
        "monotonic_datetime": False,
        "ohlc_relation_error_count": 0,
        "negative_volume_count": 0,
        "negative_oi_count": 0,
        "request_start_date_match": False,
        "request_end_date_match": False,
        "unique_trade_dates_match": False,
        "jd_total_rows_match": False,
        "jd_session_time_error_count": 0,
        "jd_per_day_row_mismatch_count": 0,
        "jd_min_day_rows": 0,
        "jd_max_day_rows": 0,
        "strict_ready": False,
        "blocking_reason": "",
    }
    if conflicts.get(contract):
        result["blocking_reason"] = "source_conflict"
        return result
    if minute_path is None:
        result["blocking_reason"] = "missing_file"
        return result
    if not minute_path.exists():
        result["blocking_reason"] = "missing_path"
        return result

    result["sha256"] = _sha256(minute_path)
    data, error = _safe_read_csv(minute_path)
    if error:
        result["read_error"] = error
        result["blocking_reason"] = "read_error"
        return result
    required = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    missing_columns = [column for column in required if column not in data.columns]
    if missing_columns:
        result["blocking_reason"] = f"missing_columns:{','.join(missing_columns)}"
        return result
    if data.empty:
        result["blocking_reason"] = "empty_file"
        return result

    data = data.copy()
    data["bar_datetime_ts"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    result["rows"] = int(len(data))
    result["unique_vt_symbol_count"] = int(data["vt_symbol"].astype(str).nunique(dropna=True))
    if data["bar_datetime_ts"].notna().any():
        first_ts = data["bar_datetime_ts"].min()
        last_ts = data["bar_datetime_ts"].max()
        result["first_bar_datetime"] = str(first_ts)
        result["last_bar_datetime"] = str(last_ts)
        result["unique_trade_dates"] = int(data["bar_datetime_ts"].dt.date.nunique())
        result["request_start_date_match"] = bool(pd.notna(request_start) and first_ts.normalize() == request_start.normalize())
        result["request_end_date_match"] = bool(pd.notna(request_end) and last_ts.normalize() == request_end.normalize())
    result["unique_trade_dates_match"] = bool(result["unique_trade_dates"] == observed_price_rows)
    result["ohlc_null_count"] = int(data[["open", "high", "low", "close"]].isna().any(axis=1).sum())
    result["volume_null_count"] = int(data["volume"].isna().sum())
    result["oi_null_count"] = int(data[["open_oi", "close_oi"]].isna().any(axis=1).sum())
    result["duplicate_key_count"] = int(data.duplicated(["vt_symbol", "bar_datetime"]).sum())
    sorted_index = data.sort_values(["vt_symbol", "bar_datetime_ts"], kind="mergesort").index
    result["monotonic_datetime"] = bool(sorted_index.equals(data.index))
    high_ref = data[["open", "low", "close"]].max(axis=1)
    low_ref = data[["open", "high", "close"]].min(axis=1)
    result["ohlc_relation_error_count"] = int((data["high"].lt(high_ref) | data["low"].gt(low_ref)).sum())
    result["negative_volume_count"] = int(data["volume"].lt(0).sum())
    result["negative_oi_count"] = int(data[["open_oi", "close_oi"]].lt(0).any(axis=1).sum())

    if product == "jd.DCE":
        session_stats = _jd_session_stats(data)
        result["jd_session_time_error_count"] = int(session_stats["session_time_error_count"])
        result["jd_per_day_row_mismatch_count"] = int(session_stats["per_day_row_mismatch_count"])
        result["jd_min_day_rows"] = int(session_stats.get("min_day_rows", 0))
        result["jd_max_day_rows"] = int(session_stats.get("max_day_rows", 0))
        result["jd_total_rows_match"] = bool(result["rows"] == observed_price_rows * EXPECTED_JD_DAY_ROWS)
    else:
        result["jd_total_rows_match"] = True

    checks = [
        result["rows"] > 0,
        result["unique_vt_symbol_count"] == 1,
        str(data["vt_symbol"].dropna().astype(str).iloc[0]) == contract,
        result["ohlc_null_count"] == 0,
        result["volume_null_count"] == 0,
        result["oi_null_count"] == 0,
        result["duplicate_key_count"] == 0,
        result["monotonic_datetime"],
        result["ohlc_relation_error_count"] == 0,
        result["negative_volume_count"] == 0,
        result["negative_oi_count"] == 0,
        result["request_start_date_match"],
        result["request_end_date_match"],
        result["unique_trade_dates_match"],
        result["jd_total_rows_match"],
    ]
    if product == "jd.DCE":
        checks.extend([result["jd_session_time_error_count"] == 0, result["jd_per_day_row_mismatch_count"] == 0])
    result["strict_ready"] = bool(all(checks))

    if result["strict_ready"]:
        result["blocking_reason"] = ""
    else:
        boolean_failed = [
            key
            for key in [
                "monotonic_datetime",
                "request_start_date_match",
                "request_end_date_match",
                "unique_trade_dates_match",
                "jd_total_rows_match",
            ]
            if not bool(result.get(key))
        ]
        numeric_failed = [
            key
            for key in [
                "unique_vt_symbol_count",
                "ohlc_null_count",
                "volume_null_count",
                "oi_null_count",
                "duplicate_key_count",
                "ohlc_relation_error_count",
                "negative_volume_count",
                "negative_oi_count",
                "jd_session_time_error_count",
                "jd_per_day_row_mismatch_count",
            ]
            if (int(result.get(key, 0) or 0) != 1 if key == "unique_vt_symbol_count" else int(result.get(key, 0) or 0) != 0)
        ]
        result["blocking_reason"] = "strict_failed:" + ",".join(sorted(set(boolean_failed + numeric_failed)))
    return result


def build_strict_manifest() -> pd.DataFrame:
    mod = _load_stage052()
    manifest = mod._read_csv(mod.MINUTE_GAP_MANIFEST_PATH)
    minute_index, conflicts = build_strict_file_index(mod.BACKFILL_ROOT)
    rows = [_audit_one(row, minute_index.get(str(row.contract_vt)), conflicts) for row in manifest.itertuples(index=False)]
    return pd.DataFrame(rows)


def build_summary(strict: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product, group in strict.groupby("product_vt_symbol", dropna=False):
        ready = group["strict_ready"].astype(bool)
        rows.append(
            {
                "product_vt_symbol": str(product),
                "contract_count": int(len(group)),
                "minute_file_ready": int(group["minute_file_ready"].astype(bool).sum()),
                "strict_ready": int(ready.sum()),
                "missing_file_count": int(group["blocking_reason"].astype(str).eq("missing_file").sum()),
                "source_conflict_count": int(group["source_conflict_count"].gt(0).sum()),
                "strict_failed_count": int((group["minute_file_ready"].astype(bool) & ~ready).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["product_vt_symbol"]).reset_index(drop=True)


def _stage091_margin_ready() -> tuple[bool, str]:
    if not STAGE091_DECISION_PATH.exists():
        return False, "stage091_decision_missing"
    data = json.loads(STAGE091_DECISION_PATH.read_text(encoding="utf-8"))
    accepted = int(data.get("accepted_route_count", 0) or 0)
    ready = bool(data.get("ready_for_true_ledger_replay", False))
    decision = str(data.get("decision", ""))
    return bool(ready and accepted > 0), decision


def make_decision(strict: pd.DataFrame) -> dict[str, Any]:
    total = int(len(strict))
    file_ready = int(strict["minute_file_ready"].astype(bool).sum())
    strict_ready = int(strict["strict_ready"].astype(bool).sum())
    missing = int((~strict["minute_file_ready"].astype(bool)).sum())
    strict_failed = int(strict["minute_file_ready"].astype(bool).sum() - strict_ready)
    remaining_jd_not_ready = int(
        (strict["product_vt_symbol"].astype(str).eq("jd.DCE") & ~strict["strict_ready"].astype(bool)).sum()
    )
    margin_ready, margin_decision = _stage091_margin_ready()
    if missing == 0 and strict_failed == 0 and margin_ready:
        decision = "stage112_strict_minute_and_margin_ready_for_true_ledger_gate"
        ready_for_true_ledger_replay = True
    elif strict_failed > 0:
        decision = "stage112_strict_minute_content_failed_keep_blocked"
        ready_for_true_ledger_replay = False
    else:
        decision = "stage112_strict_minute_existing_files_pass_margin_or_missing_files_blocked"
        ready_for_true_ledger_replay = False
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "manifest_contract_count": total,
        "minute_file_ready_count": file_ready,
        "strict_ready_count": strict_ready,
        "minute_missing_count": missing,
        "strict_failed_count": strict_failed,
        "remaining_jd_not_ready_count": remaining_jd_not_ready,
        "expected_jd_day_rows": EXPECTED_JD_DAY_ROWS,
        "jd_margin_history_ready": margin_ready,
        "stage091_decision": margin_decision,
        "ready_for_true_ledger_replay": ready_for_true_ledger_replay,
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine_run": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "formal_ab_triggered": False,
        "source_links": SOURCE_LINKS,
        "external_research_judgment": (
            "vn.py 的 BarData/BarGenerator 语义支持用 OHLC、时间序列、重复键做基础验收；"
            "本阶段把 Stage111 的偏宽口径收紧为 strict gate，防止乱序、session 缺失或 OI/volume 异常数据进入真账本。"
        ),
        "overfit_reflection_before": "否。本阶段只收紧数据 gate，不看收益、不调策略参数。",
        "overfit_reflection_after": "否。严格门槛只会降低错误数据通过概率，不会通过绩效筛选制造收益。",
        "continue_value_before": "有。Stage111 独立评估指出若不收紧 manifest，后续批次可能继承偏宽口径。",
        "continue_value_after": "有。若 strict 通过，可继续补剩余 jd；若失败，应先修数据而不是跑回测。",
        "outputs": {
            "strict_manifest": str(STRICT_MANIFEST_PATH),
            "summary": str(SUMMARY_PATH),
            "input_audit": str(INPUT_AUDIT_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], strict: pd.DataFrame, summary: pd.DataFrame) -> None:
    failures = strict[strict["minute_file_ready"].astype(bool) & ~strict["strict_ready"].astype(bool)].copy()
    missing = strict[~strict["minute_file_ready"].astype(bool)].copy()
    lines = [
        "# Stage112 strict minute content gate",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读严格数据验收；不下载、不回测收益、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- vn.py 的 BarData/BarGenerator 是 OHLC bar 语义，适合把高低价关系、时间序列、重复键纳入数据闸门。",
        "- 我的判断：Stage112 不创造 alpha，只把 Stage111 agent 提醒的宽口径收紧。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## Blocking Counts",
        "",
        f"- manifest_contract_count：`{decision['manifest_contract_count']}`",
        f"- minute_file_ready_count：`{decision['minute_file_ready_count']}`",
        f"- strict_ready_count：`{decision['strict_ready_count']}`",
        f"- minute_missing_count：`{decision['minute_missing_count']}`",
        f"- strict_failed_count：`{decision['strict_failed_count']}`",
        f"- remaining_jd_not_ready_count：`{decision['remaining_jd_not_ready_count']}`",
        f"- expected_jd_day_rows：`{decision['expected_jd_day_rows']}`",
        f"- jd_margin_history_ready：`{decision['jd_margin_history_ready']}`",
        f"- ready_for_true_ledger_replay：`{decision['ready_for_true_ledger_replay']}`",
        "",
        "## Strict Failures",
        "",
        _md_table(
            failures[
                [
                    "contract_vt",
                    "rows",
                    "blocking_reason",
                    "monotonic_datetime",
                    "volume_null_count",
                    "oi_null_count",
                    "negative_oi_count",
                    "request_start_date_match",
                    "request_end_date_match",
                    "unique_trade_dates_match",
                    "jd_session_time_error_count",
                    "jd_per_day_row_mismatch_count",
                ]
            ],
            max_rows=80,
        )
        if not failures.empty
        else "_无记录_",
        "",
        "## Missing Files",
        "",
        _md_table(missing[["contract_vt", "product_vt_symbol", "priority", "request_start_date", "request_end_date"]], max_rows=80),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出",
        "",
        f"- strict_manifest：`{STRICT_MANIFEST_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- input_audit：`{INPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], strict: pd.DataFrame, summary: pd.DataFrame) -> Path:
    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage112_strict_minute_content_gate.md"
    failures = strict[strict["minute_file_ready"].astype(bool) & ~strict["strict_ready"].astype(bool)].copy()
    missing = strict[~strict["minute_file_ready"].astype(bool)].copy()
    lines = [
        "# Stage112 strict minute content gate",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        "- 阶段性质：只读严格数据验收；不下载、不回测收益、不改官方 live config、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 参考：vn.py `BarData` / `BarGenerator`、TqSdk market data。",
        "- 我的判断：这是对 Stage111 的数据闸门收紧，不是策略优化；通过也只代表现有分钟文件更可信。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage112_strict_minute_content_gate.py`",
        "- 新增参数：无。",
        "- 修改参数：无正式策略参数修改。",
        "- 删除参数：无。",
        "",
        "## 结果",
        "",
        f"- decision：`{decision['decision']}`",
        f"- manifest_contract_count：`{decision['manifest_contract_count']}`",
        f"- minute_file_ready_count：`{decision['minute_file_ready_count']}`",
        f"- strict_ready_count：`{decision['strict_ready_count']}`",
        f"- minute_missing_count：`{decision['minute_missing_count']}`",
        f"- strict_failed_count：`{decision['strict_failed_count']}`",
        f"- remaining_jd_not_ready_count：`{decision['remaining_jd_not_ready_count']}`",
        f"- expected_jd_day_rows：`{decision['expected_jd_day_rows']}`",
        f"- jd_margin_history_ready：`{decision['jd_margin_history_ready']}`",
        "- ready_for_true_ledger_replay：`False`",
        "- 策略变更：`False`",
        "- true engine run：`False`",
        "- order API：`0`",
        "- CTP：`False`",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## Strict Failures",
        "",
        _md_table(
            failures[
                [
                    "contract_vt",
                    "rows",
                    "blocking_reason",
                    "monotonic_datetime",
                    "volume_null_count",
                    "oi_null_count",
                    "negative_oi_count",
                    "request_start_date_match",
                    "request_end_date_match",
                    "unique_trade_dates_match",
                    "jd_session_time_error_count",
                    "jd_per_day_row_mismatch_count",
                ]
            ],
            max_rows=80,
        )
        if not failures.empty
        else "_无记录_",
        "",
        "## Missing Files",
        "",
        _md_table(missing[["contract_vt", "product_vt_symbol", "priority", "request_start_date", "request_end_date"]], max_rows=80),
        "",
        "## 回测记录字段",
        "",
        "- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。",
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
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- strict_manifest：`{STRICT_MANIFEST_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- input_audit：`{INPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    stage_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stage_path


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    mod = _load_stage052()
    strict = build_strict_manifest()
    summary = build_summary(strict)
    input_paths = [
        STAGE052_SCRIPT,
        mod.MINUTE_GAP_MANIFEST_PATH,
        STAGE091_DECISION_PATH,
        *[Path(p) for p in strict["minute_file"].astype(str).tolist() if p],
    ]
    input_audit = _input_audit(input_paths)
    decision = make_decision(strict)

    strict.to_csv(STRICT_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, strict, summary)
    stage_path = _write_stage_record(decision, strict, summary)
    decision["outputs"]["stage_record"] = str(stage_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"stage_record={stage_path}")
    return decision


if __name__ == "__main__":
    run()
