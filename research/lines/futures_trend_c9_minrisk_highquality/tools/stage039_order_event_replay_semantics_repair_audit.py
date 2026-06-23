from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage039"
MODEL_TAG = "stage039_order_event_replay_semantics_repair_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage039_c9_minrisk_order_event_replay_semantics_repair_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage038_order_event_replay_prototype_audit as s038
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage039_order_event_replay_semantics_repair_audit"

INITIAL_OPEN_ROLE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_open_trade_roles_{MODEL_TAG}.csv"
VARIANT_REPLAY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_replay_ledger_{MODEL_TAG}.csv"
VARIANT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
EVENT_CONFUSION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_confusion_{MODEL_TAG}.csv"
CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_exit_semantics_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_exit_semantics_path_chart_{MODEL_TAG}.png"
MATCH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_match_rate_chart_{MODEL_TAG}.png"
CONFUSION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_anchor_confusion_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_anchor_mismatch_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_anchor_mismatch_atlas_page{{page:03d}}_{MODEL_TAG}.png"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
ATLAS_PER_PAGE = 4


VARIANTS = [
    {
        "variant_id": "stage038_first_stage861_open",
        "fill_mode": "first_stage861_open",
        "description": "Stage038 baseline semantics: initial-order match plus first Stage861 bar open as replay fill.",
    },
    {
        "variant_id": "initial_only_official_open_anchor",
        "fill_mode": "official_open_anchor",
        "description": "Repair audit semantics: exclude synthetic reentry opens from initial pool, then anchor replay to official open price.",
    },
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    equity = pd.to_numeric(equity, errors="coerce").ffill()
    hwm = equity.cummax()
    return (equity / hwm - 1.0) * 100.0


def _curve_metrics(frame: pd.DataFrame, equity_col: str) -> dict[str, float]:
    equity = pd.to_numeric(frame[equity_col], errors="coerce").ffill()
    previous = equity.shift(1)
    previous.iloc[0] = CAPITAL
    returns = (equity / previous - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": float(_drawdown_pct(equity).min()),
        "sharpe": float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0,
    }


def _time_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")


def _hhmm(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%H:%M")


def _mark_open_trade_roles(open_trades: pd.DataFrame) -> pd.DataFrame:
    out = open_trades.copy()
    order_id = out["order_id"].astype(str)
    out["is_stage847_reentry_open"] = order_id.str.contains(r"\.stage847_c9\.2$", regex=True)
    out["open_trade_role"] = np.where(out["is_stage847_reentry_open"], "stage847_reentry_open", "initial_strategy_open")
    out["stage847_parent_order_id"] = order_id.str.replace(r"\.stage847_c9\.2$", "", regex=True)
    return out


def _replay_one_order_variant(
    row: pd.Series,
    *,
    groups: dict[str, pd.DataFrame],
    event_lookup: dict[str, dict[str, Any]],
    variant_id: str,
    fill_mode: str,
) -> dict[str, Any]:
    trade_id = str(row.get("official_open_trade_id", ""))
    vt_symbol = str(row.get("vt_symbol", ""))
    direction = s038._direction_text(row.get("direction"))
    entry_day = s038._normalize_day(row.get("official_open_date"))
    official_entry = _safe_float(row.get("official_open_price"))
    planned_stop = _safe_float(row.get("planned_stop_price"))
    official = event_lookup.get(trade_id, {})
    base = row.to_dict()
    base.update(
        {
            "variant_id": variant_id,
            "fill_mode": fill_mode,
            "stage861_day_ready": 0,
            "stage861_bar_count": 0,
            "replay_open_datetime": "",
            "replay_open_time": "",
            "replay_open_price": np.nan,
            "replay_open_price_source": "",
            "replay_open_minus_official": np.nan,
            "replay_open_abs_delta": np.nan,
            "replay_risk_price": np.nan,
            "replay_c9_stop_price": np.nan,
            "replay_c9_progress_price": np.nan,
            "replay_c2_stop_price": np.nan,
            "replay_c2_confirm_price": np.nan,
            "replay_event_family": "missing_stage861_day",
            "replay_first_stop_time": "",
            "replay_reentry_time": "",
            "replay_retry_failed_time": "",
            "replay_c2_hit_time": "",
            "official_event_family": official.get("official_event_family", "no_intraday_event"),
            "official_exit_reason": official.get("official_exit_reason", ""),
            "official_first_stop_time": official.get("official_first_stop_time", ""),
            "official_reentry_time": official.get("official_reentry_time", ""),
            "official_retry_failed_time": official.get("official_retry_failed_time", ""),
            "official_hit_time": official.get("official_hit_time", ""),
            "official_final_state": official.get("official_final_state", ""),
            "official_final_exit_price": official.get("official_final_exit_price", np.nan),
            "event_family_match": 0,
            "first_stop_time_match": 0,
            "reentry_time_match": 0,
            "retry_failed_time_match": 0,
            "c2_hit_time_match": 0,
        }
    )
    if str(row.get("match_status", "")) != "matched_initial_open_trade" or pd.isna(entry_day):
        base["replay_event_family"] = "unmatched_initial_order"
        return base

    day = s038.s010._day_for_symbol(groups, vt_symbol, entry_day)
    if day.empty:
        return base
    day = day.sort_values("bar_datetime").reset_index(drop=True)
    first = day.iloc[0]
    first_open = _safe_float(first.get("open"))
    if fill_mode == "official_open_anchor":
        replay_open = official_entry
        price_source = "official_open_trade_price_anchor"
    else:
        replay_open = first_open if np.isfinite(first_open) and first_open > 0 else _safe_float(first.get("close"))
        price_source = "first_stage861_bar_open"
    risk_price = abs(replay_open - planned_stop) if np.isfinite(replay_open) and np.isfinite(planned_stop) else np.nan
    base.update(
        {
            "stage861_day_ready": 1,
            "stage861_bar_count": int(len(day)),
            "replay_open_datetime": _time_text(first.get("bar_datetime")),
            "replay_open_time": _hhmm(first.get("bar_datetime")),
            "replay_open_price": replay_open,
            "replay_open_price_source": price_source,
            "replay_open_minus_official": replay_open - official_entry if np.isfinite(official_entry) else np.nan,
            "replay_open_abs_delta": abs(replay_open - official_entry) if np.isfinite(official_entry) else np.nan,
            "replay_risk_price": risk_price,
            "replay_c2_stop_price": planned_stop,
            "replay_c2_confirm_price": replay_open + s038._direction_sign(direction) * risk_price
            if np.isfinite(risk_price)
            else np.nan,
        }
    )
    min_risk = max(1e-9, abs(replay_open) * 1e-12)
    if not np.isfinite(risk_price) or risk_price < min_risk:
        base["replay_event_family"] = "invalid_replay_risk"
        return base

    c9 = s038._first_c9_stop_or_progress(day, entry_price=replay_open, risk_price=risk_price, direction=direction)
    base.update(
        {
            "replay_c9_stop_price": c9["stop_price"],
            "replay_c9_progress_price": c9["progress_price"],
        }
    )
    if c9["event"] == "stop":
        retry = s038._reentry_after_stop(
            day,
            direction=direction,
            entry_price=replay_open,
            stop_price=float(c9["stop_price"]),
            stop_idx=int(c9["idx"]),
        )
        family = "c9_flat_no_reentry"
        if int(retry["reentry_idx"]) >= 0:
            family = "c9_open_after_reentry"
            if int(retry["retry_failed_idx"]) >= 0:
                family = "c9_flat_retry_failed"
        base.update(
            {
                "replay_event_family": family,
                "replay_first_stop_time": str(c9["time"]),
                "replay_reentry_time": str(retry["reentry_time"]),
                "replay_retry_failed_time": str(retry["retry_failed_time"]),
                "replay_same_bar_progress": int(c9.get("same_bar_progress", 0)),
            }
        )
    else:
        c2 = s038._first_c2_stop_or_confirm(
            day,
            entry_price=replay_open,
            stop_price=planned_stop,
            risk_price=risk_price,
            direction=direction,
        )
        if c2["event"] == "c2_stop":
            family = "c2_stop"
            hit_time = str(c2["time"])
        else:
            family = "open_no_intraday_event"
            hit_time = ""
        base.update(
            {
                "replay_event_family": family,
                "replay_c2_hit_time": hit_time,
                "replay_c2_same_bar_confirm": int(c2.get("same_bar_confirm", 0)),
            }
        )

    official_family = str(base.get("official_event_family", "no_intraday_event"))
    replay_family = str(base.get("replay_event_family", ""))
    base["event_family_match"] = int(
        (official_family == "no_intraday_event" and replay_family == "open_no_intraday_event")
        or official_family == replay_family
    )
    base["first_stop_time_match"] = int(
        bool(base.get("official_first_stop_time")) and base.get("official_first_stop_time") == base.get("replay_first_stop_time")
    )
    base["reentry_time_match"] = int(
        bool(base.get("official_reentry_time")) and base.get("official_reentry_time") == base.get("replay_reentry_time")
    )
    base["retry_failed_time_match"] = int(
        bool(base.get("official_retry_failed_time"))
        and base.get("official_retry_failed_time") == base.get("replay_retry_failed_time")
    )
    base["c2_hit_time_match"] = int(
        bool(base.get("official_hit_time")) and base.get("official_hit_time") == base.get("replay_c2_hit_time")
    )
    return base


def _build_variant_replay(candidates: pd.DataFrame, open_trades: pd.DataFrame, intraday: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    open_roles = _mark_open_trade_roles(open_trades)
    initial_pool = open_roles[open_roles["open_trade_role"].eq("initial_strategy_open")].copy()
    matches = s038._match_initial_orders(candidates, initial_pool)
    groups = s038._load_minute_groups(matches)
    event_lookup = s038._official_event_lookup(intraday)
    rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        for _, row in matches.iterrows():
            rows.append(
                _replay_one_order_variant(
                    row,
                    groups=groups,
                    event_lookup=event_lookup,
                    variant_id=str(variant["variant_id"]),
                    fill_mode=str(variant["fill_mode"]),
                )
            )
    replay = pd.DataFrame(rows)
    for column in [
        "official_open_price",
        "official_open_volume",
        "candidate_selected_volume",
        "replay_open_price",
        "replay_open_minus_official",
        "replay_open_abs_delta",
        "replay_risk_price",
        "event_family_match",
        "first_stop_time_match",
        "reentry_time_match",
        "retry_failed_time_match",
        "c2_hit_time_match",
    ]:
        if column in replay.columns:
            replay[column] = pd.to_numeric(replay[column], errors="coerce")
    open_roles["used_for_initial_matching"] = open_roles["open_trade_role"].eq("initial_strategy_open").astype(int)
    return open_roles, replay, groups


def _event_confusion(replay: pd.DataFrame) -> pd.DataFrame:
    data = replay.copy()
    data["official_event_family"] = data["official_event_family"].fillna("no_intraday_event")
    data["replay_event_family"] = data["replay_event_family"].fillna("missing")
    table = (
        data.groupby(["variant_id", "official_event_family", "replay_event_family"], dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            abs_price_delta_median=("replay_open_abs_delta", "median"),
            event_family_match=("event_family_match", "sum"),
            first_stop_time_match=("first_stop_time_match", "sum"),
            reentry_time_match=("reentry_time_match", "sum"),
            retry_failed_time_match=("retry_failed_time_match", "sum"),
            c2_hit_time_match=("c2_hit_time_match", "sum"),
        )
        .reset_index()
        .sort_values(["variant_id", "official_event_family", "orders"], ascending=[True, True, False])
    )
    return table


def _variant_summary(replay: pd.DataFrame, open_roles: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    initial_open_count = int(open_roles["open_trade_role"].eq("initial_strategy_open").sum())
    reentry_open_count = int(open_roles["open_trade_role"].eq("stage847_reentry_open").sum())
    for variant in VARIANTS:
        variant_id = str(variant["variant_id"])
        data = replay[replay["variant_id"].eq(variant_id)].copy()
        ready = data[data["stage861_day_ready"].eq(1)].copy()
        matched = data[data["match_status"].astype(str).eq("matched_initial_open_trade")]
        rows.append(
            {
                "variant_id": variant_id,
                "fill_mode": variant["fill_mode"],
                "description": variant["description"],
                "open_trade_total": int(len(open_roles)),
                "initial_strategy_open_count": initial_open_count,
                "stage847_reentry_open_count": reentry_open_count,
                "opened_candidates": int(len(data)),
                "matched_initial_orders": int(len(matched)),
                "stage861_replay_ready_orders": int(len(ready)),
                "unmatched_initial_pool_open_after_matching": int(
                    pd.to_numeric(data.get("unmatched_official_open_trades_after_initial_matching", 0), errors="coerce")
                    .fillna(0)
                    .max()
                ),
                "median_replay_open_abs_delta": float(pd.to_numeric(ready["replay_open_abs_delta"], errors="coerce").median())
                if len(ready)
                else np.nan,
                "p90_replay_open_abs_delta": float(pd.to_numeric(ready["replay_open_abs_delta"], errors="coerce").quantile(0.9))
                if len(ready)
                else np.nan,
                "max_replay_open_abs_delta": float(pd.to_numeric(ready["replay_open_abs_delta"], errors="coerce").max())
                if len(ready)
                else np.nan,
                "event_family_match_rate_pct": float(pd.to_numeric(ready["event_family_match"], errors="coerce").fillna(0).mean() * 100.0)
                if len(ready)
                else 0.0,
                "event_family_mismatch_orders": int(pd.to_numeric(ready["event_family_match"], errors="coerce").fillna(0).eq(0).sum()),
                "first_stop_time_match_count": int(pd.to_numeric(ready.get("first_stop_time_match", 0), errors="coerce").fillna(0).sum()),
                "reentry_time_match_count": int(pd.to_numeric(ready.get("reentry_time_match", 0), errors="coerce").fillna(0).sum()),
                "retry_failed_time_match_count": int(pd.to_numeric(ready.get("retry_failed_time_match", 0), errors="coerce").fillna(0).sum()),
                "c2_hit_time_match_count": int(pd.to_numeric(ready.get("c2_hit_time_match", 0), errors="coerce").fillna(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _same_exit_curves(curve: pd.DataFrame, lots: pd.DataFrame, replay: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    for variant in VARIANTS:
        variant_id = str(variant["variant_id"])
        data = replay[replay["variant_id"].eq(variant_id)].copy()
        sensitivity = s038._closed_lot_sensitivity(lots, data)
        sensitivity["exit_date_ts"] = pd.to_datetime(sensitivity["exit_date_ts"], errors="coerce").dt.normalize()
        daily_delta = (
            pd.to_numeric(sensitivity["entry_price_delta_pnl_same_exit"], errors="coerce")
            .fillna(0.0)
            .groupby(sensitivity["exit_date_ts"])
            .sum()
        )
        safe_id = variant_id.replace("-", "_")
        out[f"{safe_id}_delta"] = out["date"].map(daily_delta).fillna(0.0)
        out[f"{safe_id}_cum_delta"] = out[f"{safe_id}_delta"].cumsum()
        out[f"{safe_id}_equity"] = out["account_equity"] + out[f"{safe_id}_cum_delta"]
        out[f"{safe_id}_drawdown_pct"] = _drawdown_pct(out[f"{safe_id}_equity"])
    return out


def _summary(curve: pd.DataFrame, lots: pd.DataFrame, open_roles: pd.DataFrame, replay: pd.DataFrame, variants: pd.DataFrame, semantics_curve: pd.DataFrame) -> pd.DataFrame:
    official = s038._official_metrics(curve, lots)
    first_row = variants[variants["variant_id"].eq("stage038_first_stage861_open")].iloc[0].to_dict()
    anchor_row = variants[variants["variant_id"].eq("initial_only_official_open_anchor")].iloc[0].to_dict()
    anchor_metrics = _curve_metrics(semantics_curve, "initial_only_official_open_anchor_equity")
    first_metrics = _curve_metrics(semantics_curve, "stage038_first_stage861_open_equity")
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        **official,
        "open_trade_total": int(len(open_roles)),
        "initial_strategy_open_count": int(open_roles["open_trade_role"].eq("initial_strategy_open").sum()),
        "stage847_reentry_open_count": int(open_roles["open_trade_role"].eq("stage847_reentry_open").sum()),
        "stage038_first_stage861_event_match_rate_pct": float(first_row["event_family_match_rate_pct"]),
        "official_open_anchor_event_match_rate_pct": float(anchor_row["event_family_match_rate_pct"]),
        "official_open_anchor_event_mismatch_orders": int(anchor_row["event_family_mismatch_orders"]),
        "official_open_anchor_ready_orders": int(anchor_row["stage861_replay_ready_orders"]),
        "official_open_anchor_first_stop_time_match_count": int(anchor_row["first_stop_time_match_count"]),
        "official_open_anchor_reentry_time_match_count": int(anchor_row["reentry_time_match_count"]),
        "official_open_anchor_retry_failed_time_match_count": int(anchor_row["retry_failed_time_match_count"]),
        "official_open_anchor_c2_hit_time_match_count": int(anchor_row["c2_hit_time_match_count"]),
        "stage038_first_stage861_same_exit_end_equity": first_metrics["end_equity"],
        "stage038_first_stage861_same_exit_max_drawdown_pct": first_metrics["max_drawdown_pct"],
        "official_open_anchor_same_exit_end_equity": anchor_metrics["end_equity"],
        "official_open_anchor_same_exit_max_drawdown_pct": anchor_metrics["max_drawdown_pct"],
        "decision": "stage039_official_open_anchor_replay_semantics_improved_but_not_execution_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
    }
    return pd.DataFrame([row])


def _plot_path(curve: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#111827", linewidth=1.2, label="official equity")
    axes[0].plot(
        curve["date"],
        curve["stage038_first_stage861_open_equity"],
        color="#dc2626",
        linewidth=1.0,
        label="same-exit first Stage861 open sensitivity",
    )
    axes[0].plot(
        curve["date"],
        curve["initial_only_official_open_anchor_equity"],
        color="#16a34a",
        linewidth=0.9,
        linestyle="--",
        label="same-exit official open anchor",
    )
    axes[0].set_title("Same-exit replay semantics equity audit")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#111827", linewidth=1.0, label="official DD")
    axes[1].plot(
        curve["date"],
        curve["stage038_first_stage861_open_drawdown_pct"],
        color="#dc2626",
        linewidth=1.0,
        label="first Stage861 open DD",
    )
    axes[1].plot(
        curve["date"],
        curve["initial_only_official_open_anchor_drawdown_pct"],
        color="#16a34a",
        linewidth=0.9,
        linestyle="--",
        label="official open anchor DD",
    )
    axes[1].set_title("Drawdown comparison, audit only")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")

    axes[2].plot(
        curve["date"],
        curve["stage038_first_stage861_open_cum_delta"],
        color="#dc2626",
        linewidth=1.1,
        label="cum delta: first Stage861 open",
    )
    axes[2].plot(
        curve["date"],
        curve["initial_only_official_open_anchor_cum_delta"],
        color="#16a34a",
        linewidth=0.9,
        linestyle="--",
        label="cum delta: official open anchor",
    )
    axes[2].axhline(0, color="#6b7280", linewidth=0.8)
    axes[2].set_title("Cumulative same-exit PnL delta from replay fill semantics")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best")
    fig.suptitle("Stage039 order-event replay semantics repair audit", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_match_chart(variants: pd.DataFrame) -> None:
    data = variants.copy()
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    labels = data["variant_id"].tolist()
    x = np.arange(len(data))
    axes[0].bar(x, data["event_family_match_rate_pct"], color=["#dc2626", "#16a34a"])
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    axes[0].set_ylim(0, 105)
    axes[0].set_ylabel("event-family match rate %")
    axes[0].set_title("Replay event-family consistency")
    axes[0].grid(True, axis="y", alpha=0.25)
    for idx, value in enumerate(data["event_family_match_rate_pct"]):
        axes[0].text(idx, float(value) + 1.5, f"{float(value):.2f}%", ha="center", fontsize=9)

    width = 0.22
    metrics = [
        ("first_stop_time_match_count", "#991b1b", "first stop"),
        ("reentry_time_match_count", "#2563eb", "reentry"),
        ("retry_failed_time_match_count", "#7c2d12", "retry failed"),
        ("c2_hit_time_match_count", "#f97316", "C2 hit"),
    ]
    for offset, (column, color, label) in enumerate(metrics):
        axes[1].bar(x + (offset - 1.5) * width, data[column], width=width, color=color, label=label)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    axes[1].set_title("Exact event-time match counts")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend(loc="best")
    fig.savefig(MATCH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_confusion(confusion: pd.DataFrame) -> None:
    data = confusion[confusion["variant_id"].eq("initial_only_official_open_anchor")].copy()
    if data.empty:
        return
    pivot = data.pivot_table(
        index="official_event_family",
        columns="replay_event_family",
        values="orders",
        aggfunc="sum",
        fill_value=0,
    )
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    im = ax.imshow(pivot.to_numpy(), cmap="Greens")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            value = int(pivot.iloc[i, j])
            if value:
                ax.text(j, i, str(value), ha="center", va="center", color="#111827", fontsize=8)
    ax.set_title("Official event family vs official-open-anchor replay event family")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.savefig(CONFUSION_CHART_OUT, dpi=150)
    plt.close(fig)


def _select_anchor_mismatches(replay: pd.DataFrame) -> pd.DataFrame:
    data = replay[
        replay["variant_id"].eq("initial_only_official_open_anchor")
        & replay["stage861_day_ready"].eq(1)
        & pd.to_numeric(replay["event_family_match"], errors="coerce").fillna(0).eq(0)
    ].copy()
    if data.empty:
        return data
    return data.sort_values(["official_event_family", "replay_event_family", "official_open_date", "vt_symbol"]).reset_index(drop=True)


def _plot_mismatch_atlas(replay: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_anchor_mismatches(replay)
    if selected.empty:
        _write_csv(pd.DataFrame(), ATLAS_MANIFEST_OUT)
        return [], pd.DataFrame()
    pages: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page_idx, start in enumerate(range(0, len(selected), ATLAS_PER_PAGE), start=1):
        page_rows = selected.iloc[start : start + ATLAS_PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(page_rows), 1, figsize=(14, 3.5 * len(page_rows)), sharex=False, constrained_layout=True)
        if len(page_rows) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, page_rows.iterrows()):
            day = s038.s010._day_for_symbol(groups, str(row["vt_symbol"]), s038._normalize_day(row["official_open_date"]))
            if day.empty:
                ax.text(0.5, 0.5, "missing Stage861 day", ha="center", va="center")
                ax.set_axis_off()
            else:
                day = day.sort_values("bar_datetime").reset_index(drop=True)
                x = np.arange(len(day))
                ax.plot(x, pd.to_numeric(day["close"], errors="coerce"), color="#2563eb", linewidth=0.9, label="Stage861 close")
                for column, color, label, style in [
                    ("official_open_price", "#111827", "official open", "--"),
                    ("planned_stop_price", "#b91c1c", "planned/C2 stop", "-."),
                    ("replay_c9_stop_price", "#dc2626", "C9 -0.5R stop", ":"),
                    ("replay_c9_progress_price", "#16a34a", "C9 +0.5R progress", ":"),
                    ("replay_c2_confirm_price", "#f97316", "C2 +1R confirm", ":"),
                ]:
                    value = _safe_float(row.get(column))
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linewidth=0.9, linestyle=style, label=label)
                for column, color, label in [
                    ("replay_open_datetime", "#7c3aed", "replay day first bar"),
                    ("replay_first_stop_time", "#dc2626", "replay C9 stop"),
                    ("replay_reentry_time", "#2563eb", "replay reentry"),
                    ("replay_retry_failed_time", "#7c2d12", "replay retry failed"),
                    ("replay_c2_hit_time", "#f97316", "replay C2 stop"),
                    ("official_first_stop_time", "#991b1b", "official first stop"),
                    ("official_reentry_time", "#1d4ed8", "official reentry"),
                    ("official_retry_failed_time", "#7c2d12", "official retry failed"),
                    ("official_hit_time", "#ea580c", "official C2 hit"),
                ]:
                    text = str(row.get(column, ""))
                    if not text or text == "nan":
                        continue
                    ts = pd.to_datetime(text, errors="coerce")
                    if pd.isna(ts):
                        continue
                    matches = np.flatnonzero(pd.to_datetime(day["bar_datetime"], errors="coerce").eq(ts).to_numpy())
                    if len(matches):
                        ax.axvline(int(matches[0]), color=color, linewidth=0.8, alpha=0.75, label=label)
                tick_positions = np.linspace(0, max(len(day) - 1, 0), num=min(6, len(day)), dtype=int)
                ax.set_xticks(tick_positions)
                ax.set_xticklabels([_hhmm(day.loc[pos, "bar_datetime"]) for pos in tick_positions], fontsize=8)
                ax.grid(True, alpha=0.25)
            title = (
                f"{row.get('official_open_trade_id')} {row.get('vt_symbol')} {row.get('official_open_date')} "
                f"{row.get('direction')} official={row.get('official_event_family')} replay={row.get('replay_event_family')}"
            )
            ax.set_title(title, fontsize=9)
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), loc="best", fontsize=7)
            manifest_rows.append(
                {
                    "page": page_idx,
                    "candidate_index": row.get("candidate_index"),
                    "official_open_trade_id": row.get("official_open_trade_id"),
                    "vt_symbol": row.get("vt_symbol"),
                    "official_open_date": row.get("official_open_date"),
                    "direction": row.get("direction"),
                    "official_event_family": row.get("official_event_family"),
                    "replay_event_family": row.get("replay_event_family"),
                    "official_open_price": row.get("official_open_price"),
                    "planned_stop_price": row.get("planned_stop_price"),
                    "replay_risk_price": row.get("replay_risk_price"),
                    "official_first_stop_time": row.get("official_first_stop_time"),
                    "official_hit_time": row.get("official_hit_time"),
                    "replay_first_stop_time": row.get("replay_first_stop_time"),
                    "replay_c2_hit_time": row.get("replay_c2_hit_time"),
                }
            )
        output = Path(str(ATLAS_TEMPLATE).format(page=page_idx))
        fig.savefig(output, dpi=150)
        plt.close(fig)
        pages.append(output)
    manifest = pd.DataFrame(manifest_rows)
    _write_csv(manifest, ATLAS_MANIFEST_OUT)
    return pages, manifest


def _write_report(
    summary: pd.DataFrame,
    variants: pd.DataFrame,
    confusion: pd.DataFrame,
    replay: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    row = summary.iloc[0].to_dict()
    anchor_mismatch = _select_anchor_mismatches(replay)
    anchor_confusion = confusion[confusion["variant_id"].eq("initial_only_official_open_anchor")].copy()
    lines = [
        "# Stage039 订单事件回放语义修复审计",
        "",
        "## 结论",
        "",
        "- 决策：`stage039_official_open_anchor_replay_semantics_improved_but_not_execution_rule`。",
        "- 本阶段只做 replay 语义修复审计，不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API、不触发 A/B。",
        f"- official trades 中 `Open` 共 `{int(row['open_trade_total'])}` 条，其中 initial strategy open `{int(row['initial_strategy_open_count'])}` 条，C9 synthetic reentry open `{int(row['stage847_reentry_open_count'])}` 条；Stage039 已把 reentry open 从 initial matching pool 剥离。",
        f"- Stage038 first Stage861 open 语义 event-family match rate 为 `{row['stage038_first_stage861_event_match_rate_pct']:.4f}%`；official open anchor 语义提升到 `{row['official_open_anchor_event_match_rate_pct']:.4f}%`。",
        f"- official open anchor ready `{int(row['official_open_anchor_ready_orders'])}` 笔，仍有 `{int(row['official_open_anchor_event_mismatch_orders'])}` 笔 event family mismatch；因此只能作为事件语义校准底座，不能当作可执行分钟成交模型。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{row['end_equity']:.2f}`",
        f"- 总收益：`{row['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe：`{row['sharpe']:.4f}`",
        f"- 总滑点：`{row['total_slippage']:.0f}`",
        f"- 总交易次数：`{row['total_trade_count']:.0f}`",
        f"- closed-lot 胜率：`{row['closed_lot_win_rate_pct']:.4f}%`",
        "",
        "## 外部调研与判断",
        "",
        "- vn.py `BacktestingEngine` 的 BAR 模式在每根 bar 先撮合 limit、再撮合 stop，limit/stop 都用 bar 的 open/high/low 判断成交价语义；这说明回放必须按订单流前向定义，不能用最终成交价反推时点。",
        "- Backtrader 文档同样把 Market/Limit/Stop 执行定义在下一可用价格、bar open 和 bar 内触价逻辑上；NautilusTrader 文档强调 OHLC 需要明确价格序列和 timestamp convention。",
        "- 本阶段判断：官方 open price 是当前产物中能复现 C9/C2 事件的语义锚点，但它本身不是实盘可交易时点；若未来要测试分钟进出场，还要继续补 `_resolve_trade_price` 的可执行代理或真实成交时点。",
        "",
        "## Variant Summary",
        "",
        _md_table(variants, max_rows=None),
        "",
        "## Official-Anchor Confusion",
        "",
        _md_table(anchor_confusion, max_rows=40),
        "",
        "## Official-Anchor Remaining Mismatches",
        "",
        _md_table(
            anchor_mismatch[
                [
                    "candidate_index",
                    "official_open_trade_id",
                    "vt_symbol",
                    "official_open_date",
                    "direction",
                    "official_event_family",
                    "replay_event_family",
                    "official_open_price",
                    "planned_stop_price",
                    "replay_risk_price",
                    "official_first_stop_time",
                    "official_hit_time",
                    "replay_first_stop_time",
                    "replay_c2_hit_time",
                ]
            ]
            if not anchor_mismatch.empty
            else pd.DataFrame(),
            max_rows=20,
        ),
        "",
        "## Visuals",
        "",
        f"- same-exit semantics path chart：`{PATH_CHART_OUT}`",
        f"- event match rate chart：`{MATCH_CHART_OUT}`",
        f"- official anchor confusion chart：`{CONFUSION_CHART_OUT}`",
        *[f"- mismatch atlas page：`{path}`" for path in atlas_paths],
        "",
        "## Files",
        "",
        f"- open trade roles：`{INITIAL_OPEN_ROLE_OUT}`",
        f"- variant replay ledger：`{VARIANT_REPLAY_OUT}`",
        f"- variant summary：`{VARIANT_SUMMARY_OUT}`",
        f"- event confusion：`{EVENT_CONFUSION_OUT}`",
        f"- semantics curve：`{CURVE_OUT}`",
        f"- summary：`{SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 视觉观察",
        "",
        "- path chart 显示 first Stage861 open 同 exit 敏感曲线从 2021 后明显低于 official，而 official open anchor 与 official 基本重合；这说明主要偏差来自成交价锚点，不是 C9/C2 事件公式本身。",
        "- match chart 显示 official open anchor 后 first-stop/reentry/retry/C2 时间匹配大幅增加，但仍未达到 100%，剩余 mismatch 需要继续看 `_resolve_trade_price`、daily bar 与 Stage861 minute 源、以及同 bar 顺序边界。",
        "- mismatch atlas 只画剩余 event-family 不一致样本；若样本集中在 no_intraday_event 被 replay 成 C2/C9 stop，说明 Stage861 minute 源和官方事件源仍存在边界差，不得把这些差异写成交易规则。",
        "",
        "## 后续",
        "",
        "- 下一步应审计 `_resolve_trade_price` 的 proxy 来源，尝试重建 official open anchor 的可执行 timestamp/proxy ledger；如果无法点时化，就只能把 official open anchor 用作事件归因底座，不能用于实盘分钟开仓规则。",
        "- 在 replay 语义和成交锚点都未通过一致性审计前，继续暂停新增分钟级开仓、恢复、降仓或退出候选。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve, open_trades, candidates, lots, intraday, _trades = s038._prepare_inputs()
    open_roles, replay, groups = _build_variant_replay(candidates, open_trades, intraday)
    variants = _variant_summary(replay, open_roles)
    confusion = _event_confusion(replay)
    semantics_curve = _same_exit_curves(curve, lots, replay)
    summary = _summary(curve, lots, open_roles, replay, variants, semantics_curve)

    _write_csv(open_roles, INITIAL_OPEN_ROLE_OUT)
    _write_csv(replay, VARIANT_REPLAY_OUT)
    _write_csv(variants, VARIANT_SUMMARY_OUT)
    _write_csv(confusion, EVENT_CONFUSION_OUT)
    _write_csv(semantics_curve, CURVE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path(semantics_curve)
    _plot_match_chart(variants)
    _plot_confusion(confusion)
    atlas_paths, _manifest = _plot_mismatch_atlas(replay, groups)

    _write_report(summary, variants, confusion, replay, atlas_paths)

    row = summary.iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": row["decision"],
        "candidate_ready": 0,
        "ab_triggered": 0,
        "rule_added": 0,
        "official_config_changed": 0,
        "open_trade_total": int(row["open_trade_total"]),
        "initial_strategy_open_count": int(row["initial_strategy_open_count"]),
        "stage847_reentry_open_count": int(row["stage847_reentry_open_count"]),
        "stage038_first_stage861_event_match_rate_pct": float(row["stage038_first_stage861_event_match_rate_pct"]),
        "official_open_anchor_event_match_rate_pct": float(row["official_open_anchor_event_match_rate_pct"]),
        "official_open_anchor_event_mismatch_orders": int(row["official_open_anchor_event_mismatch_orders"]),
        "official_open_anchor_ready_orders": int(row["official_open_anchor_ready_orders"]),
        "judgment": (
            "Separating synthetic C9 reentry opens from initial strategy opens and anchoring replay to official open price "
            "repairs most event semantics, but official open price is not yet a tradable minute timestamp."
        ),
        "overfit_guard": (
            "No year/product/direction/session/clock filter is promoted. This stage repairs ledger semantics only and "
            "does not add an entry, exit, restore, or reduce-risk rule."
        ),
        "next_step": (
            "Reconstruct or audit _resolve_trade_price proxy timestamps before using the replay ledger for minute-level rule tests."
        ),
        "outputs": {
            "open_trade_roles": INITIAL_OPEN_ROLE_OUT,
            "variant_replay": VARIANT_REPLAY_OUT,
            "variant_summary": VARIANT_SUMMARY_OUT,
            "event_confusion": EVENT_CONFUSION_OUT,
            "semantics_curve": CURVE_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "match_chart": MATCH_CHART_OUT,
            "confusion_chart": CONFUSION_CHART_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
            "atlas_pages": atlas_paths,
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
