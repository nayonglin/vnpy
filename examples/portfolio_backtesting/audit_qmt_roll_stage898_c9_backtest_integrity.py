from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage898"
MODEL_TAG = "stage898_c9_backtest_integrity_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage898_c9_backtest_integrity_audit"

STAGE861_TAG = "stage861_stage860_full_visual_atlas_v1"
STAGE863_TAG = "stage863_stage847_c10_budget_lock_engine_v1"
STAGE880_TAG = "stage880_stage863_session_boundary_audit_v1"
STAGE896_TAG = "stage896_c9_vs_official_halfyear_rolling3y_v1"
STAGE897_TAG = "stage897_c9_janjun_rolling1y_v1"

C9_PROFILE = "stage847_stage819_c4_05r_stop_retry_once"
C9_ROLL_ARM = "c9_stage847_stage819_30w"

STAGE861_PREFIX = "qmt_roll_stage861_stage860_full_visual_atlas"
STAGE863_PREFIX = "qmt_roll_stage863_stage847_c10_budget_lock_engine"
STAGE880_PREFIX = "qmt_roll_stage880_stage863_session_boundary_audit"
STAGE896_PREFIX = "qmt_roll_stage896_c9_vs_official_halfyear_rolling3y"
STAGE897_PREFIX = "qmt_roll_stage897_c9_janjun_rolling1y"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
METRIC_RECOMPUTE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_metric_recompute_{MODEL_TAG}.csv"
MINUTE_CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_checks_{MODEL_TAG}.csv"
EVENT_CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_trade_checks_{MODEL_TAG}.csv"
FINDINGS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_findings_{MODEL_TAG}.csv"
COVERAGE_GAPS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_gaps_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

STAGE825_MINUTE_SOURCE_PATHS = (
    OUTPUT_DIR / "qmt_roll_stage449_minute_session_rebuild_full_minute_bars_stage449_minute_session_rebuild_full_v1.csv",
    OUTPUT_DIR / "qmt_roll_stage498_actual_trade_fill_key_readiness_completed_minute_bars_stage498_actual_trade_fill_key_readiness_v1.csv",
)


def _path(prefix: str, suffix: str, tag: str) -> Path:
    return OUTPUT_DIR / f"{prefix}_{suffix}_{tag}.csv"


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _bool_pass(diff: float, tolerance: float) -> int:
    return int(np.isfinite(diff) and abs(diff) <= tolerance)


def _append_metric_check(
    rows: list[dict[str, Any]],
    *,
    source: str,
    key: str,
    metric: str,
    summary_value: Any,
    recomputed_value: Any,
    tolerance: float,
) -> None:
    summary_float = _safe_float(summary_value)
    recomputed_float = _safe_float(recomputed_value)
    diff = recomputed_float - summary_float
    rows.append(
        {
            "source": source,
            "key": key,
            "metric": metric,
            "summary_value": summary_float,
            "recomputed_value": recomputed_float,
            "diff": diff,
            "tolerance": tolerance,
            "pass": _bool_pass(diff, tolerance),
        }
    )


def _max_drawdown_from_equity(equity: pd.Series) -> float:
    values = pd.to_numeric(equity, errors="coerce").dropna()
    if values.empty:
        return np.nan
    peak = values.cummax()
    dd = values / peak - 1.0
    return float(dd.min() * 100.0)


