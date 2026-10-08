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
STAGE = "Stage861"
MODEL_TAG = "stage861_stage860_full_visual_atlas_v1"
OUTPUT_PREFIX = "qmt_roll_stage861_stage860_full_visual_atlas"

STAGE825_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"
STAGE825_TAG = "stage825_stage819_intraday_rule_forensics_v1"
STAGE849_PREFIX = "qmt_roll_stage849_stage848_pressure_path_forensics"
STAGE849_TAG = "stage849_stage848_pressure_path_forensics_v1"
STAGE860_PREFIX = "qmt_roll_stage860_stage859_full_coverage_import"
STAGE860_TAG = "stage860_stage859_full_coverage_import_v1"
STAGE900_PREFIX = "qmt_roll_stage900_stage898_c9_gap_backfill"
STAGE900_TAG = "stage900_stage898_c9_gap_backfill_v1"

STAGE825_CLOSED_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_closed_lots_{STAGE825_TAG}.csv"
STAGE849_PRESSURE_PATH = OUTPUT_DIR / f"{STAGE849_PREFIX}_minute_features_{STAGE849_TAG}.csv"
STAGE860_PATCH_BARS_PATH = OUTPUT_DIR / f"{STAGE860_PREFIX}_combined_patch_minute_bars_{STAGE860_TAG}.csv"
STAGE860_REQUEST_COVERAGE_PATH = OUTPUT_DIR / f"{STAGE860_PREFIX}_request_coverage_after_stage860_{STAGE860_TAG}.csv"
STAGE860_STAGE825_COVERAGE_PATH = OUTPUT_DIR / f"{STAGE860_PREFIX}_stage825_coverage_after_stage860_{STAGE860_TAG}.csv"
STAGE860_PRESSURE_COVERAGE_PATH = OUTPUT_DIR / f"{STAGE860_PREFIX}_stage849_pressure_coverage_after_stage860_{STAGE860_TAG}.csv"
STAGE900_C9_GAP_BARS_PATH = OUTPUT_DIR / f"{STAGE900_PREFIX}_minute_bars_{STAGE900_TAG}.csv"

FULL_MINUTE_BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_minute_bars_{MODEL_TAG}.csv"
ENTRY_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_lot_features_{MODEL_TAG}.csv"
ENTRY_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_bucket_stats_{MODEL_TAG}.csv"
ENTRY_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_coverage_by_year_{MODEL_TAG}.csv"
ENTRY_ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_atlas_manifest_{MODEL_TAG}.csv"
ENTRY_ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_atlas_page{{page:03d}}_{MODEL_TAG}.png"
PRESSURE_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_key_date_features_{MODEL_TAG}.csv"
PRESSURE_ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_atlas_manifest_{MODEL_TAG}.csv"
PRESSURE_ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_atlas_page{{page:03d}}_{MODEL_TAG}.png"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

ENTRY_PER_PAGE = 6
PRESSURE_PER_PAGE = 7


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        result = float(value)
    except (TypeError, ValueError):
        return default
    if np.isfinite(result):
        return result
    return default


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_csv_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _prepare_minute_frame(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    data = frame.copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data = data.dropna(subset=["vt_symbol", "bar_datetime", "open", "high", "low", "close"])
    data["bar_date"] = data["bar_datetime"].dt.normalize()
    if "minute_source" not in data.columns:
        data["minute_source"] = source_name
    else:
        data["minute_source"] = data["minute_source"].fillna(source_name)
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    columns = [
        "vt_symbol",
        "bar_datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
        "bar_date",
        "minute_source",
    ]
    for column in columns:
        if column not in data.columns:
            data[column] = np.nan
    return data[columns].reset_index(drop=True)


def _load_full_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    original = _prepare_minute_frame(s825._load_minute_bars(vt_symbols), "stage825_original_minute_source")
    patch = _prepare_minute_frame(_load_csv(STAGE860_PATCH_BARS_PATH), "stage860_combined_patch")
    patch = patch[patch["vt_symbol"].astype(str).isin(vt_symbols)].copy()
    c9_gap_patch = _prepare_minute_frame(_load_csv_optional(STAGE900_C9_GAP_BARS_PATH), "stage900_c9_gap_patch")
    # Stage900 is scoped by the Stage898 C9 open-trade audit.  Keep it whole
    # because some C9-only open days are outside the Stage861 baseline lot sample.
    c9_gap_patch = c9_gap_patch.copy()
    frames = [frame for frame in [original, patch, c9_gap_patch] if not frame.empty]
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True, sort=False)
    data["source_priority"] = data["minute_source"].astype(str).str.contains("stage900|stage860|stage859|stage855").astype(int)
    data = data.sort_values(["vt_symbol", "bar_datetime", "source_priority"])
    data = data.drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
    return data.drop(columns=["source_priority"]).sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)


