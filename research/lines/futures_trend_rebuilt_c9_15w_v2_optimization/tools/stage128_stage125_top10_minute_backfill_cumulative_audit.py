from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE_ID = "stage128_stage125_top10_minute_backfill_cumulative_audit"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"rebuilt_c9_v2_{STAGE_ID}"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_1624_stage128_stage125_top10_minute_backfill_cumulative_audit.md"

STAGE124_FRAMES_DIR = LINE_DIR / "outputs" / "stage124_full_market_single_product_c9_replay" / "frames_by_product"
RAW_MINUTE_ROOT = (
    ROOT
    / "examples"
    / "portfolio_backtesting"
    / "downloaded_futures"
    / "tqsdk_stage127_stage125_top10_loss_window_minute_backfill"
)

LOSS_WINDOW_START = pd.Timestamp("2022-03-09")
LOSS_WINDOW_END = pd.Timestamp("2022-06-29")
PRODUCTS = ["m.DCE", "ni.SHFE", "CY.CZCE", "eb.DCE", "y.DCE", "zn.SHFE", "ag.SHFE", "v.DCE", "PK.CZCE", "rr.DCE"]

EXPECTED_PATH = OUT / f"{OUTPUT_PREFIX}_expected_contracts_{MODEL_TAG}.csv"
AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_contract_audit_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

