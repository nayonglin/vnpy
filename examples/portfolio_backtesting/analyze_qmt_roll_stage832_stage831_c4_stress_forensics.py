from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage752_theoretical_winner_kline_atlas as s752
import analyze_qmt_roll_stage815_stage813_top40_loss_kline_atlas as s815
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap as s830
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage832"
MODEL_TAG = "stage832_stage831_c4_stress_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage832_stage831_c4_stress_forensics"

STAGE831_TAG = "stage831_stage830_c4_yearly_robustness_v1"
STAGE831_PREFIX = "qmt_roll_stage831_stage830_c4_yearly_robustness"
STAGE831_COMPARISON_PATH = OUTPUT_DIR / f"{STAGE831_PREFIX}_comparison_{STAGE831_TAG}.csv"

BASE_ARM = s830.BASE_ARM
CAP_ARM = s830.CAP_ARM
DATA_END = pd.Timestamp("2026-05-29")
BROKER100 = 100.0
DD50 = -50.0
MAX_WORKERS = max(1, min(2, int(os.environ.get("STAGE832_MAX_WORKERS", "2"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
CONTRACT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_margin_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
STRESS_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stress_days_{MODEL_TAG}.csv"
STRESS_ANCHORS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stress_anchors_{MODEL_TAG}.csv"
TOP_MARGIN_PRODUCTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_margin_products_{MODEL_TAG}.csv"
CAP_EVENT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cap_event_summary_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
PATH_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stress_path_chart_{MODEL_TAG}.png"
MARGIN_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anchor_margin_chart_{MODEL_TAG}.png"
KLINE_ATLAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stress_kline_atlas_{MODEL_TAG}.png"
INTRADAY_ATLAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_event_atlas_{MODEL_TAG}.png"

_WORKER_STATE: dict[str, Any] = {}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _naive_date_series(series: pd.Series) -> pd.Series:
    def convert(value: Any) -> pd.Timestamp:
        if pd.isna(value):
            return pd.NaT
        ts = pd.Timestamp(value)
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)
        return ts.normalize()

    return series.map(convert)


def _ensure_worker_state() -> dict[str, Any]:
    if _WORKER_STATE:
        return _WORKER_STATE
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)
    _WORKER_STATE["metadata"] = metadata
    return _WORKER_STATE


def _stress_start_months() -> list[str]:
    if not STAGE831_COMPARISON_PATH.exists():
        raise FileNotFoundError(f"missing Stage831 comparison: {STAGE831_COMPARISON_PATH}")
    comparison = pd.read_csv(STAGE831_COMPARISON_PATH, encoding="utf-8-sig")
    for column in ["C4_broker100_fail", "dd50_fail_C4", "dd50_fail_A"]:
        comparison[column] = pd.to_numeric(comparison.get(column, 0), errors="coerce").fillna(0.0)
    stress = comparison[
        comparison["C4_broker100_fail"].gt(0)
        | comparison["dd50_fail_C4"].gt(comparison["dd50_fail_A"])
    ].copy()
    starts = stress["start_month"].astype(str).tolist()
    if not starts:
        starts = comparison.sort_values("max_broker10_margin_to_equity_pct_C4", ascending=False)["start_month"].head(4).astype(str).tolist()
    return starts


def _profile_for_arm(metadata: dict[str, Any], arm: str, start: pd.Timestamp) -> dict[str, Any]:
    start_text = _month_text(start)
    if arm == BASE_ARM:
        profile = s827._profile(metadata, enabled=False)
        label = f"Stage832 Stage819 baseline stress forensics {start_text}"
        note = "Stage832 stress forensics A arm."
    elif arm == CAP_ARM:
        profile = s830._cap_profile(metadata)
        label = f"Stage832 Stage830 C4 stress forensics {start_text}"
        note = "Stage832 stress forensics C4 arm; frozen Stage830 parameters."
    else:
        raise ValueError(f"unknown arm: {arm}")
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"stage832_{arm}_{start_text.replace('-', '_')}",
        label=label,
        note=f"{spec.capital.note} | {note}",
    )
    result = dict(profile)
    result["spec"] = replace(spec, capital=capital, profile=result["profile"])
    return result


def _contract_margin(positions: pd.DataFrame, metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if positions.empty:
        return pd.DataFrame(), pd.DataFrame()
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["end_pos", "close_price", "pre_close", "holding_pnl", "trading_pnl", "net_pnl"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["size"] = frame["vt_symbol"].map(metadata["sizes"]).fillna(1.0).astype(float)
    frame["margin_ratio"] = frame["vt_symbol"].map(metadata["margin_ratios"]).fillna(0.15).astype(float)
    frame["product_vt_symbol"] = frame["vt_symbol"].map(s513._product_from_contract)
    frame["position_direction"] = np.select(
        [frame["end_pos"].gt(0), frame["end_pos"].lt(0)],
        ["long", "short"],
        default="flat",
    )
    frame["abs_end_pos"] = frame["end_pos"].abs()
    frame["c3_margin_exact"] = (
        frame["abs_end_pos"] * frame["close_price"].clip(lower=0.0) * frame["size"] * frame["margin_ratio"]
    )
    frame = frame[frame["abs_end_pos"].gt(0)].copy()
    product = (
        frame.groupby(["start_month", "arm", "variant", "date", "product_vt_symbol", "position_direction"], as_index=False)
        .agg(
            c3_margin_exact=("c3_margin_exact", "sum"),
            abs_end_pos=("abs_end_pos", "sum"),
            contract_count=("vt_symbol", "nunique"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            net_pnl=("net_pnl", "sum"),
        )
        .sort_values(["start_month", "arm", "date", "c3_margin_exact"], ascending=[True, True, True, False])
    )
    return frame, product


def _run_one(task: tuple[str, str]) -> dict[str, pd.DataFrame]:
    arm, start_text = task
    state = _ensure_worker_state()
    metadata = state["metadata"]
    start = pd.Timestamp(start_text).normalize()
    original_start = s827.START
    original_end = s827.END
    try:
        s827.START = start
        s827.END = DATA_END
        profile = _profile_for_arm(metadata, arm, start)
        combined, frames = s827._run_profile(profile, metadata)
        summary, curve = s827._metric(profile, combined)
        for frame in [summary, curve]:
            frame["arm"] = arm
            frame["requested_start_month"] = start_text
            frame["start_month"] = start_text
            frame["start_year"] = int(start.year)
            frame["analysis_start"] = start.strftime("%Y-%m-%d")
            frame["analysis_end"] = DATA_END.strftime("%Y-%m-%d")

        positions = frames.get("positions", pd.DataFrame()).copy()
        trades = frames.get("trades", pd.DataFrame()).copy()
        trade_events = frames.get("trade_events", pd.DataFrame()).copy()
        intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
        for frame in [positions, trades, trade_events, intraday_events]:
            if frame.empty:
                continue
            frame["arm"] = arm
            frame["requested_start_month"] = start_text
            frame["start_month"] = start_text
            frame["start_year"] = int(start.year)
        contract_margin, product_margin = _contract_margin(positions, metadata)
        return {
            "summary": summary,
            "curves": curve,
            "positions": positions,
            "trades": trades,
            "trade_events": trade_events,
            "intraday_events": intraday_events,
            "contract_margin": contract_margin,
            "product_margin": product_margin,
        }
    finally:
        s827.START = original_start
        s827.END = original_end


def _concat(results: list[dict[str, pd.DataFrame]], key: str) -> pd.DataFrame:
    frames = [item.get(key, pd.DataFrame()) for item in results if not item.get(key, pd.DataFrame()).empty]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _daily_wide(curves: pd.DataFrame) -> pd.DataFrame:
    data = curves.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    columns = [
        "account_equity",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "net_pnl",
        "trade_count",
        "total_slippage",
    ]
    base = data[data["arm"].eq(BASE_ARM)][["start_month", "date", *columns]].copy()
    cap = data[data["arm"].eq(CAP_ARM)][["start_month", "date", *columns]].copy()
    merged = base.merge(cap, on=["start_month", "date"], suffixes=("_A", "_C4"), how="outer")
    for column in columns:
        merged[f"{column}_delta_C4_minus_A"] = (
            pd.to_numeric(merged.get(f"{column}_C4"), errors="coerce").fillna(0.0)
            - pd.to_numeric(merged.get(f"{column}_A"), errors="coerce").fillna(0.0)
        )
    return merged.sort_values(["start_month", "date"]).reset_index(drop=True)


def _stress_tables(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    wide = _daily_wide(curves)
    for column in ["broker10_margin_to_equity_pct_C4", "drawdown_pct_C4"]:
        wide[column] = pd.to_numeric(wide[column], errors="coerce")
    stress = wide[
        wide["broker10_margin_to_equity_pct_C4"].gt(BROKER100)
        | wide["drawdown_pct_C4"].le(DD50)
    ].copy()
    stress["stress_reason"] = np.select(
        [
            stress["broker10_margin_to_equity_pct_C4"].gt(BROKER100) & stress["drawdown_pct_C4"].le(DD50),
            stress["broker10_margin_to_equity_pct_C4"].gt(BROKER100),
            stress["drawdown_pct_C4"].le(DD50),
        ],
        ["broker100_and_dd50", "broker100", "dd50"],
        default="other",
    )

    anchors: list[dict[str, Any]] = []
    for start_month, group in wide.groupby("start_month", sort=True):
        c4 = group.copy()
        if c4.empty:
            continue
        max_broker = c4.loc[c4["broker10_margin_to_equity_pct_C4"].idxmax()]
        trough = c4.loc[c4["drawdown_pct_C4"].idxmin()]
        first_broker = c4[c4["broker10_margin_to_equity_pct_C4"].gt(BROKER100)].head(1)
        first_dd50 = c4[c4["drawdown_pct_C4"].le(DD50)].head(1)
        for label, row in [
            ("max_broker10", max_broker),
            ("max_drawdown", trough),
        ]:
            item = row.to_dict()
            item["anchor_type"] = label
            anchors.append(item)
        if not first_broker.empty:
            item = first_broker.iloc[0].to_dict()
            item["anchor_type"] = "first_broker100"
            anchors.append(item)
        if not first_dd50.empty:
            item = first_dd50.iloc[0].to_dict()
            item["anchor_type"] = "first_dd50"
            anchors.append(item)
    anchor_df = pd.DataFrame(anchors).sort_values(["start_month", "date", "anchor_type"]).reset_index(drop=True)
    return stress, anchor_df


def _top_margin_products(product_margin: pd.DataFrame, anchors: pd.DataFrame) -> pd.DataFrame:
    if product_margin.empty or anchors.empty:
        return pd.DataFrame()
    data = product_margin.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    rows: list[pd.DataFrame] = []
    for anchor in anchors.to_dict("records"):
        start_month = str(anchor["start_month"])
        date = pd.Timestamp(anchor["date"]).normalize()
        c4 = data[data["start_month"].astype(str).eq(start_month) & data["arm"].eq(CAP_ARM) & data["date"].eq(date)].copy()
        if c4.empty:
            continue
        total = c4["c3_margin_exact"].sum()
        c4["anchor_type"] = anchor["anchor_type"]
        c4["anchor_broker10_pct"] = anchor.get("broker10_margin_to_equity_pct_C4", np.nan)
        c4["anchor_drawdown_pct"] = anchor.get("drawdown_pct_C4", np.nan)
        c4["margin_share_pct"] = np.where(total > 0, c4["c3_margin_exact"] / total * 100.0, 0.0)
        a = data[data["start_month"].astype(str).eq(start_month) & data["arm"].eq(BASE_ARM) & data["date"].eq(date)].copy()
        keys = ["start_month", "date", "product_vt_symbol", "position_direction"]
        a_small = a[keys + ["c3_margin_exact", "abs_end_pos", "contract_count"]].rename(
            columns={
                "c3_margin_exact": "A_c3_margin_exact",
                "abs_end_pos": "A_abs_end_pos",
                "contract_count": "A_contract_count",
            }
        )
        c4 = c4.merge(a_small, on=keys, how="left")
        c4["A_c3_margin_exact"] = pd.to_numeric(c4["A_c3_margin_exact"], errors="coerce").fillna(0.0)
        c4["margin_delta_C4_minus_A"] = c4["c3_margin_exact"] - c4["A_c3_margin_exact"]
        rows.append(c4.sort_values("c3_margin_exact", ascending=False).head(8))
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _cap_event_summary(trade_events: pd.DataFrame, anchors: pd.DataFrame) -> pd.DataFrame:
    if trade_events.empty:
        return pd.DataFrame()
    events = trade_events.copy()
    if "reason" not in events.columns:
        return pd.DataFrame()
    events = events[events["arm"].eq(CAP_ARM) & events["reason"].astype(str).str.startswith("broker10_margin_cap")].copy()
    if events.empty:
        return pd.DataFrame()
    events["datetime"] = _naive_date_series(events["datetime"])
    anchors_min = (
        anchors.groupby("start_month", as_index=False)
        .agg(
            first_stress_date=("date", "min"),
            max_broker10_pct=("broker10_margin_to_equity_pct_C4", "max"),
            min_drawdown_pct=("drawdown_pct_C4", "min"),
        )
    )
    rows: list[dict[str, Any]] = []
    for start_month, group in events.groupby("start_month", sort=True):
        anchor = anchors_min[anchors_min["start_month"].astype(str).eq(str(start_month))]
        first_stress = pd.Timestamp(anchor.iloc[0]["first_stress_date"]).normalize() if not anchor.empty else pd.NaT
        reduced = pd.to_numeric(group.get("reduced_volume", 0), errors="coerce").fillna(0.0)
        before = group[group["datetime"].le(first_stress)] if pd.notna(first_stress) else group.iloc[0:0]
        rows.append(
            {
                "start_month": start_month,
                "cap_events": int(len(group)),
                "cap_reduced_volume": float(reduced.sum()),
                "first_stress_date": first_stress.strftime("%Y-%m-%d") if pd.notna(first_stress) else "",
                "cap_events_before_first_stress": int(len(before)),
                "cap_reduced_volume_before_first_stress": float(
                    pd.to_numeric(before.get("reduced_volume", 0), errors="coerce").fillna(0.0).sum()
                ),
                "max_projected_before": float(
                    pd.to_numeric(group.get("projected_broker10_margin_to_equity_before", np.nan), errors="coerce").max()
                ),
                "max_projected_after": float(
                    pd.to_numeric(group.get("projected_broker10_margin_to_equity_after", np.nan), errors="coerce").max()
                ),
            }
        )
    return pd.DataFrame(rows)


def _plot_path_chart(curves: pd.DataFrame, stress_starts: list[str]) -> None:
    data = curves[curves["start_month"].astype(str).isin(stress_starts)].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    fig, axes = plt.subplots(len(stress_starts), 3, figsize=(21, 4.3 * len(stress_starts)), constrained_layout=True)
    axes_arr = np.atleast_2d(axes)
    colors = {BASE_ARM: "#2563eb", CAP_ARM: "#16a34a"}
    labels = {BASE_ARM: "A", CAP_ARM: "C4"}
    for row_idx, start_month in enumerate(stress_starts):
        frame = data[data["start_month"].astype(str).eq(start_month)].copy()
        for arm, group in frame.groupby("arm"):
            group = group.sort_values("date")
            axes_arr[row_idx, 0].plot(group["date"], group["account_equity"], color=colors.get(arm), label=labels.get(arm, arm), linewidth=1.0)
            axes_arr[row_idx, 1].plot(group["date"], group["drawdown_pct"], color=colors.get(arm), label=labels.get(arm, arm), linewidth=1.0)
            axes_arr[row_idx, 2].plot(
                group["date"],
                group["broker10_margin_to_equity_pct"],
                color=colors.get(arm),
                label=labels.get(arm, arm),
                linewidth=1.0,
            )
        axes_arr[row_idx, 0].set_title(f"{start_month} equity")
        axes_arr[row_idx, 1].set_title(f"{start_month} drawdown")
        axes_arr[row_idx, 2].set_title(f"{start_month} broker10 margin/equity")
        axes_arr[row_idx, 1].axhline(DD50, color="#dc2626", linestyle="--", linewidth=0.8)
        axes_arr[row_idx, 2].axhline(BROKER100, color="#dc2626", linestyle="--", linewidth=0.8)
        for ax in axes_arr[row_idx, :]:
            ax.grid(True, alpha=0.22)
            ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_margin_chart(top_margin: pd.DataFrame) -> None:
    if top_margin.empty:
        return
    anchors = top_margin[top_margin["anchor_type"].isin(["max_broker10", "first_broker100"])].copy()
    if anchors.empty:
        anchors = top_margin.copy()
    groups = list(anchors.groupby(["start_month", "anchor_type"], sort=True))
    fig, axes = plt.subplots(len(groups), 1, figsize=(15, max(4, 3.2 * len(groups))), constrained_layout=True)
    axes_list = list(np.atleast_1d(axes))
    for ax, ((start_month, anchor_type), group) in zip(axes_list, groups, strict=False):
        group = group.sort_values("c3_margin_exact", ascending=True).tail(8)
        labels = group["product_vt_symbol"].astype(str) + " " + group["position_direction"].astype(str)
        y = np.arange(len(group))
        ax.barh(y - 0.16, group["A_c3_margin_exact"], height=0.32, color="#2563eb", label="A")
        ax.barh(y + 0.16, group["c3_margin_exact"], height=0.32, color="#16a34a", label="C4")
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        date = pd.Timestamp(group["date"].iloc[0]).strftime("%Y-%m-%d")
        ax.set_title(f"{start_month} {anchor_type} {date} top margin products")
        ax.grid(True, axis="x", alpha=0.22)
        ax.legend(loc="best")
    fig.savefig(MARGIN_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_stress_kline_atlas(contract_margin: pd.DataFrame, anchors: pd.DataFrame) -> None:
    if contract_margin.empty or anchors.empty:
        return
    rows: list[dict[str, Any]] = []
    data = contract_margin.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    for anchor in anchors[anchors["anchor_type"].eq("max_broker10")].to_dict("records"):
        start_month = str(anchor["start_month"])
        date = pd.Timestamp(anchor["date"]).normalize()
        focus = data[
            data["start_month"].astype(str).eq(start_month)
            & data["arm"].eq(CAP_ARM)
            & data["date"].eq(date)
        ].copy()
        for item in focus.sort_values("c3_margin_exact", ascending=False).head(2).to_dict("records"):
            item["stress_date"] = date
            item["anchor_broker10_pct"] = anchor.get("broker10_margin_to_equity_pct_C4", np.nan)
            item["anchor_drawdown_pct"] = anchor.get("drawdown_pct_C4", np.nan)
            rows.append(item)
    if not rows:
        return
    selected = pd.DataFrame(rows)
    fig, axes = plt.subplots(len(selected), 1, figsize=(18, max(4, 3.2 * len(selected))), constrained_layout=True)
    axes_list = list(np.atleast_1d(axes))
    for ax, row in zip(axes_list, selected.to_dict("records"), strict=False):
        vt_symbol = row["vt_symbol"]
        stress_date = pd.Timestamp(row["stress_date"]).normalize()
        bars, source = s815._read_plot_bars(vt_symbol)
        if bars.empty:
            ax.axis("off")
            ax.text(0.5, 0.5, f"missing daily bars {vt_symbol} {stress_date:%Y-%m-%d}", ha="center", va="center")
            continue
        idx = s752._event_index(bars, stress_date)
        start = max(0, idx - 50)
        end = min(len(bars), idx + 51)
        window = bars.iloc[start:end].copy().reset_index(drop=True)
        local_idx = idx - start
        s752._plot_candles(ax, window)
        for ma, color in [(5, "#f59e0b"), (10, "#2563eb"), (20, "#7c3aed"), (40, "#111827")]:
            ax.plot(window["close"].rolling(ma).mean().to_numpy(), color=color, linewidth=0.85, alpha=0.82)
        ax.axvline(local_idx, color="#dc2626", linestyle="--", linewidth=1.0)
        ticks = np.linspace(0, len(window) - 1, num=min(8, len(window)), dtype=int)
        ax.set_xticks(ticks)
        ax.set_xticklabels([pd.Timestamp(window.loc[pos, "date"]).strftime("%Y-%m-%d") for pos in ticks], rotation=28, ha="right", fontsize=7)
        ax.grid(True, alpha=0.18)
        ax.set_title(
            (
                f"{row['start_month']} {vt_symbol} {row['position_direction']} stress={stress_date:%Y-%m-%d} "
                f"pos={_safe_float(row.get('end_pos')):.0f} margin={_safe_float(row.get('c3_margin_exact')):,.0f} "
                f"broker10={_safe_float(row.get('anchor_broker10_pct')):.2f}% source={source}"
            ),
            fontsize=8.5,
            loc="left",
        )
    fig.suptitle("Stage832 C4 max-broker stress daily K atlas", fontsize=13)
    fig.savefig(KLINE_ATLAS_PATH, dpi=150)
    plt.close(fig)


def _plot_intraday_event_atlas(intraday_events: pd.DataFrame, anchors: pd.DataFrame) -> None:
    if intraday_events.empty or anchors.empty:
        return
    events = intraday_events[intraday_events["arm"].eq(CAP_ARM)].copy()
    events["datetime"] = _naive_date_series(events["datetime"])
    anchors_min = anchors[anchors["anchor_type"].eq("max_broker10")][["start_month", "date"]].copy()
    anchors_min["date"] = pd.to_datetime(anchors_min["date"], errors="coerce").dt.normalize()
    selected_rows: list[pd.DataFrame] = []
    for anchor in anchors_min.to_dict("records"):
        start_month = str(anchor["start_month"])
        anchor_date = pd.Timestamp(anchor["date"]).normalize()
        part = events[
            events["start_month"].astype(str).eq(start_month)
            & events["datetime"].between(anchor_date - pd.Timedelta(days=45), anchor_date)
        ].copy()
        if part.empty:
            continue
        selected_rows.append(part.sort_values("volume", ascending=False).head(2))
    if not selected_rows:
        return
    selected = pd.concat(selected_rows, ignore_index=True, sort=False).drop_duplicates(["start_month", "trade_id"]).head(10)
    vt_symbols = set(selected["vt_symbol"].dropna().astype(str))
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    fig, axes = plt.subplots(len(selected), 1, figsize=(18, max(4, 2.9 * len(selected))), constrained_layout=True)
    axes_list = list(np.atleast_1d(axes))
    for ax, row in zip(axes_list, selected.to_dict("records"), strict=False):
        vt_symbol = str(row["vt_symbol"])
        event_date = pd.Timestamp(row["datetime"]).normalize()
        bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        day = bars[bars["bar_date"].eq(event_date)].copy().reset_index(drop=True) if not bars.empty else pd.DataFrame()
        if day.empty:
            ax.axis("off")
            ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {event_date:%Y-%m-%d}", ha="center", va="center")
            continue
        window = day.head(260).copy().reset_index(drop=True)
        s825._plot_candles(ax, window)
        ax.plot(np.arange(len(window)), window["close"].rolling(5).mean(), color="#f59e0b", linewidth=0.75)
        ax.plot(np.arange(len(window)), window["close"].rolling(20).mean(), color="#2563eb", linewidth=0.75)
        for value, color, label in [
            (_safe_float(row.get("entry_price")), "#1d4ed8", "entry"),
            (_safe_float(row.get("stop_price")), "#dc2626", "stop"),
            (_safe_float(row.get("confirm_price")), "#16a34a", "confirm"),
        ]:
            if np.isfinite(value):
                ax.axhline(value, color=color, linewidth=0.9, alpha=0.85)
        hit_time = pd.Timestamp(row.get("hit_time")) if row.get("hit_time") else pd.NaT
        if pd.notna(hit_time):
            times = pd.to_datetime(window["bar_datetime"], errors="coerce")
            idx = int((times - hit_time).abs().idxmin())
            ax.axvline(idx, color="#dc2626", linestyle="--", linewidth=0.9)
        ticks = np.linspace(0, len(window) - 1, num=min(8, len(window)), dtype=int)
        ax.set_xticks(ticks)
        ax.set_xticklabels([pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
        ax.grid(True, alpha=0.18)
        ax.set_title(
            (
                f"{row['start_month']} {vt_symbol} {row.get('direction')} {event_date:%Y-%m-%d} "
                f"volume={_safe_float(row.get('volume')):.0f} note={row.get('note', '')}"
            ),
            fontsize=8.5,
            loc="left",
        )
    fig.suptitle("Stage832 C4 intraday stop events before max-broker stress", fontsize=13)
    fig.savefig(INTRADAY_ATLAS_PATH, dpi=150)
    plt.close(fig)


def _write_report(
    stress_starts: list[str],
    stress_days: pd.DataFrame,
    anchors: pd.DataFrame,
    top_margin: pd.DataFrame,
    cap_summary: pd.DataFrame,
) -> None:
    anchor_display = anchors[
        [
            "start_month",
            "anchor_type",
            "date",
            "account_equity_A",
            "account_equity_C4",
            "drawdown_pct_A",
            "drawdown_pct_C4",
            "broker10_margin_to_equity_pct_A",
            "broker10_margin_to_equity_pct_C4",
            "net_pnl_delta_C4_minus_A",
        ]
    ].copy() if not anchors.empty else pd.DataFrame()
    top_display = top_margin[
        [
            "start_month",
            "date",
            "anchor_type",
            "product_vt_symbol",
            "position_direction",
            "c3_margin_exact",
            "A_c3_margin_exact",
            "margin_delta_C4_minus_A",
            "margin_share_pct",
            "abs_end_pos",
            "A_abs_end_pos",
            "holding_pnl",
            "net_pnl",
        ]
    ].copy() if not top_margin.empty else pd.DataFrame()
    stress_summary = (
        stress_days.groupby(["start_month", "stress_reason"], as_index=False)
        .agg(
            days=("date", "count"),
            max_broker10_C4=("broker10_margin_to_equity_pct_C4", "max"),
            min_drawdown_C4=("drawdown_pct_C4", "min"),
            min_equity_gap_C4_minus_A=("account_equity_delta_C4_minus_A", "min"),
        )
        .sort_values(["start_month", "stress_reason"])
        if not stress_days.empty
        else pd.DataFrame()
    )
    lines = [
        "# Stage832 Stage831 C4 broker100/DD50压力归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读归因；不改策略、不调参数、不连接 CTP、不调用下单。",
        f"- 重跑起点：`{', '.join(stress_starts)}`。",
        "",
        "## 外部调研与判断",
        "",
        "- CFTC/期货基础资料说明期货账户会逐日盯市，保证金不足会触发补充保证金或强平；因此入场瞬间的保证金闸门不等同于持仓路径安全。",
        "- CTA/trend-following 仓位管理资料强调 portfolio risk、volatility、margin 和 position sizing 要共同约束；Stage832 按此框架把权益分母、保证金分子、产品集中度分开归因。",
        "",
        "## Stress Day Summary",
        "",
        _md_table(stress_summary, max_rows=30),
        "",
        "## Anchor Days",
        "",
        _md_table(anchor_display, max_rows=30),
        "",
        "## Top Margin Products On Anchor Days",
        "",
        _md_table(top_display, max_rows=40),
        "",
        "## Cap Events Before Stress",
        "",
        _md_table(cap_summary, max_rows=20),
        "",
        "## Charts",
        "",
        f"- stress path chart：`{PATH_CHART_PATH}`",
        f"- anchor margin chart：`{MARGIN_CHART_PATH}`",
        f"- stress K atlas：`{KLINE_ATLAS_PATH}`",
        f"- intraday event atlas：`{INTRADAY_ATLAS_PATH}`",
        "",
        "## Judgment",
        "",
        "- Stage832 是归因，不是晋级验证。核心检验是 C4 的 broker100/DD50 来自入口闸门失效、持仓后盯市路径、还是产品集中暴露。",
        "- 若压力来自少数产品或年份，不得直接做黑名单；只能作为 full-path survival 规则设计前的证据。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stress_starts = _stress_start_months()
    cached_paths = [
        SUMMARY_PATH,
        CURVES_PATH,
        CONTRACT_MARGIN_PATH,
        PRODUCT_MARGIN_PATH,
        TRADE_EVENTS_PATH,
        INTRADAY_EVENTS_PATH,
        STRESS_DAYS_PATH,
        STRESS_ANCHORS_PATH,
        TOP_MARGIN_PRODUCTS_PATH,
        CAP_EVENT_SUMMARY_PATH,
    ]
    use_cache = all(path.exists() for path in cached_paths) and os.environ.get("STAGE832_FORCE_RERUN", "0") != "1"
    if use_cache:
        print("[stage832] using cached replay outputs; set STAGE832_FORCE_RERUN=1 to rerun engines", flush=True)
        summary = pd.read_csv(SUMMARY_PATH, encoding="utf-8-sig")
        curves = pd.read_csv(CURVES_PATH, encoding="utf-8-sig")
        contract_margin = pd.read_csv(CONTRACT_MARGIN_PATH, encoding="utf-8-sig")
        product_margin = pd.read_csv(PRODUCT_MARGIN_PATH, encoding="utf-8-sig")
        trade_events = pd.read_csv(TRADE_EVENTS_PATH, encoding="utf-8-sig")
        intraday_events = pd.read_csv(INTRADAY_EVENTS_PATH, encoding="utf-8-sig")
        stress_days = pd.read_csv(STRESS_DAYS_PATH, encoding="utf-8-sig")
        anchors = pd.read_csv(STRESS_ANCHORS_PATH, encoding="utf-8-sig")
        top_margin = pd.read_csv(TOP_MARGIN_PRODUCTS_PATH, encoding="utf-8-sig")
        cap_summary = pd.read_csv(CAP_EVENT_SUMMARY_PATH, encoding="utf-8-sig")
    else:
        tasks = [(arm, start) for start in stress_starts for arm in (BASE_ARM, CAP_ARM)]
        results: list[dict[str, pd.DataFrame]] = []

        print(f"[stage832] launching {len(tasks)} stress forensics runs workers={MAX_WORKERS}: {stress_starts}", flush=True)
        if MAX_WORKERS == 1:
            for index, task in enumerate(tasks, start=1):
                print(f"[stage832] running {index}/{len(tasks)} {task[1]} {task[0]}", flush=True)
                results.append(_run_one(task))
        else:
            with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_map = {executor.submit(_run_one, task): task for task in tasks}
                for index, future in enumerate(as_completed(future_map), start=1):
                    task = future_map[future]
                    results.append(future.result())
                    print(f"[stage832] completed {index}/{len(tasks)} {task[1]} {task[0]}", flush=True)

        summary = _concat(results, "summary")
        curves = _concat(results, "curves")
        positions = _concat(results, "positions")
        contract_margin = _concat(results, "contract_margin")
        product_margin = _concat(results, "product_margin")
        trade_events = _concat(results, "trade_events")
        intraday_events = _concat(results, "intraday_events")

        stress_days, anchors = _stress_tables(curves)
        top_margin = _top_margin_products(product_margin, anchors)
        cap_summary = _cap_event_summary(trade_events, anchors)

        summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
        curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
        positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
        contract_margin.to_csv(CONTRACT_MARGIN_PATH, index=False, encoding="utf-8-sig")
        product_margin.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
        trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
        intraday_events.to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
        stress_days.to_csv(STRESS_DAYS_PATH, index=False, encoding="utf-8-sig")
        anchors.to_csv(STRESS_ANCHORS_PATH, index=False, encoding="utf-8-sig")
        top_margin.to_csv(TOP_MARGIN_PRODUCTS_PATH, index=False, encoding="utf-8-sig")
        cap_summary.to_csv(CAP_EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    _plot_path_chart(curves, stress_starts)
    _plot_margin_chart(top_margin)
    _plot_stress_kline_atlas(contract_margin, anchors)
    _plot_intraday_event_atlas(intraday_events, anchors)
    _write_report(stress_starts, stress_days, anchors, top_margin, cap_summary)

    stress_summary = (
        stress_days.groupby("start_month", as_index=False)
        .agg(
            stress_days=("date", "count"),
            broker100_days=("stress_reason", lambda s: int(s.astype(str).str.contains("broker100").sum())),
            dd50_days=("stress_reason", lambda s: int(s.astype(str).str.contains("dd50").sum())),
            max_broker10_C4=("broker10_margin_to_equity_pct_C4", "max"),
            min_drawdown_C4=("drawdown_pct_C4", "min"),
        )
        if not stress_days.empty
        else pd.DataFrame()
    )
    top_products_summary = (
        top_margin.groupby(["product_vt_symbol", "position_direction"], as_index=False)
        .agg(
            rows=("date", "count"),
            margin_sum=("c3_margin_exact", "sum"),
            margin_delta_sum=("margin_delta_C4_minus_A", "sum"),
            max_margin_share_pct=("margin_share_pct", "max"),
        )
        .sort_values("margin_sum", ascending=False)
        .head(15)
        if not top_margin.empty
        else pd.DataFrame()
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "stress_starts": stress_starts,
        "stress_summary": stress_summary.to_dict("records"),
        "top_products_summary": top_products_summary.to_dict("records"),
        "cap_event_summary": cap_summary.to_dict("records"),
        "decision": "read_only_forensics_no_promotion",
        "judgment": (
            "C4 stress attribution checks whether Stage830 entry margin cap failed because margin/equity risk is "
            "generated after entry by mark-to-market, equity denominator collapse, and product concentration."
        ),
        "overfit_reflection": (
            "This is attribution only. It selects starts from the already failed Stage831 broker100/DD50 set and does not "
            "add any trading rule or tune thresholds."
        ),
        "continue_value": (
            "Continue only if the stress evidence suggests a structural full-path survival rule. Do not patch single products, "
            "years, or lower the entry cap by small increments."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "positions": str(POSITIONS_PATH),
            "contract_margin": str(CONTRACT_MARGIN_PATH),
            "product_margin": str(PRODUCT_MARGIN_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "stress_days": str(STRESS_DAYS_PATH),
            "stress_anchors": str(STRESS_ANCHORS_PATH),
            "top_margin_products": str(TOP_MARGIN_PRODUCTS_PATH),
            "cap_event_summary": str(CAP_EVENT_SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "path_chart": str(PATH_CHART_PATH),
            "margin_chart": str(MARGIN_CHART_PATH),
            "kline_atlas": str(KLINE_ATLAS_PATH),
            "intraday_atlas": str(INTRADAY_ATLAS_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print("stress_summary", flush=True)
    print(stress_summary.to_string(index=False), flush=True)
    print("top_products_summary", flush=True)
    print(top_products_summary.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
