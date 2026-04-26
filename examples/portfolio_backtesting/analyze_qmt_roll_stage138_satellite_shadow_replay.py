from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_ai_product_pool_shadow_portfolio as shadow
from analyze_qmt_roll_ai_product_suitability_full_market_walkforward import (
    PREDICTIONS_OUTPUT_PATH,
    SOURCE_PREFIX,
)
from analyze_qmt_roll_ai_product_suitability_walkforward import PROBABILITY_COLUMN


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage138_satellite_shadow_replay_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage138_satellite_shadow_replay"

SATELLITE_CANDIDATES_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage137_satellite_principle_audit_satellite_candidates_stage137_satellite_principle_audit_v1.csv"
)
STAGE78_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"
FULL_MARKET_POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_position_changes_2020_2026_04.csv"
FULL_MARKET_DAILY_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_daily.csv"

MONTHLY_LABEL_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_label_{MODEL_TAG}.csv"
LABEL_AGG_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_label_aggregate_{MODEL_TAG}.csv"
PRODUCT_LABEL_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_label_{MODEL_TAG}.csv"
SHADOW_ELIGIBILITY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shadow_eligibility_{MODEL_TAG}.csv"
SHADOW_DAILY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shadow_daily_{MODEL_TAG}.csv"
SHADOW_SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shadow_summary_{MODEL_TAG}.csv"
SHADOW_YEARLY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shadow_yearly_{MODEL_TAG}.csv"
SHADOW_PRODUCT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shadow_product_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class LabelSpec:
    strategy: str
    description: str


@dataclass(frozen=True)
class ShadowSpec:
    strategy: str
    score_type: str
    top_n: int
    description: str


LABEL_SPECS: tuple[LabelSpec, ...] = (
    LabelSpec("all_full_market_reference", "全市场候选标签基准，只用于相对参考"),
    LabelSpec("ai_top8_all_products_reference", "全市场AI Top8标签基准，只用于相对参考"),
    LabelSpec("structural_candidates_all", "Stage137名字无关结构候选全体"),
    LabelSpec("structural_candidates_without_fu", "剔除fu后的结构候选，用于验证原则是否离开fu仍成立"),
    LabelSpec("structural_candidates_ai_top8", "结构候选与AI Top8交集"),
    LabelSpec("structural_candidates_ai_top12", "结构候选与AI Top12交集"),
    LabelSpec("fu_only_diagnostic", "fu单品种诊断，不作为新规则"),
)

