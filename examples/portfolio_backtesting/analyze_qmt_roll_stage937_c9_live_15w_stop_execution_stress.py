from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import font_manager
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
import analyze_qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns as s936
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage937"
MODEL_TAG = "stage937_c9_live_15w_stop_execution_stress_v1"
OUTPUT_PREFIX = "qmt_roll_stage937_c9_live_15w_stop_execution_stress"

STRESS_TICKS = (0, 1, 2, 5)
INTRADAY_SCOPE = "intraday_only"
ALL_STOP_SCOPE = "all_strategy_stop_close"

DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv"
STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_events_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DASHBOARD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dashboard_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _configure_font() -> None:
    candidates = [
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/3419f2a427639ad8c8e139149a287865a90fa17e.asset/AssetData/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for item in candidates:
        path = Path(item)
        if path.exists():
            font_manager.fontManager.addfont(str(path))
            prop = font_manager.FontProperties(fname=str(path))
            plt.rcParams["font.family"] = prop.get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False


def _price_meta(metadata: dict[str, Any], vt_symbol: str) -> tuple[float, float]:
    sizes = metadata.get("sizes", {})
    ticks = metadata.get("priceticks", {})
    size = float(sizes.get(vt_symbol, 1.0) or 1.0)
    tick = float(ticks.get(vt_symbol, 0.0) or 0.0)
    if not np.isfinite(size) or size <= 0:
        size = 1.0
    if not np.isfinite(tick) or tick <= 0:
        tick = 0.0
    return size, tick


def _append_event(
    rows: list[dict[str, Any]],
    *,
    start: pd.Timestamp,
    row: pd.Series,
    event_time_value: Any,
    stop_source: str,
    stop_sequence: str,
    metadata: dict[str, Any],
) -> None:
    event_time = pd.to_datetime(event_time_value, errors="coerce")
    if pd.isna(event_time):
        return
    vt_symbol = str(row.get("vt_symbol", ""))
    if not vt_symbol:
        return
    volume = float(pd.to_numeric(pd.Series([row.get("volume", 0.0)]), errors="coerce").fillna(0.0).iloc[0])
    if volume <= 0:
        return
    size, tick = _price_meta(metadata, vt_symbol)
    cost_per_tick = volume * size * tick
    rows.append(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "requested_start": _date_text(start),
            "requested_start_month": _start_month_text(start),
            "event_time": event_time.isoformat(),
            "event_date": event_time.normalize().date().isoformat(),
            "stop_source": stop_source,
            "stop_sequence": stop_sequence,
            "vt_symbol": vt_symbol,
            "product_vt_symbol": str(row.get("product_vt_symbol", "")),
            "direction": str(row.get("direction", "")),
            "volume": volume,
            "size": size,
            "pricetick": tick,
            "cost_per_tick": float(cost_per_tick),
            "entry_price": float(pd.to_numeric(pd.Series([row.get("entry_price", np.nan)]), errors="coerce").iloc[0]),
            "stop_price": float(pd.to_numeric(pd.Series([row.get("stop_price", np.nan)]), errors="coerce").iloc[0]),
            "exit_reason": str(row.get("exit_reason", "")),
            "final_state": str(row.get("final_state", "")),
        }
    )


def _intraday_stop_events(
    frames: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
    start: pd.Timestamp,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    c2_events = frames.get("c2_events", pd.DataFrame()).copy()
    if not c2_events.empty:
        for _, row in c2_events.iterrows():
            _append_event(
                rows,
                start=start,
                row=row,
                event_time_value=row.get("hit_time"),
                stop_source="stage827_c2_1r_stop",
                stop_sequence="c2_stop",
                metadata=metadata,
            )
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame()).copy()
    if not stop_retry_events.empty:
        for _, row in stop_retry_events.iterrows():
            _append_event(
                rows,
                start=start,
                row=row,
                event_time_value=row.get("first_stop_time"),
                stop_source="stage847_c9_05r_stop_retry",
                stop_sequence="initial_05r_stop",
                metadata=metadata,
            )
            retry_failed = int(
                pd.to_numeric(pd.Series([row.get("retry_failed", 0)]), errors="coerce").fillna(0).iloc[0]
            )
            if retry_failed:
                _append_event(
                    rows,
                    start=start,
                    row=row,
                    event_time_value=row.get("retry_failed_time"),
                    stop_source="stage847_c9_05r_stop_retry",
                    stop_sequence="retry_failed_05r_stop",
                    metadata=metadata,
                )
    return pd.DataFrame(rows)


