from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DAILY_DIR = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage895"
MODEL_TAG = "stage895_stage894_market_panel_manifest_v1"
OUTPUT_PREFIX = "qmt_roll_stage895_stage894_market_panel_manifest"
SOURCE_CANDIDATE = "official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"

COMMODITY_EXCHANGES = {"SHFE", "DCE", "CZCE", "INE", "GFEX"}
MIN_MARKET_PRODUCTS = 20
TARGET_PRODUCTS = 25
FETCH_START_PREV_NIGHT = "20:55:00"
FETCH_END_DAY = "15:15:00"

STAGE892_FEATURES_PATH = OUTPUT_DIR / (
    "qmt_roll_stage892_stage891_market_breadth_audit_features_"
    "stage892_stage891_market_breadth_audit_v1.csv"
)
STAGE893_ENTRY_COVERAGE_PATH = OUTPUT_DIR / (
    "qmt_roll_stage893_stage892_market_panel_feasibility_entry_date_coverage_"
    "stage893_stage892_market_panel_feasibility_v1.csv"
)
STAGE893_DATE_SYMBOL_COUNTS_PATH = OUTPUT_DIR / (
    "qmt_roll_stage893_stage892_market_panel_feasibility_date_symbol_counts_"
    "stage893_stage892_market_panel_feasibility_v1.csv"
)

DAILY_PANEL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_panel_{MODEL_TAG}.csv"
ENTRY_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_date_panel_coverage_{MODEL_TAG}.csv"
DOWNLOAD_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_download_manifest_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalise_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d")


def _product_from_symbol(symbol: str) -> str:
    base = str(symbol).split(".")[0]
    return re.sub(r"\d+[A-Z]?$", "", base)


def _infer_contract(path: Path) -> dict[str, str]:
    exchange = path.parent.name
    symbol = path.stem
    product = _product_from_symbol(symbol)
    return {
        "exchange": exchange,
        "symbol": symbol,
        "vt_symbol": f"{symbol}.{exchange}",
        "tq_symbol": f"{exchange}.{symbol}",
        "product": product,
        "product_vt_symbol": f"{product}.{exchange}",
    }


def _daily_files() -> list[Path]:
    if not DAILY_DIR.exists():
        return []
    return sorted(
        path
        for path in DAILY_DIR.rglob("*.csv")
        if path.is_file() and not path.name.startswith("_") and path.parent.name in COMMODITY_EXCHANGES
    )


def _load_entry_dates() -> tuple[pd.DataFrame, list[str]]:
    features = _load_required_csv(STAGE892_FEATURES_PATH)
    features["entry_date_str"] = _normalise_date_series(features["entry_date"])
    features = features.dropna(subset=["entry_date_str"]).copy()
    return features, sorted(features["entry_date_str"].unique().tolist())


def _load_existing_minute_pairs() -> set[tuple[str, str]]:
    counts = _load_required_csv(STAGE893_DATE_SYMBOL_COUNTS_PATH)
    if counts.empty:
        return set()
    counts["bar_date"] = counts["bar_date"].astype(str)
    counts["vt_symbol"] = counts["vt_symbol"].astype(str)
    counts = counts[counts["bar_date"].ne("") & counts["vt_symbol"].ne("")]
    return set(zip(counts["bar_date"], counts["vt_symbol"], strict=False))


def _build_daily_panel(entry_dates: set[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    usecols = ["trade_date", "close", "volume", "open_oi", "close_oi"]
    for path in _daily_files():
        info = _infer_contract(path)
        try:
            data = pd.read_csv(path, encoding="utf-8-sig", usecols=usecols)
        except ValueError:
            continue
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    **info,
                    "trade_date": "",
                    "close": np.nan,
                    "volume": np.nan,
                    "open_oi": np.nan,
                    "close_oi": np.nan,
                    "read_error": str(exc),
                }
            )
            continue
        data["trade_date"] = _normalise_date_series(data["trade_date"])
        data = data[data["trade_date"].isin(entry_dates)].copy()
        if data.empty:
            continue
        for column in ["close", "volume", "open_oi", "close_oi"]:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        data = data[data["close"].gt(0) & (data["volume"].gt(0) | data["close_oi"].gt(0))].copy()
        if data.empty:
            continue
        data["liquidity_score"] = data["volume"] + data["close_oi"] * 0.05
        data["read_error"] = ""
        for row in data.to_dict("records"):
            rows.append({**info, **row})
    if not rows:
        return pd.DataFrame(
            columns=[
                "trade_date",
                "exchange",
                "symbol",
                "vt_symbol",
                "tq_symbol",
                "product",
                "product_vt_symbol",
                "close",
                "volume",
                "open_oi",
                "close_oi",
                "liquidity_score",
                "read_error",
            ]
        )
    panel = pd.DataFrame(rows)
    panel = panel[panel["trade_date"].astype(str).ne("")].copy()
    return panel.reset_index(drop=True)


