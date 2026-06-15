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

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage864_stage863_broker10_peak_forensics as s864
import analyze_qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine as s883
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage884"
MODEL_TAG = "stage884_stage883_broker10_path_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage884_stage883_broker10_path_forensics"

STAGE883_PREFIX = s883.OUTPUT_PREFIX
STAGE883_TAG = s883.MODEL_TAG

C4_ARM = s883.C4_ARM
C9_ARM = s883.C9_ARM
C17_ARM = s883.C17_ARM
ARMS = [C4_ARM, C9_ARM, C17_ARM]

BROKER_MARGIN_MULTIPLIER = s864.BROKER_MARGIN_MULTIPLIER
TOP_PEAK_DATES_PER_ARM = 10
MAX_ATLAS_ROWS = 12
PER_PAGE = 3

CURVE_IN = OUTPUT_DIR / f"{STAGE883_PREFIX}_curve_{STAGE883_TAG}.csv"
CLOSED_LOTS_IN = OUTPUT_DIR / f"{STAGE883_PREFIX}_closed_lots_{STAGE883_TAG}.csv"
ENTRY_RISK_IN = OUTPUT_DIR / f"{STAGE883_PREFIX}_entry_risk_{STAGE883_TAG}.csv"
DECISION_IN = OUTPUT_DIR / f"{STAGE883_PREFIX}_decision_{STAGE883_TAG}.json"

PEAK_DATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_peak_dates_{MODEL_TAG}.csv"
ACTIVE_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_active_lots_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_attribution_{MODEL_TAG}.csv"
PAIR_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pair_delta_{MODEL_TAG}.csv"
DECOMPOSITION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_denominator_decomposition_{MODEL_TAG}.csv"
CUMULATIVE_PNL_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cumulative_pnl_delta_{MODEL_TAG}.csv"
ENTRY_CONTEXT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_context_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


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


