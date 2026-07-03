from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage009_dense_start_goal_audit as s009
import stage039_full_market_ai_top8_proxy as s039


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage072"
MODEL_TAG = "stage072_q90_vol_overlay_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage072_q90_vol_overlay_proxy"

CAPITAL = 150000.0
BASE_VARIANT = "stage013_engine"
TARGET_VARIANT = "full_market_ai_top8_and_active_positions_lt3"
OVERLAY_SUFFIX = "_q90_vol_overlay"
OVERLAY_LOOKBACK = 63
OVERLAY_MIN_PERIODS = 20
OVERLAY_QUANTILE = 0.90
OVERLAY_MIN_HISTORY = 126
OVERLAY_FLOOR = 0.35
EPS = 1e-9

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage072_q90_vol_overlay_proxy"
STAGES_DIR = LINE_DIR / "stages"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE070_OUTPUT_DIR = LINE_DIR / "outputs" / "stage070_super_quality_sibling_panel"
STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE070_PREFIX = "rebuilt_c9_stage070_super_quality_sibling_panel"
STAGE070_TAG = "stage070_super_quality_sibling_panel_v1"

BASE_STAGE006_SUMMARY_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_summary_{STAGE006_TAG}.csv"
STAGE070_PANEL_CURVES_PATH = STAGE070_OUTPUT_DIR / f"{STAGE070_PREFIX}_panel_curves_{STAGE070_TAG}.csv.gz"

PANEL_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_panel_curves_{MODEL_TAG}.csv.gz"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return data.to_markdown(index=False)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def compute_q90_vol_multiplier(
    equity: pd.Series,
    *,
    lookback: int = OVERLAY_LOOKBACK,
    min_periods: int = OVERLAY_MIN_PERIODS,
    quantile: float = OVERLAY_QUANTILE,
    min_history: int = OVERLAY_MIN_HISTORY,
    floor: float = OVERLAY_FLOOR,
) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill().astype(float)
    pnl = values.diff().fillna(0.0)
    previous_equity = values.shift(1).replace(0.0, np.nan)
    daily_return = (pnl / previous_equity).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    trailing_vol = daily_return.rolling(int(lookback), min_periods=int(min_periods)).std().shift(1) * math.sqrt(252.0)
    q_vol = trailing_vol.expanding(min_periods=int(min_history)).quantile(float(quantile)).shift(1)
    multiplier = (q_vol / trailing_vol).clip(upper=1.0)
    multiplier = multiplier.where(trailing_vol.gt(q_vol), 1.0)
    multiplier = multiplier.fillna(1.0).clip(lower=float(floor), upper=1.0)
    return multiplier.astype(float).reset_index(drop=True)