def _select_product_panel(panel: pd.DataFrame, existing_pairs: set[tuple[str, str]]) -> pd.DataFrame:
    if panel.empty:
        return panel
    sorted_panel = panel.sort_values(
        ["trade_date", "product_vt_symbol", "liquidity_score", "volume", "close_oi"],
        ascending=[True, True, False, False, False],
    )
    product_best = sorted_panel.groupby(["trade_date", "product_vt_symbol"], dropna=False).head(1).copy()
    product_best = product_best.sort_values(
        ["trade_date", "liquidity_score", "volume", "close_oi"], ascending=[True, False, False, False]
    )
    product_best["product_rank"] = product_best.groupby("trade_date").cumcount() + 1
    product_best["selected_for_panel"] = product_best["product_rank"].le(TARGET_PRODUCTS)
    product_best["already_has_local_minute"] = [
        (str(row.trade_date), str(row.vt_symbol)) in existing_pairs for row in product_best.itertuples()
    ]
    product_best["needs_minute_download"] = product_best["selected_for_panel"] & ~product_best[
        "already_has_local_minute"
    ]
    return product_best.reset_index(drop=True)


def _build_coverage(selected: pd.DataFrame, features: pd.DataFrame, stage893_coverage: pd.DataFrame) -> pd.DataFrame:
    lots_by_date = features.groupby("entry_date_str", dropna=False).size().rename("c9_lots")
    product_list = features.groupby("entry_date_str")["product"].apply(
        lambda x: ",".join(sorted(set(x.dropna().astype(str))))
    )
    selected_only = selected[selected["selected_for_panel"]].copy()
    grouped = selected_only.groupby("trade_date", dropna=False).agg(
        theoretical_selected_symbols=("vt_symbol", "nunique"),
        theoretical_selected_products=("product_vt_symbol", "nunique"),
        selected_already_local_minute=("already_has_local_minute", "sum"),
        selected_needs_download=("needs_minute_download", "sum"),
        total_selected_volume=("volume", "sum"),
        median_selected_oi=("close_oi", "median"),
    )
    grouped = grouped.reset_index().rename(columns={"trade_date": "entry_date"})

    all_dates = pd.DataFrame({"entry_date": sorted(features["entry_date_str"].dropna().unique())})
    coverage = all_dates.merge(grouped, on="entry_date", how="left")
    coverage = coverage.merge(lots_by_date, left_on="entry_date", right_index=True, how="left")
    coverage = coverage.merge(product_list.rename("products_on_entry_date"), left_on="entry_date", right_index=True, how="left")
    for column in [
        "theoretical_selected_symbols",
        "theoretical_selected_products",
        "selected_already_local_minute",
        "selected_needs_download",
        "total_selected_volume",
        "median_selected_oi",
        "c9_lots",
    ]:
        coverage[column] = pd.to_numeric(coverage[column], errors="coerce").fillna(0)
    coverage["meets20_theoretical"] = coverage["theoretical_selected_products"].ge(MIN_MARKET_PRODUCTS)
    coverage["meets20_current_local_for_selected"] = coverage["selected_already_local_minute"].ge(MIN_MARKET_PRODUCTS)
    stage893 = stage893_coverage[
        ["entry_date", "combined_local_symbols", "meets_20_combined"]
    ].copy()
    coverage = coverage.merge(stage893, on="entry_date", how="left")
    coverage["combined_local_symbols"] = pd.to_numeric(coverage["combined_local_symbols"], errors="coerce").fillna(0)
    coverage["meets_20_combined"] = coverage["meets_20_combined"].fillna(False).astype(bool)
    top_symbols = (
        selected_only.groupby("trade_date")["vt_symbol"]
        .apply(lambda x: ",".join(list(x.astype(str))[:8]))
        .rename("selected_symbol_sample")
    )
    coverage = coverage.merge(top_symbols, left_on="entry_date", right_index=True, how="left")
    coverage["selected_symbol_sample"] = coverage["selected_symbol_sample"].fillna("")
    return coverage.reset_index(drop=True)