SHADOW_SPECS: tuple[ShadowSpec, ...] = (
    ShadowSpec(
        strategy="baseline_all_products",
        score_type="baseline",
        top_n=0,
        description="全市场冻结持仓路径基准，只用于影子过滤对照",
    ),
    ShadowSpec(
        strategy="structural_candidates_all",
        score_type="name_blind_structural",
        top_n=5,
        description="只允许Stage137结构候选开新仓",
    ),
    ShadowSpec(
        strategy="structural_candidates_without_fu",
        score_type="name_blind_structural_ex_fu",
        top_n=4,
        description="只允许剔除fu后的结构候选开新仓",
    ),
    ShadowSpec(
        strategy="structural_candidates_ai_top8",
        score_type="structural_and_ai_top8",
        top_n=8,
        description="只允许结构候选且当期AI排名前8的品种开新仓",
    ),
    ShadowSpec(
        strategy="structural_candidates_ai_top12",
        score_type="structural_and_ai_top12",
        top_n=12,
        description="只允许结构候选且当期AI排名前12的品种开新仓",
    ),
    ShadowSpec(
        strategy="fu_only_diagnostic",
        score_type="single_product_diagnostic",
        top_n=1,
        description="只允许fu开新仓的诊断组，不作为正式规则",
    ),
)


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    numeric = _safe_float(value, default=float("nan"))
    if math.isnan(numeric):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.{digits}f}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 30) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def read_predictions() -> pd.DataFrame:
    _require(PREDICTIONS_OUTPUT_PATH)
    frame = pd.read_csv(PREDICTIONS_OUTPUT_PATH, encoding="utf-8-sig")
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    numeric_columns = [
        PROBABILITY_COLUMN,
        "future_net_pnl_60d",
        "target_future_top_half_60d",
        "future_rank_centered_60d",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["ai_rank"] = frame.groupby("eval_date")[PROBABILITY_COLUMN].rank(ascending=False, method="first")
    return frame


def read_candidates() -> pd.DataFrame:
    _require(SATELLITE_CANDIDATES_PATH)
    frame = pd.read_csv(SATELLITE_CANDIDATES_PATH, encoding="utf-8-sig")
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    return frame.sort_values("name_blind_structural_rank").reset_index(drop=True)


def select_products(group: pd.DataFrame, strategy: str, candidate_products: set[str]) -> pd.DataFrame:
    if strategy == "all_full_market_reference":
        return group.copy()
    if strategy == "ai_top8_all_products_reference":
        return group[group["ai_rank"] <= 8].copy()
    if strategy == "structural_candidates_all":
        return group[group["product_vt_symbol"].isin(candidate_products)].copy()
    if strategy == "structural_candidates_without_fu":
        return group[group["product_vt_symbol"].isin(candidate_products - {"fu.SHFE"})].copy()
    if strategy == "structural_candidates_ai_top8":
        return group[(group["product_vt_symbol"].isin(candidate_products)) & (group["ai_rank"] <= 8)].copy()
    if strategy == "structural_candidates_ai_top12":
        return group[(group["product_vt_symbol"].isin(candidate_products)) & (group["ai_rank"] <= 12)].copy()
    if strategy == "fu_only_diagnostic":
        return group[group["product_vt_symbol"].eq("fu.SHFE")].copy()
    raise ValueError(f"unknown label strategy: {strategy}")


def build_label_audit(predictions: pd.DataFrame, candidate_products: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_rows: list[dict[str, Any]] = []
    product_rows: list[dict[str, Any]] = []
    descriptions = {spec.strategy: spec.description for spec in LABEL_SPECS}

    for eval_date, group in predictions.groupby("eval_date", sort=True):
        group = group.sort_values("ai_rank")
        for spec in LABEL_SPECS:
            selected = select_products(group, spec.strategy, candidate_products)
            selected_count = int(len(selected))
            future_sum = float(selected["future_net_pnl_60d"].sum()) if selected_count else 0.0
            monthly_rows.append(
                {
                    "label_strategy": spec.strategy,
                    "description": spec.description,
                    "eval_date": pd.Timestamp(eval_date).date().isoformat(),
                    "selected_count": selected_count,
                    "selected_products": ",".join(selected["product_vt_symbol"].astype(str).tolist()),
                    "selected_future_net_pnl_60d": future_sum,
                    "selected_mean_future_net_pnl_60d": float(selected["future_net_pnl_60d"].mean()) if selected_count else 0.0,
                    "selected_positive_product_rate_pct": float((selected["future_net_pnl_60d"] > 0).mean() * 100.0)
                    if selected_count
                    else 0.0,
                    "selected_top_half_rate_pct": float(selected["target_future_top_half_60d"].mean() * 100.0)
                    if selected_count
                    else 0.0,
                    "selected_mean_rank_centered": float(selected["future_rank_centered_60d"].mean())
                    if selected_count
                    else 0.0,
                }
            )
            for row in selected.itertuples(index=False):
                product_rows.append(
                    {
                        "label_strategy": spec.strategy,
                        "description": descriptions[spec.strategy],
                        "eval_date": pd.Timestamp(eval_date).date().isoformat(),
                        "product_vt_symbol": row.product_vt_symbol,
                        "ai_rank": int(row.ai_rank),
                        "ai_probability": _safe_float(getattr(row, PROBABILITY_COLUMN)),
                        "future_net_pnl_60d": _safe_float(row.future_net_pnl_60d),
                        "target_future_top_half_60d": int(_safe_float(row.target_future_top_half_60d)),
                        "future_rank_centered_60d": _safe_float(row.future_rank_centered_60d),
                    }
                )

    monthly = pd.DataFrame(monthly_rows)
    product = pd.DataFrame(product_rows)
    return monthly, product


def aggregate_label_audit(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for strategy, group in monthly.groupby("label_strategy", sort=False):
        non_empty = group[group["selected_count"] > 0]
        rows.append(
            {
                "label_strategy": strategy,
                "description": str(group["description"].iloc[0]),
                "eval_count": int(group["eval_date"].nunique()),
                "non_empty_eval_count": int(len(non_empty)),
                "empty_eval_count": int((group["selected_count"] == 0).sum()),
                "mean_selected_count": float(group["selected_count"].mean()),
                "total_selected_count": int(group["selected_count"].sum()),
                "total_future_net_pnl_60d": float(group["selected_future_net_pnl_60d"].sum()),
                "mean_period_future_net_pnl_60d": float(group["selected_future_net_pnl_60d"].mean()),
                "median_period_future_net_pnl_60d": float(group["selected_future_net_pnl_60d"].median()),
                "positive_period_rate_pct": float((group["selected_future_net_pnl_60d"] > 0).mean() * 100.0),
                "worst_period_future_net_pnl_60d": float(group["selected_future_net_pnl_60d"].min()),
                "best_period_future_net_pnl_60d": float(group["selected_future_net_pnl_60d"].max()),
                "mean_product_positive_rate_pct": float(group["selected_positive_product_rate_pct"].mean()),
                "mean_top_half_rate_pct": float(group["selected_top_half_rate_pct"].mean()),
                "mean_rank_centered": float(group["selected_mean_rank_centered"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("total_future_net_pnl_60d", ascending=False).reset_index(drop=True)


def aggregate_product_labels(product_rows: pd.DataFrame) -> pd.DataFrame:
    if product_rows.empty:
        return pd.DataFrame()
    grouped = (
        product_rows.groupby(["label_strategy", "product_vt_symbol"], as_index=False)
        .agg(
            selected_periods=("eval_date", "count"),
            mean_ai_rank=("ai_rank", "mean"),
            mean_ai_probability=("ai_probability", "mean"),
            total_future_net_pnl_60d=("future_net_pnl_60d", "sum"),
            mean_future_net_pnl_60d=("future_net_pnl_60d", "mean"),
            positive_period_rate_pct=("future_net_pnl_60d", lambda s: float((s > 0).mean() * 100.0)),
            top_half_rate_pct=("target_future_top_half_60d", lambda s: float(s.mean() * 100.0)),
            mean_rank_centered=("future_rank_centered_60d", "mean"),
        )
        .sort_values(["label_strategy", "total_future_net_pnl_60d"], ascending=[True, False])
    )
    return grouped.reset_index(drop=True)


def build_shadow_eligibility(predictions: pd.DataFrame, candidate_products: set[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for eval_date, group in predictions.groupby("eval_date", sort=True):
        group = group.sort_values("ai_rank")
        for spec in SHADOW_SPECS:
            if spec.strategy == "baseline_all_products":
                continue
            selected = select_products(group, spec.strategy, candidate_products)
            for row in selected.itertuples(index=False):
                rows.append(
                    {
                        "strategy": spec.strategy,
                        "score_type": spec.score_type,
                        "eval_date": pd.Timestamp(eval_date),
                        "product_vt_symbol": row.product_vt_symbol,
                        "score": _safe_float(getattr(row, PROBABILITY_COLUMN)),
                        "score_rank": int(row.ai_rank),
                        "top_n": spec.top_n,
                    }
                )
    return pd.DataFrame(rows).sort_values(["strategy", "eval_date", "score_rank"]).reset_index(drop=True)


def run_shadow_replay(predictions: pd.DataFrame, eligibility: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    _require(FULL_MARKET_POSITION_CHANGES_PATH)
    _require(FULL_MARKET_DAILY_PATH)

    shadow.POSITION_CHANGES_PATH = FULL_MARKET_POSITION_CHANGES_PATH
    shadow.OFFICIAL_DAILY_PATH = FULL_MARKET_DAILY_PATH
    shadow.MARKET_PREDICTIONS_PATH = PREDICTIONS_OUTPUT_PATH

    position_changes = shadow.load_position_changes()
    official_daily = shadow.load_official_daily()
    signal_lookup = shadow.build_signal_lookup(eligibility)
    eval_dates = sorted(pd.Timestamp(date) for date in predictions["eval_date"].unique())
    first_eval_date = min(eval_dates)
    all_dates = pd.Series(sorted(position_changes["date"].unique()))
    valid_dates = all_dates[all_dates > first_eval_date]
    if valid_dates.empty:
        raise RuntimeError("no dates after first prediction eval date")
    evaluation_start = pd.Timestamp(valid_dates.iloc[0])

    date_signal = pd.DataFrame({"date": valid_dates})
    date_signal["signal_date"] = shadow.latest_signal_dates(date_signal["date"], eval_dates)
    signal_date_by_date = {
        pd.Timestamp(row.date): pd.Timestamp(row.signal_date)
        for row in date_signal.itertuples(index=False)
        if not pd.isna(row.signal_date)
    }

    official_eval = official_daily[official_daily["date"] >= evaluation_start].copy()
    if official_eval.empty:
        raise RuntimeError("official daily has no evaluation rows")
    initial_balance = float(official_eval.iloc[0]["balance"] - official_eval.iloc[0]["net_pnl"])

    strategy_frames: list[pd.DataFrame] = []
    for spec in SHADOW_SPECS:
        strategy_frames.append(
            shadow.build_shadow_rows(
                position_changes=position_changes,
                strategy=spec.strategy,
                evaluation_start=evaluation_start,
                signal_date_by_date=signal_date_by_date,
                signal_lookup=signal_lookup,
            )
        )
    strategy_rows = pd.concat(strategy_frames, ignore_index=True)
    spec_by_strategy = {spec.strategy: spec for spec in SHADOW_SPECS}
    daily = shadow.calculate_daily(strategy_rows, initial_balance)
    summary = shadow.calculate_summary(daily, initial_balance, spec_by_strategy)
    yearly = shadow.calculate_yearly(daily)
    product = shadow.calculate_product_attribution(strategy_rows)
    return daily, summary, yearly, product


def build_verdict(label_aggregate: pd.DataFrame, shadow_summary: pd.DataFrame) -> str:
    label = label_aggregate.set_index("label_strategy")
    shadow_idx = shadow_summary.set_index("strategy")

    no_fu_label_total = _safe_float(label.loc["structural_candidates_without_fu", "total_future_net_pnl_60d"])
    all_label_total = _safe_float(label.loc["structural_candidates_all", "total_future_net_pnl_60d"])
    fu_label_total = _safe_float(label.loc["fu_only_diagnostic", "total_future_net_pnl_60d"])
    no_fu_shadow_diff = _safe_float(
        shadow_idx.loc["structural_candidates_without_fu", "end_balance_diff_vs_baseline"]
    )
    all_shadow_diff = _safe_float(shadow_idx.loc["structural_candidates_all", "end_balance_diff_vs_baseline"])

    if no_fu_label_total > 0 and no_fu_shadow_diff > 0:
        return "STRUCTURAL_SATELLITE_SHADOW_PASS_KEEP_SHADOW_ONLY"
    if all_label_total > 0 and fu_label_total > 0 and no_fu_label_total <= 0 and all_shadow_diff > 0:
        return "FU_DEPENDENT_NOT_GENERAL_KEEP_STAGE78_FROZEN"
    return "STOP_SATELLITE_EXPANSION_KEEP_STAGE78_FROZEN"


def build_report(payload: dict[str, Any]) -> str:
    candidates = pd.DataFrame(payload["candidates"])
    label_aggregate = pd.DataFrame(payload["label_aggregate"])
    product_label = pd.DataFrame(payload["product_label"])
    shadow_summary = pd.DataFrame(payload["shadow_summary"])
    shadow_yearly = pd.DataFrame(payload["shadow_yearly"])
    metrics = payload["stage78_metrics"]

    return "\n".join(
        [
            f"# {MODEL_TAG}",
            "",
            "## 边界",
            "",
            "- 本阶段不修改Stage78正式策略，不新增交易规则。",
            "- 本阶段不是可执行vn.py回测，而是两层影子审计：未来60日标签审计 + 全市场冻结持仓路径开仓过滤影子复盘。",
            "- 标签审计使用固定的Stage137结构候选，不用未来收益生成候选。",
            "- `fu_only_diagnostic`只作为诊断，不允许升级为新规则。",
            "",
            "## 结论",
            "",
            f"- 判定：`{payload['verdict']}`。",
            "- 如果结构卫星原则离开`fu`后不能稳定成立，就不能扩大正式卫星池。",
            "- 当前可接受动作：Stage78继续冻结保留`fu`；卫星扩展只保留影子观察。",
            "",
            "## Stage78正式基准",
            "",
            f"- 期末权益：`{_fmt(metrics['end_balance'])}`",
            f"- 总收益：`{float(metrics['total_return_pct']):.4f}%`",
            f"- 最大回撤：`{float(metrics['max_dd_percent']):.4f}%`",
            f"- Sharpe：`{float(metrics['sharpe_ratio']):.4f}`",
            f"- 总滑点：`{_fmt(metrics['total_slippage'])}`",
            f"- 总交易次数：`{int(float(metrics['total_trade_count'])):,}`",
            f"- 胜率：`{float(metrics['win_ratio_pct']):.4f}%`",
            "",
            "## 固定结构候选",
            "",
            _to_markdown_table(
                candidates,
                [
                    "product_vt_symbol",
                    "name_blind_structural_rank",
                    "name_blind_structural_score",
                    "future_60d_total_net_pnl",
                    "stage78_full_net_pnl",
                ],
                max_rows=20,
            ),
            "",
            "## 标签聚合审计",
            "",
            _to_markdown_table(
                label_aggregate,
                [
                    "label_strategy",
                    "eval_count",
                    "mean_selected_count",
                    "total_future_net_pnl_60d",
                    "positive_period_rate_pct",
                    "worst_period_future_net_pnl_60d",
                    "mean_top_half_rate_pct",
                ],
                max_rows=20,
            ),
            "",
            "## 影子开仓过滤结果",
            "",
            _to_markdown_table(
                shadow_summary,
                [
                    "strategy",
                    "end_balance",
                    "end_balance_diff_vs_baseline",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_trade_count",
                    "total_slippage",
                ],
                max_rows=20,
            ),
            "",
            "## 影子年度结果",
            "",
            _to_markdown_table(
                shadow_yearly,
                ["strategy", "year", "net_pnl", "trade_count", "slippage", "max_dd_percent", "end_balance"],
                max_rows=40,
            ),
            "",
            "## 品种标签审计",
            "",
            _to_markdown_table(
                product_label[
                    product_label["label_strategy"].isin(
                        ["structural_candidates_all", "structural_candidates_without_fu", "fu_only_diagnostic"]
                    )
                ],
                [
                    "label_strategy",
                    "product_vt_symbol",
                    "selected_periods",
                    "mean_ai_rank",
                    "total_future_net_pnl_60d",
                    "positive_period_rate_pct",
                    "top_half_rate_pct",
                ],
                max_rows=40,
            ),
            "",
            "## 判断",
            "",
            "- 结构卫星原则如果只能靠`fu`贡献成立，就不是可推广规则。",
            "- 影子复盘若显示候选池降低亏损，只能说明它有风控观察价值，仍不能直接扩大正式池。",
            "- 后续若继续，应做影子月报或执行成本审计；不应把`UR/pg/eb/sn`直接写进正式策略。",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (SATELLITE_CANDIDATES_PATH, STAGE78_SUMMARY_PATH, PREDICTIONS_OUTPUT_PATH):
        _require(path)

    candidates = read_candidates()
    candidate_products = set(candidates["product_vt_symbol"].astype(str))
    predictions = read_predictions()
    monthly_label, selected_product_rows = build_label_audit(predictions, candidate_products)
    label_aggregate = aggregate_label_audit(monthly_label)
    product_label = aggregate_product_labels(selected_product_rows)
    shadow_eligibility = build_shadow_eligibility(predictions, candidate_products)
    shadow_daily, shadow_summary, shadow_yearly, shadow_product = run_shadow_replay(predictions, shadow_eligibility)

    stage78_summary = json.loads(STAGE78_SUMMARY_PATH.read_text(encoding="utf-8"))
    stage78_metrics = dict(stage78_summary["reference_metrics"]["full_2020_2026"])
    stage78_metrics["win_ratio_pct"] = stage78_summary["experiments"][0].get("win_ratio_pct", 0.0)
    verdict = build_verdict(label_aggregate, shadow_summary)

    monthly_label.to_csv(MONTHLY_LABEL_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    label_aggregate.to_csv(LABEL_AGG_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    product_label.to_csv(PRODUCT_LABEL_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    shadow_eligibility.to_csv(SHADOW_ELIGIBILITY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    shadow_daily.to_csv(SHADOW_DAILY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    shadow_summary.to_csv(SHADOW_SUMMARY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    shadow_yearly.to_csv(SHADOW_YEARLY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    shadow_product.to_csv(SHADOW_PRODUCT_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    payload: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "analysis_type": "satellite_shadow_replay_no_formal_strategy_change",
        "verdict": verdict,
        "base_version": stage78_summary.get("official_version", "official_stage78_defensive_v1"),
        "stage78_metrics": stage78_metrics,
        "design_boundary": (
            "Two-layer shadow audit only: fixed Stage137 structural candidates, future-label audit, and entry-filter "
            "shadow replay on frozen full-market position-change path. No strategy parameters are changed."
        ),
        "candidate_products": sorted(candidate_products),
        "candidates": candidates.to_dict(orient="records"),
        "label_aggregate": label_aggregate.to_dict(orient="records"),
        "product_label": product_label.to_dict(orient="records"),
        "shadow_summary": shadow_summary.to_dict(orient="records"),
        "shadow_yearly": shadow_yearly.to_dict(orient="records"),
        "parameters": {
            "label_strategies": [spec.__dict__ for spec in LABEL_SPECS],
            "shadow_specs": [spec.__dict__ for spec in SHADOW_SPECS],
            "signal_effective_rule": "latest eval_date strictly earlier than trade date",
            "legacy_position_rule": "positions already open at shadow evaluation start are kept until original exit",
        },
        "artifacts": {
            "monthly_label": str(MONTHLY_LABEL_OUTPUT_PATH),
            "label_aggregate": str(LABEL_AGG_OUTPUT_PATH),
            "product_label": str(PRODUCT_LABEL_OUTPUT_PATH),
            "shadow_eligibility": str(SHADOW_ELIGIBILITY_OUTPUT_PATH),
            "shadow_daily": str(SHADOW_DAILY_OUTPUT_PATH),
            "shadow_summary": str(SHADOW_SUMMARY_OUTPUT_PATH),
            "shadow_yearly": str(SHADOW_YEARLY_OUTPUT_PATH),
            "shadow_product": str(SHADOW_PRODUCT_OUTPUT_PATH),
            "summary": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(build_report(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "verdict": verdict,
                "candidate_products": sorted(candidate_products),
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
