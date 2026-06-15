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
import analyze_qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit as s889


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage892"
MODEL_TAG = "stage892_stage891_market_breadth_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage892_stage891_market_breadth_audit"
SOURCE_CANDIDATE = "official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"

EARLY_BARS = 60
MIN_MARKET_SYMBOLS = 20
BREATH_MIDPOINT = 0.50
PER_PAGE = 4
MAX_ATLAS_ROWS = 24

FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
MARKET_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_market_daily_{MODEL_TAG}.csv"
STATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
PROXY_YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_yearly_{MODEL_TAG}.csv"
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
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _direction_sign(direction: str) -> int:
    return 1 if str(direction).lower() == "long" else -1


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _prepare_stage889_features() -> pd.DataFrame:
    if s889.FEATURES_PATH.exists():
        data = _load_required_csv(s889.FEATURES_PATH)
    else:
        data = s889._build_features()
    for column in ["entry_date", "exit_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    numeric_columns = [
        "lot_id",
        "entry_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "winner",
        "big_winner",
        "early_price_dir_return_pct",
        "early_oi_change_pct",
        "early_exit_pnl",
        "early_exit_delta",
        "first_0p5r_bar_index",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    return data.reset_index(drop=True)


def _load_full_minute_bars() -> pd.DataFrame:
    data = _load_required_csv(s889.FULL_MINUTE_BARS_PATH)
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "bar_date", "open", "close"]).reset_index(drop=True)


