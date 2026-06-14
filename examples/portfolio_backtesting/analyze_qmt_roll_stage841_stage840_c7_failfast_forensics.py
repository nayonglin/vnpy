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
STAGE = "Stage841"
MODEL_TAG = "stage841_stage840_c7_failfast_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage841_stage840_c7_failfast_forensics"

STAGE840_TAG = "stage840_stage830_c4_120m_failfast_engine_v1"
STAGE840_PREFIX = "qmt_roll_stage840_stage830_c4_120m_failfast_engine"
STAGE830_TAG = "stage830_stage827_c2_broker10_margin_cap_v1"
STAGE830_PREFIX = "qmt_roll_stage830_stage827_c2_broker10_margin_cap"
STAGE825_TAG = "stage825_stage819_intraday_rule_forensics_v1"
STAGE825_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"

FAILFAST_EVENTS_PATH = OUTPUT_DIR / f"{STAGE840_PREFIX}_failfast_events_{STAGE840_TAG}.csv"
STAGE840_CLOSED_PATH = OUTPUT_DIR / f"{STAGE840_PREFIX}_closed_lots_{STAGE840_TAG}.csv"
STAGE830_C4_CLOSED_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_closed_lots_{STAGE830_TAG}.csv"
STAGE825_FEATURES_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_intraday_features_{STAGE825_TAG}.csv"

EVENT_DIAGNOSTICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_diagnostics_{MODEL_TAG}.csv"
BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_stats_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
CHART_PATH_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