def _build_manifest(selected: pd.DataFrame) -> pd.DataFrame:
    data = selected[selected["selected_for_panel"]].copy()
    if data.empty:
        return pd.DataFrame()
    starts = pd.to_datetime(data["trade_date"], errors="coerce") - pd.Timedelta(days=1)
    ends = pd.to_datetime(data["trade_date"], errors="coerce")
    data["fetch_start"] = starts.dt.strftime("%Y-%m-%d") + f" {FETCH_START_PREV_NIGHT}"
    data["fetch_end"] = ends.dt.strftime("%Y-%m-%d") + f" {FETCH_END_DAY}"
    data["required_intraday_bars"] = 60
    data["session_policy"] = "previous_night_2055_to_entry_date_1515_then_normalize_trade_date"
    data["planned_source"] = "tqsdk_DataDownloader_or_equivalent_csv_import"
    data["download_priority"] = np.where(data["needs_minute_download"], "missing_minute_required", "already_local_minute")
    columns = [
        "trade_date",
        "product_rank",
        "exchange",
        "symbol",
        "vt_symbol",
        "tq_symbol",
        "product_vt_symbol",
        "close",
        "volume",
        "close_oi",
        "liquidity_score",
        "already_has_local_minute",
        "needs_minute_download",
        "download_priority",
        "fetch_start",
        "fetch_end",
        "required_intraday_bars",
        "session_policy",
        "planned_source",
    ]
    return data[columns].sort_values(["trade_date", "product_rank"]).reset_index(drop=True)


def _build_product_summary(manifest: pd.DataFrame) -> pd.DataFrame:
    if manifest.empty:
        return pd.DataFrame()
    summary = manifest.groupby("product_vt_symbol", dropna=False).agg(
        selected_dates=("trade_date", "nunique"),
        missing_minute_dates=("needs_minute_download", "sum"),
        median_rank=("product_rank", "median"),
        mean_volume=("volume", "mean"),
        median_oi=("close_oi", "median"),
    )
    summary = summary.reset_index().sort_values(["selected_dates", "median_rank"], ascending=[False, True])
    return summary


def _coverage_stats(coverage: pd.DataFrame) -> dict[str, Any]:
    return {
        "entry_dates": int(len(coverage)),
        "theoretical_meets20_dates": int(coverage["meets20_theoretical"].sum()),
        "theoretical_meets20_pct": float(coverage["meets20_theoretical"].mean() * 100.0) if len(coverage) else 0.0,
        "current_selected_local_meets20_dates": int(coverage["meets20_current_local_for_selected"].sum()),
        "current_selected_local_meets20_pct": float(coverage["meets20_current_local_for_selected"].mean() * 100.0)
        if len(coverage)
        else 0.0,
        "median_theoretical_products": float(coverage["theoretical_selected_products"].median()) if len(coverage) else 0.0,
        "min_theoretical_products": float(coverage["theoretical_selected_products"].min()) if len(coverage) else 0.0,
        "max_theoretical_products": float(coverage["theoretical_selected_products"].max()) if len(coverage) else 0.0,
        "median_required_downloads": float(coverage["selected_needs_download"].median()) if len(coverage) else 0.0,
        "total_required_manifest_rows": int(coverage["selected_needs_download"].sum()) if len(coverage) else 0,
    }


def _plot_summary(coverage: pd.DataFrame, product_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), dpi=180, constrained_layout=True)
    ordered = coverage.sort_values("entry_date").reset_index(drop=True)
    x = np.arange(len(ordered))
    axes[0].plot(x, ordered["theoretical_selected_products"], label="Daily theoretical products", lw=1.8)
    axes[0].plot(x, ordered["selected_already_local_minute"], label="Selected already local minute", lw=1.2)
    axes[0].plot(x, ordered["combined_local_symbols"], label="Stage893 local union", lw=1.2)
    axes[0].axhline(MIN_MARKET_PRODUCTS, color="#dc2626", ls="--", lw=1.1, label="min required=20")
    axes[0].set_title("C9 entry-date theoretical market panel coverage from daily data")
    axes[0].set_ylabel("Symbols/products")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25)

    axes[1].hist(coverage["selected_needs_download"], bins=20, color="#2563eb", alpha=0.78)
    axes[1].set_title("Required missing minute downloads per entry date for selected panel")
    axes[1].set_xlabel("Missing selected minute symbols")
    axes[1].set_ylabel("Entry dates")
    axes[1].grid(alpha=0.25)

    top_products = product_summary.head(20).sort_values("selected_dates", ascending=True)
    axes[2].barh(top_products["product_vt_symbol"], top_products["selected_dates"], color="#059669", alpha=0.82)
    axes[2].set_title("Most frequently selected products for market panel manifest")
    axes[2].set_xlabel("Selected entry dates")
    axes[2].grid(axis="x", alpha=0.25)
    fig.savefig(SUMMARY_CHART_PATH)
    plt.close(fig)


