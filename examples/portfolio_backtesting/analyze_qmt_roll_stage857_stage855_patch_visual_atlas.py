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


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage857"
MODEL_TAG = "stage857_stage855_patch_visual_atlas_v1"
OUTPUT_PREFIX = "qmt_roll_stage857_stage855_patch_visual_atlas"

STAGE825_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"
STAGE825_TAG = "stage825_stage819_intraday_rule_forensics_v1"
STAGE849_PREFIX = "qmt_roll_stage849_stage848_pressure_path_forensics"
STAGE849_TAG = "stage849_stage848_pressure_path_forensics_v1"
STAGE855_PREFIX = "qmt_roll_stage855_stage854_local_raw_import"
STAGE855_TAG = "stage855_stage854_local_raw_import_v1"

PATCH_BARS_PATH = OUTPUT_DIR / f"{STAGE855_PREFIX}_patch_minute_bars_{STAGE855_TAG}.csv"
REQUEST_COVERAGE_PATH = OUTPUT_DIR / f"{STAGE855_PREFIX}_request_coverage_after_patch_{STAGE855_TAG}.csv"
PRESSURE_COVERAGE_PATH = OUTPUT_DIR / f"{STAGE855_PREFIX}_stage849_pressure_coverage_after_patch_{STAGE855_TAG}.csv"
STAGE825_CLOSED_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_closed_lots_{STAGE825_TAG}.csv"
STAGE849_MINUTE_PATH = OUTPUT_DIR / f"{STAGE849_PREFIX}_minute_features_{STAGE849_TAG}.csv"
STAGE856_SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage856_stage855_remaining_gap_download_summary_stage856_stage855_remaining_gap_download_v1.csv"
)

PATCH_ENTRY_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_patch_entry_lot_features_{MODEL_TAG}.csv"
PATCH_ENTRY_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_patch_entry_bucket_stats_{MODEL_TAG}.csv"
PATCH_PRESSURE_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_patch_pressure_features_{MODEL_TAG}.csv"
PATCH_ENTRY_ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_atlas_manifest_{MODEL_TAG}.csv"
PATCH_PRESSURE_ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_atlas_manifest_{MODEL_TAG}.csv"
PATCH_ENTRY_ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_atlas_page{{page:03d}}_{MODEL_TAG}.png"
PATCH_PRESSURE_ATLAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_key_dates_{MODEL_TAG}.png"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PER_ENTRY_PAGE = 6


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normal_date(value: Any) -> pd.Timestamp:
    return pd.Timestamp(pd.to_datetime(value, errors="coerce")).normalize()


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _source_id_to_lot_id(value: Any) -> int | None:
    text = str(value)
    if not text.startswith("lot_"):
        return None
    try:
        return int(text.split("_", 1)[1])
    except ValueError:
        return None


def _load_patch_bars() -> pd.DataFrame:
    patch = _load_csv(PATCH_BARS_PATH)
    if patch.empty:
        return patch
    patch = patch.copy()
    patch["bar_datetime"] = pd.to_datetime(patch["bar_datetime"], errors="coerce")
    patch = patch.dropna(subset=["vt_symbol", "bar_datetime", "open", "high", "low", "close"])
    patch["bar_date"] = patch["bar_datetime"].dt.normalize()
    patch["minute_source"] = "stage855_local_raw_patch"
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in patch.columns:
            patch[column] = pd.to_numeric(patch[column], errors="coerce")
    return patch.reset_index(drop=True)


def _combined_minute_bars(vt_symbols: set[str], patch_bars: pd.DataFrame) -> pd.DataFrame:
    original = s825._load_minute_bars(vt_symbols)
    patch = patch_bars[patch_bars["vt_symbol"].astype(str).isin(vt_symbols)].copy()
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
    frames = [frame[[col for col in columns if col in frame.columns]].copy() for frame in [original, patch] if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=columns)
    data = pd.concat(frames, ignore_index=True, sort=False)
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = data["bar_datetime"].dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["source_priority"] = data["minute_source"].astype(str).eq("stage855_local_raw_patch").astype(int)
    data = data.sort_values(["vt_symbol", "bar_datetime", "source_priority"])
    data = data.drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
    return data.drop(columns=["source_priority"]).sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)


