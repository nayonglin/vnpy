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
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage828"
MODEL_TAG = "stage828_stage827_c2_drawdown_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage828_stage827_c2_drawdown_forensics"

STAGE827_TAG = "stage827_stage819_intraday_c2_engine_ac_v1"
STAGE827_PREFIX = "qmt_roll_stage827_stage819_intraday_c2_engine_ac"
BASE_ARM = "stage827_stage819_baseline"
C2_ARM = "stage827_stage819_c2_engine"

CURVE_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_curve_{STAGE827_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_trades_{STAGE827_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_closed_lots_{STAGE827_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_entry_risk_{STAGE827_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_entry_candidates_{STAGE827_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_intraday_events_{STAGE827_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DAILY_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_delta_{MODEL_TAG}.csv"
WINDOW_LOT_DIFF_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_lot_diff_{MODEL_TAG}.csv"
WINDOW_PRODUCT_ATTR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_product_attr_{MODEL_TAG}.csv"
C2_EVENT_IMPACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c2_event_impact_{MODEL_TAG}.csv"
EXPOSURE_DIFF_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exposure_diff_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
PATH_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
EVENT_ATLAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_2022_event_atlas_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s825._safe_float(value, default=default)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required Stage827 output: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _prepare() -> dict[str, pd.DataFrame]:
    curve = _load_csv(CURVE_PATH)
    trades = _load_csv(TRADES_PATH)
    lots = _load_csv(CLOSED_LOTS_PATH)
    entry_risk = _load_csv(ENTRY_RISK_PATH)
    entry_candidates = _load_csv(ENTRY_CANDIDATES_PATH)
    intraday = _load_csv(INTRADAY_EVENTS_PATH)

    for frame in [curve, trades, lots, entry_risk, entry_candidates, intraday]:
        for column in ["date", "entry_date", "exit_date", "datetime", "hit_time"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")

    return {
        "curve": curve,
        "trades": trades,
        "lots": lots,
        "entry_risk": entry_risk,
        "entry_candidates": entry_candidates,
        "intraday": intraday,
    }


def _drawdown_window(curve: pd.DataFrame) -> dict[str, Any]:
    c2 = curve[curve["arm"].eq(C2_ARM)].sort_values("date").copy()
    c2["account_equity"] = pd.to_numeric(c2["account_equity"], errors="coerce")
    c2["drawdown_pct"] = pd.to_numeric(c2["drawdown_pct"], errors="coerce")
    trough_idx = c2["drawdown_pct"].idxmin()
    trough = c2.loc[trough_idx]
    before = c2.loc[:trough_idx].copy()
    peak_idx = before["account_equity"].idxmax()
    peak = c2.loc[peak_idx]
    start = pd.Timestamp(peak["date"]).normalize()
    trough_date = pd.Timestamp(trough["date"]).normalize()
    context_start = max(c2["date"].min().normalize(), start - pd.Timedelta(days=60))
    context_end = min(c2["date"].max().normalize(), trough_date + pd.Timedelta(days=30))
    return {
        "peak_date": start,
        "peak_equity": float(peak["account_equity"]),
        "trough_date": trough_date,
        "trough_equity": float(trough["account_equity"]),
        "trough_drawdown_pct": float(trough["drawdown_pct"]),
        "context_start": context_start,
        "context_end": context_end,
    }


def _daily_delta(curve: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "account_equity",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "net_pnl",
        "trade_count",
        "total_slippage",
    ]
    base = curve[curve["arm"].eq(BASE_ARM)][columns].copy()
    c2 = curve[curve["arm"].eq(C2_ARM)][columns].copy()
    merged = base.merge(c2, on="date", suffixes=("_A", "_C"), how="outer").sort_values("date")
    for column in columns[1:]:
        merged[f"{column}_delta_C_minus_A"] = (
            pd.to_numeric(merged[f"{column}_C"], errors="coerce").fillna(0.0)
            - pd.to_numeric(merged[f"{column}_A"], errors="coerce").fillna(0.0)
        )
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce").dt.normalize()
    return merged


def _open_key_frame(lots: pd.DataFrame) -> pd.DataFrame:
    data = lots.copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    for column in ["entry_price", "exit_price", "volume", "realized_pnl", "risk_amount", "r_multiple"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data["open_key"] = (
        data["entry_date"].dt.strftime("%Y-%m-%d").fillna("")
        + "|"
        + data["vt_symbol"].astype(str)
        + "|"
        + data["direction"].astype(str)
        + "|"
        + data["signal"].astype(str)
        + "|"
        + data["entry_context"].astype(str)
        + "|"
        + data["layer_kind"].astype(str)
    )
    return data


def _window_lot_diff(lots: pd.DataFrame, window: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = _open_key_frame(lots)
    start = pd.Timestamp(window["peak_date"])
    trough = pd.Timestamp(window["trough_date"])
    overlap = data[data["entry_date"].le(trough) & data["exit_date"].ge(start)].copy()
    agg_cols = {
        "entry_date": "min",
        "exit_date": "max",
        "vt_symbol": "first",
        "product": "first",
        "direction": "first",
        "signal": "first",
        "entry_context": "first",
        "layer_kind": "first",
        "volume": "sum",
        "realized_pnl": "sum",
        "risk_amount": "sum",
        "r_multiple": "sum",
        "exit_reason": lambda series: ";".join(sorted(set(series.dropna().astype(str)))),
    }
    a = (
        overlap[overlap["arm"].eq(BASE_ARM)]
        .groupby("open_key", dropna=False)
        .agg(agg_cols)
        .reset_index()
        .add_prefix("A_")
        .rename(columns={"A_open_key": "open_key"})
    )
    c = (
        overlap[overlap["arm"].eq(C2_ARM)]
        .groupby("open_key", dropna=False)
        .agg(agg_cols)
        .reset_index()
        .add_prefix("C_")
        .rename(columns={"C_open_key": "open_key"})
    )
    merged = a.merge(c, on="open_key", how="outer")
    for column in ["volume", "realized_pnl", "risk_amount", "r_multiple"]:
        merged[f"{column}_delta_C_minus_A"] = (
            pd.to_numeric(merged.get(f"C_{column}"), errors="coerce").fillna(0.0)
            - pd.to_numeric(merged.get(f"A_{column}"), errors="coerce").fillna(0.0)
        )
    merged["presence"] = np.select(
        [
            merged["A_vt_symbol"].notna() & merged["C_vt_symbol"].notna(),
            merged["A_vt_symbol"].isna() & merged["C_vt_symbol"].notna(),
            merged["A_vt_symbol"].notna() & merged["C_vt_symbol"].isna(),
        ],
        ["both", "C_only", "A_only"],
        default="unknown",
    )
    merged["abs_pnl_delta"] = merged["realized_pnl_delta_C_minus_A"].abs()
    merged.sort_values(["abs_pnl_delta", "open_key"], ascending=[False, True], inplace=True)

    product_rows: list[dict[str, Any]] = []
    product_col = merged["C_product"].combine_first(merged["A_product"])
    direction_col = merged["C_direction"].combine_first(merged["A_direction"])
    for (product, direction), group in merged.groupby([product_col, direction_col], dropna=False):
        product_rows.append(
            {
                "product": product,
                "direction": direction,
                "rows": int(len(group)),
                "C_only": int(group["presence"].eq("C_only").sum()),
                "A_only": int(group["presence"].eq("A_only").sum()),
                "both": int(group["presence"].eq("both").sum()),
                "realized_pnl_delta_C_minus_A": float(group["realized_pnl_delta_C_minus_A"].sum()),
                "risk_amount_delta_C_minus_A": float(group["risk_amount_delta_C_minus_A"].sum()),
                "volume_delta_C_minus_A": float(group["volume_delta_C_minus_A"].sum()),
            }
        )
    product_attr = pd.DataFrame(product_rows).sort_values(
        "realized_pnl_delta_C_minus_A",
        ascending=True,
    )

    exposure_rows: list[dict[str, Any]] = []
    for presence, group in merged.groupby("presence"):
        exposure_rows.append(
            {
                "presence": presence,
                "rows": int(len(group)),
                "realized_pnl_delta_C_minus_A": float(group["realized_pnl_delta_C_minus_A"].sum()),
                "risk_amount_delta_C_minus_A": float(group["risk_amount_delta_C_minus_A"].sum()),
                "volume_delta_C_minus_A": float(group["volume_delta_C_minus_A"].sum()),
            }
        )
    exposure = pd.DataFrame(exposure_rows).sort_values("presence")
    return merged, product_attr, exposure


def _event_impact(lots: pd.DataFrame, intraday: pd.DataFrame) -> pd.DataFrame:
    data = _open_key_frame(lots)
    c2_lots = data[data["arm"].eq(C2_ARM)].copy()
    base_lots = data[data["arm"].eq(BASE_ARM)].copy()
    base_by_open = (
        base_lots.groupby("open_key", dropna=False)
        .agg(
            A_exit_date=("exit_date", "max"),
            A_realized_pnl=("realized_pnl", "sum"),
            A_r_multiple=("r_multiple", "sum"),
            A_exit_reason=("exit_reason", lambda s: ";".join(sorted(set(s.dropna().astype(str))))),
        )
        .reset_index()
    )
    c2_by_trade = c2_lots.set_index("open_trade_id", drop=False)
    rows: list[dict[str, Any]] = []
    events = intraday.copy()
    events["datetime"] = pd.to_datetime(events["datetime"], errors="coerce")
    events["hit_time"] = pd.to_datetime(events["hit_time"], errors="coerce")
    for event in events.to_dict("records"):
        trade_id = str(event.get("trade_id", ""))
        lot = c2_by_trade.loc[trade_id] if trade_id in c2_by_trade.index else None
        if isinstance(lot, pd.DataFrame):
            lot = lot.iloc[0]
        if lot is None:
            rows.append({**event, "match_status": "missing_c2_lot"})
            continue
        base = base_by_open[base_by_open["open_key"].eq(lot["open_key"])]
        base_row = base.iloc[0].to_dict() if not base.empty else {}
        c_pnl = _safe_float(lot.get("realized_pnl"), 0.0)
        a_pnl = _safe_float(base_row.get("A_realized_pnl"), np.nan)
        rows.append(
            {
                "event_date": pd.Timestamp(event["datetime"]).strftime("%Y-%m-%d") if pd.notna(event.get("datetime")) else "",
                "hit_time": pd.Timestamp(event["hit_time"]).strftime("%Y-%m-%d %H:%M") if pd.notna(event.get("hit_time")) else "",
                "trade_id": trade_id,
                "vt_symbol": event.get("vt_symbol"),
                "product": lot.get("product"),
                "direction": event.get("direction"),
                "entry_price": event.get("entry_price"),
                "stop_price": event.get("stop_price"),
                "confirm_price": event.get("confirm_price"),
                "volume": event.get("volume"),
                "C_exit_date": pd.Timestamp(lot.get("exit_date")).strftime("%Y-%m-%d") if pd.notna(lot.get("exit_date")) else "",
                "C_realized_pnl": c_pnl,
                "C_exit_reason": lot.get("exit_reason"),
                "A_exit_date": pd.Timestamp(base_row.get("A_exit_date")).strftime("%Y-%m-%d") if base_row else "",
                "A_realized_pnl": a_pnl,
                "A_exit_reason": base_row.get("A_exit_reason", ""),
                "direct_pnl_delta_C_minus_A": c_pnl - a_pnl if np.isfinite(a_pnl) else np.nan,
                "match_status": "matched_open_key" if base_row else "C_only_open_key",
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result["event_year"] = pd.to_datetime(result["event_date"], errors="coerce").dt.year
        result.sort_values(["event_date", "vt_symbol"], inplace=True)
    return result


def _plot_path(delta: pd.DataFrame, window: dict[str, Any]) -> None:
    start = pd.Timestamp(window["context_start"])
    end = pd.Timestamp(window["context_end"])
    data = delta[delta["date"].between(start, end)].copy()
    if data.empty:
        return
    fig, axes = plt.subplots(4, 1, figsize=(18, 13), sharex=True, constrained_layout=True)
    x = pd.to_datetime(data["date"])
    axes[0].plot(x, data["account_equity_A"], label="A baseline", color="#2563eb", linewidth=1.2)
    axes[0].plot(x, data["account_equity_C"], label="C2 engine", color="#dc2626", linewidth=1.2)
    axes[0].axvline(window["peak_date"], color="#475569", linestyle="--", linewidth=0.9)
    axes[0].axvline(window["trough_date"], color="#111827", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage828 C2 drawdown path: equity")
    axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.22)

    axes[1].plot(x, data["drawdown_pct_A"], label="A drawdown", color="#2563eb", linewidth=1.1)
    axes[1].plot(x, data["drawdown_pct_C"], label="C2 drawdown", color="#dc2626", linewidth=1.1)
    axes[1].set_title("Drawdown")
    axes[1].grid(True, alpha=0.22)

    colors = np.where(data["net_pnl_delta_C_minus_A"].to_numpy() >= 0, "#16a34a", "#b91c1c")
    axes[2].bar(x, data["net_pnl_delta_C_minus_A"], color=colors, width=0.8)
    axes[2].set_title("Daily net pnl delta: C2 - A")
    axes[2].grid(True, alpha=0.22)

    axes[3].plot(x, data["broker10_margin_to_equity_pct_A"], label="A margin/equity", color="#2563eb", linewidth=1.1)
    axes[3].plot(x, data["broker10_margin_to_equity_pct_C"], label="C2 margin/equity", color="#dc2626", linewidth=1.1)
    axes[3].set_title("Broker10 margin to equity pct")
    axes[3].grid(True, alpha=0.22)
    axes[3].legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _direction_sign(direction: str) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _plot_candles(ax: plt.Axes, bars: pd.DataFrame) -> None:
    width = 0.64
    for idx, row in enumerate(bars.itertuples(index=False)):
        open_price = float(row.open)
        high_price = float(row.high)
        low_price = float(row.low)
        close_price = float(row.close)
        color = "#dc2626" if close_price >= open_price else "#059669"
        ax.vlines(idx, low_price, high_price, color=color, linewidth=0.7, alpha=0.9)
        lower = min(open_price, close_price)
        height = abs(close_price - open_price)
        if height <= 0:
            height = max(high_price - low_price, 1.0) * 0.006
            lower -= height / 2.0
        ax.add_patch(
            plt.Rectangle(
                (idx - width / 2.0, lower),
                width,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.35,
                alpha=0.75,
            )
        )


def _plot_event_atlas(events: pd.DataFrame) -> None:
    events_2022 = events[pd.to_datetime(events["event_date"], errors="coerce").dt.year.eq(2022)].copy()
    if events_2022.empty:
        return
    vt_symbols = set(events_2022["vt_symbol"].dropna().astype(str))
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    max_rows = min(8, len(events_2022))
    part = events_2022.head(max_rows).copy().reset_index(drop=True)
    fig, axes = plt.subplots(max_rows, 1, figsize=(18, max(4.0, 3.0 * max_rows)), constrained_layout=True)
    if max_rows == 1:
        axes = [axes]
    for ax, row in zip(axes, part.to_dict("records"), strict=False):
        vt_symbol = str(row["vt_symbol"])
        event_date = pd.Timestamp(row["event_date"]).normalize()
        bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        entry_day = bars[bars["bar_date"].eq(event_date)].copy().reset_index(drop=True) if not bars.empty else pd.DataFrame()
        if entry_day.empty:
            ax.axis("off")
            ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {event_date:%Y-%m-%d}", ha="center", va="center")
            continue
        window = entry_day.head(240).copy().reset_index(drop=True)
        _plot_candles(ax, window)
        ax.plot(np.arange(len(window)), window["close"].rolling(5).mean(), color="#f59e0b", linewidth=0.8)
        ax.plot(np.arange(len(window)), window["close"].rolling(20).mean(), color="#2563eb", linewidth=0.8)
        entry_price = _safe_float(row.get("entry_price"))
        stop_price = _safe_float(row.get("stop_price"))
        confirm_price = _safe_float(row.get("confirm_price"))
        ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.85)
        ax.axhline(stop_price, color="#b91c1c", linewidth=0.95, alpha=0.85)
        ax.axhline(confirm_price, color="#15803d", linewidth=0.95, alpha=0.85)
        hit_time = pd.Timestamp(row["hit_time"]) if row.get("hit_time") else pd.NaT
        if pd.notna(hit_time):
            times = pd.to_datetime(window["bar_datetime"], errors="coerce")
            idx = int((times - hit_time).abs().idxmin())
            ax.axvline(idx, color="#b91c1c", linestyle="--", linewidth=0.9)
            ax.scatter([idx], [stop_price], color="#b91c1c", s=18, zorder=5)
        ticks = np.linspace(0, len(window) - 1, num=min(7, len(window)), dtype=int)
        ax.set_xticks(ticks)
        ax.set_xticklabels([pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(True, alpha=0.18)
        ax.set_title(
            (
                f"{vt_symbol} {row['direction']} {event_date:%Y-%m-%d} "
                f"C_pnl={_safe_float(row.get('C_realized_pnl')):,.0f} "
                f"A_pnl={_safe_float(row.get('A_realized_pnl')):,.0f} "
                f"delta={_safe_float(row.get('direct_pnl_delta_C_minus_A')):,.0f}"
            ),
            fontsize=8.5,
            loc="left",
        )
    fig.suptitle("Stage828 2022 C2 intraday stop event atlas", fontsize=13)
    fig.savefig(EVENT_ATLAS_PATH, dpi=150)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    daily_delta: pd.DataFrame,
    lot_diff: pd.DataFrame,
    product_attr: pd.DataFrame,
    exposure: pd.DataFrame,
    event_impact: pd.DataFrame,
    window: dict[str, Any],
) -> None:
    worst_days = daily_delta.sort_values("drawdown_pct_delta_C_minus_A").head(10)
    pnl_days = daily_delta.sort_values("net_pnl_delta_C_minus_A").head(15)
    events_2022 = event_impact[pd.to_datetime(event_impact["event_date"], errors="coerce").dt.year.eq(2022)].copy()
    direct_by_year = (
        event_impact.groupby("event_year", dropna=False)
        .agg(
            events=("trade_id", "size"),
            direct_pnl_delta_C_minus_A=("direct_pnl_delta_C_minus_A", "sum"),
            C_realized_pnl=("C_realized_pnl", "sum"),
            A_realized_pnl=("A_realized_pnl", "sum"),
        )
        .reset_index()
        if not event_impact.empty
        else pd.DataFrame()
    )
    lines = [
        "# Stage828 Stage827 C2回撤恶化归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读归因；不改策略、不调参数、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势/CTA资料普遍强调止损必须和仓位、波动、组合风险一起评估；单笔止损改善不等于组合回撤改善。",
        "- 本阶段借鉴的是 stop-loss/re-entry 分析框架：把直接止损收益和后续资金释放后的间接交易分开看。",
        "",
        "## Drawdown Window",
        "",
        _md_table(summary, max_rows=20),
        "",
        "## Worst C2-vs-A Drawdown Gap Days",
        "",
        _md_table(
            worst_days[
                [
                    "date",
                    "account_equity_A",
                    "account_equity_C",
                    "drawdown_pct_A",
                    "drawdown_pct_C",
                    "drawdown_pct_delta_C_minus_A",
                    "broker10_margin_to_equity_pct_A",
                    "broker10_margin_to_equity_pct_C",
                    "net_pnl_delta_C_minus_A",
                ]
            ],
            max_rows=10,
        ),
        "",
        "## Worst Daily PnL Delta Days",
        "",
        _md_table(
            pnl_days[
                [
                    "date",
                    "net_pnl_A",
                    "net_pnl_C",
                    "net_pnl_delta_C_minus_A",
                    "trade_count_A",
                    "trade_count_C",
                    "broker10_margin_to_equity_pct_A",
                    "broker10_margin_to_equity_pct_C",
                ]
            ],
            max_rows=15,
        ),
        "",
        "## C2 Event Direct Impact By Year",
        "",
        _md_table(direct_by_year, max_rows=20),
        "",
        "## 2022 C2 Events",
        "",
        _md_table(
            events_2022[
                [
                    "event_date",
                    "hit_time",
                    "vt_symbol",
                    "direction",
                    "volume",
                    "C_realized_pnl",
                    "A_realized_pnl",
                    "direct_pnl_delta_C_minus_A",
                    "C_exit_reason",
                    "A_exit_reason",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Drawdown Window Exposure Diff",
        "",
        _md_table(exposure, max_rows=10),
        "",
        "## Worst Product Contribution In Window",
        "",
        _md_table(product_attr.head(20), max_rows=20),
        "",
        "## Largest Lot Diffs In Window",
        "",
        _md_table(
            lot_diff[
                [
                    "open_key",
                    "presence",
                    "A_entry_date",
                    "C_entry_date",
                    "A_exit_date",
                    "C_exit_date",
                    "A_realized_pnl",
                    "C_realized_pnl",
                    "realized_pnl_delta_C_minus_A",
                    "A_exit_reason",
                    "C_exit_reason",
                ]
            ].head(30),
            max_rows=30,
        ),
        "",
        "## Charts",
        "",
        f"- path：`{PATH_CHART_PATH}`",
        f"- 2022 event atlas：`{EVENT_ATLAS_PATH}`",
        "",
        "## Judgment",
        "",
        "- Stage004 不支持把 C2 晋级为候选。C2 的直接止损事件多数改善单笔损益，但组合路径中释放资金带来的后续暴露使 2022 回撤更深。",
        "- 这说明日内止损必须配套账户层风险预算或再入场纪律；单独加止损会改变组合资金流，不能只看 closed lot 层面。",
        "- 下一步如果继续，只能研究不调参的账户层闸门或归因验证；不能改 R 倍数、冷却天数或品种过滤去修补 2022。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = _prepare()
    curve = frames["curve"]
    lots = frames["lots"]
    intraday = frames["intraday"]
    window = _drawdown_window(curve)
    daily_delta = _daily_delta(curve)
    lot_diff, product_attr, exposure = _window_lot_diff(lots, window)
    event_impact = _event_impact(lots, intraday)

    peak_date = pd.Timestamp(window["peak_date"])
    trough_date = pd.Timestamp(window["trough_date"])
    window_delta = daily_delta[daily_delta["date"].between(peak_date, trough_date)].copy()
    c2 = curve[curve["arm"].eq(C2_ARM)].copy()
    base = curve[curve["arm"].eq(BASE_ARM)].copy()
    c2_trough = c2.loc[pd.to_numeric(c2["drawdown_pct"], errors="coerce").idxmin()]
    base_same_day = base[base["date"].eq(c2_trough["date"])].iloc[0]
    summary = pd.DataFrame(
        [
            {
                "metric": "c2_peak_date",
                "value": peak_date.strftime("%Y-%m-%d"),
            },
            {
                "metric": "c2_trough_date",
                "value": trough_date.strftime("%Y-%m-%d"),
            },
            {
                "metric": "c2_trough_equity",
                "value": float(window["trough_equity"]),
            },
            {
                "metric": "a_equity_same_day",
                "value": float(base_same_day["account_equity"]),
            },
            {
                "metric": "equity_gap_C_minus_A_at_trough",
                "value": float(window["trough_equity"]) - float(base_same_day["account_equity"]),
            },
            {
                "metric": "c2_trough_dd_pct",
                "value": float(window["trough_drawdown_pct"]),
            },
            {
                "metric": "a_dd_same_day_pct",
                "value": float(base_same_day["drawdown_pct"]),
            },
            {
                "metric": "dd_gap_C_minus_A_pp",
                "value": float(window["trough_drawdown_pct"]) - float(base_same_day["drawdown_pct"]),
            },
            {
                "metric": "window_net_pnl_delta_C_minus_A",
                "value": float(window_delta["net_pnl_delta_C_minus_A"].sum()),
            },
            {
                "metric": "window_max_margin_pct_gap_C_minus_A",
                "value": float(window_delta["broker10_margin_to_equity_pct_delta_C_minus_A"].max()),
            },
            {
                "metric": "c2_event_count_total",
                "value": int(len(event_impact)),
            },
            {
                "metric": "c2_event_count_2022",
                "value": int(pd.to_datetime(event_impact["event_date"], errors="coerce").dt.year.eq(2022).sum())
                if not event_impact.empty
                else 0,
            },
        ]
    )

    _plot_path(daily_delta, window)
    _plot_event_atlas(event_impact)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    daily_delta.to_csv(DAILY_DELTA_PATH, index=False, encoding="utf-8-sig")
    lot_diff.to_csv(WINDOW_LOT_DIFF_PATH, index=False, encoding="utf-8-sig")
    product_attr.to_csv(WINDOW_PRODUCT_ATTR_PATH, index=False, encoding="utf-8-sig")
    event_impact.to_csv(C2_EVENT_IMPACT_PATH, index=False, encoding="utf-8-sig")
    exposure.to_csv(EXPOSURE_DIFF_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, daily_delta, lot_diff, product_attr, exposure, event_impact, window)

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "window": _json_safe(window),
        "summary": summary.to_dict("records"),
        "decision": "c2_not_promoted_drawdown_worse_due_second_order_exposure",
        "overfit_reflection": (
            "No parameter was changed. The attribution rejects threshold tuning and focuses on second-order exposure after stop-out."
        ),
        "continue_value": (
            "Continue only with non-tuned account-level exposure attribution or guard design; do not tune R multiples or product filters."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "daily_delta": str(DAILY_DELTA_PATH),
            "window_lot_diff": str(WINDOW_LOT_DIFF_PATH),
            "window_product_attr": str(WINDOW_PRODUCT_ATTR_PATH),
            "c2_event_impact": str(C2_EVENT_IMPACT_PATH),
            "exposure_diff": str(EXPOSURE_DIFF_PATH),
            "report": str(REPORT_PATH),
            "path_chart": str(PATH_CHART_PATH),
            "event_atlas": str(EVENT_ATLAS_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("summary")
    print(summary.to_string(index=False))
    print("worst product attr")
    print(product_attr.head(12).to_string(index=False))


if __name__ == "__main__":
    main()
