from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage071"
MODEL_TAG = "stage071_initial_entry_proxy_mismatch_root_cause_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit"

SCRIPT_PATH = Path(__file__).resolve()
TOOL_DIR = SCRIPT_PATH.parent
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage068_initial_entry_tick_coverage_audit as s068


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage071_initial_entry_proxy_mismatch_root_cause_audit"
STAGE070_DIR = LINE_DIR / "outputs" / "stage070_initial_entry_price_proxy_anchor_batch_refill"

FEATURES_IN = (
    STAGE070_DIR
    / "qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_anchor_price_features_"
    "stage070_initial_entry_price_proxy_anchor_batch_refill_v1.csv"
)
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
MISMATCH_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mismatch_audit_{MODEL_TAG}.csv"
CLASS_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_class_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_mismatch_class_chart_{MODEL_TAG}.png"
DELTA_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_mismatch_delta_chart_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_mismatch_tick_atlas_{MODEL_TAG}.png"

OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"
NEAR_R_TOL = 0.05


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def _target_minute(anchor_time: Any) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.to_datetime(anchor_time, errors="coerce").floor("min")
    return start, start + pd.Timedelta(minutes=1)


def _load_proxy_features() -> pd.DataFrame:
    features = _read_csv(FEATURES_IN)
    proxy = features[features["anchor_role"].eq("price_proxy_anchor")].copy()
    for col in [
        "official_open_price",
        "nearest_price_value",
        "min_abs_price_delta",
        "min_abs_price_delta_r",
        "median_spread_r",
        "median_depth1",
        "risk_price",
        "realized_pnl",
    ]:
        if col in proxy.columns:
            proxy[col] = _safe_num(proxy[col])
    for col in ["anchor_ready", "price_exact_any", "price_near_r", "official_open_inside_any_spread"]:
        if col in proxy.columns:
            proxy[col] = _bool_series(proxy[col])
    proxy["anchor_time"] = pd.to_datetime(proxy["anchor_time"], errors="coerce")
    return proxy.sort_values(["anchor_time", "official_open_trade_id"]).reset_index(drop=True)


def _estimated_tick_size(prices: pd.Series) -> float:
    values = sorted({round(float(v), 8) for v in pd.to_numeric(prices, errors="coerce").dropna() if float(v) > 0})
    if len(values) < 2:
        return np.nan
    diffs = [round(values[i] - values[i - 1], 8) for i in range(1, len(values)) if values[i] > values[i - 1]]
    positive = [d for d in diffs if d > 0]
    return float(min(positive)) if positive else np.nan


def _classify(row: pd.Series, target: pd.DataFrame) -> dict[str, Any]:
    base = {
        "tick_rows_target": int(len(target)),
        "last_min": np.nan,
        "last_max": np.nan,
        "bid_min": np.nan,
        "bid_max": np.nan,
        "ask_min": np.nan,
        "ask_max": np.nan,
        "estimated_tick_size": np.nan,
        "delta_estimated_ticks": np.nan,
        "official_vs_book_position": "no_target_ticks",
        "root_cause_class": "no_target_ticks_unresolved",
        "root_cause_note": "",
    }
    official = float(row["official_open_price"]) if pd.notna(row.get("official_open_price")) else np.nan
    if target.empty or pd.isna(official):
        return base
    for col in ["last_price", "bid_price1", "ask_price1"]:
        target[col] = _safe_num(target[col]) if col in target.columns else np.nan
    price_values = pd.concat(
        [
            target.get("last_price", pd.Series(dtype=float)),
            target.get("bid_price1", pd.Series(dtype=float)),
            target.get("ask_price1", pd.Series(dtype=float)),
        ],
        ignore_index=True,
    )
    tick_size = _estimated_tick_size(price_values)
    min_abs_delta = float(row["min_abs_price_delta"]) if pd.notna(row.get("min_abs_price_delta")) else np.nan
    base["estimated_tick_size"] = tick_size
    if pd.notna(tick_size) and tick_size > 0 and pd.notna(min_abs_delta):
        base["delta_estimated_ticks"] = float(min_abs_delta / tick_size)
    for prefix, col in [("last", "last_price"), ("bid", "bid_price1"), ("ask", "ask_price1")]:
        if col in target.columns and target[col].notna().any():
            base[f"{prefix}_min"] = float(target[col].min())
            base[f"{prefix}_max"] = float(target[col].max())
    bid_min, bid_max = base["bid_min"], base["bid_max"]
    ask_min, ask_max = base["ask_min"], base["ask_max"]
    last_min, last_max = base["last_min"], base["last_max"]
    inside_spread = bool(row.get("official_open_inside_any_spread", False))
    near_r = bool(row.get("price_near_r", False))
    if pd.notna(bid_min) and official < bid_min:
        base["official_vs_book_position"] = "below_target_bid_range"
    elif pd.notna(ask_max) and official > ask_max:
        base["official_vs_book_position"] = "above_target_ask_range"
    elif pd.notna(last_min) and last_min <= official <= last_max:
        base["official_vs_book_position"] = "inside_target_last_range"
    elif pd.notna(bid_min) and pd.notna(ask_max) and bid_min <= official <= ask_max:
        base["official_vs_book_position"] = "inside_target_book_envelope"
    else:
        base["official_vs_book_position"] = "outside_target_tick_envelope"
    if inside_spread:
        base["root_cause_class"] = "inside_spread_not_exact"
        base["root_cause_note"] = "official price appears executable inside at least one target-minute top-book spread but no exact field match"
    elif near_r:
        base["root_cause_class"] = "near_005r_outside_spread"
        base["root_cause_note"] = "small R-normalized price gap outside target-minute spread; treat as price-basis tolerance candidate only"
    elif base["official_vs_book_position"] in ["below_target_bid_range", "above_target_ask_range"]:
        base["root_cause_class"] = "outside_target_book_range"
        base["root_cause_note"] = "official price is outside target-minute bid/ask range; inspect price source, continuous adjustment, or anchor convention"
    elif base["official_vs_book_position"] in ["inside_target_last_range", "inside_target_book_envelope"]:
        base["root_cause_class"] = "inside_target_range_not_exact"
        base["root_cause_note"] = "official price lies inside minute envelope but not exact last/bid/ask/mid sample"
    else:
        base["root_cause_class"] = "outside_target_tick_range_unresolved"
        base["root_cause_note"] = "official price is outside available target-minute tick fields"
    return base


