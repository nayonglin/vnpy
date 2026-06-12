from __future__ import annotations

from dataclasses import replace
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
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage798_stage777_top20_loss_kline_atlas as s798
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804
import analyze_qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly as s813
import qmt_roll_official_candidate_stage813_config as stage813_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
TUSHARE_EARLY_ROOT = PROJECT_DIR / "downloaded_futures" / "tushare_stage196_stage78_2015_2019"

MODEL_TAG = "stage815_stage813_top40_loss_kline_atlas_v1"
OUTPUT_PREFIX = "qmt_roll_stage815_stage813_top40_loss_kline_atlas"
LINE_ID = "futures_trend_2019_data_extension"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")
TOP_N = 40
PER_PAGE = 4
PRE_BARS = 50
POST_BARS = 50
MA_LINES = (
    (5, "#f59e0b"),
    (10, "#2563eb"),
    (20, "#7c3aed"),
    (40, "#111827"),
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
TOP_LOSSES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top40_losses_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_page{{page:02d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


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


def _read_tushare_early_bars(vt_symbol: Any) -> pd.DataFrame:
    text = str(vt_symbol or "")
    if "." not in text:
        return pd.DataFrame()
    contract_symbol, exchange = text.split(".", 1)
    exchange_dir = TUSHARE_EARLY_ROOT / exchange
    if not exchange_dir.exists():
        return pd.DataFrame()
    candidates: list[Path] = []
    for name in {contract_symbol, contract_symbol.lower(), contract_symbol.upper()}:
        candidates.extend(exchange_dir.glob(f"{name}__*.csv"))
        candidates.append(exchange_dir / f"{name}.csv")
    path = next((item for item in candidates if item.exists()), None)
    if path is None:
        return pd.DataFrame()

    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame.rename(columns={"vol": "volume", "oi": "close_oi"}, inplace=True)
    for column in ["open", "high", "low", "close", "volume", "close_oi"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame.dropna(subset=["date", "open", "high", "low", "close"])
        .drop_duplicates("date")
        .sort_values("date")
        .reset_index(drop=True)
    )


def _read_plot_bars(vt_symbol: Any) -> tuple[pd.DataFrame, str]:
    bars, source = s798._read_plot_bars(vt_symbol)
    if not bars.empty:
        return bars, source
    early = _read_tushare_early_bars(vt_symbol)
    if not early.empty:
        return early, "tushare_early_daily"
    return pd.DataFrame(), "missing"


def _profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s813._profile(metadata, START, enabled=True)
    spec = profile["spec"]
    official_overrides = stage813_cfg.build_official_candidate_stage813_overrides()
    capital = replace(
        spec.capital,
        variant="stage815_stage813_official_candidate_full_2018",
        label="Stage815 Stage813 official candidate full 2018",
        note=(
            f"{spec.capital.note} | Stage815 full-period top-loss K-line atlas. "
            f"source={stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_VERSION}."
        ),
    )
    profile = dict(profile)
    profile["profile"] = "stage815_stage813_official_candidate_full"
    profile["spec"] = replace(
        spec,
        capital=capital,
        overrides={**spec.overrides, **official_overrides},
        profile=profile["profile"],
    )
    profile["note"] = "Stage813 official candidate full-period replay for top-loss K-line atlas."
    return profile


def _run_full() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    metadata = s513._metadata()
    profile = _profile(metadata)
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    combined, frames = s778._run_profile(
        profile=profile,
        start=START,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve = s804._metric_from_combined(profile, combined, START)
    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    closed = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    if closed.empty:
        raise RuntimeError("Stage813 closed lots are empty")
    enriched = s757._add_lot_features(closed, trades, entry_risk)
    for column in ["entry_date", "exit_date"]:
        enriched[column] = pd.to_datetime(enriched[column], errors="coerce").dt.normalize()
    enriched = enriched[
        enriched["entry_date"].ge(START.normalize())
        & enriched["exit_date"].le(END.normalize())
    ].copy()
    return summary, curve, frames, enriched


def _holding_bar_count(row: pd.Series) -> int:
    bars, _source = _read_plot_bars(row["vt_symbol"])
    if bars.empty:
        return 0
    entry_idx = s752._event_index(bars, pd.Timestamp(row["entry_date"]))
    exit_idx = s752._event_index(bars, pd.Timestamp(row["exit_date"]))
    return max(0, exit_idx - entry_idx + 1)


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


def _plot_page(page_rows: pd.DataFrame, page: int, total_pages: int) -> tuple[Path, list[dict[str, Any]]]:
    chart_records: list[dict[str, Any]] = []
    row_count = max(len(page_rows), 1)
    fig = plt.figure(figsize=(19, 4.9 * row_count), constrained_layout=True)
    outer = fig.add_gridspec(row_count, 1)
    for idx, (_, row) in enumerate(page_rows.iterrows()):
        inner = outer[idx].subgridspec(2, 1, height_ratios=[3.2, 1.0], hspace=0.02)
        price_ax = fig.add_subplot(inner[0])
        volume_ax = fig.add_subplot(inner[1], sharex=price_ax)
        bars, bar_source = _read_plot_bars(row["vt_symbol"])
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
                    "bar_source": bar_source,
                    "chart_page": page,
                }
            )
            continue
        chart_record = _plot_one(price_ax, volume_ax, row, bars)
        chart_record["missing_bars"] = 0
        chart_record["bar_source"] = bar_source
        chart_record["chart_page"] = page
        chart_records.append(chart_record)

    fig.suptitle(
        (
            f"Stage813 official candidate top {TOP_N} theoretical loss trades "
            f"(page {page}/{total_pages}, sorted by loss pct, MA5/10/20/40, pre50/post50)"
        ),
        fontsize=15,
    )
    chart_path = Path(str(CHART_PATH_TEMPLATE).format(page=page))
    fig.savefig(chart_path, dpi=170)
    plt.close(fig)
    return chart_path, chart_records


def _plot_pages(top: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    total_pages = int(math.ceil(len(top) / PER_PAGE)) if len(top) else 1
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        page_rows = top.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        chart_path, chart_records = _plot_page(page_rows, page, total_pages)
        paths.append(chart_path)
        records.extend(chart_records)
    return paths, pd.DataFrame(records)


def _write_report(
    summary: pd.DataFrame,
    closed: pd.DataFrame,
    top: pd.DataFrame,
    chart_paths: list[Path],
    chart_records: pd.DataFrame,
) -> None:
    row = summary.iloc[0].to_dict()
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
        "chart_page",
        "bar_source",
    ]
    lines = [
        "# Stage815 Stage813亏损比例Top40 K线图谱",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源版本：`{stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 排序指标：`theory_loss_pct = -directional(entry->exit return pct)`，即按开平仓价的方向性亏损比例排序。",
        "- 图形：每笔开仓前50根、平仓后50根；蓝色入场、紫色出场、红色背景为持仓亏损段；下方面板为成交量和OI。",
        "",
        "## Full-Period Result",
        "",
        _md_table(
            pd.DataFrame(
                [
                    {
                        "end_equity": row.get("end_equity"),
                        "total_return_pct": row.get("total_return_pct"),
                        "max_dd_pct": row.get("max_dd_pct"),
                        "sharpe": row.get("sharpe"),
                        "total_slippage": row.get("total_slippage"),
                        "total_trade_count": row.get("total_trade_count"),
                        "win_rate_pct": row.get("nonzero_daily_win_rate_pct"),
                    }
                ]
            ),
            max_rows=5,
        ),
        "",
        "## Top40 Summary",
        "",
        _md_table(
            pd.DataFrame(
                [
                    {
                        "closed_lots": len(closed),
                        "loser_lots": int(pd.to_numeric(closed["theory_return_pct"], errors="coerce").lt(0).sum()),
                        "top_n": len(top),
                        "worst_theory_loss_pct": float(top["theory_loss_pct"].max()) if len(top) else np.nan,
                        "rank40_theory_loss_pct": float(top["theory_loss_pct"].iloc[-1]) if len(top) else np.nan,
                        "top40_realized_pnl": float(pd.to_numeric(top["realized_pnl"], errors="coerce").sum()) if len(top) else 0.0,
                        "oi_hit_count": int(
                            pd.to_numeric(top["oi_price_confirm_risk_restore_applied"], errors="coerce")
                            .fillna(0)
                            .eq(1)
                            .sum()
                        )
                        if len(top)
                        else 0,
                        "missing_bar_lots": int(chart_records["missing_bars"].sum()) if len(chart_records) else 0,
                        "minute_aggregated_lots": int(chart_records["bar_source"].eq("minute_aggregated").sum())
                        if len(chart_records) and "bar_source" in chart_records
                        else 0,
                        "tushare_early_daily_lots": int(chart_records["bar_source"].eq("tushare_early_daily").sum())
                        if len(chart_records) and "bar_source" in chart_records
                        else 0,
                    }
                ]
            ),
            max_rows=5,
        ),
        "",
        "## Top40 Trades",
        "",
        _md_table(top[[column for column in display_cols if column in top.columns]], max_rows=50),
        "",
        "## Charts",
        "",
        *[f"- `{path}`" for path in chart_paths],
        "",
        "## Judgment",
        "",
        "- 本阶段只读复盘，不新增交易规则，不修改策略参数。",
        "- 过拟合判断：本次画图本身不过拟合；如果后续从这40笔直接反推过滤条件，会有高过拟合风险。",
        "- 继续价值判断：有价值。它能帮助识别 Stage813 的左尾是否集中在 OI放大、趋势末端假突破、短周期急反或特定退出类型上。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, curve, frames, closed = _run_full()
    top = _select_top_losses(closed)
    chart_paths, chart_records = _plot_pages(top)
    top_with_chart = top.merge(chart_records, on="lot_id", how="left")

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    frames.get("trades", pd.DataFrame()).to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    frames.get("entry_risk", pd.DataFrame()).to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    frames.get("entry_candidates", pd.DataFrame()).to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    frames.get("trade_events", pd.DataFrame()).to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    closed.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    top_with_chart.to_csv(TOP_LOSSES_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, closed, top_with_chart, chart_paths, chart_records)

    summary_row = summary.iloc[0].to_dict()
    decision = {
        "stage": "Stage815",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "task": "Stage813 official candidate full-period top 40 theoretical loss K-line atlas",
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "source_version": stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_VERSION,
        "start": START.date().isoformat(),
        "end": END.date().isoformat(),
        "ranking_metric": "theory_loss_pct = -directional(entry->exit return pct)",
        "full_period_result": {
            "end_equity": summary_row.get("end_equity"),
            "total_return_pct": summary_row.get("total_return_pct"),
            "max_dd_pct": summary_row.get("max_dd_pct"),
            "sharpe": summary_row.get("sharpe"),
            "total_slippage": summary_row.get("total_slippage"),
            "total_trade_count": summary_row.get("total_trade_count"),
            "win_rate_pct": summary_row.get("nonzero_daily_win_rate_pct"),
        },
        "top40_summary": {
            "closed_lots": int(len(closed)),
            "loser_lots": int(pd.to_numeric(closed["theory_return_pct"], errors="coerce").lt(0).sum()),
            "top_n": int(len(top_with_chart)),
            "worst_theory_loss_pct": float(top_with_chart["theory_loss_pct"].max()) if len(top_with_chart) else np.nan,
            "rank40_theory_loss_pct": float(top_with_chart["theory_loss_pct"].iloc[-1]) if len(top_with_chart) else np.nan,
            "top40_realized_pnl": float(pd.to_numeric(top_with_chart["realized_pnl"], errors="coerce").sum())
            if len(top_with_chart)
            else 0.0,
            "oi_hit_count": int(
                pd.to_numeric(top_with_chart["oi_price_confirm_risk_restore_applied"], errors="coerce")
                .fillna(0)
                .eq(1)
                .sum()
            )
            if len(top_with_chart)
            else 0,
            "missing_bar_lots": int(chart_records["missing_bars"].sum()) if len(chart_records) else 0,
            "minute_aggregated_lots": int(chart_records["bar_source"].eq("minute_aggregated").sum())
            if len(chart_records) and "bar_source" in chart_records
            else 0,
            "tushare_early_daily_lots": int(chart_records["bar_source"].eq("tushare_early_daily").sum())
            if len(chart_records) and "bar_source" in chart_records
            else 0,
        },
        "overfit_reflection": (
            "Low for chart generation because no strategy rule or parameter is changed. "
            "High only if thresholds are inferred from these 40 examples without predeclared multi-start validation."
        ),
        "continue_value": (
            "Yes as visual forensics for Stage813 left-tail structure; no RSI/OI/shape threshold tuning from charts alone."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curve": str(CURVE_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "top_losses": str(TOP_LOSSES_PATH),
            "report": str(REPORT_PATH),
            "charts": [str(path) for path in chart_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
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
        "chart_page",
        "bar_source",
    ]
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(top_with_chart[[column for column in display_cols if column in top_with_chart.columns]].to_string(index=False))
    for path in chart_paths:
        print(f"chart={path}")


if __name__ == "__main__":
    main()
