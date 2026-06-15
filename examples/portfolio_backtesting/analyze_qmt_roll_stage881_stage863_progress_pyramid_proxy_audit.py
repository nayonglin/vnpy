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
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage881"
MODEL_TAG = "stage881_stage863_progress_pyramid_proxy_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage881_stage863_progress_pyramid_proxy_audit"

STAGE861_PREFIX = "qmt_roll_stage861_stage860_full_visual_atlas"
STAGE861_TAG = "stage861_stage860_full_visual_atlas_v1"
STAGE863_PREFIX = "qmt_roll_stage863_stage847_c10_budget_lock_engine"
STAGE863_TAG = "stage863_stage847_c10_budget_lock_engine_v1"

FULL_MINUTE_BARS_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_full_minute_bars_{STAGE861_TAG}.csv"
STAGE863_CLOSED_LOTS_PATH = OUTPUT_DIR / f"{STAGE863_PREFIX}_closed_lots_{STAGE863_TAG}.csv"

FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
STATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

C9_ARM = s847.C9_ARM
PYRAMID_PROGRESS_R = 0.5
PYRAMID_ADD_VOLUME_MULTIPLIER = 1.0
PER_PAGE = 4
MAX_ATLAS_ROWS = 16


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


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _prepare_closed_lots() -> pd.DataFrame:
    data = _load_required_csv(STAGE863_CLOSED_LOTS_PATH).copy()
    data = data[data["arm"].astype(str).eq(C9_ARM)].copy()
    if data.empty:
        raise RuntimeError(f"no C9 closed lots in {STAGE863_CLOSED_LOTS_PATH}")
    for column in ["entry_date", "exit_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    numeric_columns = [
        "lot_id",
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "winner",
        "big_winner",
        "stop_distance",
        "entry_risk_distance_pct",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    data["winner"] = data["winner"].fillna(data["realized_pnl"].fillna(0).gt(0).astype(int))
    data["big_winner"] = data["big_winner"].fillna(0).astype(int)
    return data.reset_index(drop=True)


def _load_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    data = _load_required_csv(FULL_MINUTE_BARS_PATH)
    data = data[data["vt_symbol"].astype(str).isin(vt_symbols)].copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close"]).reset_index(
        drop=True
    )


def _risk_price(row: pd.Series) -> float:
    stop_distance = _safe_float(row.get("stop_distance"))
    if stop_distance > 0:
        return stop_distance
    risk_amount = _safe_float(row.get("risk_amount"))
    size = _safe_float(row.get("size"))
    volume = _safe_float(row.get("volume"))
    if risk_amount > 0 and size > 0 and volume > 0:
        return risk_amount / (size * volume)
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("entry_risk_distance_pct"))
    if entry_price > 0 and risk_pct > 0:
        return entry_price * risk_pct
    return np.nan


def _first_half_r_event(
    day: pd.DataFrame,
    *,
    direction: str,
    entry_price: float,
    risk_price: float,
) -> tuple[str, int, str]:
    sign = _direction_sign(direction)
    progress_price = entry_price + sign * PYRAMID_PROGRESS_R * risk_price
    adverse_price = entry_price - sign * PYRAMID_PROGRESS_R * risk_price
    for idx, item in enumerate(day.itertuples(index=False)):
        if direction == "long":
            progress_hit = float(item.high) >= progress_price
            adverse_hit = float(item.low) <= adverse_price
        else:
            progress_hit = float(item.low) <= progress_price
            adverse_hit = float(item.high) >= adverse_price
        if progress_hit and adverse_hit:
            return "ambiguous_same_bar", idx, pd.Timestamp(item.bar_datetime).isoformat()
        if adverse_hit:
            return "adverse_first", idx, pd.Timestamp(item.bar_datetime).isoformat()
        if progress_hit:
            return "progress_first", idx, pd.Timestamp(item.bar_datetime).isoformat()
    return "neither", -1, ""


