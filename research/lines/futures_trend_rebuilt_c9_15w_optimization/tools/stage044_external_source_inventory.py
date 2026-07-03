from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage044"
MODEL_TAG = "stage044_external_source_inventory_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage044_external_source_inventory"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage044_external_source_inventory"
STAGES_DIR = LINE_DIR / "stages"

BACKTEST_OUTPUTS = PROJECT_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"
SUPPLY_DEMAND_DIR = BACKTEST_OUTPUTS / "external_supply_demand_cache"
CFTC_DIR = BACKTEST_OUTPUTS / "external_cftc_cot_cache"
MEMBER_RANK_DIR = BACKTEST_OUTPUTS / "external_domestic_member_rank_cache"
FORWARD_LEDGER_DIR = BACKTEST_OUTPUTS / "external_state_forward_ledger"

OBJECTIVE_START = pd.Timestamp("2020-01-01")
LEFT_TAIL_START = pd.Timestamp("2022-01-01")
LEFT_TAIL_END = pd.Timestamp("2023-12-31")
OBJECTIVE_END = pd.Timestamp("2026-06-30")

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PRODUCT_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_coverage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if not isinstance(value, (str, bytes)) and pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_空_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _normalise_product(value: Any) -> str:
    text = str(value).strip()
    if "." in text:
        text = text.split(".", 1)[0]
    return "".join(ch for ch in text if ch.isalpha()).upper()


def _date_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (int, np.integer)):
        return f"{int(value):08d}"
    if isinstance(value, (float, np.floating)) and np.isfinite(value) and float(value).is_integer():
        return f"{int(value):08d}"
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return f"{int(float(text)):08d}"
    return text


def _parse_dates(series: pd.Series) -> pd.Series:
    text = series.map(_date_text)
    compact = text.str.fullmatch(r"\d{8}")
    parsed = pd.to_datetime(series, errors="coerce")
    if compact.any():
        parsed.loc[compact] = pd.to_datetime(text.loc[compact], format="%Y%m%d", errors="coerce")
    return parsed


def _summarize_table_coverage(
    frame: pd.DataFrame,
    source_name: str,
    date_column: str,
    product_column: str | None = None,
    point_in_time_validated: int = 0,
    source_path: str = "",
    source_authority: str = "",
) -> dict[str, Any]:
    if frame.empty or date_column not in frame.columns:
        return {
            "source_name": source_name,
            "source_path": source_path,
            "source_authority": source_authority,
            "row_count": int(len(frame)),
            "date_min": "",
            "date_max": "",
            "unique_date_count": 0,
            "product_count": 0,
            "covers_objective_start": 0,
            "covers_2022_left_tail": 0,
            "covers_objective_end": 0,
            "point_in_time_validated": int(point_in_time_validated),
        }
    data = frame.copy()
    dates = _parse_dates(data[date_column]).dropna().dt.normalize()
    products = pd.Series(dtype=str)
    if product_column and product_column in data.columns:
        products = data[product_column].dropna().map(_normalise_product)
        products = products[products.ne("")]
    date_min = dates.min() if not dates.empty else pd.NaT
    date_max = dates.max() if not dates.empty else pd.NaT
    return {
        "source_name": source_name,
        "source_path": source_path,
        "source_authority": source_authority,
        "row_count": int(len(frame)),
        "date_min": date_min.date().isoformat() if pd.notna(date_min) else "",
        "date_max": date_max.date().isoformat() if pd.notna(date_max) else "",
        "unique_date_count": int(dates.nunique()) if not dates.empty else 0,
        "product_count": int(products.nunique()) if not products.empty else 0,
        "covers_objective_start": int(pd.notna(date_min) and date_min <= OBJECTIVE_START),
        "covers_2022_left_tail": int(pd.notna(date_min) and pd.notna(date_max) and date_min <= LEFT_TAIL_START and date_max >= LEFT_TAIL_END),
        "covers_objective_end": int(pd.notna(date_max) and date_max >= OBJECTIVE_END),
        "point_in_time_validated": int(point_in_time_validated),
    }


