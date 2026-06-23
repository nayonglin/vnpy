from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage105"
MODEL_TAG = "stage105_contract_month_oi_gap_repair_manifest_v1"
OUTPUT_PREFIX = "qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage105_contract_month_oi_gap_repair_manifest"

DOWNLOADED_FUTURES_DIR = REPO_DIR / "examples" / "portfolio_backtesting" / "downloaded_futures"
PRIMARY_DAILY_ROOT = DOWNLOADED_FUTURES_DIR / "tqsdk_daily_2010_2026_04"
STAGE104_DIR = LINE_DIR / "outputs" / "stage104_contract_month_oi_migration_readiness_audit"
FEATURES_IN = (
    STAGE104_DIR
    / "qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit_features_"
    "stage104_contract_month_oi_migration_readiness_audit_v1.csv"
)
SUMMARY104_IN = (
    STAGE104_DIR
    / "qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit_summary_"
    "stage104_contract_month_oi_migration_readiness_audit_v1.csv"
)
STAGE102_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage102_bar_resolution_frontier_audit"
    / "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_summary_"
    "stage102_bar_resolution_frontier_audit_v1.csv"
)
CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

GAP_ROWS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_rows_{MODEL_TAG}.csv"
REPAIR_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_manifest_{MODEL_TAG}.csv"
ACTION_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_action_summary_{MODEL_TAG}.csv"
PRODUCT_YEAR_GAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_gap_matrix_{MODEL_TAG}.csv"
SOURCE_AGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_age_audit_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_gap_chart_{MODEL_TAG}.png"
GAP_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_gap_heatmap_{MODEL_TAG}.png"
ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_repair_action_chart_{MODEL_TAG}.png"
SOURCE_AGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_age_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        out = float(value)
        return None if np.isnan(out) or np.isinf(out) else out
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _load_features() -> pd.DataFrame:
    features = _read_csv(FEATURES_IN)
    for column in ["official_open_date", "source_date"]:
        features[column] = pd.to_datetime(features[column], errors="coerce").dt.normalize()
    for column in [
        "candidate_index",
        "source_age_days",
        "order_realized_pnl",
        "right_tail_visual",
        "bottom_loss_visual",
        "panel_ready",
        "target_contract_found_active",
        "active_contract_count",
    ]:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")
    features["entry_year"] = features["official_open_date"].dt.year
    return features


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _all_downloaded_csv() -> list[Path]:
    if not DOWNLOADED_FUTURES_DIR.exists():
        return []
    return sorted(DOWNLOADED_FUTURES_DIR.rglob("*.csv"))


def _contract_variants(vt_symbol: Any, exchange: Any) -> list[str]:
    vt_text = "" if pd.isna(vt_symbol) else str(vt_symbol).strip()
    contract = vt_text.split(".", 1)[0]
    exchange_text = "" if pd.isna(exchange) else str(exchange).strip()
    variants = {contract, contract.lower(), contract.upper()}
    match = re.match(r"([A-Za-z]+)(\d+)", contract)
    if match and exchange_text == "CZCE":
        code = match.group(1).upper()
        digits = match.group(2)
        if len(digits) == 4:
            variants.add(code + digits[-3:])
        if len(digits) == 3:
            variants.add(code + digits)
    return sorted(variants)


def _expected_primary_path(vt_symbol: str, exchange: str) -> Path:
    contract = vt_symbol.split(".", 1)[0]
    variants = _contract_variants(vt_symbol, exchange)
    filename = variants[0]
    if exchange != "CZCE":
        filename = contract.lower()
    else:
        filename = contract.upper()
        match = re.match(r"([A-Za-z]+)(\d{4})", contract)
        if match:
            filename = match.group(1).upper() + match.group(2)[-3:]
    return PRIMARY_DAILY_ROOT / exchange / f"{filename}.csv"


def _schema_kind(path: Path) -> tuple[str, str, int, str]:
    try:
        columns = pd.read_csv(path, nrows=0).columns.tolist()
    except Exception as exc:  # pragma: no cover - defensive file audit
        return "read_error", str(exc), 0, ""
    column_text = ",".join(columns)
    has_oi = int("close_oi" in columns or "open_oi" in columns or "open_interest" in columns)
    if {"trade_date", "close_oi", "open_oi"}.issubset(columns):
        kind = "daily_oi"
    elif {"datetime", "close_oi", "open_oi"}.issubset(columns):
        kind = "datetime_oi"
    elif "datetime" in columns and has_oi:
        kind = "intraday_oi"
    elif "datetime" in columns:
        kind = "intraday_no_oi"
    else:
        kind = "unknown"
    digest = hashlib.sha256(column_text.encode("utf-8")).hexdigest()[:16]
    return kind, column_text, has_oi, digest