def _build_mismatch_audit(proxy: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    mismatches = proxy[proxy["anchor_ready"] & ~proxy["price_exact_any"]].copy()
    for _, row in mismatches.iterrows():
        path = Path(str(row["tick_file_path"]))
        target = pd.DataFrame()
        if path.exists() and path.stat().st_size > 0:
            ticks = pd.read_csv(path, encoding="utf-8-sig")
            ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
            start, end = _target_minute(row["anchor_time"])
            target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
        details = _classify(row, target)
        rows.append(
            {
                "event_key": row["event_key"],
                "official_open_trade_id": row["official_open_trade_id"],
                "candidate_index": row["candidate_index"],
                "vt_symbol": row["vt_symbol"],
                "direction": row["direction"],
                "anchor_time": row["anchor_time"],
                "official_open_price": row["official_open_price"],
                "nearest_price_field": row.get("nearest_price_field", ""),
                "nearest_price_value": row.get("nearest_price_value", np.nan),
                "min_abs_price_delta": row.get("min_abs_price_delta", np.nan),
                "min_abs_price_delta_r": row.get("min_abs_price_delta_r", np.nan),
                "median_spread_r": row.get("median_spread_r", np.nan),
                "official_open_inside_any_spread": row.get("official_open_inside_any_spread", False),
                "price_near_r": row.get("price_near_r", False),
                "realized_pnl": row.get("realized_pnl", 0.0),
                "normalized_product": row.get("normalized_product", ""),
                "product_family": row.get("product_family", ""),
                "timestamp_alignment_class": row.get("timestamp_alignment_class", ""),
                "tick_file_path": row.get("tick_file_path", ""),
                **details,
            }
        )
    return pd.DataFrame(rows).sort_values(["anchor_time", "event_key"]).reset_index(drop=True)


def _class_summary(audit: pd.DataFrame) -> pd.DataFrame:
    if audit.empty:
        return pd.DataFrame()
    return (
        audit.groupby("root_cause_class", as_index=False)
        .agg(
            mismatch_count=("event_key", "size"),
            net_realized_pnl=("realized_pnl", "sum"),
            median_delta_r=("min_abs_price_delta_r", "median"),
            max_delta_r=("min_abs_price_delta_r", "max"),
            inside_spread_count=("official_open_inside_any_spread", "sum"),
            near_r_count=("price_near_r", "sum"),
        )
        .sort_values(["mismatch_count", "root_cause_class"], ascending=[False, True])
    )


def _official_metrics() -> dict[str, Any]:
    return s068._official_metrics()


def _official_curve() -> pd.DataFrame:
    return s068._official_curve()


def _plot_path(proxy: pd.DataFrame, audit: pd.DataFrame) -> None:
    curve = _official_curve()
    proxy = proxy.copy()
    proxy["class_for_plot"] = np.where(proxy["price_exact_any"], "price_proxy_exact", "price_proxy_mismatch")
    events = proxy.sort_values("anchor_time")
    palette = {"price_proxy_exact": "#009e73", "price_proxy_mismatch": "#d55e00"}
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=False)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#0072b2", linewidth=2.0)
    for cls, data in events.groupby("class_for_plot"):
        axes[0].scatter(
            data["anchor_time"],
            np.interp(data["anchor_time"].astype("int64"), curve["date"].astype("int64"), curve["account_equity"] / 1_000_000),
            color=palette.get(cls, "#999999"),
            s=34,
            alpha=0.72,
            label=cls,
        )
    axes[0].set_title("Stage071 official path by proxy exact/mismatch class")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)
    if not audit.empty:
        for cls, data in audit.groupby("root_cause_class"):
            data = data.sort_values("anchor_time").copy()
            data["cum_pnl"] = data["realized_pnl"].cumsum()
            axes[1].plot(data["anchor_time"], data["cum_pnl"] / 10_000, marker="o", linewidth=1.5, label=cls)
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_title("Mismatch cumulative PnL by root-cause class")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].grid(alpha=0.25)
    axes[1].legend(loc="upper left", fontsize=7)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_delta(audit: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    if audit.empty:
        for ax in axes:
            ax.text(0.5, 0.5, "No mismatches", ha="center", va="center")
            ax.set_axis_off()
    else:
        for cls, data in audit.groupby("root_cause_class"):
            axes[0].scatter(data["anchor_time"], data["min_abs_price_delta_r"], s=70, label=cls, alpha=0.82)
        axes[0].axhline(NEAR_R_TOL, color="black", linestyle="--", linewidth=1.0)
        axes[0].set_title("Proxy mismatch delta / R over time")
        axes[0].set_ylabel("min abs price delta / R")
        axes[0].grid(alpha=0.25)
        axes[0].legend(fontsize=7)
        summary = _class_summary(audit)
        axes[1].barh(summary["root_cause_class"], summary["mismatch_count"], color="#d55e00", alpha=0.78)
        axes[1].set_title("Mismatch count by root-cause class")
        axes[1].grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(DELTA_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_atlas(audit: pd.DataFrame) -> None:
    if audit.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No mismatches", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(ATLAS_OUT, dpi=180)
        plt.close(fig)
        return
    data = audit.sort_values("min_abs_price_delta_r", ascending=False).head(14).copy()
    n = len(data)
    fig, axes = plt.subplots(n, 1, figsize=(14, max(4, 2.35 * n)), squeeze=False)
    for i, (_, row) in enumerate(data.iterrows()):
        ax = axes[i, 0]
        path = Path(str(row["tick_file_path"]))
        ticks = pd.DataFrame()
        if path.exists():
            ticks = pd.read_csv(path, encoding="utf-8-sig")
            ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
            start, end = _target_minute(row["anchor_time"])
            ticks = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
        for col, color, label in [
            ("last_price", "#0072b2", "last"),
            ("ask_price1", "#d55e00", "ask1"),
            ("bid_price1", "#009e73", "bid1"),
        ]:
            if not ticks.empty and col in ticks.columns:
                ticks[col] = _safe_num(ticks[col])
                ax.plot(ticks["tick_datetime"], ticks[col], color=color, linewidth=1.0, label=label)
        ax.axhline(float(row["official_open_price"]), color="black", linestyle="--", linewidth=0.9, label="official open")
        title = (
            f"{row['official_open_trade_id']} {row['vt_symbol']} {pd.to_datetime(row['anchor_time']).strftime('%Y-%m-%d %H:%M')} "
            f"deltaR={row['min_abs_price_delta_r']:.3f} class={row['root_cause_class']}"
        )
        ax.set_title(title, fontsize=8)
        ax.grid(alpha=0.22)
        ax.legend(loc="upper left", fontsize=6)
    fig.tight_layout()
    fig.savefig(ATLAS_OUT, dpi=180)
    plt.close(fig)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s068._md_table(frame, max_rows=max_rows)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, audit: pd.DataFrame) -> None:
    lines = [
        "# Stage071 初始开仓 proxy mismatch 根因审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 当前正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- Stage070 proxy ready：`{decision['stage070_proxy_ready_count']}`；exact：`{decision['stage070_proxy_exact_count']}`；mismatch：`{decision['mismatch_count']}`。",
        f"- mismatch near <=0.05R：`{decision['near_mismatch_count']}`；far >0.05R：`{decision['far_mismatch_count']}`。",
        "- 本阶段不新增交易规则、不跑 true engine、不触发 A/B；只解释 price proxy mismatch 的数据口径。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{decision['official_metrics'].get('end_equity')}`",
        f"- 总收益：`{decision['official_metrics'].get('total_return_pct')}`",
        f"- 最大回撤：`{decision['official_metrics'].get('max_drawdown_pct')}`",
        f"- Sharpe：`{decision['official_metrics'].get('sharpe')}`",
        f"- 总滑点：`{decision['official_metrics'].get('total_slippage')}`",
        f"- 总交易次数：`{decision['official_metrics'].get('total_trade_count')}`",
        "",
        "## 根因分类",
        "",
        _md_table(summary),
        "",
        "## mismatch 样本",
        "",
        _md_table(
            audit[
                [
                    "official_open_trade_id",
                    "vt_symbol",
                    "anchor_time",
                    "official_open_price",
                    "nearest_price_value",
                    "min_abs_price_delta_r",
                    "official_vs_book_position",
                    "root_cause_class",
                    "realized_pnl",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 视觉文件",
        "",
        f"- path/class chart：`{PATH_CHART_OUT}`",
        f"- delta/root chart：`{DELTA_CHART_OUT}`",
        f"- mismatch atlas：`{ATLAS_OUT}`",
        "",
        "## 判断",
        "",
        "- Stage070 的 mismatch 不能当作交易信号，因为 mismatch 组净 PnL 仍为正，且分布跨交易所和时段。",
        "- 可接受近似误差与盘口外价格源差异必须分开；否则直接抽取 spread/depth 会把价格口径误差误判为微观结构信号。",
        "- 下一步应先修正或标记 price source/root-cause，再决定是否继续补全 219 笔 proxy tick。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    proxy = _load_proxy_features()
    audit = _build_mismatch_audit(proxy)
    summary = _class_summary(audit)
    _write_csv(audit, MISMATCH_AUDIT_OUT)
    _write_csv(summary, CLASS_SUMMARY_OUT)

    exact_count = int(proxy["price_exact_any"].sum())
    proxy_ready = int(proxy["anchor_ready"].sum())
    mismatch_count = int(len(audit))
    near_count = int(audit["price_near_r"].sum()) if not audit.empty else 0
    far_count = int((~audit["price_near_r"]).sum()) if not audit.empty else 0
    unresolved = int(audit["root_cause_class"].str.contains("outside_target_book_range|outside_target_tick_range", regex=True).sum()) if not audit.empty else 0
    if unresolved > 0:
        decision_text = "stage071_proxy_mismatch_root_cause_unresolved_no_rule"
        next_step = "inspect_price_source_continuous_adjustment_and_anchor_convention_before_more_tca"
    else:
        decision_text = "stage071_proxy_mismatch_mostly_tolerance_classified_no_rule"
        next_step = "continue_proxy_refill_with_root_cause_labels_and_no_trade_rules"
    official_metrics = _official_metrics()
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_metrics": official_metrics,
        "decision": decision_text,
        "next_step": next_step,
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "stage070_proxy_ready_count": proxy_ready,
        "stage070_proxy_exact_count": exact_count,
        "mismatch_count": mismatch_count,
        "near_mismatch_count": near_count,
        "far_mismatch_count": far_count,
        "unresolved_mismatch_count": unresolved,
        "outputs": {
            "mismatch_audit": MISMATCH_AUDIT_OUT,
            "class_summary": CLASS_SUMMARY_OUT,
            "path_chart": PATH_CHART_OUT,
            "delta_chart": DELTA_CHART_OUT,
            "atlas": ATLAS_OUT,
            "report": REPORT_OUT,
        },
    }
    summary_row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_text,
        "stage070_proxy_ready_count": proxy_ready,
        "stage070_proxy_exact_count": exact_count,
        "mismatch_count": mismatch_count,
        "near_mismatch_count": near_count,
        "far_mismatch_count": far_count,
        "unresolved_mismatch_count": unresolved,
        "end_equity": official_metrics.get("end_equity"),
        "total_return_pct": official_metrics.get("total_return_pct"),
        "max_drawdown_pct": official_metrics.get("max_drawdown_pct"),
        "sharpe": official_metrics.get("sharpe"),
        "total_slippage": official_metrics.get("total_slippage"),
        "total_trade_count": official_metrics.get("total_trade_count"),
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
    }
    _write_csv(pd.DataFrame([summary_row]), SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_path(proxy, audit)
    _plot_delta(audit)
    _plot_atlas(audit)
    _write_report(decision, summary, audit)
    print(json.dumps(_json_safe(summary_row), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
