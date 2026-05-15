from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
MODEL_TAG: str = "stage276_profit_lock_trade_drilldown_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage276_profit_lock_trade_drilldown"

STAGE273_DETAIL: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage273_profit_lock_effectiveness_search_sim_detail_stage273_profit_lock_effectiveness_search_v1.csv"
)
STAGE273_CANDIDATE_SUMMARY: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage273_profit_lock_effectiveness_search_candidate_summary_stage273_profit_lock_effectiveness_search_v1.csv"
)
STAGE273_TIER_EFFECTIVENESS: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage273_profit_lock_effectiveness_search_tier_effectiveness_stage273_profit_lock_effectiveness_search_v1.csv"
)
STAGE275_DECISION: Path = (
    OUTPUT_DIR / "qmt_roll_stage275_profit_lock_full_robustness_decision_stage275_profit_lock_full_robustness_v1.json"
)
STAGE275_START_COMPARISON: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage275_profit_lock_full_robustness_start_year_comparison_stage275_profit_lock_full_robustness_v1.csv"
)
STAGE275_HORIZON_COMPARISON: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage275_profit_lock_full_robustness_horizon_comparison_stage275_profit_lock_full_robustness_v1.csv"
)
STAGE275_SLIPPAGE_COMPARISON: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage275_profit_lock_full_robustness_slippage_comparison_stage275_profit_lock_full_robustness_v1.csv"
)

OFFICIAL_ID: str = "current_official"
CANDIDATE_ID: str = "two_segment_l0.30_h0.90"


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if np.isnan(result) or np.isinf(result):
        return 0.0
    return result


def _build_leg_delta(detail: pd.DataFrame) -> pd.DataFrame:
    keep_cols = [
        "leg_id",
        "entry_year",
        "product_vt_symbol",
        "direction",
        "volume",
        "weight",
        "actual_pnl_pct",
        "sim_pnl_pct",
        "stop_hit",
        "stop_tier_trigger",
        "stop_tier_lock",
        "sim_exit_date",
        "actual_exit_date",
        "sim_exit_before_actual",
        "max_close_profit_pct",
    ]
    official = detail[detail["candidate_id"].eq(OFFICIAL_ID)][keep_cols].copy()
    candidate = detail[detail["candidate_id"].eq(CANDIDATE_ID)][keep_cols].copy()
    merged = official.merge(candidate, on="leg_id", suffixes=("_a", "_d"))
    merged["delta_pct"] = pd.to_numeric(merged["sim_pnl_pct_d"], errors="coerce").fillna(0.0) - pd.to_numeric(
        merged["sim_pnl_pct_a"], errors="coerce"
    ).fillna(0.0)
    merged["weight"] = pd.to_numeric(merged["weight_a"], errors="coerce").fillna(0.0)
    merged["weighted_delta"] = merged["delta_pct"] * merged["weight"]
    merged["product_vt_symbol"] = merged["product_vt_symbol_a"].astype(str)
    merged["entry_year"] = pd.to_numeric(merged["entry_year_a"], errors="coerce").fillna(0).astype(int)
    merged["direction"] = merged["direction_a"].astype(str)
    merged["d_stop_tier"] = (
        pd.to_numeric(merged["stop_tier_trigger_d"], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2%}")
        + "->"
        + pd.to_numeric(merged["stop_tier_lock_d"], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2%}")
    )
    merged.loc[pd.to_numeric(merged["stop_tier_trigger_d"], errors="coerce").fillna(0.0).le(0), "d_stop_tier"] = "no_lock"
    merged["a_stop_hit"] = pd.to_numeric(merged["stop_hit_a"], errors="coerce").fillna(0).astype(int)
    merged["d_stop_hit"] = pd.to_numeric(merged["stop_hit_d"], errors="coerce").fillna(0).astype(int)
    merged["d_early_exit"] = pd.to_numeric(merged["sim_exit_before_actual_d"], errors="coerce").fillna(0).astype(int)
    return merged


