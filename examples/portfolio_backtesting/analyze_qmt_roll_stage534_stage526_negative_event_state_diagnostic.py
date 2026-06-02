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


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage534_stage526_negative_event_state_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage534_stage526_negative_event_state_diagnostic"

STAGE533_EVENT_PATH = OUTPUT_DIR / (
    "qmt_roll_stage533_stage526_corr_gate_event_attribution_events_"
    "stage533_stage526_corr_gate_event_attribution_v1.csv"
)
EVENT_FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_features_{MODEL_TAG}.csv"
FEATURE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_summary_{MODEL_TAG}.csv"
GROUP_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_group_summary_{MODEL_TAG}.csv"
RULE_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rule_probe_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

FOCUS_PRODUCTS = {"MA.CZCE", "AP.CZCE", "SA.CZCE"}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _load_events() -> pd.DataFrame:
    if not STAGE533_EVENT_PATH.exists():
        raise FileNotFoundError(STAGE533_EVENT_PATH)
    events = pd.read_csv(STAGE533_EVENT_PATH)
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    for column in [
        "delta_volume",
        "edge_net_pnl",
        "edge_per_delta_volume",
        "segment_days",
        "same_direction_correlation_max_corr_control",
        "same_direction_correlation_gate_weight_control",
        "active_positions_before_control",
        "remaining_position_slots_control",
        "planned_entry_price_control",
        "stop_price_control",
        "margin_per_contract_control",
        "risk_per_contract_control",
        "rsi_value_control",
        "breakout_control",
        "bullish_alignment_control",
        "bearish_alignment_control",
        "ma_mid_value_control",
        "ma_long_value_control",
    ]:
        events[column] = pd.to_numeric(events.get(column, 0.0), errors="coerce").fillna(0.0)
    return events


def _derive_features(events: pd.DataFrame) -> pd.DataFrame:
    frame = events.copy()
    direction_sign = np.where(frame["direction"].astype(str).str.lower().eq("long"), 1.0, -1.0)
    entry = frame["planned_entry_price_control"].replace(0, np.nan)
    ma_mid = frame["ma_mid_value_control"].replace(0, np.nan)
    ma_long = frame["ma_long_value_control"].replace(0, np.nan)
    frame["edge_sign"] = np.select(
        [frame["edge_net_pnl"].gt(0), frame["edge_net_pnl"].lt(0)],
        ["positive", "negative"],
        default="flat",
    )
    frame["focus_product"] = frame["product_vt_symbol"].isin(FOCUS_PRODUCTS).astype(int)
    frame["focus_negative"] = (frame["focus_product"].eq(1) & frame["edge_net_pnl"].lt(0)).astype(int)
    frame["focus_positive"] = (frame["focus_product"].eq(1) & frame["edge_net_pnl"].gt(0)).astype(int)
    frame["nonfocus_negative"] = (frame["focus_product"].eq(0) & frame["edge_net_pnl"].lt(0)).astype(int)
    frame["rsi_direction_strength"] = np.where(direction_sign > 0, frame["rsi_value_control"] - 50.0, 50.0 - frame["rsi_value_control"])
    frame["trend_spread_pct"] = direction_sign * (ma_mid - ma_long) / entry * 100.0
    frame["price_extension_mid_pct"] = direction_sign * (frame["planned_entry_price_control"] - ma_mid) / entry * 100.0
    frame["price_extension_long_pct"] = direction_sign * (frame["planned_entry_price_control"] - ma_long) / entry * 100.0
    frame["stop_distance_pct"] = (frame["planned_entry_price_control"] - frame["stop_price_control"]).abs() / entry * 100.0
    frame["margin_per_delta_volume"] = frame["delta_volume"].abs() * frame["margin_per_contract_control"]
    frame["fast_fail"] = (frame["edge_net_pnl"].lt(0) & frame["segment_days"].le(6)).astype(int)
    frame["large_delta"] = frame["delta_volume"].abs().ge(frame["delta_volume"].abs().quantile(0.75)).astype(int)
    frame["low_corr_or_no_active"] = (
        frame["same_direction_correlation_max_corr_control"].le(0.10)
        | frame["same_direction_correlation_active_count_control"].le(0)
    ).astype(int)
    frame["low_trend_spread"] = frame["trend_spread_pct"].le(1.0).astype(int)
    frame["weak_direction_rsi"] = frame["rsi_direction_strength"].le(10.0).astype(int)
    frame["near_mid_price"] = frame["price_extension_mid_pct"].le(2.0).astype(int)
    frame["state_key"] = (
        "fast_fail="
        + frame["fast_fail"].astype(str)
        + "|low_corr="
        + frame["low_corr_or_no_active"].astype(str)
        + "|weak_rsi="
        + frame["weak_direction_rsi"].astype(str)
        + "|low_spread="
        + frame["low_trend_spread"].astype(str)
    )
    return frame


