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
STAGE = "Stage874"
MODEL_TAG = "stage874_stage863_second_retry_feasibility_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage874_stage863_second_retry_feasibility_audit"

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
    events = events[events["final_state"].astype(str).eq("flat_retry_failed")].copy()
    for column in [
        "entry_price",
        "stop_price",
        "progress_price",
        "risk_price",
        "stop_r",
        "volume",
        "first_stop_bar_index",
        "reentry_bar_index",
        "retry_failed_bar_index",
    ]:
        if column in events.columns:
            events[column] = pd.to_numeric(events[column], errors="coerce")
    events["event_date"] = pd.to_datetime(events["datetime"].astype(str).str.slice(0, 10), errors="coerce").dt.normalize()
    events["event_year"] = events["event_date"].dt.year
    events = events.sort_values(["event_date", "vt_symbol", "trade_id"]).reset_index(drop=True)
    events["event_id"] = np.arange(len(events))
    return events


def _prepare_size_map() -> dict[str, float]:
    lots = _load_required_csv(STAGE863_CLOSED_LOTS_PATH)
    lots["size"] = pd.to_numeric(lots.get("size"), errors="coerce")
    size_map = (
        lots.dropna(subset=["vt_symbol", "size"])
        .drop_duplicates("vt_symbol")
        .set_index("vt_symbol")["size"]
        .astype(float)
        .to_dict()
    )
    return {str(k): float(v) for k, v in size_map.items()}


def _event_day(minute_by_symbol: dict[str, pd.DataFrame], vt_symbol: str, event_date: pd.Timestamp) -> pd.DataFrame:
    day = minute_by_symbol.get(str(vt_symbol), pd.DataFrame())
    if day.empty or pd.isna(event_date):
        return pd.DataFrame()
    return day[day["bar_date"].eq(event_date)].copy().reset_index(drop=True)


def _hit_reclaim(row: pd.Series, direction: str, entry_price: float) -> bool:
    return bool(row["high"] >= entry_price) if direction == "long" else bool(row["low"] <= entry_price)


def _hit_stop(row: pd.Series, direction: str, stop_price: float) -> bool:
    return bool(row["low"] <= stop_price) if direction == "long" else bool(row["high"] >= stop_price)


def _hit_progress(row: pd.Series, direction: str, progress_price: float) -> bool:
    return bool(row["high"] >= progress_price) if direction == "long" else bool(row["low"] <= progress_price)