def _strategy_stop_close_events(
    frames: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
    start: pd.Timestamp,
) -> pd.DataFrame:
    trades = frames.get("trades", pd.DataFrame()).copy()
    if trades.empty:
        return pd.DataFrame()
    offsets = trades.get("offset", pd.Series("", index=trades.index)).astype(str).str.lower()
    reasons = trades.get("exit_reason", pd.Series("", index=trades.index)).astype(str)
    stop_closes = trades[offsets.eq("close") & reasons.str.contains("stop", case=False, na=False)].copy()
    rows: list[dict[str, Any]] = []
    for _, row in stop_closes.iterrows():
        _append_event(
            rows,
            start=start,
            row=row,
            event_time_value=row.get("datetime"),
            stop_source="strategy_stop_close",
            stop_sequence=str(row.get("exit_reason", "")),
            metadata=metadata,
        )
    return pd.DataFrame(rows)


def _stress_curves(combined: pd.DataFrame, events: pd.DataFrame, stress_ticks: int) -> pd.DataFrame:
    curve = combined.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if events.empty:
        daily_cost_per_tick = pd.Series(dtype=float)
    else:
        event_frame = events.copy()
        event_frame["event_date"] = pd.to_datetime(event_frame["event_date"], errors="coerce").dt.normalize()
        daily_cost_per_tick = pd.to_numeric(event_frame["cost_per_tick"], errors="coerce").fillna(0.0).groupby(
            event_frame["event_date"]
        ).sum()
    curve["stop_cost_per_tick_daily"] = curve["date"].map(daily_cost_per_tick).fillna(0.0)
    curve["extra_stop_execution_cost_daily"] = curve["stop_cost_per_tick_daily"] * float(stress_ticks)
    curve["extra_stop_execution_cost_cum"] = curve["extra_stop_execution_cost_daily"].cumsum()
    curve["stress_ticks"] = int(stress_ticks)
    curve["stressed_account_equity"] = (
        pd.to_numeric(curve["account_equity"], errors="coerce").fillna(float(OFFICIAL_LIVE_CAPITAL))
        - curve["extra_stop_execution_cost_cum"]
    )
    curve["stressed_nav"] = curve["stressed_account_equity"] / float(OFFICIAL_LIVE_CAPITAL)
    curve["stressed_drawdown_pct"] = _drawdown_pct(curve["stressed_account_equity"])
    return curve


def _horizon_row(curve: pd.DataFrame, target_date: pd.Timestamp) -> pd.Series | None:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["date"].le(target_date.normalize())].dropna(subset=["date"]).sort_values("date")
    if frame.empty:
        return None
    return frame.iloc[-1]


