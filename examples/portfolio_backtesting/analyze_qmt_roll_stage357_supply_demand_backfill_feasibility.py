from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage316_supply_demand_quality_probe as stage316
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


MODEL_TAG = "stage357_supply_demand_backfill_feasibility_v1"
OUTPUT_PREFIX = "qmt_roll_stage357_supply_demand_backfill_feasibility"
LINE_ID = "futures_trend_drawdown30_preserve_return"

OUTPUT_SUMMARY_CSV: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
OUTPUT_JSON: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
OUTPUT_REPORT: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

TEST_DAYS: tuple[str, ...] = (
    "20200102",
    "20200601",
    "20210104",
    "20210512",
    "20210702",
    "20220309",
    "20221207",
    "20221230",
)

WAREHOUSE_SOURCES: tuple[tuple[str, str, Any], ...] = (
    ("shfe", "futures_shfe_warehouse_receipt", stage316._parse_shfe_warehouse),
    ("czce", "futures_warehouse_receipt_czce", stage316._parse_czce_warehouse),
    ("gfex", "futures_gfex_warehouse_receipt", stage316._parse_gfex_warehouse),
)


def _basis_probe(day: str) -> dict[str, Any]:
    try:
        data = stage316._run_akshare_source("futures_spot_price", day, sorted(stage316.PRODUCTS_BY_CODE))
    except Exception as exc:  # pragma: no cover - external source instability
        return {
            "day": day,
            "source": "basis",
            "status": "error",
            "rows": 0,
            "product_count": 0,
            "products": "",
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:300],
        }
    if not isinstance(data, pd.DataFrame) or data.empty:
        return {
            "day": day,
            "source": "basis",
            "status": "empty",
            "rows": 0,
            "product_count": 0,
            "products": "",
            "error_type": "",
            "error_message": "",
        }
    frame = data.copy()
    if "symbol" in frame.columns:
        frame["product_code"] = frame["symbol"].astype(str).str.upper()
        products = sorted(set(frame["product_code"]) & set(stage316.PRODUCTS_BY_CODE))
    else:
        products = []
    return {
        "day": day,
        "source": "basis",
        "status": "ok",
        "rows": int(len(frame)),
        "product_count": int(len(products)),
        "products": ",".join(products),
        "error_type": "",
        "error_message": "",
    }


def _warehouse_probe(day: str, exchange: str, function_name: str, parser: Any) -> dict[str, Any]:
    try:
        data = stage316._run_akshare_source(function_name, day)
        rows = parser(day, data) if data is not None else []
    except Exception as exc:  # pragma: no cover - external source instability
        return {
            "day": day,
            "source": f"warehouse_{exchange}",
            "status": "error",
            "rows": 0,
            "product_count": 0,
            "products": "",
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:300],
        }
    products = sorted({str(row.get("product_code", "")).upper() for row in rows if row.get("product_code")})
    return {
        "day": day,
        "source": f"warehouse_{exchange}",
        "status": "ok" if rows else "empty",
        "rows": int(len(rows)),
        "product_count": int(len(products)),
        "products": ",".join(products),
        "error_type": "",
        "error_message": "",
    }


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    basis = summary[summary["source"].eq("basis")]
    warehouse = summary[summary["source"].str.startswith("warehouse_")]
    basis_ok_days = int(basis["status"].eq("ok").sum())
    warehouse_ok_days = int(warehouse["status"].eq("ok").groupby(summary.loc[warehouse.index, "day"]).any().sum())
    warehouse_exchange_ok_days = (
        warehouse.assign(ok=warehouse["status"].eq("ok"))
        .groupby("source", as_index=False)
        .agg(ok_days=("ok", "sum"), product_days=("product_count", "sum"))
        .to_dict("records")
    )
    total_days = len(TEST_DAYS)
    critical_days = {"20210512", "20210702", "20220309", "20221207"}
    critical = summary[summary["day"].isin(critical_days)]
    critical_basis_ok = int(critical[critical["source"].eq("basis")]["status"].eq("ok").sum())
    critical_warehouse_ok = int(
        critical[critical["source"].str.startswith("warehouse_")]
        .groupby("day")["status"]
        .apply(lambda item: item.eq("ok").any())
        .sum()
    )
    basis_can_backfill = basis_ok_days >= total_days - 1 and critical_basis_ok >= len(critical_days) - 1
    warehouse_has_some_history = warehouse_ok_days >= total_days - 1 and critical_warehouse_ok >= len(critical_days) - 1
    all_warehouse_sources_complete = all(int(item["ok_days"]) >= total_days - 1 for item in warehouse_exchange_ok_days)
    can_backfill = (
        basis_ok_days >= total_days - 1
        and warehouse_ok_days >= total_days - 1
        and critical_basis_ok >= len(critical_days) - 1
        and critical_warehouse_ok >= len(critical_days) - 1
    )
    if basis_can_backfill and warehouse_has_some_history and not all_warehouse_sources_complete:
        decision = "sample_supports_basis_backfill_but_warehouse_exchange_gaps"
    elif can_backfill:
        decision = "sample_supports_full_backfill"
    else:
        decision = "sample_backfill_needs_source_fallbacks"
    return {
        "decision": decision,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "test_days": list(TEST_DAYS),
        "basis_ok_days": basis_ok_days,
        "warehouse_ok_days": warehouse_ok_days,
        "warehouse_exchange_ok_days": warehouse_exchange_ok_days,
        "critical_basis_ok": critical_basis_ok,
        "critical_warehouse_ok": critical_warehouse_ok,
        "basis_can_backfill": bool(basis_can_backfill),
        "warehouse_has_some_history": bool(warehouse_has_some_history),
        "all_warehouse_sources_complete": bool(all_warehouse_sources_complete),
        "can_run_full_backfill_next": bool(can_backfill),
    }


