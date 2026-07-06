from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage111"
MODEL_TAG = "stage111_minute_content_manifest_gate_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage111_minute_content_manifest_gate"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage111_minute_content_manifest_gate"
STAGES_DIR = LINE_DIR / "stages"

STAGE052_SCRIPT = LINE_DIR / "tools" / "stage052_tqsdk_jd_minute_backfill.py"
STAGE091_DECISION_PATH = (
    LINE_DIR
    / "outputs"
    / "stage091_jd_margin_source_contract_matrix"
    / "rebuilt_c9_v2_stage091_jd_margin_source_contract_matrix_decision_stage091_jd_margin_source_contract_matrix_v1.json"
)

CONTENT_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_content_manifest_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

SOURCE_LINKS = {
    "tqsdk_market_data": "https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html",
    "tqsdk_backtest": "https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html",
    "tqsdk_get_kline_serial": "https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html",
}


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


def _safe_read_csv(path: Path) -> tuple[pd.DataFrame, str]:
    try:
        return pd.read_csv(path, encoding="utf-8-sig"), ""
    except Exception as exc:  # pragma: no cover - this is an audit surface
        return pd.DataFrame(), repr(exc)


def _safe_ts(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce")


def _audit_one(row: Any, minute_path: Path | None) -> dict[str, Any]:
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
        "sha256": "",
        "read_error": "",
        "rows": 0,
        "expected_jd_day_rows": observed_price_rows * 225 if product == "jd.DCE" else 0,
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
        "within_request_window": False,
        "jd_day_rows_match": False,
        "content_basic_ready": False,
        "content_strict_ready": False,
        "blocking_reason": "",
    }
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
    if data.empty:
        result["blocking_reason"] = "empty_file"
        return result

    required = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    missing_columns = [column for column in required if column not in data.columns]
    if missing_columns:
        result["blocking_reason"] = f"missing_columns:{','.join(missing_columns)}"
        return result

    data = data.copy()
    data["bar_datetime_ts"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    rows = int(len(data))
    result["rows"] = rows
    result["unique_vt_symbol_count"] = int(data["vt_symbol"].astype(str).nunique(dropna=True))
    if data["bar_datetime_ts"].notna().any():
        first_ts = data["bar_datetime_ts"].min()
        last_ts = data["bar_datetime_ts"].max()
        result["first_bar_datetime"] = str(first_ts)
        result["last_bar_datetime"] = str(last_ts)
        result["unique_trade_dates"] = int(data["bar_datetime_ts"].dt.date.nunique())
        result["within_request_window"] = bool(
            pd.notna(request_start)
            and pd.notna(request_end)
            and first_ts.normalize() >= request_start.normalize()
            and last_ts.normalize() <= request_end.normalize()
        )

    result["ohlc_null_count"] = int(data[["open", "high", "low", "close"]].isna().any(axis=1).sum())
    result["volume_null_count"] = int(data["volume"].isna().sum())
    result["oi_null_count"] = int(data[["open_oi", "close_oi"]].isna().any(axis=1).sum())
    result["duplicate_key_count"] = int(data.duplicated(["vt_symbol", "bar_datetime"]).sum())
    result["monotonic_datetime"] = bool(data.sort_values(["vt_symbol", "bar_datetime_ts"]).index.equals(data.index))
    high_ref = data[["open", "low", "close"]].max(axis=1)
    low_ref = data[["open", "high", "close"]].min(axis=1)
    result["ohlc_relation_error_count"] = int((data["high"].lt(high_ref) | data["low"].gt(low_ref)).sum())
    result["negative_volume_count"] = int(data["volume"].lt(0).sum())
    result["negative_oi_count"] = int(data[["open_oi", "close_oi"]].lt(0).any(axis=1).sum())
    result["jd_day_rows_match"] = bool(product == "jd.DCE" and rows == observed_price_rows * 225)

    content_basic_ready = (
        rows > 0
        and result["unique_vt_symbol_count"] == 1
        and str(data["vt_symbol"].dropna().astype(str).iloc[0]) == contract
        and result["ohlc_null_count"] == 0
        and result["duplicate_key_count"] == 0
        and result["ohlc_relation_error_count"] == 0
        and result["negative_volume_count"] == 0
        and result["within_request_window"]
    )
    result["content_basic_ready"] = bool(content_basic_ready)
    if product == "jd.DCE":
        result["content_strict_ready"] = bool(content_basic_ready and result["jd_day_rows_match"])
    else:
        result["content_strict_ready"] = bool(content_basic_ready)

    if not result["content_basic_ready"]:
        result["blocking_reason"] = "basic_content_failed"
    elif product == "jd.DCE" and not result["jd_day_rows_match"]:
        result["blocking_reason"] = "jd_day_rows_mismatch"
    else:
        result["blocking_reason"] = ""
    return result


def build_content_manifest() -> pd.DataFrame:
    mod = _load_stage052()
    manifest = mod._read_csv(mod.MINUTE_GAP_MANIFEST_PATH)
    minute_index = mod.build_minute_file_index()
    rows = [_audit_one(row, minute_index.get(str(row.contract_vt))) for row in manifest.itertuples(index=False)]
    return pd.DataFrame(rows)


def build_summary(content: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product, group in content.groupby("product_vt_symbol", dropna=False):
        rows.append(
            {
                "product_vt_symbol": str(product),
                "contract_count": int(len(group)),
                "minute_file_ready": int(group["minute_file_ready"].astype(bool).sum()),
                "content_basic_ready": int(group["content_basic_ready"].astype(bool).sum()),
                "content_strict_ready": int(group["content_strict_ready"].astype(bool).sum()),
                "missing_file_count": int(group["blocking_reason"].astype(str).eq("missing_file").sum()),
                "failed_content_count": int(
                    group["minute_file_ready"].astype(bool).sum() - group["content_strict_ready"].astype(bool).sum()
                ),
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


def make_decision(content: pd.DataFrame, summary: pd.DataFrame) -> dict[str, Any]:
    total = int(len(content))
    file_ready = int(content["minute_file_ready"].astype(bool).sum())
    strict_ready = int(content["content_strict_ready"].astype(bool).sum())
    missing = int((~content["minute_file_ready"].astype(bool)).sum())
    content_failed = int(content["minute_file_ready"].astype(bool).sum() - strict_ready)
    remaining_jd_missing = int(
        (
            content["product_vt_symbol"].astype(str).eq("jd.DCE")
            & ~content["content_strict_ready"].astype(bool)
        ).sum()
    )
    margin_ready, margin_decision = _stage091_margin_ready()
    if missing == 0 and content_failed == 0 and margin_ready:
        decision = "stage111_minute_content_and_margin_ready_for_true_ledger_gate"
        ready_for_true_ledger_replay = True
    elif content_failed > 0:
        decision = "stage111_minute_content_quality_failed_keep_blocked"
        ready_for_true_ledger_replay = False
    else:
        decision = "stage111_minute_content_ready_for_existing_files_margin_or_missing_files_blocked"
        ready_for_true_ledger_replay = False
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "manifest_contract_count": total,
        "minute_file_ready_count": file_ready,
        "content_strict_ready_count": strict_ready,
        "minute_missing_count": missing,
        "content_failed_count": content_failed,
        "remaining_jd_content_or_file_missing": remaining_jd_missing,
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
            "TqSdk K线接口能提供 OHLC/volume/OI 序列，但真账本回放前不能只看文件存在；"
            "必须把行数、hash、时间窗、重复键、OHLC 合法性和合约保证金分别作为硬闸门。"
        ),
        "overfit_reflection_before": "否。本阶段只做分钟数据内容验收，不看收益、不调参数、不筛策略结果。",
        "overfit_reflection_after": "否。结论来自数据完整性和保证金阻塞，不来自绩效表现。",
        "continue_value_before": "有。Stage110 已补 6 个 jd 文件，但独立评估要求机器可验 manifest 才能继续。",
        "continue_value_after": (
            "有。若现有文件内容验收通过，可继续补剩余分钟缺口；但 jd 逐日保证金未 ready 前仍不能 true ledger replay。"
        ),
        "outputs": {
            "content_manifest": str(CONTENT_MANIFEST_PATH),
            "summary": str(SUMMARY_PATH),
            "input_audit": str(INPUT_AUDIT_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], content: pd.DataFrame, summary: pd.DataFrame) -> None:
    failures = content[content["minute_file_ready"].astype(bool) & ~content["content_strict_ready"].astype(bool)].copy()
    missing = content[~content["minute_file_ready"].astype(bool)].copy()
    lines = [
        "# Stage111 minute content manifest gate",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读数据内容验收；不下载、不回测收益、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk K线接口提供历史/实时 K 线序列；`TqBacktest` 是历史数据语境，不等同于实盘 CTP 通路。",
        "- 我的判断：文件存在只能证明索引可发现，不能证明可以进入真账本；本阶段把内容级验收固化成机器可复验 manifest。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## Blocking Counts",
        "",
        f"- manifest_contract_count：`{decision['manifest_contract_count']}`",
        f"- minute_file_ready_count：`{decision['minute_file_ready_count']}`",
        f"- content_strict_ready_count：`{decision['content_strict_ready_count']}`",
        f"- minute_missing_count：`{decision['minute_missing_count']}`",
        f"- content_failed_count：`{decision['content_failed_count']}`",
        f"- remaining_jd_content_or_file_missing：`{decision['remaining_jd_content_or_file_missing']}`",
        f"- jd_margin_history_ready：`{decision['jd_margin_history_ready']}`",
        f"- ready_for_true_ledger_replay：`{decision['ready_for_true_ledger_replay']}`",
        "",
        "## Content Failures",
        "",
        _md_table(
            failures[
                [
                    "contract_vt",
                    "rows",
                    "blocking_reason",
                    "ohlc_null_count",
                    "duplicate_key_count",
                    "ohlc_relation_error_count",
                    "within_request_window",
                    "jd_day_rows_match",
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
        f"- content_manifest：`{CONTENT_MANIFEST_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- input_audit：`{INPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], content: pd.DataFrame, summary: pd.DataFrame) -> Path:
    stage_path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage111_minute_content_manifest_gate.md"
    failures = content[content["minute_file_ready"].astype(bool) & ~content["content_strict_ready"].astype(bool)].copy()
    missing = content[~content["minute_file_ready"].astype(bool)].copy()
    lines = [
        "# Stage111 minute content manifest gate",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        "- 阶段性质：只读数据内容验收；不下载、不回测收益、不改官方 live config、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 参考：TqSdk market data、TqBacktest、`get_kline_serial` 官方文档。",
        "- 我的判断：文件存在不是足够证据；真账本前必须有机器可验内容 manifest。该阶段仍不是策略优化。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage111_minute_content_manifest_gate.py`",
        "- 新增参数：无。",
        "- 修改参数：无正式策略参数修改。",
        "- 删除参数：无。",
        "",
        "## 结果",
        "",
        f"- decision：`{decision['decision']}`",
        f"- manifest_contract_count：`{decision['manifest_contract_count']}`",
        f"- minute_file_ready_count：`{decision['minute_file_ready_count']}`",
        f"- content_strict_ready_count：`{decision['content_strict_ready_count']}`",
        f"- minute_missing_count：`{decision['minute_missing_count']}`",
        f"- content_failed_count：`{decision['content_failed_count']}`",
        f"- remaining_jd_content_or_file_missing：`{decision['remaining_jd_content_or_file_missing']}`",
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
        "## Content Failures",
        "",
        _md_table(
            failures[
                [
                    "contract_vt",
                    "rows",
                    "blocking_reason",
                    "ohlc_null_count",
                    "duplicate_key_count",
                    "ohlc_relation_error_count",
                    "within_request_window",
                    "jd_day_rows_match",
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
        f"- content_manifest：`{CONTENT_MANIFEST_PATH}`",
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
    content = build_content_manifest()
    summary = build_summary(content)
    input_paths = [
        STAGE052_SCRIPT,
        mod.MINUTE_GAP_MANIFEST_PATH,
        STAGE091_DECISION_PATH,
        *[Path(p) for p in content["minute_file"].astype(str).tolist() if p],
    ]
    input_audit = _input_audit(input_paths)
    decision = make_decision(content, summary)

    content.to_csv(CONTENT_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, content, summary)
    stage_path = _write_stage_record(decision, content, summary)
    decision["outputs"]["stage_record"] = str(stage_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"stage_record={stage_path}")
    return decision


if __name__ == "__main__":
    run()
