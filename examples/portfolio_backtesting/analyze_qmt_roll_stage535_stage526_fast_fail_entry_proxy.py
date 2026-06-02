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
MODEL_TAG = "stage535_stage526_fast_fail_entry_proxy_v1"
OUTPUT_PREFIX = "qmt_roll_stage535_stage526_fast_fail_entry_proxy"

STAGE534_EVENT_FEATURE_PATH = OUTPUT_DIR / (
    "qmt_roll_stage534_stage526_negative_event_state_diagnostic_event_features_"
    "stage534_stage526_negative_event_state_diagnostic_v1.csv"
)
STAGE533_POSITIONS_PATH = OUTPUT_DIR / (
    "qmt_roll_stage533_stage526_corr_gate_event_attribution_positions_"
    "stage533_stage526_corr_gate_event_attribution_v1.csv"
)

EVENT_FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_features_{MODEL_TAG}.csv"
FEATURE_DIAGNOSTIC_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_diagnostic_{MODEL_TAG}.csv"
BIN_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bin_summary_{MODEL_TAG}.csv"
RULE_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rule_probe_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

CONTROL_VARIANT = "r080_pc25_maxpos4_control"


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


def _safe_corr(left: pd.Series, right: pd.Series, method: str = "spearman") -> float:
    frame = pd.concat([left, right], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 5 or frame.iloc[:, 0].nunique() < 2 or frame.iloc[:, 1].nunique() < 2:
        return 0.0
    result = frame.iloc[:, 0].corr(frame.iloc[:, 1], method=method)
    return float(result) if pd.notna(result) else 0.0


def _load_stage534_events() -> pd.DataFrame:
    if not STAGE534_EVENT_FEATURE_PATH.exists():
        raise FileNotFoundError(STAGE534_EVENT_FEATURE_PATH)
    events = pd.read_csv(STAGE534_EVENT_FEATURE_PATH)
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    numeric_columns = [
        "edge_net_pnl",
        "edge_slippage",
        "edge_trade_count",
        "delta_volume",
        "segment_days",
        "planned_entry_price_control",
        "stop_price_control",
        "ma_mid_value_control",
        "ma_long_value_control",
        "rsi_direction_strength",
        "trend_spread_pct",
        "price_extension_mid_pct",
        "price_extension_long_pct",
        "stop_distance_pct",
        "same_direction_correlation_max_corr_control",
        "same_direction_correlation_active_count_control",
        "fast_fail",
        "large_delta",
        "low_corr_or_no_active",
        "low_trend_spread",
        "weak_direction_rsi",
        "near_mid_price",
    ]
    for column in numeric_columns:
        events[column] = pd.to_numeric(events.get(column, 0.0), errors="coerce").fillna(0.0)
    events["direction_sign"] = np.where(events["direction"].astype(str).str.lower().eq("long"), 1.0, -1.0)
    return events


def _load_position_closes(contracts: set[str]) -> pd.DataFrame:
    if not STAGE533_POSITIONS_PATH.exists():
        raise FileNotFoundError(STAGE533_POSITIONS_PATH)
    usecols = ["date", "vt_symbol", "close_price", "pre_close", "variant"]
    frames: list[pd.DataFrame] = []
    for chunk in pd.read_csv(STAGE533_POSITIONS_PATH, usecols=usecols, chunksize=500_000):
        mask = chunk["variant"].eq(CONTROL_VARIANT) & chunk["vt_symbol"].isin(contracts)
        if not mask.any():
            continue
        view = chunk.loc[mask, ["date", "vt_symbol", "close_price", "pre_close"]].copy()
        view["date"] = pd.to_datetime(view["date"], errors="coerce").dt.normalize()
        for column in ["close_price", "pre_close"]:
            view[column] = pd.to_numeric(view[column], errors="coerce")
        view = view.dropna(subset=["date", "close_price"])
        view = view[view["close_price"].gt(0)]
        frames.append(view)
    if not frames:
        return pd.DataFrame(columns=["date", "vt_symbol", "close_price", "pre_close"])
    closes = pd.concat(frames, ignore_index=True, sort=False)
    closes = closes.drop_duplicates(["date", "vt_symbol"]).sort_values(["vt_symbol", "date"])
    return closes.reset_index(drop=True)


def _series_feature_for_event(event: pd.Series, history: pd.DataFrame) -> dict[str, Any]:
    event_date = pd.Timestamp(event["date"]).normalize()
    contract = str(event["contract_vt_symbol"])
    direction_sign = float(event["direction_sign"])
    series = history[history["vt_symbol"].eq(contract)].sort_values("date")
    series = series[series["date"].le(event_date)].copy()
    if series.empty:
        return {
            "close_feature_status": "missing_close_history",
            "close_used_date": None,
            "close_used_price": 0.0,
        }

    close = series["close_price"].astype(float).to_numpy()
    dates = series["date"].to_numpy()
    close_t = float(close[-1])
    rows: dict[str, Any] = {
        "close_feature_status": "ok",
        "close_used_date": pd.Timestamp(dates[-1]).date().isoformat(),
        "close_used_price": close_t,
    }

    def dir_ret(window: int) -> float:
        if len(close) <= window or close[-window - 1] <= 0:
            return np.nan
        return direction_sign * (close_t / float(close[-window - 1]) - 1.0) * 100.0

    for window in [1, 3, 5, 10, 20]:
        rows[f"dir_ret_{window}d_pct"] = dir_ret(window)

    if len(close) > 10:
        price_diff = np.diff(close[-11:])
        directional_move = direction_sign * (close_t - float(close[-11]))
        rows["directional_efficiency_10d"] = directional_move / max(float(np.abs(price_diff).sum()), 1e-9)
        pct_returns = pd.Series(close[-11:]).pct_change().dropna().abs()
        rows["avg_abs_ret_10d_pct"] = float(pct_returns.mean() * 100.0)
        rows["vol_expansion_1_over_10"] = abs(rows["dir_ret_1d_pct"]) / max(rows["avg_abs_ret_10d_pct"], 1e-9)
    else:
        rows["directional_efficiency_10d"] = np.nan
        rows["avg_abs_ret_10d_pct"] = np.nan
        rows["vol_expansion_1_over_10"] = np.nan

    if len(close) > 20:
        prior20 = close[-21:-1]
        prior_max = float(np.max(prior20))
        prior_min = float(np.min(prior20))
        if direction_sign > 0:
            rows["close_breakout_margin_20d_pct"] = (close_t / max(prior_max, 1e-9) - 1.0) * 100.0
            rows["directional_range_position_20d"] = (close_t - prior_min) / max(prior_max - prior_min, 1e-9)
        else:
            rows["close_breakout_margin_20d_pct"] = (prior_min / max(close_t, 1e-9) - 1.0) * 100.0
            rows["directional_range_position_20d"] = (prior_max - close_t) / max(prior_max - prior_min, 1e-9)
    else:
        rows["close_breakout_margin_20d_pct"] = np.nan
        rows["directional_range_position_20d"] = np.nan

    return rows


def _attach_entry_visible_features(events: pd.DataFrame, closes: pd.DataFrame) -> pd.DataFrame:
    features = [_series_feature_for_event(event, closes) for _, event in events.iterrows()]
    frame = pd.concat([events.reset_index(drop=True), pd.DataFrame(features)], axis=1)
    numeric_columns = [
        "close_used_price",
        "dir_ret_1d_pct",
        "dir_ret_3d_pct",
        "dir_ret_5d_pct",
        "dir_ret_10d_pct",
        "dir_ret_20d_pct",
        "directional_efficiency_10d",
        "avg_abs_ret_10d_pct",
        "vol_expansion_1_over_10",
        "close_breakout_margin_20d_pct",
        "directional_range_position_20d",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")

    frame["weak_5d_continuation"] = frame["dir_ret_5d_pct"].le(0.0).fillna(False).astype(int)
    frame["weak_10d_continuation"] = frame["dir_ret_10d_pct"].le(0.0).fillna(False).astype(int)
    frame["low_efficiency_10d"] = frame["directional_efficiency_10d"].le(0.25).fillna(False).astype(int)
    frame["weak_close_breakout20"] = frame["close_breakout_margin_20d_pct"].le(0.20).fillna(False).astype(int)
    frame["low_vol_expansion"] = frame["vol_expansion_1_over_10"].le(1.0).fillna(False).astype(int)
    frame["entry_weak_stack_count"] = (
        frame[
            [
                "weak_5d_continuation",
                "weak_10d_continuation",
                "low_efficiency_10d",
                "weak_close_breakout20",
                "low_vol_expansion",
                "weak_direction_rsi",
                "low_trend_spread",
                "near_mid_price",
            ]
        ]
        .fillna(0)
        .astype(int)
        .sum(axis=1)
    )
    frame["entry_quality_key"] = (
        "stack="
        + frame["entry_weak_stack_count"].astype(str)
        + "|large="
        + frame["large_delta"].astype(int).astype(str)
        + "|lowcorr="
        + frame["low_corr_or_no_active"].astype(int).astype(str)
    )
    return frame


def _feature_diagnostic(frame: pd.DataFrame) -> pd.DataFrame:
    features = [
        "dir_ret_1d_pct",
        "dir_ret_3d_pct",
        "dir_ret_5d_pct",
        "dir_ret_10d_pct",
        "dir_ret_20d_pct",
        "directional_efficiency_10d",
        "avg_abs_ret_10d_pct",
        "vol_expansion_1_over_10",
        "close_breakout_margin_20d_pct",
        "directional_range_position_20d",
        "rsi_direction_strength",
        "trend_spread_pct",
        "price_extension_mid_pct",
        "price_extension_long_pct",
        "stop_distance_pct",
        "entry_weak_stack_count",
    ]
    fast_fail = frame[frame["fast_fail"].eq(1)]
    negative = frame[frame["edge_net_pnl"].lt(0)]
    positive = frame[frame["edge_net_pnl"].gt(0)]
    rows: list[dict[str, Any]] = []
    for feature in features:
        rows.append(
            {
                "feature": feature,
                "non_null": int(frame[feature].notna().sum()) if feature in frame else 0,
                "fast_fail_median": float(fast_fail[feature].median()) if feature in frame and len(fast_fail) else 0.0,
                "negative_median": float(negative[feature].median()) if feature in frame and len(negative) else 0.0,
                "positive_median": float(positive[feature].median()) if feature in frame and len(positive) else 0.0,
                "all_median": float(frame[feature].median()) if feature in frame and len(frame) else 0.0,
                "fast_fail_minus_positive_median": (
                    float(fast_fail[feature].median()) - float(positive[feature].median())
                    if feature in frame and len(fast_fail) and len(positive)
                    else 0.0
                ),
                "spearman_to_edge": _safe_corr(frame[feature], frame["edge_net_pnl"]) if feature in frame else 0.0,
                "spearman_to_fast_fail": _safe_corr(frame[feature], frame["fast_fail"]) if feature in frame else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("spearman_to_fast_fail")


def _bin_summary(frame: pd.DataFrame) -> pd.DataFrame:
    features = [
        "directional_efficiency_10d",
        "dir_ret_5d_pct",
        "dir_ret_10d_pct",
        "close_breakout_margin_20d_pct",
        "vol_expansion_1_over_10",
        "entry_weak_stack_count",
    ]
    rows: list[pd.DataFrame] = []
    for feature in features:
        valid = frame.dropna(subset=[feature]).copy()
        if valid.empty:
            continue
        if valid[feature].nunique() >= 4:
            valid["bin"] = pd.qcut(valid[feature], q=4, duplicates="drop").astype(str)
        else:
            valid["bin"] = valid[feature].astype(str)
        grouped = (
            valid.groupby("bin", as_index=False)
            .agg(
                event_count=("event_id", "count"),
                edge_sum=("edge_net_pnl", "sum"),
                negative_edge_sum=("edge_net_pnl", lambda item: float(item[item < 0].sum())),
                positive_edge_sum=("edge_net_pnl", lambda item: float(item[item > 0].sum())),
                fast_fail_count=("fast_fail", "sum"),
                positive_count=("edge_net_pnl", lambda item: int((item > 0).sum())),
                median_value=(feature, "median"),
            )
            .sort_values("median_value")
        )
        grouped.insert(0, "feature", feature)
        rows.append(grouped)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True, sort=False)


def _rule_probes(frame: pd.DataFrame) -> pd.DataFrame:
    probes: list[tuple[str, pd.Series]] = [
        (
            "entry_large_delta_low_eff10",
            frame["large_delta"].eq(1) & frame["low_efficiency_10d"].eq(1),
        ),
        (
            "entry_large_delta_weak5_breakout",
            frame["large_delta"].eq(1) & frame["weak_5d_continuation"].eq(1) & frame["weak_close_breakout20"].eq(1),
        ),
        (
            "entry_low_corr_low_eff10",
            frame["low_corr_or_no_active"].eq(1) & frame["low_efficiency_10d"].eq(1),
        ),
        (
            "entry_low_corr_weak_breakout",
            frame["low_corr_or_no_active"].eq(1) & frame["weak_close_breakout20"].eq(1),
        ),
        (
            "entry_weak_stack_ge5",
            frame["entry_weak_stack_count"].ge(5),
        ),
        (
            "entry_large_lowcorr_stack_ge4",
            frame["large_delta"].eq(1) & frame["low_corr_or_no_active"].eq(1) & frame["entry_weak_stack_count"].ge(4),
        ),
        (
            "entry_large_stack_ge4",
            frame["large_delta"].eq(1) & frame["entry_weak_stack_count"].ge(4),
        ),
        (
            "entry_low_eff_weak5_weak10",
            frame["low_efficiency_10d"].eq(1) & frame["weak_5d_continuation"].eq(1) & frame["weak_10d_continuation"].eq(1),
        ),
        (
            "entry_focus_low_eff_weak5",
            frame["focus_product"].eq(1) & frame["low_efficiency_10d"].eq(1) & frame["weak_5d_continuation"].eq(1),
        ),
    ]

    total_negative_edge = float(frame.loc[frame["edge_net_pnl"].lt(0), "edge_net_pnl"].sum())
    total_positive_edge = float(frame.loc[frame["edge_net_pnl"].gt(0), "edge_net_pnl"].sum())
    total_fast_fail_count = int(frame["fast_fail"].sum())
    rows: list[dict[str, Any]] = []
    for name, mask in probes:
        subset = frame[mask.fillna(False)].copy()
        negative_edge = float(subset.loc[subset["edge_net_pnl"].lt(0), "edge_net_pnl"].sum()) if len(subset) else 0.0
        positive_edge = float(subset.loc[subset["edge_net_pnl"].gt(0), "edge_net_pnl"].sum()) if len(subset) else 0.0
        fast_fail_count = int(subset["fast_fail"].sum()) if len(subset) else 0
        rows.append(
            {
                "probe": name,
                "event_count": int(len(subset)),
                "edge_sum": float(subset["edge_net_pnl"].sum()) if len(subset) else 0.0,
                "negative_edge_sum": negative_edge,
                "positive_edge_sum": positive_edge,
                "negative_count": int(subset["edge_net_pnl"].lt(0).sum()) if len(subset) else 0,
                "positive_count": int(subset["edge_net_pnl"].gt(0).sum()) if len(subset) else 0,
                "fast_fail_count": fast_fail_count,
                "fast_fail_capture_pct": fast_fail_count / max(total_fast_fail_count, 1) * 100.0,
                "fast_fail_precision_pct": fast_fail_count / max(len(subset), 1) * 100.0 if len(subset) else 0.0,
                "coverage_of_total_negative_edge_pct": abs(negative_edge) / max(abs(total_negative_edge), 1e-9) * 100.0,
                "positive_edge_at_risk_pct": positive_edge / max(total_positive_edge, 1e-9) * 100.0,
            }
        )
    result = pd.DataFrame(rows)
    return result.sort_values(["edge_sum", "fast_fail_capture_pct"], ascending=[True, False])


def _decision(frame: pd.DataFrame, feature_diag: pd.DataFrame, rule_probe: pd.DataFrame) -> dict[str, Any]:
    acceptable = rule_probe[
        (rule_probe["negative_edge_sum"].lt(0))
        & (rule_probe["positive_edge_sum"].le(rule_probe["negative_edge_sum"].abs() * 0.30))
        & (rule_probe["fast_fail_capture_pct"].ge(25.0))
        & (rule_probe["fast_fail_precision_pct"].ge(35.0))
    ].copy()
    best_probe = acceptable.iloc[0].to_dict() if not acceptable.empty else rule_probe.iloc[0].to_dict()
    decision_label = "entry_proxy_not_ready_keep_stage526"
    if not acceptable.empty:
        decision_label = "entry_proxy_has_followup_engine_probe"

    return {
        "stage": "Stage235",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "event_count": int(len(frame)),
        "events_with_close_feature": int(frame["close_feature_status"].eq("ok").sum()),
        "fast_fail_event_count": int(frame["fast_fail"].sum()),
        "negative_edge_sum": float(frame.loc[frame["edge_net_pnl"].lt(0), "edge_net_pnl"].sum()),
        "positive_edge_sum": float(frame.loc[frame["edge_net_pnl"].gt(0), "edge_net_pnl"].sum()),
        "best_probe": _json_safe(best_probe),
        "feature_diagnostic_top_fast_fail_positive": _json_safe(
            feature_diag.sort_values("spearman_to_fast_fail", ascending=False).head(8).to_dict(orient="records")
        ),
        "feature_diagnostic_top_fast_fail_negative": _json_safe(
            feature_diag.sort_values("spearman_to_fast_fail").head(8).to_dict(orient="records")
        ),
        "interpretation": (
            "只读诊断：所有规则探针都只使用信号日收盘后可见状态；fast_fail仅作为评价标签，"
            "不得直接进入实盘规则。"
        ),
    }


def _plot(frame: pd.DataFrame, rule_probe: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    ax_eff, ax_box, ax_probe, ax_breakout = axes.flatten()

    colors = np.where(frame["fast_fail"].eq(1), "#dc2626", np.where(frame["edge_net_pnl"].lt(0), "#f97316", "#2563eb"))
    sizes = np.clip(frame["delta_volume"].abs() * 5 + 20, 25, 260)
    ax_eff.scatter(
        frame["directional_efficiency_10d"],
        frame["edge_net_pnl"],
        c=colors,
        s=sizes,
        alpha=0.75,
        edgecolors="#111827",
        linewidths=0.35,
    )
    ax_eff.axhline(0, color="#111827", linewidth=1)
    ax_eff.axvline(0.25, color="#6b7280", linestyle="--", linewidth=1)
    ax_eff.set_title("Edge vs 10d directional efficiency")
    ax_eff.set_xlabel("10d directional efficiency")
    ax_eff.set_ylabel("event edge net pnl")
    ax_eff.grid(alpha=0.25)

    box_data = [
        frame.loc[frame["fast_fail"].eq(1), "directional_efficiency_10d"].dropna(),
        frame.loc[(frame["edge_net_pnl"].lt(0)) & frame["fast_fail"].eq(0), "directional_efficiency_10d"].dropna(),
        frame.loc[frame["edge_net_pnl"].gt(0), "directional_efficiency_10d"].dropna(),
    ]
    ax_box.boxplot(box_data, tick_labels=["fast fail", "other neg", "positive"], showfliers=False)
    ax_box.axhline(0.25, color="#6b7280", linestyle="--", linewidth=1)
    ax_box.set_title("10d efficiency distribution")
    ax_box.grid(axis="y", alpha=0.25)

    show = rule_probe.sort_values("edge_sum").head(9).copy()
    ax_probe.barh(show["probe"], show["negative_edge_sum"], color="#dc2626", label="negative edge")
    ax_probe.barh(show["probe"], show["positive_edge_sum"], left=show["negative_edge_sum"], color="#16a34a", label="positive edge")
    ax_probe.axvline(0, color="#111827", linewidth=1)
    ax_probe.set_title("Entry-visible probe edge split")
    ax_probe.grid(axis="x", alpha=0.25)
    ax_probe.legend(loc="lower right", fontsize=8)

    ax_breakout.scatter(
        frame["close_breakout_margin_20d_pct"],
        frame["dir_ret_5d_pct"],
        c=colors,
        s=sizes,
        alpha=0.75,
        edgecolors="#111827",
        linewidths=0.35,
    )
    ax_breakout.axvline(0.20, color="#6b7280", linestyle="--", linewidth=1)
    ax_breakout.axhline(0.0, color="#6b7280", linestyle="--", linewidth=1)
    ax_breakout.set_title("Breakout margin vs 5d continuation")
    ax_breakout.set_xlabel("20d close breakout margin pct")
    ax_breakout.set_ylabel("5d directional return pct")
    ax_breakout.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    frame: pd.DataFrame,
    feature_diag: pd.DataFrame,
    bin_summary: pd.DataFrame,
    rule_probe: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    worst = frame.sort_values("edge_net_pnl").head(24)
    lines = [
        "# Stage235 Stage526快失败入场前代理诊断",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：Stage234 后续只读诊断；把事后快失败标签转成入场时可见代理的预测力测试。",
        "- 运行前过拟合判断：否。固定 Stage234 事件集，只新增信号日收盘前后可见的历史收盘序列特征；不改策略、不扫参数。",
        "- 运行前继续价值判断：是。若能找到低自由度代理，才值得进入真实引擎 A/C；若找不到，应停止这条形状。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势/突破系统常见反假突破方向是趋势强度、波动扩张、突破幅度、近端动量延续和震荡度。",
        "- GitHub 上常见的 turtle/Donchian/ATR/ADX 类实现也主要围绕这些变量组织，但多数示例没有解决商品组合保证金和真实成交路径问题。",
        "- 因此本阶段不复制外部策略，只把这些思想降维成当前引擎可复验的入场前代理变量。",
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
        "## 特征诊断",
        "",
        _md_table(feature_diag),
        "",
        "## 分箱汇总",
        "",
        _md_table(bin_summary, max_rows=80),
        "",
        "## 最差事件与入场代理",
        "",
        _md_table(
            worst[
                [
                    "date",
                    "product_vt_symbol",
                    "contract_vt_symbol",
                    "direction",
                    "signal",
                    "delta_volume",
                    "segment_days",
                    "edge_net_pnl",
                    "fast_fail",
                    "dir_ret_5d_pct",
                    "dir_ret_10d_pct",
                    "directional_efficiency_10d",
                    "close_breakout_margin_20d_pct",
                    "vol_expansion_1_over_10",
                    "entry_weak_stack_count",
                    "entry_quality_key",
                ]
            ],
            max_rows=24,
        ),
        "",
        "## 图表视觉复盘",
        "",
        f"- 图表：`{CHART_PATH}`",
        "- 左上：如果快失败真正可被趋势效率识别，红点应明显堆在低效率区。",
        "- 左下：箱线图用来确认红点和正贡献是否有可分离的分布。",
        "- 右上：规则探针如果红色负edge大、绿色正edge小，才值得进入真实引擎。",
        "- 右下：弱突破+弱延续如果有效，红点应集中在突破幅度低且5日方向收益弱的左下区域。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    events = _load_stage534_events()
    contracts = set(events["contract_vt_symbol"].astype(str).dropna())
    closes = _load_position_closes(contracts)
    frame = _attach_entry_visible_features(events, closes)
    feature_diag = _feature_diagnostic(frame)
    bin_summary = _bin_summary(frame)
    rule_probe = _rule_probes(frame)
    decision = _decision(frame, feature_diag, rule_probe)
    _plot(frame, rule_probe)
    _write_report(frame, feature_diag, bin_summary, rule_probe, decision)

    frame.to_csv(EVENT_FEATURE_PATH, index=False, encoding="utf-8-sig")
    feature_diag.to_csv(FEATURE_DIAGNOSTIC_PATH, index=False, encoding="utf-8-sig")
    bin_summary.to_csv(BIN_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    rule_probe.to_csv(RULE_PROBE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
