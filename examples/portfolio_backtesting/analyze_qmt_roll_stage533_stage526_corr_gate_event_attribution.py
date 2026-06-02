from __future__ import annotations

from dataclasses import dataclass
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


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
import analyze_qmt_roll_stage532_stage526_corr_gate_frontier as s532  # noqa: E402


MODEL_TAG = "stage533_stage526_corr_gate_event_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage533_stage526_corr_gate_event_attribution"
LINE_ID = "futures_trend_drawdown30_preserve_return"

CONTROL_VARIANT = s532.CONTROL_VARIANT
C1_VARIANT = s532.CORR_VARIANT
MAIN_BAD_START = pd.Timestamp("2022-03-09")
MAIN_BAD_END = pd.Timestamp("2022-12-07")

EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_events_{MODEL_TAG}.csv"
SEGMENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_segments_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_pairs_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


@dataclass(frozen=True)
class EventSegment:
    event_id: str
    status: str
    segment_start: str | None
    segment_end: str | None
    segment_days: int
    edge_net_pnl: float
    edge_slippage: float
    edge_trade_count: float
    min_cum_edge: float
    max_cum_edge: float
    max_abs_position_delta: float


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


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


def _run_control_and_c1() -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    identity_map = s519._product_identity_cluster_map(metadata)
    specs = [spec for spec in s532._variants(identity_map) if spec.variant in {CONTROL_VARIANT, C1_VARIANT}]
    position_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    for spec in specs:
        print(f"[stage533] running {spec.variant}", flush=True)
        _, positions, candidates = s532._run_variant_with_candidates(spec, metadata)
        position_frames.append(positions)
        candidate_frames.append(candidates)
    positions = pd.concat(position_frames, ignore_index=True, sort=False)
    candidates = pd.concat(candidate_frames, ignore_index=True, sort=False)
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.normalize()
    return positions, candidates


def _candidate_pairs(candidates: pd.DataFrame) -> pd.DataFrame:
    key = ["date", "product_vt_symbol", "contract_vt_symbol", "entry_context", "direction", "signal"]
    base_columns = key + [
        "candidate_status",
        "skip_reason",
        "selected_volume",
        "selected_volume_ungated",
        "same_direction_correlation_gate_weight",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_avg_corr",
        "same_direction_correlation_active_count",
        "same_direction_correlation_corr_count",
        "active_positions_before",
        "remaining_position_slots",
        "planned_entry_price",
        "stop_price",
        "margin_per_contract",
        "risk_per_contract",
        "rsi_value",
        "breakout",
        "bullish_alignment",
        "bearish_alignment",
        "ma_mid_value",
        "ma_long_value",
    ]
    frame = candidates.copy()
    missing = [column for column in base_columns if column not in frame.columns]
    if missing:
        raise RuntimeError(f"candidate columns missing: {missing}")
    control = frame[frame["variant"].eq(CONTROL_VARIANT)][base_columns].copy()
    c1 = frame[frame["variant"].eq(C1_VARIANT)][base_columns].copy()
    pairs = control.merge(c1, on=key, how="inner", suffixes=("_control", "_c1"))
    numeric_columns = [column for column in pairs.columns if column not in key and column not in {"candidate_status_control", "candidate_status_c1", "skip_reason_control", "skip_reason_c1"}]
    for column in numeric_columns:
        pairs[column] = pd.to_numeric(pairs[column], errors="coerce").fillna(0.0)
    pairs["delta_volume"] = pairs["selected_volume_c1"] - pairs["selected_volume_control"]
    pairs["delta_margin"] = pairs["delta_volume"] * pairs["margin_per_contract_c1"]
    pairs["corr_bucket"] = pd.cut(
        pairs["same_direction_correlation_max_corr_control"],
        bins=[-np.inf, 0.65, 0.75, 0.85, np.inf],
        labels=["<=0.65", "0.65-0.75", "0.75-0.85", ">0.85"],
    ).astype(str)
    pairs["event_id"] = (
        pairs["date"].dt.strftime("%Y%m%d")
        + "_"
        + pairs["contract_vt_symbol"].astype(str)
        + "_"
        + pairs["direction"].astype(str)
        + "_"
        + pairs["signal"].astype(str)
    )
    pairs["is_scaled_open_both"] = (
        pairs["candidate_status_control"].astype(str).eq("opened")
        & pairs["candidate_status_c1"].astype(str).eq("opened")
        & (
            pairs["same_direction_correlation_gate_weight_control"].lt(0.999999)
            | pairs["same_direction_correlation_gate_weight_c1"].lt(0.999999)
        )
    ).astype(int)
    pairs["period_bucket"] = np.select(
        [
            pairs["date"].between(MAIN_BAD_START, MAIN_BAD_END),
            pairs["date"].lt(MAIN_BAD_START),
            pairs["date"].gt(MAIN_BAD_END),
        ],
        ["bad_2022_main", "pre_bad_window", "post_bad_window"],
        default="other",
    )
    return pairs