PER_PAGE = 4


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def _parse_datetime(value: Any) -> pd.Timestamp:
    text = str(value)
    if text.endswith("+08:00"):
        text = text[:-6]
    ts = pd.to_datetime(text, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    return pd.Timestamp(ts).tz_localize(None) if pd.Timestamp(ts).tzinfo is not None else pd.Timestamp(ts)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _prepare_events() -> pd.DataFrame:
    events = _load_csv(FAILFAST_EVENTS_PATH)
    events["event_datetime"] = events["datetime"].map(_parse_datetime)
    events["entry_date"] = events["event_datetime"].dt.normalize()
    events["entry_date_text"] = events["entry_date"].dt.strftime("%Y-%m-%d")
    events["hit_datetime"] = events["hit_time"].map(_parse_datetime)
    events["hit_time_text"] = events["hit_datetime"].dt.strftime("%Y-%m-%d %H:%M")
    for column in ["entry_price", "stop_price", "progress_price", "risk_price", "volume"]:
        events[column] = pd.to_numeric(events.get(column), errors="coerce")
    events["event_id"] = np.arange(1, len(events) + 1)
    return events


def _prepare_closed(path: Path) -> pd.DataFrame:
    closed = _load_csv(path)
    closed["entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce").dt.normalize()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce").dt.normalize()
    for column in ["entry_price", "exit_price", "volume", "size", "realized_pnl", "risk_amount", "r_multiple"]:
        closed[column] = pd.to_numeric(closed.get(column), errors="coerce")
    return closed


def _match_lot(event: pd.Series, closed: pd.DataFrame, *, require_exit_reason: str | None = None) -> tuple[str, pd.Series | None]:
    data = closed[
        closed["vt_symbol"].astype(str).eq(str(event["vt_symbol"]))
        & closed["direction"].astype(str).eq(str(event["direction"]))
        & closed["entry_date"].eq(event["entry_date"])
    ].copy()
    if require_exit_reason is not None and "exit_reason" in data.columns:
        data = data[data["exit_reason"].astype(str).eq(require_exit_reason)].copy()
    if data.empty:
        return "no_same_symbol_direction_date", None
    data["entry_price_abs_diff"] = (pd.to_numeric(data["entry_price"], errors="coerce") - float(event["entry_price"])).abs()
    data["volume_abs_diff"] = (pd.to_numeric(data["volume"], errors="coerce") - float(event["volume"])).abs()
    exact = data[data["entry_price_abs_diff"].le(1e-8)].copy()
    if not exact.empty:
        exact.sort_values(["volume_abs_diff", "lot_id"], inplace=True)
        return "exact_entry_price", exact.iloc[0]
    data.sort_values(["entry_price_abs_diff", "volume_abs_diff", "lot_id"], inplace=True)
    return "nearest_entry_price", data.iloc[0]


def _direction_sign(direction: str) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _entry_day_features(event: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(event["vt_symbol"])
    direction = str(event["direction"])
    entry_date = pd.Timestamp(event["entry_date"]).normalize()
    entry_price = float(event["entry_price"])
    stop_price = float(event["stop_price"])
    progress_price = float(event["progress_price"])
    risk_price = abs(float(event["risk_price"]))
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    entry_day = bars[bars["bar_date"].eq(entry_date)].copy() if not bars.empty else pd.DataFrame()
    result: dict[str, Any] = {
        "minute_coverage_state": "entry_day_covered" if not entry_day.empty else "missing_entry_day_minutes",
        "entry_day_minute_bars": int(len(entry_day)),
        "hit_bar_index": np.nan,
        "entry_day_close_return_r": np.nan,
        "post_hit_reclaim_entry": 0,
        "post_hit_reach_0p5r_progress": 0,
        "post_hit_reach_1r_target": 0,
        "post_hit_max_mfe_r": np.nan,
        "post_hit_max_adverse_r": np.nan,
        "opening_range15_direction_break_after_hit": 0,
    }
    if entry_day.empty or entry_price <= 0 or risk_price <= 0:
        return result

    hit_dt = event.get("hit_datetime", pd.NaT)
    if pd.notna(hit_dt):
        matches = entry_day[pd.to_datetime(entry_day["bar_datetime"], errors="coerce").eq(hit_dt)]
        if not matches.empty:
            result["hit_bar_index"] = int(matches.index[0])

    sign = _direction_sign(direction)
    close_price = float(entry_day["close"].iloc[-1])
    result["entry_day_close_return_r"] = sign * (close_price - entry_price) / risk_price

    if pd.isna(result["hit_bar_index"]):
        after = entry_day.iloc[0:0].copy()
    else:
        after = entry_day.iloc[int(result["hit_bar_index"]) + 1 :].copy()
    if not after.empty:
        if direction == "long":
            result["post_hit_reclaim_entry"] = int(pd.to_numeric(after["high"], errors="coerce").ge(entry_price).any())
            result["post_hit_reach_0p5r_progress"] = int(pd.to_numeric(after["high"], errors="coerce").ge(progress_price).any())
            result["post_hit_reach_1r_target"] = int(pd.to_numeric(after["high"], errors="coerce").ge(entry_price + risk_price).any())
            result["post_hit_max_mfe_r"] = float((pd.to_numeric(after["high"], errors="coerce").max() - entry_price) / risk_price)
            result["post_hit_max_adverse_r"] = float((entry_price - pd.to_numeric(after["low"], errors="coerce").min()) / risk_price)
        else:
            result["post_hit_reclaim_entry"] = int(pd.to_numeric(after["low"], errors="coerce").le(entry_price).any())
            result["post_hit_reach_0p5r_progress"] = int(pd.to_numeric(after["low"], errors="coerce").le(progress_price).any())
            result["post_hit_reach_1r_target"] = int(pd.to_numeric(after["low"], errors="coerce").le(entry_price - risk_price).any())
            result["post_hit_max_mfe_r"] = float((entry_price - pd.to_numeric(after["low"], errors="coerce").min()) / risk_price)
            result["post_hit_max_adverse_r"] = float((pd.to_numeric(after["high"], errors="coerce").max() - entry_price) / risk_price)

    if len(entry_day) >= 15 and not after.empty:
        opening = entry_day.head(15)
        if direction == "long":
            result["opening_range15_direction_break_after_hit"] = int(
                pd.to_numeric(after["high"], errors="coerce").ge(float(opening["high"].max())).any()
            )
        else:
            result["opening_range15_direction_break_after_hit"] = int(
                pd.to_numeric(after["low"], errors="coerce").le(float(opening["low"].min())).any()
            )
    return result


def _classify(row: pd.Series) -> str:
    if str(row.get("c4_match_quality", "")).startswith("no_"):
        return "path_specific_unmatched"
    c4_pnl = _safe_float(row.get("c4_realized_pnl"))
    c7_pnl = _safe_float(row.get("c7_realized_pnl"))
    if not np.isfinite(c4_pnl) or not np.isfinite(c7_pnl):
        return "unclassified"
    if c4_pnl > 0 and c7_pnl < c4_pnl:
        return "killed_c4_winner"
    if c4_pnl < 0 and c7_pnl > c4_pnl:
        return "saved_c4_loser"
    if c4_pnl < 0 and c7_pnl <= c4_pnl:
        return "worse_than_c4_loser"
    if c4_pnl == 0:
        return "c4_flat"
    return "other_matched"


def _build_diagnostics() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events = _prepare_events()
    c7_closed = _prepare_closed(STAGE840_CLOSED_PATH)
    c4_closed = _prepare_closed(STAGE830_C4_CLOSED_PATH)
    stage825_features = _load_csv(STAGE825_FEATURES_PATH)
    stage825_features["entry_date"] = pd.to_datetime(stage825_features["entry_date"], errors="coerce").dt.normalize()

    vt_symbols = set(events["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)

    rows: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        c7_match_quality, c7_lot = _match_lot(
            event,
            c7_closed,
            require_exit_reason="stage840_intraday_120m_05r_failfast_stop",
        )
        c4_match_quality, c4_lot = _match_lot(event, c4_closed)
        baseline_match_quality, baseline_lot = _match_lot(event, stage825_features)
        features = _entry_day_features(event, minute_by_symbol)
        row: dict[str, Any] = {
            "event_id": int(event["event_id"]),
            "datetime": event["event_datetime"],
            "entry_date": event["entry_date"],
            "hit_time": event["hit_datetime"],
            "vt_symbol": str(event["vt_symbol"]),
            "product_vt_symbol": str(event["product_vt_symbol"]),
            "direction": str(event["direction"]),
            "entry_price": float(event["entry_price"]),
            "stop_price": float(event["stop_price"]),
            "progress_price": float(event["progress_price"]),
            "risk_price": float(event["risk_price"]),
            "volume": float(event["volume"]),
            "c7_match_quality": c7_match_quality,
            "c4_match_quality": c4_match_quality,
            "baseline_match_quality": baseline_match_quality,
        }
        for prefix, lot in [("c7", c7_lot), ("c4", c4_lot), ("baseline", baseline_lot)]:
            if lot is None:
                continue
            for column in [
                "lot_id",
                "exit_date",
                "exit_price",
                "volume",
                "realized_pnl",
                "risk_amount",
                "r_multiple",
                "exit_reason",
                "signal",
                "mfe_r",
                "mae_r",
                "entry_day_first_1p0r_outcome",
                "entry_day_close_return_pct",
            ]:
                if column in lot.index:
                    row[f"{prefix}_{column}"] = lot[column]
        row.update(features)
        rows.append(row)

    diagnostics = pd.DataFrame(rows)
    diagnostics["c7_vs_c4_pnl_delta"] = pd.to_numeric(diagnostics.get("c7_realized_pnl"), errors="coerce") - pd.to_numeric(
        diagnostics.get("c4_realized_pnl"), errors="coerce"
    )
    diagnostics["c7_vs_baseline_pnl_delta"] = pd.to_numeric(
        diagnostics.get("c7_realized_pnl"), errors="coerce"
    ) - pd.to_numeric(diagnostics.get("baseline_realized_pnl"), errors="coerce")
    diagnostics["forensic_bucket"] = diagnostics.apply(_classify, axis=1)
    diagnostics["recovered_after_stop_shape"] = np.select(
        [
            diagnostics["post_hit_reach_1r_target"].eq(1),
            diagnostics["post_hit_reach_0p5r_progress"].eq(1),
            diagnostics["post_hit_reclaim_entry"].eq(1),
        ],
        ["post_hit_reached_1r", "post_hit_reached_0p5r", "post_hit_reclaimed_entry"],
        default="no_same_day_recovery",
    )
    bucket = _bucket_stats(diagnostics)
    summary = _summary(diagnostics)
    return diagnostics, bucket, summary


def _bucket_stats(diagnostics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group_col in ["forensic_bucket", "recovered_after_stop_shape", "product_vt_symbol", "direction"]:
        for value, group in diagnostics.groupby(group_col, dropna=False):
            rows.append(
                {
                    "group_col": group_col,
                    "group_value": str(value),
                    "events": int(len(group)),
                    "c4_matched_events": int((~group["c4_match_quality"].astype(str).str.startswith("no_")).sum()),
                    "c4_total_pnl": float(pd.to_numeric(group.get("c4_realized_pnl"), errors="coerce").sum()),
                    "c7_total_pnl": float(pd.to_numeric(group.get("c7_realized_pnl"), errors="coerce").sum()),
                    "c7_vs_c4_delta": float(pd.to_numeric(group.get("c7_vs_c4_pnl_delta"), errors="coerce").sum()),
                    "post_hit_reclaim_entry_events": int(pd.to_numeric(group.get("post_hit_reclaim_entry"), errors="coerce").fillna(0).sum()),
                    "post_hit_reach_0p5r_events": int(
                        pd.to_numeric(group.get("post_hit_reach_0p5r_progress"), errors="coerce").fillna(0).sum()
                    ),
                    "post_hit_reach_1r_events": int(pd.to_numeric(group.get("post_hit_reach_1r_target"), errors="coerce").fillna(0).sum()),
                    "median_post_hit_mfe_r": float(pd.to_numeric(group.get("post_hit_max_mfe_r"), errors="coerce").median()),
                    "median_entry_day_close_r": float(pd.to_numeric(group.get("entry_day_close_return_r"), errors="coerce").median()),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["group_col", "c7_vs_c4_delta"], ascending=[True, True], inplace=True)
    return result


def _summary(diagnostics: pd.DataFrame) -> pd.DataFrame:
    matched = diagnostics[~diagnostics["c4_match_quality"].astype(str).str.startswith("no_")].copy()
    killed = matched[matched["forensic_bucket"].eq("killed_c4_winner")]
    saved = matched[matched["forensic_bucket"].eq("saved_c4_loser")]
    rows = [
        {
            "events": int(len(diagnostics)),
            "c4_matched_events": int(len(matched)),
            "path_specific_unmatched_events": int(diagnostics["forensic_bucket"].eq("path_specific_unmatched").sum()),
            "killed_c4_winner_events": int(len(killed)),
            "saved_c4_loser_events": int(len(saved)),
            "matched_c4_total_pnl": float(pd.to_numeric(matched.get("c4_realized_pnl"), errors="coerce").sum()),
            "matched_c7_total_pnl": float(pd.to_numeric(matched.get("c7_realized_pnl"), errors="coerce").sum()),
            "matched_c7_vs_c4_delta": float(pd.to_numeric(matched.get("c7_vs_c4_pnl_delta"), errors="coerce").sum()),
            "killed_winner_delta": float(pd.to_numeric(killed.get("c7_vs_c4_pnl_delta"), errors="coerce").sum()),
            "saved_loser_delta": float(pd.to_numeric(saved.get("c7_vs_c4_pnl_delta"), errors="coerce").sum()),
            "post_hit_reclaim_entry_events": int(pd.to_numeric(diagnostics.get("post_hit_reclaim_entry"), errors="coerce").fillna(0).sum()),
            "post_hit_reach_0p5r_events": int(pd.to_numeric(diagnostics.get("post_hit_reach_0p5r_progress"), errors="coerce").fillna(0).sum()),
            "post_hit_reach_1r_events": int(pd.to_numeric(diagnostics.get("post_hit_reach_1r_target"), errors="coerce").fillna(0).sum()),
            "decision": "stage841_diagnostic_only_c7_failfast_hurts_by_killing_recoverable_entries",
        }
    ]
    return pd.DataFrame(rows)


def _plot_event(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row["vt_symbol"])
    direction = str(row["direction"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    entry_day = bars[bars["bar_date"].eq(entry_date)].copy() if not bars.empty else pd.DataFrame()
    record = {
        "event_id": int(row["event_id"]),
        "vt_symbol": vt_symbol,
        "entry_date": entry_date.strftime("%Y-%m-%d"),
        "chart_missing_minutes": int(entry_day.empty),
    }
    if entry_day.empty:
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            f"missing entry-day minutes\n{vt_symbol} {direction} {entry_date:%Y-%m-%d}",
            ha="center",
            va="center",
            color="#991b1b",
            fontsize=10,
        )
        return record

    window = entry_day.head(240).copy().reset_index(drop=True)
    s825._plot_candles(ax, window)
    x = np.arange(len(window))
    ax.plot(x, window["close"].rolling(5).mean(), color="#f59e0b", linewidth=0.8, alpha=0.8)
    ax.plot(x, window["close"].rolling(20).mean(), color="#2563eb", linewidth=0.8, alpha=0.75)
    entry_price = float(row["entry_price"])
    stop_price = float(row["stop_price"])
    progress_price = float(row["progress_price"])
    risk_price = float(row["risk_price"])
    sign = _direction_sign(direction)
    ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.9)
    ax.axhline(stop_price, color="#dc2626", linewidth=1.0, linestyle="--", alpha=0.9)
    ax.axhline(progress_price, color="#16a34a", linewidth=0.9, linestyle=":", alpha=0.9)
    ax.axhline(entry_price + sign * risk_price, color="#16a34a", linewidth=0.9, alpha=0.8)
    hit_index = row.get("hit_bar_index")
    if pd.notna(hit_index) and int(hit_index) < len(window):
        ax.axvline(int(hit_index), color="#dc2626", linewidth=1.0, alpha=0.85)
    if len(window) >= 15:
        opening = window.head(15)
        ax.axhline(float(opening["high"].max()), color="#7c3aed", linewidth=0.75, linestyle="--", alpha=0.7)
        ax.axhline(float(opening["low"].min()), color="#7c3aed", linewidth=0.75, linestyle="--", alpha=0.7)
        ax.axvspan(0, 14, color="#fef3c7", alpha=0.22)
    ticks = np.linspace(0, len(window) - 1, num=min(7, len(window)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    ax.tick_params(axis="y", labelsize=7)
    title = (
        f"#{int(row['event_id'])} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
        f"{row.get('forensic_bucket','')} delta_vs_C4={_safe_float(row.get('c7_vs_c4_pnl_delta')):,.0f} "
        f"recover={row.get('recovered_after_stop_shape','')}"
    )
    ax.set_title(title, fontsize=8.5, loc="left")
    return record


def _plot_atlas(diagnostics: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    vt_symbols = set(diagnostics["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    ordered = diagnostics.copy()
    ordered["sort_delta"] = pd.to_numeric(ordered["c7_vs_c4_pnl_delta"], errors="coerce").fillna(0.0)
    ordered.sort_values(["sort_delta", "event_id"], ascending=[True, True], inplace=True)
    total_pages = int(math.ceil(len(ordered) / PER_PAGE)) if len(ordered) else 0
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        part = ordered.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.3 * len(part))), constrained_layout=True)
        if len(part) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, part.iterrows(), strict=False):
            rec = _plot_event(ax, row, minute_by_symbol)
            rec["chart_page"] = page
            records.append(rec)
        fig.suptitle(
            (
                "Stage841 C7 fail-fast event atlas "
                "(blue=entry, red dashed=-0.5R stop, green dotted=+0.5R, green=+1R, purple=OR15)"
            ),
            fontsize=13,
        )
        path = Path(str(CHART_PATH_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _write_report(summary: pd.DataFrame, bucket: pd.DataFrame, diagnostics: pd.DataFrame, atlas_paths: list[Path]) -> None:
    lines = [
        "# Stage841 C7 Fail-Fast事件误伤法证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读数据分析 + 分钟K视觉法证；不新增规则、不跑新引擎、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- 公开资料只支持止损必须预定义、仓位必须受控；趋势跟随系统的过紧初始止损容易产生 whipsaw，不能把初期 MAE 直接等同于错误入场。",
        "- 本阶段只解释 Stage840 C7 为什么失败，不继续扫 fail-fast 时间窗、R 倍数或重试次数。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## Bucket Stats",
        "",
        _md_table(bucket, max_rows=40),
        "",
        "## Worst Event Deltas",
        "",
        _md_table(
            diagnostics.sort_values("c7_vs_c4_pnl_delta", ascending=True).head(15)[
                [
                    "event_id",
                    "vt_symbol",
                    "direction",
                    "entry_date",
                    "volume",
                    "forensic_bucket",
                    "recovered_after_stop_shape",
                    "c4_realized_pnl",
                    "c7_realized_pnl",
                    "c7_vs_c4_pnl_delta",
                    "post_hit_max_mfe_r",
                    "entry_day_close_return_r",
                ]
            ],
            max_rows=15,
        ),
        "",
        "## Atlas",
        "",
        *[f"- atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- C7 的问题不是止损执行错误，而是触发条件太粗：许多事件止损后当天还能重新站回入场、到达 0.5R 或 1R，说明它把趋势初期抖动当成错误。",
        "- 下一步不能继续调 `120m/0.5R`，应该寻找更低误伤的结构破坏条件，例如止损后不能重新站回入场、不能重新突破 OR15，或持仓后方向结构连续破坏；这些也必须先做只读法证再冻结引擎。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    diagnostics, bucket, summary = _build_diagnostics()
    atlas_paths, atlas_manifest = _plot_atlas(diagnostics)

    diagnostics.to_csv(EVENT_DIAGNOSTICS_PATH, index=False, encoding="utf-8-sig")
    bucket.to_csv(BUCKET_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, bucket, diagnostics, atlas_paths)

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "formal_ab_triggered": False,
        "ctp_connected": False,
        "order_api_called": False,
        "decision": "stage841_diagnostic_only_c7_failfast_hurts_by_killing_recoverable_entries",
        "summary": summary.to_dict("records"),
        "overfit_reflection": (
            "This stage analyzes the already-failed C7 events only. It does not tune windows, R multiples, products, "
            "directions, years, or retry counts."
        ),
        "continue_value": (
            "Use the diagnostics to design a lower-degree structural-break hypothesis, not another fail-fast parameter scan."
        ),
        "outputs": {
            "event_diagnostics": str(EVENT_DIAGNOSTICS_PATH),
            "bucket_stats": str(BUCKET_PATH),
            "summary": str(SUMMARY_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("summary")
    print(summary.to_string(index=False))
    print("bucket")
    print(bucket.to_string(index=False))


if __name__ == "__main__":
    main()
