from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage452_iterative_1455_proxy_backfill as s452  # noqa: E402
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from main_contract_mapping import build_contract_metadata, build_daily_mapping, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_universe import END_DT, START_DT  # noqa: E402


MODEL_TAG = "stage454_preclose_signal_bar_data_readiness_v1"
OUTPUT_PREFIX = "qmt_roll_stage454_preclose_signal_bar_data_readiness"
LINE_ID = "futures_trend_drawdown30_preserve_return"

REQUIRED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_keys_{MODEL_TAG}.csv"
PRODUCT_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_coverage_{MODEL_TAG}.csv"
SYMBOL_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_symbol_coverage_{MODEL_TAG}.csv"
DOWNLOAD_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_plan_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _required_main_contract_keys() -> pd.DataFrame:
    overrides = _c3_overrides(START_DT)
    supported = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported)
    daily_mapping = build_daily_mapping(supported_symbols=supported)
    start = pd.Timestamp(START_DT).tz_localize(None).normalize()
    end = pd.Timestamp(END_DT).tz_localize(None).normalize()
    rows: list[dict[str, Any]] = []
    for date_text, mapping in daily_mapping.items():
        date = pd.Timestamp(date_text).normalize()
        if date < start or date > end:
            continue
        for product in metadata["product_symbols"]:
            vt_symbol = mapping.get(product, "")
            if not vt_symbol:
                continue
            rows.append({"date": date, "product_vt_symbol": product, "vt_symbol": vt_symbol})
    return pd.DataFrame(rows).drop_duplicates(["date", "product_vt_symbol", "vt_symbol"]).sort_values(
        ["date", "product_vt_symbol"]
    )


def _vt_symbol_from_raw_path(path: Path) -> str:
    exchange = path.parent.name
    symbol = path.name.replace("_minute_backtest.csv", "")
    return f"{symbol}.{exchange}"


def _covered_preclose_keys() -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for root in s452.RAW_ROOTS:
        if not root.exists():
            continue
        for path in root.glob("*/*_minute_backtest.csv"):
            vt_symbol = _vt_symbol_from_raw_path(path)
            try:
                for chunk in pd.read_csv(path, usecols=["bar_datetime"], chunksize=200_000, encoding="utf-8-sig"):
                    dt = pd.to_datetime(chunk["bar_datetime"], errors="coerce")
                    frame = pd.DataFrame({"bar_datetime": dt}).dropna()
                    if frame.empty:
                        continue
                    frame["date"] = frame["bar_datetime"].dt.normalize()
                    frame["time"] = frame["bar_datetime"].dt.strftime("%H:%M")
                    window = frame[(frame["time"] >= "14:55") & (frame["time"] < "15:00")]
                    if window.empty:
                        continue
                    part = window[["date"]].drop_duplicates().copy()
                    part["vt_symbol"] = vt_symbol
                    rows.append(part[["vt_symbol", "date"]])
            except ValueError:
                continue
    if not rows:
        return pd.DataFrame(columns=["vt_symbol", "date"])
    return pd.concat(rows, ignore_index=True).drop_duplicates(["vt_symbol", "date"]).sort_values(["vt_symbol", "date"])


def _coverage(required: pd.DataFrame, covered: pd.DataFrame) -> pd.DataFrame:
    marked = covered.copy()
    marked["has_preclose_1455_1500"] = 1
    result = required.merge(marked, on=["vt_symbol", "date"], how="left")
    result["has_preclose_1455_1500"] = result["has_preclose_1455_1500"].fillna(0).astype(int)
    return result