def _build_market_daily(minute_bars: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (bar_date, vt_symbol), group in minute_bars.groupby(["bar_date", "vt_symbol"], dropna=False):
        first = group.sort_values("bar_datetime").head(EARLY_BARS).copy()
        if len(first) < EARLY_BARS:
            continue
        open_price = _safe_float(first.iloc[0]["open"])
        close_price = _safe_float(first.iloc[-1]["close"])
        if open_price <= 0 or not np.isfinite(close_price):
            continue
        ret_pct = (close_price / open_price - 1.0) * 100.0
        rows.append(
            {
                "bar_date": pd.Timestamp(bar_date).normalize(),
                "vt_symbol": str(vt_symbol),
                "first60_return_pct": ret_pct,
                "first60_volume_sum": float(pd.to_numeric(first["volume"], errors="coerce").fillna(0.0).sum()),
                "first60_oi_change_pct": (
                    (float(first.iloc[-1]["close_oi"]) / float(first.iloc[0]["open_oi"]) - 1.0) * 100.0
                    if _safe_float(first.iloc[0].get("open_oi"), 0.0) > 0
                    and np.isfinite(_safe_float(first.iloc[-1].get("close_oi")))
                    else np.nan
                ),
            }
        )
    symbol_daily = pd.DataFrame(rows)
    if symbol_daily.empty:
        return pd.DataFrame()

    daily_rows: list[dict[str, Any]] = []
    for bar_date, group in symbol_daily.groupby("bar_date", dropna=False):
        returns = pd.to_numeric(group["first60_return_pct"], errors="coerce").dropna()
        if returns.empty:
            continue
        daily_rows.append(
            {
                "bar_date": pd.Timestamp(bar_date).normalize(),
                "market_symbol_count": int(len(returns)),
                "market_up_share": float(returns.gt(0).mean()),
                "market_down_share": float(returns.lt(0).mean()),
                "market_flat_share": float(returns.eq(0).mean()),
                "market_median_return_pct": float(returns.median()),
                "market_mean_abs_return_pct": float(returns.abs().mean()),
                "market_total_first60_volume": float(pd.to_numeric(group["first60_volume_sum"], errors="coerce").sum()),
                "market_median_oi_change_pct": float(
                    pd.to_numeric(group["first60_oi_change_pct"], errors="coerce").median()
                ),
            }
        )
    return pd.DataFrame(daily_rows).sort_values("bar_date").reset_index(drop=True)


def _build_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    lots = _prepare_stage889_features()
    minute_bars = _load_full_minute_bars()
    market_daily = _build_market_daily(minute_bars)
    data = lots.merge(market_daily, left_on="entry_date", right_on="bar_date", how="left")
    sign = data["direction"].map(_direction_sign)
    data["market_same_direction_share"] = np.where(
        sign.gt(0),
        data["market_up_share"],
        data["market_down_share"],
    )
    data["market_opposite_direction_share"] = np.where(
        sign.gt(0),
        data["market_down_share"],
        data["market_up_share"],
    )
    data["market_signal_median_return_pct"] = sign * data["market_median_return_pct"]
    data["market_breadth_state"] = np.where(
        data["market_symbol_count"].fillna(0).lt(MIN_MARKET_SYMBOLS),
        "market_breadth_missing",
        np.where(
            data["market_same_direction_share"].ge(BREATH_MIDPOINT),
            "market_breadth_favorable",
            "market_breadth_adverse",
        ),
    )
    early_price = pd.to_numeric(data["early_price_dir_return_pct"], errors="coerce")
    data["own_first60_price_side"] = np.where(early_price.ge(0), "own_price_favorable", "own_price_adverse")
    data.loc[early_price.isna(), "own_first60_price_side"] = "own_price_missing"
    data["market_own_combo_state"] = data["market_breadth_state"].astype(str) + "__" + data[
        "own_first60_price_side"
    ].astype(str)
    return data, market_daily


def _state_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_loser_pnl = float(pd.to_numeric(features["realized_pnl"], errors="coerce").clip(upper=0).sum())
    for state, group in features.groupby("market_own_combo_state", dropna=False):
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        loser_pnl = float(pnl[pnl.lt(0)].sum())
        rows.append(
            {
                "market_own_combo_state": str(state),
                "lots": int(len(group)),
                "lot_pct": float(len(group) / len(features) * 100.0) if len(features) else 0.0,
                "pnl_sum": float(pnl.sum()),
                "loser_lots": int(pnl.lt(0).sum()),
                "loser_pnl": loser_pnl,
                "loser_pnl_coverage_pct": float(abs(loser_pnl) / abs(total_loser_pnl) * 100.0)
                if total_loser_pnl < 0
                else 0.0,
                "winner_lots": int(pnl.gt(0).sum()),
                "winner_pnl": float(pnl[pnl.gt(0)].sum()),
                "big_winner_lots": int(pd.to_numeric(group["big_winner"], errors="coerce").fillna(0).sum()),
                "median_r": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                "median_same_direction_share": float(
                    pd.to_numeric(group["market_same_direction_share"], errors="coerce").median()
                ),
                "median_market_signal_return_pct": float(
                    pd.to_numeric(group["market_signal_median_return_pct"], errors="coerce").median()
                ),
                "median_own_first60_price_return_pct": float(
                    pd.to_numeric(group["early_price_dir_return_pct"], errors="coerce").median()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["loser_pnl_coverage_pct", "lots"], ascending=[False, False]).reset_index(
        drop=True
    )


def _proxy_masks(features: pd.DataFrame) -> list[dict[str, Any]]:
    market_adverse = features["market_breadth_state"].eq("market_breadth_adverse")
    own_adverse = features["own_first60_price_side"].eq("own_price_adverse")
    own_favorable = features["own_first60_price_side"].eq("own_price_favorable")
    first05_adverse = features["first_0p5r_outcome"].astype(str).eq("adverse_first")
    return [
        {
            "proxy_id": "MB1_exit60_market_breadth_adverse",
            "rule_text": "Exit at 60th-bar close if market first60 breadth is adverse to the signal direction.",
            "mask": market_adverse,
        },
        {
            "proxy_id": "MB2_exit60_market_and_own_price_adverse",
            "rule_text": "Exit at 60th-bar close if market breadth is adverse and own first60 price is adverse.",
            "mask": market_adverse & own_adverse,
        },
        {
            "proxy_id": "MB3_exit60_market_adverse_and_05r_adverse_first",
            "rule_text": "Exit at 60th-bar close if market breadth is adverse and own entry-day first 0.5R event is adverse.",
            "mask": market_adverse & first05_adverse,
        },
        {
            "proxy_id": "MB4_exit60_market_adverse_own_price_favorable",
            "rule_text": "Exit at 60th-bar close if market breadth is adverse but own first60 price is favorable.",
            "mask": market_adverse & own_favorable,
        },
    ]


def _summarize_proxy(features: pd.DataFrame, proxy_id: str, rule_text: str, mask: pd.Series) -> tuple[dict[str, Any], pd.DataFrame]:
    triggered = features[mask.fillna(False)].copy()
    applicable = triggered[pd.to_numeric(triggered["early_exit_delta"], errors="coerce").notna()].copy()
    if applicable.empty:
        base_total = float(pd.to_numeric(features["realized_pnl"], errors="coerce").sum())
        summary = {
            "proxy_id": proxy_id,
            "rule_text": rule_text,
            "trigger_lots": int(len(triggered)),
            "applicable_lots": 0,
            "applicable_lot_pct": 0.0,
            "affected_original_pnl": 0.0,
            "gross_proxy_delta": 0.0,
            "base_total_pnl": base_total,
            "proxy_total_pnl": base_total,
            "winner_cut": 0.0,
            "loser_saved": 0.0,
            "big_winner_cut": 0.0,
            "affected_big_winner_lots": 0,
            "positive_delta_years": 0,
            "negative_delta_years": 0,
            "decision_hint": "not_promoted_no_trigger",
        }
        return summary, pd.DataFrame()

    pnl = pd.to_numeric(applicable["realized_pnl"], errors="coerce").fillna(0.0)
    delta = pd.to_numeric(applicable["early_exit_delta"], errors="coerce").fillna(0.0)
    years = (
        applicable.assign(delta=delta)
        .groupby("entry_year", dropna=False)["delta"]
        .sum()
        .reset_index(name="gross_proxy_delta")
    )
    base_total = float(pd.to_numeric(features["realized_pnl"], errors="coerce").sum())
    gross_delta = float(delta.sum())
    winner_cut = float(delta[pnl.gt(0)].sum())
    loser_saved = float(delta[pnl.lt(0)].sum())
    big_mask = pd.to_numeric(applicable["big_winner"], errors="coerce").fillna(0).gt(0)
    big_winner_cut = float(delta[big_mask].sum())
    pos_years = int(years["gross_proxy_delta"].gt(0).sum())
    neg_years = int(years["gross_proxy_delta"].lt(0).sum())
    hint = "positive_proxy_only_needs_true_engine" if gross_delta > 0 else "not_promoted_proxy_negative"
    if gross_delta > 0 and len(applicable) < 10:
        hint = "positive_proxy_too_sparse"
    summary = {
        "proxy_id": proxy_id,
        "rule_text": rule_text,
        "trigger_lots": int(len(triggered)),
        "applicable_lots": int(len(applicable)),
        "applicable_lot_pct": float(len(applicable) / len(features) * 100.0),
        "affected_original_pnl": float(pnl.sum()),
        "gross_proxy_delta": gross_delta,
        "base_total_pnl": base_total,
        "proxy_total_pnl": base_total + gross_delta,
        "winner_cut": winner_cut,
        "loser_saved": loser_saved,
        "big_winner_cut": big_winner_cut,
        "affected_big_winner_lots": int(big_mask.sum()),
        "positive_delta_years": pos_years,
        "negative_delta_years": neg_years,
        "decision_hint": hint,
    }
    years.insert(0, "proxy_id", proxy_id)
    years["affected_lots"] = applicable.groupby("entry_year")["lot_id"].count().reindex(years["entry_year"]).to_numpy()
    years["winner_cut"] = applicable.assign(delta=delta, winner=pnl.gt(0)).groupby("entry_year").apply(
        lambda g: float(g.loc[g["winner"], "delta"].sum()), include_groups=False
    ).reindex(years["entry_year"], fill_value=0.0).to_numpy()
    years["loser_saved"] = applicable.assign(delta=delta, loser=pnl.lt(0)).groupby("entry_year").apply(
        lambda g: float(g.loc[g["loser"], "delta"].sum()), include_groups=False
    ).reindex(years["entry_year"], fill_value=0.0).to_numpy()
    years["big_winner_cut"] = applicable.assign(delta=delta, big_winner=big_mask).groupby("entry_year").apply(
        lambda g: float(g.loc[g["big_winner"], "delta"].sum()), include_groups=False
    ).reindex(years["entry_year"], fill_value=0.0).to_numpy()
    return summary, years


def _proxy_summary(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summaries: list[dict[str, Any]] = []
    yearly_parts: list[pd.DataFrame] = []
    for spec in _proxy_masks(features):
        summary, yearly = _summarize_proxy(features, spec["proxy_id"], spec["rule_text"], spec["mask"])
        summaries.append(summary)
        yearly_parts.append(yearly)
    return pd.DataFrame(summaries), pd.concat(yearly_parts, ignore_index=True) if yearly_parts else pd.DataFrame()


def _plot_summary(state_summary: pd.DataFrame, proxy_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(18, 14), constrained_layout=True)
    axes[0].bar(state_summary["market_own_combo_state"], state_summary["loser_pnl_coverage_pct"], color="#dc2626")
    axes[0].set_title("C9 loser PnL coverage by market breadth + own first60 state")
    axes[0].set_ylabel("loser PnL coverage (%)")
    axes[0].tick_params(axis="x", rotation=22, labelsize=8)
    axes[0].grid(axis="y", alpha=0.2)

    colors = np.where(proxy_summary["gross_proxy_delta"].gt(0), "#16a34a", "#64748b")
    axes[1].bar(proxy_summary["proxy_id"], proxy_summary["gross_proxy_delta"] / 1_000_000, color=colors)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Exit60 proxy deltas by market breadth state")
    axes[1].set_ylabel("delta, million")
    axes[1].tick_params(axis="x", rotation=18, labelsize=8)
    axes[1].grid(axis="y", alpha=0.2)

    axes[2].scatter(
        state_summary["median_same_direction_share"],
        state_summary["pnl_sum"] / 1_000_000,
        s=np.maximum(40, state_summary["lots"] * 5),
        c=np.where(state_summary["pnl_sum"].ge(0), "#16a34a", "#dc2626"),
        alpha=0.78,
    )
    for _, row in state_summary.iterrows():
        axes[2].annotate(str(row["market_own_combo_state"]).replace("market_breadth_", "").replace("__", "\n"), (
            row["median_same_direction_share"],
            row["pnl_sum"] / 1_000_000,
        ), xytext=(4, 4), textcoords="offset points", fontsize=7)
    axes[2].axhline(0, color="#111827", linewidth=0.8)
    axes[2].axvline(BREATH_MIDPOINT, color="#64748b", linestyle="--", linewidth=0.8)
    axes[2].set_title("State PnL vs market same-direction breadth")
    axes[2].set_xlabel("median same-direction breadth share")
    axes[2].set_ylabel("PnL, million")
    axes[2].grid(alpha=0.2)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame, proxy_summary: pd.DataFrame) -> pd.DataFrame:
    masks = {spec["proxy_id"]: spec["mask"] for spec in _proxy_masks(features)}
    parts: list[pd.DataFrame] = []
    ordered = list(proxy_summary.sort_values("gross_proxy_delta", ascending=False)["proxy_id"])
    for proxy_id in ordered:
        subset = features[masks[proxy_id].fillna(False)].copy()
        if subset.empty:
            continue
        subset["atlas_proxy_id"] = proxy_id
        parts.append(subset.sort_values("realized_pnl", ascending=True).head(2))
        parts.append(subset.sort_values("realized_pnl", ascending=False).head(2))
    if not parts:
        # If the broad-market trigger never becomes applicable, still render representative K-line evidence
        # so the audit has visual support for the data-scope conclusion.
        for state, subset in features.groupby("market_own_combo_state", dropna=False):
            sample = subset.copy()
            if sample.empty:
                continue
            sample["atlas_proxy_id"] = f"MB0_representative_{state}"
            parts.append(sample.sort_values("realized_pnl", ascending=True).head(2))
            parts.append(sample.sort_values("realized_pnl", ascending=False).head(2))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates("lot_id").head(MAX_ATLAS_ROWS).reset_index(drop=True)


def _plot_row(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row["vt_symbol"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    direction = str(row["direction"])
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = (
        bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(340).reset_index(drop=True)
        if not bars.empty
        else pd.DataFrame()
    )
    record = {
        "lot_id": int(_safe_float(row.get("lot_id"), -1)),
        "vt_symbol": vt_symbol,
        "entry_date": entry_date.strftime("%Y-%m-%d") if pd.notna(entry_date) else "",
        "atlas_proxy_id": str(row.get("atlas_proxy_id", "")),
        "market_breadth_state": str(row.get("market_breadth_state", "")),
        "market_same_direction_share": _safe_float(row.get("market_same_direction_share")),
        "chart_missing_minutes": int(day.empty),
    }
    if day.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"missing minute bars\n{vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
        return record

    s825._plot_candles(ax, day)
    entry_price = _safe_float(row.get("entry_price"))
    risk_amount = _safe_float(row.get("risk_amount"))
    volume = _safe_float(row.get("volume"))
    size = _safe_float(row.get("size"))
    risk_price = risk_amount / (volume * size) if volume > 0 and size > 0 else np.nan
    sign = _direction_sign(direction)
    ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.9, label="entry")
    if risk_price > 0:
        ax.axhline(entry_price - sign * 0.5 * risk_price, color="#ef4444", linewidth=0.9, alpha=0.85, label="-0.5R")
        ax.axhline(entry_price + sign * 0.5 * risk_price, color="#22c55e", linewidth=0.9, alpha=0.85, label="+0.5R")
    if len(day) >= EARLY_BARS:
        ax.axvspan(0, EARLY_BARS - 1, color="#fef3c7", alpha=0.22)
    ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        dedup = dict(zip(labels, handles))
        ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
    title = (
        f"lot{int(_safe_float(row.get('lot_id'), -1))} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
        f"{row.get('atlas_proxy_id')} breadth={_safe_float(row.get('market_same_direction_share')):.2f} "
        f"n={int(_safe_float(row.get('market_symbol_count'), 0))} own60={_safe_float(row.get('early_price_dir_return_pct')):.2f}% "
        f"delta={_safe_float(row.get('early_exit_delta')):,.0f} pnl={_safe_float(row.get('realized_pnl')):,.0f}"
    )
    ax.set_title(title, fontsize=8.0, loc="left")
    return record


def _plot_atlas(features: pd.DataFrame, proxy_summary: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(features, proxy_summary)
    if selected.empty:
        return [], pd.DataFrame()
    minute_bars = s889._prepare_minute_bars(set(selected["vt_symbol"].astype(str).dropna()))
    minute_by_symbol = s825._minute_groups(minute_bars)
    page_count = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, page_count + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.25 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            rec = _plot_row(ax, row, minute_by_symbol)
            rec.update(
                {
                    "chart_page": page,
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "early_exit_delta": _safe_float(row.get("early_exit_delta")),
                    "own_first60_price_side": str(row.get("own_first60_price_side", "")),
                }
            )
            records.append(rec)
        fig.suptitle(
            (
                f"Stage892 market breadth atlas page {page}/{page_count}; "
                "blue=entry, red=-0.5R, green=+0.5R, yellow=first60"
            ),
            fontsize=13,
        )
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _decision(features: pd.DataFrame, proxy_summary: pd.DataFrame) -> str:
    missing_share = float(features["market_breadth_state"].eq("market_breadth_missing").mean())
    if missing_share >= 0.95:
        return "stage892_market_breadth_data_scope_not_broad_enough_no_engine"
    positive = proxy_summary[proxy_summary["gross_proxy_delta"].gt(0)].copy()
    if positive.empty:
        return "stage892_market_breadth_proxy_negative_no_engine"
    best = positive.sort_values("gross_proxy_delta", ascending=False).iloc[0]
    loser_pnl = abs(float(pd.to_numeric(features["realized_pnl"], errors="coerce").clip(upper=0).sum()))
    materiality = loser_pnl * 0.01
    if _safe_float(best["gross_proxy_delta"]) < materiality:
        return "stage892_market_breadth_tiny_positive_proxy_no_engine"
    if int(_safe_float(best["positive_delta_years"], 0.0)) < int(_safe_float(best["negative_delta_years"], 0.0)):
        return "stage892_market_breadth_year_fragile_no_engine"
    if _safe_float(best["winner_cut"], 0.0) < 0 and abs(_safe_float(best["winner_cut"], 0.0)) > _safe_float(
        best["loser_saved"], 0.0
    ):
        return "stage892_market_breadth_right_tail_cost_no_engine"
    return "stage892_market_breadth_positive_proxy_only_needs_true_engine"


def _write_report(
    features: pd.DataFrame,
    market_daily: pd.DataFrame,
    state_summary: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    proxy_yearly: pd.DataFrame,
    atlas_paths: list[Path],
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage892 market breadth first60 audit",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- source_candidate: `{SOURCE_CANDIDATE}`",
        "- scope: readonly first60 cross-market breadth audit; no new rule, no true engine, no CTP, no A/B.",
        "",
        "## External Research Judgment",
        "",
        "- CME materials support using broad market participation, volume/OI, and predefined stop discipline as context.",
        "- My judgment: breadth can be an exogenous participation label, but only a fixed 50% first60 breadth midpoint is allowed here; no threshold, product, direction, or year scan.",
        "",
        "## Data Scope",
        "",
        f"- C9 closed lots: `{len(features)}`",
        f"- market daily rows: `{len(market_daily)}`",
        f"- min market symbols per date: `{MIN_MARKET_SYMBOLS}`",
        f"- breadth midpoint: `{BREATH_MIDPOINT}`",
        f"- atlas pages: `{len(atlas_paths)}`",
        "",
        "## State Summary",
        "",
        _md_table(state_summary, max_rows=12),
        "",
        "## Proxy Summary",
        "",
        _md_table(proxy_summary, max_rows=None),
        "",
        "## Proxy Yearly",
        "",
        _md_table(proxy_yearly, max_rows=40),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- best_proxy: `{decision['best_proxy']['proxy_id']}`",
        f"- conclusion: {decision['conclusion']}",
        "",
        "## Visual Atlas",
        "",
        f"- summary chart: `{SUMMARY_CHART_PATH}`",
    ]
    for path in atlas_paths:
        lines.append(f"- atlas: `{path}`")
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- features: `{FEATURES_PATH}`",
            f"- market daily: `{MARKET_DAILY_PATH}`",
            f"- state summary: `{STATE_SUMMARY_PATH}`",
            f"- proxy summary: `{PROXY_SUMMARY_PATH}`",
            f"- proxy yearly: `{PROXY_YEARLY_PATH}`",
            f"- atlas manifest: `{ATLAS_MANIFEST_PATH}`",
            f"- decision: `{DECISION_PATH}`",
            "",
            "## Anti-overfit Reflection",
            "",
            "- Before run: no. This uses one fixed first60 window and one fixed 50% cross-market breadth midpoint.",
            "- After run: if the result is weak, scanning breadth thresholds, product families, directions, years, or alternative minute windows would be overfitting.",
            "",
            "## Continue-Value Reflection",
            "",
            "- Before run: valuable. This is a genuinely different information source from own-contract K-line micro-shapes.",
            "- After run: follow the decision. Only a material, stable proxy with controlled winner-cut may justify a frozen true engine.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features, market_daily = _build_features()
    state_summary = _state_summary(features)
    proxy_summary, proxy_yearly = _proxy_summary(features)
    _plot_summary(state_summary, proxy_summary)
    atlas_paths, atlas_manifest = _plot_atlas(features, proxy_summary)

    features.to_csv(FEATURES_PATH, index=False, encoding="utf-8-sig")
    market_daily.to_csv(MARKET_DAILY_PATH, index=False, encoding="utf-8-sig")
    state_summary.to_csv(STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_yearly.to_csv(PROXY_YEARLY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    positive = proxy_summary[proxy_summary["gross_proxy_delta"].gt(0)].copy()
    best_proxy = (
        positive.sort_values("gross_proxy_delta", ascending=False).iloc[0].to_dict()
        if not positive.empty
        else proxy_summary.sort_values("gross_proxy_delta", ascending=False).iloc[0].to_dict()
    )
    decision_value = _decision(features, proxy_summary)
    if decision_value == "stage892_market_breadth_data_scope_not_broad_enough_no_engine":
        conclusion = (
            "The Stage861 minute source is complete for target trades but is event-scoped, not a broad "
            "continuous market panel; fixed first60 market breadth is therefore not actionable from this data."
        )
    else:
        conclusion = (
            "Only promote market breadth if the fixed first60 50% breadth label materially improves proxy PnL, "
            "is not year-fragile, and avoids material right-tail cuts."
        )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_candidate": SOURCE_CANDIDATE,
        "decision": decision_value,
        "c9_closed_lots": int(len(features)),
        "market_daily_rows": int(len(market_daily)),
        "market_min_symbols": MIN_MARKET_SYMBOLS,
        "breadth_midpoint": BREATH_MIDPOINT,
        "best_proxy": best_proxy,
        "market_breadth_missing_lot_pct": float(features["market_breadth_state"].eq("market_breadth_missing").mean() * 100.0),
        "conclusion": conclusion,
        "guardrails": {
            "strategy_changed": False,
            "official_stage372_changed": False,
            "official_candidate_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "formal_ab_triggered": False,
            "readonly_only": True,
            "new_rule_created": False,
        },
        "outputs": {
            "features": str(FEATURES_PATH),
            "market_daily": str(MARKET_DAILY_PATH),
            "state_summary": str(STATE_SUMMARY_PATH),
            "proxy_summary": str(PROXY_SUMMARY_PATH),
            "proxy_yearly": str(PROXY_YEARLY_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    _write_report(features, market_daily, state_summary, proxy_summary, proxy_yearly, atlas_paths, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