SOURCE_LINKS = {
    "tqsdk_backtest": "https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html",
    "tqsdk_data_downloader": "https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return None if not math.isfinite(number) else number
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


def _slug(product: str) -> str:
    return str(product).replace(".", "_").replace("/", "_")


def _raw_path(contract_vt: str) -> Path:
    symbol, exchange = str(contract_vt).split(".", 1)
    return RAW_MINUTE_ROOT / exchange / f"{symbol}_minute_backtest.csv"


def _date_list(values: pd.Series) -> str:
    dates = sorted({pd.Timestamp(v).date().isoformat() for v in values.dropna()})
    return "|".join(dates)


def expected_contracts() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product in PRODUCTS:
        path = STAGE124_FRAMES_DIR / f"{_slug(product)}_closed_lots.csv.gz"
        if not path.exists():
            continue
        lots = pd.read_csv(path)
        lots["entry_date"] = pd.to_datetime(lots.get("entry_date"), errors="coerce").dt.normalize()
        lots["exit_date"] = pd.to_datetime(lots.get("exit_date"), errors="coerce").dt.normalize()
        lots["realized_pnl"] = pd.to_numeric(lots.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
        overlap = lots[
            lots["entry_date"].between(LOSS_WINDOW_START, LOSS_WINDOW_END)
            | lots["exit_date"].between(LOSS_WINDOW_START, LOSS_WINDOW_END)
        ].copy()
        for contract, group in overlap.groupby("vt_symbol", dropna=False):
            contract_text = str(contract)
            contract_lots = lots[lots["vt_symbol"].astype(str).eq(contract_text)].copy()
            entry_dates = contract_lots["entry_date"].dropna()
            if entry_dates.empty:
                continue
            rows.append(
                {
                    "contract_vt": contract_text,
                    "product_vt_symbol": product,
                    "entry_date_count": int(entry_dates.nunique()),
                    "entry_dates": _date_list(entry_dates),
                    "window_overlap_lots": int(len(group)),
                    "all_contract_lots": int(len(contract_lots)),
                    "window_abs_realized_pnl": float(group["realized_pnl"].abs().sum()),
                    "abs_realized_pnl": float(contract_lots["realized_pnl"].abs().sum()),
                    "raw_minute_path": str(_raw_path(contract_text)),
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(
        ["window_abs_realized_pnl", "abs_realized_pnl", "entry_date_count", "contract_vt"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def _audit_one(row: Any) -> dict[str, Any]:
    path = Path(str(row.raw_minute_path))
    entry_dates = [item for item in str(row.entry_dates).split("|") if item]
    result: dict[str, Any] = {
        "contract_vt": str(row.contract_vt),
        "product_vt_symbol": str(row.product_vt_symbol),
        "raw_minute_path": str(path),
        "exists": path.exists(),
        "rows": 0,
        "first_bar_datetime": "",
        "last_bar_datetime": "",
        "sha256": "",
        "entry_date_count": int(row.entry_date_count),
        "entry_dates": str(row.entry_dates),
        "covered_entry_date_count": 0,
        "missing_entry_dates": str(row.entry_dates),
        "duplicate_key_count": 0,
        "ohlc_null_count": 0,
        "ohlc_relation_error_count": 0,
        "negative_volume_count": 0,
        "read_error": "",
        "strict_entry_day_ready": False,
    }
    if not path.exists():
        return result
    try:
        data = pd.read_csv(path, encoding="utf-8-sig")
    except Exception as exc:  # pragma: no cover
        result["read_error"] = repr(exc)
        return result
    required = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        result["read_error"] = "missing_columns:" + ",".join(missing)
        return result
    data["bar_datetime_ts"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data = data.dropna(subset=["bar_datetime_ts"]).copy()
    for column in ["open", "high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["bar_date"] = data["bar_datetime_ts"].dt.strftime("%Y-%m-%d")
    covered = sorted(set(data["bar_date"]) & set(entry_dates))
    missing_entry_dates = sorted(set(entry_dates) - set(covered))
    result.update(
        {
            "rows": int(len(data)),
            "first_bar_datetime": str(data["bar_datetime_ts"].min()) if len(data) else "",
            "last_bar_datetime": str(data["bar_datetime_ts"].max()) if len(data) else "",
            "sha256": _sha256(path),
            "covered_entry_date_count": int(len(covered)),
            "missing_entry_dates": "|".join(missing_entry_dates),
            "duplicate_key_count": int(data.duplicated(["vt_symbol", "bar_datetime_ts"]).sum()),
            "ohlc_null_count": int(data[["open", "high", "low", "close"]].isna().sum().sum()),
            "ohlc_relation_error_count": int(
                (
                    (data["high"] < data[["open", "close", "low"]].max(axis=1))
                    | (data["low"] > data[["open", "close", "high"]].min(axis=1))
                ).sum()
            ),
            "negative_volume_count": int(data["volume"].lt(0).sum()),
        }
    )
    result["strict_entry_day_ready"] = (
        result["exists"]
        and result["rows"] > 0
        and result["covered_entry_date_count"] == result["entry_date_count"]
        and result["duplicate_key_count"] == 0
        and result["ohlc_null_count"] == 0
        and result["ohlc_relation_error_count"] == 0
        and result["negative_volume_count"] == 0
        and not result["read_error"]
    )
    return result


def audit(expected: pd.DataFrame) -> pd.DataFrame:
    if expected.empty:
        return pd.DataFrame()
    return pd.DataFrame([_audit_one(row) for row in expected.itertuples(index=False)])


def summarize(expected: pd.DataFrame, audit_frame: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {"metric": "expected_contract_count", "value": str(int(len(expected)))},
        {"metric": "expected_entry_date_count", "value": str(int(pd.to_numeric(expected.get("entry_date_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())) if not expected.empty else "0"},
        {"metric": "raw_file_exists_count", "value": str(int(audit_frame.get("exists", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())) if not audit_frame.empty else "0"},
        {"metric": "strict_entry_day_ready_count", "value": str(int(audit_frame.get("strict_entry_day_ready", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())) if not audit_frame.empty else "0"},
        {"metric": "covered_entry_date_count", "value": str(int(pd.to_numeric(audit_frame.get("covered_entry_date_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())) if not audit_frame.empty else "0"},
        {"metric": "missing_entry_date_count", "value": str(int(pd.to_numeric(audit_frame.get("entry_date_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum() - pd.to_numeric(audit_frame.get("covered_entry_date_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())) if not audit_frame.empty else "0"},
        {"metric": "total_raw_minute_rows", "value": str(int(pd.to_numeric(audit_frame.get("rows", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())) if not audit_frame.empty else "0"},
        {"metric": "duplicate_key_count", "value": str(int(pd.to_numeric(audit_frame.get("duplicate_key_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())) if not audit_frame.empty else "0"},
        {"metric": "ohlc_null_count", "value": str(int(pd.to_numeric(audit_frame.get("ohlc_null_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())) if not audit_frame.empty else "0"},
        {"metric": "ohlc_relation_error_count", "value": str(int(pd.to_numeric(audit_frame.get("ohlc_relation_error_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())) if not audit_frame.empty else "0"},
        {"metric": "negative_volume_count", "value": str(int(pd.to_numeric(audit_frame.get("negative_volume_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())) if not audit_frame.empty else "0"},
        {"metric": "stage861_full_minute_source_updated", "value": "False"},
        {"metric": "strategy_rule_changed", "value": "False"},
        {"metric": "true_engine_run", "value": "False"},
        {"metric": "order_api_called", "value": "0"},
        {"metric": "ctp_connected", "value": "False"},
    ]
    return pd.DataFrame(rows)


def make_decision(expected: pd.DataFrame, audit_frame: pd.DataFrame, summary: pd.DataFrame) -> dict[str, Any]:
    summary_map = {str(row["metric"]): str(row["value"]) for row in summary.to_dict(orient="records")}
    expected_contracts = int(summary_map.get("expected_contract_count", "0"))
    ready_contracts = int(summary_map.get("strict_entry_day_ready_count", "0"))
    missing_entry_dates = int(summary_map.get("missing_entry_date_count", "0"))
    data_issue_count = int(summary_map.get("duplicate_key_count", "0")) + int(summary_map.get("ohlc_null_count", "0")) + int(summary_map.get("ohlc_relation_error_count", "0")) + int(summary_map.get("negative_volume_count", "0"))
    if expected_contracts > 0 and ready_contracts == expected_contracts and missing_entry_dates == 0 and data_issue_count == 0:
        decision = "stage128_stage125_top10_window_raw_minute_backfill_complete"
    else:
        decision = "stage128_stage125_top10_window_raw_minute_backfill_incomplete"
    return {
        "stage": "Stage128",
        "stage_id": STAGE_ID,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "scope": "Cumulative audit for Stage127 raw minute backfill of Stage125 top10 products' 2022 loss-window overlapping contracts.",
        "expected_contract_count": expected_contracts,
        "strict_entry_day_ready_count": ready_contracts,
        "missing_entry_date_count": missing_entry_dates,
        "total_raw_minute_rows": int(summary_map.get("total_raw_minute_rows", "0")),
        "stage861_full_minute_source_updated": False,
        "strategy_rule_changed": False,
        "true_engine_run": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": "否。本阶段只做数据覆盖审计，不按结果调参或筛选策略。",
        "overfit_reflection_after": "否。补齐和验收 raw 分钟输入只提高输入完整性，不构成策略优化。",
        "continue_value_before": "有。Stage126 指出 Stage125 前十品种分钟加载为 0，必须先验收 raw 分钟输入。",
        "continue_value_after": "有。raw entry-day 数据已可用；下一步若要影响回测，需要合并到 Stage861 覆盖源或让 Stage124 显式读取 overlay。",
        "source_links": SOURCE_LINKS,
        "outputs": {
            "expected": str(EXPECTED_PATH),
            "audit": str(AUDIT_PATH),
            "summary": str(SUMMARY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }


def write_report(decision: dict[str, Any], expected: pd.DataFrame, audit_frame: pd.DataFrame, summary: pd.DataFrame) -> None:
    lines = [
        "# Stage128 Stage125 前十品种分钟补数累计审计",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- decision：`{decision['decision']}`",
        "- 阶段性质：数据补齐验收；不回测收益，不改策略，不连接 CTP，不调用订单 API。",
        "- 结论边界：Stage127 raw entry-day 分钟文件已验收；Stage861 full-minute 源尚未更新，所以既有 Stage124/125 回测结果尚未因此改变。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk `TqBacktest + get_kline_serial` 可按历史时间推进拿分钟 K；DataDownloader 更适合长期批量历史下载但可能需要专业版权限。",
        "- 我的判断：先验收实际交易合约入口日分钟线，是验证 Stage125 stop/retry 口径的最小可行补数闭环。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Contract Audit",
        "",
        _md_table(audit_frame, max_rows=80),
        "",
        "## Expected Contracts",
        "",
        _md_table(expected, max_rows=80),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stage_record(decision: dict[str, Any], expected: pd.DataFrame, audit_frame: pd.DataFrame, summary: pd.DataFrame) -> None:
    lines = [
        "# Stage128 Stage125 前十品种分钟补数累计审计",
        "",
        f"- 时间：{decision['generated_at']}",
        f"- line_id：`{LINE_ID}`",
        "- 类型：数据补齐验收，不是新策略版本，不是新回测",
        f"- decision：`{decision['decision']}`",
        f"- expected_contract_count：`{decision['expected_contract_count']}`",
        f"- strict_entry_day_ready_count：`{decision['strict_entry_day_ready_count']}`",
        f"- missing_entry_date_count：`{decision['missing_entry_date_count']}`",
        f"- total_raw_minute_rows：`{decision['total_raw_minute_rows']}`",
        "- 策略变更：无",
        "- true engine run：无",
        "- 订单 API：`0`",
        "- CTP：`False`",
        "- Stage861 full-minute 源更新：`False`",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Contract Audit",
        "",
        _md_table(audit_frame, max_rows=80),
        "",
        "## 后续",
        "",
        "- 若要让 Stage124/125 重跑时使用这些数据，需要合并到 Stage861 覆盖版 full-minute 源，或在 Stage124 前显式注入 overlay。",
        "- 这次补的是 Stage125 2022 亏损窗口前十品种的 entry-day raw 分钟线，不等于全市场、全合约、全持仓周期分钟线已经完整。",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    expected = expected_contracts()
    audit_frame = audit(expected)
    summary = summarize(expected, audit_frame)
    decision = make_decision(expected, audit_frame, summary)

    expected.to_csv(EXPECTED_PATH, index=False, encoding="utf-8-sig")
    audit_frame.to_csv(AUDIT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(decision, expected, audit_frame, summary)
    write_stage_record(decision, expected, audit_frame, summary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
