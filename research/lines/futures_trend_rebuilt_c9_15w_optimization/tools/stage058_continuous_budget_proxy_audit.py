from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage058"
MODEL_TAG = "stage058_continuous_budget_proxy_audit_v1"
STAGE_SLUG = "stage058_continuous_budget_proxy_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage058_continuous_budget_proxy_audit"

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
PROJECT_DIR = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE038_FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"

STAGE055_OUTPUT_DIR = LINE_DIR / "outputs" / "stage055_new_entry_signal_budget_audit"
STAGE055_PREFIX = "rebuilt_c9_stage055_new_entry_signal_budget_audit"
STAGE055_TAG = "stage055_new_entry_signal_budget_audit_v1"
STAGE055_FEATURE_MATRIX_PATH = STAGE055_OUTPUT_DIR / f"{STAGE055_PREFIX}_feature_matrix_{STAGE055_TAG}.csv"

PROXY_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_rows_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
QUALITY_BUCKETS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_buckets_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MIN_FULL_RETENTION_PCT = 80.0

EXTERNAL_RESEARCH_JUDGMENT = (
    "Trend-following position sizing references support scaling risk continuously by conviction and risk state. "
    "Stage058 therefore audits fixed continuous budget proxy shapes before any true-engine implementation."
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
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
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.copy()
    if max_rows is not None:
        shown = shown.head(max_rows)
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _to_bool(series: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        values = series.copy()
    else:
        values = pd.Series(series, index=index)
    if values.empty:
        return values.astype(bool)
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).ne(0)
    text = values.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"})


def _compute_quality_score(entries: pd.DataFrame) -> pd.Series:
    components: list[pd.Series] = []
    probability = _num(entries, "full_market_probability").clip(0.0, 1.0)
    if probability.notna().any():
        components.append(probability)
    ai_score = _num(entries, "ai_score").clip(0.0, 1.0)
    if ai_score.notna().any():
        components.append(ai_score)
    ai_rank = _num(entries, "ai_rank")
    rank_score = ((10.0 - ai_rank) / 9.0).clip(0.0, 1.0)
    if rank_score.notna().any():
        components.append(rank_score)
    if not components:
        return pd.Series(0.5, index=entries.index, dtype="float64")
    score = pd.concat(components, axis=1).mean(axis=1, skipna=True)
    return score.fillna(0.5).clip(0.0, 1.0)


def _candidate_multipliers(entries: pd.DataFrame) -> pd.DataFrame:
    quality = _compute_quality_score(entries)
    account_injured = _to_bool(entries.get("account_injured", False), index=entries.index)
    full_market_ai_top8 = _to_bool(entries.get("full_market_ai_top8", False), index=entries.index)
    linear_floor25 = (0.25 + 0.75 * quality).clip(0.25, 1.0)
    linear_floor50 = (0.50 + 0.50 * quality).clip(0.50, 1.0)
    recovery_floor75 = linear_floor25.where(~account_injured, np.maximum(linear_floor25, 0.75))
    top8_recovery_floor = recovery_floor75.where(~full_market_ai_top8, np.maximum(recovery_floor75, 0.85))
    return pd.DataFrame(
        {
            "quality_linear_floor25": linear_floor25,
            "quality_linear_floor50": linear_floor50,
            "quality_recovery_floor75": recovery_floor75,
            "quality_top8_recovery_floor": top8_recovery_floor,
        },
        index=entries.index,
    )


def _apply_continuous_budget(
    entries: pd.DataFrame,
    multipliers: pd.Series,
    *,
    variant: str,
    sample_scope: str,
) -> pd.DataFrame:
    result = entries.copy()
    result["sample_scope"] = sample_scope
    result["variant"] = variant
    result["budget_multiplier"] = pd.to_numeric(multipliers, errors="coerce").fillna(1.0).clip(0.0, 1.0)
    selected_volume = _num(result, "selected_volume", 1.0).fillna(1.0).clip(lower=0.0)
    realized_pnl = _num(result, "realized_pnl", 0.0).fillna(0.0)
    reducible_volume = (selected_volume - 1.0).clip(lower=0.0)
    result["candidate_volume_proxy"] = np.where(
        selected_volume.gt(1.0),
        1.0 + reducible_volume * result["budget_multiplier"],
        selected_volume,
    )
    result["removed_volume_proxy"] = (selected_volume - result["candidate_volume_proxy"]).clip(lower=0.0)
    result["removed_volume_fraction"] = np.where(
        selected_volume.gt(0.0),
        result["removed_volume_proxy"] / selected_volume,
        0.0,
    )
    result["removed_pnl_proxy"] = realized_pnl * result["removed_volume_fraction"]
    result["candidate_pnl_proxy"] = realized_pnl - result["removed_pnl_proxy"]
    result["quality_score"] = _compute_quality_score(result)
    result["selected_volume"] = selected_volume
    result["realized_pnl"] = realized_pnl
    return result


def _summarize_budget_proxy(proxy: pd.DataFrame) -> pd.DataFrame:
    if proxy.empty:
        return pd.DataFrame()
    data = proxy.copy()
    for column in [
        "realized_pnl",
        "candidate_pnl_proxy",
        "removed_pnl_proxy",
        "budget_multiplier",
        "selected_volume",
        "candidate_volume_proxy",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    data["candidate_delta_pnl_row"] = data["candidate_pnl_proxy"] - data["realized_pnl"]
    data["removed_positive_pnl_proxy"] = data["removed_pnl_proxy"].where(data["removed_pnl_proxy"].gt(0.0), 0.0)
    data["removed_negative_pnl_proxy"] = data["removed_pnl_proxy"].where(data["removed_pnl_proxy"].lt(0.0), 0.0)
    data["reduced_event"] = data["candidate_volume_proxy"].lt(data["selected_volume"] - 1e-12).astype("int64")
    summary = (
        data.groupby(["sample_scope", "variant"], dropna=False)
        .agg(
            row_count=("realized_pnl", "size"),
            reduced_event_count=("reduced_event", "sum"),
            original_pnl_sum=("realized_pnl", "sum"),
            candidate_pnl_sum=("candidate_pnl_proxy", "sum"),
            candidate_delta_pnl=("candidate_delta_pnl_row", "sum"),
            removed_pnl_proxy_sum=("removed_pnl_proxy", "sum"),
            removed_positive_pnl_proxy=("removed_positive_pnl_proxy", "sum"),
            removed_negative_pnl_proxy=("removed_negative_pnl_proxy", "sum"),
            selected_volume_sum=("selected_volume", "sum"),
            candidate_volume_sum=("candidate_volume_proxy", "sum"),
            avg_budget_multiplier=("budget_multiplier", "mean"),
            min_budget_multiplier=("budget_multiplier", "min"),
        )
        .reset_index()
    )
    summary["pnl_retention_pct"] = np.where(
        summary["original_pnl_sum"].gt(0.0),
        summary["candidate_pnl_sum"] / summary["original_pnl_sum"] * 100.0,
        np.nan,
    )
    summary["loss_reduction_pct"] = np.where(
        summary["original_pnl_sum"].lt(0.0),
        summary["candidate_delta_pnl"] / summary["original_pnl_sum"].abs() * 100.0,
        np.nan,
    )
    summary["volume_retention_pct"] = np.where(
        summary["selected_volume_sum"].gt(0.0),
        summary["candidate_volume_sum"] / summary["selected_volume_sum"] * 100.0,
        np.nan,
    )
    return summary.sort_values(["variant", "sample_scope"]).reset_index(drop=True)


def _quality_bucket_summary(entries: pd.DataFrame, sample_scope: str) -> pd.DataFrame:
    data = entries.copy()
    data["sample_scope"] = sample_scope
    data["quality_score"] = _compute_quality_score(data)
    data["realized_pnl"] = _num(data, "realized_pnl", 0.0).fillna(0.0)
    data["winner_flag"] = _to_bool(data.get("winner", data["realized_pnl"].gt(0.0)), index=data.index)
    if len(data) < 5:
        data["quality_bucket"] = 1
    else:
        data["quality_bucket"] = pd.qcut(data["quality_score"].rank(method="first"), 5, labels=False) + 1
    grouped = (
        data.groupby(["sample_scope", "quality_bucket"], dropna=False)
        .agg(
            row_count=("realized_pnl", "size"),
            pnl_sum=("realized_pnl", "sum"),
            mean_pnl=("realized_pnl", "mean"),
            win_rate_pct=("winner_flag", lambda s: float(s.mean() * 100.0)),
            selected_volume_mean=("selected_volume", "mean"),
        )
        .reset_index()
    )
    return grouped.sort_values(["sample_scope", "quality_bucket"]).reset_index(drop=True)


def _build_proxy_rows(full_entries: pd.DataFrame, pressure_entries: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for sample_scope, entries in [("full", full_entries), ("pressure", pressure_entries)]:
        multipliers = _candidate_multipliers(entries)
        for variant in multipliers.columns:
            rows.append(_apply_continuous_budget(entries, multipliers[variant], variant=variant, sample_scope=sample_scope))
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _evaluate_variants(summary: pd.DataFrame) -> pd.DataFrame:
    full = summary[summary["sample_scope"].eq("full")].set_index("variant")
    pressure = summary[summary["sample_scope"].eq("pressure")].set_index("variant")
    variants = sorted(set(full.index) & set(pressure.index))
    rows: list[dict[str, Any]] = []
    for variant in variants:
        full_row = full.loc[variant]
        pressure_row = pressure.loc[variant]
        full_retention = float(full_row.get("pnl_retention_pct", np.nan))
        pressure_delta = float(pressure_row.get("candidate_delta_pnl", np.nan))
        rows.append(
            {
                "variant": variant,
                "full_pnl_retention_pct": full_retention,
                "pressure_candidate_delta_pnl": pressure_delta,
                "full_candidate_delta_pnl": float(full_row.get("candidate_delta_pnl", np.nan)),
                "pressure_loss_reduction_pct": float(pressure_row.get("loss_reduction_pct", np.nan)),
                "passes_proxy_gate": bool(full_retention >= MIN_FULL_RETENTION_PCT and pressure_delta > 0.0),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["passes_proxy_gate", "pressure_candidate_delta_pnl", "full_pnl_retention_pct"],
        ascending=[False, False, False],
    )


def _plot(summary: pd.DataFrame) -> None:
    pivot_delta = summary.pivot(index="variant", columns="sample_scope", values="candidate_delta_pnl").fillna(0.0)
    pivot_retention = summary[summary["sample_scope"].eq("full")].set_index("variant")["pnl_retention_pct"]
    fig, axes = plt.subplots(2, 1, figsize=(15, 10), constrained_layout=True)
    x = np.arange(len(pivot_delta.index))
    axes[0].bar(x - 0.18, pivot_delta.get("pressure", pd.Series(0, index=pivot_delta.index)), width=0.36, label="pressure delta")
    axes[0].bar(x + 0.18, pivot_delta.get("full", pd.Series(0, index=pivot_delta.index)), width=0.36, label="full delta")
    axes[0].axhline(0.0, color="#111827", linewidth=0.9)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(pivot_delta.index.tolist(), rotation=25, ha="right")
    axes[0].set_title("Continuous Budget Proxy Delta PnL")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].bar(pivot_retention.index.tolist(), pivot_retention.values, color="#2563eb")
    axes[1].axhline(MIN_FULL_RETENTION_PCT, color="#f97316", linewidth=1.1, label="80% retention")
    axes[1].set_title("Full-Sample PnL Retention")
    axes[1].set_ylabel("%")
    axes[1].tick_params(axis="x", rotation=25)
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend(loc="best")
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, evaluation: pd.DataFrame, buckets: pd.DataFrame) -> None:
    report = f"""# Stage058 - 连续风险预算 proxy 审计

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：只读 proxy 审计；不改官方 C9，不连接 CTP，不调用订单 API。

## 外部调研判断

- pysystemtrade / Rob Carver、time-series momentum volatility scaling、trend-following position sizing 资料都支持连续 risk/forecast scaling。
- Stage058 因此只测试固定连续预算 proxy 是否同时满足压力样本减亏与全样本收益保留。

## 候选预算形状

- `quality_linear_floor25`：`0.25 + 0.75 * quality_score`。
- `quality_linear_floor50`：`0.50 + 0.50 * quality_score`。
- `quality_recovery_floor75`：账户受伤状态至少保留 `0.75` 预算，避免恢复右尾被砍。
- `quality_top8_recovery_floor`：在 recovery floor 基础上，full-market AI top8 至少保留 `0.85` 预算。
- 以上只作用于 `1` 手以上的预算，保留最小 `1` 手。

## 评价结论

{_md_table(evaluation)}

## 汇总

{_md_table(summary)}

## 质量分桶

{_md_table(buckets)}

## 判断

- 本阶段结论：`{decision['decision']}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

- proxy_rows: `{PROXY_ROWS_PATH}`
- summary: `{SUMMARY_PATH}`
- quality_buckets: `{QUALITY_BUCKETS_PATH}`
- chart: `{CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage058_continuous_budget_proxy_audit.md"
    content = f"""# Stage058 - 连续风险预算 proxy 审计

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 proxy 审计，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：pysystemtrade/Rob Carver forecast scaling、time-series momentum volatility scaling、trend-following position sizing / target volatility 资料。
- 我的判断：Stage057 已反证硬 cap，Stage058 只审计连续预算是否同时有压力减亏和全样本收益保留，不直接写交易规则。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage058_continuous_budget_proxy_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage058_continuous_budget_proxy.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；proxy 固定审计 `quality_linear_floor25/50`、`quality_recovery_floor75`、`quality_top8_recovery_floor`。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`{decision['decision']}`。
- 通过 proxy gate 的 variant：`{decision['passing_variant_count']}`。
- 最优 variant：`{decision['best_variant']}`。
- 最优 pressure delta PnL：`{decision['best_pressure_candidate_delta_pnl']:.2f}`。
- 最优 full retention：`{decision['best_full_pnl_retention_pct']:.4f}%`。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{SUMMARY_PATH}`
- chart：`{CHART_PATH}`

## 过拟合反思

- 运行前判断：否。Stage058 只做固定 proxy 审计，不按结果调 TopN、手数、品种或阈值。
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：有。Stage057 后需要验证连续预算方向是否比硬 cap 更有生命力。
- 运行后判断：{decision['continue_value_after']}
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    full_entries = _read_csv(STAGE038_FEATURE_MATRIX_PATH)
    pressure_entries = _read_csv(STAGE055_FEATURE_MATRIX_PATH)
    proxy_rows = _build_proxy_rows(full_entries, pressure_entries)
    summary = _summarize_budget_proxy(proxy_rows)
    evaluation = _evaluate_variants(summary)
    buckets = pd.concat(
        [
            _quality_bucket_summary(full_entries, "full"),
            _quality_bucket_summary(pressure_entries, "pressure"),
        ],
        ignore_index=True,
        sort=False,
    )
    _plot(summary)

    proxy_rows.to_csv(PROXY_ROWS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    buckets.to_csv(QUALITY_BUCKETS_PATH, index=False, encoding="utf-8-sig")

    passing = evaluation[evaluation["passes_proxy_gate"]]
    if passing.empty:
        best = evaluation.iloc[0] if not evaluation.empty else pd.Series(dtype=object)
        decision_text = "stage058_continuous_budget_proxy_no_variant_passed_keep_readonly"
        continue_after = "有限。连续预算方向仍有机制价值，但本批固定 proxy 不能直接进入真引擎。"
    else:
        best = passing.iloc[0]
        decision_text = "stage058_continuous_budget_proxy_has_candidate_needs_true_engine_probe"
        continue_after = "有。至少一个固定连续预算 proxy 同时满足压力减亏和全样本收益保留，下一步可做冻结真引擎探针。"

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "continuous_budget_proxy_readonly",
        "decision": decision_text,
        "strategy_changed": False,
        "official_live_config_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "passing_variant_count": int(len(passing)),
        "best_variant": str(best.get("variant", "")) if not best.empty else "",
        "best_pressure_candidate_delta_pnl": float(best.get("pressure_candidate_delta_pnl", np.nan)) if not best.empty else np.nan,
        "best_full_pnl_retention_pct": float(best.get("full_pnl_retention_pct", np.nan)) if not best.empty else np.nan,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": "否。固定 proxy 审计，不按结果调 TopN、手数、品种或日期。",
        "continue_value_before": "有。Stage057 证明硬 cap 错杀右尾，需要验证连续预算是否更合理。",
        "overfit_reflection_after": "否。本阶段没有调参，也没有进入真引擎；若根据结果微调 floor/分层才会过拟合。",
        "continue_value_after": continue_after,
        "outputs": {
            "proxy_rows": str(PROXY_ROWS_PATH),
            "summary": str(SUMMARY_PATH),
            "quality_buckets": str(QUALITY_BUCKETS_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary, evaluation, buckets)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