def _build_report(summary: pd.DataFrame, decision: dict[str, Any]) -> str:
    display = summary.copy()
    display["error_message"] = display["error_message"].fillna("").astype(str).str.slice(0, 120)
    lines = [
        "# Stage357 供需数据2020-2022补齐可得性探针",
        "",
        "## 定位",
        "",
        "- 本阶段不修改 C3 策略规则，不调供需公式，不调阈值。",
        "- 只抽查 2020-2022 关键交易日，确认 Stage316 使用的 AKShare 基差和仓单接口是否可用于历史补齐。",
        "- 若抽样失败，下一步先补数据源 fallback；若抽样通过，再跑全量 2020-2022 raw cache 和点时化重建。",
        "",
        "## 抽样日期",
        "",
        ", ".join(TEST_DAYS),
        "",
        "## 数据源返回摘要",
        "",
        to_markdown_table(display),
        "",
        "## 判定",
        "",
        f"- `{decision['decision']}`",
        f"- basis ok days：`{decision['basis_ok_days']}/{len(TEST_DAYS)}`",
        f"- warehouse ok days：`{decision['warehouse_ok_days']}/{len(TEST_DAYS)}`",
        f"- critical basis ok：`{decision['critical_basis_ok']}/4`",
        f"- critical warehouse ok：`{decision['critical_warehouse_ok']}/4`",
        f"- warehouse exchange completeness：`{decision['warehouse_exchange_ok_days']}`",
        f"- all warehouse sources complete：`{decision['all_warehouse_sources_complete']}`",
        "",
        "## 反思",
        "",
        "- 是否过拟合：否。这里只验证数据可得性，不改变模型规则和阈值。",
        "- 是否继续有价值：有。只有确认 2020-2022 数据可得，才能判断 C3 的 2021 回撤是否缺少供需视角。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for day in TEST_DAYS:
        print(f"[stage357] basis {day}", flush=True)
        rows.append(_basis_probe(day))
        for exchange, function_name, parser in WAREHOUSE_SOURCES:
            print(f"[stage357] warehouse {exchange} {day}", flush=True)
            rows.append(_warehouse_probe(day, exchange, function_name, parser))

    summary = pd.DataFrame(rows)
    decision = _decision(summary)
    summary.to_csv(OUTPUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    OUTPUT_JSON.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_REPORT.write_text(_build_report(summary, decision), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