def _pyramid_proxy_for_lot(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    lot_id = int(_safe_float(row.get("lot_id"), -1))
    vt_symbol = str(row.get("vt_symbol", ""))
    direction = str(row.get("direction", ""))
    entry_date = pd.Timestamp(row.get("entry_date")).normalize()
    entry_price = _safe_float(row.get("entry_price"))
    exit_price = _safe_float(row.get("exit_price"))
    volume = _safe_float(row.get("volume"))
    size = _safe_float(row.get("size"))
    risk_price = _risk_price(row)
    sign = _direction_sign(direction)
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    if bars.empty or "bar_date" not in bars.columns:
        day = pd.DataFrame()
    else:
        day = bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
    base = {
        "lot_id": lot_id,
        "vt_symbol": vt_symbol,
        "product": str(row.get("product", "")),
        "direction": direction,
        "entry_date": entry_date.strftime("%Y-%m-%d") if pd.notna(entry_date) else "",
        "exit_date": pd.Timestamp(row.get("exit_date")).strftime("%Y-%m-%d") if pd.notna(row.get("exit_date")) else "",
        "entry_price": entry_price,
        "exit_price": exit_price,
        "volume": volume,
        "size": size,
        "risk_price": risk_price,
        "realized_pnl": _safe_float(row.get("realized_pnl"), 0.0),
        "r_multiple": _safe_float(row.get("r_multiple")),
        "winner": int(_safe_float(row.get("winner"), 0.0)),
        "big_winner": int(_safe_float(row.get("big_winner"), 0.0)),
        "exit_reason": str(row.get("exit_reason", "")),
        "entry_day_minute_bars": int(len(day)),
        "first_05r_state": "invalid_or_missing",
        "first_05r_index": -1,
        "first_05r_time": "",
        "pyramid_candidate": 0,
        "pyramid_state": "not_candidate",
        "pyramid_add_price": np.nan,
        "pyramid_stop_price": entry_price,
        "pyramid_exit_price": np.nan,
        "pyramid_exit_time": "",
        "pyramid_add_volume": np.nan,
        "pyramid_risk_cash": np.nan,
        "pyramid_proxy_pnl": 0.0,
        "pyramid_proxy_r": np.nan,
    }
    if day.empty or entry_price <= 0 or exit_price <= 0 or volume <= 0 or size <= 0 or risk_price <= 0:
        return base

    first_state, event_idx, event_time = _first_half_r_event(
        day,
        direction=direction,
        entry_price=entry_price,
        risk_price=risk_price,
    )
    base.update(
        {
            "first_05r_state": first_state,
            "first_05r_index": event_idx,
            "first_05r_time": event_time,
        }
    )
    if first_state != "progress_first":
        return base

    add_price = entry_price + sign * PYRAMID_PROGRESS_R * risk_price
    stop_price = entry_price
    add_volume = volume * PYRAMID_ADD_VOLUME_MULTIPLIER
    risk_cash = abs(add_price - stop_price) * size * add_volume
    if risk_cash <= 0:
        return base

    exit_price_for_add = exit_price
    exit_time = ""
    pyramid_state = "held_to_original_exit"

    # Conservative same-bar check: if the progress bar also trades back to the add-on stop,
    # the add-on is considered stopped immediately.
    for idx in range(event_idx, len(day)):
        item = day.iloc[idx]
        if direction == "long":
            stop_hit = float(item["low"]) <= stop_price
        else:
            stop_hit = float(item["high"]) >= stop_price
        if stop_hit:
            exit_price_for_add = stop_price
            exit_time = pd.Timestamp(item["bar_datetime"]).isoformat()
            pyramid_state = "same_bar_stop" if idx == event_idx else "entry_day_stop"
            break

    proxy_pnl = sign * (exit_price_for_add - add_price) * size * add_volume
    base.update(
        {
            "pyramid_candidate": 1,
            "pyramid_state": pyramid_state,
            "pyramid_add_price": add_price,
            "pyramid_stop_price": stop_price,
            "pyramid_exit_price": exit_price_for_add,
            "pyramid_exit_time": exit_time,
            "pyramid_add_volume": add_volume,
            "pyramid_risk_cash": risk_cash,
            "pyramid_proxy_pnl": proxy_pnl,
            "pyramid_proxy_r": proxy_pnl / risk_cash if risk_cash > 0 else np.nan,
        }
    )
    return base


def _build_features(closed_lots: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    minute_by_symbol = s825._minute_groups(minute_bars)
    rows = [_pyramid_proxy_for_lot(row, minute_by_symbol) for _, row in closed_lots.iterrows()]
    return pd.DataFrame(rows)


def _state_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for state, group in features.groupby("pyramid_state", dropna=False):
        pnl = pd.to_numeric(group["pyramid_proxy_pnl"], errors="coerce").fillna(0.0)
        original = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "pyramid_state": str(state),
                "lots": int(len(group)),
                "candidate_lots": int(pd.to_numeric(group["pyramid_candidate"], errors="coerce").fillna(0).sum()),
                "original_pnl": float(original.sum()),
                "pyramid_proxy_pnl": float(pnl.sum()),
                "pyramid_proxy_r_median": float(pd.to_numeric(group["pyramid_proxy_r"], errors="coerce").median()),
                "positive_pyramid_lots": int(pnl.gt(0).sum()),
                "negative_pyramid_lots": int(pnl.lt(0).sum()),
                "winner_lots": int(pd.to_numeric(group["winner"], errors="coerce").fillna(0).sum()),
                "big_winner_lots": int(pd.to_numeric(group["big_winner"], errors="coerce").fillna(0).sum()),
                "risk_cash": float(pd.to_numeric(group["pyramid_risk_cash"], errors="coerce").fillna(0).sum()),
            }
        )
    order = {
        "held_to_original_exit": 0,
        "entry_day_stop": 1,
        "same_bar_stop": 2,
        "not_candidate": 3,
    }
    result = pd.DataFrame(rows)
    if not result.empty:
        result["sort_key"] = result["pyramid_state"].map(order).fillna(99)
        result = result.sort_values(["sort_key", "lots"], ascending=[True, False]).drop(columns=["sort_key"])
    return result.reset_index(drop=True)


