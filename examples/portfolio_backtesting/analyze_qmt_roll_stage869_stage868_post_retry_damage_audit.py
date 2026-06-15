from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage864_stage863_broker10_peak_forensics as s864
import analyze_qmt_roll_stage865_stage864_sizing_brake_proxy_audit as s865
import analyze_qmt_roll_stage866_stage865_high_heat_minute_path_audit as s866
import analyze_qmt_roll_stage868_stage847_close_confirm_retry_engine as s868
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage869"
MODEL_TAG = "stage869_stage868_post_retry_damage_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage869_stage868_post_retry_damage_audit"

C9_ARM = s868.C9_ARM

EVENT_NEXT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_next_entry_{MODEL_TAG}.csv"
STATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
YEARLY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_summary_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

MAX_ATLAS_ROWS = 12
PER_PAGE = 3


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _date_from_text(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    text = str(value)
    if len(text) >= 10:
        return pd.to_datetime(text[:10], errors="coerce")
    return pd.to_datetime(text, errors="coerce")


def _normalize_date_series(series: pd.Series) -> pd.Series:
    return series.map(_date_from_text).dt.normalize()


def _prepare_entries() -> pd.DataFrame:
    entries = _load_required_csv(s865.ENTRY_AUDIT_PATH).copy()
    entries = entries[entries["profile"].astype(str).eq(C9_ARM)].copy()
    entries["date"] = _normalize_date_series(entries["date"])
    entries["matched_entry_date"] = _normalize_date_series(entries["matched_entry_date"])
    numeric_columns = [
        "entry_key",
        "selected_volume",
        "matched_lots",
        "matched_volume",
        "matched_pnl",
        "matched_risk",
        "matched_r_multiple_sum",
        "matched_max_r",
        "matched_winner",
        "matched_big_winner",
        "before_broker10_pct",
        "add_broker10_pct",
        "projected_broker10_pct",
        "entry_price",
        "stop_price",
        "stop_distance",
        "actual_margin_amount",
    ]
    for column in numeric_columns:
        if column in entries.columns:
            entries[column] = pd.to_numeric(entries[column], errors="coerce")
    entries = entries[entries["matched_lots"].fillna(0).gt(0)].copy()
    entries["entry_year"] = entries["matched_entry_date"].dt.year
    entries["product_direction_key"] = entries["product_vt_symbol"].astype(str) + "|" + entries["direction"].astype(str)

    path_features = _load_required_csv(s866.ENTRY_PATH_FEATURES_PATH).copy()
    feature_columns = [
        "entry_key",
        "minute_path_state",
        "first_05_event",
        "first_stop_time",
        "reclaim_entry_time_after_stop",
        "retry_failed_time_after_reclaim",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "entry_day_close_r",
    ]
    path_features = path_features[[column for column in feature_columns if column in path_features.columns]].copy()
    if "entry_key" in path_features.columns:
        path_features["entry_key"] = pd.to_numeric(path_features["entry_key"], errors="coerce")
        entries = entries.merge(path_features, on="entry_key", how="left")
    return entries.sort_values(["matched_entry_date", "entry_key"]).reset_index(drop=True)


def _prepare_events() -> pd.DataFrame:
    events = _load_required_csv(s868.STOP_RETRY_EVENTS_PATH).copy()
    events = events[events["profile"].astype(str).eq(C9_ARM)].copy()
    events["event_date"] = _normalize_date_series(events["datetime"])
    for column in [
        "entry_price",
        "stop_price",
        "progress_price",
        "risk_price",
        "volume",
        "first_stop_bar_index",
        "reentry_bar_index",
        "retry_failed_bar_index",
        "retry_reentered",
        "retry_failed",
    ]:
        if column in events.columns:
            events[column] = pd.to_numeric(events[column], errors="coerce")
    events["product_direction_key"] = events["product_vt_symbol"].astype(str) + "|" + events["direction"].astype(str)
    events = events.sort_values(["event_date", "product_direction_key", "trade_id"]).reset_index(drop=True)
    events["event_id"] = np.arange(len(events))
    return events


def _match_next_same_product_direction(events: pd.DataFrame, entries: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped_entries = {
        key: group.sort_values(["matched_entry_date", "entry_key"]).reset_index(drop=True)
        for key, group in entries.groupby("product_direction_key", dropna=False)
    }
    for _, event in events.iterrows():
        key = str(event["product_direction_key"])
        event_date = event["event_date"]
        candidates = grouped_entries.get(key, pd.DataFrame())
        if candidates.empty or pd.isna(event_date):
            next_entry = None
        else:
            future = candidates[candidates["matched_entry_date"].gt(event_date)].copy()
            next_entry = None if future.empty else future.iloc[0]

        base = {
            "event_id": int(event["event_id"]),
            "event_date": event_date,
            "event_trade_id": event.get("trade_id", ""),
            "event_vt_symbol": event.get("vt_symbol", ""),
            "event_product_vt_symbol": event.get("product_vt_symbol", ""),
            "direction": event.get("direction", ""),
            "product_direction_key": key,
            "event_final_state": event.get("final_state", ""),
            "event_retry_reentered": int(_safe_float(event.get("retry_reentered"), 0) > 0),
            "event_retry_failed": int(_safe_float(event.get("retry_failed"), 0) > 0),
            "event_entry_price": _safe_float(event.get("entry_price")),
            "event_stop_price": _safe_float(event.get("stop_price")),
            "event_progress_price": _safe_float(event.get("progress_price")),
            "event_volume": _safe_float(event.get("volume")),
            "event_first_stop_time": event.get("first_stop_time", ""),
            "event_reentry_time": event.get("reentry_time", ""),
            "event_retry_failed_time": event.get("retry_failed_time", ""),
        }
        if next_entry is None:
            base.update(
                {
                    "has_next_same_pd_entry": 0,
                    "next_entry_key": np.nan,
                    "next_entry_date": pd.NaT,
                    "days_to_next_entry": np.nan,
                    "next_contract_vt_symbol": "",
                    "next_signal": "",
                    "next_selected_volume": np.nan,
                    "next_matched_volume": np.nan,
                    "next_matched_pnl": 0.0,
                    "next_matched_r_multiple_sum": 0.0,
                    "next_matched_max_r": np.nan,
                    "next_matched_winner": 0,
                    "next_matched_big_winner": 0,
                    "next_matched_exit_reasons": "",
                    "next_before_broker10_pct": np.nan,
                    "next_add_broker10_pct": np.nan,
                    "next_projected_broker10_pct": np.nan,
                    "next_minute_path_state": "",
                    "next_first_05_event": "",
                    "next_entry_day_mfe_r": np.nan,
                    "next_entry_day_mae_r": np.nan,
                    "next_entry_day_close_r": np.nan,
                    "next_entry_price": np.nan,
                    "next_stop_price": np.nan,
                }
            )
            rows.append(base)
            continue

        next_date = next_entry["matched_entry_date"]
        base.update(
            {
                "has_next_same_pd_entry": 1,
                "next_entry_key": int(_safe_float(next_entry.get("entry_key"), -1)),
                "next_entry_date": next_date,
                "days_to_next_entry": int((pd.Timestamp(next_date) - pd.Timestamp(event_date)).days)
                if pd.notna(next_date) and pd.notna(event_date)
                else np.nan,
                "next_contract_vt_symbol": next_entry.get("contract_vt_symbol", ""),
                "next_signal": next_entry.get("matched_signal", ""),
                "next_selected_volume": _safe_float(next_entry.get("selected_volume")),
                "next_matched_volume": _safe_float(next_entry.get("matched_volume")),
                "next_matched_pnl": _safe_float(next_entry.get("matched_pnl"), 0.0),
                "next_matched_r_multiple_sum": _safe_float(next_entry.get("matched_r_multiple_sum"), 0.0),
                "next_matched_max_r": _safe_float(next_entry.get("matched_max_r")),
                "next_matched_winner": int(_safe_float(next_entry.get("matched_winner"), 0) > 0),
                "next_matched_big_winner": int(_safe_float(next_entry.get("matched_big_winner"), 0) > 0),
                "next_matched_exit_reasons": next_entry.get("matched_exit_reasons", ""),
                "next_before_broker10_pct": _safe_float(next_entry.get("before_broker10_pct")),
                "next_add_broker10_pct": _safe_float(next_entry.get("add_broker10_pct")),
                "next_projected_broker10_pct": _safe_float(next_entry.get("projected_broker10_pct")),
                "next_minute_path_state": next_entry.get("minute_path_state", ""),
                "next_first_05_event": next_entry.get("first_05_event", ""),
                "next_entry_day_mfe_r": _safe_float(next_entry.get("entry_day_mfe_r")),
                "next_entry_day_mae_r": _safe_float(next_entry.get("entry_day_mae_r")),
                "next_entry_day_close_r": _safe_float(next_entry.get("entry_day_close_r")),
                "next_entry_price": _safe_float(next_entry.get("entry_price")),
                "next_stop_price": _safe_float(next_entry.get("stop_price")),
            }
        )
        rows.append(base)
    result = pd.DataFrame(rows)
    result["next_entry_year"] = pd.to_datetime(result["next_entry_date"], errors="coerce").dt.year
    return result


def _unique_next_entries(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame[frame["has_next_same_pd_entry"].eq(1)].copy()
    data = data.dropna(subset=["next_entry_key"])
    return data.sort_values(["event_date", "event_id"]).drop_duplicates("next_entry_key")


def _state_summary(event_next: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for state, group in event_next.groupby("event_final_state", dropna=False):
        unique = _unique_next_entries(group)
        next_found = int(group["has_next_same_pd_entry"].sum())
        rows.append(
            {
                "event_final_state": state,
                "events": int(len(group)),
                "next_same_pd_found_events": next_found,
                "next_same_pd_found_rate_pct": next_found / len(group) * 100.0 if len(group) else 0.0,
                "unique_next_entries": int(len(unique)),
                "event_level_next_pnl_sum": float(group["next_matched_pnl"].sum()),
                "unique_next_pnl_sum": float(unique["next_matched_pnl"].sum()) if not unique.empty else 0.0,
                "unique_next_win_rate_pct": float(unique["next_matched_pnl"].gt(0).mean() * 100.0)
                if not unique.empty
                else 0.0,
                "unique_next_big_winners": int(unique["next_matched_big_winner"].sum()) if not unique.empty else 0,
                "unique_next_losers": int(unique["next_matched_pnl"].lt(0).sum()) if not unique.empty else 0,
                "unique_next_winners": int(unique["next_matched_pnl"].gt(0).sum()) if not unique.empty else 0,
                "median_days_to_next_entry": float(unique["days_to_next_entry"].median()) if not unique.empty else np.nan,
                "median_next_projected_broker10_pct": float(unique["next_projected_broker10_pct"].median())
                if not unique.empty
                else np.nan,
                "median_next_mfe_minus_mae_r": float(
                    (unique["next_entry_day_mfe_r"] - unique["next_entry_day_mae_r"]).median()
                )
                if not unique.empty
                else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("event_final_state")


def _proxy_summary(event_next: pd.DataFrame) -> pd.DataFrame:
    specs = [
        (
            "RF_NEXT1_block_first_same_pd_after_retry_failed",
            event_next["event_final_state"].astype(str).eq("flat_retry_failed"),
            "After a real-time retry_failed event, block only the next same product-direction entry.",
        ),
        (
            "ALL_STOP_NEXT1_block_first_same_pd_after_any_stop_retry_event",
            event_next["event_final_state"].astype(str).isin(["flat_retry_failed", "flat_no_reentry", "open_after_reentry"]),
            "Diagnostic: after any C9 stop/retry event, block the next same product-direction entry.",
        ),
        (
            "OPEN_RETRY_NEXT1_control_after_open_after_reentry",
            event_next["event_final_state"].astype(str).eq("open_after_reentry"),
            "Control: block next same product-direction entry after retry reentered and stayed open.",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for proxy_id, mask, rule_text in specs:
        affected = _unique_next_entries(event_next[mask].copy())
        pnl = pd.to_numeric(affected["next_matched_pnl"], errors="coerce").fillna(0.0) if not affected.empty else pd.Series(dtype=float)
        losers = affected[pnl.lt(0)] if not affected.empty else pd.DataFrame()
        winners = affected[pnl.gt(0)] if not affected.empty else pd.DataFrame()
        big = affected[pd.to_numeric(affected.get("next_matched_big_winner", 0), errors="coerce").fillna(0).gt(0)] if not affected.empty else pd.DataFrame()
        rows.append(
            {
                "proxy_id": proxy_id,
                "rule_text": rule_text,
                "source_events": int(mask.sum()),
                "affected_unique_next_entries": int(len(affected)),
                "affected_next_pnl": float(pnl.sum()) if not affected.empty else 0.0,
                "proxy_pnl_delta_if_blocked": float(-pnl.sum()) if not affected.empty else 0.0,
                "loser_saved_proxy": float(-losers["next_matched_pnl"].sum()) if not losers.empty else 0.0,
                "winner_cut_proxy": float(-winners["next_matched_pnl"].sum()) if not winners.empty else 0.0,
                "big_winner_cut_proxy": float(-big["next_matched_pnl"].sum()) if not big.empty else 0.0,
                "affected_winners": int(len(winners)),
                "affected_losers": int(len(losers)),
                "affected_big_winners": int(len(big)),
                "median_days_to_next_entry": float(affected["days_to_next_entry"].median()) if not affected.empty else np.nan,
                "judgment": "diagnostic_only_no_engine",
            }
        )
    return pd.DataFrame(rows)


def _yearly_summary(event_next: pd.DataFrame) -> pd.DataFrame:
    retry_failed = event_next[event_next["event_final_state"].astype(str).eq("flat_retry_failed")].copy()
    unique = _unique_next_entries(retry_failed)
    if unique.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for year, group in unique.groupby("next_entry_year", dropna=False):
        rows.append(
            {
                "next_entry_year": int(year) if pd.notna(year) else -1,
                "unique_next_entries_after_retry_failed": int(len(group)),
                "next_pnl_sum": float(group["next_matched_pnl"].sum()),
                "winners": int(group["next_matched_pnl"].gt(0).sum()),
                "losers": int(group["next_matched_pnl"].lt(0).sum()),
                "big_winners": int(group["next_matched_big_winner"].sum()),
                "median_days_to_next_entry": float(group["days_to_next_entry"].median()),
                "median_projected_broker10_pct": float(group["next_projected_broker10_pct"].median()),
            }
        )
    return pd.DataFrame(rows).sort_values("next_entry_year")


def _plot_summary(event_next: pd.DataFrame, state_summary: pd.DataFrame, proxy_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    ax = axes[0, 0]
    ax.barh(
        state_summary["event_final_state"].astype(str),
        state_summary["unique_next_pnl_sum"],
        color=np.where(state_summary["unique_next_pnl_sum"].ge(0), "#16a34a", "#dc2626"),
    )
    ax.axvline(0, color="#171717", linewidth=0.8)
    ax.set_title("Unique next same product-direction PnL by event state")
    ax.grid(True, axis="x", alpha=0.2)

    ax = axes[0, 1]
    data = event_next[event_next["has_next_same_pd_entry"].eq(1)].copy()
    colors = {
        "flat_retry_failed": "#dc2626",
        "flat_no_reentry": "#64748b",
        "open_after_reentry": "#16a34a",
    }
    for state, group in data.groupby("event_final_state", dropna=False):
        ax.scatter(
            group["next_projected_broker10_pct"],
            group["next_matched_pnl"],
            s=np.clip(pd.to_numeric(group["next_matched_volume"], errors="coerce").fillna(1) * 2.0, 20, 160),
            c=colors.get(str(state), "#7c3aed"),
            alpha=0.65,
            label=str(state),
        )
    ax.axhline(0, color="#171717", linewidth=0.8)
    ax.axvline(90, color="#dc2626", linestyle="--", linewidth=0.9)
    ax.set_title("Next entry heat vs PnL")
    ax.set_xlabel("next projected broker10 (%)")
    ax.set_ylabel("next matched PnL")
    ax.grid(True, alpha=0.2)
    ax.legend(loc="best", fontsize=8)

    ax = axes[1, 0]
    ax.barh(
        proxy_summary["proxy_id"],
        proxy_summary["proxy_pnl_delta_if_blocked"],
        color=np.where(proxy_summary["proxy_pnl_delta_if_blocked"].ge(0), "#16a34a", "#dc2626"),
    )
    ax.axvline(0, color="#171717", linewidth=0.8)
    ax.set_title("First next same product-direction block proxy")
    ax.grid(True, axis="x", alpha=0.2)

    ax = axes[1, 1]
    retry_failed = data[data["event_final_state"].astype(str).eq("flat_retry_failed")].copy()
    if retry_failed.empty:
        ax.text(0.5, 0.5, "No retry_failed next-entry observations", ha="center", va="center")
    else:
        ax.hist(retry_failed["days_to_next_entry"].dropna(), bins=min(12, max(3, retry_failed["days_to_next_entry"].nunique())), color="#7c2d12", alpha=0.75)
    ax.set_title("Days to next same product-direction entry after retry_failed")
    ax.set_xlabel("calendar days")
    ax.set_ylabel("events")
    ax.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(SUMMARY_CHART_PATH, dpi=160)
    plt.close(fig)


def _load_minute_groups_for_atlas(selected: pd.DataFrame) -> dict[str, pd.DataFrame]:
    vt_symbols = set(selected["event_vt_symbol"].dropna().astype(str))
    vt_symbols.update(selected["next_contract_vt_symbol"].dropna().astype(str))
    vt_symbols.discard("")
    minute_bars = s864._load_full_minute_bars(vt_symbols)
    return s825._minute_groups(minute_bars)


def _event_markers(row: pd.Series) -> dict[str, Any]:
    return {
        "first_stop": row.get("event_first_stop_time", ""),
        "reentry": row.get("event_reentry_time", ""),
        "retry_failed": row.get("event_retry_failed_time", ""),
    }


def _plot_atlas(event_next: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    retry_failed = event_next[
        event_next["event_final_state"].astype(str).eq("flat_retry_failed") & event_next["has_next_same_pd_entry"].eq(1)
    ].copy()
    if retry_failed.empty:
        return [], pd.DataFrame()
    selected = pd.concat(
        [
            retry_failed.sort_values("next_matched_pnl", ascending=True).head(4),
            retry_failed.sort_values("next_matched_pnl", ascending=False).head(4),
            retry_failed.sort_values("next_projected_broker10_pct", ascending=False).head(4),
        ],
        ignore_index=True,
        sort=False,
    ).drop_duplicates("next_entry_key").head(MAX_ATLAS_ROWS)
    minute_by_symbol = _load_minute_groups_for_atlas(selected)

    paths: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for start in range(0, len(selected), PER_PAGE):
        page_rows = selected.iloc[start : start + PER_PAGE].reset_index(drop=True)
        page = len(paths) + 1
        fig, axes = plt.subplots(len(page_rows), 2, figsize=(16, 4.2 * len(page_rows)), squeeze=False)
        for idx, row in page_rows.iterrows():
            event_levels = {
                "entry": _safe_float(row.get("event_entry_price")),
                "stop": _safe_float(row.get("event_stop_price")),
                "progress": _safe_float(row.get("event_progress_price")),
            }
            event_bars = s864._plot_day(
                axes[idx, 0],
                minute_by_symbol,
                str(row["event_vt_symbol"]),
                row["event_date"],
                (
                    f"event {row['event_vt_symbol']} {row['direction']} {pd.Timestamp(row['event_date']):%Y-%m-%d} "
                    f"{row['event_final_state']}"
                ),
                levels=event_levels,
                markers=_event_markers(row),
            )
            next_levels = {
                "entry": _safe_float(row.get("next_entry_price")),
                "stop": _safe_float(row.get("next_stop_price")),
            }
            if np.isfinite(next_levels["entry"]) and np.isfinite(next_levels["stop"]):
                sign = 1 if str(row["direction"]) == "long" else -1
                distance = abs(next_levels["entry"] - next_levels["stop"])
                next_levels["progress"] = next_levels["entry"] + sign * 0.5 * distance
            next_bars = s864._plot_day(
                axes[idx, 1],
                minute_by_symbol,
                str(row["next_contract_vt_symbol"]),
                row["next_entry_date"],
                (
                    f"next {row['next_contract_vt_symbol']} {row['direction']} {pd.Timestamp(row['next_entry_date']):%Y-%m-%d} "
                    f"PnL={_safe_float(row.get('next_matched_pnl')):.0f} {row.get('next_minute_path_state')}"
                ),
                levels=next_levels,
            )
            manifest_rows.append(
                {
                    "page": page,
                    "event_id": row["event_id"],
                    "event_vt_symbol": row["event_vt_symbol"],
                    "event_date": pd.Timestamp(row["event_date"]).date().isoformat(),
                    "direction": row["direction"],
                    "next_entry_key": row["next_entry_key"],
                    "next_contract_vt_symbol": row["next_contract_vt_symbol"],
                    "next_entry_date": pd.Timestamp(row["next_entry_date"]).date().isoformat(),
                    "days_to_next_entry": row["days_to_next_entry"],
                    "next_matched_pnl": row["next_matched_pnl"],
                    "next_projected_broker10_pct": row["next_projected_broker10_pct"],
                    "next_minute_path_state": row["next_minute_path_state"],
                    "event_day_bars": event_bars,
                    "next_entry_day_bars": next_bars,
                }
            )
        fig.suptitle("Stage869 retry-failed event -> next same product-direction entry atlas", fontsize=13)
        fig.tight_layout()
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=160)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _decision(proxy_summary: pd.DataFrame) -> str:
    if proxy_summary.empty:
        return "stage869_post_retry_damage_no_evidence"
    row = proxy_summary[proxy_summary["proxy_id"].eq("RF_NEXT1_block_first_same_pd_after_retry_failed")]
    if row.empty:
        return "stage869_post_retry_damage_no_evidence"
    item = row.iloc[0]
    delta = _safe_float(item.get("proxy_pnl_delta_if_blocked"), 0.0)
    big_winners = int(_safe_float(item.get("affected_big_winners"), 0.0))
    affected = int(_safe_float(item.get("affected_unique_next_entries"), 0.0))
    if affected < 5:
        return "stage869_post_retry_damage_too_sparse_no_engine"
    if delta > 0 and big_winners == 0:
        return "stage869_retry_failed_next_same_pd_cooldown_candidate_needs_engine"
    return "stage869_retry_failed_next_same_pd_cooldown_rejected_no_engine"


def _write_report(
    event_next: pd.DataFrame,
    state_summary: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    yearly_summary: pd.DataFrame,
    atlas_paths: list[Path],
    decision: str,
) -> None:
    retry_failed = event_next[event_next["event_final_state"].astype(str).eq("flat_retry_failed")].copy()
    top_retry_failed = retry_failed[retry_failed["has_next_same_pd_entry"].eq(1)].sort_values("next_matched_pnl").head(20)
    lines = [
        "# Stage869 C9 retry_failed 后续同产品方向损伤审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读事件后续归因与分钟K视觉复盘；不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- Backtrader stop order documentation：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/",
        "- Backtrader stop/bracket examples：https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/",
        "- 我的判断：二次失败是实时可知的信息，但它是否足以暂停同产品方向，必须看后续第一笔同产品方向 entry 的全周期分布；如果它仍贡献右尾，cooldown 就是过拟合补丁。",
        "",
        "## State Summary",
        "",
        _md_table(state_summary, max_rows=None),
        "",
        "## Proxy Summary",
        "",
        _md_table(proxy_summary, max_rows=None),
        "",
        "## Retry-Failed Next Entry Worst Cases",
        "",
        _md_table(
            top_retry_failed[
                [
                    "event_date",
                    "event_vt_symbol",
                    "direction",
                    "next_entry_date",
                    "days_to_next_entry",
                    "next_contract_vt_symbol",
                    "next_projected_broker10_pct",
                    "next_minute_path_state",
                    "next_matched_pnl",
                    "next_matched_big_winner",
                    "next_matched_exit_reasons",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Yearly Summary",
        "",
        _md_table(yearly_summary, max_rows=None) if not yearly_summary.empty else "_no retry_failed next-entry yearly observations_",
        "",
        "## Visuals",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
    ]
    lines.extend(f"- atlas page：`{path}`" for path in atlas_paths)
    lines.extend(
        [
            "",
            "## Judgment",
            "",
            f"- 决策：`{decision}`。",
            "- 本阶段只验证“retry_failed 后下一笔同产品方向 entry 是否应该被阻断”的证据，不生成正式策略。",
            "- 如果 proxy 净增益不稳定、覆盖样本少或误伤 big winner，则不进入真实引擎；如果证据干净，下一阶段也只能做一次冻结语义引擎，不能扫 cooldown 天数或产品方向阈值。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = _prepare_entries()
    events = _prepare_events()
    event_next = _match_next_same_product_direction(events, entries)
    state_summary = _state_summary(event_next)
    proxy_summary = _proxy_summary(event_next)
    yearly_summary = _yearly_summary(event_next)
    _plot_summary(event_next, state_summary, proxy_summary)
    atlas_paths, atlas_manifest = _plot_atlas(event_next)
    decision = _decision(proxy_summary)

    event_next.to_csv(EVENT_NEXT_PATH, index=False, encoding="utf-8-sig")
    state_summary.to_csv(STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    yearly_summary.to_csv(YEARLY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(event_next, state_summary, proxy_summary, yearly_summary, atlas_paths, decision)

    rf_proxy = proxy_summary[proxy_summary["proxy_id"].eq("RF_NEXT1_block_first_same_pd_after_retry_failed")]
    rf_row = rf_proxy.iloc[0].to_dict() if not rf_proxy.empty else {}
    payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "inputs": {
            "stage868_stop_retry_events": str(s868.STOP_RETRY_EVENTS_PATH),
            "stage865_entry_audit": str(s865.ENTRY_AUDIT_PATH),
            "stage866_entry_path_features": str(s866.ENTRY_PATH_FEATURES_PATH),
        },
        "counts": {
            "c9_stop_retry_events": int(len(events)),
            "c9_events_with_next_same_pd_entry": int(event_next["has_next_same_pd_entry"].sum()),
            "retry_failed_events": int(event_next["event_final_state"].astype(str).eq("flat_retry_failed").sum()),
            "retry_failed_with_next_same_pd_entry": int(
                (
                    event_next["event_final_state"].astype(str).eq("flat_retry_failed")
                    & event_next["has_next_same_pd_entry"].eq(1)
                ).sum()
            ),
        },
        "state_summary": state_summary.to_dict("records"),
        "proxy_summary": proxy_summary.to_dict("records"),
        "rf_next1_proxy": rf_row,
        "decision": decision,
        "overfit_reflection": (
            "本阶段不是策略过拟合：只用 C9 已产生的实时 retry_failed 事件，检查后续第一笔同产品方向 entry，"
            "没有扫描 cooldown 天数、阈值、品种、方向或年份。"
        ),
        "continue_value": (
            "有条件继续：若 retry_failed 后第一笔同产品方向 entry 的阻断 proxy 干净，下一步可做一次冻结引擎；"
            "若误伤右尾或样本混杂，则停止该 cooldown 方向。"
        ),
        "outputs": {
            "event_next": str(EVENT_NEXT_PATH),
            "state_summary": str(STATE_SUMMARY_PATH),
            "proxy_summary": str(PROXY_SUMMARY_PATH),
            "yearly_summary": str(YEARLY_SUMMARY_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