def _detail_rows_for_curve(
    curve: pd.DataFrame,
    events: pd.DataFrame,
    start: pd.Timestamp,
    stress_ticks: int,
    stress_scope: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon_key, months, label in s936.HORIZONS:
        target_date = start + pd.DateOffset(months=months)
        if target_date > s936.LATEST_COMPLETE_DATA_DATE:
            continue
        row = _horizon_row(curve, target_date)
        if row is None:
            continue
        actual_end = pd.Timestamp(row["date"]).normalize()
        dated = curve[pd.to_datetime(curve["date"], errors="coerce").dt.normalize().le(actual_end)].copy()
        if events.empty:
            events_to_horizon = events.copy()
        else:
            event_dates = pd.to_datetime(events["event_date"], errors="coerce").dt.normalize()
            events_to_horizon = events[event_dates.le(actual_end)].copy()
        stressed_equity = pd.to_numeric(dated["stressed_account_equity"], errors="coerce")
        baseline_equity = pd.to_numeric(pd.Series([row.get("account_equity", np.nan)]), errors="coerce").iloc[0]
        end_equity = float(pd.to_numeric(pd.Series([row.get("stressed_account_equity", np.nan)]), errors="coerce").iloc[0])
        return_pct = (end_equity / float(OFFICIAL_LIVE_CAPITAL) - 1.0) * 100.0
        baseline_return_pct = (float(baseline_equity) / float(OFFICIAL_LIVE_CAPITAL) - 1.0) * 100.0
        c2_count = int(events_to_horizon["stop_source"].astype(str).eq("stage827_c2_1r_stop").sum()) if not events_to_horizon.empty else 0
        c9_count = (
            int(events_to_horizon["stop_source"].astype(str).eq("stage847_c9_05r_stop_retry").sum())
            if not events_to_horizon.empty
            else 0
        )
        cost_per_tick = (
            float(pd.to_numeric(events_to_horizon.get("cost_per_tick", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum())
            if not events_to_horizon.empty
            else 0.0
        )
        rows.append(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
                "requested_start": _date_text(start),
                "requested_start_month": _start_month_text(start),
                "horizon_key": horizon_key,
                "horizon_label": label,
                "horizon_months": int(months),
                "target_date": _date_text(target_date),
                "actual_end": _date_text(actual_end),
                "stress_scope": stress_scope,
                "stress_ticks": int(stress_ticks),
                "account_capital": float(OFFICIAL_LIVE_CAPITAL),
                "baseline_end_equity": float(baseline_equity),
                "stressed_end_equity": end_equity,
                "baseline_return_pct": float(baseline_return_pct),
                "stressed_return_pct": float(return_pct),
                "return_delta_vs_baseline_pct": float(return_pct - baseline_return_pct),
                "max_dd_pct_to_horizon": float(_drawdown_pct(stressed_equity).min()) if len(stressed_equity) else np.nan,
                "intraday_stop_close_count_to_horizon": int(len(events_to_horizon)),
                "c2_stop_close_count_to_horizon": c2_count,
                "c9_stop_close_count_to_horizon": c9_count,
                "stop_cost_per_tick_to_horizon": cost_per_tick,
                "extra_stop_execution_cost_to_horizon": cost_per_tick * float(stress_ticks),
            }
        )
    return rows


def _stats(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (stress_scope, horizon_key, stress_ticks), group in detail.groupby(
        ["stress_scope", "horizon_key", "stress_ticks"],
        sort=False,
    ):
        returns = pd.to_numeric(group["stressed_return_pct"], errors="coerce")
        delta = pd.to_numeric(group["return_delta_vs_baseline_pct"], errors="coerce")
        min_idx = returns.idxmin()
        max_idx = returns.idxmax()
        rows.append(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "stress_scope": stress_scope,
                "horizon_key": horizon_key,
                "horizon_label": str(group["horizon_label"].iloc[0]),
                "stress_ticks": int(stress_ticks),
                "sample_count": int(len(group)),
                "positive_count": int((returns > 0.0).sum()),
                "positive_rate_pct": float((returns > 0.0).mean() * 100.0),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "median_delta_vs_baseline_pct": float(delta.median()),
                "min_return_start": str(group.loc[min_idx, "requested_start_month"]),
                "max_return_start": str(group.loc[max_idx, "requested_start_month"]),
                "worst_max_dd_pct_to_horizon": float(pd.to_numeric(group["max_dd_pct_to_horizon"], errors="coerce").min()),
                "median_extra_stop_execution_cost": float(
                    pd.to_numeric(group["extra_stop_execution_cost_to_horizon"], errors="coerce").median()
                ),
                "max_extra_stop_execution_cost": float(
                    pd.to_numeric(group["extra_stop_execution_cost_to_horizon"], errors="coerce").max()
                ),
                "median_intraday_stop_close_count": float(
                    pd.to_numeric(group["intraday_stop_close_count_to_horizon"], errors="coerce").median()
                ),
                "max_intraday_stop_close_count": int(
                    pd.to_numeric(group["intraday_stop_close_count_to_horizon"], errors="coerce").max()
                ),
            }
        )
    return pd.DataFrame(rows)


def _write_report(detail: pd.DataFrame, stats: pd.DataFrame, events: pd.DataFrame, decision: dict[str, Any]) -> None:
    stats_view = stats[
        [
            "stress_scope",
            "horizon_label",
            "stress_ticks",
            "sample_count",
            "positive_count",
            "min_return_pct",
            "median_return_pct",
            "max_return_pct",
            "median_delta_vs_baseline_pct",
            "worst_max_dd_pct_to_horizon",
            "median_extra_stop_execution_cost",
            "max_extra_stop_execution_cost",
        ]
    ].copy()
    stress5 = detail[pd.to_numeric(detail["stress_ticks"], errors="coerce").eq(5)].copy()
    detail_view = stress5[
        [
            "stress_scope",
            "requested_start_month",
            "horizon_label",
            "stressed_return_pct",
            "return_delta_vs_baseline_pct",
            "max_dd_pct_to_horizon",
            "intraday_stop_close_count_to_horizon",
            "extra_stop_execution_cost_to_horizon",
        ]
    ].sort_values(["horizon_label", "requested_start_month"])
    source_summary = pd.DataFrame()
    if not events.empty:
        source_summary = (
            events.groupby(["stress_scope", "requested_start_month", "stop_source"])
            .agg(stop_close_count=("stop_source", "size"), cost_per_tick=("cost_per_tick", "sum"))
            .reset_index()
        )
    lines = [
        "# Stage937 C9 当前实盘15万止损执行压力版",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前实盘版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 当前实盘 profile：`{OFFICIAL_LIVE_PROFILE_NAME}`，账户资金 `{OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        f"- AI 池：`{OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        f"- 起点：从 `{s936.REQUESTED_START.date()}` 起，每年 `1月1日` 和 `7月1日`。",
        f"- 数据终点：`{s936.LATEST_COMPLETE_DATA_DATE.date()}`；只统计完整半年/一年 horizon。",
        "- 压力方式：对止损类平仓事件增加额外不利成交成本；不改变信号、手数、止损线或重进逻辑。",
        "- 口径1 intraday_only：Stage827 C2 1R intraday stop，以及 Stage847 C9 0.5R initial stop / retry failed stop。",
        "- 口径2 all_strategy_stop_close：所有 `exit_reason` 包含 stop 的策略平仓成交。",
        "- 不连接 CTP，不读取账户，不调用订单 API。",
        "",
        "## 统计结论",
        "",
        _md_table(stats_view, max_rows=20),
        "",
        "## 5 tick 压力明细",
        "",
        _md_table(detail_view, max_rows=40),
        "",
        "## 止损事件摘要",
        "",
        _md_table(source_summary, max_rows=80),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_dashboard(stats: pd.DataFrame) -> None:
    _configure_font()
    plot_stats = stats[stats["stress_scope"].astype(str).eq(ALL_STOP_SCOPE)].copy()
    if plot_stats.empty:
        plot_stats = stats.copy()
    fig, axes = plt.subplots(2, 1, figsize=(10, 9), dpi=180, sharex=True)
    colors = {"min_return_pct": "#D64545", "median_return_pct": "#2B6CB0", "max_return_pct": "#2F855A"}
    labels = {"min_return_pct": "最低", "median_return_pct": "中位", "max_return_pct": "最高"}
    for ax, horizon_label in zip(axes, ["半年", "一年"]):
        sub = plot_stats[plot_stats["horizon_label"].astype(str).eq(horizon_label)].sort_values("stress_ticks")
        for column, color in colors.items():
            ax.plot(
                sub["stress_ticks"],
                sub[column],
                marker="o",
                linewidth=2,
                color=color,
                label=labels[column],
            )
            for x, y in zip(sub["stress_ticks"], sub[column]):
                ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
        ax.axhline(0, color="#1f2933", linewidth=1)
        ax.set_title(f"{horizon_label}收益率：全部策略止损平仓额外不利 tick 压力", loc="left", fontsize=13)
        ax.set_ylabel("收益率")
        ax.grid(axis="y", color="#d9dee7", linewidth=0.7, alpha=0.75)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(loc="best", frameon=False, ncols=3)
    axes[-1].set_xlabel("每次止损平仓额外不利 tick")
    fig.suptitle("C9当前实盘15万：止损执行压力版", fontsize=16, fontweight="bold")
    fig.text(
        0.5,
        0.935,
        "主图为 all_strategy_stop_close；intraday_only 见 stats 明细；不改变策略规则和仓位路径；订单API=0",
        ha="center",
        fontsize=9.5,
        color="#4a5568",
    )
    fig.subplots_adjust(left=0.1, right=0.97, top=0.88, bottom=0.08, hspace=0.35)
    fig.savefig(DASHBOARD_PATH, facecolor="white", bbox_inches="tight")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"[stage937] current live={OFFICIAL_LIVE_VERSION} starts={s936.REQUESTED_START.date()} "
        f"data_end={s936.LATEST_COMPLETE_DATA_DATE.date()} stress_ticks={STRESS_TICKS}",
        flush=True,
    )
    metadata = s901.s513._metadata()
    starts = s936._build_start_dates()
    detail_rows: list[dict[str, Any]] = []
    all_curves: list[pd.DataFrame] = []
    all_events: list[pd.DataFrame] = []
    skipped: list[dict[str, Any]] = []

    for idx, start in enumerate(starts, start=1):
        max_months = s936._max_complete_horizon_months(start)
        if max_months <= 0:
            skipped.append({"requested_start": _date_text(start), "reason": "no_complete_half_year_or_one_year_horizon"})
            continue
        run_end = start + pd.DateOffset(months=max_months)
        print(
            f"[stage937] running {idx}/{len(starts)} start={_date_text(start)} run_end={_date_text(run_end)}",
            flush=True,
        )
        combined, frames, _spec = s901._run_live_c9(metadata, start, run_end)
        scoped_events = {
            INTRADAY_SCOPE: _intraday_stop_events(frames, metadata, start),
            ALL_STOP_SCOPE: _strategy_stop_close_events(frames, metadata, start),
        }
        for stress_scope, events in scoped_events.items():
            if not events.empty:
                events = events.copy()
                events["stress_scope"] = stress_scope
            all_events.append(events)
            for stress_ticks in STRESS_TICKS:
                curve = _stress_curves(combined, events, stress_ticks)
                curve["stage"] = STAGE
                curve["model_tag"] = MODEL_TAG
                curve["line_id"] = LINE_ID
                curve["official_live_version"] = OFFICIAL_LIVE_VERSION
                curve["requested_start"] = _date_text(start)
                curve["requested_start_month"] = _start_month_text(start)
                curve["requested_run_end"] = _date_text(run_end)
                curve["stress_scope"] = stress_scope
                all_curves.append(curve)
                detail_rows.extend(_detail_rows_for_curve(curve, events, start, stress_ticks, stress_scope))

    detail = pd.DataFrame(detail_rows).sort_values(
        ["stress_scope", "horizon_months", "stress_ticks", "requested_start"]
    ).reset_index(drop=True)
    events_df = pd.concat(all_events, ignore_index=True, sort=False) if all_events else pd.DataFrame()
    curves = pd.concat(all_curves, ignore_index=True, sort=False) if all_curves else pd.DataFrame()
    stats = _stats(detail) if not detail.empty else pd.DataFrame()

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "requested_start": s936.REQUESTED_START.date().isoformat(),
        "start_schedule": "Jan 1 and Jul 1 every year",
        "latest_complete_data_date": s936.LATEST_COMPLETE_DATA_DATE.date().isoformat(),
        "stress_ticks": list(STRESS_TICKS),
        "stress_scopes": {
            INTRADAY_SCOPE: "Stage827 C2 1R intraday stop and Stage847 C9 0.5R stop/retry close events",
            ALL_STOP_SCOPE: "All strategy close trades whose exit_reason contains stop",
        },
        "stress_formula": "extra_cost = stress_ticks * pricetick * contract_size * close_volume",
        "detail_count": int(len(detail)),
        "event_stop_close_count_by_scope": (
            events_df.groupby("stress_scope").size().astype(int).to_dict() if not events_df.empty else {}
        ),
        "stats": stats.to_dict(orient="records") if not stats.empty else [],
        "skipped_starts": skipped,
        "decision": "stage937_live_c9_15w_stop_execution_stress_measured_no_order_api",
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": (
            "否。压力 tick 档位是固定执行成本情景，不改变策略信号、手数、止损线或重进逻辑。"
        ),
        "continue_value_before": (
            "是。它直接检验历史分钟止损价相对真实盘口成交可能偏乐观的影响。"
        ),
        "overfit_reflection_after": (
            "否。本次只是对固定 live 口径叠加执行成本压力；不能用结果反向调整策略参数。"
        ),
        "continue_value_after": (
            "是。结果可作为实盘止损成交偏差的保守区间，后续应优先用真实 TCA 校准 tick 压力。"
        ),
        "outputs": {
            "detail": str(DETAIL_PATH),
            "stats": str(STATS_PATH),
            "events": str(EVENTS_PATH),
            "curves": str(CURVES_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "dashboard": str(DASHBOARD_PATH),
        },
    }

    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    stats.to_csv(STATS_PATH, index=False, encoding="utf-8-sig")
    events_df.to_csv(EVENTS_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(detail, stats, events_df, decision)
    if not stats.empty:
        _plot_dashboard(stats)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    if not stats.empty:
        print("stats")
        print(
            stats[
                [
                    "horizon_label",
                    "stress_scope",
                    "stress_ticks",
                    "sample_count",
                    "positive_count",
                    "min_return_pct",
                    "median_return_pct",
                    "max_return_pct",
                    "median_delta_vs_baseline_pct",
                    "worst_max_dd_pct_to_horizon",
                    "median_extra_stop_execution_cost",
                    "max_extra_stop_execution_cost",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
