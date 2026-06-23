from __future__ import annotations

from datetime import datetime
from functools import lru_cache
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
STAGE = "Stage104"
MODEL_TAG = "stage104_contract_month_oi_migration_readiness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage104_contract_month_oi_migration_readiness_audit"

TQSDK_DAILY_DIR = (
    REPO_DIR
    / "examples"
    / "portfolio_backtesting"
    / "downloaded_futures"
    / "tqsdk_daily_2010_2026_04"
)
STAGE102_ROWS_IN = (
    LINE_DIR
    / "outputs"
    / "stage102_bar_resolution_frontier_audit"
    / "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_resolution_rows_"
    "stage102_bar_resolution_frontier_audit_v1.csv"
)
STAGE102_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage102_bar_resolution_frontier_audit"
    / "qmt_roll_stage102_c9_minrisk_bar_resolution_frontier_audit_summary_"
    "stage102_bar_resolution_frontier_audit_v1.csv"
)
STAGE045_CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_panel_inventory_{MODEL_TAG}.csv"
PRODUCT_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_coverage_{MODEL_TAG}.csv"
RANK_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rank_summary_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_panel_coverage_chart_{MODEL_TAG}.png"
PRODUCT_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_coverage_heatmap_{MODEL_TAG}.png"
RANK_SHARE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rank_share_chart_{MODEL_TAG}.png"
PROMOTION_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_chart_{MODEL_TAG}.png"

READY_STATE = "panel_ready"
MIN_TARGET_COVERAGE_PCT = 95.0
MAX_SOURCE_AGE_DAYS = 7

STATE_COLORS = {
    READY_STATE: "#15803d",
    "target_contract_not_in_product_panel": "#dc2626",
    "target_contract_inactive_or_absent": "#f59e0b",
    "preentry_date_missing": "#7f7f7f",
    "panel_missing": "#7f7f7f",
    "single_contract_panel": "#f59e0b",
    "stale_source_date": "#f97316",
}


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


def _load_stage102_rows() -> pd.DataFrame:
    rows = _read_csv(STAGE102_ROWS_IN)
    for column in ["official_open_date", "order_first_entry_date", "order_exit_date"]:
        if column in rows.columns:
            rows[column] = pd.to_datetime(rows[column], errors="coerce").dt.normalize()
    for column in [
        "order_realized_pnl",
        "order_positive_pnl",
        "order_negative_pnl",
        "right_tail_visual",
        "bottom_loss_visual",
        "maxdd_context",
        "candidate_index",
    ]:
        if column in rows.columns:
            rows[column] = pd.to_numeric(rows[column], errors="coerce")
    rows["official_open_date"] = rows["official_open_date"].fillna(rows.get("order_first_entry_date"))
    rows = rows[rows["official_open_date"].notna()].copy()
    return rows.reset_index(drop=True)


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(STAGE045_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "total_slippage", "trade_count"]:
        if column in curve.columns:
            curve[column] = pd.to_numeric(curve[column], errors="coerce")
    curve = curve[curve["date"].notna()].copy()
    return curve.sort_values("date").reset_index(drop=True)


def _normalize_product(product: Any, vt_symbol: Any) -> tuple[str, str, str]:
    product_text = "" if pd.isna(product) else str(product).strip()
    if "." in product_text:
        code, exchange = product_text.rsplit(".", 1)
    else:
        vt_text = "" if pd.isna(vt_symbol) else str(vt_symbol).strip()
        if "." in vt_text:
            contract, exchange = vt_text.rsplit(".", 1)
            match = re.match(r"([A-Za-z]+)", contract)
            code = match.group(1) if match else product_text
        else:
            code, exchange = product_text, ""
    code = code.upper() if exchange == "CZCE" else code.lower()
    return code, exchange, f"{code}.{exchange}" if exchange else code


def _contract_code(vt_symbol: Any) -> str:
    text = "" if pd.isna(vt_symbol) else str(vt_symbol).strip()
    return text.split(".", 1)[0]


def _contract_variants(contract: str, exchange: str) -> set[str]:
    variants = {contract, contract.lower(), contract.upper()}
    match = re.match(r"([A-Za-z]+)(\d+)", contract)
    if match and exchange == "CZCE":
        code = match.group(1).upper()
        digits = match.group(2)
        if len(digits) == 4:
            variants.add(code + digits[-3:])
        if len(digits) == 3:
            variants.add(code + digits)
    return variants


