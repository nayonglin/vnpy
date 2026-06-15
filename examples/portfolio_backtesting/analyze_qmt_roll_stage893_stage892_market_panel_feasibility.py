from __future__ import annotations

from collections import defaultdict
from datetime import datetime
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
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DOWNLOADED_DIR = PROJECT_DIR / "downloaded_futures"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage893"
MODEL_TAG = "stage893_stage892_market_panel_feasibility_v1"
OUTPUT_PREFIX = "qmt_roll_stage893_stage892_market_panel_feasibility"
SOURCE_CANDIDATE = stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION

EARLY_BARS = 60
MIN_MARKET_SYMBOLS = 20
CHUNK_SIZE = 250_000

STAGE892_FEATURES_PATH = OUTPUT_DIR / (
    "qmt_roll_stage892_stage891_market_breadth_audit_features_"
    "stage892_stage891_market_breadth_audit_v1.csv"
)
STAGE892_MARKET_DAILY_PATH = OUTPUT_DIR / (
    "qmt_roll_stage892_stage891_market_breadth_audit_market_daily_"
    "stage892_stage891_market_breadth_audit_v1.csv"
)
STAGE861_FULL_MINUTE_BARS_PATH = OUTPUT_DIR / (
    "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_"
    "stage861_stage860_full_visual_atlas_v1.csv"
)

SOURCE_INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_inventory_{MODEL_TAG}.csv"
ENTRY_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_date_coverage_{MODEL_TAG}.csv"
DATE_SYMBOL_COUNTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_date_symbol_counts_{MODEL_TAG}.csv"
CANDIDATE_UNIVERSE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_universe_{MODEL_TAG}.csv"
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


def _infer_vt_symbol_from_path(path: Path) -> str:
    exchange = path.parent.name
    stem = path.stem
    stem = re.sub(r"_(?:completed_)?minute_backtest$", "", stem)
    stem = re.sub(r"_\d{8}$", "", stem)
    return f"{stem}.{exchange}"


def _product_from_symbol(vt_symbol: str) -> str:
    base = str(vt_symbol).split(".")[0]
    product = re.sub(r"\d+[A-Z]?$", "", base)
    exchange = str(vt_symbol).split(".")[-1] if "." in str(vt_symbol) else ""
    return f"{product}.{exchange}" if exchange else product


def _source_name(path: Path) -> str:
    try:
        return path.relative_to(DOWNLOADED_DIR).parts[0]
    except ValueError:
        return path.parent.name


def _minute_files() -> list[Path]:
    if not DOWNLOADED_DIR.exists():
        return []
    return sorted(
        path
        for path in DOWNLOADED_DIR.rglob("*.csv")
        if path.is_file()
        and (
            path.name.endswith("_minute_backtest.csv")
            or path.name.endswith("_completed_minute_backtest.csv")
        )
    )


def _daily_files() -> list[Path]:
    if not DOWNLOADED_DIR.exists():
        return []
    return sorted(
        path
        for path in DOWNLOADED_DIR.rglob("*.csv")
        if path.is_file()
        and "minute_backtest" not in path.name
        and not path.name.startswith("_")
    )


def _load_entry_dates() -> tuple[pd.DataFrame, list[str]]:
    features = _load_required_csv(STAGE892_FEATURES_PATH)
    features["entry_date_str"] = _normalise_date_series(features["entry_date"])
    features = features.dropna(subset=["entry_date_str"]).copy()
    dates = sorted(features["entry_date_str"].unique().tolist())
    return features, dates


def _build_stage861_counts(entry_dates: set[str]) -> pd.DataFrame:
    data = _load_required_csv(STAGE861_FULL_MINUTE_BARS_PATH)
    data["bar_date_str"] = _normalise_date_series(data["bar_date"])
    data = data[data["bar_date_str"].isin(entry_dates)].copy()
    if data.empty:
        return pd.DataFrame(columns=["source_name", "bar_date", "vt_symbol", "bar_rows"])
    counts = (
        data.groupby(["bar_date_str", "vt_symbol"], dropna=False)
        .size()
        .reset_index(name="bar_rows")
    )
    counts = counts[counts["bar_rows"].ge(EARLY_BARS)].copy()
    counts.insert(0, "source_name", "stage861_event_panel")
    counts = counts.rename(columns={"bar_date_str": "bar_date"})
    return counts[["source_name", "bar_date", "vt_symbol", "bar_rows"]].reset_index(drop=True)