def _yearly_summary(features: pd.DataFrame) -> pd.DataFrame:
    temp = features.copy()
    temp["entry_year"] = pd.to_datetime(temp["entry_date"], errors="coerce").dt.year
    temp["pyramid_candidate"] = pd.to_numeric(temp["pyramid_candidate"], errors="coerce").fillna(0).astype(int)
    temp["pyramid_proxy_pnl"] = pd.to_numeric(temp["pyramid_proxy_pnl"], errors="coerce").fillna(0.0)
    temp["realized_pnl"] = pd.to_numeric(temp["realized_pnl"], errors="coerce").fillna(0.0)
    return (
        temp.groupby("entry_year", dropna=False)
        .agg(
            lots=("lot_id", "size"),
            candidate_lots=("pyramid_candidate", "sum"),
            original_pnl=("realized_pnl", "sum"),
            pyramid_proxy_pnl=("pyramid_proxy_pnl", "sum"),
            positive_pyramid_lots=("pyramid_proxy_pnl", lambda s: int(pd.to_numeric(s, errors="coerce").gt(0).sum())),
            negative_pyramid_lots=("pyramid_proxy_pnl", lambda s: int(pd.to_numeric(s, errors="coerce").lt(0).sum())),
        )
        .reset_index()
    )


def _overall_summary(features: pd.DataFrame) -> dict[str, Any]:
    candidate = features[features["pyramid_candidate"].eq(1)].copy()
    base_total = float(pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0).sum())
    delta = float(pd.to_numeric(features["pyramid_proxy_pnl"], errors="coerce").fillna(0.0).sum())
    return {
        "all_lots": int(len(features)),
        "valid_entry_day_lots": int(features["entry_day_minute_bars"].gt(0).sum()),
        "pyramid_candidate_lots": int(len(candidate)),
        "pyramid_candidate_pct": float(len(candidate) / len(features) * 100.0) if len(features) else 0.0,
        "base_closed_lot_pnl": base_total,
        "pyramid_proxy_delta": delta,
        "proxy_closed_lot_pnl": base_total + delta,
        "candidate_original_pnl": float(pd.to_numeric(candidate["realized_pnl"], errors="coerce").fillna(0.0).sum()),
        "candidate_big_winner_lots": int(pd.to_numeric(candidate["big_winner"], errors="coerce").fillna(0).sum()),
        "held_to_original_exit_lots": int(candidate["pyramid_state"].eq("held_to_original_exit").sum()),
        "entry_day_stop_lots": int(candidate["pyramid_state"].eq("entry_day_stop").sum()),
        "same_bar_stop_lots": int(candidate["pyramid_state"].eq("same_bar_stop").sum()),
        "pyramid_positive_lots": int(pd.to_numeric(candidate["pyramid_proxy_pnl"], errors="coerce").fillna(0).gt(0).sum()),
        "pyramid_negative_lots": int(pd.to_numeric(candidate["pyramid_proxy_pnl"], errors="coerce").fillna(0).lt(0).sum()),
        "pyramid_risk_cash": float(pd.to_numeric(candidate["pyramid_risk_cash"], errors="coerce").fillna(0.0).sum()),
    }


