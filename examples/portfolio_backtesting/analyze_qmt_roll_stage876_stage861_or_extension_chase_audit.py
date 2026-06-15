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
STAGE = "Stage876"
MODEL_TAG = "stage876_stage861_or_extension_chase_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage876_stage861_or_extension_chase_audit"

STAGE861_PREFIX = "qmt_roll_stage861_stage860_full_visual_atlas"
STAGE861_TAG = "stage861_stage860_full_visual_atlas_v1"

ENTRY_FEATURES_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_entry_lot_features_{STAGE861_TAG}.csv"
FULL_MINUTE_BARS_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_full_minute_bars_{STAGE861_TAG}.csv"

FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_{MODEL_TAG}.csv"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

OPENING_RANGE_BARS = 15
PER_PAGE = 4
MAX_ATLAS_ROWS = 20


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


def _prepare_features() -> pd.DataFrame:
    data = _load_required_csv(ENTRY_FEATURES_PATH).copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    numeric_columns = [
        "lot_id",
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "risk_pct",
        "stop_distance",
        "big_winner",
        "winner",
        "entry_day_minute_bars",
        "opening_range_high",
        "opening_range_low",
        "opening_range_width_pct",
        "opening_range_breakout_confirmed",
    ]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    data["winner"] = pd.to_numeric(data.get("winner"), errors="coerce").fillna(
        data["realized_pnl"].fillna(0).gt(0).astype(int)
    )
    data["big_winner"] = pd.to_numeric(data.get("big_winner"), errors="coerce").fillna(0).astype(int)

    width = (data["opening_range_high"] - data["opening_range_low"]).abs()
    width = width.where(width.gt(0))
    sign = data["direction"].map(lambda item: _direction_sign(item))
    signal_edge = np.where(
        data["direction"].astype(str).eq("long"),
        data["opening_range_high"],
        data["opening_range_low"],
    )
    data["or_width_abs"] = width
    data["or_signal_edge"] = signal_edge
    data["or_extension"] = sign * (data["entry_price"] - data["or_signal_edge"]) / data["or_width_abs"]
    data["or_extension"] = pd.to_numeric(data["or_extension"], errors="coerce")

    data["or_extension_bucket"] = "missing_or"
    data.loc[data["or_extension"].le(0), "or_extension_bucket"] = "inside_or_or_opposite"
    data.loc[data["or_extension"].gt(0) & data["or_extension"].le(1), "or_extension_bucket"] = "edge_to_1or"
    data.loc[data["or_extension"].gt(1), "or_extension_bucket"] = "extended_gt_1or"
    data["or_beyond_edge"] = data["or_extension"].gt(0).astype(int)
    return data.reset_index(drop=True)


def _load_minute_bars() -> pd.DataFrame:
    data = _load_required_csv(FULL_MINUTE_BARS_PATH)
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close"]).reset_index(
        drop=True
    )


def _bucket_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, group in features.groupby("or_extension_bucket", dropna=False):
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "bucket": str(bucket),
                "lots": int(len(group)),
                "lot_pct": float(len(group) / len(features) * 100.0) if len(features) else 0.0,
                "pnl_sum": float(pnl.sum()),
                "abs_pnl_sum": float(pnl.abs().sum()),
                "win_rate_pct": float(pd.to_numeric(group["winner"], errors="coerce").fillna(0).mean() * 100.0)
                if len(group)
                else np.nan,
                "median_r": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                "median_or_extension": float(pd.to_numeric(group["or_extension"], errors="coerce").median()),
                "big_winner_lots": int(pd.to_numeric(group["big_winner"], errors="coerce").fillna(0).sum()),
                "winner_pnl": float(pnl[pnl.gt(0)].sum()),
                "loser_pnl": float(pnl[pnl.lt(0)].sum()),
            }
        )
    order = {
        "inside_or_or_opposite": 0,
        "edge_to_1or": 1,
        "extended_gt_1or": 2,
        "missing_or": 3,
    }
    result = pd.DataFrame(rows)
    if not result.empty:
        result["sort_key"] = result["bucket"].map(order).fillna(99)
        result = result.sort_values("sort_key").drop(columns=["sort_key"]).reset_index(drop=True)
    return result