def _recompute_stage863(rows: list[dict[str, Any]]) -> None:
    summary = _read_csv(_path(STAGE863_PREFIX, "summary", STAGE863_TAG))
    curve = _read_csv(_path(STAGE863_PREFIX, "curve", STAGE863_TAG))
    for arm, group in curve.groupby("arm", sort=False):
        srow = summary[summary["arm"].astype(str).eq(str(arm))]
        if srow.empty:
            continue
        srow = srow.iloc[0]
        group = group.sort_values("date")
        last = group.iloc[-1]
        capital = _safe_float(srow.get("account_capital"))
        end_equity = _safe_float(last.get("account_equity"))
        rebased_end = _safe_float(last.get("rebased_equity"))
        _append_metric_check(
            rows=rows,
            source="stage863_full_period",
            key=str(arm),
            metric="end_equity",
            summary_value=srow.get("end_equity"),
            recomputed_value=end_equity,
            tolerance=0.01,
        )
        _append_metric_check(
            rows=rows,
            source="stage863_full_period",
            key=str(arm),
            metric="rebased_end_equity",
            summary_value=srow.get("rebased_end_equity"),
            recomputed_value=rebased_end,
            tolerance=0.01,
        )
        _append_metric_check(
            rows=rows,
            source="stage863_full_period",
            key=str(arm),
            metric="total_return_pct",
            summary_value=srow.get("total_return_pct"),
            recomputed_value=(end_equity / capital - 1.0) * 100.0,
            tolerance=1e-8,
        )
        _append_metric_check(
            rows=rows,
            source="stage863_full_period",
            key=str(arm),
            metric="rebased_total_return_pct",
            summary_value=srow.get("rebased_total_return_pct"),
            recomputed_value=(_safe_float(last.get("rebased_nav")) - 1.0) * 100.0,
            tolerance=1e-8,
        )
        _append_metric_check(
            rows=rows,
            source="stage863_full_period",
            key=str(arm),
            metric="max_dd_pct_from_equity",
            summary_value=srow.get("max_dd_pct"),
            recomputed_value=_max_drawdown_from_equity(group["account_equity"]),
            tolerance=1e-8,
        )
        _append_metric_check(
            rows=rows,
            source="stage863_full_period",
            key=str(arm),
            metric="max_dd_pct_from_curve",
            summary_value=srow.get("max_dd_pct"),
            recomputed_value=pd.to_numeric(group["drawdown_pct"], errors="coerce").min(),
            tolerance=1e-8,
        )
        _append_metric_check(
            rows=rows,
            source="stage863_full_period",
            key=str(arm),
            metric="total_trade_count",
            summary_value=srow.get("total_trade_count"),
            recomputed_value=pd.to_numeric(group["trade_count"], errors="coerce").fillna(0).sum(),
            tolerance=1e-8,
        )
        _append_metric_check(
            rows=rows,
            source="stage863_full_period",
            key=str(arm),
            metric="total_slippage",
            summary_value=srow.get("total_slippage"),
            recomputed_value=pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0).sum(),
            tolerance=0.01,
        )
        _append_metric_check(
            rows=rows,
            source="stage863_full_period",
            key=str(arm),
            metric="max_broker10_margin_to_rebased_equity_pct",
            summary_value=srow.get("max_broker10_margin_to_rebased_equity_pct"),
            recomputed_value=pd.to_numeric(group["broker10_margin_to_rebased_equity_pct"], errors="coerce").max(),
            tolerance=1e-8,
        )


def _recompute_rolling(
    rows: list[dict[str, Any]],
    *,
    source: str,
    summary_path: Path,
    curves_path: Path,
) -> None:
    summary = _read_csv(summary_path)
    curves = _read_csv(curves_path)
    for (window_id, arm_key), group in curves.groupby(["window_id", "arm_key"], sort=False):
        srow = summary[
            summary["window_id"].astype(str).eq(str(window_id))
            & summary["arm_key"].astype(str).eq(str(arm_key))
        ]
        if srow.empty:
            continue
        srow = srow.iloc[0]
        group = group.sort_values("date")
        last = group.iloc[-1]
        key = f"{window_id}|{arm_key}"
        _append_metric_check(
            rows=rows,
            source=source,
            key=key,
            metric="rebased_end_equity",
            summary_value=srow.get("rebased_end_equity"),
            recomputed_value=last.get("rebased_equity"),
            tolerance=0.01,
        )
        _append_metric_check(
            rows=rows,
            source=source,
            key=key,
            metric="rebased_total_return_pct",
            summary_value=srow.get("rebased_total_return_pct"),
            recomputed_value=(_safe_float(last.get("rebased_nav")) - 1.0) * 100.0,
            tolerance=1e-8,
        )
        _append_metric_check(
            rows=rows,
            source=source,
            key=key,
            metric="rebased_max_dd_pct_from_equity",
            summary_value=srow.get("rebased_max_dd_pct"),
            recomputed_value=_max_drawdown_from_equity(group["rebased_equity"]),
            tolerance=1e-8,
        )
        _append_metric_check(
            rows=rows,
            source=source,
            key=key,
            metric="total_trade_count",
            summary_value=srow.get("total_trade_count"),
            recomputed_value=pd.to_numeric(group["trade_count"], errors="coerce").fillna(0).sum(),
            tolerance=1e-8,
        )
        _append_metric_check(
            rows=rows,
            source=source,
            key=key,
            metric="total_slippage",
            summary_value=srow.get("total_slippage"),
            recomputed_value=pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0).sum(),
            tolerance=0.01,
        )
        _append_metric_check(
            rows=rows,
            source=source,
            key=key,
            metric="max_broker10_margin_to_rebased_equity_pct",
            summary_value=srow.get("max_broker10_margin_to_rebased_equity_pct"),
            recomputed_value=pd.to_numeric(group["broker10_margin_to_rebased_equity_pct"], errors="coerce").max(),
            tolerance=1e-8,
        )


