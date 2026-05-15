from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage264_hot_product_gap_audit_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage264_hot_product_gap_audit"

TRADABLE_AUDIT_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_tradable_universe_audit_full_market_tradable_universe_v1.csv"
)
STRUCTURAL_AUDIT_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_structural_prefilter_audit_full_market_structural_prefilter_v1.csv"
)
STATIC18_PLUS_FU_UNIVERSE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv"
)
PRODUCTS_PATH: Path = OUTPUT_DIR / "tqsdk_all_futures_products_2010_2026_04.csv"

AUDIT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_audit_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

HOT_PRODUCTS: tuple[tuple[str, str, str], ...] = (
    ("ag.SHFE", "白银", "贵金属/工业属性"),
    ("sc.INE", "原油", "能源"),
    ("fu.SHFE", "燃料油", "能源"),
    ("TA.CZCE", "PTA", "能化/聚酯"),
    ("m.DCE", "豆粕", "油脂油料"),
    ("p.DCE", "棕榈油", "油脂油料"),
    ("y.DCE", "豆油", "油脂油料"),
    ("i.DCE", "铁矿石", "黑色原料"),
    ("v.DCE", "PVC", "能化/建材"),
    ("c.DCE", "玉米", "农产品"),
    ("ao.SHFE", "氧化铝", "有色/铝链"),
)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _one(df: pd.DataFrame, product: str) -> dict[str, Any]:
    if df.empty or "product_vt_symbol" not in df.columns:
        return {}
    rows = df[df["product_vt_symbol"].astype(str).eq(product)]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def _safe_float(value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pd.isna(result):
        return 0.0
    return result


def _safe_int(value: object) -> int:
    try:
        result = int(float(value))
    except (TypeError, ValueError):
        return 0
    return result


def _product_status(
    product: str,
    tradable_row: dict[str, Any],
    structural_row: dict[str, Any],
    official_products: set[str],
    all_products: set[str],
) -> str:
    if product in official_products:
        return "official_or_fu_baseline"
    if not tradable_row:
        return "missing_from_tqsdk_product_or_universe"
    if _safe_int(tradable_row.get("eligible", 0)) != 1:
        return f"data_or_executability_blocked:{tradable_row.get('exclude_reason', '')}"
    if structural_row and _safe_int(structural_row.get("structural_prefilter_kept", 0)) != 1:
        return f"structural_blocked:{structural_row.get('structural_prefilter_reject_reason', '')}"
    if product in all_products:
        return "eligible_for_add_one_test"
    return "unknown"


def _test_tier(status: str) -> str:
    if status == "official_or_fu_baseline":
        return "baseline_revalidation"
    if status.startswith("data_or_executability_blocked"):
        return "data_completion_first"
    if status.startswith("structural_blocked"):
        return "counterfactual_add_one_after_structural_review"
    if status == "eligible_for_add_one_test":
        return "direct_add_one_ready"
    return "universe_rebuild_first"


def build_audit() -> tuple[pd.DataFrame, dict[str, Any]]:
    tradable = _read_csv(TRADABLE_AUDIT_PATH)
    structural = _read_csv(STRUCTURAL_AUDIT_PATH)
    official = _read_csv(STATIC18_PLUS_FU_UNIVERSE_PATH)
    products = _read_csv(PRODUCTS_PATH)

    official_products = set(official["product_vt_symbol"].dropna().astype(str))
    all_products = set(products["product_vt"].dropna().astype(str))

    rows: list[dict[str, Any]] = []
    for product, chinese_name, sector in HOT_PRODUCTS:
        tradable_row = _one(tradable, product)
        structural_row = _one(structural, product)
        status = _product_status(product, tradable_row, structural_row, official_products, all_products)
        rows.append(
            {
                "product_vt_symbol": product,
                "chinese_name": chinese_name,
                "sector": sector,
                "in_tqsdk_products": int(product in all_products),
                "in_stage78_static18_plus_fu": int(product in official_products),
                "tradable_universe_eligible": _safe_int(tradable_row.get("eligible", 0)),
                "tradable_exclude_reason": str(tradable_row.get("exclude_reason", "")),
                "structural_prefilter_kept": _safe_int(structural_row.get("structural_prefilter_kept", 0)),
                "structural_reject_reason": str(structural_row.get("structural_prefilter_reject_reason", "")),
                "mapping_days": _safe_int(tradable_row.get("mapping_days", 0)),
                "latest_mapping_date": str(tradable_row.get("latest_mapping_date", "")),
                "recent_bar_coverage_ratio": _safe_float(tradable_row.get("recent_bar_coverage_ratio", 0.0)),
                "recent_nonzero_volume_ratio": _safe_float(tradable_row.get("recent_nonzero_volume_ratio", 0.0)),
                "recent_median_volume": _safe_float(tradable_row.get("recent_median_volume", 0.0)),
                "estimated_margin_per_contract": _safe_float(tradable_row.get("estimated_margin_per_contract", 0.0)),
                "status": status,
                "test_tier": _test_tier(status),
            }
        )

    audit = pd.DataFrame(rows)
    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "target_products": [product for product, _, _ in HOT_PRODUCTS],
        "coverage": {
            "targets": int(len(audit)),
            "in_stage78_static18_plus_fu": int(audit["in_stage78_static18_plus_fu"].sum()),
            "tradable_universe_eligible": int(audit["tradable_universe_eligible"].sum()),
            "structural_prefilter_kept": int(audit["structural_prefilter_kept"].sum()),
            "data_completion_first": int(audit["test_tier"].eq("data_completion_first").sum()),
            "direct_or_counterfactual_ready": int(
                audit["test_tier"].isin(
                    ["direct_add_one_ready", "counterfactual_add_one_after_structural_review", "baseline_revalidation"]
                ).sum()
            ),
        },
        "status_counts": audit["status"].value_counts().to_dict(),
        "tier_counts": audit["test_tier"].value_counts().to_dict(),
        "artifacts": {
            "audit_csv": str(AUDIT_OUTPUT_PATH),
            "summary_json": str(SUMMARY_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
    }
    return audit, summary


def _table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_empty_"
    view = df.copy()
    float_columns = [
        "recent_bar_coverage_ratio",
        "recent_nonzero_volume_ratio",
        "recent_median_volume",
        "estimated_margin_per_contract",
    ]
    for column in float_columns:
        if column in view.columns:
            view[column] = view[column].map(lambda value: f"{float(value):.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(str(item) for item in row) + " |" for row in view.to_numpy()]
    return "\n".join([header, sep, *rows])


def build_report(audit: pd.DataFrame, summary: dict[str, Any]) -> str:
    columns = [
        "product_vt_symbol",
        "chinese_name",
        "sector",
        "in_stage78_static18_plus_fu",
        "tradable_universe_eligible",
        "structural_prefilter_kept",
        "recent_bar_coverage_ratio",
        "recent_nonzero_volume_ratio",
        "recent_median_volume",
        "estimated_margin_per_contract",
        "status",
        "test_tier",
    ]
    return "\n".join(
        [
            "# Stage264 Hot Product Gap Audit",
            "",
            "## Judgement",
            "",
            "- This is a universe-boundary and data-quality audit, not a return search.",
            "- All eleven hot missing/adjacent products stay in scope.",
            "- Products blocked by bar coverage must be fixed before add-one backtests; otherwise the result would mix strategy quality with data incompleteness.",
            "",
            "## Coverage",
            "",
            json.dumps(summary["coverage"], ensure_ascii=False, indent=2),
            "",
            "## Tier Counts",
            "",
            json.dumps(summary["tier_counts"], ensure_ascii=False, indent=2),
            "",
            "## Product Audit",
            "",
            _table(audit[columns]),
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audit, summary = build_audit()
    audit.to_csv(AUDIT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(build_report(audit, summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