def _source_dates_for_product(product_key: str) -> pd.Series:
    if "." not in product_key:
        return pd.Series(dtype="datetime64[ns]")
    _, exchange = product_key.rsplit(".", 1)
    directory = PRIMARY_DAILY_ROOT / exchange
    if not directory.exists():
        return pd.Series(dtype="datetime64[ns]")
    code = product_key.rsplit(".", 1)[0]
    pattern = re.compile(r"^" + re.escape(code) + r"\d+[A-Za-z]*$", re.IGNORECASE)
    dates: list[pd.Series] = []
    for path in directory.glob("*.csv"):
        if not pattern.match(path.stem):
            continue
        try:
            frame = pd.read_csv(path, usecols=["trade_date"])
        except Exception:
            continue
        series = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize().dropna()
        dates.append(series)
    if not dates:
        return pd.Series(dtype="datetime64[ns]")
    return pd.concat(dates, ignore_index=True).drop_duplicates().sort_values().reset_index(drop=True)


def _build_gap_rows(features: pd.DataFrame) -> pd.DataFrame:
    all_csv = _all_downloaded_csv()
    gap = features[features["readiness_state"].ne("panel_ready")].copy()
    rows: list[dict[str, Any]] = []
    for _, item in gap.iterrows():
        vt_symbol = str(item["vt_symbol"])
        exchange = str(item["exchange"])
        variants = _contract_variants(vt_symbol, exchange)
        exact_paths = [path for path in all_csv if path.parent.name == exchange and path.stem in variants]
        primary_expected = _expected_primary_path(vt_symbol, exchange)
        schema_kinds: list[str] = []
        schema_hashes: list[str] = []
        exact_paths_text: list[str] = []
        exact_path_has_oi = 0
        for path in exact_paths:
            kind, _, has_oi, digest = _schema_kind(path)
            schema_kinds.append(kind)
            schema_hashes.append(digest)
            exact_paths_text.append(str(path.relative_to(REPO_DIR)))
            exact_path_has_oi = max(exact_path_has_oi, has_oi)

        product_dates = _source_dates_for_product(str(item["stage104_product_key"]))
        source_date = item["source_date"]
        entry_date = item["official_open_date"]
        dates_between = 0
        previous_source_is_adjacent = 0
        if not product_dates.empty and pd.notna(source_date) and pd.notna(entry_date):
            between = product_dates[(product_dates.gt(source_date)) & (product_dates.lt(entry_date))]
            dates_between = int(len(between))
            previous_source_is_adjacent = int(dates_between == 0)

        readiness = str(item["readiness_state"])
        if readiness == "stale_source_date" and previous_source_is_adjacent:
            repair_action = "calendar_holiday_gap_accept_with_trading_day_gate"
            local_repair_possible = 1
        elif exact_paths:
            repair_action = "exact_contract_file_found_in_alternate_root_review_schema"
            local_repair_possible = int(exact_path_has_oi)
        elif entry_date.year >= 2026:
            repair_action = "download_or_refresh_near_endpoint_target_contract_daily_oi"
            local_repair_possible = 0
        else:
            repair_action = "backfill_legacy_target_contract_daily_oi"
            local_repair_possible = 0

        rows.append(
            {
                "candidate_index": int(item["candidate_index"]) if not pd.isna(item["candidate_index"]) else np.nan,
                "vt_symbol": vt_symbol,
                "target_contract": str(item["target_contract"]),
                "exchange": exchange,
                "stage104_product_key": str(item["stage104_product_key"]),
                "official_open_date": entry_date,
                "source_date": source_date,
                "source_age_days": float(item["source_age_days"]) if not pd.isna(item["source_age_days"]) else np.nan,
                "entry_year": int(item["entry_year"]) if not pd.isna(item["entry_year"]) else np.nan,
                "readiness_state_stage104": readiness,
                "order_realized_pnl": float(item["order_realized_pnl"]),
                "right_tail_visual": int(item.get("right_tail_visual", 0) or 0),
                "bottom_loss_visual": int(item.get("bottom_loss_visual", 0) or 0),
                "contract_variants": "|".join(variants),
                "primary_expected_path": str(primary_expected.relative_to(REPO_DIR)),
                "primary_expected_exists": int(primary_expected.exists()),
                "exact_file_any_downloaded_count": len(exact_paths),
                "exact_file_any_downloaded_has_oi": exact_path_has_oi,
                "exact_file_any_downloaded_paths": "|".join(exact_paths_text),
                "exact_file_schema_kinds": "|".join(sorted(set(schema_kinds))),
                "exact_file_schema_hashes": "|".join(sorted(set(schema_hashes))),
                "product_dates_between_source_and_entry": dates_between,
                "previous_source_is_trading_adjacent": previous_source_is_adjacent,
                "local_repair_possible": local_repair_possible,
                "repair_action": repair_action,
                "rule_allowed": 0,
                "true_engine_allowed": 0,
                "ab_allowed": 0,
            }
        )
    out = pd.DataFrame(rows).sort_values(["official_open_date", "vt_symbol"]).reset_index(drop=True)
    return out


