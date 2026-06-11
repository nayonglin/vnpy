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

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage752_theoretical_winner_kline_atlas as s752
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage777_am41_oi08_monthly as s777
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage797_stage777_top_loss_kline_atlas_v2"
OUTPUT_PREFIX = "qmt_roll_stage797_stage777_top_loss_kline_atlas"
LINE_ID = "futures_trend_2019_data_extension"

START = pd.Timestamp("2020-01-01")
TOP_N = 5
PRE_BARS = 50
POST_BARS = 50
MA_LINES = (
    (5, "#f59e0b"),
    (10, "#2563eb"),
    (20, "#7c3aed"),
    (40, "#111827"),
)

CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
PRIOR_CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_stage797_stage777_top_loss_kline_atlas_v1.csv"
TOP_LOSSES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_losses_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top5_kline_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _safe_float(row: pd.Series, column: str) -> float:
    try:
        return float(row.get(column, np.nan))
    except (TypeError, ValueError):
        return math.nan


def _format_money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "nan"
    return f"{number:,.0f}"


def _stage777_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profiles = {profile["profile"]: profile for profile in s772._profile_specs(metadata)}
    return profiles["oi_restore_am40"]


def _holding_bar_count(row: pd.Series) -> int:
    bars = s752._read_contract_bars(row["vt_symbol"])
    if bars.empty:
        return 0
    entry_idx = s752._event_index(bars, pd.Timestamp(row["entry_date"]))
    exit_idx = s752._event_index(bars, pd.Timestamp(row["exit_date"]))
    return max(0, exit_idx - entry_idx + 1)