def _scan_second_retry(event: pd.Series, day: pd.DataFrame, size: float) -> dict[str, Any]:
    direction = str(event.get("direction") or "")
    entry_price = _safe_float(event.get("entry_price"))
    stop_price = _safe_float(event.get("stop_price"))
    progress_price = _safe_float(event.get("progress_price"))
    volume = _safe_float(event.get("volume"), 0.0)
    retry_failed_time = pd.to_datetime(event.get("retry_failed_time"), errors="coerce")
    sign = 1.0 if direction == "long" else -1.0
    risk_price = abs(entry_price - stop_price)

    base = {
        "event_id": int(event["event_id"]),
        "event_date": event.get("event_date"),
        "event_year": _safe_int(event.get("event_year"), 0),
        "trade_id": event.get("trade_id", ""),
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
        "retry_failed_time": event.get("retry_failed_time", ""),
        "retry_failed_bar_index": _safe_int(event.get("retry_failed_bar_index")),
        "minute_bars_on_day": int(len(day)),
        "second_reclaim": 0,
        "second_reclaim_time": "",
        "second_reclaim_bar_index": -1,
        "second_stop": 0,
        "second_stop_time": "",
        "second_stop_bar_index": -1,
        "second_progress_after_reclaim": 0,
        "second_progress_time": "",
        "second_progress_bar_index": -1,
        "bars_after_retry_failed": 0,
        "bars_after_second_reclaim": 0,
        "extra_loss_if_second_stop": 0.0,
        "eod_mark_to_market_pnl_after_second_reentry": np.nan,
        "mfe_r_after_second_reentry": np.nan,
        "mae_r_after_second_reentry": np.nan,
        "close_r_after_second_reentry": np.nan,
        "audit_state": "missing_minute_day",
    }
    if day.empty or pd.isna(retry_failed_time) or not np.isfinite(entry_price) or not np.isfinite(stop_price):
        return base

    after_failed = day[day["bar_datetime"].gt(retry_failed_time)].copy()
    base["bars_after_retry_failed"] = int(len(after_failed))
    if after_failed.empty:
        base["audit_state"] = "no_bars_after_retry_failed"
        return base

    second_reclaim_idx = -1
    second_reclaim_time = pd.NaT
    for idx, row in after_failed.iterrows():
        if _hit_reclaim(row, direction, entry_price):
            second_reclaim_idx = int(idx)
            second_reclaim_time = row["bar_datetime"]
            break

    if second_reclaim_idx < 0:
        base["audit_state"] = "no_second_reclaim"
        return base

    base.update(
        {
            "second_reclaim": 1,
            "second_reclaim_time": pd.Timestamp(second_reclaim_time).isoformat(),
            "second_reclaim_bar_index": second_reclaim_idx,
        }
    )

    after_reclaim = day[day.index > second_reclaim_idx].copy()
    base["bars_after_second_reclaim"] = int(len(after_reclaim))
    if not after_reclaim.empty and np.isfinite(risk_price) and risk_price > 0:
        last_close = float(after_reclaim.iloc[-1]["close"])
        base["eod_mark_to_market_pnl_after_second_reentry"] = sign * (last_close - entry_price) * size * volume
        if direction == "long":
            mfe_r = (float(after_reclaim["high"].max()) - entry_price) / risk_price
            mae_r = (entry_price - float(after_reclaim["low"].min())) / risk_price
            close_r = (last_close - entry_price) / risk_price
        else:
            mfe_r = (entry_price - float(after_reclaim["low"].min())) / risk_price
            mae_r = (float(after_reclaim["high"].max()) - entry_price) / risk_price
            close_r = (entry_price - last_close) / risk_price
        base["mfe_r_after_second_reentry"] = mfe_r
        base["mae_r_after_second_reentry"] = mae_r
        base["close_r_after_second_reentry"] = close_r

    for idx, row in after_reclaim.iterrows():
        if not base["second_progress_after_reclaim"] and _hit_progress(row, direction, progress_price):
            base["second_progress_after_reclaim"] = 1
            base["second_progress_time"] = pd.Timestamp(row["bar_datetime"]).isoformat()
            base["second_progress_bar_index"] = int(idx)
        if _hit_stop(row, direction, stop_price):
            base["second_stop"] = 1
            base["second_stop_time"] = pd.Timestamp(row["bar_datetime"]).isoformat()
            base["second_stop_bar_index"] = int(idx)
            base["extra_loss_if_second_stop"] = sign * (stop_price - entry_price) * size * volume
            break

    base["audit_state"] = "flat_second_retry_failed" if base["second_stop"] else "open_after_second_reentry"
    return base


def build_event_audit() -> pd.DataFrame:
    minute_by_symbol = _prepare_minute_bars()
    events = _prepare_events()
    size_map = _prepare_size_map()
    rows: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        vt_symbol = str(event.get("vt_symbol") or "")
        day = _event_day(minute_by_symbol, vt_symbol, event["event_date"])
        size = float(size_map.get(vt_symbol, 1.0))
        rows.append(_scan_second_retry(event, day, size))
    return pd.DataFrame(rows)


def build_summary(event_audit: pd.DataFrame) -> pd.DataFrame:
    retry_failed_events = int(len(event_audit))
    second_reclaim_events = int(event_audit["second_reclaim"].sum()) if retry_failed_events else 0
    second_stop_events = int(event_audit["second_stop"].sum()) if retry_failed_events else 0
    open_after_second_reentry = int((event_audit["audit_state"].astype(str) == "open_after_second_reentry").sum())
    no_second_reclaim = int((event_audit["audit_state"].astype(str) == "no_second_reclaim").sum())
    extra_loss = float(event_audit["extra_loss_if_second_stop"].fillna(0).sum()) if retry_failed_events else 0.0
    open_eod_mtm = float(
        event_audit.loc[event_audit["audit_state"].astype(str).eq("open_after_second_reentry"), "eod_mark_to_market_pnl_after_second_reentry"]
        .fillna(0)
        .sum()
    )
    conservative_eod_proxy = extra_loss + open_eod_mtm
    return pd.DataFrame(
        [
            {
                "retry_failed_events": retry_failed_events,
                "second_reclaim_events": second_reclaim_events,
                "second_reclaim_rate_pct": second_reclaim_events / retry_failed_events * 100 if retry_failed_events else 0.0,
                "no_second_reclaim_events": no_second_reclaim,
                "second_stop_events": second_stop_events,
                "second_stop_rate_conditional_pct": second_stop_events / second_reclaim_events * 100 if second_reclaim_events else 0.0,
                "open_after_second_reentry_events": open_after_second_reentry,
                "second_progress_after_reclaim_events": int(event_audit["second_progress_after_reclaim"].sum())
                if retry_failed_events
                else 0,
                "extra_loss_if_second_stop": extra_loss,
                "open_after_second_reentry_eod_mtm": open_eod_mtm,
                "conservative_same_day_proxy": conservative_eod_proxy,
                "decision": "stage874_second_retry_not_promoted_no_engine",
            }
        ]
    )