def _classify_source_readiness(summary: dict[str, Any]) -> str:
    if int(summary.get("covers_2022_left_tail", 0)) == 0:
        return "forward_monitor_only"
    if int(summary.get("point_in_time_validated", 0)) == 0:
        return "history_candidate_needs_pit_validation"
    if int(summary.get("product_count", 0)) < 5:
        return "limited_product_history_candidate"
    return "history_selector_candidate"


def _read_csvs(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if path.exists():
            frame = pd.read_csv(path, encoding="utf-8-sig")
            if not frame.empty:
                frames.append(frame.dropna(axis=1, how="all"))
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _basis_history() -> pd.DataFrame:
    return _read_csvs(sorted(SUPPLY_DEMAND_DIR.glob("supply_demand_basis_*.csv")))


def _warehouse_history() -> pd.DataFrame:
    return _read_csvs(sorted(SUPPLY_DEMAND_DIR.glob("supply_demand_warehouse_*.csv")))


def _member_rank_history() -> pd.DataFrame:
    return _read_csvs(sorted(MEMBER_RANK_DIR.glob("member_rank_sum_daily_*.csv")))


def _forward_ledgers() -> pd.DataFrame:
    return _read_csvs(sorted(FORWARD_LEDGER_DIR.glob("*.csv")))


def _cftc_history_summary() -> tuple[dict[str, Any], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for path in sorted(CFTC_DIR.glob("*.zip")):
        with ZipFile(path) as archive:
            names = archive.namelist()
            if not names:
                continue
            with archive.open(names[0]) as handle:
                data = pd.read_csv(handle, usecols=["Report_Date_as_YYYY-MM-DD", "Market_and_Exchange_Names"], low_memory=False)
        data["source_zip"] = path.name
        rows.extend(data.to_dict("records"))
    frame = pd.DataFrame(rows)
    summary = _summarize_table_coverage(
        frame,
        source_name="cftc_cot_disaggregated_weekly",
        date_column="Report_Date_as_YYYY-MM-DD",
        product_column="Market_and_Exchange_Names",
        point_in_time_validated=1,
        source_path=str(CFTC_DIR),
        source_authority="official_cftc",
    )
    summary["readiness"] = "mapping_required_not_cn_direct_selector"
    return summary, frame


def _product_coverage_rows(source_name: str, frame: pd.DataFrame, product_column: str, date_column: str) -> pd.DataFrame:
    if frame.empty or product_column not in frame.columns or date_column not in frame.columns:
        return pd.DataFrame()
    data = frame[[product_column, date_column]].copy()
    data["product_code"] = data[product_column].map(_normalise_product)
    data["date"] = _parse_dates(data[date_column]).dt.normalize()
    data = data.dropna(subset=["date"])
    data = data[data["product_code"].ne("")]
    if data.empty:
        return pd.DataFrame()
    grouped = data.groupby("product_code", as_index=False).agg(
        row_count=("date", "size"),
        date_min=("date", "min"),
        date_max=("date", "max"),
        unique_date_count=("date", "nunique"),
    )
    grouped["source_name"] = source_name
    grouped["date_min"] = grouped["date_min"].dt.date.astype(str)
    grouped["date_max"] = grouped["date_max"].dt.date.astype(str)
    return grouped[["source_name", "product_code", "row_count", "date_min", "date_max", "unique_date_count"]]


def _build_inventory() -> tuple[pd.DataFrame, pd.DataFrame]:
    basis = _basis_history()
    warehouse = _warehouse_history()
    member = _member_rank_history()
    forward = _forward_ledgers()
    cftc_summary, cftc = _cftc_history_summary()

    summaries = [
        _summarize_table_coverage(
            basis,
            source_name="domestic_basis_history_backfill",
            date_column="date",
            product_column="symbol",
            point_in_time_validated=0,
            source_path=str(SUPPLY_DEMAND_DIR),
            source_authority="third_party_akshare_100ppi",
        ),
        _summarize_table_coverage(
            warehouse,
            source_name="domestic_warehouse_receipt_history",
            date_column="date",
            product_column="product_code",
            point_in_time_validated=0,
            source_path=str(SUPPLY_DEMAND_DIR),
            source_authority="exchange_or_exchange_via_library_mixed",
        ),
        _summarize_table_coverage(
            member,
            source_name="domestic_member_rank_history",
            date_column="date",
            product_column="variety",
            point_in_time_validated=0,
            source_path=str(MEMBER_RANK_DIR),
            source_authority="official_exchange_via_library",
        ),
        _summarize_table_coverage(
            forward,
            source_name="external_forward_ledger",
            date_column="source_date",
            product_column="product_code",
            point_in_time_validated=1,
            source_path=str(FORWARD_LEDGER_DIR),
            source_authority="mixed_forward_monitor",
        ),
        cftc_summary,
    ]
    for item in summaries:
        item["readiness"] = item.get("readiness") or _classify_source_readiness(item)
    summary = pd.DataFrame(summaries)

    product_frames = [
        _product_coverage_rows("domestic_basis_history_backfill", basis, "symbol", "date"),
        _product_coverage_rows("domestic_warehouse_receipt_history", warehouse, "product_code", "date"),
        _product_coverage_rows("domestic_member_rank_history", member, "variety", "date"),
        _product_coverage_rows("external_forward_ledger", forward, "product_code", "source_date"),
        _product_coverage_rows("cftc_cot_disaggregated_weekly", cftc, "Market_and_Exchange_Names", "Report_Date_as_YYYY-MM-DD"),
    ]
    product_coverage = pd.concat([f for f in product_frames if not f.empty], ignore_index=True, sort=False)
    return summary, product_coverage


def _write_report(summary: pd.DataFrame, product_coverage: pd.DataFrame, decision: dict[str, Any], stage_record_path: Path) -> None:
    report = f"""# Stage044 - 外生数据源资格库存审计

- 记录时间：`{datetime.now().strftime('%Y-%m-%dT%H:%M')}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`

## 口径

- 只审计本地已存在外生缓存，不写交易规则。
- 检查日期覆盖、产品覆盖、是否覆盖 `2022-2023` 左尾窗口、是否已有 point-in-time 证明。
- 不改官方 C9、不连接 CTP、不调用订单 API。

## 来源汇总

{_md_table(summary)}

## 产品覆盖样例

{_md_table(product_coverage.sort_values(['source_name', 'product_code']).head(40))}

## 判断

- 可作为下一步研究候选但必须补 PIT 规则的历史源：`{decision['history_candidates_needing_pit']}`。
- 只能 forward monitor 或映射不足的来源：`{decision['blocked_or_forward_only_sources']}`。
- 当前没有任何来源可直接进入历史 selector；下一步若继续，应优先对 `warehouse_receipt` 和 `basis` 做 `T+1` 点时化与坏窗口覆盖归因。

## 输出

- summary：`{SUMMARY_PATH}`
- product_coverage：`{PRODUCT_COVERAGE_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
- stage_record：`{stage_record_path}`

## 反思

- 运行前过拟合反思：否。本阶段是数据资格审计，不根据收益挑规则。
- 运行后过拟合反思：否。没有把 backfilled 外生数据直接用于交易；若跳过 PIT 验证直接做历史 selector 就会过拟合/泄漏。
- 运行前继续价值反思：有。Stage043 后必须寻找真正能解释左尾的外生状态。
- 运行后继续价值反思：有，但只限 `basis/warehouse` 的点时化和覆盖归因；CFTC 需要跨市场映射，member rank 缺 2022，forward ledger 历史太短。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    stage_record_path.write_text(report, encoding="utf-8")


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    summary, product_coverage = _build_inventory()
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_coverage.to_csv(PRODUCT_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    history_candidates = summary[summary["readiness"].eq("history_candidate_needs_pit_validation")]["source_name"].tolist()
    blocked = summary[~summary["readiness"].eq("history_candidate_needs_pit_validation")]["source_name"].tolist()
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage044_external_inventory_found_basis_warehouse_need_pit_no_trade_rule",
        "history_candidates_needing_pit": history_candidates,
        "blocked_or_forward_only_sources": blocked,
        "strategy_changed": False,
        "true_engine": False,
        "ctp_connected": False,
        "order_api_called": False,
    }
    stage_record_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage044_external_source_inventory.md"
    decision["stage_record_path"] = str(stage_record_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, product_coverage, decision, stage_record_path)
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(main()), ensure_ascii=False, indent=2))