def _read_downloaded_minute_counts(paths: list[Path], entry_dates: set[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        inferred_symbol = _infer_vt_symbol_from_path(path)
        source = _source_name(path)
        try:
            header = pd.read_csv(path, encoding="utf-8-sig", nrows=0)
        except Exception as exc:  # noqa: BLE001 - inventory should preserve unreadable files.
            rows.append(
                {
                    "source_name": source,
                    "bar_date": "",
                    "vt_symbol": inferred_symbol,
                    "bar_rows": 0,
                    "read_error": str(exc),
                    "file_path": str(path),
                }
            )
            continue

        columns = list(header.columns)
        date_col = "bar_date" if "bar_date" in columns else "bar_datetime" if "bar_datetime" in columns else ""
        if not date_col:
            continue
        usecols = [date_col]
        if "vt_symbol" in columns:
            usecols.append("vt_symbol")

        counts: defaultdict[tuple[str, str], int] = defaultdict(int)
        try:
            reader = pd.read_csv(path, encoding="utf-8-sig", usecols=usecols, chunksize=CHUNK_SIZE)
            for chunk in reader:
                dates = _normalise_date_series(chunk[date_col])
                mask = dates.isin(entry_dates)
                if not mask.any():
                    continue
                relevant = pd.DataFrame({"bar_date": dates[mask]})
                if "vt_symbol" in chunk.columns:
                    relevant["vt_symbol"] = chunk.loc[mask, "vt_symbol"].astype(str).values
                else:
                    relevant["vt_symbol"] = inferred_symbol
                grouped = relevant.groupby(["bar_date", "vt_symbol"], dropna=False).size()
                for key, value in grouped.items():
                    counts[(str(key[0]), str(key[1]))] += int(value)
        except Exception as exc:  # noqa: BLE001 - inventory should preserve unreadable files.
            rows.append(
                {
                    "source_name": source,
                    "bar_date": "",
                    "vt_symbol": inferred_symbol,
                    "bar_rows": 0,
                    "read_error": str(exc),
                    "file_path": str(path),
                }
            )
            continue

        for (bar_date, vt_symbol), bar_rows in counts.items():
            if bar_rows >= EARLY_BARS:
                rows.append(
                    {
                        "source_name": source,
                        "bar_date": bar_date,
                        "vt_symbol": vt_symbol,
                        "bar_rows": int(bar_rows),
                        "read_error": "",
                        "file_path": str(path),
                    }
                )
    if not rows:
        return pd.DataFrame(columns=["source_name", "bar_date", "vt_symbol", "bar_rows", "read_error", "file_path"])
    return pd.DataFrame(rows)


def _build_candidate_universe() -> pd.DataFrame:
    universe_path, eligibility_path = stage819_cfg.build_official_candidate_stage819_30w_paths()
    rows: list[dict[str, Any]] = []
    if universe_path.exists():
        universe = pd.read_csv(universe_path, encoding="utf-8-sig")
        for _, row in universe.iterrows():
            symbol = ""
            for column in ["vt_symbol", "product_vt_symbol", "symbol", "product"]:
                if column in universe.columns and pd.notna(row.get(column)):
                    symbol = str(row[column])
                    break
            rows.append(
                {
                    "source_file": str(universe_path),
                    "source_kind": "official_candidate_product_universe",
                    "vt_symbol": symbol,
                    "product": _product_from_symbol(symbol) if symbol else "",
                }
            )
    if eligibility_path.exists():
        eligibility = pd.read_csv(eligibility_path, encoding="utf-8-sig")
        if "product_vt_symbol" in eligibility.columns:
            products = sorted(eligibility["product_vt_symbol"].dropna().astype(str).unique().tolist())
            for product in products:
                rows.append(
                    {
                        "source_file": str(eligibility_path),
                        "source_kind": "official_candidate_ai_eligibility_products",
                        "vt_symbol": product,
                        "product": _product_from_symbol(product),
                    }
                )
    if not rows:
        return pd.DataFrame(columns=["source_file", "source_kind", "vt_symbol", "product"])
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def _summarise_inventory(
    minute_paths: list[Path],
    daily_paths: list[Path],
    downloaded_counts: pd.DataFrame,
    stage861_counts: pd.DataFrame,
    entry_dates: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    minute_file_by_source: defaultdict[str, int] = defaultdict(int)
    for path in minute_paths:
        minute_file_by_source[_source_name(path)] += 1
    daily_file_by_source: defaultdict[str, int] = defaultdict(int)
    for path in daily_paths:
        daily_file_by_source[_source_name(path)] += 1

    sources = sorted(set(minute_file_by_source) | set(daily_file_by_source))
    for source in sources:
        source_counts = downloaded_counts[downloaded_counts["source_name"].eq(source)].copy()
        nonempty = source_counts[source_counts["bar_date"].astype(str).ne("")]
        rows.append(
            {
                "source_name": source,
                "source_kind": "downloaded_minute" if minute_file_by_source[source] else "downloaded_daily_only",
                "minute_files": int(minute_file_by_source[source]),
                "daily_files": int(daily_file_by_source[source]),
                "usable_date_symbol_pairs_on_c9_entry_dates": int(len(nonempty)),
                "unique_symbols_on_c9_entry_dates": int(nonempty["vt_symbol"].nunique()) if not nonempty.empty else 0,
                "entry_dates_covered": int(nonempty["bar_date"].nunique()) if not nonempty.empty else 0,
                "min_bar_date": str(nonempty["bar_date"].min()) if not nonempty.empty else "",
                "max_bar_date": str(nonempty["bar_date"].max()) if not nonempty.empty else "",
                "max_symbols_on_one_entry_date": int(nonempty.groupby("bar_date")["vt_symbol"].nunique().max())
                if not nonempty.empty
                else 0,
                "entry_date_coverage_pct": float(nonempty["bar_date"].nunique() / len(entry_dates) * 100.0)
                if entry_dates
                else 0.0,
            }
        )

    rows.append(
        {
            "source_name": "stage861_event_panel",
            "source_kind": "backtest_output_event_panel",
            "minute_files": 1,
            "daily_files": 0,
            "usable_date_symbol_pairs_on_c9_entry_dates": int(len(stage861_counts)),
            "unique_symbols_on_c9_entry_dates": int(stage861_counts["vt_symbol"].nunique()) if not stage861_counts.empty else 0,
            "entry_dates_covered": int(stage861_counts["bar_date"].nunique()) if not stage861_counts.empty else 0,
            "min_bar_date": str(stage861_counts["bar_date"].min()) if not stage861_counts.empty else "",
            "max_bar_date": str(stage861_counts["bar_date"].max()) if not stage861_counts.empty else "",
            "max_symbols_on_one_entry_date": int(stage861_counts.groupby("bar_date")["vt_symbol"].nunique().max())
            if not stage861_counts.empty
            else 0,
            "entry_date_coverage_pct": float(stage861_counts["bar_date"].nunique() / len(entry_dates) * 100.0)
            if entry_dates
            else 0.0,
        }
    )

    return pd.DataFrame(rows).sort_values(
        ["source_kind", "usable_date_symbol_pairs_on_c9_entry_dates", "minute_files"],
        ascending=[True, False, False],
    )


def _symbols_by_date(counts: pd.DataFrame, source_filter: str | None = None) -> dict[str, set[str]]:
    if source_filter is not None:
        counts = counts[counts["source_name"].eq(source_filter)].copy()
    result: dict[str, set[str]] = {}
    for bar_date, group in counts.groupby("bar_date", dropna=False):
        if str(bar_date):
            result[str(bar_date)] = set(group["vt_symbol"].dropna().astype(str))
    return result


def _build_entry_coverage(
    features: pd.DataFrame,
    stage861_counts: pd.DataFrame,
    downloaded_counts: pd.DataFrame,
    entry_dates: list[str],
) -> pd.DataFrame:
    stage861_map = _symbols_by_date(stage861_counts)
    downloaded_map = _symbols_by_date(downloaded_counts[downloaded_counts["bar_date"].astype(str).ne("")])
    stage859_map = _symbols_by_date(downloaded_counts, "tqsdk_stage859_stage856_remaining_gap_backfill")
    lot_counts = features.groupby("entry_date_str", dropna=False).size().to_dict()
    products = (
        features.groupby("entry_date_str")["product"]
        .apply(lambda x: ",".join(sorted(set(x.dropna().astype(str)))))
        .to_dict()
        if "product" in features.columns
        else {}
    )
    rows: list[dict[str, Any]] = []
    for entry_date in entry_dates:
        s861 = stage861_map.get(entry_date, set())
        downloaded = downloaded_map.get(entry_date, set())
        s859 = stage859_map.get(entry_date, set())
        combined = s861 | downloaded
        rows.append(
            {
                "entry_date": entry_date,
                "c9_lots": int(lot_counts.get(entry_date, 0)),
                "products_on_entry_date": products.get(entry_date, ""),
                "stage861_event_symbols": int(len(s861)),
                "stage859_gap_symbols": int(len(s859)),
                "downloaded_local_minute_symbols": int(len(downloaded)),
                "combined_local_symbols": int(len(combined)),
                "meets_20_stage861": bool(len(s861) >= MIN_MARKET_SYMBOLS),
                "meets_20_downloaded": bool(len(downloaded) >= MIN_MARKET_SYMBOLS),
                "meets_20_combined": bool(len(combined) >= MIN_MARKET_SYMBOLS),
                "combined_symbol_sample": ",".join(sorted(combined)[:8]),
            }
        )
    return pd.DataFrame(rows)


def _coverage_summary(coverage: pd.DataFrame, column: str) -> dict[str, Any]:
    values = pd.to_numeric(coverage[column], errors="coerce").fillna(0.0)
    return {
        "min": float(values.min()) if len(values) else 0.0,
        "p25": float(values.quantile(0.25)) if len(values) else 0.0,
        "median": float(values.median()) if len(values) else 0.0,
        "p75": float(values.quantile(0.75)) if len(values) else 0.0,
        "max": float(values.max()) if len(values) else 0.0,
        "meets_20_dates": int(values.ge(MIN_MARKET_SYMBOLS).sum()),
        "total_dates": int(len(values)),
        "meets_20_pct": float(values.ge(MIN_MARKET_SYMBOLS).mean() * 100.0) if len(values) else 0.0,
    }


def _plot_summary(coverage: pd.DataFrame, inventory: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), dpi=180, constrained_layout=True)

    coverage_sorted = coverage.sort_values("combined_local_symbols").reset_index(drop=True)
    axes[0].plot(coverage_sorted.index + 1, coverage_sorted["stage861_event_symbols"], label="Stage861 event panel", lw=1.6)
    axes[0].plot(
        coverage_sorted.index + 1,
        coverage_sorted["downloaded_local_minute_symbols"],
        label="Downloaded local minute union",
        lw=1.6,
    )
    axes[0].plot(
        coverage_sorted.index + 1,
        coverage_sorted["combined_local_symbols"],
        label="Combined local symbols",
        lw=2.0,
        color="#111827",
    )
    axes[0].axhline(MIN_MARKET_SYMBOLS, color="#dc2626", linestyle="--", lw=1.2, label="min required=20")
    axes[0].set_title("C9 entry-date local minute symbol coverage")
    axes[0].set_xlabel("Entry dates sorted by combined local symbols")
    axes[0].set_ylabel("Symbols with >=60 bars")
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].grid(alpha=0.25)

    axes[1].hist(coverage["combined_local_symbols"], bins=20, color="#2563eb", alpha=0.78)
    axes[1].axvline(MIN_MARKET_SYMBOLS, color="#dc2626", linestyle="--", lw=1.2)
    axes[1].set_title("Distribution of combined local minute symbols per C9 entry date")
    axes[1].set_xlabel("Combined local symbols")
    axes[1].set_ylabel("Entry dates")
    axes[1].grid(alpha=0.25)

    inv = inventory.sort_values("usable_date_symbol_pairs_on_c9_entry_dates", ascending=False).head(10)
    labels = inv["source_name"].astype(str).str.replace("tqsdk_", "", regex=False)
    axes[2].barh(labels, inv["usable_date_symbol_pairs_on_c9_entry_dates"], color="#059669", alpha=0.8)
    axes[2].set_title("Local downloaded sources: usable date-symbol pairs on C9 entry dates")
    axes[2].set_xlabel("Date-symbol pairs")
    axes[2].invert_yaxis()
    axes[2].grid(axis="x", alpha=0.25)

    fig.savefig(path)
    plt.close(fig)


def _write_report(
    features: pd.DataFrame,
    inventory: pd.DataFrame,
    coverage: pd.DataFrame,
    candidate_universe: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_rows = [
        {
            "coverage_source": "stage861_event_symbols",
            **_coverage_summary(coverage, "stage861_event_symbols"),
        },
        {
            "coverage_source": "downloaded_local_minute_symbols",
            **_coverage_summary(coverage, "downloaded_local_minute_symbols"),
        },
        {
            "coverage_source": "combined_local_symbols",
            **_coverage_summary(coverage, "combined_local_symbols"),
        },
    ]
    summary = pd.DataFrame(summary_rows)
    worst = coverage.sort_values(["combined_local_symbols", "entry_date"]).head(15)
    best = coverage.sort_values(["combined_local_symbols", "entry_date"], ascending=[False, True]).head(15)
    inv_view = inventory.sort_values(
        ["usable_date_symbol_pairs_on_c9_entry_dates", "minute_files"], ascending=[False, False]
    ).head(15)

    lines = [
        "# Stage893 Stage892 Market Panel Feasibility",
        "",
        f"- stage: `{STAGE}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- line_id: `{LINE_ID}`",
        f"- source_candidate: `{SOURCE_CANDIDATE}`",
        f"- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- c9_closed_lots: `{len(features)}`",
        f"- unique_entry_dates: `{coverage['entry_date'].nunique()}`",
        f"- min_market_symbols_required: `{MIN_MARKET_SYMBOLS}`",
        f"- early_bars_required_per_symbol: `{EARLY_BARS}`",
        "",
        "## External Research Boundary",
        "",
        "- TqSdk `DataDownloader` is the right external shape for historical CSV download across a symbol list and explicit start/end windows.",
        "- TqSdk `get_kline_serial` is limited to a serial K-line window and is better treated as subscription/recent-sequence plumbing than a full offline panel builder.",
        "- vn.py supports historical data storage/import/export workflows, but Stage893 intentionally does not import new data or touch the local database.",
        "- Judgment: a market-breadth rule should not be written until the local data first proves same-day broad minute coverage across C9 entry dates.",
        "",
        "## Coverage Summary",
        "",
        _md_table(summary),
        "",
        "## Source Inventory",
        "",
        _md_table(inv_view),
        "",
        "## Worst Entry-Date Coverage",
        "",
        _md_table(
            worst[
                [
                    "entry_date",
                    "c9_lots",
                    "products_on_entry_date",
                    "stage861_event_symbols",
                    "downloaded_local_minute_symbols",
                    "combined_local_symbols",
                    "meets_20_combined",
                    "combined_symbol_sample",
                ]
            ]
        ),
        "",
        "## Best Entry-Date Coverage",
        "",
        _md_table(
            best[
                [
                    "entry_date",
                    "c9_lots",
                    "products_on_entry_date",
                    "stage861_event_symbols",
                    "downloaded_local_minute_symbols",
                    "combined_local_symbols",
                    "meets_20_combined",
                    "combined_symbol_sample",
                ]
            ]
        ),
        "",
        "## Candidate Universe Hint",
        "",
        f"- candidate_universe_rows: `{len(candidate_universe)}`",
        f"- candidate_universe_products: `{candidate_universe['product'].nunique() if not candidate_universe.empty else 0}`",
        "- This is only a universe hint; it is not minute coverage proof.",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- local_panel_feasible: `{decision['local_panel_feasible']}`",
        f"- readonly: `{decision['guardrails']['readonly']}`",
        f"- no_downloads: `{decision['guardrails']['no_downloads']}`",
        f"- no_ctp: `{decision['guardrails']['no_ctp']}`",
        f"- no_order_api: `{decision['guardrails']['no_order_api']}`",
        f"- no_ab_trigger: `{decision['guardrails']['no_ab_trigger']}`",
        "",
        "## Conclusion",
        "",
        "- Stage893 is a data-panel feasibility audit, not an alpha or backtest stage.",
        "- If combined local coverage does not meet 20 symbols on every C9 entry date, current local files are not enough to build a robust market-breadth minute rule.",
        "- Do not lower the 20-symbol requirement to rescue the idea; that would convert a breadth concept into a thin sample artifact.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    features, entry_dates = _load_entry_dates()
    entry_date_set = set(entry_dates)
    minute_paths = _minute_files()
    daily_paths = _daily_files()

    stage861_counts = _build_stage861_counts(entry_date_set)
    downloaded_counts = _read_downloaded_minute_counts(minute_paths, entry_date_set)
    date_symbol_counts = pd.concat([stage861_counts, downloaded_counts], ignore_index=True, sort=False)
    inventory = _summarise_inventory(minute_paths, daily_paths, downloaded_counts, stage861_counts, entry_dates)
    coverage = _build_entry_coverage(features, stage861_counts, downloaded_counts, entry_dates)
    candidate_universe = _build_candidate_universe()

    source_summaries = {
        "stage861_event_symbols": _coverage_summary(coverage, "stage861_event_symbols"),
        "downloaded_local_minute_symbols": _coverage_summary(coverage, "downloaded_local_minute_symbols"),
        "combined_local_symbols": _coverage_summary(coverage, "combined_local_symbols"),
    }
    local_panel_feasible = bool(coverage["meets_20_combined"].all()) if not coverage.empty else False
    decision_name = (
        "stage893_local_market_panel_feasible_needs_clean_roll_mapping"
        if local_panel_feasible
        else "stage893_local_market_panel_not_available_no_breadth_engine"
    )
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "source_candidate": SOURCE_CANDIDATE,
        "decision": decision_name,
        "local_panel_feasible": local_panel_feasible,
        "min_market_symbols_required": MIN_MARKET_SYMBOLS,
        "early_bars_required_per_symbol": EARLY_BARS,
        "metrics": {
            "c9_closed_lots": int(len(features)),
            "unique_entry_dates": int(len(entry_dates)),
            "downloaded_minute_files_scanned": int(len(minute_paths)),
            "downloaded_daily_files_found_not_used_for_minute_panel": int(len(daily_paths)),
            "candidate_universe_rows": int(len(candidate_universe)),
            "candidate_universe_products": int(candidate_universe["product"].nunique())
            if not candidate_universe.empty
            else 0,
            "source_summaries": source_summaries,
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
            "source_inventory": str(SOURCE_INVENTORY_PATH),
            "entry_date_coverage": str(ENTRY_COVERAGE_PATH),
            "date_symbol_counts": str(DATE_SYMBOL_COUNTS_PATH),
            "candidate_universe": str(CANDIDATE_UNIVERSE_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }

    inventory.to_csv(SOURCE_INVENTORY_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(ENTRY_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    date_symbol_counts.to_csv(DATE_SYMBOL_COUNTS_PATH, index=False, encoding="utf-8-sig")
    candidate_universe.to_csv(CANDIDATE_UNIVERSE_PATH, index=False, encoding="utf-8-sig")
    _plot_summary(coverage, inventory, SUMMARY_CHART_PATH)
    _write_report(features, inventory, coverage, candidate_universe, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