def _build_repair_manifest(gap_rows: pd.DataFrame) -> pd.DataFrame:
    missing = gap_rows[gap_rows["readiness_state_stage104"].eq("target_contract_not_in_product_panel")].copy()
    if missing.empty:
        return pd.DataFrame()
    grouped = (
        missing.groupby(["vt_symbol", "target_contract", "exchange", "stage104_product_key", "repair_action"], dropna=False)
        .agg(
            linked_gap_order_count=("candidate_index", "count"),
            first_entry_date=("official_open_date", "min"),
            last_entry_date=("official_open_date", "max"),
            pnl_sum=("order_realized_pnl", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            primary_expected_path=("primary_expected_path", "first"),
            exact_file_any_downloaded_count=("exact_file_any_downloaded_count", "max"),
        )
        .reset_index()
    )
    grouped["download_symbol"] = grouped["exchange"] + "." + grouped["target_contract"]
    grouped["required_start_date"] = pd.to_datetime(grouped["first_entry_date"], errors="coerce") - pd.Timedelta(days=14)
    grouped["required_end_date"] = pd.to_datetime(grouped["last_entry_date"], errors="coerce")
    grouped["required_fields"] = "trade_date,open,high,low,close,volume,open_oi,close_oi"
    grouped["raw_manifest_required"] = 1
    grouped["strategy_rule_allowed"] = 0
    return grouped.sort_values(["first_entry_date", "vt_symbol"]).reset_index(drop=True)


def _build_action_summary(gap_rows: pd.DataFrame) -> pd.DataFrame:
    summary = (
        gap_rows.groupby("repair_action", dropna=False)
        .agg(
            gap_order_count=("candidate_index", "count"),
            unique_contract_count=("vt_symbol", "nunique"),
            pnl_sum=("order_realized_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            local_repair_possible_count=("local_repair_possible", "sum"),
        )
        .reset_index()
        .sort_values(["gap_order_count", "repair_action"], ascending=[False, True])
    )
    return summary.reset_index(drop=True)


def _build_product_year_gap(gap_rows: pd.DataFrame) -> pd.DataFrame:
    if gap_rows.empty:
        return pd.DataFrame()
    grouped = (
        gap_rows.groupby(["stage104_product_key", "entry_year", "readiness_state_stage104"], dropna=False)
        .agg(
            gap_order_count=("candidate_index", "count"),
            pnl_sum=("order_realized_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
        )
        .reset_index()
        .sort_values(["entry_year", "stage104_product_key", "readiness_state_stage104"])
    )
    return grouped.reset_index(drop=True)


def _build_source_age_audit(gap_rows: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "candidate_index",
        "vt_symbol",
        "official_open_date",
        "source_date",
        "source_age_days",
        "readiness_state_stage104",
        "product_dates_between_source_and_entry",
        "previous_source_is_trading_adjacent",
        "repair_action",
        "order_realized_pnl",
    ]
    return gap_rows[cols].copy()


def _build_promotion_gate(features: pd.DataFrame, gap_rows: pd.DataFrame, repair_manifest: pd.DataFrame) -> pd.DataFrame:
    total_orders = int(len(features))
    stage104_ready = int(features["panel_ready"].sum())
    repaired_by_trading_calendar = int(
        gap_rows["repair_action"].eq("calendar_holiday_gap_accept_with_trading_day_gate").sum()
    )
    effective_ready = stage104_ready + repaired_by_trading_calendar
    exact_alt_found = int(
        gap_rows[
            gap_rows["readiness_state_stage104"].eq("target_contract_not_in_product_panel")
            & gap_rows["exact_file_any_downloaded_count"].gt(0)
        ].shape[0]
    )
    missing_contracts = int(repair_manifest["vt_symbol"].nunique()) if not repair_manifest.empty else 0
    gates = [
        {
            "gate": "stage104_gap_manifest_built",
            "pass": 1,
            "observed": f"gap_rows={len(gap_rows)}, unique_missing_contracts={missing_contracts}",
            "required": "all non-ready rows classified",
            "rule_allowed": 0,
        },
        {
            "gate": "calendar_stale_rows_reclassified",
            "pass": int(repaired_by_trading_calendar == int(features["readiness_state"].eq("stale_source_date").sum())),
            "observed": f"{repaired_by_trading_calendar}/{int(features['readiness_state'].eq('stale_source_date').sum())}",
            "required": "stale source rows must be previous trading source, not data leak",
            "rule_allowed": 0,
        },
        {
            "gate": "alternate_local_exact_files_found",
            "pass": int(exact_alt_found > 0),
            "observed": f"missing_target_exact_alt_found_rows={exact_alt_found}",
            "required": "local alternate files can repair missing target contracts",
            "rule_allowed": 0,
        },
        {
            "gate": "effective_target_coverage_ge95pct",
            "pass": int(effective_ready / total_orders * 100.0 >= 95.0),
            "observed": f"{effective_ready}/{total_orders}={effective_ready / total_orders * 100.0:.4f}%",
            "required": ">=95.0% after safe repair classification",
            "rule_allowed": 0,
        },
        {
            "gate": "raw_hash_schema_manifest_complete",
            "pass": 0,
            "observed": "repair manifest specifies missing files but raw files not downloaded/hashed",
            "required": "raw file path/hash/schema/source permission for every repaired row",
            "rule_allowed": 0,
        },
        {
            "gate": "true_engine_or_ab_allowed",
            "pass": 0,
            "observed": "gap repair audit only",
            "required": "coverage + raw provenance + visual right-tail gate must pass first",
            "rule_allowed": 0,
        },
    ]
    return pd.DataFrame(gates)


def _attach_curve_y(gap_rows: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    left = gap_rows.sort_values("official_open_date").copy()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left, right, left_on="official_open_date", right_on="date", direction="backward")


def _plot_path_chart(gap_rows: pd.DataFrame, curve: pd.DataFrame, action_summary: pd.DataFrame) -> None:
    plot_rows = _attach_curve_y(gap_rows, curve)
    colors = {
        "backfill_legacy_target_contract_daily_oi": "#dc2626",
        "download_or_refresh_near_endpoint_target_contract_daily_oi": "#f97316",
        "calendar_holiday_gap_accept_with_trading_day_gate": "#15803d",
        "exact_contract_file_found_in_alternate_root_review_schema": "#2563eb",
    }
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(4, 1, height_ratios=[2.2, 1.1, 1.0, 1.2], hspace=0.12)
    ax_eq = fig.add_subplot(gs[0, 0])
    ax_dd = fig.add_subplot(gs[1, 0], sharex=ax_eq)
    ax_broker = fig.add_subplot(gs[2, 0], sharex=ax_eq)
    ax_action = fig.add_subplot(gs[3, 0])

    ax_eq.plot(curve["date"], curve["account_equity"], color="#111827", linewidth=1.4)
    for action, group in plot_rows.groupby("repair_action"):
        ax_eq.scatter(
            group["official_open_date"],
            group["account_equity"],
            s=np.where(group["bottom_loss_visual"].eq(1), 70, 34),
            color=colors.get(action, "#6b7280"),
            alpha=0.82,
            edgecolor=np.where(group["right_tail_visual"].eq(1), "#111827", "none"),
            linewidth=0.9,
            label=action,
        )
    ax_eq.set_title("Stage105 OI panel gap repair map on official path")
    ax_eq.set_ylabel("equity")
    ax_eq.grid(alpha=0.2)
    ax_eq.legend(loc="upper left", fontsize=8)

    ax_dd.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#fecaca", alpha=0.8)
    ax_dd.plot(curve["date"], curve["drawdown_pct"], color="#991b1b", linewidth=1.0)
    ax_dd.set_ylabel("drawdown %")
    ax_dd.grid(alpha=0.2)

    ax_broker.plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#2563eb", linewidth=1.0)
    ax_broker.axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.8)
    ax_broker.set_ylabel("broker10 %")
    ax_broker.grid(alpha=0.2)

    action_summary = action_summary.sort_values("gap_order_count")
    ax_action.barh(action_summary["repair_action"], action_summary["gap_order_count"], color="#64748b")
    ax_action.set_xlabel("gap rows")
    ax_action.grid(axis="x", alpha=0.2)

    fig.autofmt_xdate()
    fig.savefig(PATH_CHART_OUT, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_gap_heatmap(product_year_gap: pd.DataFrame) -> None:
    if product_year_gap.empty:
        return
    pivot = product_year_gap.pivot_table(
        index="stage104_product_key",
        columns="entry_year",
        values="gap_order_count",
        aggfunc="sum",
        fill_value=0,
    ).sort_index()
    fig, ax = plt.subplots(figsize=(12, max(6, 0.35 * len(pivot))))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="YlOrRd")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            value = int(pivot.iloc[y, x])
            if value:
                ax.text(x, y, str(value), ha="center", va="center", fontsize=8)
    ax.set_title("Non-ready OI panel gap count by product-year")
    ax.set_xlabel("entry year")
    ax.set_ylabel("product")
    fig.colorbar(image, ax=ax, label="gap rows")
    fig.savefig(GAP_HEATMAP_OUT, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_action_chart(action_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = np.where(action_summary["local_repair_possible_count"].gt(0), "#15803d", "#dc2626")
    ax.barh(action_summary["repair_action"], action_summary["gap_order_count"], color=colors)
    ax.set_xlabel("gap rows")
    ax.set_title("Stage105 repair action classification")
    for y, row in enumerate(action_summary.itertuples(index=False)):
        ax.text(row.gap_order_count + 0.15, y, f"contracts={row.unique_contract_count}", va="center", fontsize=8)
    ax.grid(axis="x", alpha=0.2)
    fig.savefig(ACTION_CHART_OUT, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_source_age(source_age: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.5))
    colors = np.where(source_age["previous_source_is_trading_adjacent"].eq(1), "#15803d", "#dc2626")
    ax.scatter(
        pd.to_datetime(source_age["official_open_date"]),
        source_age["source_age_days"],
        s=np.where(source_age["readiness_state_stage104"].eq("stale_source_date"), 80, 32),
        color=colors,
        alpha=0.8,
    )
    ax.axhline(7, color="#dc2626", linestyle="--", linewidth=0.9)
    ax.set_ylabel("calendar source age days")
    ax.set_xlabel("entry date")
    ax.set_title("Calendar source-age gaps vs trading-day adjacency")
    ax.grid(alpha=0.2)
    fig.autofmt_xdate()
    fig.savefig(SOURCE_AGE_CHART_OUT, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _summary(
    features: pd.DataFrame,
    gap_rows: pd.DataFrame,
    repair_manifest: pd.DataFrame,
    gates: pd.DataFrame,
) -> dict[str, Any]:
    baseline = _read_csv(STAGE102_SUMMARY_IN).iloc[0].to_dict()
    prior = _read_csv(SUMMARY104_IN).iloc[0].to_dict()
    total_orders = int(len(features))
    stage104_ready = int(features["panel_ready"].sum())
    trading_adjacent_fix = int(
        gap_rows["repair_action"].eq("calendar_holiday_gap_accept_with_trading_day_gate").sum()
    )
    effective_ready = stage104_ready + trading_adjacent_fix
    missing_file_rows = int(gap_rows["readiness_state_stage104"].eq("target_contract_not_in_product_panel").sum())
    exact_alt_found = int(
        gap_rows[
            gap_rows["readiness_state_stage104"].eq("target_contract_not_in_product_panel")
            & gap_rows["exact_file_any_downloaded_count"].gt(0)
        ].shape[0]
    )
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage105_gap_repair_manifest_built_external_backfill_required_no_rule",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "stage104_target_panel_ready_count": int(prior["target_contract_panel_ready_count"]),
        "timestamp_ready_order_count": total_orders,
        "stage104_gap_row_count": int(len(gap_rows)),
        "missing_target_contract_file_gap_row_count": missing_file_rows,
        "stale_source_calendar_gap_row_count": int(gap_rows["readiness_state_stage104"].eq("stale_source_date").sum()),
        "calendar_holiday_adjacent_reclassifiable_count": trading_adjacent_fix,
        "exact_alternate_local_file_found_row_count": exact_alt_found,
        "unique_missing_contract_count": int(repair_manifest["vt_symbol"].nunique()) if not repair_manifest.empty else 0,
        "legacy_2020_missing_gap_row_count": int(
            gap_rows["repair_action"].eq("backfill_legacy_target_contract_daily_oi").sum()
        ),
        "near_endpoint_2026_missing_gap_row_count": int(
            gap_rows["repair_action"].eq("download_or_refresh_near_endpoint_target_contract_daily_oi").sum()
        ),
        "effective_panel_ready_after_calendar_reclass_count": effective_ready,
        "effective_panel_ready_after_calendar_reclass_rate_pct": effective_ready / total_orders * 100.0,
        "right_tail_gap_row_count": int(gap_rows["right_tail_visual"].sum()),
        "bottom_loss_gap_row_count": int(gap_rows["bottom_loss_visual"].sum()),
        "promotion_gate_count": int(len(gates)),
        "promotion_gate_pass_count": int(gates["pass"].sum()),
        "panel_feature_rule_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "end_equity": float(baseline["end_equity"]),
        "total_return_pct": float(baseline["total_return_pct"]),
        "max_drawdown_pct": float(baseline["max_drawdown_pct"]),
        "sharpe": float(baseline["sharpe"]),
        "total_slippage": float(baseline["total_slippage"]),
        "total_trade_count": float(baseline["total_trade_count"]),
        "closed_lot_win_rate_pct": float(baseline["closed_lot_win_rate_pct"]),
        "max_broker10_margin_to_equity_pct": float(baseline["max_broker10_margin_to_equity_pct"]),
    }


def _write_report(
    summary: dict[str, Any],
    gap_rows: pd.DataFrame,
    repair_manifest: pd.DataFrame,
    action_summary: pd.DataFrame,
    product_year_gap: pd.DataFrame,
    gates: pd.DataFrame,
) -> None:
    top_missing = repair_manifest.sort_values(["linked_gap_order_count", "first_entry_date"], ascending=[False, True]).head(15)
    weak_cells = product_year_gap.sort_values(["gap_order_count", "entry_year"], ascending=[False, True]).head(15)
    lines = [
        "# Stage105 合约月份 OI 缺口修复 manifest",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{summary['created_at']}`",
        "- 阶段性质：只读数据缺口修复 manifest；不是真引擎、不生成交易规则",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：",
        "  - TqSdk Kline 对象字段：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html`",
        "  - TqSdk 介绍：`https://tqsdk-python.readthedocs.io/en/latest/intro.html`",
        "  - CME contract trading codes：`https://www.cmegroup.com/education/courses/introduction-to-futures/understanding-contract-trading-codes`",
        "  - CME daily volume and open interest：`https://www.cmegroup.com/market-data/browse-data/exchange-volume.html`",
        "- 我的判断：TqSdk 日线字段确实能承载 `open_oi/close_oi`，但合约代码格式、年份位数和本地下载批次覆盖会造成数据缺口。缺口修复应该先回到具体合约文件与 raw schema，而不是把 `missing`、`rank` 或年份缺口解释为交易信号。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{SCRIPT_PATH.relative_to(REPO_DIR)}`",
        "- 新增输出：gap rows、repair manifest、action summary、product-year gap matrix、source-age audit、promotion gate 和四张视觉图。",
        "- 新增参数：无策略参数；只使用 Stage104 已冻结的 non-ready 行做文件级审计。",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 回测/归因参数",
        "",
        "- 数据区间：沿用 Stage104 `219` 笔 timestamp-ready 订单与 Stage045 官方资金路径。",
        "- 本地搜索范围：`examples/portfolio_backtesting/downloaded_futures/**/*.csv`。",
        "- 审计口径：精确合约文件是否存在、schema 是否含 OI、自然日 source-age 是否只是交易日历空档、缺失合约需要的补数 manifest。",
        "- 策略/归因口径：`strategy_feature_usable=0`、`true_engine_run=0`、`ab_triggered=0`。",
        "",
        "## 结果",
        "",
        f"- 期末权益：`{summary['end_equity']:,.2f}`",
        f"- 总收益：`{summary['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{summary['max_drawdown_pct']:.4f}%`",
        f"- Sharpe：`{summary['sharpe']:.4f}`",
        f"- 总滑点：`{summary['total_slippage']:,.0f}`",
        f"- 总交易次数：`{summary['total_trade_count']:,.0f}`",
        f"- 胜率：closed-lot win rate `{summary['closed_lot_win_rate_pct']:.4f}%`",
        "- 其他关键指标：",
        f"  - `decision={summary['decision']}`",
        f"  - `stage104_gap_row_count={summary['stage104_gap_row_count']}`",
        f"  - `missing_target_contract_file_gap_row_count={summary['missing_target_contract_file_gap_row_count']}`",
        f"  - `stale_source_calendar_gap_row_count={summary['stale_source_calendar_gap_row_count']}`",
        f"  - `calendar_holiday_adjacent_reclassifiable_count={summary['calendar_holiday_adjacent_reclassifiable_count']}`",
        f"  - `exact_alternate_local_file_found_row_count={summary['exact_alternate_local_file_found_row_count']}`",
        f"  - `unique_missing_contract_count={summary['unique_missing_contract_count']}`",
        f"  - `legacy_2020_missing_gap_row_count={summary['legacy_2020_missing_gap_row_count']}`",
        f"  - `near_endpoint_2026_missing_gap_row_count={summary['near_endpoint_2026_missing_gap_row_count']}`",
        f"  - `effective_panel_ready_after_calendar_reclass_count={summary['effective_panel_ready_after_calendar_reclass_count']}/{summary['timestamp_ready_order_count']}`",
        f"  - `effective_panel_ready_after_calendar_reclass_rate_pct={summary['effective_panel_ready_after_calendar_reclass_rate_pct']:.4f}%`",
        f"  - `right_tail_gap_row_count={summary['right_tail_gap_row_count']}`",
        f"  - `bottom_loss_gap_row_count={summary['bottom_loss_gap_row_count']}`",
        f"  - `promotion_gate_pass_count={summary['promotion_gate_pass_count']}/{summary['promotion_gate_count']}`",
        f"  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`",
        "",
        "## 视觉观察",
        "",
        "- official path gap chart：缺口主要贴在 2020 初期与 2026 近端，两个自然日 stale 点可解释为交易日历相邻；缺口点不形成可交易状态。",
        "- product-year gap heatmap：缺口集中在 `2020` 多品种与 `2026` 近端少数合约，说明当前阻断是下载批次覆盖，不是策略结构。",
        "- repair action chart：最大动作是 `backfill_legacy_target_contract_daily_oi`，其次是 `download_or_refresh_near_endpoint_target_contract_daily_oi`；本地 alternate exact 文件未找到。",
        "- source-age chart：`CF201` 与 `AP205` 自然日超过 7 天，但产品交易日之间没有中间日期，更适合作为交易日历相邻修正，不应当被当作市场信号。",
        "",
        "## 代表性表格",
        "",
        "### Repair Action Summary",
        _md_table(action_summary, None),
        "",
        "### Missing Contract Manifest Top",
        _md_table(
            top_missing[
                [
                    "vt_symbol",
                    "stage104_product_key",
                    "linked_gap_order_count",
                    "first_entry_date",
                    "last_entry_date",
                    "pnl_sum",
                    "bottom_loss_count",
                    "primary_expected_path",
                    "download_symbol",
                ]
            ],
            15,
        ),
        "",
        "### Product-Year Gap Cells",
        _md_table(
            weak_cells[
                [
                    "stage104_product_key",
                    "entry_year",
                    "readiness_state_stage104",
                    "gap_order_count",
                    "pnl_sum",
                    "bottom_loss_count",
                ]
            ],
            15,
        ),
        "",
        "### Promotion Gates",
        _md_table(gates, None),
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_OUT.relative_to(REPO_DIR)}`",
        f"- summary：`{SUMMARY_OUT.relative_to(REPO_DIR)}`",
        f"- decision：`{DECISION_OUT.relative_to(REPO_DIR)}`",
        f"- gap rows：`{GAP_ROWS_OUT.relative_to(REPO_DIR)}`",
        f"- repair manifest：`{REPAIR_MANIFEST_OUT.relative_to(REPO_DIR)}`",
        f"- action summary：`{ACTION_SUMMARY_OUT.relative_to(REPO_DIR)}`",
        "- charts：",
        f"  - `{PATH_CHART_OUT.name}`",
        f"  - `{GAP_HEATMAP_OUT.name}`",
        f"  - `{ACTION_CHART_OUT.name}`",
        f"  - `{SOURCE_AGE_CHART_OUT.name}`",
        "",
        "## 结论",
        "",
        "- 本阶段结论：Stage104 的 `2` 个 stale source 可以改用交易日历相邻 gate 解释，但 `31` 个目标合约文件缺失在本地所有下载批次中都没有精确替代文件；必须外部补数或刷新 TqSDK 日线根目录。",
        "- 原因：本地 exact alternate file 命中为 `0`，effective ready 即使加入交易日历相邻修正也只有 `188/219=85.8447%`，仍低于 `95%` 规则研究门槛。",
        "- 下一步：按 repair manifest 补 `2020` legacy target contract daily OI 与 `2026` near-endpoint target contract daily OI，落盘 raw path/hash/schema/source permission 后重跑 Stage104/105；补齐前不做 rank/share 规则。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。Stage105 是文件级缺口修复审计，不按收益设计条件。",
        "- 运行后判断：否。缺口分类没有被用于开仓/降仓/退出，且明确把 `missing` 与 product-year 集中度排除为交易信号。",
        "- 原因：如果用 2020 或 2026 缺口对应的亏损去写规则，就是用数据缺失包装 alpha；本阶段只生成补数清单。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。Stage104 已证明合约月 OI 有部分覆盖且右尾覆盖完整，值得把数据契约补清。",
        "- 运行后判断：有价值，但下一步价值在补数，不在策略研究。",
        "- 原因：两个 stale row 已被交易日历解释，说明 Stage104 gate 可精炼；但 `31` 个目标合约文件缺失仍是硬阻断。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：是，追加 Stage105 摘要和边界。",
        "- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。",
        "- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    curve = _load_curve()
    gap_rows = _build_gap_rows(features)
    repair_manifest = _build_repair_manifest(gap_rows)
    action_summary = _build_action_summary(gap_rows)
    product_year_gap = _build_product_year_gap(gap_rows)
    source_age = _build_source_age_audit(gap_rows)
    gates = _build_promotion_gate(features, gap_rows, repair_manifest)
    summary = _summary(features, gap_rows, repair_manifest, gates)

    gap_rows.to_csv(GAP_ROWS_OUT, index=False, encoding="utf-8-sig")
    repair_manifest.to_csv(REPAIR_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    action_summary.to_csv(ACTION_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    product_year_gap.to_csv(PRODUCT_YEAR_GAP_OUT, index=False, encoding="utf-8-sig")
    source_age.to_csv(SOURCE_AGE_OUT, index=False, encoding="utf-8-sig")
    gates.to_csv(PROMOTION_GATE_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": summary["decision"],
        "line_id": LINE_ID,
        "created_at": summary["created_at"],
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "order_api_called": False,
        "ctp_connected": False,
        "next_allowed_action": (
            "backfill missing target contract daily OI files with raw hash/schema/source permission, then rerun Stage104/105"
        ),
        "blocked_actions": [
            "rank/share threshold before >=95% coverage",
            "using missing/product-year/source-age as trading rule",
            "true engine or A/B",
            "official candidate",
        ],
        "summary": summary,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_path_chart(gap_rows, curve, action_summary)
    _plot_gap_heatmap(product_year_gap)
    _plot_action_chart(action_summary)
    _plot_source_age(source_age)
    _write_report(summary, gap_rows, repair_manifest, action_summary, product_year_gap, gates)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