def apply_multiplier_to_equity(equity: pd.Series, multiplier: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill().astype(float).reset_index(drop=True)
    mult = pd.to_numeric(multiplier, errors="coerce").fillna(1.0).astype(float).reset_index(drop=True)
    pnl = values.diff().fillna(0.0)
    adjusted = values.iloc[0] + (pnl * mult).cumsum()
    return adjusted.astype(float)


def build_overlay_panel_from_frames(
    panel_curves: pd.DataFrame,
    *,
    target_variants: list[str],
    overlay_suffix: str = OVERLAY_SUFFIX,
) -> pd.DataFrame:
    frame = panel_curves.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["requested_start_month"] = frame["requested_start_month"].astype(str)
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame[frame["variant"].isin([BASE_VARIANT, *target_variants])].dropna(subset=["date", "equity"]).copy()
    base = frame.copy()
    base["stage072_vol_multiplier"] = 1.0
    base["stage072_overlay_applied"] = 0
    parts = [base[["variant", "requested_start_month", "date", "equity", "stage072_vol_multiplier", "stage072_overlay_applied"]]]

    for variant in target_variants:
        selected = frame[frame["variant"].eq(variant)].copy()
        overlay_frames: list[pd.DataFrame] = []
        for source, group in selected.groupby("requested_start_month", sort=True):
            group = group.sort_values("date").reset_index(drop=True)
            multiplier = compute_q90_vol_multiplier(group["equity"])
            overlay = group[["requested_start_month", "date"]].copy()
            overlay["variant"] = f"{variant}{overlay_suffix}"
            overlay["equity"] = apply_multiplier_to_equity(group["equity"], multiplier)
            overlay["stage072_vol_multiplier"] = multiplier
            overlay["stage072_overlay_applied"] = multiplier.lt(1.0 - EPS).astype("int64")
            overlay["requested_start_month"] = str(source)
            overlay_frames.append(overlay[["variant", "requested_start_month", "date", "equity", "stage072_vol_multiplier", "stage072_overlay_applied"]])
        if overlay_frames:
            parts.append(pd.concat(overlay_frames, ignore_index=True, sort=False))

    return pd.concat(parts, ignore_index=True, sort=False).sort_values(
        ["variant", "requested_start_month", "date"]
    ).reset_index(drop=True)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s039._drawdown_pct(equity)


def _sharpe_from_equity(equity: pd.Series) -> float:
    return s039._sharpe_from_equity(equity)


def _source_summary(panel_curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in panel_curves.groupby(["variant", "requested_start_month"], sort=True):
        g = group.sort_values("date").copy()
        equity = pd.to_numeric(g["equity"], errors="coerce")
        rows.append(
            {
                "variant": str(g["variant"].iloc[0]),
                "requested_start_month": str(g["requested_start_month"].iloc[0]),
                "actual_start": pd.Timestamp(g["date"].iloc[0]).date().isoformat(),
                "actual_end": pd.Timestamp(g["date"].iloc[-1]).date().isoformat(),
                "trading_days": int(len(g)),
                "end_equity": float(equity.iloc[-1]),
                "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
                "max_dd_pct": float(_drawdown_pct(equity).min()),
                "sharpe": _sharpe_from_equity(equity),
                "overlay_day_count": int(pd.to_numeric(g.get("stage072_overlay_applied"), errors="coerce").fillna(0).sum()),
                "mean_multiplier": float(pd.to_numeric(g.get("stage072_vol_multiplier"), errors="coerce").fillna(1.0).mean()),
                "min_multiplier": float(pd.to_numeric(g.get("stage072_vol_multiplier"), errors="coerce").fillna(1.0).min()),
            }
        )
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _goal_audit(panel_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    curves = panel_curves[["variant", "requested_start_month", "date", "equity"]].copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["equity"] = pd.to_numeric(curves["equity"], errors="coerce")
    aggregate, _to_final, _fixed, worst = s009._run_audit(curves)
    return aggregate, worst


def _retention(source_summary: pd.DataFrame) -> pd.DataFrame:
    base_stage006 = _read_csv(BASE_STAGE006_SUMMARY_PATH)
    base_stage006 = base_stage006[["requested_start_month", "total_return_pct"]].rename(
        columns={"total_return_pct": "total_return_pct_base_stage006"}
    )
    stage013 = source_summary[source_summary["variant"].eq(BASE_VARIANT)][
        ["requested_start_month", "total_return_pct"]
    ].rename(columns={"total_return_pct": "total_return_pct_stage013"})
    rows = []
    for variant in sorted(set(source_summary["variant"]) - {BASE_VARIANT}):
        candidate = source_summary[source_summary["variant"].eq(variant)][
            ["requested_start_month", "total_return_pct"]
        ].rename(columns={"total_return_pct": "candidate_total_return_pct"})
        merged = base_stage006.merge(stage013, on="requested_start_month", how="inner").merge(
            candidate, on="requested_start_month", how="inner"
        )
        merged["variant"] = variant
        merged["vs_base_stage006_return_ratio"] = (
            merged["candidate_total_return_pct"]
            / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
        )
        merged["vs_stage013_return_ratio"] = (
            merged["candidate_total_return_pct"]
            / pd.to_numeric(merged["total_return_pct_stage013"], errors="coerce").replace(0.0, np.nan)
        )
        merged["passes_80pct_retention_vs_base_stage006"] = merged["vs_base_stage006_return_ratio"].ge(0.80).astype("int64")
        merged["passes_80pct_retention_vs_stage013"] = merged["vs_stage013_return_ratio"].ge(0.80).astype("int64")
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _variant_summary(source_summary: pd.DataFrame, aggregate: pd.DataFrame, retention: pd.DataFrame) -> pd.DataFrame:
    base_source = source_summary[source_summary["variant"].eq(BASE_VARIANT)].set_index("requested_start_month")
    rows = []
    for variant, group in source_summary.groupby("variant", sort=True):
        source_idx = group.set_index("requested_start_month")
        common = source_idx.index.intersection(base_source.index)
        return_delta = source_idx.loc[common, "total_return_pct"] - base_source.loc[common, "total_return_pct"]
        maxdd_delta = source_idx.loc[common, "max_dd_pct"] - base_source.loc[common, "max_dd_pct"]
        all_gt1y = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
        final = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
        ret = retention[retention["variant"].eq(variant)] if not retention.empty else pd.DataFrame()
        rows.append(
            {
                "variant": variant,
                "min_return_pct": float(group["total_return_pct"].min()),
                "median_return_pct": float(group["total_return_pct"].median()),
                "worst_max_dd_pct": float(group["max_dd_pct"].min()),
                "median_sharpe": float(group["sharpe"].median()),
                "return_improved_count_vs_stage013": int(return_delta.gt(EPS).sum()),
                "return_worse_count_vs_stage013": int(return_delta.lt(-EPS).sum()),
                "maxdd_improved_count_vs_stage013": int(maxdd_delta.gt(EPS).sum()),
                "maxdd_worse_count_vs_stage013": int(maxdd_delta.lt(-EPS).sum()),
                "overlay_day_count_median": float(group["overlay_day_count"].median()),
                "mean_multiplier_median": float(group["mean_multiplier"].median()),
                "min_multiplier_min": float(group["min_multiplier"].min()),
                "all_gt1y_window_count": int(all_gt1y["window_count"].sum()) if not all_gt1y.empty else 0,
                "all_gt1y_negative_count": int(all_gt1y["negative_count"].sum()) if not all_gt1y.empty else 0,
                "all_gt1y_min_return_pct": float(all_gt1y["min_return_pct"].min()) if not all_gt1y.empty else np.nan,
                "to_final_negative_count": int(final["negative_count"].sum()) if not final.empty else 0,
                "to_final_min_return_pct": float(final["min_return_pct"].min()) if not final.empty else np.nan,
                "retention_vs_base_pass_count": int(ret["passes_80pct_retention_vs_base_stage006"].sum()) if not ret.empty else 0,
                "retention_vs_stage013_pass_count": int(ret["passes_80pct_retention_vs_stage013"].sum()) if not ret.empty else 0,
                "retention_rows": int(len(ret)),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["all_gt1y_negative_count", "all_gt1y_min_return_pct", "median_return_pct"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def _decision(variant_summary: pd.DataFrame) -> dict[str, Any]:
    candidate_variant = f"{TARGET_VARIANT}{OVERLAY_SUFFIX}"
    candidate = variant_summary[variant_summary["variant"].eq(candidate_variant)]
    if candidate.empty:
        decision = "stage072_overlay_missing_candidate"
        next_stage = "debug_stage072_outputs"
        candidate_row: dict[str, Any] = {}
    else:
        candidate_row = candidate.iloc[0].to_dict()
        if (
            int(candidate_row["all_gt1y_negative_count"]) == 0
            and int(candidate_row["retention_vs_base_pass_count"]) == int(candidate_row["retention_rows"])
            and int(candidate_row["retention_rows"]) > 0
        ):
            decision = "stage072_q90_vol_overlay_has_goal_proxy_candidate_requires_true_engine"
            next_stage = "freeze_overlay_true_engine_validation"
        elif int(candidate_row["all_gt1y_negative_count"]) < 315429:
            decision = "stage072_q90_vol_overlay_partial_improvement_not_goal"
            next_stage = "do_not_tune_overlay_quantile_turn_to_new_pit_or_account_outer_layer_design"
        else:
            decision = "stage072_q90_vol_overlay_no_left_tail_value_stop"
            next_stage = "turn_to_new_pit_information"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "next_stage": next_stage,
        "arms": {
            "A": BASE_VARIANT,
            "B": f"{BASE_VARIANT}{OVERLAY_SUFFIX}",
            "C0": TARGET_VARIANT,
            "C": f"{TARGET_VARIANT}{OVERLAY_SUFFIX}",
        },
        "overlay": {
            "lookback": OVERLAY_LOOKBACK,
            "min_periods": OVERLAY_MIN_PERIODS,
            "quantile": OVERLAY_QUANTILE,
            "min_history": OVERLAY_MIN_HISTORY,
            "floor": OVERLAY_FLOOR,
        },
        "candidate": candidate_row,
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "triggered_ab_experiment": True,
        "external_research_judgment": (
            "条件波动率目标资料显示高波动状态下风险管理可能降低尾部和回撤；pysystemtrade/Rob Carver 的风险 overlay "
            "讨论同时提醒 overlay 会降低趋势正偏度，校准应按分布点或开启频率而不是回测收益调参。Stage072 因此固定 q90、63日、floor 0.35，"
            "只做账户外层 proxy，不扫参数。"
        ),
        "overfit_reflection_before": (
            "有风险但可控。账户 overlay 可能很容易被调成历史窗口补丁；本阶段只用固定 q90 分布点，不扫 lookback、floor 或 quantile。"
        ),
        "overfit_reflection_after": (
            "否。本阶段没有根据结果调参；若继续改 q80/q95、floor、lookback 或按 2022 窗口定制，就是过拟合。"
        ),
        "continue_value_before": "有。Stage071 证明加风险低覆盖剩余左尾，需要验证账户外层是否能低自由度缓冲。",
        "continue_value_after": (
            "若仍不能清零严格负窗口，则 q90 overlay 只能作为方向证据，下一步不能调参救它，应转新 PIT 信息源或更结构化账户设计。"
        ),
        "outputs": {
            "panel_curves": str(PANEL_CURVES_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "variant_summary": str(VARIANT_SUMMARY_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], variant_summary: pd.DataFrame, worst: pd.DataFrame) -> None:
    lines = [
        "# Stage072 - q90 realized-vol 账户 overlay proxy",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        f"- 下一步：`{decision['next_stage']}`",
        "- 阶段性质：账户外层 closed-curve proxy；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        f"- A/B/C：`{decision['arms']}`",
        f"- Overlay：`{decision['overlay']}`",
        "",
        "## 结果摘要",
        "",
        _md_table(variant_summary, max_rows=20),
        "",
        "## 最差窗口",
        "",
        _md_table(worst.head(24), max_rows=24),
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage072_q90_vol_overlay_proxy.md"
    report = REPORT_PATH.read_text(encoding="utf-8")
    header = f"""# Stage072 - q90 realized-vol 账户 overlay proxy

- 记录时间：`{timestamp.isoformat(timespec='minutes')}`
- line_id：`{LINE_ID}`
- 当前模式：`day`
- model_tag：`{MODEL_TAG}`
- 是否重要突破版本：`否`
- 是否触发A/B：`是，A/B/C proxy`
- 决策：`{decision['decision']}`

## 本次版本变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage072_q90_vol_overlay_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_stage072_q90_vol_overlay_proxy.py`
- 新增参数：`OVERLAY_LOOKBACK={OVERLAY_LOOKBACK}`、`OVERLAY_QUANTILE={OVERLAY_QUANTILE}`、`OVERLAY_FLOOR={OVERLAY_FLOOR}`、`OVERLAY_MIN_HISTORY={OVERLAY_MIN_HISTORY}`。
- 修改参数：无，Stage013/Stage070/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：Stage013 与 Stage070 最佳加风险曲线的账户外层 q90 vol overlay proxy。
- 本阶段不连接 CTP，不调用订单 API，不改实盘。

"""
    path.write_text(header + report, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage070_panel = _read_csv(STAGE070_PANEL_CURVES_PATH, parse_dates=["date"])
    panel = build_overlay_panel_from_frames(
        stage070_panel,
        target_variants=[BASE_VARIANT, TARGET_VARIANT],
    )
    source_summary = _source_summary(panel)
    aggregate, worst = _goal_audit(panel)
    retention = _retention(source_summary)
    variant_summary = _variant_summary(source_summary, aggregate, retention)
    decision = _decision(variant_summary)

    panel.to_csv(PANEL_CURVES_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, variant_summary, worst)
    stage_record = _write_stage_record(decision)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
