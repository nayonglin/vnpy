from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage733_shadowless_preentry_quality as s733
import analyze_qmt_roll_stage736_postentry_smooth_kline_addon_proxy as s736


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage737_postentry_addon_overlay_equity_v1"
OUTPUT_PREFIX = "qmt_roll_stage737_postentry_addon_overlay_equity"
LINE_ID = "futures_trend_winner_trade_forensics"

OFFICIAL_POSITIONS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage719_official_winner_trade_forensics_positions_stage719_official_winner_trade_forensics_v1.csv"
)
SOURCE_ADDON_LOTS_PATH = s736.ADDON_LOTS_PATH
SOURCE_ADDON_METRICS_PATH = s736.ADDON_METRICS_PATH

DAILY_EQUITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_equity_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

INITIAL_CAPITAL = 200_000.0


def _load_official_daily() -> pd.DataFrame:
    if not OFFICIAL_POSITIONS_PATH.exists():
        raise FileNotFoundError(OFFICIAL_POSITIONS_PATH)
    positions = pd.read_csv(OFFICIAL_POSITIONS_PATH, encoding="utf-8-sig")
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
    positions["net_pnl"] = pd.to_numeric(positions["net_pnl"], errors="coerce").fillna(0.0)
    daily = positions.groupby("date", as_index=False).agg(official_net_pnl=("net_pnl", "sum"))
    daily = daily[daily["date"] >= pd.Timestamp("2020-01-01")].sort_values("date").reset_index(drop=True)
    daily["official_equity"] = INITIAL_CAPITAL + daily["official_net_pnl"].cumsum()
    return daily