def _patch_entry_lots(request_coverage: pd.DataFrame, closed_lots: pd.DataFrame) -> pd.DataFrame:
    requests = request_coverage[
        request_coverage["request_type"].astype(str).eq("stage825_entry_day")
        & pd.to_numeric(request_coverage["stage855_patch_bars"], errors="coerce").fillna(0).gt(0)
        & pd.to_numeric(request_coverage["covered_after_patch"], errors="coerce").fillna(0).astype(int).eq(1)
    ].copy()
    requests["lot_id"] = requests["source_id"].map(_source_id_to_lot_id)
    requests = requests.dropna(subset=["lot_id"])
    requests["lot_id"] = requests["lot_id"].astype(int)
    meta_cols = [
        "lot_id",
        "required_date",
        "priority_abs_pnl",
        "big_winner",
        "stage855_patch_bars",
        "coverage_action_after_patch",
    ]
    selected = closed_lots[closed_lots["lot_id"].isin(set(requests["lot_id"]))].copy()
    selected = selected.merge(requests[meta_cols], on="lot_id", how="left", suffixes=("", "_request"))
    selected["stage855_patch_bars"] = pd.to_numeric(selected["stage855_patch_bars"], errors="coerce").fillna(0).astype(int)
    selected["stage855_priority_abs_pnl"] = pd.to_numeric(selected["priority_abs_pnl"], errors="coerce").fillna(0.0)
    selected["stage855_request_date"] = pd.to_datetime(selected["required_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return selected.sort_values(["stage855_priority_abs_pnl", "lot_id"], ascending=[False, True]).reset_index(drop=True)


def _patch_entry_features(entry_lots: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    if entry_lots.empty:
        return pd.DataFrame()
    features = s825._build_intraday_features(entry_lots.copy(), minute_bars)
    display_cols = [
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "exit_date",
        "realized_pnl",
        "r_multiple",
        "big_winner",
        "stage855_patch_bars",
        "minute_coverage_state",
        "entry_day_minute_bars",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "entry_day_close_return_pct",
        "entry_day_first_0p5r_outcome",
        "entry_day_first_0p5r_time",
        "entry_day_first_1p0r_outcome",
        "entry_day_first_1p0r_time",
        "fail_fast_30m_05r",
        "confirm_fast_60m_1r",
        "reentry_cross_count_after_05r_stop",
        "exit_reason",
        "signal",
        "risk_multiplier",
        "oi_price_confirm_risk_restore_applied",
    ]
    existing = [col for col in display_cols if col in features.columns]
    return features[existing].copy()


def _bucket_stats(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    specs = [
        "entry_day_first_0p5r_outcome",
        "entry_day_first_1p0r_outcome",
        "fail_fast_30m_05r",
        "confirm_fast_60m_1r",
        "reentry_cross_count_after_05r_stop",
        "direction",
        "exit_reason",
    ]
    data = features.copy()
    data["realized_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").fillna(0.0)
    data["r_multiple"] = pd.to_numeric(data["r_multiple"], errors="coerce")
    for spec in specs:
        if spec not in data.columns:
            continue
        bucket_series = data[spec].fillna("missing").astype(str)
        for bucket, group in data.groupby(bucket_series, dropna=False):
            rows.append(
                {
                    "bucket_type": spec,
                    "bucket": str(bucket),
                    "lot_count": int(len(group)),
                    "pnl_sum": float(group["realized_pnl"].sum()),
                    "pnl_median": float(group["realized_pnl"].median()) if len(group) else np.nan,
                    "win_rate": float(group["realized_pnl"].gt(0).mean()) if len(group) else np.nan,
                    "r_median": float(group["r_multiple"].median()) if group["r_multiple"].notna().any() else np.nan,
                    "big_winner_count": int(pd.to_numeric(group.get("big_winner", 0), errors="coerce").fillna(0).sum()),
                }
            )
    return pd.DataFrame(rows).sort_values(["bucket_type", "lot_count"], ascending=[True, False]).reset_index(drop=True)


def _plot_entry_atlas(features: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if features.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    ordered = features.copy()
    ordered["abs_priority"] = pd.to_numeric(ordered.get("stage855_patch_bars"), errors="coerce").fillna(0)
    ordered["abs_pnl"] = pd.to_numeric(ordered["realized_pnl"], errors="coerce").abs()
    ordered = ordered.sort_values(["abs_pnl", "stage855_patch_bars", "lot_id"], ascending=[False, False, True])
    page_count = int(math.ceil(len(ordered) / PER_ENTRY_PAGE))
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, page_count + 1):
        part = ordered.iloc[(page - 1) * PER_ENTRY_PAGE : page * PER_ENTRY_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.1 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            record = s825._plot_lot(ax, row, minute_by_symbol)
            record["chart_page"] = page
            record["vt_symbol"] = str(row.get("vt_symbol", ""))
            record["entry_date"] = str(row.get("entry_date", ""))
            record["stage855_patch_bars"] = int(_safe_float(row.get("stage855_patch_bars"), 0.0))
            records.append(record)
        fig.suptitle(
            (
                f"Stage857 Stage855 patch entry-day atlas page {page}/{page_count}; "
                "blue=entry, red=0.5R stop, green=1R target, purple=OR15"
            ),
            fontsize=13,
        )
        path = Path(str(PATCH_ENTRY_ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _pressure_patch_features(pressure_coverage: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    patch_rows = pressure_coverage[
        pd.to_numeric(pressure_coverage["stage855_patch_bars"], errors="coerce").fillna(0).gt(0)
    ].copy()
    if patch_rows.empty:
        return pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    records: list[dict[str, Any]] = []
    for row in patch_rows.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        day = _normal_date(row.date_text)
        bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        day_bars = (
            bars[bars["bar_date"].eq(day)].copy().sort_values("bar_datetime").reset_index(drop=True)
            if not bars.empty
            else pd.DataFrame()
        )
        direction = str(row.direction)
        record = {
            "episode_id": str(row.episode_id),
            "vt_symbol": vt_symbol,
            "date": day.strftime("%Y-%m-%d"),
            "direction": direction,
            "minute_bars": int(len(day_bars)),
            "stage855_patch_bars": int(_safe_float(row.stage855_patch_bars, 0.0)),
            "entry_avg_C4": _safe_float(getattr(row, "entry_avg_C4", np.nan)),
            "entry_avg_C9": _safe_float(getattr(row, "entry_avg_C9", np.nan)),
            "exit_avg_C4": _safe_float(getattr(row, "exit_avg_C4", np.nan)),
            "exit_avg_C9": _safe_float(getattr(row, "exit_avg_C9", np.nan)),
        }
        if not day_bars.empty:
            open_price = float(day_bars.iloc[0]["open"])
            high_price = float(pd.to_numeric(day_bars["high"], errors="coerce").max())
            low_price = float(pd.to_numeric(day_bars["low"], errors="coerce").min())
            close_price = float(day_bars.iloc[-1]["close"])
            sign = 1.0 if direction == "long" else -1.0
            if direction == "long":
                favorable = (high_price / open_price - 1.0) * 100.0 if open_price > 0 else np.nan
                adverse = (low_price / open_price - 1.0) * 100.0 if open_price > 0 else np.nan
            else:
                favorable = (open_price / low_price - 1.0) * 100.0 if low_price > 0 else np.nan
                adverse = (open_price / high_price - 1.0) * 100.0 if high_price > 0 else np.nan
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
                }
            )
        records.append(record)
    return pd.DataFrame(records).sort_values(["episode_id", "date"]).reset_index(drop=True)


def _plot_pressure_atlas(features: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    fig, axes = plt.subplots(len(features), 1, figsize=(18, max(4.0, 3.2 * len(features))), constrained_layout=True)
    axes_list = list(np.atleast_1d(axes))
    manifest: list[dict[str, Any]] = []
    for ax, (_, row) in zip(axes_list, features.iterrows(), strict=False):
        vt_symbol = str(row["vt_symbol"])
        day = _normal_date(row["date"])
        bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        day_bars = (
            bars[bars["bar_date"].eq(day)].copy().sort_values("bar_datetime").head(320).reset_index(drop=True)
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
            ax.set_xticklabels([pd.Timestamp(day_bars.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                dedup = dict(zip(labels, handles))
                ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
            ax.grid(True, alpha=0.18)
        title = (
            f"{row['episode_id']} | {vt_symbol} {row['direction']} {day:%Y-%m-%d} "
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
                "chart_path": str(PATCH_PRESSURE_ATLAS_PATH),
            }
        )
    fig.suptitle("Stage857 Stage855 patch pressure key-date atlas", fontsize=13)
    fig.savefig(PATCH_PRESSURE_ATLAS_PATH, dpi=150)
    plt.close(fig)
    return pd.DataFrame(manifest)


def _write_report(
    summary: pd.DataFrame,
    entry_features: pd.DataFrame,
    bucket_stats: pd.DataFrame,
    pressure_features: pd.DataFrame,
    entry_paths: list[Path],
) -> None:
    lines = [
        "# Stage857 Stage855新增覆盖分钟K视觉图谱",
        "",
        "## 阶段定位",
        "",
        "- 阶段性质：只读视觉复盘与特征重算；不改策略、不接引擎、不连接 CTP、不调用下单。",
        "- 目标：把 Stage855 本地 raw patch 新增覆盖的 entry-day lots 和压力 key dates 转成可审计的分钟K视觉证据。",
        "- 约束：本阶段不生成新交易规则；剩余关键缺口未补齐前，不允许把局部图谱包装成全周期分钟策略证明。",
        "",
        "## 核心摘要",
        "",
        _md_table(summary),
        "",
        "## 新增覆盖 entry-day lots",
        "",
        _md_table(
            entry_features[
                [
                    col
                    for col in [
                        "lot_id",
                        "vt_symbol",
                        "direction",
                        "entry_date",
                        "exit_date",
                        "realized_pnl",
                        "r_multiple",
                        "big_winner",
                        "entry_day_minute_bars",
                        "entry_day_first_0p5r_outcome",
                        "entry_day_first_1p0r_outcome",
                        "reentry_cross_count_after_05r_stop",
                    ]
                    if col in entry_features.columns
                ]
            ].head(40),
            max_rows=40,
        ),
        "",
        "## 新增覆盖 entry-day bucket",
        "",
        _md_table(bucket_stats.head(80), max_rows=80),
        "",
        "## 新增覆盖压力 key dates",
        "",
        _md_table(pressure_features.head(30), max_rows=30),
        "",
        "## 图谱输出",
        "",
        *[f"- entry atlas：`{path}`" for path in entry_paths],
        f"- pressure atlas：`{PATCH_PRESSURE_ATLAS_PATH}`",
        "",
        "## 判断",
        "",
        "- Stage857 只把 Stage855 的新增分钟K覆盖转成视觉证据，没有支持任何新规则上线。",
        "- 新增覆盖样本里包含大赢家和大亏损，适合作为后续复盘材料；但仍缺 `FG209/fu2205/fu2209/rb2210/FG601/AP210/lc2401` 等关键 exact dates。",
        "- 下一步仍应补数并重跑全量 Stage825/849 图谱；不能根据本阶段局部样本继续扫 `R` 倍数、OR 窗口或重试次数。",
        "",
        "## 输出文件",
        "",
        f"- patch_entry_features：`{PATCH_ENTRY_FEATURES_PATH}`",
        f"- patch_entry_bucket_stats：`{PATCH_ENTRY_BUCKET_PATH}`",
        f"- patch_pressure_features：`{PATCH_PRESSURE_FEATURES_PATH}`",
        f"- entry_atlas_manifest：`{PATCH_ENTRY_ATLAS_MANIFEST_PATH}`",
        f"- pressure_atlas_manifest：`{PATCH_PRESSURE_ATLAS_MANIFEST_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段只做已恢复数据的视觉审计，不改规则。",
        "- 运行后判断：否。但如果用这 `24` 笔新增 entry-day 覆盖反推新阈值，就会过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。Stage855 已恢复的数据必须被转成可读图谱，否则补数收益停留在覆盖率表。",
        "- 运行后判断：有价值但仍受限。图谱能帮助人工识别形态，但全周期规则验证仍依赖剩余关键分钟K补齐。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    request_coverage = _load_csv(REQUEST_COVERAGE_PATH)
    pressure_coverage = _load_csv(PRESSURE_COVERAGE_PATH)
    closed_lots = _load_csv(STAGE825_CLOSED_PATH)
    patch_bars = _load_patch_bars()

    entry_lots = _patch_entry_lots(request_coverage, closed_lots)
    pressure_patch_rows = pressure_coverage[
        pd.to_numeric(pressure_coverage["stage855_patch_bars"], errors="coerce").fillna(0).gt(0)
    ].copy()
    vt_symbols = set(entry_lots["vt_symbol"].astype(str).dropna().unique())
    vt_symbols.update(pressure_patch_rows["vt_symbol"].astype(str).dropna().unique())
    minute_bars = _combined_minute_bars(vt_symbols, patch_bars)

    entry_features = _patch_entry_features(entry_lots, minute_bars)
    bucket_stats = _bucket_stats(entry_features)
    entry_paths, entry_manifest = _plot_entry_atlas(entry_features, minute_bars)

    pressure_features = _pressure_patch_features(pressure_coverage, minute_bars)
    pressure_manifest = _plot_pressure_atlas(pressure_features, minute_bars)

    stage856_permission_blocked = 0
    if STAGE856_SUMMARY_PATH.exists():
        stage856_summary = _load_csv(STAGE856_SUMMARY_PATH)
        if "permission_blocked_batches" in stage856_summary.columns and not stage856_summary.empty:
            stage856_permission_blocked = int(_safe_float(stage856_summary.iloc[0]["permission_blocked_batches"], 0.0))

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "decision": "stage857_stage855_patch_visual_atlas_no_rule",
                "patch_minute_bars": int(len(patch_bars)),
                "patch_entry_lots": int(len(entry_features)),
                "patch_entry_big_winner_lots": int(
                    pd.to_numeric(entry_features.get("big_winner", 0), errors="coerce").fillna(0).sum()
                )
                if not entry_features.empty
                else 0,
                "patch_entry_pnl_sum": float(pd.to_numeric(entry_features.get("realized_pnl", 0), errors="coerce").fillna(0).sum())
                if not entry_features.empty
                else 0.0,
                "patch_pressure_key_dates": int(len(pressure_features)),
                "patch_pressure_minute_bars": int(pd.to_numeric(pressure_features.get("minute_bars", 0), errors="coerce").fillna(0).sum())
                if not pressure_features.empty
                else 0,
                "entry_atlas_pages": int(len(entry_paths)),
                "pressure_atlas_pages": int(1 if not pressure_features.empty else 0),
                "stage856_permission_blocked_batches": stage856_permission_blocked,
                "new_rule_allowed": 0,
                "engine_allowed": 0,
            }
        ]
    )

    entry_features.to_csv(PATCH_ENTRY_FEATURES_PATH, index=False, encoding="utf-8-sig")
    bucket_stats.to_csv(PATCH_ENTRY_BUCKET_PATH, index=False, encoding="utf-8-sig")
    pressure_features.to_csv(PATCH_PRESSURE_FEATURES_PATH, index=False, encoding="utf-8-sig")
    entry_manifest.to_csv(PATCH_ENTRY_ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    pressure_manifest.to_csv(PATCH_PRESSURE_ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage857_stage855_patch_visual_atlas_no_rule",
        "new_rule_allowed": 0,
        "engine_allowed": 0,
        "metrics": summary.iloc[0].to_dict(),
        "inputs": {
            "stage855_patch_bars": str(PATCH_BARS_PATH),
            "stage855_request_coverage": str(REQUEST_COVERAGE_PATH),
            "stage855_pressure_coverage": str(PRESSURE_COVERAGE_PATH),
            "stage825_closed_lots": str(STAGE825_CLOSED_PATH),
            "stage849_minute_features": str(STAGE849_MINUTE_PATH),
        },
        "outputs": {
            "patch_entry_features": str(PATCH_ENTRY_FEATURES_PATH),
            "patch_entry_bucket_stats": str(PATCH_ENTRY_BUCKET_PATH),
            "patch_pressure_features": str(PATCH_PRESSURE_FEATURES_PATH),
            "entry_atlas_manifest": str(PATCH_ENTRY_ATLAS_MANIFEST_PATH),
            "pressure_atlas_manifest": str(PATCH_PRESSURE_ATLAS_MANIFEST_PATH),
            "entry_atlas_paths": [str(path) for path in entry_paths],
            "pressure_atlas_path": str(PATCH_PRESSURE_ATLAS_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "judgement": (
            "Stage857 converts newly recovered local raw minute bars into visual evidence only. "
            "It does not justify a new rule while residual exact contract/date gaps remain."
        ),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, entry_features, bucket_stats, pressure_features, entry_paths)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