def _proxy_masks(features: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    edge_to_1or = features["or_extension"].gt(0) & features["or_extension"].le(1)
    extended_gt_1or = features["or_extension"].gt(1)
    all_beyond = features["or_extension"].gt(0)
    return [
        (
            "P1_block_edge_to_1or",
            "Skip entries whose entry price is beyond the signal-side OR15 edge but within 1x OR width.",
            edge_to_1or,
        ),
        (
            "P2_block_extended_gt_1or",
            "Skip entries whose entry price is more than 1x OR width beyond the signal-side OR15 edge.",
            extended_gt_1or,
        ),
        (
            "P3_block_all_beyond_edge",
            "Skip entries whose entry price is already beyond the signal-side OR15 edge.",
            all_beyond,
        ),
    ]


def _proxy_summary(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    original = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    base_total = float(original.sum())
    rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    for proxy_id, rule_text, mask in _proxy_masks(features):
        affected = mask.fillna(False)
        delta = pd.Series(0.0, index=features.index)
        delta.loc[affected] = -original.loc[affected]
        winners = affected & original.gt(0)
        losers = affected & original.lt(0)
        big = affected & features["big_winner"].eq(1)
        yearly_delta = (
            pd.DataFrame({"entry_year": features["entry_year"], "delta": delta, "original": original, "affected": affected})
            .groupby("entry_year", dropna=False)
            .agg(delta=("delta", "sum"), affected=("affected", "sum"), original=("original", "sum"))
            .reset_index()
        )
        rows.append(
            {
                "proxy_id": proxy_id,
                "rule_text": rule_text,
                "all_lots": int(len(features)),
                "affected_lots": int(affected.sum()),
                "affected_lot_pct": float(affected.mean() * 100.0),
                "affected_original_pnl": float(original.loc[affected].sum()),
                "gross_proxy_delta": float(delta.sum()),
                "base_total_pnl": base_total,
                "proxy_total_pnl": float(base_total + delta.sum()),
                "winner_cut": float(delta.loc[winners].sum()),
                "loser_saved": float(delta.loc[losers].sum()),
                "big_winner_cut": float(delta.loc[big].sum()),
                "affected_big_winner_lots": int(big.sum()),
                "positive_delta_years": int(yearly_delta["delta"].gt(0).sum()),
                "negative_delta_years": int(yearly_delta["delta"].lt(0).sum()),
                "worst_year_delta": float(yearly_delta["delta"].min()) if not yearly_delta.empty else 0.0,
                "best_year_delta": float(yearly_delta["delta"].max()) if not yearly_delta.empty else 0.0,
                "decision": "proxy_only_not_promoted_live_semantics_and_right_tail_risk",
            }
        )
        for _, item in yearly_delta.iterrows():
            year_mask = features["entry_year"].eq(item["entry_year"])
            yearly_rows.append(
                {
                    "proxy_id": proxy_id,
                    "entry_year": int(item["entry_year"]) if pd.notna(item["entry_year"]) else 0,
                    "lots": int(year_mask.sum()),
                    "affected_lots": int(item["affected"]),
                    "original_pnl": float(item["original"]),
                    "gross_proxy_delta": float(item["delta"]),
                    "winner_cut": float(delta.loc[year_mask & winners].sum()),
                    "loser_saved": float(delta.loc[year_mask & losers].sum()),
                    "big_winner_cut": float(delta.loc[year_mask & big].sum()),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(yearly_rows)


def _plot_summary_chart(bucket_summary: pd.DataFrame, proxy_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 5), constrained_layout=True)
    bucket = bucket_summary.copy()
    axes[0].bar(bucket["bucket"], bucket["pnl_sum"], color=["#2563eb", "#f59e0b", "#ef4444", "#6b7280"])
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("Actual PnL by OR extension bucket")
    axes[0].tick_params(axis="x", rotation=25, labelsize=8)
    axes[0].grid(axis="y", alpha=0.2)

    proxy = proxy_summary.copy()
    axes[1].bar(proxy["proxy_id"], proxy["gross_proxy_delta"], color="#7c3aed")
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Skip-trade proxy delta")
    axes[1].tick_params(axis="x", rotation=25, labelsize=8)
    axes[1].grid(axis="y", alpha=0.2)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    beyond = features[features["or_extension"].gt(0)].copy()
    inside = features[features["or_extension"].le(0)].copy()
    parts = [
        beyond.sort_values("realized_pnl", ascending=True).head(8),
        beyond.sort_values("realized_pnl", ascending=False).head(6),
        inside[inside["big_winner"].eq(1)].sort_values("realized_pnl", ascending=False).head(4),
        inside.sort_values("realized_pnl", ascending=True).head(2),
    ]
    selected = pd.concat(parts, ignore_index=True)
    selected = selected.drop_duplicates("lot_id").head(MAX_ATLAS_ROWS)
    return selected.reset_index(drop=True)


def _plot_row(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    lot_id = int(row["lot_id"])
    vt_symbol = str(row["vt_symbol"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = bars[bars["bar_date"].eq(entry_date)].copy() if not bars.empty else pd.DataFrame()
    record = {
        "lot_id": lot_id,
        "vt_symbol": vt_symbol,
        "entry_date": entry_date.strftime("%Y-%m-%d") if pd.notna(entry_date) else "",
        "chart_missing_minutes": int(day.empty),
    }
    if day.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"missing minute bars\nlot{lot_id} {vt_symbol}", ha="center", va="center")
        return record

    window = day.sort_values("bar_datetime").head(240).reset_index(drop=True)
    s825._plot_candles(ax, window)
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("risk_pct"))
    direction = str(row.get("direction"))
    sign = _direction_sign(direction)
    ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.9, label="entry")
    if np.isfinite(entry_price) and np.isfinite(risk_pct) and risk_pct > 0:
        ax.axhline(entry_price * (1.0 - sign * 0.5 * risk_pct), color="#ef4444", linewidth=0.9, alpha=0.85)
        ax.axhline(entry_price * (1.0 + sign * 1.0 * risk_pct), color="#16a34a", linewidth=0.9, alpha=0.85)
    if len(window) >= OPENING_RANGE_BARS:
        opening = window.head(OPENING_RANGE_BARS)
        or_high = float(opening["high"].max())
        or_low = float(opening["low"].min())
        ax.axhline(or_high, color="#7c3aed", linestyle="--", linewidth=0.8, alpha=0.75, label="OR high")
        ax.axhline(or_low, color="#7c3aed", linestyle="--", linewidth=0.8, alpha=0.75, label="OR low")
        ax.axvspan(0, OPENING_RANGE_BARS - 1, color="#fef3c7", alpha=0.22)
    ticks = np.linspace(0, len(window) - 1, num=min(7, len(window)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    title = (
        f"lot{lot_id} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
        f"bucket={row.get('or_extension_bucket')} ext={_safe_float(row.get('or_extension')):.2f} "
        f"pnl={_safe_float(row.get('realized_pnl')):,.0f} R={_safe_float(row.get('r_multiple')):.2f}"
    )
    ax.set_title(title, fontsize=8.5, loc="left")
    return record


def _plot_atlas(features: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(features)
    minute_by_symbol = s825._minute_groups(minute_bars)
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    page_count = int(math.ceil(len(selected) / PER_PAGE)) if len(selected) else 0
    for page in range(1, page_count + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.2 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            rec = _plot_row(ax, row, minute_by_symbol)
            rec.update(
                {
                    "chart_page": page,
                    "or_extension_bucket": str(row.get("or_extension_bucket", "")),
                    "or_extension": _safe_float(row.get("or_extension")),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                }
            )
            records.append(rec)
        fig.suptitle(
            (
                f"Stage876 OR extension chase audit page {page}/{page_count}; "
                "blue=entry, red=0.5R stop, green=1R target, purple=OR15"
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
    bucket_summary: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    yearly: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    lines = [
        "# Stage876 OR Extension Chase Audit",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读代理审计；不改正式版、不改候选配置、不连接 CTP、不调用下单、不接真实引擎。",
        "",
        "## 外部调研判断",
        "",
        "- Turtle/whipsaw 规则支持预定义突破、止损和重入，但不支持按个别亏损事后救参。",
        "- Opening Range Breakout 类规则把早盘区间作为自然尺度；本阶段只用固定 `OR15` 和 `1x OR width`，不扫参数。",
        "- 我的判断：如果入场价已经在信号方向超过开盘区间边界太多，可能是追价；但如果跳过会砍右尾或年度不稳，就不能接引擎。",
        "",
        "## Bucket Summary",
        "",
        _md_table(bucket_summary, max_rows=20),
        "",
        "## Proxy Summary",
        "",
        _md_table(proxy_summary, max_rows=20),
        "",
        "## Yearly Proxy",
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
        "- 决策：`stage876_or_extension_chase_proxy_not_promoted_no_engine`",
        "- 理由：`all_beyond_edge` skip proxy 表面增加 PnL，但同时砍掉大额赢家，且正贡献集中在 2022/2023，2021 为明显负贡献；这更像压力年份追价标签，不是可穿越周期的分钟级入场规则。",
        "- 下一步：不接 OR extension 真实引擎，不扫 OR 分钟数、OR width 倍数、品种、方向或年份；若继续，必须换成更本质的账户/持仓层生存线或暂停本线。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _prepare_features()
    minute_bars = _load_minute_bars()
    bucket = _bucket_summary(features)
    proxy, yearly = _proxy_summary(features)
    _plot_summary_chart(bucket, proxy)
    atlas_paths, atlas_manifest = _plot_atlas(features, minute_bars)

    features.to_csv(FEATURES_PATH, index=False, encoding="utf-8-sig")
    bucket.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(features, bucket, proxy, yearly, atlas_paths)

    all_beyond = proxy[proxy["proxy_id"].eq("P3_block_all_beyond_edge")].iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "entry_lots": int(len(features)),
        "decision": "stage876_or_extension_chase_proxy_not_promoted_no_engine",
        "all_beyond_edge": {
            "affected_lots": int(all_beyond.get("affected_lots", 0)),
            "gross_proxy_delta": _safe_float(all_beyond.get("gross_proxy_delta")),
            "winner_cut": _safe_float(all_beyond.get("winner_cut")),
            "loser_saved": _safe_float(all_beyond.get("loser_saved")),
            "big_winner_cut": _safe_float(all_beyond.get("big_winner_cut")),
            "positive_delta_years": int(all_beyond.get("positive_delta_years", 0)),
            "negative_delta_years": int(all_beyond.get("negative_delta_years", 0)),
        },
        "next_action": "Do not promote OR extension chase filter; stop OR width/threshold scans.",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
