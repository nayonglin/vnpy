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
STAGE = "Stage839"
MODEL_TAG = "stage839_stage825_uncovered_failure_kline_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage839_stage825_uncovered_failure_kline_forensics"

STAGE825_FEATURES_PATH = OUTPUT_DIR / (
    "qmt_roll_stage825_stage819_intraday_rule_forensics_intraday_features_"
    "stage825_stage819_intraday_rule_forensics_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_stats_{MODEL_TAG}.csv"
SUBSHAPE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_subshape_stats_{MODEL_TAG}.csv"
CANDIDATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_diagnostics_{MODEL_TAG}.csv"
TOP_LOSSES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_uncovered_losses_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_chart_{MODEL_TAG}.png"
CHART_PATH_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_uncovered_atlas_page{{page:03d}}_{MODEL_TAG}.png"

PER_PAGE = 4
MAX_ATLAS_PAGES = 8


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s825._safe_float(value, default=default)


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _date(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce").normalize()


def _load_features() -> pd.DataFrame:
    if not STAGE825_FEATURES_PATH.exists():
        raise RuntimeError(f"Missing Stage825 features: {STAGE825_FEATURES_PATH}")
    frame = pd.read_csv(STAGE825_FEATURES_PATH, encoding="utf-8-sig")
    for column in ("entry_date", "exit_date"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    numeric_columns = [
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "risk_pct",
        "entry_risk_distance_pct",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "entry_day_close_return_pct",
        "mfe_30m_r",
        "mae_30m_r",
        "mfe_60m_r",
        "mae_60m_r",
        "mfe_120m_r",
        "mae_120m_r",
        "fail_fast_30m_05r",
        "fail_fast_60m_05r",
        "fail_fast_120m_05r",
        "confirm_fast_60m_1r",
        "opening_range_breakout_confirmed",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["entry_year"] = frame["entry_date"].dt.year.astype("Int64")
    frame["is_loss"] = frame["realized_pnl"].lt(0).astype(int)
    return frame


def _load_minute_bars(features: pd.DataFrame) -> pd.DataFrame:
    vt_symbols = set(features["vt_symbol"].astype(str).dropna().unique())
    return s825._load_minute_bars(vt_symbols)


def _entry_day_bars(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bars = minute_by_symbol.get(str(row["vt_symbol"]), pd.DataFrame())
    if bars.empty:
        return pd.DataFrame()
    entry_date = _date(row["entry_date"])
    return bars[bars["bar_date"].eq(entry_date)].copy().reset_index(drop=True)


def _path_bucket(row: pd.Series) -> str:
    state = str(row.get("minute_coverage_state", ""))
    outcome = str(row.get("entry_day_first_1p0r_outcome", ""))
    if state != "entry_day_covered" or outcome in {"", "nan", "NaN", "None"}:
        return "uncovered_missing_minutes"
    if outcome == "stop_first":
        return "c2_shape_stop_first"
    if outcome == "target_first":
        return "uncovered_target_first_then_later_loss_risk"
    if outcome == "neither":
        return "uncovered_neither_no_1r_entryday"
    return f"uncovered_other_{outcome}"


def _entry_day_close_gross(row: pd.Series) -> float:
    entry_price = _safe_float(row.get("entry_price"))
    size = _safe_float(row.get("size"), 1.0)
    volume = _safe_float(row.get("volume"), 0.0)
    close_ret = _safe_float(row.get("entry_day_close_return_pct"))
    if not np.isfinite(entry_price * size * volume * close_ret):
        return np.nan
    return float(close_ret * entry_price * size * volume)


def _half_r_stop_gross(row: pd.Series) -> float:
    risk_amount = abs(_safe_float(row.get("risk_amount")))
    if np.isfinite(risk_amount) and risk_amount > 0:
        return float(-0.5 * risk_amount)
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("risk_pct"))
    size = _safe_float(row.get("size"), 1.0)
    volume = _safe_float(row.get("volume"), 0.0)
    if np.isfinite(entry_price * risk_pct * size * volume) and risk_pct > 0:
        return float(-0.5 * entry_price * risk_pct * size * volume)
    return np.nan


def _first_hit_index(
    entry_day: pd.DataFrame,
    *,
    direction: str,
    entry_price: float,
    risk_pct: float,
    multiple: float,
    side: str,
) -> int | None:
    if entry_day.empty or entry_price <= 0 or risk_pct <= 0:
        return None
    sign = _direction_sign(direction)
    level = entry_price * (1.0 + sign * risk_pct * multiple)
    for idx, item in enumerate(entry_day.itertuples(index=False)):
        if side == "target":
            hit = float(item.high) >= level if direction == "long" else float(item.low) <= level
        elif side == "stop":
            stop = entry_price * (1.0 - sign * risk_pct * multiple)
            hit = float(item.low) <= stop if direction == "long" else float(item.high) >= stop
        else:
            hit = False
        if hit:
            return idx
    return None


def _mark_target_first_giveback(features: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    minute_by_symbol = s825._minute_groups(minute_bars)
    rows: list[dict[str, Any]] = []
    for _, row in features.iterrows():
        lot_id = int(row["lot_id"])
        direction = str(row["direction"])
        outcome = str(row.get("entry_day_first_1p0r_outcome", ""))
        entry_price = _safe_float(row.get("entry_price"))
        risk_pct = _safe_float(row.get("risk_pct"))
        result = {
            "lot_id": lot_id,
            "target_first_index": np.nan,
            "target_first_time": "",
            "target_first_breakeven_after_target": 0,
            "target_first_half_r_giveback_after_target": 0,
            "entry_day_close_gross": _entry_day_close_gross(row),
            "half_r_stop_gross": _half_r_stop_gross(row),
        }
        if outcome == "target_first":
            entry_day = _entry_day_bars(row, minute_by_symbol)
            target_idx = _first_hit_index(
                entry_day,
                direction=direction,
                entry_price=entry_price,
                risk_pct=risk_pct,
                multiple=1.0,
                side="target",
            )
            if target_idx is not None and not entry_day.empty:
                result["target_first_index"] = int(target_idx)
                result["target_first_time"] = pd.Timestamp(entry_day.loc[target_idx, "bar_datetime"]).strftime("%Y-%m-%d %H:%M")
                after = entry_day.iloc[target_idx + 1 :]
                if not after.empty:
                    if direction == "long":
                        result["target_first_breakeven_after_target"] = int(pd.to_numeric(after["low"], errors="coerce").le(entry_price).any())
                        half_level = entry_price * (1.0 + 0.5 * risk_pct)
                        result["target_first_half_r_giveback_after_target"] = int(pd.to_numeric(after["low"], errors="coerce").le(half_level).any())
                    else:
                        result["target_first_breakeven_after_target"] = int(pd.to_numeric(after["high"], errors="coerce").ge(entry_price).any())
                        half_level = entry_price * (1.0 - 0.5 * risk_pct)
                        result["target_first_half_r_giveback_after_target"] = int(pd.to_numeric(after["high"], errors="coerce").ge(half_level).any())
        rows.append(result)
    diagnostics = pd.DataFrame(rows)
    return features.merge(diagnostics, on="lot_id", how="left")


def _add_subshapes(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy()
    data["c2_path_bucket"] = data.apply(_path_bucket, axis=1)
    close_ret = pd.to_numeric(data.get("entry_day_close_return_pct"), errors="coerce")
    outcome = data.get("entry_day_first_1p0r_outcome", pd.Series("", index=data.index)).astype(str)
    data["stage839_subshape"] = np.select(
        [
            data["c2_path_bucket"].eq("c2_shape_stop_first"),
            data["c2_path_bucket"].eq("uncovered_missing_minutes"),
            outcome.eq("target_first") & data["target_first_breakeven_after_target"].eq(1),
            outcome.eq("target_first") & data["target_first_half_r_giveback_after_target"].eq(1),
            outcome.eq("target_first"),
            outcome.eq("neither") & close_ret.lt(0),
            outcome.eq("neither") & close_ret.ge(0),
        ],
        [
            "covered_stop_first",
            "missing_minutes",
            "target_first_then_breakeven_same_day",
            "target_first_then_half_r_giveback_same_day",
            "target_first_no_material_giveback_same_day",
            "neither_close_adverse",
            "neither_close_nonadverse",
        ],
        default="other_uncovered",
    )
    return data


def _aggregate_stats(data: pd.DataFrame, group_col: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for value, group in data.groupby(group_col, dropna=False):
        realized = pd.to_numeric(group["realized_pnl"], errors="coerce")
        losses = group[realized.lt(0)]
        winners = group[realized.gt(0)]
        rows.append(
            {
                group_col: str(value),
                "lots": int(len(group)),
                "loss_lots": int(len(losses)),
                "winner_lots": int(len(winners)),
                "total_pnl": float(realized.sum()),
                "loss_pnl": float(pd.to_numeric(losses["realized_pnl"], errors="coerce").sum()),
                "winner_pnl": float(pd.to_numeric(winners["realized_pnl"], errors="coerce").sum()),
                "avg_r": float(pd.to_numeric(group["r_multiple"], errors="coerce").mean()),
                "median_r": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                "win_rate_pct": float(realized.gt(0).mean() * 100.0) if len(group) else np.nan,
                "covered_entryday_lots": int(group["minute_coverage_state"].astype(str).eq("entry_day_covered").sum()),
                "median_entry_day_mfe_r": float(pd.to_numeric(group.get("entry_day_mfe_r"), errors="coerce").median()),
                "median_entry_day_mae_r": float(pd.to_numeric(group.get("entry_day_mae_r"), errors="coerce").median()),
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values("loss_pnl", inplace=True)
    return result


def _candidate_rows(data: pd.DataFrame) -> pd.DataFrame:
    specs: list[tuple[str, str, pd.Series, pd.Series]] = []
    realized = pd.to_numeric(data["realized_pnl"], errors="coerce")
    outcome = data["entry_day_first_1p0r_outcome"].astype(str)
    specs.append(
        (
            "H1_target_first_breakeven_guard",
            "入场日先到+1R后，若同日回吐到原入场价，按保本离场；目标是处理 target_first 后转亏。",
            outcome.eq("target_first") & data["target_first_breakeven_after_target"].eq(1),
            pd.Series(0.0, index=data.index),
        )
    )
    specs.append(
        (
            "H2_neither_adverse_entryday_close_exit",
            "入场日既未到+1R也未到-1R，且收盘方向为逆向，则按入场日分钟收盘价退出。",
            outcome.eq("neither") & pd.to_numeric(data["entry_day_close_return_pct"], errors="coerce").lt(0),
            pd.to_numeric(data["entry_day_close_gross"], errors="coerce"),
        )
    )
    specs.append(
        (
            "H3_120m_half_r_failfast_exit",
            "入场后前120根分钟K先有0.5R逆向、没有0.5R顺向进展，则按-0.5R实时止损。",
            pd.to_numeric(data.get("fail_fast_120m_05r"), errors="coerce").fillna(0).eq(1),
            pd.to_numeric(data["half_r_stop_gross"], errors="coerce"),
        )
    )
    rows: list[dict[str, Any]] = []
    for candidate_id, rule_text, mask, adjusted in specs:
        mask = mask.fillna(False)
        group = data[mask].copy()
        adjusted_group = adjusted[mask]
        base = realized[mask]
        delta = adjusted_group - base
        losses = base.lt(0)
        winners = base.gt(0)
        rows.append(
            {
                "candidate_id": candidate_id,
                "rule_text": rule_text,
                "affected_lots": int(mask.sum()),
                "affected_loss_lots": int(losses.sum()),
                "affected_winner_lots": int(winners.sum()),
                "baseline_pnl": float(base.sum()),
                "adjusted_gross_pnl_ex_slippage": float(adjusted_group.sum()),
                "gross_delta_ex_slippage": float(delta.sum()),
                "loss_delta_ex_slippage": float(delta[losses].sum()),
                "winner_delta_ex_slippage": float(delta[winners].sum()),
                "uncovered_loss_lots_affected": int(
                    (mask & data["is_loss"].eq(1) & ~data["c2_path_bucket"].eq("c2_shape_stop_first")).sum()
                ),
                "stage839_judgment": "diagnostic_only_not_promoted",
            }
        )
    return pd.DataFrame(rows)


def _summary(data: pd.DataFrame, candidate: pd.DataFrame) -> pd.DataFrame:
    losses = data[data["is_loss"].eq(1)]
    uncovered = losses[~losses["c2_path_bucket"].eq("c2_shape_stop_first")]
    measured_uncovered = uncovered[uncovered["minute_coverage_state"].astype(str).eq("entry_day_covered")]
    missing_uncovered = uncovered[~uncovered["minute_coverage_state"].astype(str).eq("entry_day_covered")]
    rows = [
        {
            "closed_lots": int(len(data)),
            "loss_lots": int(len(losses)),
            "total_pnl": float(pd.to_numeric(data["realized_pnl"], errors="coerce").sum()),
            "loss_pnl": float(pd.to_numeric(losses["realized_pnl"], errors="coerce").sum()),
            "c2_stop_first_loss_lots": int(losses["c2_path_bucket"].eq("c2_shape_stop_first").sum()),
            "c2_stop_first_loss_pnl": float(
                pd.to_numeric(losses.loc[losses["c2_path_bucket"].eq("c2_shape_stop_first"), "realized_pnl"], errors="coerce").sum()
            ),
            "uncovered_loss_lots": int(len(uncovered)),
            "uncovered_loss_pnl": float(pd.to_numeric(uncovered["realized_pnl"], errors="coerce").sum()),
            "measured_uncovered_loss_lots": int(len(measured_uncovered)),
            "measured_uncovered_loss_pnl": float(pd.to_numeric(measured_uncovered["realized_pnl"], errors="coerce").sum()),
            "missing_uncovered_loss_lots": int(len(missing_uncovered)),
            "missing_uncovered_loss_pnl": float(pd.to_numeric(missing_uncovered["realized_pnl"], errors="coerce").sum()),
            "best_candidate_gross_delta_ex_slippage": float(
                pd.to_numeric(candidate["gross_delta_ex_slippage"], errors="coerce").max()
            )
            if not candidate.empty
            else 0.0,
            "decision": "stage839_uncovered_failure_no_single_clean_rule_yet",
        }
    ]
    return pd.DataFrame(rows)


def _top_losses(data: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "lot_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "entry_price",
        "exit_price",
        "risk_pct",
        "entry_risk_distance_pct",
        "volume",
        "realized_pnl",
        "r_multiple",
        "c2_path_bucket",
        "stage839_subshape",
        "entry_day_first_1p0r_outcome",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "mfe_120m_r",
        "mae_120m_r",
        "entry_day_close_return_pct",
        "target_first_breakeven_after_target",
        "target_first_half_r_giveback_after_target",
        "minute_coverage_state",
        "chart_page",
    ]
    losses = data[data["is_loss"].eq(1) & ~data["c2_path_bucket"].eq("c2_shape_stop_first")].copy()
    losses.sort_values("realized_pnl", inplace=True)
    return losses[[column for column in columns if column in losses.columns]].head(PER_PAGE * MAX_ATLAS_PAGES)


def _plot_bucket_chart(bucket: pd.DataFrame, subshape: pd.DataFrame, candidate: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(20, 5.2), constrained_layout=True)
    if not bucket.empty:
        ordered = bucket.sort_values("loss_pnl").copy()
        axes[0].barh(ordered["c2_path_bucket"], ordered["loss_pnl"], color="#dc2626")
        axes[0].set_title("Loss PnL By C2 Path Bucket")
        axes[0].axvline(0, color="#111827", linewidth=0.8)
        axes[0].grid(True, axis="x", alpha=0.2)
    if not subshape.empty:
        ordered = subshape.sort_values("loss_pnl").copy()
        axes[1].barh(ordered["stage839_subshape"], ordered["loss_pnl"], color="#f97316")
        axes[1].set_title("Uncovered Subshape Loss PnL")
        axes[1].axvline(0, color="#111827", linewidth=0.8)
        axes[1].grid(True, axis="x", alpha=0.2)
    if not candidate.empty:
        ordered = candidate.sort_values("gross_delta_ex_slippage").copy()
        axes[2].barh(ordered["candidate_id"], ordered["gross_delta_ex_slippage"], color="#2563eb")
        axes[2].set_title("Diagnostic Gross Delta, Not A Strategy Result")
        axes[2].axvline(0, color="#111827", linewidth=0.8)
        axes[2].grid(True, axis="x", alpha=0.2)
    fig.suptitle("Stage839 uncovered failure forensic summary", fontsize=14)
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_uncovered_atlas(top_losses: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if top_losses.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    total_pages = int(math.ceil(len(top_losses) / PER_PAGE))
    total_pages = min(total_pages, MAX_ATLAS_PAGES)
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        part = top_losses.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.4 * len(part))), constrained_layout=True)
        if len(part) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, part.iterrows(), strict=False):
            entry_day = _entry_day_bars(row, minute_by_symbol)
            vt_symbol = str(row["vt_symbol"])
            direction = str(row["direction"])
            entry_date = _date(row["entry_date"])
            if entry_day.empty:
                ax.axis("off")
                ax.text(
                    0.5,
                    0.5,
                    (
                        f"missing minutes\nlot{int(row['lot_id'])} {vt_symbol} {direction} {entry_date:%Y-%m-%d}\n"
                        f"pnl={_safe_float(row.get('realized_pnl')):,.0f} R={_safe_float(row.get('r_multiple')):.2f}"
                    ),
                    ha="center",
                    va="center",
                    color="#991b1b",
                    fontsize=10,
                )
            else:
                window = entry_day.head(240).copy().reset_index(drop=True)
                s825._plot_candles(ax, window)
                x = np.arange(len(window))
                ax.plot(x, window["close"].rolling(5).mean(), color="#f59e0b", linewidth=0.8, alpha=0.8)
                ax.plot(x, window["close"].rolling(20).mean(), color="#2563eb", linewidth=0.8, alpha=0.75)
                entry_price = _safe_float(row.get("entry_price"))
                risk_pct = _safe_float(row.get("risk_pct"))
                if not np.isfinite(risk_pct):
                    risk_pct = _safe_float(row.get("entry_risk_distance_pct"))
                sign = _direction_sign(direction)
                ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.85)
                if risk_pct > 0 and entry_price > 0:
                    ax.axhline(entry_price * (1.0 - sign * risk_pct), color="#dc2626", linewidth=0.9, alpha=0.85)
                    ax.axhline(entry_price * (1.0 + sign * risk_pct), color="#16a34a", linewidth=0.9, alpha=0.85)
                    ax.axhline(entry_price * (1.0 - sign * 0.5 * risk_pct), color="#ef4444", linewidth=0.7, linestyle=":", alpha=0.8)
                target_idx = row.get("target_first_index")
                if pd.notna(target_idx):
                    tx = int(target_idx)
                    if 0 <= tx < len(window):
                        ax.scatter([tx], [window.loc[tx, "close"]], color="#16a34a", s=36, zorder=6)
                        ax.text(tx, window.loc[tx, "close"], "+1R first", fontsize=7, color="#166534")
                ticks = np.linspace(0, len(window) - 1, num=min(7, len(window)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                ax.grid(True, alpha=0.18, linewidth=0.5)
                ax.tick_params(axis="y", labelsize=7)
            ax.set_title(
                (
                    f"lot{int(row['lot_id'])} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
                    f"pnl={_safe_float(row.get('realized_pnl')):,.0f} R={_safe_float(row.get('r_multiple')):.2f} "
                    f"{row.get('stage839_subshape', '')}"
                ),
                fontsize=8.5,
                loc="left",
            )
            records.append(
                {
                    "chart_page": page,
                    "lot_id": int(row["lot_id"]),
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "stage839_subshape": str(row.get("stage839_subshape", "")),
                    "minute_missing": int(entry_day.empty),
                }
            )
        fig.suptitle(
            "Stage839 uncovered loss atlas (blue=entry, red=-1R, green=+1R, dotted red=-0.5R)",
            fontsize=13,
        )
        path = Path(str(CHART_PATH_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _write_report(
    summary: pd.DataFrame,
    bucket: pd.DataFrame,
    subshape: pd.DataFrame,
    candidate: pd.DataFrame,
    top_losses: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    lines = [
        "# Stage839 未覆盖失败交易分钟K法证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读数据分析 + K线视觉法证；不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "- 目标：拆分 C2 `1R stop before 1R confirm` 没覆盖的左尾，寻找是否存在低自由度、实时可执行的下一步规则形状。",
        "",
        "## 外部调研判断",
        "",
        "- 公开期货/日内交易资料中，可靠规则通常围绕固定风险单位、失败突破、达到顺向进展后的保护止损，而不是产品/年份补丁。",
        "- GitHub 开源回测中的日内策略多把 stop loss、take profit、opening range、breakeven/trailing stop 做成通用模块；本阶段只借鉴这些形状，不复制参数。",
        "- 因 Stage834 已反证 OR15 确认会误伤右尾，本阶段不再验证 OR 形状，而是看 C2 未覆盖失败能否被更少自由度的 giveback/无进展规则解释。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## C2 Path Buckets",
        "",
        _md_table(bucket, max_rows=20),
        "",
        "## Subshape Stats",
        "",
        _md_table(subshape, max_rows=30),
        "",
        "## Candidate Diagnostics",
        "",
        _md_table(candidate, max_rows=10),
        "",
        "## Top Uncovered Losses",
        "",
        _md_table(top_losses.head(40), max_rows=40),
        "",
        "## Charts",
        "",
        f"- bucket chart：`{CHART_PATH}`",
        *[f"- uncovered atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- 本阶段不推广规则。H1/H2/H3 都只是 lot-level gross 诊断，不是组合引擎结果，也未含完整换手成本和资金联动。",
        "- 如果 H1 或 H2 的 gross delta 为正，也只能说明下一阶段可冻结成真实引擎 A/C；如果 winner hurt 太大，则直接停止该形状。",
        "- 分钟K缺失仍是硬限制：缺分钟的未覆盖亏损不能被包装成分钟级规则证据。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    minute_bars = _load_minute_bars(features)
    data = _mark_target_first_giveback(features, minute_bars)
    data = _add_subshapes(data)
    bucket = _aggregate_stats(data, "c2_path_bucket")
    subshape = _aggregate_stats(data, "stage839_subshape")
    candidate = _candidate_rows(data)
    summary = _summary(data, candidate)
    top_losses = _top_losses(data)
    _plot_bucket_chart(bucket, subshape, candidate)
    atlas_paths, atlas_manifest = _plot_uncovered_atlas(top_losses, minute_bars)
    if not atlas_manifest.empty:
        top_losses = top_losses.merge(
            atlas_manifest[["lot_id", "chart_page", "minute_missing"]],
            on="lot_id",
            how="left",
            suffixes=("", "_stage839"),
        )
    _write_report(summary, bucket, subshape, candidate, top_losses, atlas_paths)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bucket.to_csv(BUCKET_PATH, index=False, encoding="utf-8-sig")
    subshape.to_csv(SUBSHAPE_PATH, index=False, encoding="utf-8-sig")
    candidate.to_csv(CANDIDATE_PATH, index=False, encoding="utf-8-sig")
    top_losses.to_csv(TOP_LOSSES_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "formal_ab_triggered": False,
        "ctp_connected": False,
        "order_api_called": False,
        "decision": "stage839_uncovered_failure_no_single_clean_rule_yet",
        "summary": summary.to_dict("records"),
        "candidate_diagnostics": candidate.drop(columns=["rule_text"], errors="ignore").to_dict("records"),
        "overfit_reflection": (
            "Stage839 is read-only and uses frozen Stage825/C2 semantics. It does not tune products, years, "
            "minute windows, or R thresholds. Promoting H1/H2/H3 from this table without a frozen engine A/C "
            "would overfit."
        ),
        "continue_value": (
            "Continue if a candidate shows positive gross delta with controlled winner hurt and enough minute coverage; "
            "otherwise return to visual taxonomy instead of parameter scanning."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "bucket_stats": str(BUCKET_PATH),
            "subshape_stats": str(SUBSHAPE_PATH),
            "candidate_diagnostics": str(CANDIDATE_PATH),
            "top_uncovered_losses": str(TOP_LOSSES_PATH),
            "bucket_chart": str(CHART_PATH),
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
    print("candidate")
    print(candidate.to_string(index=False))
    print("subshape")
    print(subshape.to_string(index=False))


if __name__ == "__main__":
    main()
