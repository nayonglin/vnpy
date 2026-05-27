from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage316_supply_demand_quality_probe as stage316
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage374_supply_demand_2015_2019_coverage_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage374_supply_demand_2015_2019_coverage_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

START_DAY = "20150101"
END_DAY = "20191231"

SAMPLE_OUTPUT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_samples_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUTPUT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _calendar_days() -> pd.Series:
    from akshare.futures import cons

    calendar = pd.Series(cons.get_calendar()).astype(str).str.replace("-", "", regex=False)
    days = calendar[(calendar >= START_DAY) & (calendar <= END_DAY)]
    return days.drop_duplicates().sort_values().reset_index(drop=True)


def _quarter_start_samples() -> list[str]:
    days = pd.DataFrame({"day": _calendar_days()})
    days["date"] = pd.to_datetime(days["day"], format="%Y%m%d")
    days["year"] = days["date"].dt.year
    days["quarter"] = days["date"].dt.quarter
    samples = days.groupby(["year", "quarter"], as_index=False).first()["day"].tolist()
    return [str(day) for day in samples]


def _safe_call(function_name: str, day: str, *args: Any) -> tuple[Any | None, str, str]:
    try:
        data = stage316._run_akshare_source(function_name, day, *args)
    except Exception as exc:  # pragma: no cover - external source instability
        return None, "error", f"{type(exc).__name__}: {str(exc)[:180]}"
    if data is None:
        return data, "empty", ""
    if isinstance(data, pd.DataFrame) and data.empty:
        return data, "empty", ""
    if isinstance(data, dict) and not any(isinstance(v, pd.DataFrame) and not v.empty for v in data.values()):
        return data, "empty", ""
    return data, "ok", ""


def _count_basis(day: str) -> dict[str, Any]:
    data, status, error = _safe_call("futures_spot_price", day, sorted(stage316.PRODUCTS_BY_CODE))
    if not isinstance(data, pd.DataFrame) or data.empty:
        return {"basis_status": status, "basis_rows": 0, "basis_products": "", "basis_error": error}
    frame = data.copy()
    if "symbol" not in frame.columns:
        return {"basis_status": "error", "basis_rows": 0, "basis_products": "", "basis_error": "missing_symbol_column"}
    products = sorted(set(frame["symbol"].astype(str).str.upper()) & set(stage316.PRODUCTS_BY_CODE))
    return {
        "basis_status": "ok" if products else "empty",
        "basis_rows": int(len(frame)),
        "basis_products": ",".join(products),
        "basis_product_count": int(len(products)),
        "basis_error": "",
    }


def _count_warehouse(day: str, exchange: str, function_name: str, parser: Any | None) -> dict[str, Any]:
    data, status, error = _safe_call(function_name, day)
    prefix = f"{exchange}_warehouse"
    if status != "ok":
        return {
            f"{prefix}_status": status,
            f"{prefix}_rows": 0,
            f"{prefix}_products": "",
            f"{prefix}_product_count": 0,
            f"{prefix}_error": error,
        }

    rows: list[dict[str, Any]] = []
    parse_error = ""
    if parser is not None:
        try:
            rows = parser(day, data)
        except Exception as exc:  # pragma: no cover - parser should stay defensive
            parse_error = f"{type(exc).__name__}: {str(exc)[:180]}"

    if parser is None and isinstance(data, pd.DataFrame):
        products: list[str] = []
        for column in data.columns:
            if str(column).lower() in {"品种", "variety", "product", "symbol"}:
                products = sorted(set(data[column].astype(str).str.upper()))
                break
        return {
            f"{prefix}_status": "ok" if not data.empty else "empty",
            f"{prefix}_rows": int(len(data)),
            f"{prefix}_products": ",".join(products),
            f"{prefix}_product_count": int(len(products)),
            f"{prefix}_error": "",
        }

    products = sorted({str(row.get("product_code", "")).upper() for row in rows if row.get("product_code")})
    parsed_status = "ok" if rows else "empty"
    if parse_error:
        parsed_status = "error"
    return {
        f"{prefix}_status": parsed_status,
        f"{prefix}_rows": int(len(rows)),
        f"{prefix}_products": ",".join(products),
        f"{prefix}_product_count": int(len(products)),
        f"{prefix}_error": parse_error,
    }


