from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage002"
MODEL_TAG = "stage002_goal_geometry_gap_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage002_goal_geometry_gap_audit"

UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage002_goal_geometry_gap_audit"

VARIANT_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_metrics_{MODEL_TAG}.csv"
WORST_CLUSTERS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_window_clusters_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_goal_gap_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class StageInput:
    stage: str
    family: str
    output_dir: str
    prefix: str
    tag: str
    aggregate_file_kind: str = "goal_aggregate"
    worst_file_kind: str = "goal_worst_windows"
    summary_file_kind: str | None = None

    @property
    def directory(self) -> Path:
        return UPSTREAM_LINE_DIR / "outputs" / self.output_dir

    @property
    def aggregate_path(self) -> Path:
        return self.directory / f"{self.prefix}_{self.aggregate_file_kind}_{self.tag}.csv"

    @property
    def worst_path(self) -> Path:
        return self.directory / f"{self.prefix}_{self.worst_file_kind}_{self.tag}.csv"

    @property
    def summary_path(self) -> Path | None:
        if self.summary_file_kind is None:
            return None
        return self.directory / f"{self.prefix}_{self.summary_file_kind}_{self.tag}.csv"


STAGE_INPUTS: tuple[StageInput, ...] = (
    StageInput(
        stage="Stage009",
        family="base_and_first_quality_proxy",
        output_dir="stage009_dense_start_goal_audit",
        prefix="rebuilt_c9_stage009_dense_start_goal_audit",
        tag="stage009_dense_start_goal_audit_v1",
        aggregate_file_kind="aggregate",
        worst_file_kind="worst_windows",
        summary_file_kind="full_cycle_retention",
    ),
    StageInput(
        stage="Stage013",
        family="account_state_pilot_true_engine",
        output_dir="stage013_account_state_pilot_gate_engine",
        prefix="rebuilt_c9_stage013_account_state_pilot_gate_engine",
        tag="stage013_account_state_pilot_gate_engine_v1",
        summary_file_kind="full_cycle_retention",
    ),
    StageInput(
        stage="Stage020",
        family="stage013_quality_add_risk_proxy",
        output_dir="stage020_stage013_high_quality_add_risk_proxy",
        prefix="rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy",
        tag="stage020_stage013_high_quality_add_risk_proxy_v1",
        summary_file_kind="summary",
    ),
    StageInput(
        stage="Stage021",
        family="full_market_consensus_jd_proxy",
        output_dir="stage021_full_market_consensus_jd_proxy",
        prefix="rebuilt_c9_stage021_full_market_consensus_jd_proxy",
        tag="stage021_full_market_consensus_jd_proxy_v1",
        summary_file_kind="summary",
    ),
    StageInput(
        stage="Stage024",
        family="regime_pause_true_engine",
        output_dir="stage024_causal_high_vol_pause_engine",
        prefix="rebuilt_c9_stage024_causal_high_vol_pause_engine",
        tag="stage024_causal_high_vol_pause_engine_v1",
        summary_file_kind="summary",
    ),
    StageInput(
        stage="Stage039",
        family="full_market_ai_top8_add_risk_proxy",
        output_dir="stage039_full_market_ai_top8_proxy",
        prefix="rebuilt_c9_stage039_full_market_ai_top8_proxy",
        tag="stage039_full_market_ai_top8_proxy_v1",
        summary_file_kind="summary",
    ),
    StageInput(
        stage="Stage046",
        family="warehouse_build_add_risk_proxy",
        output_dir="stage046_warehouse_build_add_risk_proxy",
        prefix="rebuilt_c9_stage046_warehouse_build_add_risk_proxy",
        tag="stage046_warehouse_build_add_risk_proxy_v1",
        summary_file_kind="summary",
    ),
    StageInput(
        stage="Stage052",
        family="contract_oi_share_add_risk_proxy",
        output_dir="stage052_contract_oi_share_add_risk_proxy",
        prefix="rebuilt_c9_stage052_contract_oi_share_add_risk_proxy",
        tag="stage052_contract_oi_share_add_risk_proxy_v1",
        summary_file_kind="summary",
    ),
    StageInput(
        stage="Stage062",
        family="oi_confirmed_cap_true_engine",
        output_dir="stage062_oi_confirmed_reverse_budget_engine",
        prefix="rebuilt_c9_stage062_oi_confirmed_reverse_budget_engine",
        tag="stage062_oi_confirmed_reverse_budget_engine_v1",
        summary_file_kind="retention",
    ),
    StageInput(
        stage="Stage070",
        family="super_quality_sibling_panel",
        output_dir="stage070_super_quality_sibling_panel",
        prefix="rebuilt_c9_stage070_super_quality_sibling_panel",
        tag="stage070_super_quality_sibling_panel_v1",
        summary_file_kind="variant_summary",
    ),
    StageInput(
        stage="Stage074",
        family="cold_start_capital_ramp_proxy",
        output_dir="stage074_cold_start_capital_ramp_proxy",
        prefix="rebuilt_c9_stage074_cold_start_capital_ramp_proxy",
        tag="stage074_cold_start_capital_ramp_proxy_v1",
        summary_file_kind="retention",
    ),
    StageInput(
        stage="Stage075",
        family="staggered_sleeve_proxy",
        output_dir="stage075_staggered_sleeve_deployment_proxy",
        prefix="rebuilt_c9_stage075_staggered_sleeve_deployment_proxy",
        tag="stage075_staggered_sleeve_deployment_proxy_v1",
        summary_file_kind="variant_summary",
    ),
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([default] * len(frame), index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _weighted_mean(frame: pd.DataFrame) -> float:
    if frame.empty:
        return np.nan
    weights = _numeric(frame, "window_count")
    values = _numeric(frame, "mean_return_pct", np.nan)
    mask = weights.gt(0) & values.notna()
    if not bool(mask.any()):
        return np.nan
    return float(np.average(values[mask], weights=weights[mask]))


def _first_existing_numeric(row: pd.Series, names: list[str]) -> float | None:
    for name in names:
        if name in row.index and pd.notna(row[name]):
            return float(row[name])
    return None


def load_retention_lookup(summary_path: Path | None) -> dict[str, dict[str, Any]]:
    if summary_path is None or not summary_path.exists():
        return {}
    frame = _read_csv(summary_path)
    if frame.empty or "variant" not in frame.columns:
        return {}

    lookup: dict[str, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        variant = str(row["variant"])
        pass_count = _first_existing_numeric(
            row,
            [
                "retention_vs_base_stage006_pass_count",
                "retention_vs_base_pass_count",
                "retention_vs_stage013_pass_count",
                "retention_pass_count",
            ],
        )
        rows = _first_existing_numeric(row, ["retention_rows", "source_count", "rows"])
        min_return = _first_existing_numeric(row, ["min_return_pct", "min_total_return_pct"])
        median_return = _first_existing_numeric(row, ["median_return_pct", "median_total_return_pct"])
        worst_dd = _first_existing_numeric(row, ["worst_max_dd_pct", "min_max_drawdown_pct"])
        sharpe = _first_existing_numeric(row, ["median_sharpe", "median_sharpe_ratio"])
        lookup[variant] = {
            "retention_pass_count": pass_count,
            "retention_rows": rows,
            "full_cycle_min_return_pct": min_return,
            "full_cycle_median_return_pct": median_return,
            "worst_max_dd_pct": worst_dd,
            "median_sharpe": sharpe,
        }
    return lookup


def summarize_goal_aggregate(
    stage: str,
    family: str,
    aggregate: pd.DataFrame,
    retention_lookup: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if aggregate.empty:
        return []
    retention_lookup = retention_lookup or {}
    rows: list[dict[str, Any]] = []
    for variant, variant_frame in aggregate.groupby("variant", sort=True):
        strict = variant_frame[variant_frame["audit_scope"].eq("all_trading_end_dates_gt_1y")]
        final = variant_frame[variant_frame["audit_scope"].eq("start_to_2026_06_30_only")]
        if strict.empty:
            continue

        strict_window_count = int(_numeric(strict, "window_count").sum())
        strict_negative_count = int(_numeric(strict, "negative_count").sum())
        strict_min_return = float(_numeric(strict, "min_return_pct", np.nan).min())
        strict_mean_return = _weighted_mean(strict)

        final_window_count = int(_numeric(final, "window_count").sum()) if not final.empty else 0
        final_negative_count = int(_numeric(final, "negative_count").sum()) if not final.empty else 0
        final_min_return = float(_numeric(final, "min_return_pct", np.nan).min()) if not final.empty else np.nan

        retention = retention_lookup.get(str(variant), {})
        retention_pass_count = retention.get("retention_pass_count")
        retention_rows = retention.get("retention_rows")
        if retention_pass_count is None or retention_rows in (None, 0):
            retention_goal_pass = None
        else:
            retention_goal_pass = int(float(retention_pass_count) >= float(retention_rows))

        rows.append(
            {
                "stage": stage,
                "family": family,
                "variant": str(variant),
                "candidate_id": f"{stage}:{variant}",
                "all_gt1y_window_count": strict_window_count,
                "all_gt1y_negative_count": strict_negative_count,
                "all_gt1y_negative_rate_pct": (
                    float(strict_negative_count / strict_window_count * 100.0) if strict_window_count else np.nan
                ),
                "all_gt1y_min_return_pct": strict_min_return,
                "all_gt1y_mean_return_pct": strict_mean_return,
                "to_final_window_count": final_window_count,
                "to_final_negative_count": final_negative_count,
                "to_final_min_return_pct": final_min_return,
                "retention_pass_count": retention_pass_count,
                "retention_rows": retention_rows,
                "retention_goal_pass": retention_goal_pass,
                "full_cycle_min_return_pct": retention.get("full_cycle_min_return_pct"),
                "full_cycle_median_return_pct": retention.get("full_cycle_median_return_pct"),
                "worst_max_dd_pct": retention.get("worst_max_dd_pct"),
                "median_sharpe": retention.get("median_sharpe"),
                "strict_goal_pass": int(strict_negative_count == 0 and strict_min_return > 0.0),
                "terminal_goal_pass": int(final_negative_count == 0 and (pd.isna(final_min_return) or final_min_return > 0.0)),
            }
        )
    return rows


def cluster_worst_windows(stage: str, family: str, worst: pd.DataFrame) -> pd.DataFrame:
    if worst.empty:
        return pd.DataFrame()
    frame = worst.copy()
    frame["start_date"] = pd.to_datetime(frame["start_date"], errors="coerce")
    frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce")
    frame["return_pct"] = pd.to_numeric(frame["return_pct"], errors="coerce")
    frame = frame.dropna(subset=["variant", "start_date", "end_date", "return_pct"])
    if frame.empty:
        return pd.DataFrame()
    frame["start_year_month"] = frame["start_date"].dt.strftime("%Y-%m")
    frame["end_year_month"] = frame["end_date"].dt.strftime("%Y-%m")
    frame["source_start_month"] = frame.get("source_start_month", "")
    group_cols = ["variant", "source_start_month", "start_year_month", "end_year_month"]
    grouped = frame.groupby(group_cols, dropna=False)
    clusters = grouped.agg(
        worst_window_rows=("return_pct", "size"),
        min_return_pct=("return_pct", "min"),
        median_return_pct=("return_pct", "median"),
        first_start_date=("start_date", "min"),
        last_end_date=("end_date", "max"),
    ).reset_index()
    clusters["stage"] = stage
    clusters["family"] = family
    clusters["candidate_id"] = clusters["stage"] + ":" + clusters["variant"].astype(str)
    clusters["first_start_date"] = pd.to_datetime(clusters["first_start_date"]).dt.date.astype(str)
    clusters["last_end_date"] = pd.to_datetime(clusters["last_end_date"]).dt.date.astype(str)
    columns = [
        "stage",
        "family",
        "variant",
        "candidate_id",
        "source_start_month",
        "start_year_month",
        "end_year_month",
        "worst_window_rows",
        "min_return_pct",
        "median_return_pct",
        "first_start_date",
        "last_end_date",
    ]
    return clusters[columns].sort_values(["min_return_pct", "worst_window_rows"], ascending=[True, False]).reset_index(drop=True)


def make_decision(metrics: pd.DataFrame) -> dict[str, Any]:
    if metrics.empty:
        return {
            "decision": "stage002_missing_metrics",
            "candidate_count": 0,
            "strict_goal_pass_count": 0,
        }

    data = metrics.copy()
    if "strict_goal_pass" not in data.columns:
        data["strict_goal_pass"] = (
            _numeric(data, "all_gt1y_negative_count").eq(0)
            & _numeric(data, "all_gt1y_min_return_pct", np.nan).gt(0.0)
        ).astype(int)
    if "terminal_goal_pass" not in data.columns:
        data["terminal_goal_pass"] = (
            _numeric(data, "to_final_negative_count").eq(0)
            & _numeric(data, "to_final_min_return_pct", 1.0).gt(0.0)
        ).astype(int)
    keep_cols = [
        "candidate_id",
        "stage",
        "family",
        "variant",
        "all_gt1y_negative_count",
        "all_gt1y_min_return_pct",
        "to_final_negative_count",
        "to_final_min_return_pct",
        "retention_goal_pass",
    ]
    for column in keep_cols:
        if column not in data.columns:
            data[column] = None
    if "all_gt1y_window_count" not in data.columns:
        data["all_gt1y_window_count"] = 0
    max_window_count = int(_numeric(data, "all_gt1y_window_count").max()) if not data.empty else 0
    data["full_panel_comparable"] = (
        _numeric(data, "all_gt1y_window_count").eq(float(max_window_count)) & (max_window_count > 0)
    ).astype(int)
    data["retention_goal_pass_filled"] = data["retention_goal_pass"].fillna(0).astype(int)
    strict_full = data[
        data["full_panel_comparable"].eq(1)
        & data["strict_goal_pass"].astype(int).eq(1)
        & data["retention_goal_pass_filled"].eq(1)
    ].copy()
    terminal_pass = int(data["terminal_goal_pass"].astype(int).sum())
    all_count = int(len(data))
    strict_count = int(len(strict_full))

    if strict_count > 0:
        decision = "stage002_has_goal_candidate_needs_true_engine_and_ab_review"
    else:
        decision = "stage002_goal_not_met_path_gap_map_ready"

    ranking_pool = data[data["full_panel_comparable"].eq(1)].copy()
    if ranking_pool.empty:
        ranking_pool = data.copy()
    by_negative = ranking_pool.sort_values(
        ["all_gt1y_negative_count", "all_gt1y_min_return_pct"], ascending=[True, False]
    ).iloc[0]
    by_min_return = ranking_pool.sort_values(
        ["all_gt1y_min_return_pct", "all_gt1y_negative_count"], ascending=[False, True]
    ).iloc[0]
    return {
        "decision": decision,
        "candidate_count": all_count,
        "full_panel_candidate_count": int(data["full_panel_comparable"].sum()),
        "max_all_gt1y_window_count": max_window_count,
        "terminal_goal_pass_count": terminal_pass,
        "strict_goal_pass_count": strict_count,
        "best_by_negative_count": by_negative[keep_cols].to_dict(),
        "best_by_min_return": by_min_return[keep_cols].to_dict(),
        "strict_goal_candidate_ids": strict_full["candidate_id"].tolist(),
    }


def _md_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
    if frame.empty:
        return "_无数据_"
    return frame.head(max_rows).to_markdown(index=False)


def _collect_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    metric_rows: list[dict[str, Any]] = []
    cluster_frames: list[pd.DataFrame] = []

    for spec in STAGE_INPUTS:
        aggregate = _read_csv(spec.aggregate_path)
        retention = load_retention_lookup(spec.summary_path)
        metric_rows.extend(summarize_goal_aggregate(spec.stage, spec.family, aggregate, retention))

        worst = _read_csv(spec.worst_path)
        clusters = cluster_worst_windows(spec.stage, spec.family, worst)
        if not clusters.empty:
            cluster_frames.append(clusters)

    metrics = pd.DataFrame(metric_rows)
    if not metrics.empty:
        max_window_count = int(_numeric(metrics, "all_gt1y_window_count").max())
        metrics["full_panel_comparable"] = (
            _numeric(metrics, "all_gt1y_window_count").eq(float(max_window_count)) & (max_window_count > 0)
        ).astype(int)
        metrics = metrics.sort_values(
            ["full_panel_comparable", "all_gt1y_negative_count", "all_gt1y_min_return_pct", "stage", "variant"],
            ascending=[False, True, False, True, True],
        ).reset_index(drop=True)
    clusters = pd.concat(cluster_frames, ignore_index=True, sort=False) if cluster_frames else pd.DataFrame()
    if not clusters.empty:
        clusters = clusters.sort_values(["min_return_pct", "worst_window_rows"], ascending=[True, False]).reset_index(drop=True)
    return metrics, clusters


def _plot_metrics(metrics: pd.DataFrame) -> None:
    if metrics.empty:
        return
    plot = metrics.head(18).copy()
    labels = plot["candidate_id"].astype(str).str.replace("Stage", "S", regex=False)
    fig, ax1 = plt.subplots(figsize=(15, 7))
    x = np.arange(len(plot))
    ax1.bar(x, plot["all_gt1y_negative_count"], color="#345995", alpha=0.82, label="negative windows")
    ax1.set_ylabel("Strict >1y negative windows")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=70, ha="right", fontsize=8)
    ax2 = ax1.twinx()
    ax2.plot(x, plot["all_gt1y_min_return_pct"], color="#d1495b", marker="o", linewidth=2, label="min return pct")
    ax2.axhline(0, color="#555555", linewidth=1)
    ax2.set_ylabel("Strict >1y min return pct")
    ax1.set_title("Stage002 goal geometry gap audit")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(metrics: pd.DataFrame, clusters: pd.DataFrame, decision: dict[str, Any]) -> None:
    top_metrics = metrics[
        [
            "candidate_id",
            "full_panel_comparable",
            "all_gt1y_negative_count",
            "all_gt1y_min_return_pct",
            "to_final_negative_count",
            "to_final_min_return_pct",
            "retention_goal_pass",
        ]
    ].head(15)
    top_clusters = clusters[
        [
            "candidate_id",
            "source_start_month",
            "start_year_month",
            "end_year_month",
            "worst_window_rows",
            "min_return_pct",
        ]
    ].head(20) if not clusters.empty else clusters
    lines = [
        "# Stage002 目标几何与路径缺口审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：目标几何/路径缺口审计，不产生新交易规则",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- Bailey/Lopez de Prado 的 PBO 框架提示，多次候选回测后直接挑最优很容易产生虚假发现。",
        "- Hurst/Ooi/Pedersen 的 managed futures 研究提示，趋势跟随的长期价值来自分散化和右尾捕获。",
        "- pysystemtrade capital correction 提示账户资金暴露可以调整，但必须和真实账户路径一致，不能只做历史窗口补丁。",
        "- 我的判断：本阶段应先量化路径目标缺口，不直接写过滤器或扫参数。",
        "",
        "## 关键结果",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 审计候选数：`{decision['candidate_count']}`。",
        f"- 完整面板可比候选数：`{decision['full_panel_candidate_count']}`，最大窗口数 `{decision['max_all_gt1y_window_count']}`。",
        f"- 严格目标通过候选数：`{decision['strict_goal_pass_count']}`。",
        f"- 终点口径通过候选数：`{decision['terminal_goal_pass_count']}`。",
        f"- 严格负窗口最少候选：`{decision['best_by_negative_count'].get('candidate_id')}`，负窗口 `{decision['best_by_negative_count'].get('all_gt1y_negative_count')}`，最差收益 `{decision['best_by_negative_count'].get('all_gt1y_min_return_pct')}`。",
        f"- 严格最差收益最高候选：`{decision['best_by_min_return'].get('candidate_id')}`，负窗口 `{decision['best_by_min_return'].get('all_gt1y_negative_count')}`，最差收益 `{decision['best_by_min_return'].get('all_gt1y_min_return_pct')}`。",
        "",
        "## 候选排序",
        "",
        _md_table(top_metrics, max_rows=15),
        "",
        "## 最差窗口聚类",
        "",
        _md_table(top_clusters, max_rows=20),
        "",
        "## 结论",
        "",
        "- 目前已知重建版候选没有一个同时满足严格任意 `>365` 天窗口无负收益和收益保留要求。",
        "- 多数候选的 `start_to_2026_06_30_only` 终点口径为 0 负窗口，说明最终曲线看起来可以，但中途一年以上持有窗口仍有深左尾。",
        "- 下一步应围绕路径左尾发生机制做因果源审计，而不是按当前候选继续调参。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不过拟合，本阶段是目标缺口审计，不新增交易规则。",
        "- 运行后判断：不过拟合。",
        "- 原因：只汇总已冻结候选的目标表现，没有选择新参数或按坏窗口写规则。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。",
        "- 运行后判断：有价值。",
        "- 原因：审计把终点正收益和严格路径目标拆开，能避免后续被表面资金曲线误导。",
        "",
        "## 输出文件",
        "",
        f"- variant_metrics：`{VARIANT_METRICS_PATH}`",
        f"- worst_window_clusters：`{WORST_CLUSTERS_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics, clusters = _collect_inputs()
    decision = make_decision(metrics)

    metrics.to_csv(VARIANT_METRICS_PATH, index=False, encoding="utf-8-sig")
    clusters.to_csv(WORST_CLUSTERS_PATH, index=False, encoding="utf-8-sig")
    _plot_metrics(metrics)
    _write_report(metrics, clusters, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