def _aggregate(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    grouped = (
        df.groupby(keys, as_index=False)
        .agg(
            leg_count=("leg_id", "count"),
            positive_leg_count=("weighted_delta", lambda s: int((s > 1e-12).sum())),
            negative_leg_count=("weighted_delta", lambda s: int((s < -1e-12).sum())),
            flat_leg_count=("weighted_delta", lambda s: int((s.abs() <= 1e-12).sum())),
            weighted_delta_sum=("weighted_delta", "sum"),
            median_delta_pct=("delta_pct", "median"),
            d_stop_hit_count=("d_stop_hit", "sum"),
            d_early_exit_count=("d_early_exit", "sum"),
        )
        .sort_values("weighted_delta_sum", ascending=False)
        .reset_index(drop=True)
    )
    grouped["positive_leg_rate_pct"] = (
        grouped["positive_leg_count"] / grouped["leg_count"].replace(0, np.nan) * 100.0
    ).fillna(0.0)
    return grouped


def _concentration(delta: pd.DataFrame) -> dict[str, Any]:
    positive = delta[delta["weighted_delta"] > 0].sort_values("weighted_delta", ascending=False)
    negative = delta[delta["weighted_delta"] < 0].sort_values("weighted_delta")
    total_positive = float(positive["weighted_delta"].sum())
    total_negative_abs = float((-negative["weighted_delta"]).sum())
    return {
        "positive_leg_count": int(len(positive)),
        "negative_leg_count": int(len(negative)),
        "flat_leg_count": int((delta["weighted_delta"].abs() <= 1e-12).sum()),
        "total_positive_weighted_delta": total_positive,
        "total_negative_weighted_delta_abs": total_negative_abs,
        "net_weighted_delta": float(delta["weighted_delta"].sum()),
        "top5_positive_share_pct": float(positive.head(5)["weighted_delta"].sum() / total_positive * 100.0)
        if total_positive > 0
        else 0.0,
        "top10_positive_share_pct": float(positive.head(10)["weighted_delta"].sum() / total_positive * 100.0)
        if total_positive > 0
        else 0.0,
        "top5_negative_share_pct": float((-negative.head(5)["weighted_delta"]).sum() / total_negative_abs * 100.0)
        if total_negative_abs > 0
        else 0.0,
        "top10_negative_share_pct": float((-negative.head(10)["weighted_delta"]).sum() / total_negative_abs * 100.0)
        if total_negative_abs > 0
        else 0.0,
    }


def _decision(
    *,
    stage275_decision: dict[str, Any],
    concentration: dict[str, Any],
    by_year: pd.DataFrame,
    by_product: pd.DataFrame,
    start_comparison: pd.DataFrame,
    horizon_comparison: pd.DataFrame,
    slippage_comparison: pd.DataFrame,
) -> dict[str, Any]:
    negative_years = by_year[by_year["weighted_delta_sum"] < -1e-9]
    top_product_share = 0.0
    positive_total = float(by_product[by_product["weighted_delta_sum"] > 0]["weighted_delta_sum"].sum())
    if positive_total > 0:
        top_product_share = float(by_product["weighted_delta_sum"].clip(lower=0).head(3).sum() / positive_total * 100.0)

    start_year_win_count = int((start_comparison["d_end_minus_a"] > 0).sum())
    horizon_win_rate = float((horizon_comparison[horizon_comparison["horizon"].isin(["63", "126", "252", 63, 126, 252])]["d_end_minus_a"] > 0).mean() * 100.0)
    slip_5x = slippage_comparison[slippage_comparison["slippage_multiplier"].eq(5.0)].iloc[0]

    pass_stage276 = bool(
        stage275_decision.get("pass_stage275")
        and negative_years.empty
        and concentration["net_weighted_delta"] > 0
        and concentration["top10_positive_share_pct"] < 85.0
        and top_product_share < 85.0
        and start_year_win_count >= 5
        and horizon_win_rate >= 50.0
        and _safe_float(slip_5x["d_end_minus_a"]) > 0
    )
    return {
        "candidate": "D_two_segment_30_90",
        "candidate_tiers": "0.30:0.270,0.20:0.180,0.10:0.090,0.05:0.015,0.03:0.009,0.02:0.006",
        "pass_stage276": pass_stage276,
        "promotion_decision": "freeze_as_stage78_2_research_candidate_not_auto_live" if pass_stage276 else "hold_no_promotion",
        "stage275_pass": bool(stage275_decision.get("pass_stage275")),
        "negative_event_year_count": int(len(negative_years)),
        "event_net_weighted_delta": concentration["net_weighted_delta"],
        "top10_positive_share_pct": concentration["top10_positive_share_pct"],
        "top3_product_positive_share_pct": top_product_share,
        "start_year_win_count": start_year_win_count,
        "horizon_pair_win_rate_pct": horizon_win_rate,
        "slippage_5x_end_minus_a": _safe_float(slip_5x["d_end_minus_a"]),
        "next_step": "manual_review_then_optional_stage78_2_candidate_config" if pass_stage276 else "keep_stage78_1_formal",
    }


def _format_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "- 无数据"
    view = df[[column for column in columns if column in df.columns]].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_markdown(index=False)


def _write_report(
    *,
    candidate_summary: pd.DataFrame,
    tier_effectiveness: pd.DataFrame,
    concentration: dict[str, Any],
    by_year: pd.DataFrame,
    by_product: pd.DataFrame,
    by_tier: pd.DataFrame,
    top_positive: pd.DataFrame,
    top_negative: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    d_summary = candidate_summary[candidate_summary["candidate_id"].eq(CANDIDATE_ID)].copy()
    official_summary = candidate_summary[candidate_summary["candidate_id"].eq(OFFICIAL_ID)].copy()
    report = f"""# Stage276 盈利锁定 D 候选逐笔归因与冻结审查

## 目的

- 不再搜索参数，只审查 Stage275 通过的 D 候选是否靠少数交易、少数年份或少数品种撑起来。
- D 候选：`30%->27% / 20%->18% / 10%->9% / 5%->1.5% / 3%->0.9% / 2%->0.6%`。
- 事件级归因沿用 Stage273 的真实 Stage78-1 成交路径；引擎级稳健性沿用 Stage275。

## 判定

```json
{json.dumps(decision, ensure_ascii=False, indent=2)}
```

## 候选摘要

### Official

{_format_table(official_summary, ["candidate_id", "trade_legs", "stop_hit_rate", "early_exit_rate", "weighted_pnl_sum", "weighted_delta_sum", "year_win_count", "start_year_win_count", "min_year_delta_sum", "robust_score"])}

### D

{_format_table(d_summary, ["candidate_id", "trade_legs", "stop_hit_rate", "early_exit_rate", "weighted_pnl_sum", "weighted_delta_sum", "year_win_count", "start_year_win_count", "min_year_delta_sum", "robust_score"])}

## 贡献集中度

```json
{json.dumps(concentration, ensure_ascii=False, indent=2)}
```

## 按年份拆解

{_format_table(by_year, ["entry_year", "leg_count", "positive_leg_count", "negative_leg_count", "flat_leg_count", "weighted_delta_sum", "median_delta_pct", "d_stop_hit_count", "d_early_exit_count", "positive_leg_rate_pct"])}

## 按品种拆解

{_format_table(by_product, ["product_vt_symbol", "leg_count", "positive_leg_count", "negative_leg_count", "flat_leg_count", "weighted_delta_sum", "median_delta_pct", "d_stop_hit_count", "d_early_exit_count", "positive_leg_rate_pct"], 30)}

## 按 D 触发层拆解

{_format_table(by_tier, ["d_stop_tier", "leg_count", "positive_leg_count", "negative_leg_count", "flat_leg_count", "weighted_delta_sum", "median_delta_pct", "d_stop_hit_count", "d_early_exit_count", "positive_leg_rate_pct"])}

## 当前正式层级有效性复查

{_format_table(tier_effectiveness, ["tier_label", "crossed_trade_legs", "highest_reached_trade_legs", "sim_stop_hit_trade_legs", "sim_stop_hit_before_actual_exit", "positive_help_count", "weighted_help_vs_actual_pct_sum"])}

## 正贡献 Top10

{_format_table(top_positive, ["leg_id", "entry_year", "product_vt_symbol", "direction", "weighted_delta", "delta_pct", "sim_pnl_pct_a", "sim_pnl_pct_d", "d_stop_tier", "sim_exit_date_a", "sim_exit_date_d"], 10)}

## 负贡献 Top10

{_format_table(top_negative, ["leg_id", "entry_year", "product_vt_symbol", "direction", "weighted_delta", "delta_pct", "sim_pnl_pct_a", "sim_pnl_pct_d", "d_stop_tier", "sim_exit_date_a", "sim_exit_date_d"], 10)}

## 结论

- 若 Stage276 通过，D 只能先冻结为研究候选，不自动替换 Stage78-1 实盘/影子盘参数。
- 若后续要进入正式，需要单独创建 Stage78-2 候选配置，并重新跑影子盘 SOP。

## 输出文件

- leg_delta：`{paths["leg_delta"].name}`
- by_year：`{paths["by_year"].name}`
- by_product：`{paths["by_product"].name}`
- by_tier：`{paths["by_tier"].name}`
- top_positive：`{paths["top_positive"].name}`
- top_negative：`{paths["top_negative"].name}`
- decision：`{paths["decision"].name}`
"""
    paths["report"].write_text(report, encoding="utf-8")


def main() -> None:
    detail = _read_csv(STAGE273_DETAIL)
    candidate_summary = _read_csv(STAGE273_CANDIDATE_SUMMARY)
    tier_effectiveness = _read_csv(STAGE273_TIER_EFFECTIVENESS)
    stage275_decision = json.loads(STAGE275_DECISION.read_text(encoding="utf-8"))
    start_comparison = _read_csv(STAGE275_START_COMPARISON)
    horizon_comparison = _read_csv(STAGE275_HORIZON_COMPARISON)
    slippage_comparison = _read_csv(STAGE275_SLIPPAGE_COMPARISON)

    leg_delta = _build_leg_delta(detail)
    by_year = _aggregate(leg_delta, ["entry_year"])
    by_product = _aggregate(leg_delta, ["product_vt_symbol"])
    by_tier = _aggregate(leg_delta, ["d_stop_tier"])
    concentration = _concentration(leg_delta)
    top_positive = leg_delta.sort_values("weighted_delta", ascending=False).head(30)
    top_negative = leg_delta.sort_values("weighted_delta", ascending=True).head(30)
    decision = _decision(
        stage275_decision=stage275_decision,
        concentration=concentration,
        by_year=by_year,
        by_product=by_product,
        start_comparison=start_comparison,
        horizon_comparison=horizon_comparison,
        slippage_comparison=slippage_comparison,
    )

    paths = {
        "leg_delta": OUTPUT_DIR / f"{OUTPUT_PREFIX}_leg_delta_{MODEL_TAG}.csv",
        "by_year": OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_year_{MODEL_TAG}.csv",
        "by_product": OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_product_{MODEL_TAG}.csv",
        "by_tier": OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_tier_{MODEL_TAG}.csv",
        "top_positive": OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_positive_{MODEL_TAG}.csv",
        "top_negative": OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_negative_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
    }
    leg_delta.to_csv(paths["leg_delta"], index=False, encoding="utf-8-sig")
    by_year.to_csv(paths["by_year"], index=False, encoding="utf-8-sig")
    by_product.to_csv(paths["by_product"], index=False, encoding="utf-8-sig")
    by_tier.to_csv(paths["by_tier"], index=False, encoding="utf-8-sig")
    top_positive.to_csv(paths["top_positive"], index=False, encoding="utf-8-sig")
    top_negative.to_csv(paths["top_negative"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(
        candidate_summary=candidate_summary,
        tier_effectiveness=tier_effectiveness,
        concentration=concentration,
        by_year=by_year,
        by_product=by_product,
        by_tier=by_tier,
        top_positive=top_positive,
        top_negative=top_negative,
        decision=decision,
        paths=paths,
    )

    print(json.dumps(decision, ensure_ascii=False, indent=2))
    print(f"report: {paths['report']}")


if __name__ == "__main__":
    main()