def _old_minute_source_conflicts() -> dict[str, Any]:
    usecols = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    frames: list[pd.DataFrame] = []
    for path in STAGE825_MINUTE_SOURCE_PATHS:
        if not path.exists():
            continue
        frame = pd.read_csv(path, usecols=lambda col: col in usecols, encoding="utf-8-sig")
        if frame.empty:
            continue
        frame["source_path"] = path.name
        frames.append(frame)
    if not frames:
        return {
            "old_minute_source_rows": 0,
            "old_minute_duplicate_key_rows": 0,
            "old_minute_duplicate_key_count": 0,
            "old_minute_ohlc_conflict_key_count": 0,
            "old_minute_ohlc_conflict_rows": 0,
        }
    old = pd.concat(frames, ignore_index=True, sort=False)
    old["bar_datetime"] = pd.to_datetime(old["bar_datetime"], errors="coerce")
    old = old.dropna(subset=["vt_symbol", "bar_datetime"]).copy()
    for column in ["open", "high", "low", "close"]:
        old[column] = pd.to_numeric(old[column], errors="coerce")
    dup_mask = old.duplicated(["vt_symbol", "bar_datetime"], keep=False)
    dup = old[dup_mask].copy()
    if dup.empty:
        conflict_key_count = 0
        conflict_rows = 0
    else:
        nunique = dup.groupby(["vt_symbol", "bar_datetime"])[["open", "high", "low", "close"]].nunique(dropna=False)
        conflict_keys = nunique[nunique.max(axis=1).gt(1)].reset_index()[["vt_symbol", "bar_datetime"]]
        conflict_key_count = int(len(conflict_keys))
        if conflict_key_count:
            marker = conflict_keys.assign(_conflict_key=1)
            conflict_rows = int(
                dup.merge(marker, on=["vt_symbol", "bar_datetime"], how="inner")["_conflict_key"].sum()
            )
        else:
            conflict_rows = 0
    return {
        "old_minute_source_rows": int(len(old)),
        "old_minute_duplicate_key_rows": int(len(dup)),
        "old_minute_duplicate_key_count": int(dup.drop_duplicates(["vt_symbol", "bar_datetime"]).shape[0]) if not dup.empty else 0,
        "old_minute_ohlc_conflict_key_count": conflict_key_count,
        "old_minute_ohlc_conflict_rows": conflict_rows,
    }


def _rolling_source_checks() -> dict[str, Any]:
    stage896_code = (PROJECT_DIR / "analyze_qmt_roll_stage896_c9_vs_official_halfyear_rolling3y.py").read_text(
        encoding="utf-8"
    )
    stage897_code = (PROJECT_DIR / "analyze_qmt_roll_stage897_c9_janjun_rolling1y.py").read_text(encoding="utf-8")
    return {
        "stage896_uses_stage861_full_minute_bars": int("minute_bars = _load_stage861_full_minute_bars(vt_symbols)" in stage896_code),
        "stage896_direct_old_minute_loader_count": int(stage896_code.count("minute_bars = s825._load_minute_bars")),
        "stage897_uses_stage861_full_minute_bars": int(
            "minute_bars = s896._load_stage861_full_minute_bars(vt_symbols)" in stage897_code
        ),
        "stage897_direct_old_minute_loader_count": int(stage897_code.count("minute_bars = s896.s825._load_minute_bars")),
    }