def _write_report(
    coverage: pd.DataFrame,
    manifest: pd.DataFrame,
    product_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    stats = decision["metrics"]["coverage_stats"]
    worst = coverage.sort_values(["theoretical_selected_products", "entry_date"]).head(15)
    most_missing = coverage.sort_values(["selected_needs_download", "entry_date"], ascending=[False, True]).head(15)
    top_products = product_summary.head(20)
    lines = [
        "# Stage895 Stage894 Market Panel Manifest",
        "",
        f"- stage: `{STAGE}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- line_id: `{LINE_ID}`",
        f"- source_candidate: `{SOURCE_CANDIDATE}`",
        f"- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- daily_files_scanned: `{decision['metrics']['daily_files_scanned']}`",
        f"- manifest_rows: `{len(manifest)}`",
        "",
        "## External Research Boundary",
        "",
        "- TqSdk `DataDownloader` or equivalent CSV download is the intended way to materialize the selected minute panel.",
        "- vn.py can store/import historical bars, but Stage895 does not import to database and does not run a strategy.",
        "- Judgment: the daily data is used only to define a broad, predeclared market panel; it is not a trading signal yet.",
        "",
        "## Coverage Summary",
        "",
        _md_table(pd.DataFrame([stats])),
        "",
        "## Worst Theoretical Coverage Dates",
        "",
        _md_table(
            worst[
                [
                    "entry_date",
                    "c9_lots",
                    "products_on_entry_date",
                    "theoretical_selected_products",
                    "selected_already_local_minute",
                    "selected_needs_download",
                    "combined_local_symbols",
                    "selected_symbol_sample",
                ]
            ]
        ),
        "",
        "## Highest Missing-Minute Dates",
        "",
        _md_table(
            most_missing[
                [
                    "entry_date",
                    "c9_lots",
                    "products_on_entry_date",
                    "theoretical_selected_products",
                    "selected_needs_download",
                    "selected_symbol_sample",
                ]
            ]
        ),
        "",
        "## Top Selected Products",
        "",
        _md_table(top_products),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- theoretical_panel_defined: `{decision['theoretical_panel_defined']}`",
        f"- minute_panel_materialized: `{decision['minute_panel_materialized']}`",
        f"- no_downloads: `{decision['guardrails']['no_downloads']}`",
        f"- no_strategy_rule_added: `{decision['guardrails']['no_strategy_rule_added']}`",
        "",
        "## Conclusion",
        "",
        "- Stage895 converts the Stage893 data gap into a concrete minute-panel manifest.",
        "- If theoretical coverage meets 20 products on most/all C9 entry dates, the next blocker is minute data materialization, not panel design.",
        "- No market-breadth rule can be written until the selected minute manifest is actually downloaded/imported and re-audited.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features, entry_dates = _load_entry_dates()
    stage893_coverage = _load_required_csv(STAGE893_ENTRY_COVERAGE_PATH)
    existing_pairs = _load_existing_minute_pairs()
    panel = _build_daily_panel(set(entry_dates))
    selected = _select_product_panel(panel, existing_pairs)
    coverage = _build_coverage(selected, features, stage893_coverage)
    manifest = _build_manifest(selected)
    product_summary = _build_product_summary(manifest)
    _plot_summary(coverage, product_summary)

    stats = _coverage_stats(coverage)
    theoretical_panel_defined = stats["theoretical_meets20_dates"] == stats["entry_dates"] and stats["entry_dates"] > 0
    decision_name = (
        "stage895_daily_universe_defines_full_market_panel_manifest_minute_download_required"
        if theoretical_panel_defined
        else "stage895_daily_universe_incomplete_panel_manifest_needs_data_review"
    )
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "source_candidate": SOURCE_CANDIDATE,
        "decision": decision_name,
        "theoretical_panel_defined": bool(theoretical_panel_defined),
        "minute_panel_materialized": False,
        "min_market_products": MIN_MARKET_PRODUCTS,
        "target_products": TARGET_PRODUCTS,
        "metrics": {
            "daily_files_scanned": int(len(_daily_files())),
            "daily_panel_rows": int(len(panel)),
            "selected_panel_rows": int(len(manifest)),
            "selected_products": int(product_summary["product_vt_symbol"].nunique()) if not product_summary.empty else 0,
            "coverage_stats": stats,
        },
        "guardrails": {
            "readonly": True,
            "no_downloads": True,
            "no_ctp": True,
            "no_order_api": True,
            "no_strategy_rule_added": True,
            "no_backtest": True,
            "no_ab_trigger": True,
            "official_stage372_changed": False,
            "official_candidate_config_changed": False,
        },
        "outputs": {
            "daily_panel": str(DAILY_PANEL_PATH),
            "entry_coverage": str(ENTRY_COVERAGE_PATH),
            "download_manifest": str(DOWNLOAD_MANIFEST_PATH),
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }

    panel.to_csv(DAILY_PANEL_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(ENTRY_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    manifest.to_csv(DOWNLOAD_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _write_report(coverage, manifest, product_summary, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
