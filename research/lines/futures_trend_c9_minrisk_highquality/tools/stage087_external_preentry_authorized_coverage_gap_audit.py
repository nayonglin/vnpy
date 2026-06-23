from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage087"
MODEL_TAG = "stage087_external_preentry_authorized_coverage_gap_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit"
ACCOUNT_CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
MAX_SIGNAL_AGE_DAYS = 7

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage087_external_preentry_authorized_coverage_gap_audit"
BACKTEST_OUTPUT_DIR = EXAMPLE_DIR / "backtest_outputs"

OFFICIAL_LOTS_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_closed_lots_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
OFFICIAL_CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
OFFICIAL_SUMMARY_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
MEMBER_RANK_IN = (
    BACKTEST_OUTPUT_DIR / "external_domestic_member_rank_cache" / "member_rank_sum_daily_20230101_20260417.csv"
)
BASIS_INPUTS = [
    BACKTEST_OUTPUT_DIR / "external_supply_demand_cache" / "supply_demand_basis_20200101_20221231.csv",
    BACKTEST_OUTPUT_DIR / "external_supply_demand_cache" / "supply_demand_basis_20230101_20260417.csv",
]
WAREHOUSE_INPUTS = [
    BACKTEST_OUTPUT_DIR / "external_supply_demand_cache" / "supply_demand_warehouse_20200101_20221231.csv",
    BACKTEST_OUTPUT_DIR / "external_supply_demand_cache" / "supply_demand_warehouse_20230101_20260417.csv",
]

LOT_COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_coverage_{MODEL_TAG}.csv"
PRODUCT_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_coverage_{MODEL_TAG}.csv"
YEAR_COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_coverage_{MODEL_TAG}.csv"
SOURCE_SCORECARD_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_scorecard_{MODEL_TAG}.csv"
LOCAL_ASSET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_asset_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_external_coverage_chart_{MODEL_TAG}.png"
PRODUCT_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_coverage_heatmap_{MODEL_TAG}.png"
MISSING_CONFLICT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_right_tail_conflict_chart_{MODEL_TAG}.png"
NEXT_ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_scorecard_{MODEL_TAG}.png"

SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "member_rank": {
        "label": "Member rank cache",
        "prior_stage": "Stage028/029/062/063",
        "prior_decision": "member_rank_data_engineering_first_no_rule",
        "next_action": "obtain full official or authorized member-rank history with raw query receipts and hashes",
        "official_sources_found": 1,
    },
    "basis": {
        "label": "Basis cache",
        "prior_stage": "Stage027/060",
        "prior_decision": "basis_direct_rule_closed_right_tail_conflict",
        "next_action": "validate or replace spot-basis cache with official or authorized point-in-time source",
        "official_sources_found": 0,
    },
    "warehouse": {
        "label": "Warehouse receipt cache",
        "prior_stage": "Stage027",
        "prior_decision": "warehouse_direct_rule_closed_right_tail_conflict",
        "next_action": "backfill official granular warehouse receipts for all C9 products and retain raw source hashes",
        "official_sources_found": 1,
    },
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
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return value


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


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


def _product_code_from_product(product: Any, vt_symbol: Any = "") -> str:
    raw = "" if pd.isna(product) else str(product).strip()
    if not raw and not pd.isna(vt_symbol):
        raw = str(vt_symbol).strip()
    base = raw.split(".", 1)[0]
    match = re.match(r"([A-Za-z]+)", base)
    return match.group(1).upper() if match else base.upper()


def _exchange_from_product(product: Any, vt_symbol: Any = "") -> str:
    raw = "" if pd.isna(product) else str(product).strip()
    if "." not in raw and not pd.isna(vt_symbol):
        raw = str(vt_symbol).strip()
    if "." not in raw:
        return "UNKNOWN"
    return raw.rsplit(".", 1)[1].upper()