def _plot_summary_chart(state_summary: pd.DataFrame, yearly: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(17, 5.5), constrained_layout=True)
    colors = np.where(state_summary["pyramid_proxy_pnl"].ge(0), "#16a34a", "#dc2626")
    axes[0].bar(state_summary["pyramid_state"], state_summary["pyramid_proxy_pnl"], color=colors)
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("Pyramid proxy PnL by state")
    axes[0].tick_params(axis="x", rotation=25, labelsize=8)
    axes[0].grid(axis="y", alpha=0.2)

    colors2 = np.where(yearly["pyramid_proxy_pnl"].ge(0), "#16a34a", "#dc2626")
    axes[1].bar(yearly["entry_year"].astype(str), yearly["pyramid_proxy_pnl"], color=colors2)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Pyramid proxy PnL by entry year")
    axes[1].tick_params(axis="x", rotation=25, labelsize=8)
    axes[1].grid(axis="y", alpha=0.2)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    candidate = features[features["pyramid_candidate"].eq(1)].copy()
    if candidate.empty:
        return pd.DataFrame()
    selected = [
        candidate.sort_values("pyramid_proxy_pnl", ascending=False).head(5),
        candidate.sort_values("pyramid_proxy_pnl").head(5),
    ]
    stopped = candidate[candidate["pyramid_state"].isin(["same_bar_stop", "entry_day_stop"])].copy()
    if not stopped.empty:
        selected.append(stopped.sort_values("pyramid_proxy_pnl").head(4))
    held = candidate[candidate["pyramid_state"].eq("held_to_original_exit")].copy()
    if not held.empty:
        selected.append(held.sort_values("pyramid_proxy_pnl", ascending=False).head(4))
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        .drop_duplicates("lot_id")
        .head(MAX_ATLAS_ROWS)
        .reset_index(drop=True)
    )


def _index_for_time(day: pd.DataFrame, value: Any) -> int:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts) or day.empty:
        return -1
    matched = day.index[day["bar_datetime"].eq(ts)]
    if len(matched):
        return int(matched[0])
    diffs = (day["bar_datetime"] - ts).abs()
    if diffs.empty:
        return -1
    pos = int(diffs.idxmin())
    return pos if diffs.loc[pos] <= pd.Timedelta(minutes=1) else -1


