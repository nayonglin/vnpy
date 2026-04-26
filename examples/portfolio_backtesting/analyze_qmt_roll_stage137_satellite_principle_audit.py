from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage137_satellite_principle_audit_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage137_satellite_principle_audit"

STRUCTURAL_AUDIT_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_structural_prefilter_audit_full_market_structural_prefilter_v1.csv"
)
SUITABILITY_PREDICTIONS_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_full_market_walkforward_predictions_product_suitability_full_market_wf_v1.csv"
)
STAGE78_PRODUCT_ATTRIBUTION_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage127_stage78_profit_drawdown_attribution_full_product_attribution_stage127_stage78_profit_drawdown_attribution_v1.csv"
)
STAGE136_PRODUCT_TRANSITION_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_stage136_ai_pool_switch_stability_product_transition_summary_stage136_ai_pool_switch_stability_v1.csv"
)
SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

STRUCTURAL_RANK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_name_blind_structural_rank_{MODEL_TAG}.csv"
PRODUCT_EVIDENCE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_evidence_{MODEL_TAG}.csv"
SATELLITE_CANDIDATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_candidates_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _build_name_blind_structural_rank(audit: pd.DataFrame) -> pd.DataFrame:
    frame = audit[(audit["is_static_strategy_product"] == 0) & (audit["eligible"] == 1)].copy()
    numeric_columns = [
        "recent_median_volume",
        "estimated_margin_per_contract",
        "market_trend_efficiency_60d_median",
        "market_realized_vol_60d_median",
        "market_range_pct_mean_60d_median",
        "recent_bar_coverage_ratio",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)

    high_is_good = [
        "recent_median_volume",
        "market_trend_efficiency_60d_median",
        "market_realized_vol_60d_median",
        "market_range_pct_mean_60d_median",
        "recent_bar_coverage_ratio",
    ]
    low_is_good = ["estimated_margin_per_contract"]
    for column in high_is_good:
        frame[f"{column}_rank_pct"] = frame[column].rank(pct=True, method="average")
    for column in low_is_good:
        frame[f"{column}_rank_pct"] = (-frame[column]).rank(pct=True, method="average")

    rank_columns = [f"{column}_rank_pct" for column in [*high_is_good, *low_is_good]]
    frame["name_blind_structural_score"] = frame[rank_columns].mean(axis=1)
    frame["name_blind_structural_rank"] = frame["name_blind_structural_score"].rank(
        ascending=False, method="first"
    ).astype(int)
    frame["structural_pass"] = frame["structural_prefilter_kept"].astype(int)
    frame["masked_product_id"] = [f"candidate_{index + 1:02d}" for index in range(len(frame))]
    return frame.sort_values("name_blind_structural_rank").reset_index(drop=True)


