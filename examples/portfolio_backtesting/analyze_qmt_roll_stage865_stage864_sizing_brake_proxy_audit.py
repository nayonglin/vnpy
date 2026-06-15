from __future__ import annotations

from datetime import datetime
import json
import math
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
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage865"
MODEL_TAG = "stage865_stage864_sizing_brake_proxy_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage865_stage864_sizing_brake_proxy_audit"

C9_ARM = s864.C9_ARM
BROKER_MARGIN_MULTIPLIER = s864.BROKER_MARGIN_MULTIPLIER
TARGET_PROJECTED_BROKER10_PCT = 90.0
HARD_PROJECTED_BROKER10_CAP_PCT = 100.0
EXISTING_SINGLE_ADD_BROKER10_WATCH_PCT = 20.0
STACKED_BEFORE_BROKER10_WATCH_PCT = 50.0
MATCH_LOOKAHEAD_DAYS = 4

ENTRY_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_audit_{MODEL_TAG}.csv"
BRAKE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_brake_summary_{MODEL_TAG}.csv"
PEAK_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_peak_precursor_coverage_{MODEL_TAG}.csv"
YEARLY_IMPACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_proxy_impact_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


BRAKE_SPECS = [
    {
        "brake_id": "SBB0_projected90_heat_buffer",
        "description": "投影 broker10 after-entry >= 90%，按 90% 目标等比例缩手。",
    },
    {
        "brake_id": "SBB1_nearcap90_largeadd20",
        "description": "投影 broker10 >= 90%，且单笔新增 broker10 >= 20%。",
    },
    {
        "brake_id": "SBB2_stacked50_largeadd20",
        "description": "下单前 broker10 >= 50%，且单笔新增 broker10 >= 20%；若投影超过 90% 才实际缩手。",
    },
    {
        "brake_id": "WATCH_single_add20",
        "description": "只读观察：单笔新增 broker10 >= 20%，用于衡量覆盖面，不作为可执行 brake。",
    },
]


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalize_date(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _prepare_curve(curve: pd.DataFrame) -> pd.DataFrame:
    data = curve[curve["arm"].eq(C9_ARM)].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "net_pnl"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for window in [63, 126, 252]:
        data[f"trail{window}_min_equity"] = data["account_equity"].rolling(window, min_periods=1).min().shift(1)
        data[f"trail{window}_max_equity"] = data["account_equity"].rolling(window, min_periods=1).max().shift(1)
    return data


def _prepare_entries(entry_risk: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    data = entry_risk[entry_risk["profile"].eq(C9_ARM)].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    numeric_columns = [
        "selected_volume",
        "selected_volume_ungated",
        "estimated_equity",
        "total_margin_in_use_before",
        "target_risk_amount",
        "actual_risk_amount",
        "margin_per_contract",
        "actual_margin_amount",
        "projected_total_margin_after",
        "risk_multiplier",
        "portfolio_drawdown_pct",
        "portfolio_equity_high_water",
        "entry_price",
        "stop_price",
        "planned_entry_price",
        "stop_distance",
        "size",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data[pd.to_numeric(data["selected_volume"], errors="coerce").fillna(0) > 0].copy()
    data["before_broker10_pct"] = (
        data["total_margin_in_use_before"] * BROKER_MARGIN_MULTIPLIER / data["estimated_equity"] * 100.0
    )
    data["add_broker10_pct"] = data["actual_margin_amount"] * BROKER_MARGIN_MULTIPLIER / data["estimated_equity"] * 100.0
    data["projected_broker10_pct"] = (
        data["projected_total_margin_after"] * BROKER_MARGIN_MULTIPLIER / data["estimated_equity"] * 100.0
    )
    data["projected_cap_buffer_pct"] = HARD_PROJECTED_BROKER10_CAP_PCT - data["projected_broker10_pct"]
    data["added_margin_share_of_projected"] = data["actual_margin_amount"] / data["projected_total_margin_after"]
    curve_features = curve[
        [
            "date",
            "trail63_min_equity",
            "trail126_min_equity",
            "trail252_min_equity",
            "trail63_max_equity",
            "trail126_max_equity",
            "trail252_max_equity",
        ]
    ].copy()
    data = data.merge(curve_features, on="date", how="left")
    for window in [63, 126, 252]:
        data[f"runup{window}_from_trailing_min"] = data["estimated_equity"] / data[f"trail{window}_min_equity"]
        data[f"distance_from_trail{window}_max"] = data["estimated_equity"] / data[f"trail{window}_max_equity"]
    data["entry_key"] = np.arange(len(data))
    return data.reset_index(drop=True)


def _prepare_closed_lots(closed_lots: pd.DataFrame) -> pd.DataFrame:
    data = closed_lots[closed_lots["arm"].eq(C9_ARM)].copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    for column in [
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "volume",
        "big_winner",
        "selected_volume",
        "entry_price",
        "exit_price",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["entry_date", "vt_symbol", "direction"]).reset_index(drop=True)


def _match_closed_lots(entries: pd.DataFrame, closed_lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in entries.iterrows():
        signal_date = _normalize_date(row["date"])
        vt_symbol = str(row["contract_vt_symbol"])
        direction = str(row["direction"])
        candidates = closed_lots[
            closed_lots["vt_symbol"].astype(str).eq(vt_symbol)
            & closed_lots["direction"].astype(str).eq(direction)
            & closed_lots["entry_date"].between(signal_date, signal_date + pd.Timedelta(days=MATCH_LOOKAHEAD_DAYS))
        ].copy()
        if candidates.empty:
            rows.append(
                {
                    "entry_key": row["entry_key"],
                    "matched_lots": 0,
                    "matched_entry_date": pd.NaT,
                    "matched_signal": "",
                    "matched_volume": 0.0,
                    "matched_volume_distance": np.nan,
                    "matched_pnl": 0.0,
                    "matched_risk": 0.0,
                    "matched_r_multiple_sum": 0.0,
                    "matched_max_r": np.nan,
                    "matched_winner": 0,
                    "matched_big_winner": 0,
                    "matched_exit_reasons": "",
                }
            )
            continue
        groups: list[dict[str, Any]] = []
        for entry_date, group in candidates.groupby("entry_date", dropna=False):
            volume = float(group["volume"].sum())
            pnl = float(group["realized_pnl"].sum())
            groups.append(
                {
                    "entry_key": row["entry_key"],
                    "matched_lots": int(len(group)),
                    "matched_entry_date": entry_date,
                    "matched_signal": ",".join(sorted(set(group["signal"].dropna().astype(str)))),
                    "matched_volume": volume,
                    "matched_volume_distance": abs(volume - _safe_float(row.get("selected_volume"), 0.0)),
                    "matched_date_distance": abs((pd.Timestamp(entry_date) - signal_date).days),
                    "matched_pnl": pnl,
                    "matched_risk": float(group["risk_amount"].sum()),
                    "matched_r_multiple_sum": float(group["r_multiple"].sum()),
                    "matched_max_r": float(group["r_multiple"].max()),
                    "matched_winner": int(pnl > 0),
                    "matched_big_winner": int(group["big_winner"].max() > 0),
                    "matched_exit_reasons": ",".join(sorted(set(group["exit_reason"].dropna().astype(str)))),
                }
            )
        rows.append(sorted(groups, key=lambda item: (item["matched_date_distance"], item["matched_volume_distance"]))[0])
    matched = pd.DataFrame(rows)
    return entries.merge(matched, on="entry_key", how="left")


def _brake_flags(frame: pd.DataFrame, brake_id: str) -> pd.Series:
    if brake_id == "SBB0_projected90_heat_buffer":
        return frame["projected_broker10_pct"].ge(TARGET_PROJECTED_BROKER10_PCT)
    if brake_id == "SBB1_nearcap90_largeadd20":
        return frame["projected_broker10_pct"].ge(TARGET_PROJECTED_BROKER10_PCT) & frame["add_broker10_pct"].ge(
            EXISTING_SINGLE_ADD_BROKER10_WATCH_PCT
        )
    if brake_id == "SBB2_stacked50_largeadd20":
        return frame["before_broker10_pct"].ge(STACKED_BEFORE_BROKER10_WATCH_PCT) & frame["add_broker10_pct"].ge(
            EXISTING_SINGLE_ADD_BROKER10_WATCH_PCT
        )
    if brake_id == "WATCH_single_add20":
        return frame["add_broker10_pct"].ge(EXISTING_SINGLE_ADD_BROKER10_WATCH_PCT)
    raise KeyError(brake_id)


def _apply_brake_columns(entries: pd.DataFrame) -> pd.DataFrame:
    data = entries.copy()
    target_exchange_margin = data["estimated_equity"] * TARGET_PROJECTED_BROKER10_PCT / 100.0 / BROKER_MARGIN_MULTIPLIER
    allowed_add_margin = (target_exchange_margin - data["total_margin_in_use_before"]).clip(lower=0)
    raw_after = np.floor(data["selected_volume"] * (allowed_add_margin / data["actual_margin_amount"]).clip(lower=0, upper=1))
    raw_after = np.minimum(raw_after, data["selected_volume"]).fillna(data["selected_volume"])
    for spec in BRAKE_SPECS:
        brake_id = spec["brake_id"]
        flag = _brake_flags(data, brake_id).fillna(False)
        after = np.where(flag, raw_after, data["selected_volume"])
        after = np.minimum(after, data["selected_volume"])
        reduction_ratio = np.where(data["selected_volume"] > 0, 1.0 - after / data["selected_volume"], 0.0)
        reduction_ratio = np.where(np.isfinite(reduction_ratio), reduction_ratio, 0.0)
        data[f"flag_{brake_id}"] = flag.astype(int)
        data[f"selected_after_{brake_id}"] = after
        data[f"reduction_ratio_{brake_id}"] = reduction_ratio
        data[f"proxy_pnl_delta_{brake_id}"] = -data["matched_pnl"] * reduction_ratio
        data[f"proxy_margin_reduced_{brake_id}"] = data["actual_margin_amount"] * reduction_ratio
    return data


def _brake_summary(entries: pd.DataFrame) -> pd.DataFrame:
    total_entries = len(entries)
    matched_total_pnl = float(entries["matched_pnl"].sum())
    rows: list[dict[str, Any]] = []
    for spec in BRAKE_SPECS:
        brake_id = spec["brake_id"]
        flag_col = f"flag_{brake_id}"
        reduction_col = f"reduction_ratio_{brake_id}"
        delta_col = f"proxy_pnl_delta_{brake_id}"
        flagged = entries[entries[flag_col].eq(1)].copy()
        reduced = flagged[flagged[reduction_col].gt(0)].copy()
        loser = reduced[reduced["matched_pnl"].lt(0)]
        winner = reduced[reduced["matched_pnl"].gt(0)]
        big = reduced[reduced["matched_big_winner"].gt(0)]
        rows.append(
            {
                "brake_id": brake_id,
                "description": spec["description"],
                "flagged_entries": int(len(flagged)),
                "flagged_rate_pct": len(flagged) / total_entries * 100.0 if total_entries else 0.0,
                "reduced_entries": int(len(reduced)),
                "avg_reduction_ratio": float(reduced[reduction_col].mean()) if not reduced.empty else 0.0,
                "flagged_matched_pnl": float(flagged["matched_pnl"].sum()),
                "reduced_matched_pnl": float(reduced["matched_pnl"].sum()),
                "proxy_pnl_delta": float(reduced[delta_col].sum()),
                "proxy_pnl_delta_vs_total_pnl_pct": float(reduced[delta_col].sum() / matched_total_pnl * 100.0)
                if matched_total_pnl
                else np.nan,
                "loser_saved_proxy": float((-loser["matched_pnl"] * loser[reduction_col]).sum()),
                "winner_cut_proxy": float((-winner["matched_pnl"] * winner[reduction_col]).sum()),
                "big_winner_cut_proxy": float((-big["matched_pnl"] * big[reduction_col]).sum()),
                "flagged_big_winner_entries": int((flagged["matched_big_winner"] > 0).sum()),
                "reduced_big_winner_entries": int((big["matched_big_winner"] > 0).sum()),
                "flagged_win_rate_pct": float((flagged["matched_pnl"] > 0).mean() * 100.0) if not flagged.empty else 0.0,
                "flagged_median_projected_broker10_pct": float(flagged["projected_broker10_pct"].median())
                if not flagged.empty
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _peak_precursor_coverage(entries: pd.DataFrame) -> pd.DataFrame:
    pair_delta = _load_required_csv(s864.PAIR_DELTA_PATH)
    peaks = _load_required_csv(s864.PEAK_DATES_PATH)
    peaks["date"] = pd.to_datetime(peaks["date"], errors="coerce").dt.normalize()
    c9_focus_dates = set(peaks[peaks["peak_owner_arm"].eq(C9_ARM)]["date"].dropna())
    pair_delta["focus_date_ts"] = pd.to_datetime(pair_delta["focus_date"], errors="coerce").dt.normalize()
    focus = pair_delta[pair_delta["focus_date_ts"].isin(c9_focus_dates)].copy()
    focus["c9_volume"] = pd.to_numeric(focus["c9_volume"], errors="coerce")
    focus = focus[focus["c9_volume"].fillna(0) > 0].copy()
    rows: list[dict[str, Any]] = []
    for _, row in focus.iterrows():
        entry_date = pd.to_datetime(row.get("c9_entry_date"), errors="coerce")
        candidates = entries[
            entries["contract_vt_symbol"].astype(str).eq(str(row.get("vt_symbol")))
            & entries["direction"].astype(str).eq(str(row.get("direction")))
        ].copy()
        if pd.notna(entry_date):
            entry_date = entry_date.normalize()
            candidates = candidates[
                (candidates["date"].le(entry_date))
                & (candidates["date"].ge(entry_date - pd.Timedelta(days=MATCH_LOOKAHEAD_DAYS)))
            ].copy()
        if candidates.empty:
            item = row.to_dict()
            item.update({"matched_entry_key": np.nan, "entry_match_found": 0})
            rows.append(item)
            continue
        candidates["date_distance"] = (entry_date - candidates["date"]).dt.days.abs() if pd.notna(entry_date) else 0
        candidates["volume_distance"] = (
            pd.to_numeric(candidates["selected_volume"], errors="coerce") - _safe_float(row.get("c9_volume"), 0.0)
        ).abs()
        match = candidates.sort_values(["date_distance", "volume_distance"]).iloc[0]
        item = row.to_dict()
        item.update(
            {
                "matched_entry_key": match["entry_key"],
                "entry_match_found": 1,
                "entry_decision_date": pd.Timestamp(match["date"]).date().isoformat(),
                "entry_selected_volume": _safe_float(match.get("selected_volume")),
                "entry_before_broker10_pct": _safe_float(match.get("before_broker10_pct")),
                "entry_add_broker10_pct": _safe_float(match.get("add_broker10_pct")),
                "entry_projected_broker10_pct": _safe_float(match.get("projected_broker10_pct")),
                "entry_runup63_from_trailing_min": _safe_float(match.get("runup63_from_trailing_min")),
                "matched_pnl": _safe_float(match.get("matched_pnl")),
                "matched_big_winner": int(_safe_float(match.get("matched_big_winner"), 0) > 0),
            }
        )
        for spec in BRAKE_SPECS:
            brake_id = spec["brake_id"]
            item[f"flag_{brake_id}"] = int(_safe_float(match.get(f"flag_{brake_id}"), 0) > 0)
            item[f"reduction_ratio_{brake_id}"] = _safe_float(match.get(f"reduction_ratio_{brake_id}"), 0.0)
            item[f"proxy_pnl_delta_{brake_id}"] = _safe_float(match.get(f"proxy_pnl_delta_{brake_id}"), 0.0)
        rows.append(item)
    coverage = pd.DataFrame(rows)
    if not coverage.empty:
        coverage = coverage.sort_values(
            ["focus_date", "c9_estimated_broker10_margin_to_equity_pct", "broker10_pct_delta_c9_minus_c4"],
            ascending=[True, False, False],
        )
    return coverage


def _add_peak_counts_to_summary(summary: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    if coverage.empty:
        for column in ["peak_rows", "peak_unique_entries", "peak_unique_flagged", "peak_unique_reduced"]:
            summary[column] = 0
        return summary
    unique_keys = coverage[coverage["entry_match_found"].eq(1)].drop_duplicates("matched_entry_key")
    result = summary.copy()
    result["peak_rows"] = int(len(coverage))
    result["peak_unique_entries"] = int(len(unique_keys))
    for spec in BRAKE_SPECS:
        brake_id = spec["brake_id"]
        flag_col = f"flag_{brake_id}"
        red_col = f"reduction_ratio_{brake_id}"
        mask = result["brake_id"].eq(brake_id)
        result.loc[mask, "peak_unique_flagged"] = int(unique_keys[flag_col].sum()) if flag_col in unique_keys else 0
        result.loc[mask, "peak_unique_reduced"] = int(unique_keys[red_col].gt(0).sum()) if red_col in unique_keys else 0
    return result


def _yearly_proxy_impact(entries: pd.DataFrame) -> pd.DataFrame:
    data = entries.copy()
    data["entry_year"] = pd.to_datetime(data["date"], errors="coerce").dt.year
    rows: list[dict[str, Any]] = []
    for (year,), group in data.groupby(["entry_year"], dropna=False):
        row: dict[str, Any] = {
            "entry_year": int(year) if pd.notna(year) else -1,
            "entries": int(len(group)),
            "matched_pnl": float(group["matched_pnl"].sum()),
            "big_winner_entries": int(group["matched_big_winner"].sum()),
        }
        for spec in BRAKE_SPECS:
            brake_id = spec["brake_id"]
            row[f"{brake_id}_flagged"] = int(group[f"flag_{brake_id}"].sum())
            row[f"{brake_id}_reduced"] = int(group[f"reduction_ratio_{brake_id}"].gt(0).sum())
            row[f"{brake_id}_proxy_delta"] = float(group[f"proxy_pnl_delta_{brake_id}"].sum())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("entry_year")


def _plot_summary(entries: pd.DataFrame, summary: pd.DataFrame, coverage: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    ax = axes[0, 0]
    colors = np.where(entries["matched_big_winner"].gt(0), "#16a34a", "#64748b")
    sizes = np.clip(entries["add_broker10_pct"].fillna(0) * 3.0, 15, 160)
    ax.scatter(entries["projected_broker10_pct"], entries["matched_pnl"], s=sizes, c=colors, alpha=0.65, linewidth=0.2)
    ax.axvline(TARGET_PROJECTED_BROKER10_PCT, color="#dc2626", linestyle="--", linewidth=1.0)
    ax.axhline(0, color="#171717", linewidth=0.8)
    ax.set_title("C9 entry projected broker10 vs matched PnL")
    ax.set_xlabel("projected broker10 after entry (%)")
    ax.set_ylabel("matched closed-lot PnL")
    ax.grid(True, alpha=0.2)

    ax = axes[0, 1]
    ax.scatter(entries["before_broker10_pct"], entries["add_broker10_pct"], s=35, c="#2563eb", alpha=0.5)
    ax.axhline(EXISTING_SINGLE_ADD_BROKER10_WATCH_PCT, color="#dc2626", linestyle="--", linewidth=1.0)
    ax.axvline(STACKED_BEFORE_BROKER10_WATCH_PCT, color="#7c3aed", linestyle="--", linewidth=1.0)
    ax.set_title("Before heat vs single-entry add heat")
    ax.set_xlabel("before broker10 (%)")
    ax.set_ylabel("single add broker10 (%)")
    ax.grid(True, alpha=0.2)

    ax = axes[1, 0]
    compact = summary.copy()
    ax.barh(compact["brake_id"], compact["proxy_pnl_delta"], color=np.where(compact["proxy_pnl_delta"] >= 0, "#16a34a", "#dc2626"))
    ax.axvline(0, color="#171717", linewidth=0.8)
    ax.set_title("Proxy PnL delta if reduced to 90% projected broker10")
    ax.set_xlabel("proxy PnL delta")
    ax.grid(True, axis="x", alpha=0.2)

    ax = axes[1, 1]
    if not coverage.empty:
        plot_cov = coverage[coverage["entry_match_found"].eq(1)].copy()
        x = pd.to_datetime(plot_cov["focus_date"], errors="coerce")
        ax.scatter(x, pd.to_numeric(plot_cov["c9_estimated_broker10_margin_to_equity_pct"], errors="coerce"), c="#f97316", alpha=0.7)
        ax.set_title("C9 peak-date active lots covered by entry proxies")
        ax.set_ylabel("C9 active-lot broker10 pct")
    else:
        ax.text(0.5, 0.5, "no peak coverage rows", ha="center", va="center")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(SUMMARY_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_atlas(coverage: pd.DataFrame, entries: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if coverage.empty:
        return [], pd.DataFrame()
    selected = coverage[coverage["entry_match_found"].eq(1)].copy()
    selected["c9_pct"] = pd.to_numeric(selected["c9_estimated_broker10_margin_to_equity_pct"], errors="coerce").fillna(0.0)
    selected["abs_delta"] = pd.to_numeric(selected["broker10_pct_delta_c9_minus_c4"], errors="coerce").abs().fillna(0.0)
    selected = selected.sort_values(["c9_pct", "abs_delta"], ascending=False).drop_duplicates(
        ["vt_symbol", "direction", "c9_entry_date"]
    ).head(8)
    if selected.empty:
        return [], pd.DataFrame()
    vt_symbols = set(selected["vt_symbol"].dropna().astype(str))
    minute_bars = s864._load_full_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    paths: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    per_page = 2
    for page_start in range(0, len(selected), per_page):
        page_rows = selected.iloc[page_start : page_start + per_page].reset_index(drop=True)
        page_number = len(paths) + 1
        fig, axes = plt.subplots(len(page_rows), 2, figsize=(14, 4.5 * len(page_rows)), squeeze=False)
        for row_idx, row in page_rows.iterrows():
            entry_key = row.get("matched_entry_key")
            entry = entries[entries["entry_key"].eq(entry_key)]
            entry_row = entry.iloc[0] if not entry.empty else pd.Series(dtype=object)
            vt_symbol = str(row["vt_symbol"])
            direction = str(row["direction"])
            entry_date = pd.to_datetime(row.get("c9_entry_date"), errors="coerce")
            focus_date = pd.to_datetime(row.get("focus_date"), errors="coerce")
            levels = {
                "entry": _safe_float(entry_row.get("entry_price")),
                "stop": _safe_float(entry_row.get("stop_price")),
            }
            bars_entry = s864._plot_day(
                axes[row_idx, 0],
                minute_by_symbol,
                vt_symbol,
                entry_date,
                f"{vt_symbol} {direction} entry {entry_date:%Y-%m-%d} proj={_safe_float(row.get('entry_projected_broker10_pct')):.1f}%",
                levels=levels,
            )
            bars_focus = s864._plot_day(
                axes[row_idx, 1],
                minute_by_symbol,
                vt_symbol,
                focus_date,
                f"{vt_symbol} focus {focus_date:%Y-%m-%d} c9_pct={_safe_float(row.get('c9_estimated_broker10_margin_to_equity_pct')):.1f}%",
                levels=levels,
            )
            manifest_rows.append(
                {
                    "page": page_number,
                    "vt_symbol": vt_symbol,
                    "direction": direction,
                    "entry_date": entry_date.date().isoformat() if pd.notna(entry_date) else "",
                    "focus_date": focus_date.date().isoformat() if pd.notna(focus_date) else "",
                    "entry_bars": bars_entry,
                    "focus_bars": bars_focus,
                    "entry_projected_broker10_pct": _safe_float(row.get("entry_projected_broker10_pct")),
                    "c9_estimated_broker10_margin_to_equity_pct": _safe_float(
                        row.get("c9_estimated_broker10_margin_to_equity_pct")
                    ),
                    "flag_SBB0": int(_safe_float(row.get("flag_SBB0_projected90_heat_buffer"), 0) > 0),
                }
            )
        fig.tight_layout()
        path = Path(str(ATLAS_TEMPLATE).format(page=page_number))
        fig.savefig(path, dpi=160)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _write_report(
    entries: pd.DataFrame,
    summary: pd.DataFrame,
    coverage: pd.DataFrame,
    yearly: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    top_reductions = entries.sort_values("reduction_ratio_SBB0_projected90_heat_buffer", ascending=False).head(15)
    lines = [
        "# Stage865 sizing brake只读代理审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读代理审计与分钟K视觉复盘；不写新规则、不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py GitHub：https://github.com/vnpy/vnpy",
        "- backtesting.py 逐 bar 回放文档：https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html",
        "- 我的判断：仓位 brake 必须只使用下单当时已知的账户状态，且要区分“降低保证金峰值”和“误杀趋势右尾”。本阶段只做代理，不把结果写进引擎。",
        "",
        "## Proxy Definitions",
        "",
        _md_table(pd.DataFrame(BRAKE_SPECS), max_rows=None),
        "",
        "## Brake Summary",
        "",
        _md_table(summary, max_rows=None),
        "",
        "## Top SBB0 Reductions",
        "",
        _md_table(
            top_reductions[
                [
                    "date",
                    "contract_vt_symbol",
                    "direction",
                    "selected_volume",
                    "before_broker10_pct",
                    "add_broker10_pct",
                    "projected_broker10_pct",
                    "matched_pnl",
                    "matched_big_winner",
                    "selected_after_SBB0_projected90_heat_buffer",
                    "reduction_ratio_SBB0_projected90_heat_buffer",
                    "proxy_pnl_delta_SBB0_projected90_heat_buffer",
                ]
            ],
            max_rows=15,
        ),
        "",
        "## Peak Precursor Coverage",
        "",
        _md_table(
            coverage[
                [
                    "focus_date",
                    "vt_symbol",
                    "direction",
                    "c9_entry_date",
                    "c9_volume",
                    "c9_estimated_broker10_margin_to_equity_pct",
                    "broker10_pct_delta_c9_minus_c4",
                    "entry_decision_date",
                    "entry_projected_broker10_pct",
                    "entry_add_broker10_pct",
                    "matched_pnl",
                    "flag_SBB0_projected90_heat_buffer",
                    "reduction_ratio_SBB0_projected90_heat_buffer",
                ]
            ]
            if not coverage.empty
            else pd.DataFrame(),
            max_rows=30,
        ),
        "",
        "## Yearly Proxy Impact",
        "",
        _md_table(yearly, max_rows=None),
        "",
        "## Visuals",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
    ]
    for path in atlas_paths:
        lines.append(f"- atlas page：`{path}`")
    lines.extend(
        [
            "",
            "## Judgment",
            "",
            "- Stage865 不产生新策略。SBB0/SBB1/SBB2 均能命中部分 broker10 峰值前的高热下单，但代理缩手后净 PnL 为负或接近负，且会削掉明确的大赢家，说明当前账户层 heat brake 太粗。",
            "- 下一步若继续，不能把 `90%/20%/50%` 这类代理直接升为引擎；需要先找更本质的实时状态变量，例如投影保证金高热后的分钟内价格确认失败、权益分母快速回落的即时触发，或只对已证明的二次失败路径缩手。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    curve = _prepare_curve(_load_required_csv(s864.CURVE_IN))
    entries = _prepare_entries(_load_required_csv(s864.ENTRY_RISK_IN), curve)
    closed_lots = _prepare_closed_lots(_load_required_csv(s864.CLOSED_LOTS_IN))
    entries = _match_closed_lots(entries, closed_lots)
    entries = _apply_brake_columns(entries)
    summary = _brake_summary(entries)
    coverage = _peak_precursor_coverage(entries)
    summary = _add_peak_counts_to_summary(summary, coverage)
    yearly = _yearly_proxy_impact(entries)
    _plot_summary(entries, summary, coverage)
    atlas_paths, atlas_manifest = _plot_atlas(coverage, entries)

    entries.to_csv(ENTRY_AUDIT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(BRAKE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(PEAK_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_IMPACT_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(entries, summary, coverage, yearly, atlas_paths)

    best_summary = summary.sort_values("proxy_pnl_delta", ascending=False).head(1).to_dict("records")
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "inputs": {
            "stage863_entry_risk": str(s864.ENTRY_RISK_IN),
            "stage863_closed_lots": str(s864.CLOSED_LOTS_IN),
            "stage863_curve": str(s864.CURVE_IN),
            "stage864_peak_dates": str(s864.PEAK_DATES_PATH),
            "stage864_pair_delta": str(s864.PAIR_DELTA_PATH),
            "entries": int(len(entries)),
            "matched_entries": int((entries["matched_lots"] > 0).sum()),
        },
        "brake_summary": summary.to_dict("records"),
        "best_proxy_by_pnl_delta": best_summary,
        "decision": "stage865_sizing_brake_proxy_too_blunt_no_engine",
        "overfit_reflection": (
            "不是正式策略过拟合，但这些代理仍有过拟合风险。本阶段只使用下单时已知账户字段做只读审计，"
            "没有按日期、品种、方向或峰值样本写规则；结果反而显示 heat brake 容易误伤右尾。"
        ),
        "continue_value": (
            "有继续价值，但不能沿 90/20/50 这类账户热度阈值继续扫参。下一步必须引入分钟内价格路径失败或二次失败纪律，"
            "否则账户层缩手会变成机械降风险。"
        ),
        "outputs": {
            "entry_audit": str(ENTRY_AUDIT_PATH),
            "brake_summary": str(BRAKE_SUMMARY_PATH),
            "peak_precursor_coverage": str(PEAK_COVERAGE_PATH),
            "yearly_proxy_impact": str(YEARLY_IMPACT_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("brake_summary")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
