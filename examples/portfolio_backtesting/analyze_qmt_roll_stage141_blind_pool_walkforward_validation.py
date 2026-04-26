from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage141_blind_pool_walkforward_validation_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage141_blind_pool_walkforward_validation"

PREDICTIONS_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_full_market_walkforward_predictions_product_suitability_full_market_wf_v1.csv"
)
STAGE78_UNIVERSE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv"
)
STAGE78_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

MONTHLY_SELECTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_selection_{MODEL_TAG}.csv"
ARM_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_arm_summary_{MODEL_TAG}.csv"
PRODUCT_CONTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_contribution_{MODEL_TAG}.csv"
RANDOM_DISTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_random_distribution_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

POOL_SIZE: int = 19
HYBRID_EXTRA_SIZE: int = 5
RANDOM_TRIALS: int = 300
RANDOM_SEED: int = 20260425

ARMS: tuple[str, ...] = (
    "A_stage78_static19",
    "B_blind_ai_top19",
    "B2_blind_simple_top19",
    "C_stage78_plus_ai_extra5",
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


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
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


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame


def _read_inputs() -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    for path in (PREDICTIONS_PATH, STAGE78_UNIVERSE_PATH, STAGE78_SUMMARY_PATH):
        _require(path)
    predictions = pd.read_csv(PREDICTIONS_PATH, encoding="utf-8-sig")
    universe = pd.read_csv(STAGE78_UNIVERSE_PATH, encoding="utf-8-sig")
    summary = json.loads(STAGE78_SUMMARY_PATH.read_text(encoding="utf-8"))

    predictions["eval_date"] = pd.to_datetime(predictions["eval_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    _numeric(
        predictions,
        [
            "predicted_product_suitability_probability",
            "simple_trend_suitability_score",
            "simple_trend_suitability_score_percentile",
            "future_net_pnl_60d",
            "future_rank_centered_60d",
            "target_future_top_half_60d",
        ],
    )
    predictions = predictions.dropna(subset=["eval_date", "product_vt_symbol"]).copy()
    predictions["product_vt_symbol"] = predictions["product_vt_symbol"].astype(str)
    stage78_products = sorted(universe["product_vt_symbol"].dropna().astype(str).unique().tolist())
    return predictions, stage78_products, summary


def _select_products_for_month(
    month_df: pd.DataFrame,
    stage78_products: set[str],
) -> dict[str, list[str]]:
    ranked_ai = month_df.sort_values(
        ["predicted_product_suitability_probability", "product_vt_symbol"],
        ascending=[False, True],
    )
    ranked_simple = month_df.sort_values(
        ["simple_trend_suitability_score_percentile", "simple_trend_suitability_score", "product_vt_symbol"],
        ascending=[False, False, True],
    )
    available_stage78 = [product for product in sorted(stage78_products) if product in set(month_df["product_vt_symbol"])]
    blind_ai = ranked_ai["product_vt_symbol"].head(POOL_SIZE).astype(str).tolist()
    blind_simple = ranked_simple["product_vt_symbol"].head(POOL_SIZE).astype(str).tolist()
    extra = [
        product
        for product in ranked_ai["product_vt_symbol"].astype(str).tolist()
        if product not in stage78_products
    ][:HYBRID_EXTRA_SIZE]
    hybrid = sorted(set(available_stage78 + extra))
    return {
        "A_stage78_static19": available_stage78,
        "B_blind_ai_top19": blind_ai,
        "B2_blind_simple_top19": blind_simple,
        "C_stage78_plus_ai_extra5": hybrid,
    }


def _build_monthly_selection(predictions: pd.DataFrame, stage78_products: list[str]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    stage78_set = set(stage78_products)
    for eval_date, month_df in predictions.groupby("eval_date", sort=True):
        selections = _select_products_for_month(month_df, stage78_set)
        product_to_pnl = month_df.set_index("product_vt_symbol")["future_net_pnl_60d"].to_dict()
        product_to_top_half = month_df.set_index("product_vt_symbol")["target_future_top_half_60d"].to_dict()
        product_to_probability = month_df.set_index("product_vt_symbol")[
            "predicted_product_suitability_probability"
        ].to_dict()
        all_products = set(month_df["product_vt_symbol"].astype(str).tolist())
        for arm, products in selections.items():
            selected = [product for product in products if product in all_products]
            pnl_values = [float(product_to_pnl.get(product, 0.0)) for product in selected]
            top_half_values = [float(product_to_top_half.get(product, 0.0)) for product in selected]
            probability_values = [float(product_to_probability.get(product, 0.0)) for product in selected]
            overlap = len(set(selected) & stage78_set)
            records.append(
                {
                    "eval_date": eval_date,
                    "arm": arm,
                    "pool_size": len(selected),
                    "selected_products": ",".join(selected),
                    "stage78_overlap_count": overlap,
                    "stage78_overlap_rate_pct": overlap / max(1, len(selected)) * 100.0,
                    "month_future_net_pnl_60d": float(np.sum(pnl_values)),
                    "month_mean_future_net_pnl_60d": float(np.mean(pnl_values)) if pnl_values else 0.0,
                    "month_positive_product_rate_pct": float(np.mean(np.array(pnl_values) > 0.0) * 100.0)
                    if pnl_values
                    else 0.0,
                    "month_top_half_product_rate_pct": float(np.mean(top_half_values) * 100.0)
                    if top_half_values
                    else 0.0,
                    "month_mean_probability": float(np.mean(probability_values)) if probability_values else 0.0,
                    "non_stage78_products": ",".join([product for product in selected if product not in stage78_set]),
                }
            )
    return pd.DataFrame(records).sort_values(["eval_date", "arm"]).reset_index(drop=True)


def _build_random_distribution(predictions: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    products_by_month = {
        eval_date: month_df["product_vt_symbol"].astype(str).to_numpy()
        for eval_date, month_df in predictions.groupby("eval_date", sort=True)
    }
    pnl_by_month = {
        eval_date: month_df.set_index("product_vt_symbol")["future_net_pnl_60d"].astype(float).to_dict()
        for eval_date, month_df in predictions.groupby("eval_date", sort=True)
    }
    records: list[dict[str, Any]] = []
    for trial in range(RANDOM_TRIALS):
        for pool_size in (POOL_SIZE, POOL_SIZE + HYBRID_EXTRA_SIZE):
            monthly_pnls: list[float] = []
            for eval_date, products in products_by_month.items():
                sample_size = min(pool_size, len(products))
                selected = rng.choice(products, size=sample_size, replace=False)
                total = float(sum(pnl_by_month[eval_date].get(str(product), 0.0) for product in selected))
                monthly_pnls.append(total)
            monthly = pd.Series(monthly_pnls, dtype=float)
            records.append(
                {
                    "trial": trial,
                    "pool_size": pool_size,
                    "total_future_net_pnl_60d": float(monthly.sum()),
                    "mean_month_future_net_pnl_60d": float(monthly.mean()),
                    "positive_month_rate_pct": float((monthly > 0.0).mean() * 100.0),
                    "worst_month_future_net_pnl_60d": float(monthly.min()),
                    "best_month_future_net_pnl_60d": float(monthly.max()),
                    "sharpe_like": float(monthly.mean() / monthly.std(ddof=0) * math.sqrt(12))
                    if monthly.std(ddof=0) > 0
                    else 0.0,
                }
            )
    return pd.DataFrame(records)


def _summarize_arms(monthly_selection: pd.DataFrame, random_distribution: pd.DataFrame) -> pd.DataFrame:
    summary = (
        monthly_selection.groupby("arm", as_index=False)
        .agg(
            eval_months=("eval_date", "count"),
            avg_pool_size=("pool_size", "mean"),
            total_future_net_pnl_60d=("month_future_net_pnl_60d", "sum"),
            mean_month_future_net_pnl_60d=("month_future_net_pnl_60d", "mean"),
            median_month_future_net_pnl_60d=("month_future_net_pnl_60d", "median"),
            positive_month_rate_pct=("month_future_net_pnl_60d", lambda s: float((s > 0.0).mean() * 100.0)),
            worst_month_future_net_pnl_60d=("month_future_net_pnl_60d", "min"),
            best_month_future_net_pnl_60d=("month_future_net_pnl_60d", "max"),
            avg_stage78_overlap_rate_pct=("stage78_overlap_rate_pct", "mean"),
            avg_positive_product_rate_pct=("month_positive_product_rate_pct", "mean"),
            avg_top_half_product_rate_pct=("month_top_half_product_rate_pct", "mean"),
            avg_mean_probability=("month_mean_probability", "mean"),
        )
        .reset_index(drop=True)
    )
    month_std = monthly_selection.groupby("arm")["month_future_net_pnl_60d"].std(ddof=0).replace(0.0, np.nan)
    month_mean = monthly_selection.groupby("arm")["month_future_net_pnl_60d"].mean()
    sharpe_like = (month_mean / month_std * math.sqrt(12)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    summary = summary.merge(sharpe_like.rename("sharpe_like").reset_index(), on="arm", how="left")

    random_quantiles = (
        random_distribution.groupby("pool_size")["total_future_net_pnl_60d"]
        .quantile([0.1, 0.5, 0.75, 0.9])
        .unstack()
        .rename(columns={0.1: "random_total_p10", 0.5: "random_total_p50", 0.75: "random_total_p75", 0.9: "random_total_p90"})
        .reset_index()
    )
    summary["pool_size_round"] = summary["avg_pool_size"].round().astype(int)
    summary = summary.merge(random_quantiles, left_on="pool_size_round", right_on="pool_size", how="left")
    summary.drop(columns=["pool_size", "pool_size_round"], inplace=True, errors="ignore")
    baseline_total = float(
        summary.loc[summary["arm"].eq("A_stage78_static19"), "total_future_net_pnl_60d"].iloc[0]
    )
    baseline_worst = float(
        summary.loc[summary["arm"].eq("A_stage78_static19"), "worst_month_future_net_pnl_60d"].iloc[0]
    )
    baseline_positive_rate = float(
        summary.loc[summary["arm"].eq("A_stage78_static19"), "positive_month_rate_pct"].iloc[0]
    )
    summary["excess_vs_stage78_total"] = summary["total_future_net_pnl_60d"] - baseline_total
    summary["worst_month_delta_vs_stage78"] = summary["worst_month_future_net_pnl_60d"] - baseline_worst
    summary["positive_month_rate_delta_vs_stage78"] = summary["positive_month_rate_pct"] - baseline_positive_rate
    summary["beats_random_p75_same_size"] = summary["total_future_net_pnl_60d"] > summary["random_total_p75"].fillna(np.inf)
    return summary.sort_values("total_future_net_pnl_60d", ascending=False).reset_index(drop=True)


def _build_product_contribution(monthly_selection: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pnl_lookup = {
        (row.eval_date, str(row.product_vt_symbol)): float(row.future_net_pnl_60d)
        for row in predictions[["eval_date", "product_vt_symbol", "future_net_pnl_60d"]].itertuples(index=False)
    }
    for row in monthly_selection.itertuples(index=False):
        products = [product for product in str(row.selected_products).split(",") if product]
        for product in products:
            rows.append(
                {
                    "arm": row.arm,
                    "eval_date": row.eval_date,
                    "product_vt_symbol": product,
                    "future_net_pnl_60d": pnl_lookup.get((row.eval_date, product), 0.0),
                }
            )
    detail = pd.DataFrame(rows)
    if detail.empty:
        return detail
    summary = (
        detail.groupby(["arm", "product_vt_symbol"], as_index=False)
        .agg(
            selected_months=("eval_date", "count"),
            total_future_net_pnl_60d=("future_net_pnl_60d", "sum"),
            mean_future_net_pnl_60d=("future_net_pnl_60d", "mean"),
            positive_month_rate_pct=("future_net_pnl_60d", lambda s: float((s > 0.0).mean() * 100.0)),
        )
        .sort_values(["arm", "total_future_net_pnl_60d"], ascending=[True, False])
        .reset_index(drop=True)
    )
    positive_sum = (
        summary[summary["total_future_net_pnl_60d"] > 0.0]
        .groupby("arm")["total_future_net_pnl_60d"]
        .sum()
        .rename("arm_positive_total")
    )
    summary = summary.merge(positive_sum, on="arm", how="left")
    summary["positive_contribution_share_pct"] = np.where(
        summary["arm_positive_total"].fillna(0.0) > 0.0,
        summary["total_future_net_pnl_60d"].clip(lower=0.0) / summary["arm_positive_total"] * 100.0,
        0.0,
    )
    return summary


def _decision_table(arm_summary: pd.DataFrame, product_contribution: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline = arm_summary[arm_summary["arm"].eq("A_stage78_static19")].iloc[0]
    top_share = (
        product_contribution.groupby("arm")["positive_contribution_share_pct"].max().rename("top_positive_share_pct")
    )
    for row in arm_summary.merge(top_share, on="arm", how="left").itertuples(index=False):
        if row.arm == "A_stage78_static19":
            decision = "baseline"
            reason = "正式基准参考臂"
        else:
            beats_stage78 = row.total_future_net_pnl_60d > baseline.total_future_net_pnl_60d
            weak_window_ok = row.worst_month_future_net_pnl_60d >= baseline.worst_month_future_net_pnl_60d * 1.20
            monthly_ok = row.positive_month_rate_pct >= baseline.positive_month_rate_pct - 5.0
            random_ok = bool(row.beats_random_p75_same_size)
            concentration_ok = _safe_float(row.top_positive_share_pct) <= 45.0
            if beats_stage78 and weak_window_ok and monthly_ok and random_ok and concentration_ok:
                decision = "candidate_for_real_backtest"
                reason = "标签级盲选胜出且没有明显路径恶化，可进入真实回测"
            elif beats_stage78 and not concentration_ok:
                decision = "reject_concentrated"
                reason = "总分胜出但正贡献过度集中，可能是单品种/单阶段过拟合"
            elif beats_stage78:
                decision = "shadow_only"
                reason = "总分胜出但随机、弱窗口或月度稳定性未全部通过"
            else:
                decision = "reject"
                reason = "未超过Stage78标签级基准"
        rows.append(
            {
                "arm": row.arm,
                "decision": decision,
                "reason": reason,
                "top_positive_share_pct": _safe_float(getattr(row, "top_positive_share_pct", 0.0)),
            }
        )
    return pd.DataFrame(rows)


def _build_summary_payload(
    arm_summary: pd.DataFrame,
    decision: pd.DataFrame,
    random_distribution: pd.DataFrame,
    stage78_summary: dict[str, Any],
) -> dict[str, Any]:
    stage78_full = stage78_summary["reference_metrics"]["full_2020_2026"]
    decision_map = dict(zip(decision["arm"], decision["decision"], strict=False))
    serious_candidates = [
        arm for arm, value in decision_map.items() if value == "candidate_for_real_backtest"
    ]
    return {
        "model_tag": MODEL_TAG,
        "experiment_type": "label_proxy_ab_validation",
        "is_formal_backtest": False,
        "version_ab_skill_triggered": True,
        "hypothesis": (
            "A blind rolling product pool selected only from information available at each eval date "
            "should beat the manual Stage78 static universe if the original 18 products are merely overfit."
        ),
        "arms": {
            "A": "A_stage78_static19",
            "B": "B_blind_ai_top19",
            "B2": "B2_blind_simple_top19",
            "C": "C_stage78_plus_ai_extra5",
        },
        "stage78_reference": stage78_full,
        "pool_size": POOL_SIZE,
        "hybrid_extra_size": HYBRID_EXTRA_SIZE,
        "random_trials": RANDOM_TRIALS,
        "serious_candidates": serious_candidates,
        "promotion_decision": "real_backtest_next" if serious_candidates else "no_promotion_keep_stage78",
        "arm_summary": arm_summary.to_dict(orient="records"),
        "decision": decision.to_dict(orient="records"),
        "random_distribution_summary": random_distribution.groupby("pool_size")[
            "total_future_net_pnl_60d"
        ].describe().to_dict(),
    }


def _write_report(
    arm_summary: pd.DataFrame,
    decision: pd.DataFrame,
    product_contribution: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    stage78 = summary["stage78_reference"]
    serious_candidates = ", ".join(summary.get("serious_candidates", [])) or "无"
    promotion_decision = str(summary.get("promotion_decision", "unknown"))
    arm_cols = [
        "arm",
        "eval_months",
        "avg_pool_size",
        "total_future_net_pnl_60d",
        "excess_vs_stage78_total",
        "positive_month_rate_pct",
        "worst_month_future_net_pnl_60d",
        "sharpe_like",
        "avg_stage78_overlap_rate_pct",
        "random_total_p50",
        "random_total_p75",
        "beats_random_p75_same_size",
    ]
    decision_cols = ["arm", "decision", "reason", "top_positive_share_pct"]
    top_contrib = product_contribution.groupby("arm", group_keys=False).head(8)
    contrib_cols = [
        "arm",
        "product_vt_symbol",
        "selected_months",
        "total_future_net_pnl_60d",
        "positive_month_rate_pct",
        "positive_contribution_share_pct",
    ]
    report = f"""# Stage141 盲选滚动品种池验证

## 结论
- 当前基准：`official_stage78_defensive_v1`。
- A/B技能已触发：本阶段是品种池候选实验，但只跑最小有效标签级验证，不直接改正式策略。
- 推广结论：`{promotion_decision}`，真实回测候选：`{serious_candidates}`。
- 具体含义：盲选AI Top19、简单趋势Top19、Stage78+AI额外5个卫星都没有超过Stage78标签级基准；B2路径更平滑但总贡献仍低于Stage78，因此不能进入正式化。
- 过拟合判断：否。每个月只用当期已有AI概率或简单趋势分选下一期标签，不用未来收益TopN反推交易池。
- 是否有价值继续：有限。继续证明“全市场替换原始18”的价值下降，应保留Stage78；B2可作为观察样本，不进入真实回测。

## 实验臂
- A：`A_stage78_static19`，Stage78原始19品种。
- B：`B_blind_ai_top19`，全市场AI概率盲选Top19。
- B2：`B2_blind_simple_top19`，全市场简单趋势分盲选Top19。
- C：`C_stage78_plus_ai_extra5`，Stage78原池加非原池AI Top5卫星。
- 随机基准：同月同规模随机池`{RANDOM_TRIALS}`次。

## Stage78 正式基准
- 期末权益：{_fmt(stage78.get("end_balance"))}
- 总收益：{_fmt(stage78.get("total_return_pct"))}%
- 最大回撤：{_fmt(stage78.get("max_dd_percent"))}%
- Sharpe：{_fmt(stage78.get("sharpe_ratio"))}
- 总滑点：{_fmt(stage78.get("total_slippage"))}
- 总交易次数：{_fmt(stage78.get("total_trade_count"))}

## 标签级A/B/C结果
{_to_markdown_table(arm_summary, arm_cols, max_rows=20)}

## 决策表
{_to_markdown_table(decision, decision_cols, max_rows=20)}

## 各臂主要贡献品种
{_to_markdown_table(top_contrib, contrib_cols, max_rows=40)}

## 方法边界
- 本阶段不是正式回测，只是使用已有全市场walk-forward标签的最小有效验证。
- 标签`future_net_pnl_60d`来自未来60日产品净贡献，能检验方向，但不能替代真实组合回测、保证金约束和滑点路径。
- 若某臂标签级胜出但正贡献集中在单一品种，不能推进正式化。
- 只有`candidate_for_real_backtest`才允许进入下一阶段真实回测。

## 后续规划
- 若无真实回测候选：Stage78继续冻结，停止“全市场替换原始18”的正式化。
- 若有真实回测候选：下一阶段生成动态eligibility并跑A/C正式回测、起始年稳健性、季度walk-forward和滑点压力。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    predictions, stage78_products, stage78_summary = _read_inputs()
    monthly_selection = _build_monthly_selection(predictions, stage78_products)
    random_distribution = _build_random_distribution(predictions)
    arm_summary = _summarize_arms(monthly_selection, random_distribution)
    product_contribution = _build_product_contribution(monthly_selection, predictions)
    decision = _decision_table(arm_summary, product_contribution)
    summary = _build_summary_payload(arm_summary, decision, random_distribution, stage78_summary)

    monthly_selection.to_csv(MONTHLY_SELECTION_PATH, index=False, encoding="utf-8-sig")
    arm_summary.to_csv(ARM_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_contribution.to_csv(PRODUCT_CONTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    random_distribution.to_csv(RANDOM_DISTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(arm_summary, decision, product_contribution, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