def _load_sources() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SOURCE_ADDON_LOTS_PATH.exists() or not SOURCE_ADDON_METRICS_PATH.exists():
        s736.main()
    lots = pd.read_csv(SOURCE_ADDON_LOTS_PATH, encoding="utf-8-sig")
    metrics = pd.read_csv(SOURCE_ADDON_METRICS_PATH, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date", "addon_observation_date"]:
        lots[column] = pd.to_datetime(lots[column], errors="coerce").dt.normalize()
    for column in ["volume", "size", "exit_price", "post1_close", "post2_close", "post3_close", "post5_close"]:
        if column in lots.columns:
            lots[column] = pd.to_numeric(lots[column], errors="coerce")
    return lots, metrics


def _addon_daily_increments(lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    bar_cache: dict[str, pd.DataFrame] = {}
    for row in lots.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        bars = bar_cache.get(vt_symbol)
        if bars is None:
            bars = s733._load_contract_bars(vt_symbol)
            bar_cache[vt_symbol] = bars
        if bars.empty or pd.isna(row.addon_observation_date) or pd.isna(row.exit_date):
            continue
        window = int(row.addon_window)
        obs_close_col = f"post{window}_close"
        obs_close = float(getattr(row, obs_close_col))
        exit_price = float(row.exit_price)
        direction = str(row.direction)
        sign = 1.0 if direction == "long" else -1.0 if direction == "short" else 0.0
        units = float(row.volume) * float(row.size) * float(row.addon_risk_fraction)
        obs_date = pd.Timestamp(row.addon_observation_date).normalize()
        exit_date = pd.Timestamp(row.exit_date).normalize()
        if units <= 0.0 or sign == 0.0 or exit_date <= obs_date:
            continue
        path = bars[(bars["date"] > obs_date) & (bars["date"] < exit_date)].copy()
        previous_cum = 0.0
        for bar in path.itertuples(index=False):
            cumulative = sign * (float(bar.close_price) - obs_close) * units
            rows.append(
                {
                    "feature": row.addon_feature,
                    "date": pd.Timestamp(bar.date).normalize(),
                    "lot_id": row.lot_id,
                    "addon_daily_pnl": cumulative - previous_cum,
                }
            )
            previous_cum = cumulative
        final_cum = sign * (exit_price - obs_close) * units
        rows.append(
            {
                "feature": row.addon_feature,
                "date": exit_date,
                "lot_id": row.lot_id,
                "addon_daily_pnl": final_cum - previous_cum,
            }
        )
    return pd.DataFrame(rows)


def _max_drawdown_pct(equity: pd.Series) -> float:
    high = equity.cummax()
    drawdown = equity / high - 1.0
    return float(drawdown.min() * 100.0)


def _sharpe(equity: pd.Series) -> float:
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or returns.std(ddof=0) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(252.0))


def _build_overlay(daily: pd.DataFrame, addon_increments: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    official = daily[["date", "official_equity", "official_net_pnl"]].copy()
    all_frames = []
    summary_rows: list[dict[str, Any]] = [
        {
            "feature": "official",
            "rows": 0,
            "total_addon_pnl": 0.0,
            "end_equity": float(official["official_equity"].iloc[-1]),
            "total_return_pct": float((official["official_equity"].iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0),
            "max_drawdown_pct": _max_drawdown_pct(official["official_equity"]),
            "sharpe": _sharpe(official["official_equity"]),
            "max_drawdown_delta_pp": 0.0,
            "end_equity_delta": 0.0,
        }
    ]
    official_dd = summary_rows[0]["max_drawdown_pct"]
    official_end = summary_rows[0]["end_equity"]
    for feature, group in addon_increments.groupby("feature"):
        addon_daily = group.groupby("date", as_index=False).agg(addon_daily_pnl=("addon_daily_pnl", "sum"))
        merged = official.merge(addon_daily, on="date", how="left")
        merged["addon_daily_pnl"] = merged["addon_daily_pnl"].fillna(0.0)
        merged["addon_cum_pnl"] = merged["addon_daily_pnl"].cumsum()
        merged["overlay_equity"] = merged["official_equity"] + merged["addon_cum_pnl"]
        merged["feature"] = feature
        all_frames.append(merged)
        end_equity = float(merged["overlay_equity"].iloc[-1])
        max_dd = _max_drawdown_pct(merged["overlay_equity"])
        summary_rows.append(
            {
                "feature": feature,
                "rows": int(group["lot_id"].nunique()),
                "total_addon_pnl": float(merged["addon_cum_pnl"].iloc[-1]),
                "end_equity": end_equity,
                "total_return_pct": float((end_equity / INITIAL_CAPITAL - 1.0) * 100.0),
                "max_drawdown_pct": max_dd,
                "sharpe": _sharpe(merged["overlay_equity"]),
                "max_drawdown_delta_pp": max_dd - official_dd,
                "end_equity_delta": end_equity - official_end,
            }
        )
    overlay_daily = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows).sort_values(
        ["feature"], key=lambda s: s.ne("official").astype(int), ascending=True
    )
    if not summary.empty:
        summary = summary.sort_values(["feature", "end_equity_delta"], ascending=[True, False])
        official_row = summary[summary["feature"] == "official"]
        other = summary[summary["feature"] != "official"].sort_values("end_equity_delta", ascending=False)
        summary = pd.concat([official_row, other], ignore_index=True)
    return overlay_daily, summary


def _plot_overlay(overlay_daily: pd.DataFrame, summary: pd.DataFrame, official: pd.DataFrame) -> None:
    plt.figure(figsize=(14, 8))
    plt.plot(official["date"], official["official_equity"], label="official", linewidth=2.0, color="#333333")
    for feature in summary[summary["feature"] != "official"]["feature"].head(5):
        data = overlay_daily[overlay_daily["feature"] == feature]
        plt.plot(data["date"], data["overlay_equity"], label=feature, linewidth=1.3)
    plt.title("Stage737 official equity + post-entry 0.5x add-on overlay proxy")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.grid(alpha=0.25)
    plt.legend(loc="upper left", fontsize=8)
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=160)
    plt.close()


def _build_report(summary: pd.DataFrame) -> str:
    cols = [
        "feature",
        "rows",
        "total_addon_pnl",
        "end_equity",
        "end_equity_delta",
        "total_return_pct",
        "max_drawdown_pct",
        "max_drawdown_delta_pp",
        "sharpe",
    ]
    candidates = summary[
        (summary["feature"] != "official")
        & (summary["end_equity_delta"] > 0.0)
        & (summary["max_drawdown_delta_pp"] >= -5.0)
    ].copy()
    lines = [
        "# Stage737 入场后确认仓 Overlay 权益代理",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        f"- 研究线：`{LINE_ID}`",
        "- 口径：正式 Stage719 日级权益 + Stage736 0.5x 确认仓每日增量 PnL。",
        "- 注意：这是 overlay 代理，不处理真实保证金、整数手、maxpos、强制减仓、排队和额外滑点。",
        "",
        "## Summary",
        "",
        s733._md_table(summary[cols]),
        "",
        "## 候选",
        "",
        s733._md_table(candidates[cols]),
        "",
        "## 结论",
        "",
    ]
    if candidates.empty:
        lines.append("- 没有 overlay 候选同时增加权益且回撤不显著恶化，不进入真实 A/C。")
    else:
        lines.extend(
            [
                f"- 有 {len(candidates)} 个 overlay 候选值得进一步真实 A/C 设计。",
                "- 但真实策略实现前必须处理加仓仓位与组合保证金/并发/强制减仓的交互。",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    official = _load_official_daily()
    addon_lots, _ = _load_sources()
    addon_increments = _addon_daily_increments(addon_lots)
    overlay_daily, summary = _build_overlay(official, addon_increments)
    _plot_overlay(overlay_daily, summary, official)

    overlay_daily.to_csv(DAILY_EQUITY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(summary), encoding="utf-8")
    candidates = summary[
        (summary["feature"] != "official")
        & (summary["end_equity_delta"] > 0.0)
        & (summary["max_drawdown_delta_pp"] >= -5.0)
    ].copy()
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "initial_capital": INITIAL_CAPITAL,
        "official_end_equity": float(summary.loc[summary["feature"] == "official", "end_equity"].iloc[0]),
        "candidate_count": int(len(candidates)),
        "best_feature": str(candidates.iloc[0]["feature"]) if not candidates.empty else None,
        "best_end_equity_delta": float(candidates.iloc[0]["end_equity_delta"]) if not candidates.empty else 0.0,
        "best_max_drawdown_delta_pp": float(candidates.iloc[0]["max_drawdown_delta_pp"]) if not candidates.empty else 0.0,
        "decision": (
            "postentry_addon_overlay_promising_needs_real_strategy_ac"
            if not candidates.empty
            else "postentry_addon_overlay_not_promoted"
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(s733._json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(s733._json_safe(decision), ensure_ascii=False, indent=2))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
