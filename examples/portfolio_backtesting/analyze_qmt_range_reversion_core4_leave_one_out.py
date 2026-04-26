from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_range_reversion_core4_directed_backtest import CORE_UNIVERSE_PATH, run_backtest


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
MODEL_TAG: str = "range_reversion_core4_leave_one_out_v1"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_leave_one_out_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_leave_one_out_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_leave_one_out_report_{MODEL_TAG}.md"


def _variant_slug(product_vt_symbol: str) -> str:
    return product_vt_symbol.replace(".", "_").lower()


def _write_variant_universe(source: pd.DataFrame, variant_name: str, excluded_product: str | None) -> Path:
    if excluded_product:
        frame = source[source["product_vt_symbol"].astype(str) != excluded_product].copy()
    else:
        frame = source.copy()
    if frame.empty:
        raise ValueError(f"empty leave-one-out universe: {variant_name}")
    path = OUTPUT_DIR / f"qmt_range_reversion_core4_leave_one_out_universe_{variant_name}.csv"
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _summary_row(
    *,
    variant_name: str,
    excluded_product: str,
    product_universe_path: Path,
    products: list[str],
    statistics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "variant_name": variant_name,
        "excluded_product": excluded_product,
        "products": ",".join(products),
        "product_count": len(products),
        "product_universe_path": str(product_universe_path),
        "end_balance": float(statistics.get("end_balance", 0) or 0),
        "total_return_pct": float(statistics.get("total_return", 0) or 0),
        "max_ddpercent": float(statistics.get("max_ddpercent", 0) or 0),
        "sharpe_ratio": float(statistics.get("sharpe_ratio", 0) or 0),
        "return_drawdown_ratio": float(statistics.get("return_drawdown_ratio", 0) or 0),
        "total_slippage": float(statistics.get("total_slippage", 0) or 0),
        "total_trade_count": int(statistics.get("total_trade_count", 0) or 0),
        "round_trip_count": int(statistics.get("round_trip_count", 0) or 0),
        "win_ratio_pct": float(statistics.get("win_ratio", 0) or 0),
    }


def _write_report(summary: pd.DataFrame) -> None:
    ordered = summary.sort_values(["end_balance", "sharpe_ratio"], ascending=[False, False]).reset_index(drop=True)
    lines: list[str] = [
        "# QMT Range Reversion Core4 Leave-One-Out Attribution",
        "",
        "## 结论",
        "- 本报告只做产品归因，不是正式参数优化。",
        "- 所有版本使用v3结构：产品连续历史信号、方向约束、移除连亏熄火、`entry_tr_multiplier=0.8`。",
        "- 如果某个leave-one-out版本明显好于Core4，只代表该产品在当前执行规则下拖累，需要后续分段验证；不能直接作为正式剔除依据。",
        "",
        "## 结果排序",
        ordered[
            [
                "variant_name",
                "excluded_product",
                "product_count",
                "end_balance",
                "total_return_pct",
                "max_ddpercent",
                "sharpe_ratio",
                "total_slippage",
                "total_trade_count",
                "round_trip_count",
                "win_ratio_pct",
            ]
        ].to_markdown(index=False),
        "",
        "## 输出",
        f"- summary_csv: `{SUMMARY_CSV_PATH}`",
        f"- summary_json: `{SUMMARY_JSON_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(CORE_UNIVERSE_PATH)
    source = source[pd.to_numeric(source.get("eligible", 1), errors="coerce").fillna(1).astype(int) == 1].copy()
    products = source["product_vt_symbol"].dropna().astype(str).tolist()
    variants: list[tuple[str, str | None]] = [("core4_all", None)]
    variants.extend((f"without_{_variant_slug(product)}", product) for product in products)

    rows: list[dict[str, Any]] = []
    for variant_name, excluded_product in variants:
        universe_path = _write_variant_universe(source, variant_name, excluded_product)
        variant_products = pd.read_csv(universe_path)["product_vt_symbol"].dropna().astype(str).tolist()
        print(f"[leave-one-out] running {variant_name}: {','.join(variant_products)}")
        _, _, statistics = run_backtest(
            save_artifacts=False,
            file_prefix=f"qmt_range_reversion_core4_leave_one_out_{variant_name}",
            chart_title=f"QMT Range Reversion Core4 Leave One Out {variant_name}",
            strategy_tag=f"range_reversion_core4_leave_one_out_{variant_name}",
            product_universe_path=universe_path,
            setting_overrides={
                "range_use_product_continuous_signal": True,
                "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            },
        )
        rows.append(
            _summary_row(
                variant_name=variant_name,
                excluded_product=excluded_product or "",
                product_universe_path=universe_path,
                products=variant_products,
                statistics=statistics,
            )
        )

    summary = pd.DataFrame(rows)
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps({"model_tag": MODEL_TAG, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_report(summary)
    print(summary.to_string(index=False))
    print(f"summary_csv: {SUMMARY_CSV_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