def _contract_month_serial(contract: str, exchange: str, ref_date: pd.Timestamp | None) -> float:
    match = re.match(r"([A-Za-z]+)(\d{3,4})", str(contract))
    if not match:
        return np.nan
    digits = match.group(2)
    if len(digits) == 4:
        yy = int(digits[:2])
        month = int(digits[2:])
        year = 2000 + yy if yy < 80 else 1900 + yy
    else:
        y_digit = int(digits[:1])
        month = int(digits[1:])
        ref_year = int(pd.Timestamp(ref_date).year) if ref_date is not None and not pd.isna(ref_date) else 2020
        decade = (ref_year // 10) * 10
        candidates = [decade - 10 + y_digit, decade + y_digit, decade + 10 + y_digit]
        year = min(candidates, key=lambda candidate: abs(candidate - ref_year))
    if month < 1 or month > 12:
        return np.nan
    return float(year * 12 + month)


def _product_files(product_key: str) -> list[Path]:
    if "." not in product_key:
        return []
    code, exchange = product_key.rsplit(".", 1)
    directory = TQSDK_DAILY_DIR / exchange
    if not directory.exists():
        return []
    pattern = re.compile(r"^" + re.escape(code) + r"\d+[A-Za-z]*$", re.IGNORECASE)
    return sorted(path for path in directory.glob("*.csv") if pattern.match(path.stem))


@lru_cache(maxsize=None)
def _load_product_panel(product_key: str) -> pd.DataFrame:
    files = _product_files(product_key)
    if "." not in product_key:
        return pd.DataFrame()
    _, exchange = product_key.rsplit(".", 1)
    frames: list[pd.DataFrame] = []
    for path in files:
        try:
            frame = pd.read_csv(path, usecols=["trade_date", "close", "volume", "open_oi", "close_oi"])
        except Exception:
            continue
        frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
        frame["contract"] = path.stem
        frame["contract_vt_symbol"] = f"{path.stem}.{exchange}"
        for column in ["close", "volume", "open_oi", "close_oi"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame[frame["date"].notna() & frame["close_oi"].notna()].copy()
        frames.append(
            frame[
                [
                    "date",
                    "contract",
                    "contract_vt_symbol",
                    "close",
                    "volume",
                    "open_oi",
                    "close_oi",
                ]
            ]
        )
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["product_key"] = product_key
    out["active_oi"] = out["close_oi"].fillna(0.0).clip(lower=0.0)
    out["source_family"] = "tqsdk_daily_2010_2026_04"
    return out.sort_values(["date", "contract"]).reset_index(drop=True)


def _build_inventory(product_keys: list[str], rows: pd.DataFrame) -> pd.DataFrame:
    order_counts = rows.groupby("stage104_product_key").size().rename("linked_order_count")
    inventory_rows: list[dict[str, Any]] = []
    for product_key in product_keys:
        files = _product_files(product_key)
        panel = _load_product_panel(product_key)
        inventory_rows.append(
            {
                "product_key": product_key,
                "exchange": product_key.rsplit(".", 1)[1] if "." in product_key else "",
                "file_count": len(files),
                "panel_row_count": int(len(panel)),
                "contract_count": int(panel["contract"].nunique()) if not panel.empty else 0,
                "date_min": panel["date"].min() if not panel.empty else pd.NaT,
                "date_max": panel["date"].max() if not panel.empty else pd.NaT,
                "linked_order_count": int(order_counts.get(product_key, 0)),
                "schema_columns": "trade_date,datetime,open,high,low,close,volume,open_oi,close_oi",
                "raw_authority_manifest_complete": 0,
                "rule_allowed": 0,
            }
        )
    out = pd.DataFrame(inventory_rows).sort_values(["exchange", "product_key"])
    return out.reset_index(drop=True)


def _feature_for_order(row: pd.Series) -> dict[str, Any]:
    code, exchange, product_key = _normalize_product(row.get("product"), row.get("vt_symbol"))
    entry_date = pd.Timestamp(row["official_open_date"]).normalize()
    panel = _load_product_panel(product_key)
    target_contract = _contract_code(row.get("vt_symbol"))
    variants = _contract_variants(target_contract, exchange)

    base: dict[str, Any] = {
        "candidate_index": int(row.get("candidate_index")) if not pd.isna(row.get("candidate_index")) else np.nan,
        "official_open_trade_id": row.get("official_open_trade_id", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "target_contract": target_contract,
        "direction": row.get("direction", ""),
        "official_open_date": entry_date,
        "stage104_product_key": product_key,
        "product_code": code,
        "exchange": exchange,
        "order_realized_pnl": float(row.get("order_realized_pnl", 0.0)),
        "right_tail_visual": int(row.get("right_tail_visual", 0) or 0),
        "bottom_loss_visual": int(row.get("bottom_loss_visual", 0) or 0),
        "maxdd_context": int(row.get("maxdd_context", 0) or 0),
        "source_family": "tqsdk_daily_2010_2026_04",
        "source_date": pd.NaT,
        "source_age_days": np.nan,
        "contract_file_count": len(_product_files(product_key)),
        "day_contract_count": 0,
        "active_contract_count": 0,
        "total_close_oi": np.nan,
        "target_close_oi": np.nan,
        "target_oi_share": np.nan,
        "target_oi_rank": np.nan,
        "target_rank_bucket": "missing",
        "target_contract_found_active": 0,
        "top_contract": "",
        "second_contract": "",
        "top_close_oi": np.nan,
        "second_close_oi": np.nan,
        "top_oi_share": np.nan,
        "second_oi_share": np.nan,
        "target_minus_top_months": np.nan,
        "target_minus_second_months": np.nan,
        "panel_ready": 0,
        "rule_allowed": 0,
        "true_engine_allowed": 0,
        "ab_allowed": 0,
        "readiness_state": "panel_missing",
    }

    if panel.empty:
        return base

    prior_dates = panel.loc[panel["date"].lt(entry_date), "date"]
    if prior_dates.empty:
        base["readiness_state"] = "preentry_date_missing"
        return base

    source_date = prior_dates.max()
    day = panel[panel["date"].eq(source_date)].copy()
    active = day[day["active_oi"].gt(0.0)].copy()
    active = active.sort_values(["active_oi", "volume", "contract"], ascending=[False, False, True]).reset_index(drop=True)
    active["target_rank"] = np.arange(1, len(active) + 1)
    total_oi = float(active["active_oi"].sum()) if not active.empty else 0.0

    base["source_date"] = source_date
    base["source_age_days"] = int((entry_date - source_date).days)
    base["day_contract_count"] = int(len(day))
    base["active_contract_count"] = int(len(active))
    base["total_close_oi"] = total_oi
    if not active.empty and total_oi > 0:
        base["top_contract"] = str(active["contract_vt_symbol"].iloc[0])
        base["top_close_oi"] = float(active["active_oi"].iloc[0])
        base["top_oi_share"] = float(active["active_oi"].iloc[0] / total_oi)
    if len(active) > 1 and total_oi > 0:
        base["second_contract"] = str(active["contract_vt_symbol"].iloc[1])
        base["second_close_oi"] = float(active["active_oi"].iloc[1])
        base["second_oi_share"] = float(active["active_oi"].iloc[1] / total_oi)

    target = active[active["contract"].isin(variants)]
    if target.empty:
        inactive_target = day[day["contract"].isin(variants)]
        base["readiness_state"] = (
            "target_contract_inactive_or_absent" if not inactive_target.empty else "target_contract_not_in_product_panel"
        )
        if not inactive_target.empty:
            base["target_close_oi"] = float(inactive_target["active_oi"].iloc[0])
        return base

    target_row = target.iloc[0]
    target_rank = int(target_row["target_rank"])
    base["target_contract_found_active"] = 1
    base["target_close_oi"] = float(target_row["active_oi"])
    base["target_oi_share"] = float(target_row["active_oi"] / total_oi) if total_oi > 0 else np.nan
    base["target_oi_rank"] = target_rank
    if target_rank == 1:
        base["target_rank_bucket"] = "rank_1_main"
    elif target_rank == 2:
        base["target_rank_bucket"] = "rank_2_secondary"
    else:
        base["target_rank_bucket"] = "rank_3plus_tail"

    target_serial = _contract_month_serial(str(target_row["contract"]), exchange, source_date)
    if base["top_contract"]:
        top_serial = _contract_month_serial(str(active["contract"].iloc[0]), exchange, source_date)
        base["target_minus_top_months"] = target_serial - top_serial
    if len(active) > 1:
        second_serial = _contract_month_serial(str(active["contract"].iloc[1]), exchange, source_date)
        base["target_minus_second_months"] = target_serial - second_serial

    if base["source_age_days"] > MAX_SOURCE_AGE_DAYS:
        base["readiness_state"] = "stale_source_date"
    elif base["active_contract_count"] < 2:
        base["readiness_state"] = "single_contract_panel"
    else:
        base["readiness_state"] = READY_STATE
        base["panel_ready"] = 1
    return base


def _build_features(rows: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame([_feature_for_order(row) for _, row in rows.iterrows()])
    features["entry_year"] = pd.to_datetime(features["official_open_date"], errors="coerce").dt.year
    features["positive_pnl"] = features["order_realized_pnl"].where(features["order_realized_pnl"].gt(0.0), 0.0)
    features["negative_pnl"] = features["order_realized_pnl"].where(features["order_realized_pnl"].lt(0.0), 0.0)
    return features.sort_values(["official_open_date", "candidate_index"]).reset_index(drop=True)


def _product_year_coverage(features: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        features.groupby(["stage104_product_key", "entry_year"], dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            panel_ready_count=("panel_ready", "sum"),
            target_missing_count=("target_contract_found_active", lambda series: int((series == 0).sum())),
            right_tail_count=("right_tail_visual", "sum"),
            right_tail_ready_count=("right_tail_visual", lambda series: 0),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            pnl_sum=("order_realized_pnl", "sum"),
        )
        .reset_index()
    )
    ready_right = (
        features[features["panel_ready"].eq(1)]
        .groupby(["stage104_product_key", "entry_year"])["right_tail_visual"]
        .sum()
        .rename("ready_right_tail_count")
    )
    ready_bottom = (
        features[features["panel_ready"].eq(1)]
        .groupby(["stage104_product_key", "entry_year"])["bottom_loss_visual"]
        .sum()
        .rename("ready_bottom_loss_count")
    )
    grouped = grouped.merge(ready_right, on=["stage104_product_key", "entry_year"], how="left")
    grouped = grouped.merge(ready_bottom, on=["stage104_product_key", "entry_year"], how="left")
    grouped["ready_right_tail_count"] = grouped["ready_right_tail_count"].fillna(0).astype(int)
    grouped["ready_bottom_loss_count"] = grouped["ready_bottom_loss_count"].fillna(0).astype(int)
    grouped["panel_ready_rate_pct"] = grouped["panel_ready_count"] / grouped["order_count"] * 100.0
    return grouped.sort_values(["entry_year", "stage104_product_key"]).reset_index(drop=True)


def _rank_summary(features: pd.DataFrame) -> pd.DataFrame:
    rank = features.copy()
    rank["rank_bucket_with_missing"] = rank["target_rank_bucket"].where(rank["panel_ready"].eq(1), rank["readiness_state"])
    grouped = (
        rank.groupby("rank_bucket_with_missing", dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            pnl_sum=("order_realized_pnl", "sum"),
            positive_pnl_sum=("positive_pnl", "sum"),
            negative_pnl_sum=("negative_pnl", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            maxdd_context_count=("maxdd_context", "sum"),
            median_target_oi_share=("target_oi_share", "median"),
        )
        .reset_index()
        .sort_values(["rank_bucket_with_missing"])
    )
    return grouped.reset_index(drop=True)


def _promotion_gate(features: pd.DataFrame) -> pd.DataFrame:
    order_count = int(len(features))
    ready_count = int(features["panel_ready"].sum())
    ready_rate_pct = ready_count / order_count * 100.0 if order_count else 0.0
    right_tail_total = int(features["right_tail_visual"].sum())
    right_tail_ready = int(features.loc[features["panel_ready"].eq(1), "right_tail_visual"].sum())
    product_year = _product_year_coverage(features)
    hard_gap_cells = int((product_year["panel_ready_rate_pct"] < MIN_TARGET_COVERAGE_PCT).sum())
    source_age_ready = int(features["source_age_days"].le(MAX_SOURCE_AGE_DAYS).sum())
    unique_file_count = sum(len(_product_files(product_key)) for product_key in sorted(features["stage104_product_key"].unique()))
    gates = [
        {
            "gate": "local_contract_daily_panel_present",
            "pass": int(features["contract_file_count"].gt(0).all() and features["day_contract_count"].gt(0).any()),
            "observed": f"products={features['stage104_product_key'].nunique()}, files={unique_file_count}",
            "required": "target products have local contract daily files",
            "rule_allowed": 0,
        },
        {
            "gate": "target_contract_coverage_ge95pct",
            "pass": int(ready_rate_pct >= MIN_TARGET_COVERAGE_PCT),
            "observed": f"{ready_count}/{order_count}={ready_rate_pct:.4f}%",
            "required": f">={MIN_TARGET_COVERAGE_PCT:.1f}%",
            "rule_allowed": 0,
        },
        {
            "gate": "source_date_age_le7_all_orders",
            "pass": int(source_age_ready == order_count),
            "observed": f"{source_age_ready}/{order_count}",
            "required": f"all source dates <= {MAX_SOURCE_AGE_DAYS} calendar days before entry",
            "rule_allowed": 0,
        },
        {
            "gate": "right_tail_full_coverage",
            "pass": int(right_tail_total > 0 and right_tail_ready == right_tail_total),
            "observed": f"{right_tail_ready}/{right_tail_total}",
            "required": "all visual right-tail orders covered before rule research",
            "rule_allowed": 0,
        },
        {
            "gate": "product_year_no_hard_gap",
            "pass": int(hard_gap_cells == 0),
            "observed": f"hard_gap_cells={hard_gap_cells}",
            "required": f"no product-year cell below {MIN_TARGET_COVERAGE_PCT:.1f}% for linked orders",
            "rule_allowed": 0,
        },
        {
            "gate": "raw_authority_hash_schema_manifest_complete",
            "pass": 0,
            "observed": "local TqSDK daily CSV files found; no line-level raw hash/source permission manifest",
            "required": "raw path/hash/schema/source permission manifest for all bound rows",
            "rule_allowed": 0,
        },
        {
            "gate": "true_engine_or_ab_allowed",
            "pass": 0,
            "observed": "readiness audit only",
            "required": "coverage + provenance + predeclared economic test must pass first",
            "rule_allowed": 0,
        },
    ]
    return pd.DataFrame(gates)


def _attach_curve_y(features: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    left = features.sort_values("official_open_date").copy()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    merged = pd.merge_asof(left, right, left_on="official_open_date", right_on="date", direction="backward")
    return merged.sort_index()


def _plot_path_chart(features: pd.DataFrame, curve: pd.DataFrame, product_year: pd.DataFrame) -> None:
    plot_features = _attach_curve_y(features, curve)
    fig = plt.figure(figsize=(16, 11))
    gs = fig.add_gridspec(4, 1, height_ratios=[2.2, 1.2, 1.0, 1.4], hspace=0.12)
    ax_eq = fig.add_subplot(gs[0, 0])
    ax_dd = fig.add_subplot(gs[1, 0], sharex=ax_eq)
    ax_broker = fig.add_subplot(gs[2, 0], sharex=ax_eq)
    ax_year = fig.add_subplot(gs[3, 0])

    ax_eq.plot(curve["date"], curve["account_equity"], color="#111827", linewidth=1.4, label="official equity")
    for state, group in plot_features.groupby("readiness_state"):
        ax_eq.scatter(
            group["official_open_date"],
            group["account_equity"],
            s=np.where(group["right_tail_visual"].eq(1), 56, 22),
            color=STATE_COLORS.get(state, "#6b7280"),
            alpha=0.78,
            edgecolor=np.where(group["bottom_loss_visual"].eq(1), "#111827", "none"),
            linewidth=0.8,
            label=state,
        )
    ax_eq.set_ylabel("equity")
    ax_eq.set_title("Stage104 contract-month OI panel coverage on official path")
    ax_eq.grid(alpha=0.2)
    ax_eq.legend(loc="upper left", ncols=2, fontsize=8)

    ax_dd.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#fecaca", alpha=0.8)
    ax_dd.plot(curve["date"], curve["drawdown_pct"], color="#991b1b", linewidth=1.0)
    ax_dd.set_ylabel("drawdown %")
    ax_dd.grid(alpha=0.2)

    ax_broker.plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#2563eb", linewidth=1.0)
    ax_broker.axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.8)
    ax_broker.set_ylabel("broker10 %")
    ax_broker.grid(alpha=0.2)

    yearly = product_year.groupby("entry_year").agg(order_count=("order_count", "sum"), ready=("panel_ready_count", "sum")).reset_index()
    yearly["missing"] = yearly["order_count"] - yearly["ready"]
    ax_year.bar(yearly["entry_year"].astype(str), yearly["ready"], color="#15803d", label="panel ready")
    ax_year.bar(yearly["entry_year"].astype(str), yearly["missing"], bottom=yearly["ready"], color="#dc2626", label="not ready")
    ax_year.set_ylabel("orders")
    ax_year.set_xlabel("entry year")
    ax_year.legend(loc="upper right")
    ax_year.grid(axis="y", alpha=0.2)

    fig.autofmt_xdate()
    fig.savefig(PATH_CHART_OUT, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_product_year_heatmap(product_year: pd.DataFrame) -> None:
    pivot = product_year.pivot_table(
        index="stage104_product_key",
        columns="entry_year",
        values="panel_ready_rate_pct",
        aggfunc="mean",
    ).sort_index()
    fig, ax = plt.subplots(figsize=(13, max(7, 0.35 * len(pivot))))
    masked = np.ma.masked_invalid(pivot.to_numpy(dtype=float))
    image = ax.imshow(masked, aspect="auto", cmap="RdYlGn", vmin=0, vmax=100)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(col)) for col in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            value = pivot.iloc[y, x]
            if pd.notna(value):
                ax.text(x, y, f"{value:.0f}", ha="center", va="center", fontsize=8, color="#111827")
    ax.set_title("Panel-ready rate by product-year (%)")
    ax.set_xlabel("entry year")
    ax.set_ylabel("product")
    fig.colorbar(image, ax=ax, label="ready rate %")
    fig.savefig(PRODUCT_YEAR_HEATMAP_OUT, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_rank_share_chart(features: pd.DataFrame, rank_summary: pd.DataFrame) -> None:
    fig, (ax_bar, ax_scatter) = plt.subplots(2, 1, figsize=(15, 10), gridspec_kw={"height_ratios": [1.0, 1.5]})
    rank_summary = rank_summary.copy()
    colors = [
        "#15803d" if "rank_1" in str(bucket) else "#65a30d" if "rank_2" in str(bucket) else "#dc2626"
        for bucket in rank_summary["rank_bucket_with_missing"]
    ]
    ax_bar.bar(rank_summary["rank_bucket_with_missing"], rank_summary["order_count"], color=colors, alpha=0.85)
    ax_bar.set_ylabel("orders")
    ax_bar.set_title("Target contract OI rank distribution; diagnostic only")
    ax_bar.tick_params(axis="x", rotation=20)
    ax_bar.grid(axis="y", alpha=0.2)
    ax_pnl = ax_bar.twinx()
    ax_pnl.plot(rank_summary["rank_bucket_with_missing"], rank_summary["pnl_sum"], color="#111827", marker="o", linewidth=1.0)
    ax_pnl.axhline(0.0, color="#6b7280", linewidth=0.8)
    ax_pnl.set_ylabel("PnL sum")

    ready = features[features["panel_ready"].eq(1)].copy()
    rank_color = {
        "rank_1_main": "#15803d",
        "rank_2_secondary": "#2563eb",
        "rank_3plus_tail": "#f59e0b",
    }
    for bucket, group in ready.groupby("target_rank_bucket"):
        ax_scatter.scatter(
            group["official_open_date"],
            group["target_oi_share"] * 100.0,
            s=np.where(group["right_tail_visual"].eq(1), 80, 28),
            color=rank_color.get(bucket, "#6b7280"),
            alpha=0.78,
            edgecolor=np.where(group["bottom_loss_visual"].eq(1), "#111827", "none"),
            linewidth=0.9,
            label=bucket,
        )
    ax_scatter.set_ylabel("target OI share %")
    ax_scatter.set_xlabel("entry date")
    ax_scatter.grid(alpha=0.2)
    ax_scatter.legend(loc="upper right")
    fig.autofmt_xdate()
    fig.savefig(RANK_SHARE_CHART_OUT, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_promotion_gate_chart(gates: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.5))
    colors = np.where(gates["pass"].astype(int).eq(1), "#15803d", "#dc2626")
    ax.barh(gates["gate"], gates["pass"].astype(int), color=colors)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["blocked", "pass"])
    ax.set_title("Promotion gates: data contract only, no trading rule")
    for y, row in enumerate(gates.itertuples(index=False)):
        ax.text(0.02, y, str(row.observed), va="center", ha="left", color="#111827", fontsize=8)
    ax.grid(axis="x", alpha=0.2)
    fig.savefig(PROMOTION_GATE_CHART_OUT, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _summary_row(
    features: pd.DataFrame,
    inventory: pd.DataFrame,
    product_year: pd.DataFrame,
    gates: pd.DataFrame,
    curve: pd.DataFrame,
) -> dict[str, Any]:
    order_count = int(len(features))
    ready_count = int(features["panel_ready"].sum())
    right_tail_total = int(features["right_tail_visual"].sum())
    right_tail_ready = int(features.loc[features["panel_ready"].eq(1), "right_tail_visual"].sum())
    bottom_loss_total = int(features["bottom_loss_visual"].sum())
    bottom_loss_ready = int(features.loc[features["panel_ready"].eq(1), "bottom_loss_visual"].sum())
    target_missing_count = int(features["target_contract_found_active"].eq(0).sum())
    target_found_active_count = int(features["target_contract_found_active"].sum())
    rank1_count = int(features["target_rank_bucket"].eq("rank_1_main").sum())
    rank2_count = int(features["target_rank_bucket"].eq("rank_2_secondary").sum())
    rank3_count = int(features["target_rank_bucket"].eq("rank_3plus_tail").sum())
    hard_gap_cells = int((product_year["panel_ready_rate_pct"] < MIN_TARGET_COVERAGE_PCT).sum())
    baseline = _read_csv(STAGE102_SUMMARY_IN).iloc[0].to_dict()
    end_equity = float(baseline["end_equity"])
    total_return_pct = float(baseline["total_return_pct"])
    max_drawdown_pct = float(baseline["max_drawdown_pct"])
    sharpe = float(baseline["sharpe"])
    total_slippage = float(baseline["total_slippage"])
    total_trade_count = float(baseline["total_trade_count"])
    closed_lot_win_rate_pct = float(baseline["closed_lot_win_rate_pct"])
    order_level_positive_rate_pct = (
        float(features["order_realized_pnl"].gt(0.0).sum() / order_count * 100.0) if order_count else np.nan
    )
    max_broker = float(curve["broker10_margin_to_equity_pct"].max())
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage104_contract_month_oi_migration_panel_partial_ready_no_rule",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "timestamp_ready_order_count": order_count,
        "product_count": int(features["stage104_product_key"].nunique()),
        "local_contract_daily_file_count": int(inventory["file_count"].sum()),
        "local_contract_panel_product_count": int(inventory["file_count"].gt(0).sum()),
        "target_contract_panel_ready_count": ready_count,
        "target_contract_panel_ready_rate_pct": ready_count / order_count * 100.0 if order_count else 0.0,
        "target_contract_found_active_count": target_found_active_count,
        "target_contract_missing_count": target_missing_count,
        "source_age_le7_count": int(features["source_age_days"].le(MAX_SOURCE_AGE_DAYS).sum()),
        "active_contract_ge2_count": int(features["active_contract_count"].ge(2).sum()),
        "right_tail_total_count": right_tail_total,
        "right_tail_panel_ready_count": right_tail_ready,
        "bottom_loss_total_count": bottom_loss_total,
        "bottom_loss_panel_ready_count": bottom_loss_ready,
        "target_rank1_count": rank1_count,
        "target_rank2_count": rank2_count,
        "target_rank3plus_count": rank3_count,
        "product_year_hard_gap_cell_count": hard_gap_cells,
        "promotion_gate_count": int(len(gates)),
        "promotion_gate_pass_count": int(gates["pass"].sum()),
        "panel_feature_rule_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "end_equity": end_equity,
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe": sharpe,
        "total_slippage": total_slippage,
        "total_trade_count": total_trade_count,
        "closed_lot_win_rate_pct": closed_lot_win_rate_pct,
        "order_level_positive_rate_pct": order_level_positive_rate_pct,
        "max_broker10_margin_to_equity_pct": max_broker,
    }


def _write_report(
    summary: dict[str, Any],
    inventory: pd.DataFrame,
    product_year: pd.DataFrame,
    rank_summary: pd.DataFrame,
    gates: pd.DataFrame,
) -> None:
    top_inventory = inventory.sort_values(["linked_order_count", "file_count"], ascending=[False, False]).head(12)
    weak_product_year = product_year.sort_values(["panel_ready_rate_pct", "order_count"], ascending=[True, False]).head(12)
    lines = [
        "# Stage104 合约月份 OI 迁移数据契约审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{summary['created_at']}`",
        f"- 阶段性质：只读合约粒度 OI 面板覆盖/数据契约审计；不是真引擎、不生成交易规则",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：",
        "  - CME Open Interest：`https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest`",
        "  - DCE Daily Data：`https://www.dce.com.cn/dceg/channel/list/471.html`",
        "  - Bourse de Montréal futures roll analysis：`https://www.m-x.ca/f_publications_en/cgb_guide_futures_roll_analysis_en.pdf`",
        "  - Quantpedia continuous futures methodology：`https://quantpedia.com/continuous-futures-contracts-methodology-for-backtesting/`",
        "- 我的判断：open interest 与换月迁移有第一性价值，因为它描述资金承接、流动性迁移和主次合约权力转移；但它是日级、合约级状态，不是分钟触价执行语义。当前必须先确认入场前可见、目标合约可绑定、跨年跨品种覆盖和 raw provenance，再讨论预声明假设。把主力/次主力/份额直接当阈值就是过拟合。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{SCRIPT_PATH.relative_to(REPO_DIR)}`",
        "- 新增输出：features、contract panel inventory、product-year coverage、rank summary、promotion gate、四张视觉图。",
        "- 新增参数：无策略参数；仅设置数据契约门槛 `target_contract_coverage_ge95pct` 与 `source_date_age_le7_all_orders`。",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 回测/归因参数",
        "",
        "- 数据区间：沿用 Stage102 timestamp-ready `219` 笔订单；合约日线来自本地 `tqsdk_daily_2010_2026_04`。",
        "- 可见性：每笔订单只取 `official_open_date` 之前最近一个可见日的合约 OI 面板。",
        "- 账户规模与成本口径：沿用既有资金路径作为背景；不改变交易、不复跑引擎。",
        "- 策略/归因口径：`panel_feature_rule_allowed=0`、`true_engine_run=0`、`strategy_feature_usable=0`。",
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
        f"  - `timestamp_ready_order_count={summary['timestamp_ready_order_count']}`",
        f"  - `product_count={summary['product_count']}`",
        f"  - `local_contract_daily_file_count={summary['local_contract_daily_file_count']}`",
        f"  - `target_contract_panel_ready_count={summary['target_contract_panel_ready_count']}`",
        f"  - `target_contract_panel_ready_rate_pct={summary['target_contract_panel_ready_rate_pct']:.4f}%`",
        f"  - `target_contract_missing_count={summary['target_contract_missing_count']}`",
        f"  - `source_age_le7_count={summary['source_age_le7_count']}`",
        f"  - `active_contract_ge2_count={summary['active_contract_ge2_count']}`",
        f"  - `right_tail_panel_ready_count={summary['right_tail_panel_ready_count']}/{summary['right_tail_total_count']}`",
        f"  - `bottom_loss_panel_ready_count={summary['bottom_loss_panel_ready_count']}/{summary['bottom_loss_total_count']}`",
        f"  - `target_rank1_count={summary['target_rank1_count']}`",
        f"  - `target_rank2_count={summary['target_rank2_count']}`",
        f"  - `target_rank3plus_count={summary['target_rank3plus_count']}`",
        f"  - `product_year_hard_gap_cell_count={summary['product_year_hard_gap_cell_count']}`",
        f"  - `promotion_gate_pass_count={summary['promotion_gate_pass_count']}/{summary['promotion_gate_count']}`",
        "",
        "## 视觉观察",
        "",
        "- official path panel coverage chart：资金/回撤/broker10 仍只是背景路径；panel ready 点覆盖了主要右尾样本，但 2020 与 2026 仍有红色缺口，不能直接进入规则。",
        "- product-year coverage heatmap：多数中段年份覆盖较好，缺口集中在早期/近端目标合约文件缺失；这属于数据覆盖边界，不是品种年份筛选理由。",
        "- rank/share chart：ready 样本中多数目标合约已经是 OI rank1，少量 rank2/rank3plus 也存在；这个分布只能说明当前 C9 多数交易在主力附近，不能说明 rank1 更好或 rank2 更差。",
        "- promotion gate chart：本地合约日线面板存在、右尾覆盖通过，但目标合约覆盖未达 95%、product-year 有硬缺口、raw hash/source permission manifest 不完整，因此交易规则、true engine、A/B 全部 blocked。",
        "",
        "## 代表性表格",
        "",
        "### Panel Inventory Top",
        _md_table(top_inventory[["product_key", "exchange", "file_count", "contract_count", "date_min", "date_max", "linked_order_count"]], 12),
        "",
        "### Weak Product-Year Coverage",
        _md_table(
            weak_product_year[
                [
                    "stage104_product_key",
                    "entry_year",
                    "order_count",
                    "panel_ready_count",
                    "panel_ready_rate_pct",
                    "pnl_sum",
                ]
            ],
            12,
        ),
        "",
        "### Rank Summary",
        _md_table(rank_summary, None),
        "",
        "### Promotion Gates",
        _md_table(gates, None),
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_OUT.relative_to(REPO_DIR)}`",
        f"- summary：`{SUMMARY_OUT.relative_to(REPO_DIR)}`",
        f"- decision：`{DECISION_OUT.relative_to(REPO_DIR)}`",
        f"- features：`{FEATURES_OUT.relative_to(REPO_DIR)}`",
        f"- inventory：`{INVENTORY_OUT.relative_to(REPO_DIR)}`",
        f"- product-year coverage：`{PRODUCT_YEAR_OUT.relative_to(REPO_DIR)}`",
        f"- rank summary：`{RANK_SUMMARY_OUT.relative_to(REPO_DIR)}`",
        f"- promotion gate：`{PROMOTION_GATE_OUT.relative_to(REPO_DIR)}`",
        "- charts：",
        f"  - `{PATH_CHART_OUT.name}`",
        f"  - `{PRODUCT_YEAR_HEATMAP_OUT.name}`",
        f"  - `{RANK_SHARE_CHART_OUT.name}`",
        f"  - `{PROMOTION_GATE_CHART_OUT.name}`",
        "",
        "## 结论",
        "",
        "- 本阶段结论：合约月份 OI 迁移路线从“可能需要采购”变成“本地已有部分合约日线面板，可继续做数据契约修复/只读假设预检”，但当前仍不能写交易规则。",
        f"- 原因：目标合约 active 可找到 `{summary['target_contract_found_active_count']}/{summary['timestamp_ready_order_count']}`，但严格 panel-ready 只有 `{summary['target_contract_panel_ready_count']}/{summary['timestamp_ready_order_count']}={summary['target_contract_panel_ready_rate_pct']:.4f}%`，低于 95% 门槛；缺口集中在本地面板缺少目标合约文件、source age 超限与 raw authority/hash/schema manifest 未按本线固化。",
        "- 下一步：先补齐/固化缺失合约文件与 raw provenance，或只在 `panel_ready=1` 子集做预声明视觉假设审计；不得把 missing、rank、share、product-year 或 source-age 直接做阈值。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。Stage104 是数据契约审计，不按收益调阈值。",
        "- 运行后判断：否。结论是阻止规则化并暴露覆盖缺口；rank/share 只作视觉分布，不作交易条件。",
        "- 原因：如果现在按 rank1、rank2、OI share 或缺失年份筛选，就会把数据结构和历史右尾位置混为 alpha；本阶段明确禁止。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。Stage103 关闭了当前微观结构规则化，合约月 OI 是更高层、入场前可见的外生状态。",
        "- 运行后判断：有价值，但价值在数据修复和预声明假设，不在立即接规则。",
        "- 原因：右尾覆盖目前完整，说明这个路线没有第一眼就伤害右尾；但总体覆盖不足和 provenance 缺口决定它还不能进入 true engine。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：是，追加 Stage104 摘要和边界。",
        "- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。",
        "- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_stage102_rows()
    rows[["stage104_code", "stage104_exchange", "stage104_product_key"]] = rows.apply(
        lambda row: pd.Series(_normalize_product(row.get("product"), row.get("vt_symbol"))),
        axis=1,
    )
    product_keys = sorted(rows["stage104_product_key"].dropna().astype(str).unique())
    features = _build_features(rows)
    inventory = _build_inventory(product_keys, rows)
    product_year = _product_year_coverage(features)
    rank_summary = _rank_summary(features)
    gates = _promotion_gate(features)
    curve = _load_curve()
    summary = _summary_row(features, inventory, product_year, gates, curve)

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    inventory.to_csv(INVENTORY_OUT, index=False, encoding="utf-8-sig")
    product_year.to_csv(PRODUCT_YEAR_OUT, index=False, encoding="utf-8-sig")
    rank_summary.to_csv(RANK_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    gates.to_csv(PROMOTION_GATE_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": summary["decision"],
        "line_id": LINE_ID,
        "created_at": summary["created_at"],
        "local_contract_panel_found": True,
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "order_api_called": False,
        "ctp_connected": False,
        "next_allowed_action": (
            "repair and provenance-lock missing contract-month OI panel, or run read-only predeclared "
            "hypothesis audit on panel_ready subset; no direct thresholds"
        ),
        "blocked_actions": [
            "rank/share/source-age/product-year threshold as trading rule",
            "true engine without >=95% target coverage and raw authority manifest",
            "A/B or official candidate",
            "product/year rescue filters",
        ],
        "summary": summary,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_path_chart(features, curve, product_year)
    _plot_product_year_heatmap(product_year)
    _plot_rank_share_chart(features, rank_summary)
    _plot_promotion_gate_chart(gates)
    _write_report(summary, inventory, product_year, rank_summary, gates)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