def build_yearly(event_audit: pd.DataFrame) -> pd.DataFrame:
    if event_audit.empty:
        return pd.DataFrame()
    event_audit = event_audit.copy()
    event_audit["open_after_second_reentry_eod_mtm_component"] = np.where(
        event_audit["audit_state"].astype(str).eq("open_after_second_reentry"),
        event_audit["eod_mark_to_market_pnl_after_second_reentry"].fillna(0),
        0.0,
    )
    event_audit["all_second_reclaim_eod_mtm_component"] = np.where(
        event_audit["second_reclaim"].eq(1),
        event_audit["eod_mark_to_market_pnl_after_second_reentry"].fillna(0),
        0.0,
    )
    grouped = (
        event_audit.groupby("event_year", dropna=False)
        .agg(
            retry_failed_events=("event_id", "count"),
            second_reclaim_events=("second_reclaim", "sum"),
            second_stop_events=("second_stop", "sum"),
            open_after_second_reentry_events=("audit_state", lambda s: int((s.astype(str) == "open_after_second_reentry").sum())),
            second_progress_after_reclaim_events=("second_progress_after_reclaim", "sum"),
            extra_loss_if_second_stop=("extra_loss_if_second_stop", "sum"),
            open_after_second_reentry_eod_mtm=(
                "open_after_second_reentry_eod_mtm_component",
                lambda s: float(s.fillna(0).sum()),
            ),
            all_second_reclaim_eod_mtm=("all_second_reclaim_eod_mtm_component", "sum"),
        )
        .reset_index()
    )
    grouped["second_reclaim_rate_pct"] = grouped["second_reclaim_events"] / grouped["retry_failed_events"] * 100
    grouped["second_stop_rate_conditional_pct"] = np.where(
        grouped["second_reclaim_events"].gt(0),
        grouped["second_stop_events"] / grouped["second_reclaim_events"] * 100,
        0.0,
    )
    return grouped.sort_values("event_year").reset_index(drop=True)


def plot_summary(event_audit: pd.DataFrame, summary: pd.DataFrame) -> None:
    if event_audit.empty:
        return
    counts = event_audit["audit_state"].value_counts().reindex(
        ["no_second_reclaim", "flat_second_retry_failed", "open_after_second_reentry"], fill_value=0
    )
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    counts.plot(kind="bar", ax=axes[0], color=["#64748b", "#b91c1c", "#047857"])
    axes[0].set_title("C9 retry_failed -> same-day second retry states")
    axes[0].set_ylabel("events")
    axes[0].tick_params(axis="x", rotation=20)

    reclaim = event_audit[event_audit["second_reclaim"].eq(1)].copy()
    if reclaim.empty:
        axes[1].text(0.5, 0.5, "no second reclaim", ha="center", va="center")
    else:
        colors = np.where(reclaim["second_stop"].eq(1), "#b91c1c", "#047857")
        axes[1].bar(np.arange(len(reclaim)), reclaim["close_r_after_second_reentry"].fillna(0), color=colors)
        axes[1].axhline(0, color="#111827", linewidth=0.8)
        axes[1].set_title("EOD close R after second reclaim")
        axes[1].set_ylabel("R")
    fig.suptitle(
        f"Stage874 second retry audit: decision={summary.iloc[0]['decision'] if not summary.empty else 'n/a'}",
        fontsize=12,
    )
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
    rows = event_audit[event_audit["second_reclaim"].eq(1)].copy()
    if rows.empty:
        rows = event_audit.copy()
    rows["abs_eod_proxy"] = rows["eod_mark_to_market_pnl_after_second_reentry"].abs().fillna(0)
    rows = rows.sort_values(["second_reclaim", "second_stop", "abs_eod_proxy"], ascending=[False, False, False]).head(
        MAX_ATLAS_ROWS
    )

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
            axis.axhline(float(row["entry_price"]), color="#2563eb", linewidth=0.9, label="entry")
            axis.axhline(float(row["stop_price"]), color="#7c2d12", linewidth=0.9, linestyle=":", label="0.5R stop")
            axis.axhline(float(row["progress_price"]), color="#0f766e", linewidth=0.9, linestyle="--", label="+0.5R")
            markers = [
                ("first_stop_time", "#b91c1c", "first stop"),
                ("reentry_time", "#7c3aed", "first reentry"),
                ("retry_failed_time", "#7c2d12", "retry failed"),
                ("second_reclaim_time", "#047857", "second reclaim"),
                ("second_stop_time", "#111827", "second stop"),
            ]
            for column, color, label in markers:
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
                f"state={row['audit_state']} eodR={_safe_float(row.get('close_r_after_second_reentry'), 0):.2f}",
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
                    "second_reclaim_time": row["second_reclaim_time"],
                    "second_stop_time": row["second_stop_time"],
                    "close_r_after_second_reentry": row["close_r_after_second_reentry"],
                }
            )
        fig.suptitle("Stage874 C9 retry_failed second-retry minute-K atlas", fontsize=13)
        fig.tight_layout()
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    pd.DataFrame(manifest_rows).to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return paths


