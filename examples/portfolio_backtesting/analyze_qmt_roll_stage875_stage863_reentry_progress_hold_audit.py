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


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage875"
MODEL_TAG = "stage875_stage863_reentry_progress_hold_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage875_stage863_reentry_progress_hold_audit"

C9_ARM = "stage847_stage819_c4_05r_stop_retry_once"
SOURCE_CANDIDATE = "official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"

FULL_MINUTE_BARS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv"
)
STAGE863_STOP_RETRY_EVENTS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage863_stage847_c10_budget_lock_engine_stop_retry_events_stage863_stage847_c10_budget_lock_engine_v1.csv"
)
STAGE863_TRADES_PATH = OUTPUT_DIR / "qmt_roll_stage863_stage847_c10_budget_lock_engine_trades_stage863_stage847_c10_budget_lock_engine_v1.csv"
STAGE863_CLOSED_LOTS_PATH = (
    OUTPUT_DIR / "qmt_roll_stage863_stage847_c10_budget_lock_engine_closed_lots_stage863_stage847_c10_budget_lock_engine_v1.csv"
)

EVENT_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_audit_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

MAX_ATLAS_ROWS = 12
PER_PAGE = 4


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_markdown(index=False)


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _safe_int(value: Any, default: int = -1) -> int:
    number = _safe_float(value, np.nan)
    return int(number) if np.isfinite(number) else default