def _coverage_tables(required: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    product_coverage = (
        required.groupby("product_vt_symbol")
        .agg(
            required_keys=("has_preclose_1455_1500", "size"),
            covered_keys=("has_preclose_1455_1500", "sum"),
            missing_keys=("has_preclose_1455_1500", lambda s: int((s == 0).sum())),
        )
        .reset_index()
    )
    product_coverage["coverage_rate"] = product_coverage["covered_keys"] / product_coverage["required_keys"]
    product_coverage = product_coverage.sort_values(["coverage_rate", "required_keys"], ascending=[True, False])

    symbol = (
        required.groupby(["vt_symbol", "product_vt_symbol"])
        .agg(
            required_keys=("has_preclose_1455_1500", "size"),
            covered_keys=("has_preclose_1455_1500", "sum"),
            missing_keys=("has_preclose_1455_1500", lambda s: int((s == 0).sum())),
            first_date=("date", "min"),
            last_date=("date", "max"),
        )
        .reset_index()
    )
    symbol["coverage_rate"] = symbol["covered_keys"] / symbol["required_keys"]
    symbol = symbol.sort_values(["missing_keys", "coverage_rate"], ascending=[False, True])

    missing = required[required["has_preclose_1455_1500"].eq(0)].copy()
    plans: list[dict[str, Any]] = []
    for (vt_symbol, product_vt_symbol), frame in missing.groupby(["vt_symbol", "product_vt_symbol"], sort=False):
        dates = sorted(pd.Timestamp(date).normalize() for date in frame["date"].unique())
        if not dates:
            continue
        span_start = dates[0]
        previous = dates[0]
        span_dates = [dates[0]]
        for date in dates[1:]:
            if (date - previous).days > 14:
                plans.append(
                    {
                        "vt_symbol": vt_symbol,
                        "product_vt_symbol": product_vt_symbol,
                        "span_start": span_start,
                        "span_end": previous,
                        "missing_dates": len(span_dates),
                        "span_calendar_days": int((previous - span_start).days) + 1,
                    }
                )
                span_start = date
                span_dates = []
            span_dates.append(date)
            previous = date
        plans.append(
            {
                "vt_symbol": vt_symbol,
                "product_vt_symbol": product_vt_symbol,
                "span_start": span_start,
                "span_end": previous,
                "missing_dates": len(span_dates),
                "span_calendar_days": int((previous - span_start).days) + 1,
            }
        )
    plan = pd.DataFrame(plans).sort_values(["missing_dates", "span_calendar_days"], ascending=[False, False])
    return product_coverage, symbol, plan


def _write_report(summary: pd.DataFrame, product: pd.DataFrame, symbol: pd.DataFrame, plan: pd.DataFrame, decision: dict[str, Any]) -> None:
    report = [
        "# Stage154 预收盘一致信号bar数据覆盖审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：执行语义工程可行性审计；不新增策略、不修改 Stage079/C3 交易规则。",
        "- 审计对象：如果要用预收盘价格生成信号并同一窗口成交，至少需要每日主力合约 `14:55-15:00` 分钟窗口。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 必需主力合约日键：`{decision['required_key_count']}`。",
        f"- 已覆盖：`{decision['covered_key_count']}`。",
        f"- 缺口：`{decision['missing_key_count']}`。",
        f"- 覆盖率：`{decision['coverage_rate']:.4%}`。",
        "",
        "## 汇总",
        "",
        _md_table(summary),
        "",
        "## 覆盖率最低产品",
        "",
        _md_table(product.head(30)),
        "",
        "## 缺口最多合约",
        "",
        _md_table(symbol.head(40)),
        "",
        "## 下载计划Top40",
        "",
        _md_table(plan.head(40)),
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前过拟合反思：否。只统计执行数据覆盖，不看收益结果。",
        "- 运行后过拟合反思：否。本阶段没有生成候选曲线，也没有筛选日期/品种获利。",
        "- 运行前继续价值反思：是。Stage153 说明混合信号/成交时点不可靠，需要判断一致口径是否具备数据基础。",
        "- 运行后继续价值反思：是，但必须先补齐主力合约预收盘分钟窗口；当前覆盖率过低，直接回放会大量fallback并污染结论。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    assert_stage196_database_sentinels()
    required = _required_main_contract_keys()
    covered = _covered_preclose_keys()
    coverage = _coverage(required, covered)
    product, symbol, plan = _coverage_tables(coverage)
    total = int(len(coverage))
    covered_count = int(coverage["has_preclose_1455_1500"].sum())
    missing_count = int(total - covered_count)
    coverage_rate = float(covered_count / total) if total else 0.0
    summary = pd.DataFrame(
        [
            {
                "required_key_count": total,
                "covered_key_count": covered_count,
                "missing_key_count": missing_count,
                "coverage_rate": coverage_rate,
                "required_symbols": int(coverage["vt_symbol"].nunique()),
                "covered_symbols": int(coverage[coverage["has_preclose_1455_1500"].eq(1)]["vt_symbol"].nunique()),
                "missing_symbols": int(coverage[coverage["has_preclose_1455_1500"].eq(0)]["vt_symbol"].nunique()),
                "required_products": int(coverage["product_vt_symbol"].nunique()),
                "download_plan_spans": int(len(plan)),
                "download_plan_symbols": int(plan["vt_symbol"].nunique()) if not plan.empty else 0,
            }
        ]
    )
    decision_label = (
        "consistent_preclose_data_ready"
        if coverage_rate >= 0.995
        else "consistent_preclose_replay_data_not_ready_need_main_contract_window_backfill"
    )
    decision = {
        "stage": "Stage154",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "required_key_count": total,
        "covered_key_count": covered_count,
        "missing_key_count": missing_count,
        "coverage_rate": coverage_rate,
        "download_plan_span_count": int(len(plan)),
        "download_plan_symbol_count": int(plan["vt_symbol"].nunique()) if not plan.empty else 0,
        "outputs": {
            "required": str(REQUIRED_PATH),
            "summary": str(SUMMARY_PATH),
            "product_coverage": str(PRODUCT_COVERAGE_PATH),
            "symbol_coverage": str(SYMBOL_COVERAGE_PATH),
            "download_plan": str(DOWNLOAD_PLAN_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "先按download_plan补齐主力合约14:55-15:00分钟窗口，再做信号bar和成交价一致的预收盘口径真实回放。",
    }
    coverage.to_csv(REQUIRED_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    symbol.to_csv(SYMBOL_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    plan.to_csv(DOWNLOAD_PLAN_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, product, symbol, plan, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