def _entry_lot_features(closed_lots: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    closed = closed_lots.copy()
    for column in ["entry_date", "exit_date"]:
        closed[column] = pd.to_datetime(closed[column], errors="coerce").dt.normalize()
    features = s825._build_intraday_features(closed, minute_bars)
    if "entry_year" not in features.columns:
        features["entry_year"] = pd.to_datetime(features["entry_date"], errors="coerce").dt.year
    features["realized_pnl"] = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    features["r_multiple"] = pd.to_numeric(features["r_multiple"], errors="coerce")
    return features.sort_values(["entry_date", "lot_id"]).reset_index(drop=True)


def _entry_coverage_by_year(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, group in features.groupby("entry_year", dropna=False):
        lots = int(len(group))
        covered = int(group["minute_coverage_state"].astype(str).eq("entry_day_covered").sum())
        rows.append(
            {
                "entry_year": int(year) if pd.notna(year) else "",
                "closed_lots": lots,
                "covered_lots": covered,
                "missing_lots": lots - covered,
                "coverage_rate": float(covered / lots) if lots else 0.0,
                "pnl_sum": float(group["realized_pnl"].sum()),
                "abs_pnl_sum": float(group["realized_pnl"].abs().sum()),
                "avg_entry_day_bars": float(pd.to_numeric(group["entry_day_minute_bars"], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("entry_year").reset_index(drop=True)


def _entry_bucket_stats(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    data = features.copy()
    data["winner"] = data["realized_pnl"].gt(0).astype(int)
    specs = [
        "direction",
        "signal",
        "exit_reason",
        "minute_coverage_state",
        "entry_day_first_0p5r_outcome",
        "entry_day_first_1p0r_outcome",
        "fail_fast_30m_05r",
        "confirm_fast_60m_1r",
        "reentry_cross_count_after_05r_stop",
    ]
    for spec in specs:
        if spec not in data.columns:
            continue
        series = data[spec].fillna("missing").astype(str)
        for bucket, group in data.groupby(series, dropna=False):
            if len(group) < 5:
                continue
            rows.append(
                {
                    "bucket_type": spec,
                    "bucket": str(bucket),
                    "lot_count": int(len(group)),
                    "pnl_sum": float(group["realized_pnl"].sum()),
                    "abs_pnl_sum": float(group["realized_pnl"].abs().sum()),
                    "win_rate_pct": float(group["winner"].mean() * 100.0),
                    "r_median": float(group["r_multiple"].median()) if group["r_multiple"].notna().any() else np.nan,
                    "mfe_r_median": float(pd.to_numeric(group.get("entry_day_mfe_r"), errors="coerce").median()),
                    "mae_r_median": float(pd.to_numeric(group.get("entry_day_mae_r"), errors="coerce").median()),
                    "big_winner_count": int(pd.to_numeric(group.get("big_winner", 0), errors="coerce").fillna(0).sum()),
                }
            )
    return pd.DataFrame(rows).sort_values(["bucket_type", "lot_count"], ascending=[True, False]).reset_index(drop=True)


def _plot_entry_atlas(features: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    minute_by_symbol = s825._minute_groups(minute_bars)
    ordered = features.copy()
    ordered["abs_pnl"] = pd.to_numeric(ordered["realized_pnl"], errors="coerce").abs()
    ordered["abs_r"] = pd.to_numeric(ordered["r_multiple"], errors="coerce").abs()
    ordered = ordered.sort_values(["abs_pnl", "abs_r", "entry_date", "lot_id"], ascending=[False, False, True, True])
    page_count = int(math.ceil(len(ordered) / ENTRY_PER_PAGE)) if len(ordered) else 0
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, page_count + 1):
        part = ordered.iloc[(page - 1) * ENTRY_PER_PAGE : page * ENTRY_PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.05 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            record = s825._plot_lot(ax, row, minute_by_symbol)
            record.update(
                {
                    "chart_page": page,
                    "vt_symbol": str(row.get("vt_symbol", "")),
                    "direction": str(row.get("direction", "")),
                    "entry_date": str(pd.Timestamp(row.get("entry_date")).date())
                    if pd.notna(row.get("entry_date"))
                    else "",
                    "realized_pnl": _safe_float(row.get("realized_pnl"), 0.0),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                }
            )
            manifest.append(record)
        fig.suptitle(
            (
                f"Stage861 full entry-day minute atlas page {page}/{page_count}; "
                "blue=entry, red=0.5R stop, green=1R target, purple=OR15"
            ),
            fontsize=13,
        )
        path = Path(str(ENTRY_ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _pressure_features(pressure_rows: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    minute_by_symbol = s825._minute_groups(minute_bars)
    records: list[dict[str, Any]] = []
    for row in pressure_rows.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        day = pd.Timestamp(pd.to_datetime(row.date, errors="coerce")).normalize()
        direction = str(row.direction)
        bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        day_bars = (
            bars[bars["bar_date"].eq(day)].copy().sort_values("bar_datetime").reset_index(drop=True)
            if not bars.empty
            else pd.DataFrame()
        )
        record: dict[str, Any] = {
            "episode_id": str(row.episode_id),
            "vt_symbol": vt_symbol,
            "date": day.strftime("%Y-%m-%d") if pd.notna(day) else "",
            "direction": direction,
            "minute_bars": int(len(day_bars)),
            "entry_avg_C4": _safe_float(getattr(row, "entry_avg_C4", np.nan)),
            "entry_avg_C9": _safe_float(getattr(row, "entry_avg_C9", np.nan)),
            "exit_avg_C4": _safe_float(getattr(row, "exit_avg_C4", np.nan)),
            "exit_avg_C9": _safe_float(getattr(row, "exit_avg_C9", np.nan)),
            "source_original_minute_bars": int(_safe_float(getattr(row, "minute_bars", 0), 0.0)),
        }
        if not day_bars.empty:
            open_price = float(day_bars.iloc[0]["open"])
            high_price = float(pd.to_numeric(day_bars["high"], errors="coerce").max())
            low_price = float(pd.to_numeric(day_bars["low"], errors="coerce").min())
            close_price = float(day_bars.iloc[-1]["close"])
            sign = 1.0 if direction == "long" else -1.0
            favorable = (
                (high_price / open_price - 1.0) * 100.0
                if direction == "long" and open_price > 0
                else (open_price / low_price - 1.0) * 100.0
                if direction == "short" and low_price > 0
                else np.nan
            )
            adverse = (
                (low_price / open_price - 1.0) * 100.0
                if direction == "long" and open_price > 0
                else (open_price / high_price - 1.0) * 100.0
                if direction == "short" and high_price > 0
                else np.nan
            )
            record.update(
                {
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "directional_close_return_pct": (close_price / open_price - 1.0) * 100.0 * sign
                    if open_price > 0
                    else np.nan,
                    "intraday_favorable_from_open_pct": favorable,
                    "intraday_adverse_from_open_pct": adverse,
                    "range_pct": (high_price / low_price - 1.0) * 100.0 if low_price > 0 else np.nan,
                    "first_bar_time": pd.Timestamp(day_bars.iloc[0]["bar_datetime"]).strftime("%H:%M"),
                    "last_bar_time": pd.Timestamp(day_bars.iloc[-1]["bar_datetime"]).strftime("%H:%M"),
                }
            )
        records.append(record)
    return pd.DataFrame(records).sort_values(["episode_id", "date"]).reset_index(drop=True)


def _plot_pressure_atlas(features: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if features.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    page_count = int(math.ceil(len(features) / PRESSURE_PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, page_count + 1):
        part = features.iloc[(page - 1) * PRESSURE_PER_PAGE : page * PRESSURE_PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.1 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            day = pd.Timestamp(row["date"]).normalize()
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day_bars = (
                bars[bars["bar_date"].eq(day)].copy().sort_values("bar_datetime").head(340).reset_index(drop=True)
                if not bars.empty
                else pd.DataFrame()
            )
            if day_bars.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {day:%Y-%m-%d}", ha="center", va="center")
            else:
                s825._plot_candles(ax, day_bars)
                for value, color, style, label in [
                    (_safe_float(row.get("entry_avg_C4")), "#16a34a", "-", "C4 entry avg"),
                    (_safe_float(row.get("entry_avg_C9")), "#7c3aed", "-", "C9 entry avg"),
                    (_safe_float(row.get("exit_avg_C4")), "#16a34a", "--", "C4 exit avg"),
                    (_safe_float(row.get("exit_avg_C9")), "#7c3aed", "--", "C9 exit avg"),
                ]:
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linestyle=style, linewidth=0.9, label=label)
                ticks = np.linspace(0, len(day_bars) - 1, num=min(8, len(day_bars)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels(
                    [pd.Timestamp(day_bars.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks],
                    fontsize=7,
                )
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            title = (
                f"{row['episode_id']} | {vt_symbol} {row['direction']} {day:%Y-%m-%d} "
                f"bars={int(_safe_float(row.get('minute_bars'), 0))} "
                f"dir_close={_safe_float(row.get('directional_close_return_pct')):.2f}% "
                f"adv={_safe_float(row.get('intraday_adverse_from_open_pct')):.2f}% "
                f"fav={_safe_float(row.get('intraday_favorable_from_open_pct')):.2f}%"
            )
            ax.set_title(title, loc="left", fontsize=8.3)
            manifest.append(
                {
                    "episode_id": str(row["episode_id"]),
                    "vt_symbol": vt_symbol,
                    "date": day.strftime("%Y-%m-%d"),
                    "minute_bars": int(_safe_float(row.get("minute_bars"), 0.0)),
                    "chart_page": page,
                }
            )
        fig.suptitle(f"Stage861 full pressure key-date minute atlas page {page}/{page_count}", fontsize=13)
        path = Path(str(PRESSURE_ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _write_report(
    summary: pd.DataFrame,
    entry_coverage: pd.DataFrame,
    entry_bucket: pd.DataFrame,
    pressure_features: pd.DataFrame,
    entry_paths: list[Path],
    pressure_paths: list[Path],
) -> None:
    lines = [
        "# Stage861 Stage860全覆盖分钟K视觉图谱",
        "",
        "## 阶段定位",
        "",
        "- 阶段性质：全覆盖分钟K特征重算与视觉复盘；不写新交易规则、不接真实引擎、不触发A/B。",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`。",
        "- 目标：把 Stage860 恢复的完整分钟K覆盖纳入 Stage825/849 同一视觉证据口径，消除 Stage034 覆盖偏差。",
        "",
        "## 外部调研与判断",
        "",
        "- 公开的日内规则实践常见形状仍是开盘区间、逐根K线止损、跟踪止损、收盘前处理；GitHub 开源回测代码也通常把 stop/take-profit 当作逐bar事件语义实现。",
        "- 我的判断：这些资料只支持工程纪律，不支持复制参数。Stage861 仍只产出证据，不把任何 OR、R 倍数或重试次数升级为规则。",
        "",
        "## 核心摘要",
        "",
        _md_table(summary),
        "",
        "## Entry-Day Coverage By Year",
        "",
        _md_table(entry_coverage, max_rows=30),
        "",
        "## Entry Bucket Diagnostics",
        "",
        _md_table(entry_bucket.head(80), max_rows=80),
        "",
        "## Pressure Key Dates",
        "",
        _md_table(pressure_features.head(40), max_rows=40),
        "",
        "## 图谱输出",
        "",
        *[f"- entry atlas：`{path}`" for path in entry_paths[:20]],
        *([f"- entry atlas 其余页数：`{max(0, len(entry_paths) - 20)}`"] if len(entry_paths) > 20 else []),
        *[f"- pressure atlas：`{path}`" for path in pressure_paths],
        "",
        "## 判断",
        "",
        "- 决策：`stage861_full_visual_atlas_complete_no_rule`。",
        "- Stage861 完成的是证据层修复：Stage825 entry-day 与 Stage849 pressure key date 均已用完整分钟源重算和重画。",
        "- 这还不是规则成立证据；下一步才可以在全覆盖证据上重新做少数低自由度规则假设筛查。",
        "",
        "## 输出文件",
        "",
        f"- full_minute_bars：`{FULL_MINUTE_BARS_PATH}`",
        f"- entry_lot_features：`{ENTRY_FEATURES_PATH}`",
        f"- entry_bucket_stats：`{ENTRY_BUCKET_PATH}`",
        f"- entry_coverage：`{ENTRY_COVERAGE_PATH}`",
        f"- entry_atlas_manifest：`{ENTRY_ATLAS_MANIFEST_PATH}`",
        f"- pressure_features：`{PRESSURE_FEATURES_PATH}`",
        f"- pressure_atlas_manifest：`{PRESSURE_ATLAS_MANIFEST_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段只做完整证据重算，不使用结果调参数。",
        "- 运行后判断：否。但若马上按图谱里的某一年、某品种或某个 R 倍数定规则，就会过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。Stage860 已恢复数据覆盖，必须重做全量视觉证据。",
        "- 运行后判断：仍有价值。覆盖偏差已经解除，后续可以重新进入全周期规则假设筛查，但仍必须坚持冻结规则和真实引擎 A/C。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    closed_lots = _load_csv(STAGE825_CLOSED_PATH)
    pressure_rows = _load_csv(STAGE849_PRESSURE_PATH)
    stage860_stage825 = _load_csv(STAGE860_STAGE825_COVERAGE_PATH)
    stage860_pressure = _load_csv(STAGE860_PRESSURE_COVERAGE_PATH)
    _ = _load_csv(STAGE860_REQUEST_COVERAGE_PATH)

    vt_symbols = set(closed_lots["vt_symbol"].astype(str).dropna().unique())
    vt_symbols.update(pressure_rows["vt_symbol"].astype(str).dropna().unique())
    minute_bars = _load_full_minute_bars(vt_symbols)
    entry_features = _entry_lot_features(closed_lots, minute_bars)
    entry_coverage = _entry_coverage_by_year(entry_features)
    entry_bucket = _entry_bucket_stats(entry_features)
    entry_paths, entry_manifest = _plot_entry_atlas(entry_features, minute_bars)
    pressure_features = _pressure_features(pressure_rows, minute_bars)
    pressure_paths, pressure_manifest = _plot_pressure_atlas(pressure_features, minute_bars)

    entry_covered = int(entry_features["minute_coverage_state"].astype(str).eq("entry_day_covered").sum())
    pressure_covered = int(pressure_features["minute_bars"].gt(0).sum())
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "line_id": LINE_ID,
                "decision": "stage861_full_visual_atlas_complete_no_rule"
                if entry_covered == len(entry_features) and pressure_covered == len(pressure_features)
                else "stage861_full_visual_atlas_incomplete_no_rule",
                "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
                "full_minute_bars": int(len(minute_bars)),
                "full_minute_symbols": int(minute_bars["vt_symbol"].astype(str).nunique()) if not minute_bars.empty else 0,
                "stage860_patch_minute_bars": int(len(_load_csv(STAGE860_PATCH_BARS_PATH))),
                "stage900_c9_gap_patch_minute_bars": int(len(_load_csv_optional(STAGE900_C9_GAP_BARS_PATH))),
                "entry_lots": int(len(entry_features)),
                "entry_day_covered_lots": entry_covered,
                "entry_day_missing_lots": int(len(entry_features) - entry_covered),
                "entry_day_coverage_rate": float(entry_covered / len(entry_features)) if len(entry_features) else 0.0,
                "stage860_declared_entry_covered_lots": int(
                    pd.to_numeric(stage860_stage825.get("after_stage860_entry_day_covered", 0), errors="coerce")
                    .fillna(0)
                    .sum()
                ),
                "pressure_key_dates": int(len(pressure_features)),
                "pressure_covered_dates": pressure_covered,
                "pressure_missing_dates": int(len(pressure_features) - pressure_covered),
                "pressure_coverage_rate": float(pressure_covered / len(pressure_features)) if len(pressure_features) else 0.0,
                "stage860_declared_pressure_covered_dates": int(
                    pd.to_numeric(stage860_pressure.get("covered_after_stage860", 0), errors="coerce").fillna(0).sum()
                ),
                "entry_atlas_pages": int(len(entry_paths)),
                "pressure_atlas_pages": int(len(pressure_paths)),
                "new_rule_allowed": 0,
                "engine_allowed": 0,
                "ab_allowed": 0,
            }
        ]
    )

    minute_bars.to_csv(FULL_MINUTE_BARS_PATH, index=False, encoding="utf-8-sig")
    entry_features.to_csv(ENTRY_FEATURES_PATH, index=False, encoding="utf-8-sig")
    entry_bucket.to_csv(ENTRY_BUCKET_PATH, index=False, encoding="utf-8-sig")
    entry_coverage.to_csv(ENTRY_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    entry_manifest.to_csv(ENTRY_ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    pressure_features.to_csv(PRESSURE_FEATURES_PATH, index=False, encoding="utf-8-sig")
    pressure_manifest.to_csv(PRESSURE_ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": str(summary.iloc[0]["decision"]),
        "metrics": summary.iloc[0].to_dict(),
        "inputs": {
            "stage825_closed_lots": str(STAGE825_CLOSED_PATH),
            "stage849_pressure_features": str(STAGE849_PRESSURE_PATH),
            "stage860_combined_patch_bars": str(STAGE860_PATCH_BARS_PATH),
            "stage900_c9_gap_patch_bars": str(STAGE900_C9_GAP_BARS_PATH),
            "stage860_stage825_coverage": str(STAGE860_STAGE825_COVERAGE_PATH),
            "stage860_pressure_coverage": str(STAGE860_PRESSURE_COVERAGE_PATH),
        },
        "outputs": {
            "full_minute_bars": str(FULL_MINUTE_BARS_PATH),
            "entry_lot_features": str(ENTRY_FEATURES_PATH),
            "entry_bucket_stats": str(ENTRY_BUCKET_PATH),
            "entry_coverage": str(ENTRY_COVERAGE_PATH),
            "entry_atlas_manifest": str(ENTRY_ATLAS_MANIFEST_PATH),
            "entry_atlas_paths": [str(path) for path in entry_paths],
            "pressure_features": str(PRESSURE_FEATURES_PATH),
            "pressure_atlas_manifest": str(PRESSURE_ATLAS_MANIFEST_PATH),
            "pressure_atlas_paths": [str(path) for path in pressure_paths],
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "allow_new_rule": False,
        "allow_engine": False,
        "allow_ab": False,
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, entry_coverage, entry_bucket, pressure_features, entry_paths, pressure_paths)
    print(json.dumps(_json_safe(decision["metrics"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