def _sample_rows() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for day in _quarter_start_samples():
        row: dict[str, Any] = {"day": day}
        row.update(_count_basis(day))
        row.update(
            _count_warehouse(day, "shfe", "futures_shfe_warehouse_receipt", stage316._parse_shfe_warehouse)
        )
        row.update(
            _count_warehouse(day, "czce", "futures_warehouse_receipt_czce", stage316._parse_czce_warehouse)
        )
        row.update(_count_warehouse(day, "dce", "futures_warehouse_receipt_dce", None))
        row.update(
            _count_warehouse(day, "gfex", "futures_gfex_warehouse_receipt", stage316._parse_gfex_warehouse)
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _summary(samples: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source, status_col, count_col in [
        ("basis", "basis_status", "basis_product_count"),
        ("shfe_warehouse", "shfe_warehouse_status", "shfe_warehouse_product_count"),
        ("czce_warehouse", "czce_warehouse_status", "czce_warehouse_product_count"),
        ("dce_warehouse", "dce_warehouse_status", "dce_warehouse_product_count"),
        ("gfex_warehouse", "gfex_warehouse_status", "gfex_warehouse_product_count"),
    ]:
        statuses = Counter(samples[status_col].fillna("missing"))
        rows.append(
            {
                "source": source,
                "sample_days": int(len(samples)),
                "ok_days": int(statuses.get("ok", 0)),
                "empty_days": int(statuses.get("empty", 0)),
                "error_days": int(statuses.get("error", 0)),
                "avg_product_count": float(pd.to_numeric(samples[count_col], errors="coerce").fillna(0).mean()),
            }
        )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    by_source = {str(row["source"]): row for row in summary.to_dict("records")}
    basis_ok = int(by_source["basis"]["ok_days"])
    czce_ok = int(by_source["czce_warehouse"]["ok_days"])
    shfe_ok = int(by_source["shfe_warehouse"]["ok_days"])
    dce_ok = int(by_source["dce_warehouse"]["ok_days"])

    if basis_ok >= 18 and czce_ok >= 12 and shfe_ok == 0:
        label = "basis_and_czce_backfillable_but_shfe_dce_warehouse_gaps"
    elif basis_ok >= 18:
        label = "basis_backfillable_warehouse_gaps_require_manual_review"
    else:
        label = "insufficient_2015_2019_supply_demand_source_coverage"

    return {
        "decision": label,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "start_day": START_DAY,
        "end_day": END_DAY,
        "sample_days": int(by_source["basis"]["sample_days"]),
        "basis_ok_days": basis_ok,
        "czce_warehouse_ok_days": czce_ok,
        "shfe_warehouse_ok_days": shfe_ok,
        "dce_warehouse_ok_days": dce_ok,
        "gfex_is_not_expected_for_2015_2019": True,
        "strategy_change_allowed": False,
        "recommended_next_step": "full_backfill_2015_2019_coverage_first_no_strategy_merge",
    }


def _report(samples: pd.DataFrame, summary: pd.DataFrame, decision: dict[str, Any]) -> str:
    lines = [
        "# Stage374 2015-2019供需数据覆盖审计",
        "",
        "## 定位",
        "",
        "- 本阶段只审计 2015-2019 供需数据源覆盖，不生成交易信号，不运行回测。",
        "- 目的不是救供需强逆风过滤，而是判断 2015 起长期报告是否应补齐解释层数据。",
        "",
        "## 抽样方法",
        "",
        "- 抽样范围：2015-01-01 到 2019-12-31。",
        "- 抽样规则：每年每季度首个交易日。",
        "- 数据源：AKShare 基差、SHFE/CZCE/DCE/GFEX 仓单接口。",
        "",
        "## 覆盖摘要",
        "",
        to_markdown_table(summary),
        "",
        "## 抽样明细",
        "",
        to_markdown_table(samples),
        "",
        "## 判定",
        "",
        f"- `{decision['decision']}`",
        "",
        "## 解释",
        "",
        "- 基差覆盖若稳定，可补齐 2015-2019 的供需解释层。",
        "- SHFE/DCE 仓单缺口会影响黑色链和上期所品种的三组件完整性，不能假设这些年份存在完整供需信号。",
        "- 因为 Stage059 已反证供需强逆风直套路线，本阶段不允许触发阈值、有效期或组件权重调参。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = _sample_rows()
    summary = _summary(samples)
    decision = _decision(summary)

    samples.to_csv(SAMPLE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    DECISION_OUTPUT_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(_report(samples, summary, decision), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