def _feature_summary(frame: pd.DataFrame) -> pd.DataFrame:
    numeric_features = [
        "edge_net_pnl",
        "edge_per_delta_volume",
        "delta_volume",
        "segment_days",
        "same_direction_correlation_max_corr_control",
        "same_direction_correlation_gate_weight_control",
        "active_positions_before_control",
        "rsi_direction_strength",
        "trend_spread_pct",
        "price_extension_mid_pct",
        "price_extension_long_pct",
        "stop_distance_pct",
        "margin_per_delta_volume",
    ]
    focus_neg = frame[frame["focus_negative"].eq(1)]
    other = frame[frame["focus_negative"].eq(0)]
    all_neg = frame[frame["edge_net_pnl"].lt(0)]
    all_pos = frame[frame["edge_net_pnl"].gt(0)]
    rows: list[dict[str, Any]] = []
    for feature in numeric_features:
        rows.append(
            {
                "feature": feature,
                "focus_neg_median": float(focus_neg[feature].median()) if len(focus_neg) else 0.0,
                "other_median": float(other[feature].median()) if len(other) else 0.0,
                "all_neg_median": float(all_neg[feature].median()) if len(all_neg) else 0.0,
                "all_pos_median": float(all_pos[feature].median()) if len(all_pos) else 0.0,
                "focus_neg_mean": float(focus_neg[feature].mean()) if len(focus_neg) else 0.0,
                "all_pos_mean": float(all_pos[feature].mean()) if len(all_pos) else 0.0,
                "focus_neg_minus_all_pos_median": (
                    float(focus_neg[feature].median()) - float(all_pos[feature].median())
                    if len(focus_neg) and len(all_pos)
                    else 0.0
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("feature")


def _group_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for group_type, columns in [
        ("product", ["product_vt_symbol"]),
        ("signal", ["signal"]),
        ("direction", ["direction"]),
        ("layer", ["attribution_layer"]),
        ("period", ["period_bucket"]),
        ("state_key", ["state_key"]),
    ]:
        grouped = (
            frame.groupby(columns, as_index=False)
            .agg(
                event_count=("event_id", "count"),
                edge_sum=("edge_net_pnl", "sum"),
                edge_mean=("edge_net_pnl", "mean"),
                negative_count=("edge_net_pnl", lambda item: int((item < 0).sum())),
                positive_count=("edge_net_pnl", lambda item: int((item > 0).sum())),
                focus_negative_count=("focus_negative", "sum"),
                delta_volume_sum=("delta_volume", "sum"),
                median_segment_days=("segment_days", "median"),
                median_rsi_strength=("rsi_direction_strength", "median"),
                median_trend_spread=("trend_spread_pct", "median"),
            )
            .sort_values("edge_sum", ascending=True)
        )
        grouped.insert(0, "group_type", group_type)
        grouped.rename(columns={columns[0]: "group_value"}, inplace=True)
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True, sort=False)


def _rule_probes(frame: pd.DataFrame) -> pd.DataFrame:
    probes: list[tuple[str, pd.Series]] = [
        ("focus_products_only", frame["focus_product"].eq(1)),
        ("focus_fast_fail", frame["focus_product"].eq(1) & frame["fast_fail"].eq(1)),
        ("focus_fast_fail_low_corr", frame["focus_product"].eq(1) & frame["fast_fail"].eq(1) & frame["low_corr_or_no_active"].eq(1)),
        ("focus_fast_fail_weak_rsi", frame["focus_product"].eq(1) & frame["fast_fail"].eq(1) & frame["weak_direction_rsi"].eq(1)),
        ("all_fast_fail_low_corr", frame["fast_fail"].eq(1) & frame["low_corr_or_no_active"].eq(1)),
        ("all_fast_fail_weak_rsi_low_spread", frame["fast_fail"].eq(1) & frame["weak_direction_rsi"].eq(1) & frame["low_trend_spread"].eq(1)),
        ("long_case2_fast_fail_low_corr", frame["signal"].astype(str).eq("long_case2") & frame["fast_fail"].eq(1) & frame["low_corr_or_no_active"].eq(1)),
        ("large_delta_fast_fail", frame["large_delta"].eq(1) & frame["fast_fail"].eq(1)),
    ]
    rows: list[dict[str, Any]] = []
    total_neg_edge = float(frame.loc[frame["edge_net_pnl"].lt(0), "edge_net_pnl"].sum())
    total_pos_edge = float(frame.loc[frame["edge_net_pnl"].gt(0), "edge_net_pnl"].sum())
    for name, mask in probes:
        subset = frame[mask].copy()
        rows.append(
            {
                "probe": name,
                "event_count": int(len(subset)),
                "edge_sum": float(subset["edge_net_pnl"].sum()) if len(subset) else 0.0,
                "negative_edge_sum": float(subset.loc[subset["edge_net_pnl"].lt(0), "edge_net_pnl"].sum()) if len(subset) else 0.0,
                "positive_edge_sum": float(subset.loc[subset["edge_net_pnl"].gt(0), "edge_net_pnl"].sum()) if len(subset) else 0.0,
                "negative_count": int(subset["edge_net_pnl"].lt(0).sum()) if len(subset) else 0,
                "positive_count": int(subset["edge_net_pnl"].gt(0).sum()) if len(subset) else 0,
                "focus_negative_count": int(subset["focus_negative"].sum()) if len(subset) else 0,
                "coverage_of_total_negative_edge_pct": (
                    abs(float(subset.loc[subset["edge_net_pnl"].lt(0), "edge_net_pnl"].sum())) / max(abs(total_neg_edge), 1e-9) * 100.0
                    if len(subset)
                    else 0.0
                ),
                "positive_edge_at_risk_pct": (
                    float(subset.loc[subset["edge_net_pnl"].gt(0), "edge_net_pnl"].sum()) / max(total_pos_edge, 1e-9) * 100.0
                    if len(subset)
                    else 0.0
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["edge_sum", "coverage_of_total_negative_edge_pct"], ascending=[True, False])


def _decision(frame: pd.DataFrame, feature_summary: pd.DataFrame, group_summary: pd.DataFrame, rule_probe: pd.DataFrame) -> dict[str, Any]:
    focus = frame[frame["focus_product"].eq(1)]
    focus_neg = frame[frame["focus_negative"].eq(1)]
    all_neg = frame[frame["edge_net_pnl"].lt(0)]
    focus_neg_edge = float(focus_neg["edge_net_pnl"].sum()) if len(focus_neg) else 0.0
    focus_edge = float(focus["edge_net_pnl"].sum()) if len(focus) else 0.0
    all_neg_edge = float(all_neg["edge_net_pnl"].sum()) if len(all_neg) else 0.0
    best_probe = rule_probe.iloc[0].to_dict() if not rule_probe.empty else {}
    focus_fast = rule_probe[rule_probe["probe"].eq("focus_fast_fail")]
    low_corr_probe = rule_probe[rule_probe["probe"].eq("all_fast_fail_low_corr")]
    decision_label = "negative_state_diagnostic_no_rule_ready"
    if not focus_fast.empty:
        row = focus_fast.iloc[0]
        if float(row["negative_edge_sum"]) < 0 and float(row["positive_edge_sum"]) > abs(float(row["negative_edge_sum"])) * 0.5:
            decision_label = "focus_fast_fail_catches_loss_but_positive_edge_too_high"
    if not low_corr_probe.empty:
        row = low_corr_probe.iloc[0]
        if float(row["negative_edge_sum"]) < 0 and float(row["positive_edge_sum"]) < abs(float(row["negative_edge_sum"])) * 0.25:
            decision_label = "low_corr_fast_fail_possible_followup_probe"
    return {
        "stage": "Stage234",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "event_count": int(len(frame)),
        "focus_product_event_count": int(len(focus)),
        "focus_negative_event_count": int(len(focus_neg)),
        "focus_product_edge_sum": focus_edge,
        "focus_negative_edge_sum": focus_neg_edge,
        "all_negative_edge_sum": all_neg_edge,
        "focus_negative_share_of_negative_edge_pct": abs(focus_neg_edge) / max(abs(all_neg_edge), 1e-9) * 100.0,
        "best_probe": _json_safe(best_probe),
        "feature_summary_top": feature_summary.head(8).to_dict(orient="records"),
        "worst_groups": group_summary.sort_values("edge_sum").head(10).to_dict(orient="records"),
    }


def _plot(frame: pd.DataFrame, rule_probe: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_scatter, ax_box, ax_rule, ax_product = axes.flatten()

    color = np.where(frame["focus_negative"].eq(1), "#dc2626", np.where(frame["edge_net_pnl"].lt(0), "#f97316", "#2563eb"))
    size = np.clip(frame["delta_volume"].abs() * 3, 20, 240)
    ax_scatter.scatter(frame["rsi_direction_strength"], frame["edge_net_pnl"], c=color, s=size, alpha=0.75, edgecolors="#111827", linewidths=0.35)
    ax_scatter.axhline(0, color="#111827", linewidth=1)
    ax_scatter.axvline(10, color="#6b7280", linestyle="--", linewidth=1)
    ax_scatter.set_title("Edge vs direction-adjusted RSI strength")
    ax_scatter.set_xlabel("direction RSI strength")
    ax_scatter.set_ylabel("edge net pnl")
    ax_scatter.grid(alpha=0.25)

    box_data = [
        frame.loc[frame["focus_negative"].eq(1), "segment_days"],
        frame.loc[(frame["edge_net_pnl"].lt(0)) & frame["focus_negative"].eq(0), "segment_days"],
        frame.loc[frame["edge_net_pnl"].gt(0), "segment_days"],
    ]
    ax_box.boxplot(box_data, tick_labels=["focus neg", "other neg", "positive"], showfliers=False)
    ax_box.set_title("Segment days distribution")
    ax_box.grid(axis="y", alpha=0.25)

    show = rule_probe.sort_values("edge_sum").head(8).copy()
    ax_rule.barh(show["probe"], show["edge_sum"], color=np.where(show["edge_sum"].ge(0), "#16a34a", "#dc2626"))
    ax_rule.axvline(0, color="#111827", linewidth=1)
    ax_rule.set_title("Probe edge sum")
    ax_rule.grid(axis="x", alpha=0.25)

    product = (
        frame.groupby("product_vt_symbol", as_index=False)
        .agg(edge_sum=("edge_net_pnl", "sum"), event_count=("event_id", "count"))
        .sort_values("edge_sum")
    )
    ax_product.barh(product["product_vt_symbol"], product["edge_sum"], color=np.where(product["edge_sum"].ge(0), "#16a34a", "#dc2626"))
    ax_product.axvline(0, color="#111827", linewidth=1)
    ax_product.set_title("Edge by product")
    ax_product.grid(axis="x", alpha=0.25)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    frame: pd.DataFrame,
    feature_summary: pd.DataFrame,
    group_summary: pd.DataFrame,
    rule_probe: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    focus_worst = frame[frame["focus_product"].eq(1)].sort_values("edge_net_pnl").head(20)
    lines = [
        "# Stage234 Stage526负贡献事件状态诊断",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：Stage233 后续只读诊断；聚焦 `MA/AP/SA` 负贡献事件的共同状态。",
        "- 运行前过拟合判断：否。只比较已有事件字段，不新增规则，不做产品黑名单。",
        "- 运行前继续价值判断：是。若能找到跨品种低自由度状态，后续才值得进入真实引擎 A/C。",
        "",
        "## 外部调研判断",
        "",
        "- 假突破/whipsaw 常见过滤方向包括 ADX/趋势强度、ATR 或 Keltner 突破质量、RSI/动量确认和多周期一致性。",
        "- 这些方向容易拟合历史，因此本阶段只用当前候选快照已有字段做状态诊断，不新增外部指标。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 规则探针",
        "",
        _md_table(rule_probe),
        "",
        "## 特征中位数对比",
        "",
        _md_table(feature_summary),
        "",
        "## 分组汇总",
        "",
        _md_table(group_summary.sort_values("edge_sum").head(60)),
        "",
        "## Focus产品最差事件",
        "",
        _md_table(
            focus_worst[
                [
                    "date",
                    "product_vt_symbol",
                    "contract_vt_symbol",
                    "direction",
                    "signal",
                    "attribution_layer",
                    "delta_volume",
                    "segment_days",
                    "edge_net_pnl",
                    "rsi_direction_strength",
                    "trend_spread_pct",
                    "price_extension_mid_pct",
                    "same_direction_correlation_max_corr_control",
                    "state_key",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 图表视觉复盘",
        "",
        f"- 图表：`{CHART_PATH}`",
        "- 视觉复盘需要同时看 RSI强度散点、持有天数箱线、规则探针和产品贡献。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    events = _load_events()
    frame = _derive_features(events)
    feature_summary = _feature_summary(frame)
    group_summary = _group_summary(frame)
    rule_probe = _rule_probes(frame)
    decision = _decision(frame, feature_summary, group_summary, rule_probe)
    _plot(frame, rule_probe)
    _write_report(frame, feature_summary, group_summary, rule_probe, decision)

    frame.to_csv(EVENT_FEATURE_PATH, index=False, encoding="utf-8-sig")
    feature_summary.to_csv(FEATURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    group_summary.to_csv(GROUP_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    rule_probe.to_csv(RULE_PROBE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