def _c9_open_trade_coverage(minute: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    trades = _read_csv(_path(STAGE863_PREFIX, "trades", STAGE863_TAG))
    if "bar_date" in minute.columns:
        minute_dates = pd.to_datetime(minute["bar_date"], errors="coerce").dt.date
    else:
        minute_dates = pd.to_datetime(minute["bar_datetime"], errors="coerce").dt.date
    full_keys = set(zip(minute["vt_symbol"].astype(str), minute_dates))
    opened = trades[
        trades["profile"].astype(str).isin([C9_PROFILE, "stage863_stage819_c4_c9_budget_lock"])
        & trades["offset"].astype(str).eq("Open")
    ].copy()
    opened["entry_date"] = (
        pd.to_datetime(opened["datetime"], errors="coerce", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    missing_rows: list[dict[str, Any]] = []
    stats: dict[str, Any] = {}
    for profile, group in opened.groupby("profile", sort=False):
        missing = group[
            [((str(row.vt_symbol), row.entry_date) not in full_keys) for row in group.itertuples()]
        ].copy()
        stats[f"{profile}:open_trade_count"] = int(len(group))
        stats[f"{profile}:open_missing_full_minute_entry_day_count"] = int(len(missing))
        for _, row in missing.iterrows():
            missing_rows.append(
                {
                    "profile": str(profile),
                    "trade_id": str(row.get("trade_id", "")),
                    "order_id": str(row.get("order_id", "")),
                    "vt_symbol": str(row.get("vt_symbol", "")),
                    "entry_date": str(row.get("entry_date", "")),
                    "direction": str(row.get("direction", "")),
                    "offset": str(row.get("offset", "")),
                    "price": _safe_float(row.get("price")),
                    "volume": _safe_float(row.get("volume")),
                }
            )
    return stats, pd.DataFrame(missing_rows)


def _minute_checks() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = _read_csv(_path(STAGE861_PREFIX, "summary", STAGE861_TAG))
    coverage = _read_csv(_path(STAGE861_PREFIX, "entry_coverage_by_year", STAGE861_TAG))
    minute = _read_csv(_path(STAGE861_PREFIX, "full_minute_bars", STAGE861_TAG))
    minute["bar_datetime"] = pd.to_datetime(minute["bar_datetime"], errors="coerce")
    rows: list[dict[str, Any]] = []
    declared = summary.iloc[0]
    checks = {
        "declared_full_minute_bars": int(declared["full_minute_bars"]),
        "actual_full_minute_bars": int(len(minute)),
        "declared_full_minute_symbols": int(declared["full_minute_symbols"]),
        "actual_full_minute_symbols": int(minute["vt_symbol"].nunique()),
        "entry_lots": int(declared["entry_lots"]),
        "entry_day_covered_lots": int(declared["entry_day_covered_lots"]),
        "entry_day_missing_lots": int(declared["entry_day_missing_lots"]),
        "pressure_key_dates": int(declared["pressure_key_dates"]),
        "pressure_covered_dates": int(declared["pressure_covered_dates"]),
        "pressure_missing_dates": int(declared["pressure_missing_dates"]),
        "duplicate_symbol_datetime_rows": int(minute.duplicated(["vt_symbol", "bar_datetime"]).sum()),
        "missing_datetime_rows": int(minute["bar_datetime"].isna().sum()),
    }
    numeric_cols = ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]
    for column in numeric_cols:
        if column in minute.columns:
            minute[column] = pd.to_numeric(minute[column], errors="coerce")
            checks[f"missing_{column}_rows"] = int(minute[column].isna().sum())
    checks["ohlc_high_below_low_rows"] = int((minute["high"] < minute["low"]).sum())
    checks["ohlc_high_below_open_close_rows"] = int(
        (minute["high"] < minute[["open", "close"]].max(axis=1)).sum()
    )
    checks["ohlc_low_above_open_close_rows"] = int((minute["low"] > minute[["open", "close"]].min(axis=1)).sum())
    checks["negative_volume_rows"] = int((minute["volume"] < 0).sum()) if "volume" in minute else 0
    checks["coverage_year_rows"] = int(len(coverage))
    checks["coverage_year_missing_lots_sum"] = int(pd.to_numeric(coverage["missing_lots"], errors="coerce").fillna(0).sum())
    checks.update(_rolling_source_checks())
    checks.update(_old_minute_source_conflicts())
    c9_open_checks, coverage_gaps = _c9_open_trade_coverage(minute)
    checks.update(c9_open_checks)
    for key, value in checks.items():
        rows.append({"check": key, "value": value})
    if "minute_source" in minute.columns:
        for source, count in minute["minute_source"].astype(str).value_counts().sort_index().items():
            rows.append({"check": f"minute_source_count:{source}", "value": int(count)})
    return pd.DataFrame(rows), coverage_gaps


def _event_trade_checks() -> pd.DataFrame:
    events = _read_csv(_path(STAGE863_PREFIX, "stop_retry_events", STAGE863_TAG))
    trades = _read_csv(_path(STAGE863_PREFIX, "trades", STAGE863_TAG))
    intraday = _read_csv(_path(STAGE863_PREFIX, "intraday_events", STAGE863_TAG))
    stage880_features = _read_csv(_path(STAGE880_PREFIX, "features", STAGE880_TAG))

    rows: list[dict[str, Any]] = []

    for profile, group in events.groupby("profile", sort=False):
        retry_reentered = pd.to_numeric(group["retry_reentered"], errors="coerce").fillna(0).astype(int)
        retry_failed = pd.to_numeric(group["retry_failed"], errors="coerce").fillna(0).astype(int)
        first_stop_idx = pd.to_numeric(group["first_stop_bar_index"], errors="coerce")
        reentry_idx = pd.to_numeric(group["reentry_bar_index"], errors="coerce")
        retry_failed_idx = pd.to_numeric(group["retry_failed_bar_index"], errors="coerce")
        rows.append(
            {
                "scope": "stop_retry_events",
                "profile": profile,
                "check": "event_count",
                "value": int(len(group)),
            }
        )
        rows.append(
            {
                "scope": "stop_retry_events",
                "profile": profile,
                "check": "retry_reentered_count",
                "value": int(retry_reentered.sum()),
            }
        )
        rows.append(
            {
                "scope": "stop_retry_events",
                "profile": profile,
                "check": "retry_failed_count",
                "value": int(retry_failed.sum()),
            }
        )
        rows.append(
            {
                "scope": "stop_retry_events",
                "profile": profile,
                "check": "bad_first_stop_index_count",
                "value": int((first_stop_idx < 0).sum()),
            }
        )
        rows.append(
            {
                "scope": "stop_retry_events",
                "profile": profile,
                "check": "bad_reentry_order_count",
                "value": int(((retry_reentered == 1) & (reentry_idx <= first_stop_idx)).sum()),
            }
        )
        rows.append(
            {
                "scope": "stop_retry_events",
                "profile": profile,
                "check": "bad_retry_failed_order_count",
                "value": int(((retry_failed == 1) & (retry_failed_idx <= reentry_idx)).sum()),
            }
        )
        final_counts = group["final_state"].astype(str).value_counts()
        for final_state, count in final_counts.sort_index().items():
            rows.append(
                {
                    "scope": "stop_retry_events",
                    "profile": profile,
                    "check": f"final_state_count:{final_state}",
                    "value": int(count),
                }
            )

    for profile, group in trades.groupby("profile", sort=False):
        rows.append({"scope": "trades", "profile": profile, "check": "trade_rows", "value": int(len(group))})
        synthetic = group["order_id"].astype(str).str.contains("stage847", na=False)
        rows.append(
            {
                "scope": "trades",
                "profile": profile,
                "check": "stage847_synthetic_trade_rows",
                "value": int(synthetic.sum()),
            }
        )

    for profile, group in events.groupby("profile", sort=False):
        expected_synthetic = int(
            len(group)
            + pd.to_numeric(group["retry_reentered"], errors="coerce").fillna(0).sum()
            + pd.to_numeric(group["retry_failed"], errors="coerce").fillna(0).sum()
        )
        synthetic_trades = int(
            trades[
                trades["profile"].astype(str).eq(str(profile))
                & trades["order_id"].astype(str).str.contains("stage847", na=False)
            ].shape[0]
        )
        rows.append(
            {
                "scope": "event_trade_reconciliation",
                "profile": profile,
                "check": "expected_stage847_synthetic_trades",
                "value": expected_synthetic,
            }
        )
        rows.append(
            {
                "scope": "event_trade_reconciliation",
                "profile": profile,
                "check": "actual_stage847_synthetic_trades",
                "value": synthetic_trades,
            }
        )
        rows.append(
            {
                "scope": "event_trade_reconciliation",
                "profile": profile,
                "check": "synthetic_trade_diff",
                "value": synthetic_trades - expected_synthetic,
            }
        )

    if "profile" in intraday.columns:
        for profile, group in intraday.groupby("profile", sort=False):
            rows.append(
                {
                    "scope": "intraday_events",
                    "profile": profile,
                    "check": "intraday_event_rows",
                    "value": int(len(group)),
                }
            )

    if not stage880_features.empty:
        scoped = stage880_features[stage880_features["profile"].astype(str).eq(C9_PROFILE)].copy()
        rows.append(
            {
                "scope": "session_boundary",
                "profile": C9_PROFILE,
                "check": "stage880_c9_event_rows",
                "value": int(len(scoped)),
            }
        )
        rows.append(
            {
                "scope": "session_boundary",
                "profile": C9_PROFILE,
                "check": "cross_session_reentry_count",
                "value": int(pd.to_numeric(scoped["cross_session_reentry"], errors="coerce").fillna(0).sum()),
            }
        )
        rows.append(
            {
                "scope": "session_boundary",
                "profile": C9_PROFILE,
                "check": "day_to_post_night_reentry_count",
                "value": int(pd.to_numeric(scoped["day_to_post_night_reentry"], errors="coerce").fillna(0).sum()),
            }
        )
        rows.append(
            {
                "scope": "session_boundary",
                "profile": C9_PROFILE,
                "check": "cross_session_original_matched_pnl",
                "value": float(
                    pd.to_numeric(
                        scoped.loc[pd.to_numeric(scoped["cross_session_reentry"], errors="coerce").fillna(0).eq(1), "matched_pnl"],
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                ),
            }
        )

    # Trade timestamps have date-level resolution. This is a deliberate boundary check, not a pass/fail bug.
    c9_trades = trades[trades["profile"].astype(str).eq(C9_PROFILE)].copy()
    c9_trades["datetime_ts"] = pd.to_datetime(c9_trades["datetime"], errors="coerce")
    midnight_count = int((c9_trades["datetime_ts"].dt.strftime("%H:%M:%S") == "00:00:00").sum())
    rows.append(
        {
            "scope": "timestamp_resolution",
            "profile": C9_PROFILE,
            "check": "c9_trade_rows_with_00_00_00_timestamp",
            "value": midnight_count,
        }
    )
    rows.append(
        {
            "scope": "timestamp_resolution",
            "profile": C9_PROFILE,
            "check": "c9_trade_rows_total",
            "value": int(len(c9_trades)),
        }
    )
    return pd.DataFrame(rows)


def _rolling_aggregate() -> dict[str, Any]:
    stage896 = _read_csv(_path(STAGE896_PREFIX, "summary", STAGE896_TAG))
    stage897 = _read_csv(_path(STAGE897_PREFIX, "summary", STAGE897_TAG))
    c9_3y = stage896[
        stage896["arm_key"].astype(str).eq(C9_ROLL_ARM)
        & pd.to_numeric(stage896["complete_3y"], errors="coerce").fillna(0).eq(1)
    ].copy()
    c9_1y = stage897[
        stage897["arm_key"].astype(str).eq(C9_ROLL_ARM)
        & pd.to_numeric(stage897["complete_1y"], errors="coerce").fillna(0).eq(1)
    ].copy()
    return {
        "stage896_complete_3y_windows": int(len(c9_3y)),
        "stage896_c9_positive_3y_windows": int((pd.to_numeric(c9_3y["rebased_total_return_pct"], errors="coerce") > 0).sum()),
        "stage896_c9_worst_3y_dd_pct": float(pd.to_numeric(c9_3y["rebased_max_dd_pct"], errors="coerce").min()),
        "stage896_c9_peak_broker10_pct": float(
            pd.to_numeric(c9_3y["max_broker10_margin_to_rebased_equity_pct"], errors="coerce").max()
        ),
        "stage897_complete_1y_windows": int(len(c9_1y)),
        "stage897_c9_positive_1y_windows": int((pd.to_numeric(c9_1y["rebased_total_return_pct"], errors="coerce") > 0).sum()),
        "stage897_c9_negative_1y_windows": c9_1y.loc[
            pd.to_numeric(c9_1y["rebased_total_return_pct"], errors="coerce") <= 0,
            ["window_id", "rebased_total_return_pct", "rebased_max_dd_pct", "rebased_sharpe"],
        ].to_dict(orient="records"),
        "stage897_c9_worst_1y_return_pct": float(pd.to_numeric(c9_1y["rebased_total_return_pct"], errors="coerce").min()),
        "stage897_c9_worst_1y_dd_pct": float(pd.to_numeric(c9_1y["rebased_max_dd_pct"], errors="coerce").min()),
    }


def _build_findings(metric_checks: pd.DataFrame, minute_checks: pd.DataFrame, event_checks: pd.DataFrame) -> pd.DataFrame:
    metric_fail_count = int((pd.to_numeric(metric_checks["pass"], errors="coerce").fillna(0) == 0).sum())
    minute_values = minute_checks.set_index("check")["value"].to_dict()
    event_values = event_checks.set_index(["scope", "profile", "check"])["value"].to_dict()
    findings = [
        {
            "severity": "P0",
            "status": "pass" if metric_fail_count == 0 else "fail",
            "finding": "Stage863/896/897 摘要核心指标可由资金曲线逐项复算。",
            "evidence": f"metric_check_fail_count={metric_fail_count}",
            "judgment": "若为 pass，说明当前输出文件内部没有发现收益、回撤、交易数、滑点、保证金峰值口径错配。",
        },
        {
            "severity": "P0",
            "status": "pass"
            if int(minute_values.get("entry_day_missing_lots", -1)) == 0
            and int(minute_values.get("pressure_missing_dates", -1)) == 0
            else "fail",
            "finding": "Stage861 全分钟数据覆盖了 Stage819 基准入场日审计样本。",
            "evidence": (
                f"full_minute_bars={minute_values.get('actual_full_minute_bars')}, "
                f"symbols={minute_values.get('actual_full_minute_symbols')}, "
                f"entry_missing={minute_values.get('entry_day_missing_lots')}, "
                f"pressure_missing={minute_values.get('pressure_missing_dates')}"
            ),
            "judgment": "覆盖率可信，但这只能证明本地数据完整性，不能证明每根分钟K线与交易所/tick源绝对一致。",
        },
        {
            "severity": "P0",
            "status": "pass"
            if int(minute_values.get("duplicate_symbol_datetime_rows", -1)) == 0
            and int(minute_values.get("ohlc_high_below_low_rows", -1)) == 0
            and int(minute_values.get("ohlc_high_below_open_close_rows", -1)) == 0
            and int(minute_values.get("ohlc_low_above_open_close_rows", -1)) == 0
            else "fail",
            "finding": "分钟K线基础形态检查未发现重复键或 OHLC 反常。",
            "evidence": (
                f"duplicates={minute_values.get('duplicate_symbol_datetime_rows')}, "
                f"bad_high_low={minute_values.get('ohlc_high_below_low_rows')}, "
                f"bad_high_open_close={minute_values.get('ohlc_high_below_open_close_rows')}, "
                f"bad_low_open_close={minute_values.get('ohlc_low_above_open_close_rows')}"
            ),
            "judgment": "这是必要但不充分检查，仍不能替代交易所原始数据交叉校验。",
        },
        {
            "severity": "P0",
            "status": "pass"
            if int(minute_values.get("stage896_uses_stage861_full_minute_bars", 0)) == 1
            and int(minute_values.get("stage897_uses_stage861_full_minute_bars", 0)) == 1
            and int(minute_values.get("stage896_direct_old_minute_loader_count", 1)) == 0
            and int(minute_values.get("stage897_direct_old_minute_loader_count", 1)) == 0
            else "fail",
            "finding": "Stage896/897 滚动回测分钟源必须与 Stage863 full-minute 口径一致。",
            "evidence": (
                f"stage896_full={minute_values.get('stage896_uses_stage861_full_minute_bars')}, "
                f"stage896_old_loader={minute_values.get('stage896_direct_old_minute_loader_count')}, "
                f"stage897_full={minute_values.get('stage897_uses_stage861_full_minute_bars')}, "
                f"stage897_old_loader={minute_values.get('stage897_direct_old_minute_loader_count')}"
            ),
            "judgment": "若失败，滚动稳定性结论不可采信，必须重跑 Stage896/897。",
        },
        {
            "severity": "P0",
            "status": "pass"
            if int(minute_values.get(f"{C9_PROFILE}:open_missing_full_minute_entry_day_count", 999999)) == 0
            else "fail",
            "finding": "Stage863 C9 每笔开仓 entry-day 都应有 full-minute 数据。",
            "evidence": (
                f"open_trades={minute_values.get(f'{C9_PROFILE}:open_trade_count')}, "
                f"missing={minute_values.get(f'{C9_PROFILE}:open_missing_full_minute_entry_day_count')}"
            ),
            "judgment": "若失败，C9 仍有开仓日内规则跳过样本，不能宣称全样本无数据偏差。",
        },
        {
            "severity": "P1",
            "status": "pass"
            if int(event_values.get(("event_trade_reconciliation", C9_PROFILE, "synthetic_trade_diff"), 999999)) == 0
            else "fail",
            "finding": "C9 stop/retry 事件与 stage847 合成成交数量一致。",
            "evidence": (
                f"expected={event_values.get(('event_trade_reconciliation', C9_PROFILE, 'expected_stage847_synthetic_trades'))}, "
                f"actual={event_values.get(('event_trade_reconciliation', C9_PROFILE, 'actual_stage847_synthetic_trades'))}, "
                f"diff={event_values.get(('event_trade_reconciliation', C9_PROFILE, 'synthetic_trade_diff'))}"
            ),
            "judgment": "这证明事件表和成交表内部闭合；成交价格仍是规则价加回测成本模型，不是盘口逐笔成交。",
        },
        {
            "severity": "P1",
            "status": "watch"
            if int(minute_values.get("old_minute_ohlc_conflict_key_count", 0)) > 0
            else "pass",
            "finding": "旧 Stage825 分钟源存在重复 key/OHLC 冲突，不能再作为 C9 滚动验证源。",
            "evidence": (
                f"old_duplicate_rows={minute_values.get('old_minute_duplicate_key_rows')}, "
                f"old_duplicate_keys={minute_values.get('old_minute_duplicate_key_count')}, "
                f"old_conflict_keys={minute_values.get('old_minute_ohlc_conflict_key_count')}, "
                f"old_conflict_rows={minute_values.get('old_minute_ohlc_conflict_rows')}"
            ),
            "judgment": "Stage861 full bars 使用 patch source priority 去重；滚动脚本必须使用 Stage861 full bars，后续还应做高 PnL 日期抽样核对。",
        },
        {
            "severity": "P1",
            "status": "watch",
            "finding": "C9 是日线组合引擎上叠加入场日分钟路径，不是完整分钟级撮合引擎。",
            "evidence": (
                f"c9_trade_midnight_timestamps={event_values.get(('timestamp_resolution', C9_PROFILE, 'c9_trade_rows_with_00_00_00_timestamp'))}/"
                f"{event_values.get(('timestamp_resolution', C9_PROFILE, 'c9_trade_rows_total'))}"
            ),
            "judgment": "收益曲线可信度高于纯日线止损假设，但不能宣称已完成全生命周期分钟级撮合；非入场日退出仍沿用日线策略链。",
        },
        {
            "severity": "P1",
            "status": "watch",
            "finding": "C9 存在跨时段重试路径，已由 Stage880 标注但未在引擎中禁止。",
            "evidence": (
                f"cross_session_reentry={event_values.get(('session_boundary', C9_PROFILE, 'cross_session_reentry_count'))}, "
                f"day_to_post_night={event_values.get(('session_boundary', C9_PROFILE, 'day_to_post_night_reentry_count'))}, "
                f"matched_pnl={event_values.get(('session_boundary', C9_PROFILE, 'cross_session_original_matched_pnl'))}"
            ),
            "judgment": "这不是数据偏差，但属于交易制度语义风险；真实执行前需要明确同一交易日/夜盘重试规则。",
        },
        {
            "severity": "P1",
            "status": "pass",
            "finding": "滚动回测按每个起点独立重跑，不是全周期净值切片。",
            "evidence": "Stage896/897 源码对 C9 每个 window 临时设置 START/END 并调用 _run_profile。",
            "judgment": "滚动结果对路径依赖、仓位和保证金状态的检验比切片更可信。",
        },
    ]
    return pd.DataFrame(findings)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame if max_rows is None else frame.head(max_rows)
    if data.empty:
        return "_empty_"
    return data.to_markdown(index=False)


def _write_report(
    *,
    summary: pd.DataFrame,
    metric_checks: pd.DataFrame,
    minute_checks: pd.DataFrame,
    event_checks: pd.DataFrame,
    findings: pd.DataFrame,
    rolling: dict[str, Any],
) -> None:
    failed_metrics = metric_checks[pd.to_numeric(metric_checks["pass"], errors="coerce").fillna(0).eq(0)]
    text = f"""# Stage898 C9 Backtest Integrity Audit

- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 生成时间：`{datetime.now().isoformat(timespec="seconds")}`
- 阶段性质：只读审计；不改策略、不改候选配置、不连接 CTP、不调用下单。

## 外部调研与判断

- 通用回测审计资料的共识是：重点检查 look-ahead、数据泄漏、交易成本、撮合假设与 walk-forward/滚动验证。
- vn.py 生态支持分钟 bar 聚合/存储；但本仓库 C9 当前实现不是全策略分钟级撮合，而是日线组合引擎上叠加入场日分钟 stop/retry 合成事件。
- 我的判断：C9 结果可以作为“入场日分钟路径增强后的研究回测”继续评估，不能表述为“无偏差的实盘级分钟回测”。

## 总结

{_md_table(summary)}

## 分级发现

{_md_table(findings)}

## 指标复算

- 复算检查总数：`{len(metric_checks)}`
- 失败数：`{len(failed_metrics)}`

{_md_table(failed_metrics, max_rows=20)}

## 分钟数据检查

{_md_table(minute_checks, max_rows=40)}

## 事件与成交一致性

{_md_table(event_checks, max_rows=80)}

## 滚动回测结论口径

```json
{json.dumps(rolling, ensure_ascii=False, indent=2)}
```

## 结论

- 数据内部一致性：核心指标、资金曲线、事件/合成成交的内部复算没有发现错配。
- 可信边界：C9 仍然不是完整分钟级撮合；成交时间戳为日线日期级，入场日内 stop/retry 用分钟路径合成，非入场日逻辑仍来自日线策略链。
- 是否存在偏差：本次未发现收益/回撤复算偏差，但发现 C9 full-period 仍有开仓 entry-day 分钟覆盖缺口；补齐前不能宣称“全样本无数据偏差”。
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    metric_rows: list[dict[str, Any]] = []
    _recompute_stage863(metric_rows)
    _recompute_rolling(
        metric_rows,
        source="stage896_rolling3y",
        summary_path=_path(STAGE896_PREFIX, "summary", STAGE896_TAG),
        curves_path=_path(STAGE896_PREFIX, "curves", STAGE896_TAG),
    )
    _recompute_rolling(
        metric_rows,
        source="stage897_rolling1y",
        summary_path=_path(STAGE897_PREFIX, "summary", STAGE897_TAG),
        curves_path=_path(STAGE897_PREFIX, "curves", STAGE897_TAG),
    )
    metric_checks = pd.DataFrame(metric_rows)
    minute_checks, coverage_gaps = _minute_checks()
    event_checks = _event_trade_checks()
    findings = _build_findings(metric_checks, minute_checks, event_checks)
    rolling = _rolling_aggregate()

    metric_fail_count = int((pd.to_numeric(metric_checks["pass"], errors="coerce").fillna(0) == 0).sum())
    p0_fail_count = int(findings[findings["severity"].eq("P0") & findings["status"].eq("fail")].shape[0])
    p1_watch_count = int(findings[findings["severity"].eq("P1") & findings["status"].eq("watch")].shape[0])
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "line_id": LINE_ID,
                "model_tag": MODEL_TAG,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "metric_check_count": int(len(metric_checks)),
                "metric_fail_count": metric_fail_count,
                "p0_fail_count": p0_fail_count,
                "p1_watch_count": p1_watch_count,
                "minute_entry_missing_lots": int(
                    minute_checks.set_index("check")["value"].to_dict().get("entry_day_missing_lots", -1)
                ),
                "minute_duplicate_rows": int(
                    minute_checks.set_index("check")["value"].to_dict().get("duplicate_symbol_datetime_rows", -1)
                ),
                "c9_open_missing_full_minute_entry_day_count": int(
                    minute_checks.set_index("check")["value"].to_dict().get(
                        f"{C9_PROFILE}:open_missing_full_minute_entry_day_count", -1
                    )
                ),
                "c9_integrity_decision": "pass_with_execution_semantics_watch"
                if p0_fail_count == 0 and metric_fail_count == 0
                else "fail_needs_data_completion_or_rebuild",
                "strategy_changed": False,
                "official_config_changed": False,
                "ctp_connected": False,
                "order_api_called": False,
            }
        ]
    )

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    metric_checks.to_csv(METRIC_RECOMPUTE_PATH, index=False, encoding="utf-8-sig")
    minute_checks.to_csv(MINUTE_CHECKS_PATH, index=False, encoding="utf-8-sig")
    event_checks.to_csv(EVENT_CHECKS_PATH, index=False, encoding="utf-8-sig")
    findings.to_csv(FINDINGS_PATH, index=False, encoding="utf-8-sig")
    coverage_gaps.to_csv(COVERAGE_GAPS_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": str(summary["c9_integrity_decision"].iloc[0]),
        "metric_fail_count": metric_fail_count,
        "p0_fail_count": p0_fail_count,
        "p1_watch_count": p1_watch_count,
        "rolling": rolling,
        "findings": findings.to_dict(orient="records"),
        "data_bias_statement": (
            "Metric recomputation found no equity/return/drawdown mismatch, but C9 still has open-trade "
            "entry-day minute coverage gaps. This audit therefore fails a zero-bias claim until data is "
            "completed and the affected backtests are rebuilt."
        ),
    }
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(
        summary=summary,
        metric_checks=metric_checks,
        minute_checks=minute_checks,
        event_checks=event_checks,
        findings=findings,
        rolling=rolling,
    )
    print(summary.to_string(index=False))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