def _plot_row(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row["vt_symbol"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(520).reset_index(drop=True)
    record = {
        "lot_id": int(row["lot_id"]),
        "vt_symbol": vt_symbol,
        "entry_date": entry_date.strftime("%Y-%m-%d") if pd.notna(entry_date) else "",
        "chart_missing_minutes": int(day.empty),
    }
    if day.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"missing minute bars\nlot{row['lot_id']} {vt_symbol}", ha="center", va="center")
        return record

    s825._plot_candles(ax, day)
    entry_price = _safe_float(row.get("entry_price"))
    add_price = _safe_float(row.get("pyramid_add_price"))
    stop_price = _safe_float(row.get("pyramid_stop_price"))
    if entry_price > 0:
        ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.9)
    if add_price > 0:
        ax.axhline(add_price, color="#16a34a", linewidth=0.95, alpha=0.9)
    if stop_price > 0:
        ax.axhline(stop_price, color="#dc2626", linewidth=0.8, alpha=0.55)
    add_idx = _index_for_time(day, row.get("first_05r_time"))
    if add_idx >= 0:
        ax.axvline(add_idx, color="#16a34a", linewidth=1.0, alpha=0.95)
        ax.text(add_idx, ax.get_ylim()[1], "add +0.5R", color="#16a34a", fontsize=7, rotation=90, va="top")
    stop_idx = _index_for_time(day, row.get("pyramid_exit_time"))
    if stop_idx >= 0:
        ax.axvline(stop_idx, color="#dc2626", linewidth=1.0, alpha=0.95)
        ax.text(stop_idx, ax.get_ylim()[1], "add stop", color="#dc2626", fontsize=7, rotation=90, va="top")
    ticks = np.linspace(0, len(day) - 1, num=min(9, len(day)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    ax.set_title(
        (
            f"lot{int(row['lot_id'])} {vt_symbol} {row.get('direction')} {entry_date:%Y-%m-%d} "
            f"state={row.get('pyramid_state')} base={_safe_float(row.get('realized_pnl')):,.0f} "
            f"add_pnl={_safe_float(row.get('pyramid_proxy_pnl')):,.0f} "
            f"add_R={_safe_float(row.get('pyramid_proxy_r')):.2f}"
        ),
        fontsize=8.2,
        loc="left",
    )
    return record


def _plot_atlas(features: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(features)
    if selected.empty:
        return [], pd.DataFrame()
    minute_bars = _load_minute_bars(set(selected["vt_symbol"].dropna().astype(str)))
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
                    "pyramid_state": str(row.get("pyramid_state", "")),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "pyramid_proxy_pnl": _safe_float(row.get("pyramid_proxy_pnl")),
                    "pyramid_proxy_r": _safe_float(row.get("pyramid_proxy_r")),
                }
            )
            records.append(rec)
        fig.suptitle(
            (
                f"Stage881 +0.5R progress pyramid proxy page {page}/{page_count}; "
                "blue=original entry/add stop, green=add price/time, red=add stop time"
            ),
            fontsize=12,
        )
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _write_report(
    overall: dict[str, Any],
    state_summary: pd.DataFrame,
    yearly: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    lines = [
        "# Stage881 Progress Pyramid Proxy Audit",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读代理审计；不改策略、不接真实引擎、不连接 CTP、不调用下单。",
        "",
        "## External Research Judgment",
        "",
        "- 趋势跟随资料中的 pyramiding 原则是只给已经盈利的头寸加仓，并用止损限制新增风险；这不同于继续过滤亏损样本。",
        "- 本阶段固定用 C9 已有 `+0.5R` 进展单位：若入场日先触达 `+0.5R`，假设在 `+0.5R` 价位加一笔同手数仓，新增仓止损放在原始入场价。",
        "- 我的判断：这是右尾增厚的低自由度代理，若只读代理仍不能稳定改善，后续不应写真实加仓引擎；若代理有明显上限价值，也必须先做真实资金路径和 broker10 审计。",
        "",
        "## Overall",
        "",
        _md_table(pd.DataFrame([overall]), max_rows=5),
        "",
        "## State Summary",
        "",
        _md_table(state_summary, max_rows=20),
        "",
        "## Yearly Summary",
        "",
        _md_table(yearly, max_rows=80),
        "",
        "## Charts",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- 决策：`stage881_progress_pyramid_proxy_only_needs_true_engine_before_any_promotion`",
        "- 理由：本阶段只做代理，不含新增仓的保证金路径、后续止损与资金联动，不能直接作为策略结论。",
        "- 下一步：只有当代理显示明确正上限，才允许做一次冻结真实引擎；否则停止 pyramiding 分支，不扫 `0.25R/0.5R/1R`、加仓比例、品种、方向或年份。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    closed_lots = _prepare_closed_lots()
    minute_bars = _load_minute_bars(set(closed_lots["vt_symbol"].dropna().astype(str)))
    features = _build_features(closed_lots, minute_bars)
    state_summary = _state_summary(features)
    yearly = _yearly_summary(features)
    overall = _overall_summary(features)
    _plot_summary_chart(state_summary, yearly)
    atlas_paths, atlas_manifest = _plot_atlas(features)
    _write_report(overall, state_summary, yearly, atlas_paths)

    features.to_csv(FEATURES_PATH, index=False, encoding="utf-8-sig")
    state_summary.to_csv(STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "pyramid_progress_r": PYRAMID_PROGRESS_R,
        "pyramid_add_volume_multiplier": PYRAMID_ADD_VOLUME_MULTIPLIER,
        **overall,
        "decision": "stage881_progress_pyramid_proxy_only_needs_true_engine_before_any_promotion",
        "next_action": "If proxy is materially positive, run exactly one frozen true-engine audit; otherwise stop pyramiding branch.",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