def _load_official_lots() -> pd.DataFrame:
    lots = _read_csv(OFFICIAL_LOTS_IN)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    lots = lots.dropna(subset=["entry_date"]).copy()
    lots["lookup_date"] = lots["entry_date"] - pd.Timedelta(days=1)
    lots["product_code"] = [
        _product_code_from_product(product, vt_symbol)
        for product, vt_symbol in zip(lots.get("product", ""), lots.get("vt_symbol", ""), strict=False)
    ]
    lots["exchange"] = [
        _exchange_from_product(product, vt_symbol)
        for product, vt_symbol in zip(lots.get("product", ""), lots.get("vt_symbol", ""), strict=False)
    ]
    lots["entry_year"] = lots["entry_date"].dt.year.astype(int)
    lots["realized_pnl"] = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
    lots["winner"] = lots["realized_pnl"].gt(0.0)
    lots["big_winner"] = lots.get("big_winner", pd.Series(False, index=lots.index)).fillna(False).astype(bool)
    lots["lot_key"] = lots["lot_id"].astype(str)
    return lots.sort_values(["entry_date", "lot_id"]).reset_index(drop=True)


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "drawdown_pct",
        "slippage",
        "trade_count",
        "broker10_margin_to_equity_pct",
        "total_slippage",
    ]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    prev_equity = curve["account_equity"].shift(1)
    if not curve.empty:
        prev_equity.iloc[0] = ACCOUNT_CAPITAL
    curve["daily_return"] = (curve["account_equity"] / prev_equity - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _availability_from_member() -> pd.DataFrame:
    raw = _read_csv(MEMBER_RANK_IN, required=False)
    if raw.empty:
        return pd.DataFrame(columns=["source_id", "product_code", "source_date"])
    raw["product_code"] = raw["variety"].fillna("").astype(str).str.upper().str.strip()
    raw["source_date"] = pd.to_datetime(raw["date"].astype(str), format="%Y%m%d", errors="coerce")
    raw = raw.dropna(subset=["source_date"])
    out = raw[["product_code", "source_date"]].drop_duplicates().copy()
    out["source_id"] = "member_rank"
    return out[["source_id", "product_code", "source_date"]].sort_values(["product_code", "source_date"])


def _availability_from_basis() -> pd.DataFrame:
    frames = [_read_csv(path, required=False) for path in BASIS_INPUTS]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=["source_id", "product_code", "source_date"])
    raw = pd.concat(frames, ignore_index=True)
    raw["product_code"] = raw["symbol"].fillna("").astype(str).str.upper().str.strip()
    raw["source_date"] = pd.to_datetime(raw["date"].astype(str), errors="coerce")
    raw = raw.dropna(subset=["source_date"])
    out = raw[["product_code", "source_date"]].drop_duplicates().copy()
    out["source_id"] = "basis"
    return out[["source_id", "product_code", "source_date"]].sort_values(["product_code", "source_date"])


def _availability_from_warehouse() -> pd.DataFrame:
    frames = [_read_csv(path, required=False) for path in WAREHOUSE_INPUTS]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=["source_id", "product_code", "source_date"])
    raw = pd.concat(frames, ignore_index=True)
    raw["product_code"] = raw["product_code"].fillna("").astype(str).str.upper().str.strip()
    raw["source_date"] = pd.to_datetime(raw["date"].astype(str), errors="coerce")
    raw = raw.dropna(subset=["source_date"])
    out = raw[["product_code", "source_date"]].drop_duplicates().copy()
    out["source_id"] = "warehouse"
    return out[["source_id", "product_code", "source_date"]].sort_values(["product_code", "source_date"])


def _bind_one_source(lots: pd.DataFrame, availability: pd.DataFrame, source_id: str) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for product_code, group in lots.groupby("product_code", sort=False):
        left = group.sort_values("lookup_date").copy()
        right = availability[
            availability["source_id"].eq(source_id) & availability["product_code"].eq(product_code)
        ].sort_values("source_date")
        if right.empty:
            left[f"{source_id}_source_date"] = pd.NaT
            left[f"{source_id}_ready"] = False
            left[f"{source_id}_age_days"] = np.nan
            rows.append(left)
            continue
        merged = pd.merge_asof(
            left,
            right[["source_date"]],
            left_on="lookup_date",
            right_on="source_date",
            direction="backward",
            tolerance=pd.Timedelta(days=MAX_SIGNAL_AGE_DAYS),
        )
        merged[f"{source_id}_source_date"] = merged["source_date"]
        merged[f"{source_id}_ready"] = merged["source_date"].notna()
        merged[f"{source_id}_age_days"] = (merged["lookup_date"] - merged["source_date"]).dt.days
        merged = merged.drop(columns=["source_date"])
        rows.append(merged)
    return pd.concat(rows, ignore_index=True).sort_values(["entry_date", "lot_id"]).reset_index(drop=True)