def _prepare_curve(curve: pd.DataFrame) -> pd.DataFrame:
    data = curve[curve["arm"].isin(ARMS)].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed").dt.normalize()
    for column in [
        "account_equity",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "net_pnl",
        "trade_count",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["estimated_broker10_margin_amount"] = (
        data["account_equity"] * data["broker10_margin_to_equity_pct"] / 100.0
    )
    return data.dropna(subset=["date", "arm"]).sort_values(["arm", "date"]).reset_index(drop=True)


def _curve_snapshot(curve: pd.DataFrame, arm: str, focus_date: pd.Timestamp) -> pd.Series:
    rows = curve[curve["arm"].eq(arm) & curve["date"].eq(focus_date)]
    if rows.empty:
        return pd.Series(dtype=object)
    return rows.iloc[0]


def _peak_dates(curve: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for arm, group in curve.groupby("arm", sort=False):
        part = group.sort_values("broker10_margin_to_equity_pct", ascending=False).head(TOP_PEAK_DATES_PER_ARM).copy()
        part["peak_rank"] = range(1, len(part) + 1)
        part["peak_owner_arm"] = arm
        rows.append(part)
    if not rows:
        return pd.DataFrame()
    peaks = pd.concat(rows, ignore_index=True, sort=False)
    output: list[dict[str, Any]] = []
    focus_dates = sorted(pd.to_datetime(peaks["date"], errors="coerce").dropna().unique())
    for focus_date in focus_dates:
        owner_rows = peaks[peaks["date"].eq(focus_date)]
        owner_arms = ",".join(sorted(owner_rows["peak_owner_arm"].astype(str).unique()))
        row: dict[str, Any] = {
            "focus_date": pd.Timestamp(focus_date).date().isoformat(),
            "peak_owner_arms": owner_arms,
        }
        for arm in ARMS:
            snap = _curve_snapshot(curve, arm, pd.Timestamp(focus_date))
            row[f"{arm}_equity"] = _safe_float(snap.get("account_equity"))
            row[f"{arm}_drawdown_pct"] = _safe_float(snap.get("drawdown_pct"))
            row[f"{arm}_broker10_pct"] = _safe_float(snap.get("broker10_margin_to_equity_pct"))
            row[f"{arm}_broker10_margin_amount"] = _safe_float(snap.get("estimated_broker10_margin_amount"))
            owner = owner_rows[owner_rows["peak_owner_arm"].eq(arm)]
            row[f"{arm}_peak_rank"] = int(owner["peak_rank"].iloc[0]) if not owner.empty else 0
        row["c17_minus_c9_broker10_pct"] = row[f"{C17_ARM}_broker10_pct"] - row[f"{C9_ARM}_broker10_pct"]
        row["c17_minus_c4_broker10_pct"] = row[f"{C17_ARM}_broker10_pct"] - row[f"{C4_ARM}_broker10_pct"]
        output.append(row)
    return pd.DataFrame(output).sort_values(
        [f"{C17_ARM}_peak_rank", "c17_minus_c9_broker10_pct"],
        ascending=[False, False],
    ).reset_index(drop=True)


def _prepare_closed_lots(closed_lots: pd.DataFrame) -> pd.DataFrame:
    data = closed_lots[closed_lots["arm"].isin(ARMS)].copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    for column in [
        "volume",
        "size",
        "entry_price",
        "exit_price",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "selected_volume",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    if "product" not in data.columns:
        data["product"] = data["vt_symbol"].astype(str).str.extract(r"^([A-Za-z]+)")[0]
    return data.dropna(subset=["entry_date", "exit_date", "arm", "vt_symbol"]).reset_index(drop=True)


def _price_on_date(
    minute_by_symbol: dict[str, pd.DataFrame],
    vt_symbol: str,
    focus_date: pd.Timestamp,
    fallback_price: float,
) -> tuple[float, str, int, float, float]:
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    if not bars.empty:
        day = bars[bars["bar_date"].eq(focus_date)].copy().sort_values("bar_datetime")
        if not day.empty:
            return (
                float(day["close"].iloc[-1]),
                "minute_last_close",
                int(len(day)),
                float(day["high"].max()),
                float(day["low"].min()),
            )
    return float(fallback_price), "entry_price_fallback", 0, np.nan, np.nan


def _active_lots_for_focus(
    closed_lots: pd.DataFrame,
    curve: pd.DataFrame,
    focus_dates: list[pd.Timestamp],
    minute_by_symbol: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    margin_ratios = metadata.get("margin_ratios", {})
    sizes = metadata.get("sizes", {})
    for focus_date in focus_dates:
        for arm in ARMS:
            snapshot = _curve_snapshot(curve, arm, focus_date)
            account_equity = _safe_float(snapshot.get("account_equity"))
            curve_broker10_pct = _safe_float(snapshot.get("broker10_margin_to_equity_pct"))
            active = closed_lots[
                closed_lots["arm"].eq(arm)
                & closed_lots["entry_date"].le(focus_date)
                & closed_lots["exit_date"].ge(focus_date)
            ].copy()
            for _, lot in active.iterrows():
                vt_symbol = str(lot["vt_symbol"])
                size = _safe_float(lot.get("size"), _safe_float(sizes.get(vt_symbol), 0.0))
                margin_ratio = _safe_float(margin_ratios.get(vt_symbol), 0.0)
                volume = _safe_float(lot.get("volume"), 0.0)
                fallback = _safe_float(lot.get("entry_price"), 0.0)
                price, price_source, minute_bars, day_high, day_low = _price_on_date(
                    minute_by_symbol,
                    vt_symbol,
                    focus_date,
                    fallback,
                )
                exchange_margin = price * size * volume * margin_ratio if price > 0 and size > 0 else np.nan
                broker10_margin = exchange_margin * BROKER_MARGIN_MULTIPLIER if np.isfinite(exchange_margin) else np.nan
                broker10_pct = broker10_margin / account_equity * 100.0 if account_equity > 0 else np.nan
                rows.append(
                    {
                        "focus_date": focus_date.date().isoformat(),
                        "arm": arm,
                        "account_equity": account_equity,
                        "curve_broker10_margin_to_equity_pct": curve_broker10_pct,
                        "lot_id": lot.get("lot_id"),
                        "vt_symbol": vt_symbol,
                        "product_vt_symbol": str(lot.get("product", "")),
                        "direction": str(lot.get("direction", "")),
                        "entry_date": pd.Timestamp(lot["entry_date"]).date().isoformat(),
                        "exit_date": pd.Timestamp(lot["exit_date"]).date().isoformat(),
                        "volume": volume,
                        "size": size,
                        "margin_ratio": margin_ratio,
                        "focus_price": price,
                        "focus_price_source": price_source,
                        "focus_day_minute_bars": minute_bars,
                        "focus_day_high": day_high,
                        "focus_day_low": day_low,
                        "entry_price": _safe_float(lot.get("entry_price")),
                        "exit_price": _safe_float(lot.get("exit_price")),
                        "realized_pnl": _safe_float(lot.get("realized_pnl")),
                        "risk_amount": _safe_float(lot.get("risk_amount")),
                        "r_multiple": _safe_float(lot.get("r_multiple")),
                        "signal": str(lot.get("signal", "")),
                        "exit_reason": str(lot.get("exit_reason", "")),
                        "estimated_exchange_margin": exchange_margin,
                        "estimated_broker10_margin": broker10_margin,
                        "estimated_broker10_margin_to_equity_pct": broker10_pct,
                    }
                )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["focus_date", "arm", "estimated_broker10_margin_to_equity_pct"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def _product_direction(active_lots: pd.DataFrame) -> pd.DataFrame:
    if active_lots.empty:
        return pd.DataFrame()
    data = active_lots.copy()
    for column in [
        "volume",
        "estimated_exchange_margin",
        "estimated_broker10_margin",
        "estimated_broker10_margin_to_equity_pct",
        "realized_pnl",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    return (
        data.groupby(["focus_date", "arm", "product_vt_symbol", "direction"], dropna=False)
        .agg(
            active_lots=("lot_id", "count"),
            volume=("volume", "sum"),
            estimated_exchange_margin=("estimated_exchange_margin", "sum"),
            estimated_broker10_margin=("estimated_broker10_margin", "sum"),
            estimated_broker10_margin_to_equity_pct=("estimated_broker10_margin_to_equity_pct", "sum"),
            active_lot_realized_pnl=("realized_pnl", "sum"),
        )
        .reset_index()
        .sort_values(["focus_date", "arm", "estimated_broker10_margin_to_equity_pct"], ascending=[True, True, False])
        .reset_index(drop=True)
    )


def _pair_delta(product_direction: pd.DataFrame) -> pd.DataFrame:
    if product_direction.empty:
        return pd.DataFrame()
    values = [
        "active_lots",
        "volume",
        "estimated_broker10_margin",
        "estimated_broker10_margin_to_equity_pct",
        "active_lot_realized_pnl",
    ]
    wide = product_direction.pivot_table(
        index=["focus_date", "product_vt_symbol", "direction"],
        columns="arm",
        values=values,
        aggfunc="sum",
        fill_value=0.0,
    )
    wide.columns = [f"{metric}__{arm}" for metric, arm in wide.columns]
    wide = wide.reset_index()
    for metric in values:
        for arm in ARMS:
            column = f"{metric}__{arm}"
            if column not in wide.columns:
                wide[column] = 0.0
    wide["c17_minus_c9_broker10_pct"] = (
        wide[f"estimated_broker10_margin_to_equity_pct__{C17_ARM}"]
        - wide[f"estimated_broker10_margin_to_equity_pct__{C9_ARM}"]
    )
    wide["c17_minus_c4_broker10_pct"] = (
        wide[f"estimated_broker10_margin_to_equity_pct__{C17_ARM}"]
        - wide[f"estimated_broker10_margin_to_equity_pct__{C4_ARM}"]
    )
    wide["c17_minus_c9_broker10_margin"] = (
        wide[f"estimated_broker10_margin__{C17_ARM}"] - wide[f"estimated_broker10_margin__{C9_ARM}"]
    )
    wide["c17_minus_c9_volume"] = wide[f"volume__{C17_ARM}"] - wide[f"volume__{C9_ARM}"]
    return wide.sort_values(["focus_date", "c17_minus_c9_broker10_pct"], ascending=[True, False]).reset_index(drop=True)


def _denominator_decomposition(curve: pd.DataFrame, peaks: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    c17_peak_dates = peaks[pd.to_numeric(peaks[f"{C17_ARM}_peak_rank"], errors="coerce").fillna(0).gt(0)].copy()
    for _, item in c17_peak_dates.sort_values(f"{C17_ARM}_peak_rank").iterrows():
        focus_date = pd.Timestamp(item["focus_date"])
        c17 = _curve_snapshot(curve, C17_ARM, focus_date)
        row: dict[str, Any] = {
            "focus_date": focus_date.date().isoformat(),
            "c17_peak_rank": int(item[f"{C17_ARM}_peak_rank"]),
            "c17_broker10_pct": _safe_float(c17.get("broker10_margin_to_equity_pct")),
            "c17_equity": _safe_float(c17.get("account_equity")),
            "c17_broker10_margin": _safe_float(c17.get("estimated_broker10_margin_amount")),
            "c17_drawdown_pct": _safe_float(c17.get("drawdown_pct")),
        }
        for base_arm, prefix in [(C9_ARM, "vs_c9"), (C4_ARM, "vs_c4")]:
            base = _curve_snapshot(curve, base_arm, focus_date)
            base_equity = _safe_float(base.get("account_equity"))
            base_broker10_pct = _safe_float(base.get("broker10_margin_to_equity_pct"))
            base_margin = _safe_float(base.get("estimated_broker10_margin_amount"))
            c17_equity = row["c17_equity"]
            if c17_equity > 0 and np.isfinite(base_margin):
                base_margin_on_c17_equity_pct = base_margin / c17_equity * 100.0
                denominator_effect = base_margin_on_c17_equity_pct - base_broker10_pct
                exposure_effect = row["c17_broker10_pct"] - base_margin_on_c17_equity_pct
            else:
                base_margin_on_c17_equity_pct = np.nan
                denominator_effect = np.nan
                exposure_effect = np.nan
            row[f"{prefix}_base_broker10_pct"] = base_broker10_pct
            row[f"{prefix}_base_equity"] = base_equity
            row[f"{prefix}_base_broker10_margin"] = base_margin
            row[f"{prefix}_broker10_delta_pct"] = row["c17_broker10_pct"] - base_broker10_pct
            row[f"{prefix}_equity_ratio_c17_to_base"] = c17_equity / base_equity if base_equity > 0 else np.nan
            row[f"{prefix}_margin_delta"] = row["c17_broker10_margin"] - base_margin
            row[f"{prefix}_base_margin_on_c17_equity_pct"] = base_margin_on_c17_equity_pct
            row[f"{prefix}_denominator_effect_pct"] = denominator_effect
            row[f"{prefix}_exposure_effect_pct"] = exposure_effect
        denominator = abs(row.get("vs_c9_denominator_effect_pct", 0.0))
        exposure = abs(row.get("vs_c9_exposure_effect_pct", 0.0))
        if denominator >= exposure and row.get("vs_c9_denominator_effect_pct", 0.0) > 0:
            mechanism = "equity_denominator_compression"
        elif row.get("vs_c9_exposure_effect_pct", 0.0) > 0:
            mechanism = "exposure_numerator_expansion"
        else:
            mechanism = "mixed_or_lower_than_c9"
        row["dominant_mechanism_vs_c9"] = mechanism
        rows.append(row)
    return pd.DataFrame(rows).sort_values("c17_peak_rank").reset_index(drop=True)


def _cumulative_pnl_delta(closed_lots: pd.DataFrame, focus_dates: list[pd.Timestamp]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for focus_date in focus_dates:
        subset = closed_lots[closed_lots["exit_date"].le(focus_date)].copy()
        if subset.empty:
            continue
        grouped = (
            subset.groupby(["arm", "product", "direction"], dropna=False)["realized_pnl"]
            .sum()
            .reset_index()
            .pivot_table(index=["product", "direction"], columns="arm", values="realized_pnl", fill_value=0.0)
        )
        for arm in ARMS:
            if arm not in grouped.columns:
                grouped[arm] = 0.0
        grouped = grouped.reset_index()
        grouped["focus_date"] = focus_date.date().isoformat()
        grouped["c17_minus_c9_realized_pnl"] = grouped[C17_ARM] - grouped[C9_ARM]
        grouped["c17_minus_c4_realized_pnl"] = grouped[C17_ARM] - grouped[C4_ARM]
        rows.extend(grouped.to_dict("records"))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["focus_date", "c17_minus_c9_realized_pnl"]).reset_index(drop=True)


def _entry_context(entry_risk: pd.DataFrame, focus_dates: list[pd.Timestamp]) -> pd.DataFrame:
    if entry_risk.empty:
        return pd.DataFrame()
    data = entry_risk[entry_risk["profile"].isin([C9_ARM, C17_ARM])].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    for column in [
        "selected_volume",
        "estimated_equity",
        "total_margin_in_use_before",
        "actual_margin_amount",
        "projected_total_margin_after",
    ]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data = data[pd.to_numeric(data["selected_volume"], errors="coerce").fillna(0).gt(0)].copy()
    if data.empty:
        return pd.DataFrame()
    rows: list[pd.DataFrame] = []
    for focus_date in focus_dates:
        start = focus_date - pd.Timedelta(days=10)
        part = data[data["date"].between(start, focus_date)].copy()
        if part.empty:
            continue
        part["focus_date"] = focus_date.date().isoformat()
        part["days_before_focus"] = (focus_date - part["date"]).dt.days
        part["before_broker10_pct"] = (
            part["total_margin_in_use_before"] * BROKER_MARGIN_MULTIPLIER / part["estimated_equity"] * 100.0
        )
        part["add_broker10_pct"] = part["actual_margin_amount"] * BROKER_MARGIN_MULTIPLIER / part["estimated_equity"] * 100.0
        part["projected_broker10_pct"] = (
            part["projected_total_margin_after"] * BROKER_MARGIN_MULTIPLIER / part["estimated_equity"] * 100.0
        )
        rows.append(part)
    if not rows:
        return pd.DataFrame()
    keep = [
        "focus_date",
        "days_before_focus",
        "profile",
        "date",
        "contract_vt_symbol",
        "product_vt_symbol",
        "direction",
        "signal",
        "selected_volume",
        "estimated_equity",
        "before_broker10_pct",
        "add_broker10_pct",
        "projected_broker10_pct",
    ]
    return pd.concat(rows, ignore_index=True, sort=False)[keep].sort_values(
        ["focus_date", "profile", "days_before_focus", "projected_broker10_pct"],
        ascending=[True, True, True, False],
    ).reset_index(drop=True)


def _plot_summary(decomposition: pd.DataFrame) -> None:
    if decomposition.empty:
        return
    data = decomposition.sort_values("c17_peak_rank").head(10).copy()
    labels = data["focus_date"].astype(str).tolist()
    x = np.arange(len(data))
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), constrained_layout=True)
    width = 0.24
    axes[0].bar(x - width, data["vs_c9_denominator_effect_pct"], width=width, label="denominator effect vs C9", color="#0f766e")
    axes[0].bar(
        x,
        data["vs_c9_exposure_effect_pct"],
        width=width,
        label="exposure effect vs C9",
        color="#d97706",
    )
    axes[0].bar(
        x + width,
        data["vs_c9_broker10_delta_pct"],
        width=width,
        label="C17-C9 broker10 delta",
        color="#7c3aed",
    )
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("Stage884 C17 broker10 delta decomposition vs C9")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=35, ha="right")
    axes[0].set_ylabel("percentage points")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.25)

    axes[1].bar(x, data["c17_broker10_margin"] / 1_000_000.0, label="C17 broker10 margin", color="#2563eb")
    axes[1].bar(
        x,
        data["vs_c9_base_broker10_margin"] / 1_000_000.0,
        alpha=0.55,
        label="C9 broker10 margin",
        color="#9333ea",
    )
    ax2 = axes[1].twinx()
    ax2.plot(x, data["vs_c9_equity_ratio_c17_to_base"], color="#dc2626", marker="s", label="C17/C9 equity ratio")
    axes[1].set_title("Margin numerator and equity denominator")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=35, ha="right")
    axes[1].set_ylabel("broker10 margin million")
    ax2.set_ylabel("C17/C9 equity ratio")
    handles1, labels1 = axes[1].get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    axes[1].legend(handles1 + handles2, labels1 + labels2, loc="best")
    axes[1].grid(True, alpha=0.25)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_atlas(
    active_lots: pd.DataFrame,
    pair_delta: pd.DataFrame,
    minute_by_symbol: dict[str, pd.DataFrame],
) -> tuple[list[Path], pd.DataFrame]:
    if active_lots.empty or pair_delta.empty:
        return [], pd.DataFrame()
    available_lots = active_lots[pd.to_numeric(active_lots["focus_day_minute_bars"], errors="coerce").fillna(0).gt(0)].copy()
    if available_lots.empty:
        available_lots = active_lots.copy()
    positive_pairs = pair_delta[pair_delta["c17_minus_c9_broker10_pct"].gt(0)].sort_values(
        "c17_minus_c9_broker10_pct",
        ascending=False,
    )
    selected_rows: list[pd.DataFrame] = []
    for _, pair in positive_pairs.head(12).iterrows():
        rows = available_lots[
            available_lots["arm"].eq(C17_ARM)
            & available_lots["focus_date"].astype(str).eq(str(pair["focus_date"]))
            & available_lots["product_vt_symbol"].astype(str).eq(str(pair["product_vt_symbol"]))
            & available_lots["direction"].astype(str).eq(str(pair["direction"]))
        ].copy()
        if rows.empty:
            continue
        selected_rows.append(rows.sort_values("estimated_broker10_margin_to_equity_pct", ascending=False).head(1))
    if selected_rows:
        selected = pd.concat(selected_rows, ignore_index=True, sort=False)
    else:
        selected = available_lots[available_lots["arm"].eq(C17_ARM)].copy()
    selected = (
        selected.sort_values("estimated_broker10_margin_to_equity_pct", ascending=False)
        .drop_duplicates(["focus_date", "vt_symbol", "direction"])
        .head(MAX_ATLAS_ROWS)
        .reset_index(drop=True)
    )
    if selected.empty:
        return [], pd.DataFrame()

    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page_start in range(0, len(selected), PER_PAGE):
        page_rows = selected.iloc[page_start : page_start + PER_PAGE]
        page = page_start // PER_PAGE + 1
        fig, axes = plt.subplots(PER_PAGE, 1, figsize=(16, 4.4 * PER_PAGE), constrained_layout=True)
        axes_arr = np.atleast_1d(axes)
        for ax, (_, row) in zip(axes_arr, page_rows.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            focus_date = pd.Timestamp(row["focus_date"]).normalize()
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = pd.DataFrame()
            if not bars.empty:
                day = bars[bars["bar_date"].eq(focus_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
            if day.empty:
                ax.text(
                    0.5,
                    0.5,
                    f"missing minute bars {vt_symbol} {focus_date:%Y-%m-%d}",
                    ha="center",
                    va="center",
                )
                ax.set_axis_off()
            else:
                s825._plot_candles(ax, day)
                for label, price, color, linestyle in [
                    ("entry", row.get("entry_price"), "#2563eb", "-"),
                    ("focus close", row.get("focus_price"), "#0f766e", "--"),
                    ("exit", row.get("exit_price"), "#dc2626", ":"),
                ]:
                    value = _safe_float(price)
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles, strict=False))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                f"{focus_date:%Y-%m-%d} {vt_symbol} {row.get('direction')} "
                f"C17 broker10 {row.get('estimated_broker10_margin_to_equity_pct'):.2f}%",
                fontsize=9,
            )
            manifest.append(
                {
                    "page": page,
                    "focus_date": focus_date.date().isoformat(),
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": row.get("product_vt_symbol"),
                    "direction": row.get("direction"),
                    "entry_date": row.get("entry_date"),
                    "exit_date": row.get("exit_date"),
                    "volume": _safe_float(row.get("volume")),
                    "estimated_broker10_margin_to_equity_pct": _safe_float(
                        row.get("estimated_broker10_margin_to_equity_pct")
                    ),
                    "focus_day_minute_bars": int(_safe_float(row.get("focus_day_minute_bars"), 0.0)),
                    "focus_price_source": row.get("focus_price_source"),
                }
            )
        for ax in axes_arr[len(page_rows) :]:
            ax.set_axis_off()
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.suptitle("Stage884 C17 broker10 peak active-lot minute-K atlas", fontsize=13)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(decomposition: pd.DataFrame) -> str:
    if decomposition.empty:
        return "stage884_broker10_path_forensics_failed_no_decomposition"
    top = decomposition.head(10).copy()
    denominator_dominant = top["dominant_mechanism_vs_c9"].eq("equity_denominator_compression").sum()
    exposure_expansion = top["dominant_mechanism_vs_c9"].eq("exposure_numerator_expansion").sum()
    if denominator_dominant >= 7 and exposure_expansion <= 2:
        return "stage884_broker10_worse_mainly_equity_denominator_no_engine"
    return "stage884_broker10_has_exposure_signal_needs_readonly_followup"


def _write_report(
    peaks: pd.DataFrame,
    decomposition: pd.DataFrame,
    pair_delta: pd.DataFrame,
    cumulative_pnl_delta: pd.DataFrame,
    atlas_paths: list[Path],
    decision: str,
) -> None:
    top_decomp = decomposition.head(10).copy()
    mechanism_counts = (
        top_decomp["dominant_mechanism_vs_c9"].value_counts().rename_axis("mechanism").reset_index(name="count")
        if not top_decomp.empty
        else pd.DataFrame()
    )
    top_positive_pairs = pair_delta[pair_delta["c17_minus_c9_broker10_pct"].gt(0)].sort_values(
        "c17_minus_c9_broker10_pct",
        ascending=False,
    ).head(12)
    top_pnl_deficits = cumulative_pnl_delta.sort_values("c17_minus_c9_realized_pnl").head(12)
    lines = [
        "# Stage884 Stage883 broker10 路径归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读归因和视觉复盘；不改正式版、不改 Stage819 候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- Turtle Trading 原始规则强调 volatility-normalized position sizing 与组合风险控制：https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf",
        "- Backtrader order execution docs 说明规则回测必须尊重成交语义：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/",
        "- Van Tharp / portfolio heat 资料强调单笔仓位之外还要看组合 heat；本阶段只把它作为第一性原则，不复制阈值。",
        "- 我的判断：Stage883 不是继续调 `progress R` 的问题，而要拆开 broker10 的分子和分母：若主要是权益分母被削低，就不能用简单缩手或入场过滤解决。",
        "",
        "## Decomposition",
        "",
        _md_table(top_decomp, max_rows=12),
        "",
        "## Mechanism Counts",
        "",
        _md_table(mechanism_counts, max_rows=10),
        "",
        "## Peak Dates",
        "",
        _md_table(peaks.head(20), max_rows=20),
        "",
        "## C17 Positive Product-Direction Broker10 Deltas",
        "",
        _md_table(top_positive_pairs, max_rows=12),
        "",
        "## Cumulative PnL Deficits Before Focus Dates",
        "",
        _md_table(top_pnl_deficits, max_rows=12),
        "",
        "## Visuals",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        *[f"- atlas page：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        f"- 决策：`{decision}`。",
        "- 如果 broker10 恶化主要来自 C17 前序权益分母被削低，而不是当下持仓分子扩大，则不应把 Stage884 变成一个新的仓位缩手引擎。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DECISION_IN.exists():
        raise RuntimeError(f"missing Stage883 decision: {DECISION_IN}")

    metadata = s513._metadata()
    curve = _prepare_curve(_load_required_csv(CURVE_IN))
    closed_lots = _prepare_closed_lots(_load_required_csv(CLOSED_LOTS_IN))
    entry_risk = _load_required_csv(ENTRY_RISK_IN) if ENTRY_RISK_IN.exists() else pd.DataFrame()

    peaks = _peak_dates(curve)
    c17_peak_dates = [
        pd.Timestamp(item).normalize()
        for item in peaks.loc[pd.to_numeric(peaks[f"{C17_ARM}_peak_rank"], errors="coerce").fillna(0).gt(0), "focus_date"]
    ]
    focus_dates = sorted(set(pd.to_datetime(peaks["focus_date"], errors="coerce").dropna().map(pd.Timestamp).map(lambda x: x.normalize())))

    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s864._load_full_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)

    active_lots = _active_lots_for_focus(closed_lots, curve, focus_dates, minute_by_symbol, metadata)
    product_direction = _product_direction(active_lots)
    pair_delta = _pair_delta(product_direction)
    decomposition = _denominator_decomposition(curve, peaks)
    cumulative_pnl_delta = _cumulative_pnl_delta(closed_lots, c17_peak_dates)
    entry_context = _entry_context(entry_risk, c17_peak_dates)

    _plot_summary(decomposition)
    atlas_paths, atlas_manifest = _plot_atlas(active_lots, pair_delta, minute_by_symbol)

    decision = _decision(decomposition)

    peaks.to_csv(PEAK_DATES_PATH, index=False, encoding="utf-8-sig")
    active_lots.to_csv(ACTIVE_LOTS_PATH, index=False, encoding="utf-8-sig")
    product_direction.to_csv(PRODUCT_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    pair_delta.to_csv(PAIR_DELTA_PATH, index=False, encoding="utf-8-sig")
    decomposition.to_csv(DECOMPOSITION_PATH, index=False, encoding="utf-8-sig")
    cumulative_pnl_delta.to_csv(CUMULATIVE_PNL_DELTA_PATH, index=False, encoding="utf-8-sig")
    entry_context.to_csv(ENTRY_CONTEXT_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    _write_report(peaks, decomposition, pair_delta, cumulative_pnl_delta, atlas_paths, decision)

    payload = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_stage883_decision": json.loads(DECISION_IN.read_text(encoding="utf-8")),
        "decision": decision,
        "top10_c17_mechanism_counts": (
            decomposition.head(10)["dominant_mechanism_vs_c9"].value_counts().to_dict()
            if not decomposition.empty
            else {}
        ),
        "outputs": {
            "report": str(REPORT_PATH),
            "peak_dates": str(PEAK_DATES_PATH),
            "active_lots": str(ACTIVE_LOTS_PATH),
            "product_direction": str(PRODUCT_DIRECTION_PATH),
            "pair_delta": str(PAIR_DELTA_PATH),
            "decomposition": str(DECOMPOSITION_PATH),
            "cumulative_pnl_delta": str(CUMULATIVE_PNL_DELTA_PATH),
            "entry_context": str(ENTRY_CONTEXT_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