def write_report(event_audit: pd.DataFrame, summary: pd.DataFrame, yearly: pd.DataFrame, atlas_paths: list[Path]) -> None:
    top = event_audit[event_audit["second_reclaim"].eq(1)].copy()
    if not top.empty:
        top = top.sort_values("eod_mark_to_market_pnl_after_second_reentry", ascending=False)
    lines = [
        "# Stage874 C9 retry_failed 后同日第二次重试可行性审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{SOURCE_CANDIDATE}`",
        "- 阶段性质：只读法证；不改正式版、不改候选配置、不连接 CTP、不调用下单、不接真实引擎。",
        "",
        "## 外部调研判断",
        "",
        "- Turtle 规则体系把 entry、stop、exit、position sizing 拆开，并明确 whipsaw 是趋势系统的成本；这支持“错了先退、重新确认再进”的方向，但不支持事后加重试次数救参。",
        "- Backtrader 和 vn.py 的开源实现都说明 stop / stop trail / local stop order 是可执行语义；但第二次重试是否值得，必须由本仓库逐分钟路径和组合资金联动验证。",
        "- 我的判断：本阶段只审计 C9 的 `flat_retry_failed` 后是否存在自然的同日二次 reclaim。若样本小、失败率高或只能靠个别日内反弹，不进入真实引擎。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Yearly",
        "",
        _md_table(yearly, max_rows=20),
        "",
        "## Second Reclaim Events",
        "",
        _md_table(
            top[
                [
                    "event_date",
                    "vt_symbol",
                    "direction",
                    "entry_price",
                    "stop_price",
                    "volume",
                    "second_reclaim_time",
                    "second_stop_time",
                    "audit_state",
                    "extra_loss_if_second_stop",
                    "eod_mark_to_market_pnl_after_second_reentry",
                    "mfe_r_after_second_reentry",
                    "mae_r_after_second_reentry",
                    "close_r_after_second_reentry",
                ]
            ]
            if not top.empty
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
            "- 决策：`stage874_second_retry_not_promoted_no_engine`",
            "- 理由：C9 的 `flat_retry_failed` 只有 `25` 笔，其中同日第二次 reclaim 只有 `9` 笔；这 `9` 笔里 `7` 笔随后再次触发同一个 `0.5R` stop，二次重试条件失败率 `77.78%`。保守口径下，二次失败额外亏损 `-218,210`，仅 `2` 笔能保持到日内结束。",
            "- 下一步：不接 Stage875 二次重试真实引擎，不扫重试次数。若继续本线，应回到账户/持仓层生存问题，寻找不直接砍右尾、也不增加 whipsaw 成本的低自由度规则。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    event_audit = build_event_audit()
    summary = build_summary(event_audit)
    yearly = build_yearly(event_audit)
    plot_summary(event_audit, summary)
    atlas_paths = plot_atlas(event_audit)

    event_audit.to_csv(EVENT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_PATH, index=False, encoding="utf-8-sig")
    write_report(event_audit, summary, yearly, atlas_paths)

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
        "audit_scope": "C9 flat_retry_failed events, same-day minute path after retry_failed_time",
        "summary": summary.to_dict("records")[0] if not summary.empty else {},
        "decision": "stage874_second_retry_not_promoted_no_engine",
        "overfit_reflection": (
            "本阶段没有把二次重试接入真实引擎，也没有扫描重试次数、R、小数阈值、品种、方向或年份；"
            "只用 C9 已发生的 retry_failed 事件检查自然同日第二次 reclaim 是否足够强。"
        ),
        "continue_value": (
            "二次重试分支没有继续价值；若继续本线，应回到账户/持仓层生存问题，"
            "而不是增加 whipsaw 次数。"
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