def _bind_sources(lots: pd.DataFrame, availability: pd.DataFrame) -> pd.DataFrame:
    out = lots.copy()
    for source_id in SOURCE_SPECS:
        keep_cols = ["lot_id", f"{source_id}_source_date", f"{source_id}_ready", f"{source_id}_age_days"]
        bound = _bind_one_source(lots, availability, source_id)[keep_cols]
        out = out.merge(bound, on="lot_id", how="left")
        out[f"{source_id}_ready"] = out[f"{source_id}_ready"].fillna(False).astype(bool)
    ready_cols = [f"{source_id}_ready" for source_id in SOURCE_SPECS]
    out["any_external_ready"] = out[ready_cols].any(axis=1)
    out["all_external_ready"] = out[ready_cols].all(axis=1)
    out["ready_source_count"] = out[ready_cols].sum(axis=1).astype(int)
    return out


def _local_asset_summary(availability: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    raw_specs = {
        "member_rank": [MEMBER_RANK_IN],
        "basis": BASIS_INPUTS,
        "warehouse": WAREHOUSE_INPUTS,
    }
    for source_id, paths in raw_specs.items():
        source = availability[availability["source_id"].eq(source_id)]
        rows.append(
            {
                "source_id": source_id,
                "file_count": int(sum(path.exists() for path in paths)),
                "available_product_count": int(source["product_code"].nunique()) if not source.empty else 0,
                "available_date_count": int(source["source_date"].nunique()) if not source.empty else 0,
                "start_date": source["source_date"].min().strftime("%Y-%m-%d") if not source.empty else "",
                "end_date": source["source_date"].max().strftime("%Y-%m-%d") if not source.empty else "",
                "paths": "|".join(str(path.relative_to(REPO_DIR)) for path in paths if path.exists()),
            }
        )
    return pd.DataFrame(rows)


def _official_metrics(curve: pd.DataFrame, lots: pd.DataFrame) -> dict[str, float]:
    official_summary = _read_csv(OFFICIAL_SUMMARY_IN, required=False)
    official_row = official_summary.iloc[0].to_dict() if not official_summary.empty else {}

    def official_float(column: str, default: float) -> float:
        value = official_row.get(column, default)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return default if np.isnan(number) or np.isinf(number) else number

    returns = pd.to_numeric(curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    end = float(curve["account_equity"].iloc[-1]) if not curve.empty else ACCOUNT_CAPITAL
    total_slippage = official_float("total_slippage", float(curve["slippage"].sum()))
    return {
        "end_equity": end,
        "total_return_pct": (end / ACCOUNT_CAPITAL - 1.0) * 100.0,
        "max_dd_pct": float(curve["drawdown_pct"].min()) if not curve.empty else 0.0,
        "sharpe": official_float(
            "sharpe",
            (float(returns.mean()) / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0,
        ),
        "total_slippage": total_slippage,
        "total_trade_count": official_float(
            "total_trade_count",
            float(curve["trade_count"].sum()) if "trade_count" in curve.columns else 0.0,
        ),
        "win_rate_pct": official_float(
            "nonzero_daily_win_rate_pct",
            float(lots["winner"].mean() * 100.0) if not lots.empty else 0.0,
        ),
        "broker10_peak_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max())
        if not curve.empty
        else 0.0,
    }


def _coverage_stats(frame: pd.DataFrame, ready_col: str) -> dict[str, float]:
    ready = frame[ready_col].fillna(False).astype(bool)
    total_positive = float(frame.loc[frame["realized_pnl"].gt(0), "realized_pnl"].sum())
    total_abs_loss = float(-frame.loc[frame["realized_pnl"].lt(0), "realized_pnl"].sum())
    ready_positive = float(frame.loc[ready & frame["realized_pnl"].gt(0), "realized_pnl"].sum())
    missing_positive = float(frame.loc[(~ready) & frame["realized_pnl"].gt(0), "realized_pnl"].sum())
    ready_abs_loss = float(-frame.loc[ready & frame["realized_pnl"].lt(0), "realized_pnl"].sum())
    missing_abs_loss = float(-frame.loc[(~ready) & frame["realized_pnl"].lt(0), "realized_pnl"].sum())
    return {
        "lot_count": float(len(frame)),
        "ready_lot_count": float(ready.sum()),
        "ready_lot_pct": float(ready.mean() * 100.0) if len(frame) else 0.0,
        "ready_net_pnl": float(frame.loc[ready, "realized_pnl"].sum()),
        "missing_net_pnl": float(frame.loc[~ready, "realized_pnl"].sum()),
        "ready_positive_pnl": ready_positive,
        "missing_positive_pnl": missing_positive,
        "ready_abs_loss": ready_abs_loss,
        "missing_abs_loss": missing_abs_loss,
        "positive_pnl_coverage_pct": ready_positive / total_positive * 100.0 if total_positive else 0.0,
        "loss_abs_coverage_pct": ready_abs_loss / total_abs_loss * 100.0 if total_abs_loss else 0.0,
        "missing_big_winner_count": float(frame.loc[(~ready) & frame["big_winner"], "lot_id"].nunique()),
        "ready_big_winner_count": float(frame.loc[ready & frame["big_winner"], "lot_id"].nunique()),
    }


def _source_scorecard(lots: pd.DataFrame, availability: pd.DataFrame, local_assets: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_product_years = int(lots[["product_code", "entry_year"]].drop_duplicates().shape[0])
    for source_id, spec in SOURCE_SPECS.items():
        ready_col = f"{source_id}_ready"
        stats = _coverage_stats(lots, ready_col)
        source_avail = availability[availability["source_id"].eq(source_id)]
        asset = local_assets[local_assets["source_id"].eq(source_id)]
        start_date = str(asset.iloc[0]["start_date"]) if not asset.empty else ""
        end_date = str(asset.iloc[0]["end_date"]) if not asset.empty else ""
        product_year = (
            lots.groupby(["product_code", "entry_year"], as_index=False)
            .agg(lot_count=("lot_id", "count"), ready_lot_count=(ready_col, "sum"))
        )
        ready_product_years = int(product_year[product_year["ready_lot_count"].eq(product_year["lot_count"])].shape[0])
        full_history_product_coverage = int(stats["ready_lot_pct"] >= 95.0 and ready_product_years == total_product_years)
        right_tail_missing_safe = int(stats["missing_big_winner_count"] == 0 and stats["missing_positive_pnl"] <= 0.0)
        gates = {
            "local_cache_present": int(not source_avail.empty),
            "point_in_time_key": 1,
            "preentry_bindable": int(stats["ready_lot_count"] > 0),
            "full_history_product_coverage": full_history_product_coverage,
            "official_or_authorized_provenance_validated": 0,
            "prior_not_closed": 0,
            "right_tail_missing_safe": right_tail_missing_safe,
        }
        pass_count = int(sum(gates.values()))
        gate_total = int(len(gates) + 1)
        rule_allowed = int(pass_count == len(gates))
        rows.append(
            {
                "source_id": source_id,
                "label": spec["label"],
                "local_start_date": start_date,
                "local_end_date": end_date,
                "local_product_count": int(source_avail["product_code"].nunique()) if not source_avail.empty else 0,
                "local_date_count": int(source_avail["source_date"].nunique()) if not source_avail.empty else 0,
                "c9_lot_count": int(len(lots)),
                "c9_product_year_count": total_product_years,
                "full_ready_product_year_count": ready_product_years,
                "official_sources_found_online": int(spec["official_sources_found"]),
                "max_signal_age_days": MAX_SIGNAL_AGE_DAYS,
                "prior_stage": spec["prior_stage"],
                "prior_decision": spec["prior_decision"],
                **gates,
                "rule_candidate_allowed": rule_allowed,
                "gate_pass_count": pass_count,
                "gate_total_count": gate_total,
                "readiness_score_pct": pass_count / gate_total * 100.0,
                "next_action": spec["next_action"],
                **stats,
            }
        )
    return pd.DataFrame(rows).sort_values(["rule_candidate_allowed", "readiness_score_pct"], ascending=[False, False])


def _product_year_coverage(lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (product_code, exchange, entry_year), group in lots.groupby(["product_code", "exchange", "entry_year"], sort=True):
        base = {
            "product_code": product_code,
            "exchange": exchange,
            "entry_year": int(entry_year),
            "lot_count": int(len(group)),
            "net_pnl": float(group["realized_pnl"].sum()),
            "positive_pnl": float(group.loc[group["realized_pnl"].gt(0), "realized_pnl"].sum()),
            "abs_loss": float(-group.loc[group["realized_pnl"].lt(0), "realized_pnl"].sum()),
            "big_winner_count": int(group["big_winner"].sum()),
        }
        for source_id in SOURCE_SPECS:
            ready_col = f"{source_id}_ready"
            ready = group[ready_col].fillna(False).astype(bool)
            base[f"{source_id}_ready_lot_count"] = int(ready.sum())
            base[f"{source_id}_ready_pct"] = float(ready.mean() * 100.0) if len(group) else 0.0
            base[f"{source_id}_missing_net_pnl"] = float(group.loc[~ready, "realized_pnl"].sum())
            base[f"{source_id}_missing_positive_pnl"] = float(
                group.loc[(~ready) & group["realized_pnl"].gt(0), "realized_pnl"].sum()
            )
            base[f"{source_id}_missing_big_winner_count"] = int((~ready & group["big_winner"]).sum())
        rows.append(base)
    return pd.DataFrame(rows)


def _year_coverage(lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for entry_year, group in lots.groupby("entry_year", sort=True):
        row = {
            "entry_year": int(entry_year),
            "lot_count": int(len(group)),
            "net_pnl": float(group["realized_pnl"].sum()),
            "positive_pnl": float(group.loc[group["realized_pnl"].gt(0), "realized_pnl"].sum()),
            "big_winner_count": int(group["big_winner"].sum()),
        }
        for source_id in SOURCE_SPECS:
            ready = group[f"{source_id}_ready"].fillna(False).astype(bool)
            row[f"{source_id}_ready_pct"] = float(ready.mean() * 100.0) if len(group) else 0.0
            row[f"{source_id}_missing_net_pnl"] = float(group.loc[~ready, "realized_pnl"].sum())
            row[f"{source_id}_missing_big_winner_count"] = int((~ready & group["big_winner"]).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def _summary(curve: pd.DataFrame, lots: pd.DataFrame, scorecard: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve, lots)
    allowed = int(scorecard["rule_candidate_allowed"].sum())
    best = scorecard.sort_values("readiness_score_pct", ascending=False).head(1)
    best_source = str(best.iloc[0]["source_id"]) if not best.empty else ""
    any_ready = _coverage_stats(lots, "any_external_ready")
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "decision": "stage087_external_cache_not_authorized_fullcoverage_no_rule",
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "source_count": int(len(scorecard)),
                "rule_candidate_allowed_source_count": allowed,
                "best_source_by_readiness": best_source,
                "any_external_ready_lot_pct": any_ready["ready_lot_pct"],
                "any_external_missing_positive_pnl": any_ready["missing_positive_pnl"],
                "any_external_missing_big_winner_count": any_ready["missing_big_winner_count"],
                **metrics,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, lots: pd.DataFrame, scorecard: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(14, 11), sharex=False, gridspec_kw={"height_ratios": [2.0, 1.2, 1.2, 1.2]})
    ax = axes[0]
    ax.plot(curve["date"], curve["account_equity"], color="#0f766e", linewidth=1.6, label="official equity")
    ax.set_title("Stage087 official C9/15w path with external coverage gates")
    ax.set_ylabel("equity")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")

    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.2)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)

    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#7c3aed", linewidth=1.2)
    axes[2].axhline(100.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    axes[2].grid(True, alpha=0.25)

    yearly = _year_coverage(lots)
    x = np.arange(len(yearly))
    width = 0.24
    colors = {"member_rank": "#2563eb", "basis": "#f97316", "warehouse": "#16a34a"}
    for offset, source_id in zip([-width, 0.0, width], SOURCE_SPECS, strict=False):
        axes[3].bar(x + offset, yearly[f"{source_id}_ready_pct"], width=width, color=colors[source_id], label=source_id)
    axes[3].set_xticks(x)
    axes[3].set_xticklabels(yearly["entry_year"].astype(str).tolist(), rotation=0)
    axes[3].set_ylim(0, 105)
    axes[3].set_ylabel("ready lots %")
    axes[3].grid(True, axis="y", alpha=0.25)
    axes[3].legend(loc="upper left", ncols=3)

    allowed = int(scorecard["rule_candidate_allowed"].sum())
    fig.suptitle(f"External sources allowed as rule candidates: {allowed}/{len(scorecard)}", y=0.995, fontsize=13)
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year_heatmap(product_year: pd.DataFrame) -> None:
    sources = list(SOURCE_SPECS.keys())
    fig, axes = plt.subplots(len(sources), 1, figsize=(15, 11), sharex=True)
    if len(sources) == 1:
        axes = [axes]
    products = sorted(product_year["product_code"].unique())
    years = sorted(product_year["entry_year"].unique())
    for ax, source_id in zip(axes, sources, strict=False):
        pivot = product_year.pivot_table(
            index="product_code",
            columns="entry_year",
            values=f"{source_id}_ready_pct",
            aggfunc="mean",
        ).reindex(index=products, columns=years)
        data = pivot.to_numpy(dtype=float)
        masked = np.ma.masked_invalid(data)
        im = ax.imshow(masked, aspect="auto", vmin=0, vmax=100, cmap="RdYlGn")
        ax.set_yticks(np.arange(len(products)))
        ax.set_yticklabels(products, fontsize=8)
        ax.set_title(f"{source_id} point-in-time ready % by product-year")
        ax.set_xticks(np.arange(len(years)))
        ax.set_xticklabels([str(year) for year in years], rotation=0)
        for i in range(len(products)):
            for j in range(len(years)):
                value = pivot.iloc[i, j]
                if pd.notna(value):
                    ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="#111827")
        fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01)
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_missing_conflict(scorecard: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    data = scorecard.sort_values("source_id").copy()
    x = np.arange(len(data))
    axes[0].bar(x - 0.18, data["ready_net_pnl"] / 1_000_000.0, width=0.36, color="#16a34a", label="ready net pnl")
    axes[0].bar(x + 0.18, data["missing_net_pnl"] / 1_000_000.0, width=0.36, color="#dc2626", label="missing net pnl")
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(data["source_id"], rotation=20, ha="right")
    axes[0].set_ylabel("million CNY")
    axes[0].set_title("Ready vs missing net PnL")
    axes[0].legend()
    axes[0].grid(True, axis="y", alpha=0.25)

    axes[1].bar(x - 0.18, data["missing_positive_pnl"] / 1_000_000.0, width=0.36, color="#f59e0b", label="missing positive pnl")
    axes[1].bar(x + 0.18, data["missing_big_winner_count"], width=0.36, color="#7c3aed", label="missing big winners")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["source_id"], rotation=20, ha="right")
    axes[1].set_title("Right-tail conflict inside missing coverage")
    axes[1].legend()
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(MISSING_CONFLICT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_next_action(scorecard: pd.DataFrame) -> None:
    gates = [
        "local_cache_present",
        "point_in_time_key",
        "preentry_bindable",
        "full_history_product_coverage",
        "official_or_authorized_provenance_validated",
        "prior_not_closed",
        "right_tail_missing_safe",
        "rule_candidate_allowed",
    ]
    data = scorecard.set_index("source_id")[gates].astype(float)
    fig, ax = plt.subplots(figsize=(12, 4.8))
    im = ax.imshow(data.to_numpy(), aspect="auto", vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks(np.arange(len(gates)))
    ax.set_xticklabels(gates, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index.tolist())
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, str(int(data.iloc[i, j])), ha="center", va="center", fontsize=9, color="#111827")
    ax.set_title("Stage087 source gate scorecard: 1=pass, 0=blocked")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(NEXT_ACTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, scorecard: pd.DataFrame, local_assets: pd.DataFrame, product_year: pd.DataFrame) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} external preentry authorized coverage gap audit",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            f"- official: `{OFFICIAL_LIVE_ALIAS}` / `{OFFICIAL_LIVE_VERSION}`",
            "- nature: read-only data engineering audit; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "",
            "## Official baseline",
            "",
            f"- end equity: `{row['end_equity']:,.2f}`",
            f"- total return: `{row['total_return_pct']:.4f}%`",
            f"- max drawdown: `{row['max_dd_pct']:.4f}%`",
            f"- Sharpe: `{row['sharpe']:.4f}`",
            f"- total slippage: `{row['total_slippage']:,.0f}`",
            f"- total trade count: `{row['total_trade_count']:.0f}`",
            f"- win rate (closed lots): `{row['win_rate_pct']:.4f}%`",
            f"- broker10 peak margin/equity: `{row['broker10_peak_margin_to_equity_pct']:.4f}%`",
            "",
            "## Coverage scorecard",
            "",
            _md_table(
                scorecard[
                    [
                        "source_id",
                        "local_start_date",
                        "local_end_date",
                        "ready_lot_pct",
                        "positive_pnl_coverage_pct",
                        "missing_positive_pnl",
                        "missing_big_winner_count",
                        "readiness_score_pct",
                        "rule_candidate_allowed",
                    ]
                ]
            ),
            "",
            "## Local asset summary",
            "",
            _md_table(local_assets),
            "",
            "## Visual outputs",
            "",
            f"- official path and year coverage: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- product-year coverage heatmap: `{PRODUCT_YEAR_HEATMAP_OUT}`",
            f"- missing right-tail conflict chart: `{MISSING_CONFLICT_CHART_OUT}`",
            f"- next-action gate chart: `{NEXT_ACTION_CHART_OUT}`",
            "",
            "## Visual judgment",
            "",
            "- The official equity curve still contains the target drawdown and broker10 spikes, but none of the external caches is allowed to become a rule source.",
            "- Member rank coverage starts only in 2023, so the 2018-2022 right-tail and drawdown context is unobserved by this local cache.",
            "- Basis coverage is broad after 2020, but 2018-2019 are absent and the cache is not validated as an authorized raw source.",
            "- Warehouse coverage is sparse by product/exchange and leaves major right-tail contribution in the missing bucket.",
            "",
            "## External source research used",
            "",
            "- SHFE official daily data / daily warrant page: https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/?query_params=dailystock",
            "- CZCE official position ranking page: https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm",
            "- CZCE official warehouse receipt page: https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm",
            "- DCE official daily position ranking page: https://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/rcjccpm/index.html",
            "- DCE official warehouse receipt page: https://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/cdrb/index.html",
            "- GFEX official daily position ranking page: https://www.gfex.com.cn/gfex/rcjccpm/hqsj_tjsj.shtml",
            "- GFEX official warehouse receipt page: https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml",
            "- AKShare futures data docs for exchange warehouse receipt interfaces: https://akshare.akfamily.xyz/data/futures/futures.html",
            "",
            "## Anti-overfit judgment",
            "",
            "- Before run: no overfit. The audit freezes a source-readiness gate and does not create a signal from historical winners or losers.",
            "- After run: no overfit. The result is a stop/go data-provenance decision; it rejects under-covered sources rather than fitting thresholds.",
            "",
            "## Continue-value judgment",
            "",
            "- Before run: yes. External point-in-time data is the remaining path after internal minute, tick, and account-layer routes were closed.",
            "- After run: yes, but only as data engineering. The next valuable work is to acquire or validate official/authorized raw histories, not to tune rules on the current cache.",
            "",
            "## Key files",
            "",
            f"- lot coverage: `{LOT_COVERAGE_OUT}`",
            f"- product-year coverage: `{PRODUCT_YEAR_OUT}`",
            f"- source scorecard: `{SOURCE_SCORECARD_OUT}`",
            f"- summary: `{SUMMARY_OUT}`",
            f"- decision: `{DECISION_OUT}`",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = _load_official_lots()
    curve = _load_official_curve()
    availability = pd.concat(
        [_availability_from_member(), _availability_from_basis(), _availability_from_warehouse()],
        ignore_index=True,
    )
    local_assets = _local_asset_summary(availability)
    lot_coverage = _bind_sources(lots, availability)
    product_year = _product_year_coverage(lot_coverage)
    year_coverage = _year_coverage(lot_coverage)
    scorecard = _source_scorecard(lot_coverage, availability, local_assets)
    summary = _summary(curve, lot_coverage, scorecard)

    _write_csv(lot_coverage, LOT_COVERAGE_OUT)
    _write_csv(product_year, PRODUCT_YEAR_OUT)
    _write_csv(year_coverage, YEAR_COVERAGE_OUT)
    _write_csv(scorecard, SOURCE_SCORECARD_OUT)
    _write_csv(local_assets, LOCAL_ASSET_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    _plot_official_path(curve, lot_coverage, scorecard)
    _plot_product_year_heatmap(product_year)
    _plot_missing_conflict(scorecard)
    _plot_next_action(scorecard)
    _write_report(summary, scorecard, local_assets, product_year)

    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
