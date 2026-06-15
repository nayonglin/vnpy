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
import analyze_qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit as s889
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage890"
MODEL_TAG = "stage890_stage889_first60_volume_triad_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage890_stage889_first60_volume_triad_audit"

FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
TRIAD_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_triad_summary_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
PROXY_YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_yearly_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

EARLY_BARS = 60
PER_PAGE = 4
MAX_ATLAS_ROWS = 24


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


def _prepare_stage889_features() -> pd.DataFrame:
    if s889.FEATURES_PATH.exists():
        data = _load_required_csv(s889.FEATURES_PATH)
    else:
        data = s889._build_features()
    for column in ["entry_date", "exit_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    numeric_columns = [
        "lot_id",
        "entry_price",
        "volume",
        "size",
        "realized_pnl",
        "r_multiple",
        "winner",
        "big_winner",
        "early_volume_sum",
        "early_price_dir_return_pct",
        "early_oi_change_pct",
        "early_exit_delta",
        "early_exit_pnl",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    return data.reset_index(drop=True)


def _first60_volume_table(minute_bars: pd.DataFrame) -> pd.DataFrame:
    bars = minute_bars.copy()
    bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce")
    bars["bar_date"] = pd.to_datetime(bars["bar_date"], errors="coerce").dt.normalize()
    bars["volume"] = pd.to_numeric(bars["volume"], errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    for (vt_symbol, bar_date), group in bars.groupby(["vt_symbol", "bar_date"], dropna=False):
        first = group.sort_values("bar_datetime").head(EARLY_BARS)
        rows.append(
            {
                "vt_symbol": str(vt_symbol),
                "bar_date": pd.Timestamp(bar_date).normalize(),
                "first60_bars": int(len(first)),
                "first60_volume_sum": float(first["volume"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["vt_symbol", "bar_date"]).reset_index(drop=True)


def _previous_volume_lookup(features: pd.DataFrame, volume_table: pd.DataFrame) -> pd.DataFrame:
    by_symbol = {
        str(vt_symbol): group.sort_values("bar_date").reset_index(drop=True)
        for vt_symbol, group in volume_table.groupby("vt_symbol", dropna=False)
    }
    records: list[dict[str, Any]] = []
    for _, row in features.iterrows():
        vt_symbol = str(row.get("vt_symbol", ""))
        entry_date = pd.Timestamp(row.get("entry_date")).normalize()
        current_volume = _safe_float(row.get("early_volume_sum"))
        table = by_symbol.get(vt_symbol, pd.DataFrame())
        prev = table[table["bar_date"].lt(entry_date)].tail(1) if not table.empty else pd.DataFrame()
        prev_volume = _safe_float(prev.iloc[0]["first60_volume_sum"]) if not prev.empty else np.nan
        prev_date = pd.Timestamp(prev.iloc[0]["bar_date"]).strftime("%Y-%m-%d") if not prev.empty else ""
        ratio = current_volume / prev_volume if prev_volume > 0 and np.isfinite(current_volume) else np.nan
        if not np.isfinite(ratio):
            state = "volume_missing"
        elif ratio > 1.0:
            state = "volume_expanded"
        else:
            state = "volume_faded_or_equal"
        records.append(
            {
                "lot_id": int(_safe_float(row.get("lot_id"), -1)),
                "prev_first60_volume_date": prev_date,
                "prev_first60_volume_sum": prev_volume,
                "early_volume_ratio_to_prev": ratio,
                "early_volume_state": state,
            }
        )
    return pd.DataFrame(records)


def _build_features() -> pd.DataFrame:
    features = _prepare_stage889_features()
    minute_bars = s889._prepare_minute_bars(set(features["vt_symbol"].astype(str).dropna()))
    volume_table = _first60_volume_table(minute_bars)
    volume_lookup = _previous_volume_lookup(features, volume_table)
    data = features.merge(volume_lookup, on="lot_id", how="left")
    price = pd.to_numeric(data["early_price_dir_return_pct"], errors="coerce")
    oi = pd.to_numeric(data["early_oi_change_pct"], errors="coerce")
    data["early_price_side"] = np.where(price.ge(0), "price_favorable", "price_adverse")
    data.loc[price.isna(), "early_price_side"] = "price_missing"
    data["early_oi_side"] = np.where(oi.ge(0), "oi_up", "oi_down")
    data.loc[oi.isna(), "early_oi_side"] = "oi_missing"
    data["early_triad_state"] = (
        data["early_price_side"].astype(str)
        + "__"
        + data["early_oi_side"].astype(str)
        + "__"
        + data["early_volume_state"].astype(str)
    )
    return data


def _triad_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_loser_pnl = float(pd.to_numeric(features["realized_pnl"], errors="coerce").clip(upper=0).sum())
    for state, group in features.groupby("early_triad_state", dropna=False):
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        loser_pnl = float(pnl[pnl.lt(0)].sum())
        rows.append(
            {
                "early_triad_state": str(state),
                "lots": int(len(group)),
                "lot_pct": float(len(group) / len(features) * 100.0) if len(features) else 0.0,
                "pnl_sum": float(pnl.sum()),
                "loser_lots": int(pnl.lt(0).sum()),
                "loser_pnl": loser_pnl,
                "loser_pnl_coverage_pct": float(abs(loser_pnl) / abs(total_loser_pnl) * 100.0)
                if total_loser_pnl < 0
                else 0.0,
                "winner_lots": int(pnl.gt(0).sum()),
                "winner_pnl": float(pnl[pnl.gt(0)].sum()),
                "big_winner_lots": int(pd.to_numeric(group["big_winner"], errors="coerce").fillna(0).sum()),
                "median_r": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                "median_volume_ratio_to_prev": float(
                    pd.to_numeric(group["early_volume_ratio_to_prev"], errors="coerce").median()
                ),
                "median_early_price_dir_return_pct": float(
                    pd.to_numeric(group["early_price_dir_return_pct"], errors="coerce").median()
                ),
                "median_early_oi_change_pct": float(pd.to_numeric(group["early_oi_change_pct"], errors="coerce").median()),
            }
        )
    return pd.DataFrame(rows).sort_values(["loser_pnl_coverage_pct", "lots"], ascending=[False, False]).reset_index(drop=True)


def _proxy_definitions(features: pd.DataFrame) -> list[dict[str, Any]]:
    price_adverse = features["early_price_side"].eq("price_adverse")
    oi_up = features["early_oi_side"].eq("oi_up")
    oi_down = features["early_oi_side"].eq("oi_down")
    volume_expanded = features["early_volume_state"].eq("volume_expanded")
    volume_faded = features["early_volume_state"].eq("volume_faded_or_equal")
    return [
        {
            "proxy_id": "V1_exit60_adverse_oi_up_volume_expanded",
            "rule_text": "Exit at 60th-bar close if first60 price is adverse, OI is up, and first60 volume expands vs previous trading day.",
            "mask": price_adverse & oi_up & volume_expanded,
        },
        {
            "proxy_id": "V2_exit60_adverse_any_oi_volume_expanded",
            "rule_text": "Exit at 60th-bar close if first60 price is adverse and first60 volume expands vs previous trading day.",
            "mask": price_adverse & volume_expanded,
        },
        {
            "proxy_id": "V3_exit60_adverse_oi_down_volume_expanded",
            "rule_text": "Exit at 60th-bar close if first60 price is adverse, OI is down, and first60 volume expands vs previous trading day.",
            "mask": price_adverse & oi_down & volume_expanded,
        },
        {
            "proxy_id": "V4_exit60_adverse_oi_up_volume_faded",
            "rule_text": "Exit at 60th-bar close if first60 price is adverse, OI is up, and first60 volume is not expanded.",
            "mask": price_adverse & oi_up & volume_faded,
        },
        {
            "proxy_id": "V5_exit60_adverse_oi_down_volume_faded",
            "rule_text": "Exit at 60th-bar close if first60 price is adverse, OI is down, and first60 volume is not expanded.",
            "mask": price_adverse & oi_down & volume_faded,
        },
    ]


def _proxy_summary(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    original = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    base_total = float(original.sum())
    rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    for item in _proxy_definitions(features):
        trigger = item["mask"].fillna(False)
        applicable = trigger & pd.to_numeric(features["early_exit_delta"], errors="coerce").notna()
        delta = pd.Series(0.0, index=features.index)
        delta.loc[applicable] = pd.to_numeric(features.loc[applicable, "early_exit_delta"], errors="coerce").fillna(0.0)
        winners = applicable & original.gt(0)
        losers = applicable & original.lt(0)
        big = applicable & pd.to_numeric(features["big_winner"], errors="coerce").fillna(0).eq(1)
        yearly = (
            pd.DataFrame(
                {
                    "entry_year": features["entry_year"],
                    "affected": applicable.astype(int),
                    "delta": delta,
                    "winner_delta": np.where(winners, delta, 0.0),
                    "loser_delta": np.where(losers, delta, 0.0),
                    "big_delta": np.where(big, delta, 0.0),
                }
            )
            .groupby("entry_year", dropna=False)
            .agg(
                affected_lots=("affected", "sum"),
                gross_proxy_delta=("delta", "sum"),
                winner_cut=("winner_delta", "sum"),
                loser_saved=("loser_delta", "sum"),
                big_winner_cut=("big_delta", "sum"),
            )
            .reset_index()
        )
        gross_delta = float(delta.sum())
        rows.append(
            {
                "proxy_id": item["proxy_id"],
                "rule_text": item["rule_text"],
                "trigger_lots": int(trigger.sum()),
                "applicable_lots": int(applicable.sum()),
                "applicable_lot_pct": float(applicable.mean() * 100.0),
                "affected_original_pnl": float(original.loc[applicable].sum()),
                "gross_proxy_delta": gross_delta,
                "base_total_pnl": base_total,
                "proxy_total_pnl": base_total + gross_delta,
                "winner_cut": float(delta.loc[winners].sum()),
                "loser_saved": float(delta.loc[losers].sum()),
                "big_winner_cut": float(delta.loc[big].sum()),
                "affected_big_winner_lots": int(big.sum()),
                "positive_delta_years": int(yearly["gross_proxy_delta"].gt(0).sum()),
                "negative_delta_years": int(yearly["gross_proxy_delta"].lt(0).sum()),
                "decision_hint": "positive_proxy_only_needs_true_engine" if gross_delta > 0 else "not_promoted_proxy_negative",
            }
        )
        for _, year_row in yearly.iterrows():
            yearly_rows.append(
                {
                    "proxy_id": item["proxy_id"],
                    "entry_year": int(year_row["entry_year"]) if pd.notna(year_row["entry_year"]) else 0,
                    "affected_lots": int(year_row["affected_lots"]),
                    "gross_proxy_delta": float(year_row["gross_proxy_delta"]),
                    "winner_cut": float(year_row["winner_cut"]),
                    "loser_saved": float(year_row["loser_saved"]),
                    "big_winner_cut": float(year_row["big_winner_cut"]),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(yearly_rows)


def _decision(features: pd.DataFrame, proxy_summary: pd.DataFrame) -> str:
    positives = proxy_summary[proxy_summary["gross_proxy_delta"].gt(0)].copy()
    if positives.empty:
        return "stage890_first60_volume_triad_no_clean_rule_all_proxy_negative"
    best = positives.sort_values("gross_proxy_delta", ascending=False).iloc[0]
    loser_pnl = abs(float(pd.to_numeric(features["realized_pnl"], errors="coerce").clip(upper=0).sum()))
    if _safe_float(best.get("gross_proxy_delta"), 0.0) < loser_pnl * 0.01:
        return "stage890_first60_volume_triad_tiny_positive_proxy_no_engine"
    if int(_safe_float(best.get("positive_delta_years"), 0.0)) < int(_safe_float(best.get("negative_delta_years"), 0.0)):
        return "stage890_first60_volume_triad_year_fragile_no_engine"
    if _safe_float(best.get("winner_cut"), 0.0) < 0 and abs(_safe_float(best.get("winner_cut"), 0.0)) > _safe_float(
        best.get("loser_saved"), 0.0
    ):
        return "stage890_first60_volume_triad_winner_cut_too_high_no_engine"
    return "stage890_first60_volume_triad_has_frozen_candidate_proxy_only"


def _plot_summary(triad_summary: pd.DataFrame, proxy_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), constrained_layout=True)
    top = triad_summary.head(10).copy()
    axes[0].bar(top["early_triad_state"], top["loser_pnl_coverage_pct"], color="#dc2626")
    axes[0].set_title("C9 loser PnL coverage by first60 price/OI/volume triad")
    axes[0].set_ylabel("loser PnL coverage (%)")
    axes[0].tick_params(axis="x", rotation=25, labelsize=8)
    axes[0].grid(axis="y", alpha=0.2)

    colors = np.where(proxy_summary["gross_proxy_delta"].gt(0), "#16a34a", "#64748b")
    axes[1].bar(proxy_summary["proxy_id"], proxy_summary["gross_proxy_delta"] / 1_000_000, color=colors)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Exit60 proxy deltas by volume triad")
    axes[1].set_ylabel("delta, million")
    axes[1].tick_params(axis="x", rotation=20, labelsize=8)
    axes[1].grid(axis="y", alpha=0.2)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    candidate_states = (
        features[features["early_price_side"].eq("price_adverse")]
        .groupby("early_triad_state", dropna=False)["realized_pnl"]
        .agg(["count", "sum"])
        .reset_index()
        .sort_values(["count", "sum"], ascending=[False, True])
        .head(4)["early_triad_state"]
        .astype(str)
        .tolist()
    )
    parts: list[pd.DataFrame] = []
    for state in candidate_states:
        subset = features[features["early_triad_state"].astype(str).eq(state)].copy()
        if subset.empty:
            continue
        subset["atlas_triad_state"] = state
        parts.append(subset.sort_values("realized_pnl", ascending=True).head(3))
        parts.append(subset.sort_values("realized_pnl", ascending=False).head(3))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).drop_duplicates("lot_id").head(MAX_ATLAS_ROWS).reset_index(drop=True)


def _plot_row(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row["vt_symbol"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    direction = str(row["direction"])
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = (
        bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(240).reset_index(drop=True)
        if not bars.empty
        else pd.DataFrame()
    )
    record = {
        "lot_id": int(_safe_float(row.get("lot_id"), -1)),
        "vt_symbol": vt_symbol,
        "entry_date": entry_date.strftime("%Y-%m-%d") if pd.notna(entry_date) else "",
        "atlas_triad_state": str(row.get("atlas_triad_state", "")),
        "chart_missing_minutes": int(day.empty),
    }
    if day.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"missing minute bars\n{vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
        return record
    s825._plot_candles(ax, day)
    entry_price = _safe_float(row.get("entry_price"))
    risk_price = _safe_float(row.get("risk_price"))
    sign = 1.0 if direction == "long" else -1.0
    ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.9, label="entry")
    if risk_price > 0:
        ax.axhline(entry_price - sign * 0.5 * risk_price, color="#ef4444", linewidth=0.9, alpha=0.85, label="-0.5R")
        ax.axhline(entry_price + sign * 0.5 * risk_price, color="#22c55e", linewidth=0.9, alpha=0.85, label="+0.5R")
    if len(day) >= EARLY_BARS:
        ax.axvspan(0, EARLY_BARS - 1, color="#fef3c7", alpha=0.22)
    ax2 = ax.twinx()
    if "close_oi" in day.columns and pd.to_numeric(day["close_oi"], errors="coerce").notna().any():
        ax2.plot(np.arange(len(day)), day["close_oi"], color="#7c3aed", linewidth=0.7, alpha=0.55)
        ax2.tick_params(axis="y", labelsize=6, colors="#7c3aed")
    ticks = np.linspace(0, len(day) - 1, num=min(7, len(day)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        dedup = dict(zip(labels, handles))
        ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
    title = (
        f"lot{int(_safe_float(row.get('lot_id'), -1))} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
        f"{row.get('atlas_triad_state')} vol_ratio={_safe_float(row.get('early_volume_ratio_to_prev')):.2f} "
        f"p60={_safe_float(row.get('early_price_dir_return_pct')):.2f}% "
        f"oi60={_safe_float(row.get('early_oi_change_pct')):.2f}% "
        f"pnl={_safe_float(row.get('realized_pnl')):,.0f}"
    )
    ax.set_title(title, fontsize=8.0, loc="left")
    return record


def _plot_atlas(features: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(features)
    if selected.empty:
        return [], pd.DataFrame()
    minute_bars = s889._prepare_minute_bars(set(selected["vt_symbol"].astype(str).dropna()))
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
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "early_triad_state": str(row.get("early_triad_state", "")),
                    "early_volume_ratio_to_prev": _safe_float(row.get("early_volume_ratio_to_prev")),
                }
            )
            records.append(rec)
        fig.suptitle(
            (
                f"Stage890 first60 price/OI/volume triad atlas page {page}/{page_count}; "
                "blue=entry, red=-0.5R, green=+0.5R, purple=OI, shade=first60"
            ),
            fontsize=13,
        )
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _write_report(
    features: pd.DataFrame,
    triad_summary: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    proxy_yearly: pd.DataFrame,
    atlas_paths: list[Path],
    decision: str,
) -> None:
    lines = [
        "# Stage890 first60 price/OI/volume 三元参与度审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：C9 本体只读参与度审计；不新增交易规则、不接真实引擎、不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- CME open interest / volume 资料支持把 OI 与成交量视为趋势参与度辅助信息；CME stop order 资料支持预设风控纪律。",
        "- 我的判断：本阶段只验证 first60 逆向时，成交量相对前一交易日 first60 是否能区分失败和右尾修复；不扫描倍数阈值，只用 `>1` 这个结构性二分。",
        "",
        "## Triad Summary",
        "",
        _md_table(triad_summary, max_rows=30),
        "",
        "## Proxy Summary",
        "",
        _md_table(proxy_summary, max_rows=20),
        "",
        "## Proxy Yearly",
        "",
        _md_table(proxy_yearly, max_rows=100),
        "",
        "## Decision",
        "",
        f"- decision：`{decision}`",
        "- 结论：只有当成交量三元状态显著降低 winner-cut 且年度稳定，才允许下一步冻结真实引擎；否则只保留为复盘标签。",
        "",
        "## Visual Atlas",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in atlas_paths],
        "",
        "## 输出文件",
        "",
        f"- features：`{FEATURES_PATH}`",
        f"- triad summary：`{TRIAD_SUMMARY_PATH}`",
        f"- proxy summary：`{PROXY_SUMMARY_PATH}`",
        f"- proxy yearly：`{PROXY_YEARLY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。成交量只用相对前一交易日 first60 的 `>1` 二分，不扫阈值。",
        "- 运行后判断：以输出 decision 为准；若继续扫成交量倍数、分钟数、年份或品种，就是过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。成交量是与价格/OI 不同的一阶参与度信息。",
        "- 运行后判断：以输出 decision 为准；若成交量也不能降低误伤，本线应进一步远离分钟K本体小变体。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _build_features()
    triad_summary = _triad_summary(features)
    proxy_summary, proxy_yearly = _proxy_summary(features)
    decision = _decision(features, proxy_summary)
    _plot_summary(triad_summary, proxy_summary)
    atlas_paths, atlas_manifest = _plot_atlas(features)

    features.to_csv(FEATURES_PATH, index=False, encoding="utf-8-sig")
    triad_summary.to_csv(TRIAD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_yearly.to_csv(PROXY_YEARLY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(features, triad_summary, proxy_summary, proxy_yearly, atlas_paths, decision)

    best_proxy = proxy_summary.sort_values("gross_proxy_delta", ascending=False).iloc[0].to_dict()
    payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "decision": decision,
        "c9_closed_lots": int(len(features)),
        "best_proxy": best_proxy,
        "guardrails": {
            "strategy_changed": False,
            "official_stage372_changed": False,
            "official_candidate_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "formal_ab_triggered": False,
            "readonly_only": True,
            "new_rule_created": False,
        },
        "outputs": {
            "features": str(FEATURES_PATH),
            "triad_summary": str(TRIAD_SUMMARY_PATH),
            "proxy_summary": str(PROXY_SUMMARY_PATH),
            "proxy_yearly": str(PROXY_YEARLY_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