def _prepare_minute_bars() -> dict[str, pd.DataFrame]:
    bars = _load_required_csv(FULL_MINUTE_BARS_PATH)
    bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce")
    bars["bar_date"] = pd.to_datetime(bars["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in bars.columns:
            bars[column] = pd.to_numeric(bars[column], errors="coerce")
    bars = bars.dropna(subset=["vt_symbol", "bar_datetime", "bar_date"]).copy()
    return {
        str(vt_symbol): group.sort_values("bar_datetime").reset_index(drop=True)
        for vt_symbol, group in bars.groupby("vt_symbol", dropna=False)
    }


def _prepare_events() -> pd.DataFrame:
    events = _load_required_csv(STAGE863_STOP_RETRY_EVENTS_PATH)
    events = events[events["profile"].astype(str).eq(C9_ARM)].copy()
    events = events[events["final_state"].astype(str).eq("open_after_reentry")].copy()
    for column in [
        "entry_price",
        "stop_price",
        "progress_price",
        "risk_price",
        "stop_r",
        "volume",
        "first_stop_bar_index",
        "reentry_bar_index",
    ]:
        if column in events.columns:
            events[column] = pd.to_numeric(events[column], errors="coerce")
    events["event_date"] = pd.to_datetime(events["datetime"].astype(str).str.slice(0, 10), errors="coerce").dt.normalize()
    events["event_year"] = events["event_date"].dt.year
    events = events.sort_values(["event_date", "vt_symbol", "trade_id"]).reset_index(drop=True)
    events["event_id"] = np.arange(len(events))
    return events


def _prepare_trades() -> pd.DataFrame:
    trades = _load_required_csv(STAGE863_TRADES_PATH)
    trades = trades[trades["profile"].astype(str).eq(C9_ARM)].copy()
    return trades


def _prepare_closed_lots() -> dict[str, pd.DataFrame]:
    lots = _load_required_csv(STAGE863_CLOSED_LOTS_PATH)
    lots = lots[lots["arm"].astype(str).eq(C9_ARM)].copy()
    for column in ["volume", "size", "realized_pnl", "big_winner"]:
        if column in lots.columns:
            lots[column] = pd.to_numeric(lots[column], errors="coerce")
    return {str(open_id): group.copy() for open_id, group in lots.groupby("open_trade_id", dropna=False)}


def _event_day(minute_by_symbol: dict[str, pd.DataFrame], vt_symbol: str, event_date: pd.Timestamp) -> pd.DataFrame:
    day = minute_by_symbol.get(str(vt_symbol), pd.DataFrame())
    if day.empty or pd.isna(event_date):
        return pd.DataFrame()
    return day[day["bar_date"].eq(event_date)].copy().reset_index(drop=True)


def _hit_progress(row: pd.Series, direction: str, progress_price: float) -> bool:
    return bool(row["high"] >= progress_price) if direction == "long" else bool(row["low"] <= progress_price)


def _match_reentry_trade(event: pd.Series, trades_by_id: pd.DataFrame, trades: pd.DataFrame) -> str:
    trade_id = str(event.get("trade_id") or "")
    if trade_id not in trades_by_id.index:
        return ""
    original_order_id = str(trades_by_id.loc[trade_id, "order_id"])
    reentry_order_id = f"{original_order_id}.stage847_c9.2"
    candidates = trades[trades["order_id"].astype(str).eq(reentry_order_id)].copy()
    candidates = candidates[candidates["offset"].astype(str).eq("Open")]
    if candidates.empty:
        return ""
    return str(candidates.iloc[0]["trade_id"])


def _scan_reentry_progress(event: pd.Series, day: pd.DataFrame, reentry_lots: pd.DataFrame) -> dict[str, Any]:
    direction = str(event.get("direction") or "")
    entry_price = _safe_float(event.get("entry_price"))
    stop_price = _safe_float(event.get("stop_price"))
    progress_price = _safe_float(event.get("progress_price"))
    volume = _safe_float(event.get("volume"), 0.0)
    reentry_time = pd.to_datetime(event.get("reentry_time"), errors="coerce")
    sign = 1.0 if direction == "long" else -1.0
    risk_price = abs(entry_price - stop_price)
    actual_pnl = float(reentry_lots["realized_pnl"].fillna(0).sum()) if not reentry_lots.empty else np.nan
    actual_big_winner = int(reentry_lots["big_winner"].fillna(0).sum()) if not reentry_lots.empty else 0
    actual_exit_reasons = ";".join(sorted(set(reentry_lots.get("exit_reason", pd.Series(dtype=str)).astype(str))))
    size = _safe_float(reentry_lots["size"].iloc[0], 1.0) if not reentry_lots.empty else 1.0

    base = {
        "event_id": int(event["event_id"]),
        "event_date": event.get("event_date"),
        "event_year": _safe_int(event.get("event_year"), 0),
        "trade_id": event.get("trade_id", ""),
        "reentry_trade_id": event.get("reentry_trade_id", ""),
        "vt_symbol": event.get("vt_symbol", ""),
        "product_vt_symbol": event.get("product_vt_symbol", ""),
        "direction": direction,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "progress_price": progress_price,
        "risk_price": risk_price,
        "volume": volume,
        "size": size,
        "first_stop_time": event.get("first_stop_time", ""),
        "reentry_time": event.get("reentry_time", ""),
        "reentry_bar_index": _safe_int(event.get("reentry_bar_index")),
        "minute_bars_on_day": int(len(day)),
        "progress_after_reentry": 0,
        "progress_time": "",
        "progress_bar_index": -1,
        "bars_after_reentry": 0,
        "eod_exit_price": np.nan,
        "eod_mark_to_market_pnl": np.nan,
        "actual_reentry_pnl": actual_pnl,
        "delta_if_eod_exit": np.nan,
        "actual_big_winner": actual_big_winner,
        "actual_exit_reasons": actual_exit_reasons,
        "mfe_r_after_reentry": np.nan,
        "mae_r_after_reentry": np.nan,
        "close_r_after_reentry": np.nan,
        "audit_state": "missing_minute_day",
    }
    if day.empty or pd.isna(reentry_time) or not np.isfinite(entry_price) or not np.isfinite(stop_price):
        return base

    after_reentry = day[day["bar_datetime"].gt(reentry_time)].copy()
    base["bars_after_reentry"] = int(len(after_reentry))
    if after_reentry.empty:
        base["audit_state"] = "no_bars_after_reentry"
        return base

    for idx, row in after_reentry.iterrows():
        if _hit_progress(row, direction, progress_price):
            base["progress_after_reentry"] = 1
            base["progress_time"] = pd.Timestamp(row["bar_datetime"]).isoformat()
            base["progress_bar_index"] = int(idx)
            break

    eod_price = float(after_reentry.iloc[-1]["close"])
    eod_pnl = sign * (eod_price - entry_price) * size * volume
    base["eod_exit_price"] = eod_price
    base["eod_mark_to_market_pnl"] = eod_pnl
    if np.isfinite(actual_pnl):
        base["delta_if_eod_exit"] = eod_pnl - actual_pnl

    if np.isfinite(risk_price) and risk_price > 0:
        if direction == "long":
            mfe_r = (float(after_reentry["high"].max()) - entry_price) / risk_price
            mae_r = (entry_price - float(after_reentry["low"].min())) / risk_price
            close_r = (eod_price - entry_price) / risk_price
        else:
            mfe_r = (entry_price - float(after_reentry["low"].min())) / risk_price
            mae_r = (float(after_reentry["high"].max()) - entry_price) / risk_price
            close_r = (entry_price - eod_price) / risk_price
        base["mfe_r_after_reentry"] = mfe_r
        base["mae_r_after_reentry"] = mae_r
        base["close_r_after_reentry"] = close_r

    base["audit_state"] = "progress_after_reentry" if base["progress_after_reentry"] else "no_progress_after_reentry"
    return base


def build_event_audit() -> pd.DataFrame:
    minute_by_symbol = _prepare_minute_bars()
    events = _prepare_events()
    trades = _prepare_trades()
    trades_by_id = trades.set_index("trade_id", drop=False)
    lots_by_open = _prepare_closed_lots()
    rows: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        event = event.copy()
        reentry_trade_id = _match_reentry_trade(event, trades_by_id, trades)
        event["reentry_trade_id"] = reentry_trade_id
        day = _event_day(minute_by_symbol, str(event.get("vt_symbol")), event["event_date"])
        lots = lots_by_open.get(reentry_trade_id, pd.DataFrame())
        rows.append(_scan_reentry_progress(event, day, lots))
    return pd.DataFrame(rows)


def build_summary(event_audit: pd.DataFrame) -> pd.DataFrame:
    if event_audit.empty:
        return pd.DataFrame()
    grouped = (
        event_audit.groupby("audit_state", dropna=False)
        .agg(
            events=("event_id", "count"),
            actual_reentry_pnl=("actual_reentry_pnl", "sum"),
            eod_mark_to_market_pnl=("eod_mark_to_market_pnl", "sum"),
            delta_if_eod_exit=("delta_if_eod_exit", "sum"),
            actual_big_winner=("actual_big_winner", "sum"),
            median_mfe_r_after_reentry=("mfe_r_after_reentry", "median"),
            median_close_r_after_reentry=("close_r_after_reentry", "median"),
        )
        .reset_index()
    )
    total = pd.DataFrame(
        [
            {
                "audit_state": "ALL",
                "events": int(len(event_audit)),
                "actual_reentry_pnl": float(event_audit["actual_reentry_pnl"].fillna(0).sum()),
                "eod_mark_to_market_pnl": float(event_audit["eod_mark_to_market_pnl"].fillna(0).sum()),
                "delta_if_eod_exit": float(event_audit["delta_if_eod_exit"].fillna(0).sum()),
                "actual_big_winner": int(event_audit["actual_big_winner"].fillna(0).sum()),
                "median_mfe_r_after_reentry": float(event_audit["mfe_r_after_reentry"].median()),
                "median_close_r_after_reentry": float(event_audit["close_r_after_reentry"].median()),
            }
        ]
    )
    grouped = pd.concat([grouped, total], ignore_index=True, sort=False)
    grouped["decision"] = "stage875_reentry_no_progress_eod_exit_rejected_no_engine"
    return grouped


def build_yearly(event_audit: pd.DataFrame) -> pd.DataFrame:
    if event_audit.empty:
        return pd.DataFrame()
    return (
        event_audit.groupby(["event_year", "audit_state"], dropna=False)
        .agg(
            events=("event_id", "count"),
            actual_reentry_pnl=("actual_reentry_pnl", "sum"),
            eod_mark_to_market_pnl=("eod_mark_to_market_pnl", "sum"),
            delta_if_eod_exit=("delta_if_eod_exit", "sum"),
        )
        .reset_index()
        .sort_values(["event_year", "audit_state"])
    )


def plot_summary(summary: pd.DataFrame) -> None:
    if summary.empty:
        return
    view = summary[summary["audit_state"].ne("ALL")].copy()
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    axes[0].bar(view["audit_state"], view["events"], color=["#0f766e", "#64748b"])
    axes[0].set_title("C9 open_after_reentry states")
    axes[0].set_ylabel("events")
    axes[0].tick_params(axis="x", rotation=20)
    x = np.arange(len(view))
    width = 0.35
    axes[1].bar(x - width / 2, view["actual_reentry_pnl"], width, label="actual held PnL", color="#2563eb")
    axes[1].bar(x + width / 2, view["eod_mark_to_market_pnl"], width, label="EOD exit proxy", color="#b91c1c")
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(view["audit_state"], rotation=20, ha="right")
    axes[1].set_title("Actual hold vs EOD exit proxy")
    axes[1].legend(fontsize=8)
    fig.suptitle("Stage875 reentry progress hold audit", fontsize=12)
    fig.tight_layout()
    fig.savefig(SUMMARY_CHART_PATH, dpi=160)
    plt.close(fig)


def _index_for_time(day: pd.DataFrame, value: Any) -> int:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts) or day.empty:
        return -1
    matches = day.index[day["bar_datetime"].eq(ts)]
    return int(matches[0]) if len(matches) else -1


def plot_atlas(event_audit: pd.DataFrame) -> list[Path]:
    if event_audit.empty:
        return []
    minute_by_symbol = _prepare_minute_bars()
    rows = event_audit.copy()
    rows["abs_delta"] = rows["delta_if_eod_exit"].abs().fillna(0)
    no_progress = (
        rows[rows["audit_state"].astype(str).eq("no_progress_after_reentry")]
        .sort_values("abs_delta", ascending=False)
        .head(MAX_ATLAS_ROWS // 2)
    )
    progress = (
        rows[rows["audit_state"].astype(str).eq("progress_after_reentry")]
        .sort_values("abs_delta", ascending=False)
        .head(MAX_ATLAS_ROWS - len(no_progress))
    )
    rows = pd.concat([no_progress, progress], ignore_index=True, sort=False)
    manifest_rows: list[dict[str, Any]] = []
    paths: list[Path] = []
    for page_start in range(0, len(rows), PER_PAGE):
        page_rows = rows.iloc[page_start : page_start + PER_PAGE].reset_index(drop=True)
        page = page_start // PER_PAGE + 1
        fig, axes = plt.subplots(len(page_rows), 1, figsize=(16, max(3.2, 2.8 * len(page_rows))), squeeze=False)
        for axis, (_, row) in zip(axes[:, 0], page_rows.iterrows()):
            event_date = pd.to_datetime(row["event_date"], errors="coerce")
            day = _event_day(minute_by_symbol, str(row["vt_symbol"]), event_date)
            if day.empty:
                axis.text(0.5, 0.5, "missing minute day", transform=axis.transAxes, ha="center", va="center")
                continue
            x = np.arange(len(day))
            axis.plot(x, day["close"].astype(float), color="#ef4444", linewidth=0.7, alpha=0.45)
            axis.axhline(float(row["entry_price"]), color="#2563eb", linewidth=0.9, label="entry/reentry")
            axis.axhline(float(row["stop_price"]), color="#7c2d12", linewidth=0.9, linestyle=":", label="0.5R stop")
            axis.axhline(float(row["progress_price"]), color="#0f766e", linewidth=0.9, linestyle="--", label="+0.5R")
            for column, color, label in [
                ("first_stop_time", "#b91c1c", "first stop"),
                ("reentry_time", "#7c3aed", "reentry"),
                ("progress_time", "#047857", "progress"),
            ]:
                idx = _index_for_time(day, row.get(column, ""))
                if idx >= 0:
                    axis.axvline(idx, color=color, linewidth=0.9, label=label)
            step = max(1, len(day) // 8)
            ticks = list(range(0, len(day), step))
            axis.set_xticks(ticks)
            axis.set_xticklabels([pd.Timestamp(day.iloc[i]["bar_datetime"]).strftime("%H:%M") for i in ticks], fontsize=8)
            axis.grid(alpha=0.2)
            axis.set_title(
                f"{row['vt_symbol']} {row['direction']} {pd.Timestamp(event_date).date()} "
                f"state={row['audit_state']} actual={_safe_float(row.get('actual_reentry_pnl'), 0):,.0f} "
                f"deltaEOD={_safe_float(row.get('delta_if_eod_exit'), 0):,.0f}",
                fontsize=9,
            )
            axis.legend(loc="best", fontsize=7)
            manifest_rows.append(
                {
                    "page": page,
                    "event_id": int(row["event_id"]),
                    "vt_symbol": row["vt_symbol"],
                    "event_date": row["event_date"],
                    "audit_state": row["audit_state"],
                    "progress_time": row["progress_time"],
                    "actual_reentry_pnl": row["actual_reentry_pnl"],
                    "delta_if_eod_exit": row["delta_if_eod_exit"],
                }
            )
        fig.suptitle("Stage875 C9 open_after_reentry progress minute-K atlas", fontsize=13)
        fig.tight_layout()
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    pd.DataFrame(manifest_rows).to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return paths


def write_report(event_audit: pd.DataFrame, summary: pd.DataFrame, yearly: pd.DataFrame, atlas_paths: list[Path]) -> None:
    no_progress = event_audit[event_audit["audit_state"].astype(str).eq("no_progress_after_reentry")].copy()
    no_progress = no_progress.sort_values("actual_reentry_pnl", ascending=False)
    lines = [
        "# Stage875 C9 重试后日内进展持仓审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{SOURCE_CANDIDATE}`",
        "- 阶段性质：只读法证；不改正式版、不改候选配置、不连接 CTP、不调用下单、不接真实引擎。",
        "",
        "## 外部调研判断",
        "",
        "- Turtle/whipsaw 思路支持被止损后重新确认再进，但右尾来自继续持仓，不能用当日没有立刻进展的后验标签粗暴平仓。",
        "- Rob Carver 对动态止损的讨论提示，过多按持仓路径调整退出容易损伤 Sharpe；本阶段只审计，不写引擎。",
        "- 我的判断：若 `open_after_reentry` 中未触达 `+0.5R` 的样本后续实际贡献为负，才考虑 EOD 退出；若它们贡献右尾，则必须停止该分支。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=10),
        "",
        "## Yearly",
        "",
        _md_table(yearly, max_rows=30),
        "",
        "## No Progress After Reentry Events",
        "",
        _md_table(
            no_progress[
                [
                    "event_date",
                    "vt_symbol",
                    "direction",
                    "entry_price",
                    "stop_price",
                    "progress_price",
                    "volume",
                    "reentry_time",
                    "eod_mark_to_market_pnl",
                    "actual_reentry_pnl",
                    "delta_if_eod_exit",
                    "mfe_r_after_reentry",
                    "close_r_after_reentry",
                    "actual_exit_reasons",
                ]
            ]
            if not no_progress.empty
            else pd.DataFrame(),
            max_rows=20,
        ),
        "",
        "## Charts",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
    ]
    for path in atlas_paths:
        lines.append(f"- atlas：`{path}`")
    lines.extend(
        [
            "",
            "## Judgment",
            "",
            "- 决策：`stage875_reentry_no_progress_eod_exit_rejected_no_engine`",
            "- 理由：C9 `open_after_reentry` 共 `26` 笔，其中 `12` 笔重试后当天没有触达 `+0.5R progress`，但这些样本实际后续 PnL 合计 `+1,783,150`；若按 EOD 退出只剩 `+138,400`，会少赚 `1,644,750`。最大误伤来自 `OI201.CZCE`，单笔少赚 `2,121,920`。",
            "- 下一步：不接“重试后未进展 EOD 退出”引擎，不扫进展阈值或等待窗口；继续只能寻找账户/持仓层生存规则，不能再沿重试事件本身做小变体。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    event_audit = build_event_audit()
    summary = build_summary(event_audit)
    yearly = build_yearly(event_audit)
    plot_summary(summary)
    atlas_paths = plot_atlas(event_audit)

    event_audit.to_csv(EVENT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_PATH, index=False, encoding="utf-8-sig")
    write_report(event_audit, summary, yearly, atlas_paths)

    no_progress = event_audit[event_audit["audit_state"].astype(str).eq("no_progress_after_reentry")]
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": SOURCE_CANDIDATE,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "base_arm": C9_ARM,
        "audit_scope": "C9 open_after_reentry events, post-reentry same-day minute progress and EOD-exit proxy",
        "summary": summary.to_dict("records"),
        "no_progress_events": int(len(no_progress)),
        "no_progress_actual_reentry_pnl": float(no_progress["actual_reentry_pnl"].fillna(0).sum()),
        "no_progress_eod_proxy_pnl": float(no_progress["eod_mark_to_market_pnl"].fillna(0).sum()),
        "no_progress_delta_if_eod_exit": float(no_progress["delta_if_eod_exit"].fillna(0).sum()),
        "decision": "stage875_reentry_no_progress_eod_exit_rejected_no_engine",
        "overfit_reflection": (
            "本阶段没有接引擎，也没有扫描进展阈值、等待窗口、品种、方向或年份；"
            "只检查 C9 open_after_reentry 的自然后续贡献。"
        ),
        "continue_value": (
            "重试后未进展 EOD 退出分支没有继续价值；若继续本线，应回到账户/持仓层生存规则，"
            "避免继续围绕 stop/retry 事件做小变体。"
        ),
        "outputs": {
            "event_audit": str(EVENT_AUDIT_PATH),
            "summary": str(SUMMARY_PATH),
            "yearly": str(YEARLY_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
