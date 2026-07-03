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
STAGE = "Stage061"
MODEL_TAG = "stage061_oi_confirmed_reverse_budget_proxy_v1"
STAGE_SLUG = "stage061_oi_confirmed_reverse_budget_proxy"
OUTPUT_PREFIX = "rebuilt_c9_stage061_oi_confirmed_reverse_budget_proxy"
VARIANT = "oi_confirmed_cap_to_one"
TARGET_ARCHETYPE = "late_adverse_no_edge"
MIN_FULL_RETENTION_PCT = 80.0

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
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

STAGE059_OUTPUT_DIR = LINE_DIR / "outputs" / "stage059_trade_path_excursion_audit"
STAGE059_PREFIX = "rebuilt_c9_stage059_trade_path_excursion_audit"
STAGE059_TAG = "stage059_trade_path_excursion_audit_v1"
STAGE059_LOT_PATHS_PATH = STAGE059_OUTPUT_DIR / f"{STAGE059_PREFIX}_lot_paths_{STAGE059_TAG}.csv.gz"

PROXY_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_rows_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVALUATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_evaluation_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

EXTERNAL_RESEARCH_SOURCES = [
    "CME Open Interest: https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest",
    "pysystemtrade GitHub: https://github.com/pst-group/pysystemtrade",
    "Rob Carver risk sizing note: https://qoppac.blogspot.com/2020/03/how-much-risk-should-we-take.html",
    "QuantConnect futures trend/carry risk regimes: https://www.quantconnect.com/research/15989/futures-trend-following-and-carry-in-different-risk-regimes/",
]
EXTERNAL_RESEARCH_JUDGMENT = (
    "CME treats open interest as trend participation confirmation, not a standalone signal. "
    "Rob Carver / pysystemtrade style futures systems emphasize sizing by capital-at-risk and disciplined risk budgets. "
    "Stage061 therefore audits OI-confirmed only as a frozen reverse-risk-budget proxy, not as an OI high-quality add-risk rule."
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


def _apply_oi_confirmed_reverse_budget(
    entries: pd.DataFrame,
    *,
    variant: str,
    sample_scope: str,
) -> pd.DataFrame:
    result = entries.copy()
    result["sample_scope"] = sample_scope
    result["variant"] = variant
    selected_volume = _num(result, "selected_volume", 1.0).fillna(1.0).clip(lower=0.0)
    realized_pnl = _num(result, "realized_pnl", 0.0).fillna(0.0)
    oi_confirmed = _to_bool(result.get("oi_confirmed", result.get("entry_candidate_oi_confirmed", False)), result.index)
    applied = oi_confirmed & selected_volume.gt(1.0)
    candidate_volume = selected_volume.where(~applied, 1.0)
    removed_volume = (selected_volume - candidate_volume).clip(lower=0.0)
    removed_fraction = np.where(selected_volume.gt(0.0), removed_volume / selected_volume, 0.0)
    removed_pnl = realized_pnl * removed_fraction

    result["oi_confirmed"] = oi_confirmed
    result["selected_volume"] = selected_volume
    result["realized_pnl"] = realized_pnl
    result["oi_reverse_budget_applied"] = applied
    result["candidate_volume_proxy"] = candidate_volume
    result["removed_volume_proxy"] = removed_volume
    result["removed_volume_fraction"] = removed_fraction
    result["removed_pnl_proxy"] = removed_pnl
    result["candidate_pnl_proxy"] = realized_pnl - removed_pnl
    result["budget_multiplier_proxy"] = np.where(selected_volume.gt(0.0), candidate_volume / selected_volume, 1.0)
    return result


def _summarize_oi_reverse_budget(proxy: pd.DataFrame) -> pd.DataFrame:
    if proxy.empty:
        return pd.DataFrame()
    data = proxy.copy()
    for column in [
        "realized_pnl",
        "candidate_pnl_proxy",
        "removed_pnl_proxy",
        "selected_volume",
        "candidate_volume_proxy",
        "removed_volume_proxy",
        "budget_multiplier_proxy",
    ]:
        if column in data.columns:
            values = data[column]
        else:
            values = pd.Series(0.0, index=data.index)
        data[column] = pd.to_numeric(values, errors="coerce").fillna(0.0)
    data["oi_reverse_budget_applied"] = _to_bool(data.get("oi_reverse_budget_applied", False), data.index)
    data["candidate_delta_pnl_row"] = data["candidate_pnl_proxy"] - data["realized_pnl"]
    data["removed_positive_pnl_proxy"] = data["removed_pnl_proxy"].where(data["removed_pnl_proxy"].gt(0.0), 0.0)
    data["removed_negative_pnl_proxy"] = data["removed_pnl_proxy"].where(data["removed_pnl_proxy"].lt(0.0), 0.0)
    summary = (
        data.groupby(["sample_scope", "variant"], dropna=False)
        .agg(
            row_count=("realized_pnl", "size"),
            reduced_event_count=("oi_reverse_budget_applied", "sum"),
            original_pnl_sum=("realized_pnl", "sum"),
            candidate_pnl_sum=("candidate_pnl_proxy", "sum"),
            candidate_delta_pnl=("candidate_delta_pnl_row", "sum"),
            removed_pnl_proxy_sum=("removed_pnl_proxy", "sum"),
            removed_positive_pnl_proxy=("removed_positive_pnl_proxy", "sum"),
            removed_negative_pnl_proxy=("removed_negative_pnl_proxy", "sum"),
            selected_volume_sum=("selected_volume", "sum"),
            candidate_volume_sum=("candidate_volume_proxy", "sum"),
            removed_volume_sum=("removed_volume_proxy", "sum"),
            avg_budget_multiplier_proxy=("budget_multiplier_proxy", "mean"),
            min_budget_multiplier_proxy=("budget_multiplier_proxy", "min"),
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


def _evaluate_oi_reverse_budget(summary: pd.DataFrame, *, min_full_retention_pct: float = MIN_FULL_RETENTION_PCT) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    by_scope = {scope: frame.set_index("variant") for scope, frame in summary.groupby("sample_scope")}
    full = by_scope.get("full", pd.DataFrame())
    pressure = by_scope.get("pressure", pd.DataFrame())
    target = by_scope.get("target_late_adverse", pd.DataFrame())
    variants = sorted(set(full.index) & set(pressure.index) & set(target.index))
    rows: list[dict[str, Any]] = []
    for variant in variants:
        full_row = full.loc[variant]
        pressure_row = pressure.loc[variant]
        target_row = target.loc[variant]
        full_retention = float(full_row.get("pnl_retention_pct", np.nan))
        pressure_delta = float(pressure_row.get("candidate_delta_pnl", np.nan))
        target_delta = float(target_row.get("candidate_delta_pnl", np.nan))
        rows.append(
            {
                "variant": variant,
                "full_pnl_retention_pct": full_retention,
                "full_candidate_delta_pnl": float(full_row.get("candidate_delta_pnl", np.nan)),
                "pressure_candidate_delta_pnl": pressure_delta,
                "pressure_loss_reduction_pct": float(pressure_row.get("loss_reduction_pct", np.nan)),
                "target_candidate_delta_pnl": target_delta,
                "target_loss_reduction_pct": float(target_row.get("loss_reduction_pct", np.nan)),
                "full_removed_positive_pnl_proxy": float(full_row.get("removed_positive_pnl_proxy", np.nan)),
                "full_removed_negative_pnl_proxy": float(full_row.get("removed_negative_pnl_proxy", np.nan)),
                "passes_proxy_gate": bool(
                    full_retention >= min_full_retention_pct and pressure_delta > 0.0 and target_delta > 0.0
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["passes_proxy_gate", "target_candidate_delta_pnl", "pressure_candidate_delta_pnl", "full_pnl_retention_pct"],
        ascending=[False, False, False, False],
    )


def _build_proxy_rows(full_entries: pd.DataFrame, pressure_entries: pd.DataFrame, lot_paths: pd.DataFrame) -> pd.DataFrame:
    target = lot_paths[lot_paths["path_archetype"].astype(str).eq(TARGET_ARCHETYPE)].copy()
    rows = [
        _apply_oi_confirmed_reverse_budget(full_entries, variant=VARIANT, sample_scope="full"),
        _apply_oi_confirmed_reverse_budget(pressure_entries, variant=VARIANT, sample_scope="pressure"),
        _apply_oi_confirmed_reverse_budget(target, variant=VARIANT, sample_scope="target_late_adverse"),
    ]
    return pd.concat(rows, ignore_index=True, sort=False)


def _plot(summary: pd.DataFrame, evaluation: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), constrained_layout=True)
    if not summary.empty:
        delta = summary.set_index("sample_scope")["candidate_delta_pnl"]
        colors = ["#16a34a" if value >= 0.0 else "#dc2626" for value in delta.values]
        axes[0].bar(delta.index.tolist(), delta.values, color=colors)
    axes[0].axhline(0.0, color="#111827", linewidth=1.0)
    axes[0].set_title("OI-Confirmed Reverse Budget Proxy Delta PnL")
    axes[0].grid(True, axis="y", alpha=0.25)

    if not evaluation.empty:
        row = evaluation.iloc[0]
        axes[1].bar(["full retention"], [row["full_pnl_retention_pct"]], color="#2563eb")
    axes[1].axhline(MIN_FULL_RETENTION_PCT, color="#f97316", linewidth=1.2, label="80% retention")
    axes[1].set_ylim(0, 130)
    axes[1].set_title("Full-Sample PnL Retention Gate")
    axes[1].set_ylabel("%")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend(loc="best")
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decide(summary: pd.DataFrame, evaluation: pd.DataFrame) -> dict[str, Any]:
    if evaluation.empty:
        best = pd.Series(dtype=object)
        decision_text = "stage061_oi_confirmed_reverse_budget_proxy_no_data_keep_readonly"
        continue_after = "有限。缺少评估数据，不能推进。"
    else:
        passing = evaluation[evaluation["passes_proxy_gate"]]
        best = passing.iloc[0] if not passing.empty else evaluation.iloc[0]
        if bool(best.get("passes_proxy_gate", False)):
            decision_text = "stage061_oi_confirmed_reverse_budget_proxy_candidate_needs_daily_probe"
            continue_after = (
                "有。冻结 OI-confirmed 反向预算 proxy 同时满足全样本收益保留、压力样本减亏和 late-adverse 减亏，"
                "下一步必须做日级冷启动/真引擎探针，不能直接上线。"
            )
        else:
            decision_text = "stage061_oi_confirmed_reverse_budget_proxy_failed_keep_readonly"
            continue_after = "有限。若 proxy 未同时满足收益保留和减亏，继续调 OI 条件会变成救参。"
    scope_rows = summary.set_index("sample_scope") if not summary.empty else pd.DataFrame()
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit_type": "oi_confirmed_reverse_budget_proxy_readonly",
        "decision": decision_text,
        "strategy_changed": False,
        "official_live_config_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "variant": VARIANT,
        "passes_proxy_gate": bool(best.get("passes_proxy_gate", False)) if not best.empty else False,
        "full_pnl_retention_pct": float(best.get("full_pnl_retention_pct", np.nan)) if not best.empty else np.nan,
        "full_candidate_delta_pnl": float(best.get("full_candidate_delta_pnl", np.nan)) if not best.empty else np.nan,
        "pressure_candidate_delta_pnl": (
            float(best.get("pressure_candidate_delta_pnl", np.nan)) if not best.empty else np.nan
        ),
        "pressure_loss_reduction_pct": float(best.get("pressure_loss_reduction_pct", np.nan)) if not best.empty else np.nan,
        "target_candidate_delta_pnl": float(best.get("target_candidate_delta_pnl", np.nan)) if not best.empty else np.nan,
        "target_loss_reduction_pct": float(best.get("target_loss_reduction_pct", np.nan)) if not best.empty else np.nan,
        "full_removed_positive_pnl_proxy": (
            float(best.get("full_removed_positive_pnl_proxy", np.nan)) if not best.empty else np.nan
        ),
        "full_removed_negative_pnl_proxy": (
            float(best.get("full_removed_negative_pnl_proxy", np.nan)) if not best.empty else np.nan
        ),
        "full_original_pnl_sum": float(scope_rows.loc["full", "original_pnl_sum"]) if "full" in scope_rows.index else np.nan,
        "full_candidate_pnl_sum": float(scope_rows.loc["full", "candidate_pnl_sum"]) if "full" in scope_rows.index else np.nan,
        "pressure_original_pnl_sum": (
            float(scope_rows.loc["pressure", "original_pnl_sum"]) if "pressure" in scope_rows.index else np.nan
        ),
        "pressure_candidate_pnl_sum": (
            float(scope_rows.loc["pressure", "candidate_pnl_sum"]) if "pressure" in scope_rows.index else np.nan
        ),
        "target_original_pnl_sum": (
            float(scope_rows.loc["target_late_adverse", "original_pnl_sum"])
            if "target_late_adverse" in scope_rows.index
            else np.nan
        ),
        "target_candidate_pnl_sum": (
            float(scope_rows.loc["target_late_adverse", "candidate_pnl_sum"])
            if "target_late_adverse" in scope_rows.index
            else np.nan
        ),
        "external_research_sources": EXTERNAL_RESEARCH_SOURCES,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": "否。只冻结 Stage060 给出的 OI-confirmed 反向预算候选，不扫阈值、品种、方向或日期。",
        "continue_value_before": "有。Stage060 显示 OI-confirmed 同时覆盖 late-adverse 并在全样本为负，值得做一个只读预算 proxy。",
        "overfit_reflection_after": "否。本阶段只做单一冻结 proxy，未根据结果微调 OI 阈值、手数或样本窗口。",
        "continue_value_after": continue_after,
        "outputs": {
            "proxy_rows": str(PROXY_ROWS_PATH),
            "summary": str(SUMMARY_PATH),
            "evaluation": str(EVALUATION_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, evaluation: pd.DataFrame) -> None:
    sources = "\n".join(f"- {source}" for source in EXTERNAL_RESEARCH_SOURCES)
    report = f"""# Stage061 - OI-confirmed 反向风险预算 proxy

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：只读 proxy 审计；不改官方 C9，不连接 CTP，不调用订单 API。

## 外部调研判断

{sources}

- 我的判断：OI 可以解释参与度/趋势确认，但不是单独 alpha。Stage061 只把 `oi_confirmed` 作为 Stage060 发现的反向预算候选验证，不把它当高质量加仓信号。

## 冻结形状

- variant：`{VARIANT}`
- 条件：`oi_confirmed == True AND selected_volume > 1`
- 代理动作：该条件下 `candidate_volume_proxy = 1`；其它记录保持原始 `selected_volume`。
- 解释边界：这是 closed-lot 线性代理，不是真实组合引擎，也不是日级冷启动证明。

## 评价结论

{_md_table(evaluation)}

## 汇总

{_md_table(summary)}

## 判断

- 本阶段结论：`{decision['decision']}`。
- 全样本收益保留：`{decision['full_pnl_retention_pct']:.4f}%`
- 压力样本 delta PnL：`{decision['pressure_candidate_delta_pnl']:.2f}`
- late-adverse 目标 delta PnL：`{decision['target_candidate_delta_pnl']:.2f}`
- 全样本错杀正 PnL proxy：`{decision['full_removed_positive_pnl_proxy']:.2f}`
- 全样本移除负 PnL proxy：`{decision['full_removed_negative_pnl_proxy']:.2f}`
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

- proxy_rows：`{PROXY_ROWS_PATH}`
- summary：`{SUMMARY_PATH}`
- evaluation：`{EVALUATION_PATH}`
- chart：`{CHART_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage061_oi_confirmed_reverse_budget_proxy.md"
    sources = "\n".join(f"- {source}" for source in EXTERNAL_RESEARCH_SOURCES)
    content = f"""# Stage061 - OI-confirmed 反向风险预算 proxy

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']} CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 proxy 审计，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

{sources}

- 我的判断：OI 可作为参与度/趋势确认背景，但不应直接当 alpha 或加仓条件；Stage061 只验证 Stage060 发现的 `oi_confirmed` 反向预算候选。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage061_oi_confirmed_reverse_budget_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_stage061_oi_confirmed_reverse_budget_proxy.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；proxy 固定 `VARIANT={VARIANT}`。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`{decision['decision']}`。
- proxy gate 通过：`{decision['passes_proxy_gate']}`。
- 全样本 original PnL：`{decision['full_original_pnl_sum']:.2f}`。
- 全样本 candidate PnL：`{decision['full_candidate_pnl_sum']:.2f}`。
- 全样本收益保留：`{decision['full_pnl_retention_pct']:.4f}%`。
- 压力样本 original PnL：`{decision['pressure_original_pnl_sum']:.2f}`。
- 压力样本 candidate PnL：`{decision['pressure_candidate_pnl_sum']:.2f}`。
- 压力样本 delta PnL：`{decision['pressure_candidate_delta_pnl']:.2f}`。
- 压力样本 loss reduction：`{decision['pressure_loss_reduction_pct']:.4f}%`。
- late-adverse original PnL：`{decision['target_original_pnl_sum']:.2f}`。
- late-adverse candidate PnL：`{decision['target_candidate_pnl_sum']:.2f}`。
- late-adverse delta PnL：`{decision['target_candidate_delta_pnl']:.2f}`。
- late-adverse loss reduction：`{decision['target_loss_reduction_pct']:.4f}%`。
- 全样本错杀正 PnL proxy：`{decision['full_removed_positive_pnl_proxy']:.2f}`。
- 全样本移除负 PnL proxy：`{decision['full_removed_negative_pnl_proxy']:.2f}`。

## 回测指标说明

- 本阶段不是新增真引擎回测，不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 本阶段只读复用 Stage038/055/059 输出，检验一个 closed-lot 线性代理是否值得进入日级探针。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{SUMMARY_PATH}`
- evaluation：`{EVALUATION_PATH}`
- chart：`{CHART_PATH}`

## 过拟合反思

- 运行前判断：否。只冻结 Stage060 的 OI-confirmed 候选，不扫阈值/窗口/品种/方向。
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：有。需要验证 OI-confirmed 是否能在不伤全样本收益保留的前提下减少 pressure/late-adverse。
- 运行后判断：{decision['continue_value_after']}
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    full_entries = _read_csv(STAGE038_FEATURE_MATRIX_PATH)
    pressure_entries = _read_csv(STAGE055_FEATURE_MATRIX_PATH)
    lot_paths = _read_csv(STAGE059_LOT_PATHS_PATH)

    proxy_rows = _build_proxy_rows(full_entries, pressure_entries, lot_paths)
    summary = _summarize_oi_reverse_budget(proxy_rows)
    evaluation = _evaluate_oi_reverse_budget(summary)
    _plot(summary, evaluation)

    proxy_rows.to_csv(PROXY_ROWS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    evaluation.to_csv(EVALUATION_PATH, index=False, encoding="utf-8-sig")

    decision = _decide(summary, evaluation)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, summary, evaluation)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