def _position_diff_for_contract(positions: pd.DataFrame, vt_symbol: str) -> pd.DataFrame:
    frame = positions[positions["vt_symbol"].eq(vt_symbol)].copy()
    if frame.empty:
        return pd.DataFrame()
    value_columns = ["start_pos", "end_pos", "trade_count", "turnover", "commission", "slippage", "holding_pnl", "trading_pnl", "total_pnl", "net_pnl"]
    pivot = frame.pivot_table(index="date", columns="variant", values=value_columns, aggfunc="sum")
    rows: dict[str, pd.Series] = {}
    for column in value_columns:
        control = pivot.get((column, CONTROL_VARIANT), pd.Series(0.0, index=pivot.index)).fillna(0.0)
        c1 = pivot.get((column, C1_VARIANT), pd.Series(0.0, index=pivot.index)).fillna(0.0)
        rows[f"{column}_control"] = control
        rows[f"{column}_c1"] = c1
        rows[f"{column}_edge"] = c1 - control
    result = pd.DataFrame(rows).sort_index().reset_index()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result["position_delta"] = result["end_pos_edge"]
    return result


def _segment_for_event(event: pd.Series, positions: pd.DataFrame) -> EventSegment:
    delta_volume = int(event.get("delta_volume", 0))
    if delta_volume == 0:
        return EventSegment(str(event["event_id"]), "integer_no_delta", None, None, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    contract = str(event["contract_vt_symbol"])
    direction_sign = 1 if str(event["direction"]).lower() == "long" else -1
    expected_delta = direction_sign * delta_volume
    diff = _position_diff_for_contract(positions, contract)
    if diff.empty:
        return EventSegment(str(event["event_id"]), "missing_contract_positions", None, None, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    event_date = pd.Timestamp(event["date"]).normalize()
    after = diff[diff["date"].ge(event_date)].copy()
    active = after[after["position_delta"].mul(direction_sign).gt(0)]
    if active.empty:
        return EventSegment(str(event["event_id"]), "no_position_delta_found", None, None, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    start_date = pd.Timestamp(active["date"].iloc[0]).normalize()
    after_start = diff[diff["date"].ge(start_date)].copy()
    positive_mask = after_start["position_delta"].mul(direction_sign).gt(0)
    if not bool(positive_mask.iloc[0]):
        return EventSegment(str(event["event_id"]), "no_position_delta_found", None, None, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    end_index = len(after_start) - 1
    for idx, is_active in enumerate(positive_mask.to_list()):
        if idx == 0:
            continue
        if not is_active:
            end_index = idx
            break
    segment = after_start.iloc[: end_index + 1].copy()
    cum_edge = segment["net_pnl_edge"].cumsum()
    max_abs_delta = float(segment["position_delta"].abs().max())
    status = "matched_segment"
    if abs(max_abs_delta) < abs(expected_delta):
        status = "matched_segment_but_delta_smaller_than_expected"
    return EventSegment(
        str(event["event_id"]),
        status,
        pd.Timestamp(segment["date"].iloc[0]).date().isoformat(),
        pd.Timestamp(segment["date"].iloc[-1]).date().isoformat(),
        int(len(segment)),
        float(segment["net_pnl_edge"].sum()),
        float(segment["slippage_edge"].sum()),
        float(segment["trade_count_edge"].sum()),
        float(cum_edge.min()) if len(cum_edge) else 0.0,
        float(cum_edge.max()) if len(cum_edge) else 0.0,
        max_abs_delta,
    )


def _event_segments(events: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event in events.itertuples(index=False):
        series = pd.Series(event._asdict())
        segment = _segment_for_event(series, positions)
        rows.append(segment.__dict__)
    return pd.DataFrame(rows)


def _event_analysis(pairs: pd.DataFrame, segments: pd.DataFrame, positions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    opened_both = pairs[
        pairs["candidate_status_control"].astype(str).eq("opened")
        & pairs["candidate_status_c1"].astype(str).eq("opened")
    ].copy()
    opened_both["attribution_layer"] = np.select(
        [
            opened_both["is_scaled_open_both"].eq(1) & opened_both["delta_volume"].ne(0),
            opened_both["delta_volume"].ne(0),
            opened_both["is_scaled_open_both"].eq(1),
        ],
        ["direct_corr_scaled_delta", "downstream_equity_sizing_delta", "direct_corr_integer_no_delta"],
        default="no_delta",
    )
    events = opened_both[opened_both["attribution_layer"].ne("no_delta")].merge(segments, on="event_id", how="left")
    events["edge_class"] = np.select(
        [
            events["edge_net_pnl"].gt(0),
            events["edge_net_pnl"].lt(0),
            events["delta_volume"].eq(0),
        ],
        ["strict_gate_overprotected", "strict_gate_protected", "integer_no_delta"],
        default="neutral_or_unmatched",
    )
    events["edge_per_delta_volume"] = events["edge_net_pnl"] / events["delta_volume"].replace(0, np.nan)
    events["event_year"] = pd.to_datetime(events["date"]).dt.year

    total_edge = _total_position_edge(positions)
    matched_edge = float(events["edge_net_pnl"].sum())
    agg_rows: list[dict[str, Any]] = []
    for name, group_cols in [
        ("layer", ["attribution_layer"]),
        ("period", ["period_bucket"]),
        ("product", ["product_vt_symbol"]),
        ("year", ["event_year"]),
        ("corr_bucket", ["corr_bucket"]),
        ("edge_class", ["edge_class"]),
    ]:
        grouped = (
            events.groupby(group_cols, as_index=False)
            .agg(
                event_count=("event_id", "count"),
                delta_volume_sum=("delta_volume", "sum"),
                edge_net_pnl_sum=("edge_net_pnl", "sum"),
                edge_net_pnl_mean=("edge_net_pnl", "mean"),
                positive_edge_count=("edge_net_pnl", lambda item: int((item > 0).sum())),
                negative_edge_count=("edge_net_pnl", lambda item: int((item < 0).sum())),
                max_abs_position_delta=("max_abs_position_delta", "max"),
            )
            .sort_values("edge_net_pnl_sum", ascending=False)
        )
        grouped.insert(0, "group_type", name)
        grouped.rename(columns={group_cols[0]: "group_value"}, inplace=True)
        agg_rows.append(grouped)
    aggregate = pd.concat(agg_rows, ignore_index=True, sort=False)
    decision = _decision(events, total_edge, matched_edge)
    return events, aggregate, decision


def _total_position_edge(positions: pd.DataFrame) -> float:
    daily = positions.groupby(["date", "variant"], as_index=False)["net_pnl"].sum()
    pivot = daily.pivot(index="date", columns="variant", values="net_pnl").fillna(0.0)
    return float(pivot.get(C1_VARIANT, 0.0).sum() - pivot.get(CONTROL_VARIANT, 0.0).sum())


def _decision(events: pd.DataFrame, total_edge: float, matched_edge: float) -> dict[str, Any]:
    active_events = events[events["delta_volume"].gt(0)].copy()
    direct_events = active_events[active_events["attribution_layer"].eq("direct_corr_scaled_delta")]
    downstream_events = active_events[active_events["attribution_layer"].eq("downstream_equity_sizing_delta")]
    bad = active_events[active_events["period_bucket"].eq("bad_2022_main")]
    post = active_events[active_events["period_bucket"].eq("post_bad_window")]
    top_abs = active_events.assign(abs_edge=active_events["edge_net_pnl"].abs()).sort_values("abs_edge", ascending=False).head(5)
    positive_count = int(active_events["edge_net_pnl"].gt(0).sum())
    negative_count = int(active_events["edge_net_pnl"].lt(0).sum())
    bad_edge = float(bad["edge_net_pnl"].sum()) if not bad.empty else 0.0
    post_edge = float(post["edge_net_pnl"].sum()) if not post.empty else 0.0
    total_delta = int(active_events["delta_volume"].sum()) if not active_events.empty else 0
    explained_ratio = matched_edge / total_edge * 100.0 if abs(total_edge) > 1e-9 else 0.0
    concentration = float(top_abs["edge_net_pnl"].abs().sum() / max(active_events["edge_net_pnl"].abs().sum(), 1e-9) * 100.0) if not active_events.empty else 0.0
    direct_edge = float(direct_events["edge_net_pnl"].sum()) if not direct_events.empty else 0.0
    downstream_edge = float(downstream_events["edge_net_pnl"].sum()) if not downstream_events.empty else 0.0

    if direct_edge < 0 and downstream_edge > 0:
        label = "corr_floor50_gain_is_path_dependent_not_direct_gate_edge"
    elif post_edge > 0 and bad_edge >= 0 and negative_count <= max(1, positive_count // 2):
        label = "corr_floor50_event_attribution_supports_followup"
    elif post_edge > 0 and bad_edge < 0:
        label = "corr_floor50_mixed_event_attribution_watch_only"
    else:
        label = "corr_floor50_event_attribution_not_convincing"
    return {
        "stage": "Stage233",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "active_delta_event_count": int(len(active_events)),
        "direct_delta_event_count": int(len(direct_events)),
        "downstream_delta_event_count": int(len(downstream_events)),
        "scaled_open_event_count": int(events["attribution_layer"].isin(["direct_corr_scaled_delta", "direct_corr_integer_no_delta"]).sum()),
        "total_delta_volume": total_delta,
        "positive_event_count": positive_count,
        "negative_event_count": negative_count,
        "event_edge_net_pnl": matched_edge,
        "direct_corr_scaled_edge_net_pnl": direct_edge,
        "downstream_equity_sizing_edge_net_pnl": downstream_edge,
        "total_position_edge_net_pnl": total_edge,
        "event_edge_explained_ratio_pct": explained_ratio,
        "bad_2022_main_edge_net_pnl": bad_edge,
        "post_bad_window_edge_net_pnl": post_edge,
        "top5_abs_edge_concentration_pct": concentration,
        "largest_events": top_abs[
            [
                "event_id",
                "date",
                "product_vt_symbol",
                "direction",
                "delta_volume",
                "edge_net_pnl",
                "period_bucket",
                "same_direction_correlation_max_corr_control",
            ]
        ].to_dict(orient="records"),
    }


def _plot(events: pd.DataFrame, aggregate: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    active = events[events["delta_volume"].gt(0)].copy()
    active["date"] = pd.to_datetime(active["date"], errors="coerce")
    active.sort_values("date", inplace=True)
    active["cum_event_edge"] = active["edge_net_pnl"].cumsum()

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_scatter, ax_cum, ax_product, ax_period = axes.flatten()

    colors = np.where(
        active["attribution_layer"].eq("direct_corr_scaled_delta"),
        "#dc2626",
        "#2563eb",
    )
    ax_scatter.scatter(
        active["same_direction_correlation_max_corr_control"],
        active["edge_net_pnl"],
        s=np.maximum(30, active["delta_volume"].abs() * 4),
        c=colors,
        alpha=0.75,
        edgecolors="#111827",
        linewidths=0.4,
    )
    ax_scatter.axhline(0, color="#111827", linewidth=1)
    ax_scatter.set_title("Event edge vs same-direction max corr")
    ax_scatter.set_xlabel("max corr")
    ax_scatter.set_ylabel("C1-control net PnL")
    ax_scatter.grid(alpha=0.25)

    ax_cum.plot(active["date"], active["cum_event_edge"], color="#7c3aed", linewidth=1.2)
    ax_cum.axhline(0, color="#111827", linewidth=1)
    ax_cum.axvspan(MAIN_BAD_START, MAIN_BAD_END, color="#fecaca", alpha=0.35)
    ax_cum.set_title("Cumulative matched event edge")
    ax_cum.grid(alpha=0.25)

    product = aggregate[aggregate["group_type"].eq("product")].copy().sort_values("edge_net_pnl_sum")
    ax_product.barh(product["group_value"].astype(str), product["edge_net_pnl_sum"], color=np.where(product["edge_net_pnl_sum"].ge(0), "#16a34a", "#dc2626"))
    ax_product.axvline(0, color="#111827", linewidth=1)
    ax_product.set_title("Edge by product")
    ax_product.grid(axis="x", alpha=0.25)

    period = aggregate[aggregate["group_type"].eq("period")].copy().sort_values("group_value")
    ax_period.bar(period["group_value"].astype(str), period["edge_net_pnl_sum"], color=np.where(period["edge_net_pnl_sum"].ge(0), "#16a34a", "#dc2626"))
    ax_period.axhline(0, color="#111827", linewidth=1)
    ax_period.set_title("Edge by period bucket")
    ax_period.tick_params(axis="x", rotation=20)
    ax_period.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(events: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    active = events[events["delta_volume"].gt(0)].copy()
    lines = [
        "# Stage233 Stage526同向相关性门控逐笔归因",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：固定 Stage232 control/C1，不扫参数，只解释 floor0.50 相对 floor0.35 的实际开仓差异。",
        "- 运行前过拟合判断：否。只做事件归因，不按结果调规则。",
        "- 运行前继续价值判断：是。Stage232 显示门控必须保留，但强度可能过严，需要逐笔确认误伤/保护来源。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随组合常见做法是跨市场分散、波动/风险预算和相关性治理，但同向高相关有时代表趋势扩散，不应机械压制。",
        "- 本阶段因此采用事件级 attribution：若放宽 floor 后新增手数后续产生正 edge，说明原 floor0.35 过度保护；若为负 edge，则说明原门控保护有效。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 事件汇总",
        "",
        _md_table(
            pd.DataFrame(
                [
                    {
                        "active_delta_event_count": decision.get("active_delta_event_count"),
                        "direct_delta_event_count": decision.get("direct_delta_event_count"),
                        "downstream_delta_event_count": decision.get("downstream_delta_event_count"),
                        "scaled_open_event_count": decision.get("scaled_open_event_count"),
                        "total_delta_volume": decision.get("total_delta_volume"),
                        "positive_event_count": decision.get("positive_event_count"),
                        "negative_event_count": decision.get("negative_event_count"),
                        "event_edge_net_pnl": decision.get("event_edge_net_pnl"),
                        "direct_edge_net_pnl": decision.get("direct_corr_scaled_edge_net_pnl"),
                        "downstream_edge_net_pnl": decision.get("downstream_equity_sizing_edge_net_pnl"),
                        "total_position_edge_net_pnl": decision.get("total_position_edge_net_pnl"),
                        "explained_ratio_pct": decision.get("event_edge_explained_ratio_pct"),
                    }
                ]
            )
        ),
        "",
        "## 分组归因",
        "",
        _md_table(aggregate.sort_values(["group_type", "edge_net_pnl_sum"], ascending=[True, False]), max_rows=80),
        "",
        "## 最大绝对贡献事件",
        "",
        _md_table(
            active.assign(abs_edge=active["edge_net_pnl"].abs())
            .sort_values("abs_edge", ascending=False)[
                [
                    "date",
                    "product_vt_symbol",
                    "contract_vt_symbol",
                    "direction",
                    "signal",
                    "attribution_layer",
                    "delta_volume",
                    "segment_start",
                    "segment_end",
                    "edge_net_pnl",
                    "edge_slippage",
                    "same_direction_correlation_max_corr_control",
                    "period_bucket",
                    "edge_class",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 图表视觉复盘",
        "",
        f"- 图表：`{CHART_PATH}`",
        "- 视觉复盘需要结合散点、累计edge、产品贡献和时期贡献，不只看最终净值差。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    positions, candidates = _run_control_and_c1()
    pairs = _candidate_pairs(candidates)
    events = pairs[
        pairs["candidate_status_control"].astype(str).eq("opened")
        & pairs["candidate_status_c1"].astype(str).eq("opened")
        & (pairs["delta_volume"].ne(0) | pairs["is_scaled_open_both"].eq(1))
    ].copy()
    segments = _event_segments(events, positions)
    event_analysis, aggregate, decision = _event_analysis(pairs, segments, positions)
    _plot(event_analysis, aggregate)
    _write_report(event_analysis, aggregate, decision)

    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    pairs.to_csv(CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    event_analysis.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    segments.to_csv(SEGMENT_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