def _build_suitability_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    frame = predictions.copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    numeric_columns = [
        "predicted_product_suitability_probability",
        "future_net_pnl_60d",
        "target_future_top_half_60d",
        "future_rank_centered_60d",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["ai_rank"] = frame.groupby("eval_date")["predicted_product_suitability_probability"].rank(
        ascending=False, method="first"
    )
    frame["ai_top5"] = (frame["ai_rank"] <= 5).astype(int)
    summary = (
        frame.groupby("product_vt_symbol", as_index=False)
        .agg(
            suitability_month_count=("eval_date", "count"),
            mean_ai_probability=("predicted_product_suitability_probability", "mean"),
            median_ai_probability=("predicted_product_suitability_probability", "median"),
            ai_top5_frequency_pct=("ai_top5", lambda s: float(s.mean() * 100.0)),
            future_60d_total_net_pnl=("future_net_pnl_60d", "sum"),
            future_60d_mean_net_pnl=("future_net_pnl_60d", "mean"),
            future_60d_top_half_rate_pct=("target_future_top_half_60d", lambda s: float(s.mean() * 100.0)),
            future_60d_mean_rank_centered=("future_rank_centered_60d", "mean"),
        )
        .sort_values("mean_ai_probability", ascending=False)
    )
    summary["mean_ai_probability_rank"] = summary["mean_ai_probability"].rank(ascending=False, method="first").astype(int)
    summary["future_60d_total_net_pnl_rank"] = summary["future_60d_total_net_pnl"].rank(
        ascending=False, method="first"
    ).astype(int)
    return summary


def _build_transition_summary(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["product_vt_symbol", "stage136_total_transition_net_pnl", "stage136_event_count"])
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return pd.DataFrame(columns=["product_vt_symbol", "stage136_total_transition_net_pnl", "stage136_event_count"])
    for column in ["total_product_net_pnl", "event_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return (
        frame.groupby("product_vt_symbol", as_index=False)
        .agg(
            stage136_total_transition_net_pnl=("total_product_net_pnl", "sum"),
            stage136_event_count=("event_count", "sum"),
        )
        .sort_values("stage136_total_transition_net_pnl", ascending=False)
    )


def build_payload() -> dict[str, Any]:
    for path in (STRUCTURAL_AUDIT_PATH, SUITABILITY_PREDICTIONS_PATH, STAGE78_PRODUCT_ATTRIBUTION_PATH, SUMMARY_PATH):
        _require(path)
    audit = _read_csv(STRUCTURAL_AUDIT_PATH)
    predictions = _read_csv(SUITABILITY_PREDICTIONS_PATH)
    product_attr = _read_csv(STAGE78_PRODUCT_ATTRIBUTION_PATH)
    transition = _build_transition_summary(STAGE136_PRODUCT_TRANSITION_PATH)
    summary_payload = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    structural_rank = _build_name_blind_structural_rank(audit)
    suitability = _build_suitability_summary(predictions)
    product_attr = product_attr.rename(
        columns={
            "full_net_pnl": "stage78_full_net_pnl",
            "trade_count": "stage78_trade_count",
            "slippage": "stage78_slippage",
            "active_days": "stage78_active_days",
        }
    )
    evidence = (
        structural_rank.merge(suitability, on="product_vt_symbol", how="left")
        .merge(
            product_attr[
                [
                    "product_vt_symbol",
                    "stage78_full_net_pnl",
                    "stage78_trade_count",
                    "stage78_slippage",
                    "stage78_active_days",
                    "pnl_rank",
                ]
            ],
            on="product_vt_symbol",
            how="left",
        )
        .merge(transition, on="product_vt_symbol", how="left")
    )
    evidence = evidence.fillna(0.0)

    candidates = evidence[evidence["structural_pass"].astype(int).eq(1)].copy()
    satellite_verdict = "PARTIAL_PASS_CANDIDATE_GENERATOR_NOT_TRADE_RULE"
    fu_row = evidence[evidence["product_vt_symbol"].astype(str).eq("fu.SHFE")].iloc[0].to_dict()
    sn_row = evidence[evidence["product_vt_symbol"].astype(str).eq("sn.SHFE")].iloc[0].to_dict()

    structural_rank.to_csv(STRUCTURAL_RANK_PATH, index=False, encoding="utf-8-sig")
    evidence.to_csv(PRODUCT_EVIDENCE_PATH, index=False, encoding="utf-8-sig")
    candidates.to_csv(SATELLITE_CANDIDATE_PATH, index=False, encoding="utf-8-sig")

    official_metrics = dict(summary_payload["reference_metrics"]["full_2020_2026"])
    official_metrics["win_ratio_pct"] = summary_payload["experiments"][0].get("win_ratio_pct", 0.0)

    return {
        "model_tag": MODEL_TAG,
        "analysis_type": "satellite_principle_audit_no_new_backtest",
        "base_version": summary_payload.get("official_version", "official_stage78_defensive_v1"),
        "satellite_verdict": satellite_verdict,
        "official_metrics": official_metrics,
        "fu_evidence": fu_row,
        "sn_evidence": sn_row,
        "structural_candidates": candidates.to_dict(orient="records"),
        "top_name_blind_structural_rank": evidence.sort_values("name_blind_structural_rank").head(15).to_dict(orient="records"),
        "top_future_pnl_among_new_candidates": evidence.sort_values("future_60d_total_net_pnl", ascending=False)
        .head(15)
        .to_dict(orient="records"),
        "artifacts": {
            "structural_rank": str(STRUCTURAL_RANK_PATH),
            "product_evidence": str(PRODUCT_EVIDENCE_PATH),
            "satellite_candidates": str(SATELLITE_CANDIDATE_PATH),
            "summary": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def build_report(payload: dict[str, Any]) -> str:
    metrics = payload["official_metrics"]
    fu = payload["fu_evidence"]
    sn = payload["sn_evidence"]
    candidates = pd.DataFrame(payload["structural_candidates"]).sort_values("name_blind_structural_rank")
    structural_top = pd.DataFrame(payload["top_name_blind_structural_rank"])
    future_top = pd.DataFrame(payload["top_future_pnl_among_new_candidates"])

    return "\n".join(
        [
            f"# {MODEL_TAG}",
            "",
            "## 边界",
            "",
            f"- 基准版本：`{payload['base_version']}`。",
            "- 本阶段不跑新回测，不新增卫星，不修改Stage78。",
            "- 名字无关结构分数只使用流动性、保证金可承受性、趋势效率、波动/区间、数据覆盖度，不使用品种名、不使用未来收益。",
            "- 未来60日收益和Stage78贡献只用于事后审计，不用于生成候选。",
            "",
            "## 结论",
            "",
            f"- 卫星原则判定：`{payload['satellite_verdict']}`。",
            "- 含义：结构卫星原则能作为“候选生成器”，但还不能作为自动交易规则。",
            "- `fu.SHFE`不是纯粹事后指定：在名字无关结构评分里，它在非静态候选中排名第2，能自然进入候选集。",
            "- 但原则并不只选出`fu.SHFE`，也选出`UR/eb/pg/sn`等候选；最终只采用`fu`仍然包含历史经验成分，所以不能继续写`fu`专属补丁。",
            "- 更准确的定位：`fu`是Stage78冻结版里的结构性工程例外，不是一个可无限推广的普适品种规律。",
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
            "## fu证据",
            "",
            f"- 名字无关结构排名：`{int(fu['name_blind_structural_rank'])}`",
            f"- 名字无关结构分数：`{float(fu['name_blind_structural_score']):.4f}`",
            f"- 结构预筛：`{int(fu['structural_pass'])}`",
            f"- 近期中位成交量：`{_fmt(fu['recent_median_volume'])}`",
            f"- 单手估算保证金：`{_fmt(fu['estimated_margin_per_contract'])}`",
            f"- 60日趋势效率中位数：`{float(fu['market_trend_efficiency_60d_median']):.4f}`",
            f"- 60日波动中位数：`{float(fu['market_realized_vol_60d_median']):.4f}`",
            f"- 全市场AI平均概率排名：`{int(fu['mean_ai_probability_rank'])}`",
            f"- AI Top5频率：`{float(fu['ai_top5_frequency_pct']):.2f}%`",
            f"- 未来60日审计总净损益：`{_fmt(fu['future_60d_total_net_pnl'])}`",
            f"- Stage78全周期品种贡献：`{_fmt(fu['stage78_full_net_pnl'])}`",
            f"- Stage136切换归因贡献：`{_fmt(fu['stage136_total_transition_net_pnl'])}`",
            "",
            "## sn对照",
            "",
            f"- 名字无关结构排名：`{int(sn['name_blind_structural_rank'])}`",
            f"- 名字无关结构分数：`{float(sn['name_blind_structural_score']):.4f}`",
            f"- 结构预筛：`{int(sn['structural_pass'])}`",
            f"- 全市场AI平均概率排名：`{int(sn['mean_ai_probability_rank'])}`",
            f"- AI Top5频率：`{float(sn['ai_top5_frequency_pct']):.2f}%`",
            f"- 未来60日审计总净损益：`{_fmt(sn['future_60d_total_net_pnl'])}`",
            f"- Stage78全周期品种贡献：`{_fmt(sn['stage78_full_net_pnl'])}`",
            "",
            "## 名字无关结构候选",
            "",
            _to_markdown_table(
                candidates,
                [
                    "product_vt_symbol",
                    "name_blind_structural_rank",
                    "name_blind_structural_score",
                    "recent_median_volume",
                    "estimated_margin_per_contract",
                    "market_trend_efficiency_60d_median",
                    "market_realized_vol_60d_median",
                    "market_range_pct_mean_60d_median",
                    "future_60d_total_net_pnl",
                    "stage78_full_net_pnl",
                ],
                max_rows=20,
            ),
            "",
            "## 结构分数前15名",
            "",
            _to_markdown_table(
                structural_top,
                [
                    "product_vt_symbol",
                    "structural_pass",
                    "name_blind_structural_rank",
                    "name_blind_structural_score",
                    "structural_prefilter_reject_reason",
                    "future_60d_total_net_pnl",
                    "stage78_full_net_pnl",
                ],
                max_rows=15,
            ),
            "",
            "## 未来收益审计前15名",
            "",
            _to_markdown_table(
                future_top,
                [
                    "product_vt_symbol",
                    "structural_pass",
                    "name_blind_structural_rank",
                    "name_blind_structural_score",
                    "future_60d_total_net_pnl",
                    "mean_ai_probability_rank",
                    "ai_top5_frequency_pct",
                    "stage78_full_net_pnl",
                ],
                max_rows=15,
            ),
            "",
            "## 判断",
            "",
            "- `fu`通过名字无关结构审计，所以它不是完全凭品种名硬塞进去。",
            "- 但卫星原则只能证明“候选池合理”，不能证明“只选fu且给fu特殊风险状态处理”是普适规则。",
            "- 因此Stage78可以继续冻结保留`fu`，但后续不应继续优化`fu`专属逻辑。",
            "- 如果继续卫星方向，必须先做影子审计：用结构候选池观察，不直接交易，不扩大正式池。",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    REPORT_PATH.write_text(build_report(payload), encoding="utf-8")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "analysis_type": payload["analysis_type"],
                "satellite_verdict": payload["satellite_verdict"],
                "fu_structural_rank": int(payload["fu_evidence"]["name_blind_structural_rank"]),
                "fu_structural_score": float(payload["fu_evidence"]["name_blind_structural_score"]),
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