def _run_closed_lots() -> pd.DataFrame:
    if PRIOR_CLOSED_LOTS_PATH.exists():
        cached = pd.read_csv(PRIOR_CLOSED_LOTS_PATH, encoding="utf-8-sig")
        for column in ["entry_date", "exit_date"]:
            cached[column] = pd.to_datetime(cached[column], errors="coerce").dt.normalize()
        cached.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
        return cached

    metadata = s513._metadata()
    profile = _stage777_profile(metadata)
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    _combined, frames = s778._run_profile(
        profile=profile,
        start=START,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    trades = frames["trades"]
    entry_risk = frames["entry_risk"]
    entry_candidates = frames["entry_candidates"]
    closed = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    if closed.empty:
        raise RuntimeError("Stage777 closed lots are empty")
    enriched = s757._add_lot_features(closed, trades, entry_risk)
    for column in ["entry_date", "exit_date"]:
        enriched[column] = pd.to_datetime(enriched[column], errors="coerce").dt.normalize()
    enriched = enriched[
        enriched["entry_date"].ge(START)
        & enriched["exit_date"].le(pd.Timestamp(s777.ANALYSIS_END).normalize())
    ].copy()
    enriched.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    return enriched


def _select_top_losses(closed: pd.DataFrame) -> pd.DataFrame:
    data = closed.copy()
    data["theory_return_pct"] = pd.to_numeric(data["theory_return_pct"], errors="coerce")
    data["theory_loss_pct"] = -data["theory_return_pct"]
    data["realized_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce")
    data["r_multiple"] = pd.to_numeric(data["r_multiple"], errors="coerce")
    data["risk_multiplier"] = pd.to_numeric(data.get("risk_multiplier"), errors="coerce")
    data["oi_price_confirm_risk_restore_applied"] = pd.to_numeric(
        data.get("oi_price_confirm_risk_restore_applied"),
        errors="coerce",
    )
    losers = data[data["theory_return_pct"].lt(0.0)].copy()
    losers = losers.dropna(subset=["entry_date", "exit_date", "entry_price", "exit_price", "theory_loss_pct"])
    losers.sort_values(
        ["theory_loss_pct", "r_multiple", "realized_pnl"],
        ascending=[False, True, True],
        inplace=True,
    )
    top = losers.head(TOP_N).copy().reset_index(drop=True)
    top["loss_rank"] = np.arange(1, len(top) + 1)
    top["holding_bar_count"] = top.apply(_holding_bar_count, axis=1)
    top.to_csv(TOP_LOSSES_PATH, index=False, encoding="utf-8-sig")
    return top


def _plot_one(price_ax: plt.Axes, volume_ax: plt.Axes, row: pd.Series, bars: pd.DataFrame) -> dict[str, Any]:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    entry_idx = s752._event_index(bars, entry_date)
    exit_idx = s752._event_index(bars, exit_date)
    start = max(0, entry_idx - PRE_BARS)
    end = min(len(bars), exit_idx + POST_BARS + 1)
    window = bars.iloc[start:end].copy().reset_index(drop=True)
    local_entry_idx = entry_idx - start
    local_exit_idx = exit_idx - start

    s752._plot_candles(price_ax, window)
    for ma, color in MA_LINES:
        price_ax.plot(window["close"].rolling(ma).mean().to_numpy(), color=color, linewidth=0.9, alpha=0.82)

    price_ax.axvspan(local_entry_idx, local_exit_idx, color="#fee2e2", alpha=0.30)
    price_ax.axvline(local_entry_idx, color="#1d4ed8", linewidth=1.25, alpha=0.95)
    price_ax.axvline(local_exit_idx, color="#9333ea", linewidth=1.25, alpha=0.95)
    price_ax.scatter([local_entry_idx], [float(row["entry_price"])], marker="^", s=40, color="#1d4ed8", zorder=5)
    price_ax.scatter([local_exit_idx], [float(row["exit_price"])], marker="v", s=40, color="#9333ea", zorder=5)

    tick_positions = np.linspace(0, max(0, len(window) - 1), num=min(8, len(window)), dtype=int)
    tick_labels = [pd.Timestamp(window.loc[pos, "date"]).strftime("%Y-%m-%d") for pos in tick_positions]
    price_ax.set_xticks(tick_positions)
    price_ax.set_xticklabels([])
    price_ax.grid(True, alpha=0.18, linewidth=0.6)
    price_ax.tick_params(axis="y", labelsize=8)
    price_ax.tick_params(axis="x", length=0)

    s752._plot_volume_oi(volume_ax, window)
    volume_ax.set_xticks(tick_positions)
    volume_ax.set_xticklabels(tick_labels, rotation=32, ha="right", fontsize=7)
    volume_ax.tick_params(axis="x", labelsize=7)

    oi_applied = int(_safe_float(row, "oi_price_confirm_risk_restore_applied") == 1.0)
    oi0 = _safe_float(row, "oi_price_confirm_entry_oi")
    oi1 = _safe_float(row, "oi_price_confirm_prev_oi")
    close0 = _safe_float(row, "oi_price_confirm_entry_close")
    close1 = _safe_float(row, "oi_price_confirm_prev_close")
    title = (
        f"#{int(row['loss_rank'])} lot{int(row['lot_id'])} {row['vt_symbol']} {row['direction']} "
        f"loss={float(row['theory_loss_pct']):.2f}% R={float(row['r_multiple']):.2f} "
        f"pnl={_format_money(row['realized_pnl'])} bars={int(row['holding_bar_count'])}"
    )
    subtitle = (
        f"{entry_date:%Y-%m-%d}->{exit_date:%Y-%m-%d} "
        f"{row.get('signal', '')} exit={row.get('exit_reason', '')} "
        f"risk={float(row.get('risk_multiplier', np.nan)):.2f} "
        f"OIhit={oi_applied} OI {oi1:.0f}->{oi0:.0f} close {close1:.2f}->{close0:.2f}"
    )
    price_ax.set_title(title + "\n" + subtitle, fontsize=8.5, loc="left")
    price_ax.text(
        0.01,
        0.02,
        "blue=entry purple=exit red=holding loss | MA5/10/20/40 | lower: volume bars + OI line | pre50/post50",
        transform=price_ax.transAxes,
        fontsize=7,
        color="#475569",
    )
    return {
        "lot_id": int(row["lot_id"]),
        "window_bars": int(len(window)),
        "pre_bars_available": int(local_entry_idx),
        "post_bars_available": int(len(window) - local_exit_idx - 1),
        "chart_start": pd.Timestamp(window["date"].iloc[0]).strftime("%Y-%m-%d"),
        "chart_end": pd.Timestamp(window["date"].iloc[-1]).strftime("%Y-%m-%d"),
    }


def _plot_top(top: pd.DataFrame) -> pd.DataFrame:
    chart_records: list[dict[str, Any]] = []
    row_count = max(len(top), 1)
    fig = plt.figure(figsize=(19, 4.9 * row_count), constrained_layout=True)
    outer = fig.add_gridspec(row_count, 1)
    for idx, (_, row) in enumerate(top.iterrows()):
        inner = outer[idx].subgridspec(2, 1, height_ratios=[3.2, 1.0], hspace=0.02)
        price_ax = fig.add_subplot(inner[0])
        volume_ax = fig.add_subplot(inner[1], sharex=price_ax)
        bars = s752._read_contract_bars(row["vt_symbol"])
        if bars.empty:
            price_ax.axis("off")
            volume_ax.axis("off")
            price_ax.text(
                0.5,
                0.5,
                (
                    f"missing bars\n#{int(row['loss_rank'])} lot{int(row['lot_id'])}\n"
                    f"{row['vt_symbol']} {row['direction']}\n"
                    f"{pd.Timestamp(row['entry_date']):%Y-%m-%d}->{pd.Timestamp(row['exit_date']):%Y-%m-%d}\n"
                    f"loss={float(row['theory_loss_pct']):.2f}%"
                ),
                ha="center",
                va="center",
                fontsize=11,
                color="#991b1b",
            )
            chart_records.append(
                {
                    "lot_id": int(row["lot_id"]),
                    "window_bars": 0,
                    "pre_bars_available": 0,
                    "post_bars_available": 0,
                    "chart_start": "",
                    "chart_end": "",
                    "missing_bars": 1,
                }
            )
            continue
        chart_record = _plot_one(price_ax, volume_ax, row, bars)
        chart_record["missing_bars"] = 0
        chart_records.append(chart_record)

    fig.suptitle(
        (
            "Stage797 official candidate Stage777 2020-start top 5 theoretical loss trades "
            f"(sorted by loss pct, MA5/10/20/40, pre{PRE_BARS}/post{POST_BARS})"
        ),
        fontsize=15,
    )
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)
    return pd.DataFrame(chart_records)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    closed = _run_closed_lots()
    top = _select_top_losses(closed)
    chart_records = _plot_top(top)
    top_with_chart = top.merge(chart_records, on="lot_id", how="left")
    top_with_chart.to_csv(TOP_LOSSES_PATH, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(
        [
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "source_version": "official_candidate_stage777_50w_am41_oi08_old_ai_v1",
                "start": START.date().isoformat(),
                "analysis_end": pd.Timestamp(s777.ANALYSIS_END).date().isoformat(),
                "closed_lot_count": int(len(closed)),
                "loser_lot_count": int(pd.to_numeric(closed["theory_return_pct"], errors="coerce").lt(0.0).sum()),
                "top_n": int(len(top)),
                "ma_lines": ",".join(str(ma) for ma, _color in MA_LINES),
                "worst_theory_loss_pct": float(top["theory_loss_pct"].max()) if not top.empty else np.nan,
                "worst_r_multiple": float(top["r_multiple"].min()) if not top.empty else np.nan,
                "oi_hit_count_in_top": int(
                    pd.to_numeric(top["oi_price_confirm_risk_restore_applied"], errors="coerce").fillna(0).eq(1).sum()
                )
                if not top.empty
                else 0,
                "missing_bar_lots": int(chart_records["missing_bars"].sum()) if not chart_records.empty else 0,
                "closed_lots_path": str(CLOSED_LOTS_PATH),
                "top_losses_path": str(TOP_LOSSES_PATH),
                "chart_path": str(CHART_PATH),
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": "Stage797",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "task": "official candidate Stage777 top 5 theoretical loss K-line atlas",
        "strategy_changed": False,
        "backtest_changed": False,
        "source_version": "official_candidate_stage777_50w_am41_oi08_old_ai_v1",
        "ranking_metric": "theory_loss_pct = -directional(entry->exit return pct)",
        "overfit_reflection": (
            "Low for chart generation because no parameter is changed. Interpretation risk remains if these five trades "
            "are used to design thresholds without cross-start validation."
        ),
        "continue_value": (
            "Yes as visual forensics. Any new filter idea from these charts must be predeclared and tested across yearly/monthly starts."
        ),
        "outputs": {
            "closed_lots": str(CLOSED_LOTS_PATH),
            "top_losses": str(TOP_LOSSES_PATH),
            "summary": str(SUMMARY_PATH),
            "chart": str(CHART_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    display_cols = [
        "loss_rank",
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "exit_date",
        "theory_loss_pct",
        "realized_pnl",
        "r_multiple",
        "risk_multiplier",
        "oi_price_confirm_risk_restore_applied",
        "signal",
        "exit_reason",
    ]
    print(summary.to_string(index=False))
    print(top_with_chart[[column for column in display_cols if column in top_with_chart.columns]].to_string(index=False))
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
