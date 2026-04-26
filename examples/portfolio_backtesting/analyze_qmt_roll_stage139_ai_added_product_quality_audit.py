from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_ai_product_suitability_full_market_walkforward import PREDICTIONS_OUTPUT_PATH


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage139_ai_added_product_quality_audit_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage139_ai_added_product_quality_audit"

TRANSITION_EVENTS_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_stage136_ai_pool_switch_stability_transition_events_stage136_ai_pool_switch_stability_v1.csv"
)
SIGNAL_PERIOD_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_stage136_ai_pool_switch_stability_signal_period_summary_stage136_ai_pool_switch_stability_v1.csv"
)
STAGE78_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

ENRICHED_EVENTS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_enriched_events_{MODEL_TAG}.csv"
TRANSITION_TYPE_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_transition_type_summary_{MODEL_TAG}.csv"
ADDED_BUCKET_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_added_bucket_summary_{MODEL_TAG}.csv"
ADDED_PRODUCT_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_added_product_summary_{MODEL_TAG}.csv"
ADDED_SIGNAL_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_added_signal_summary_{MODEL_TAG}.csv"
ADDED_TAIL_EVENTS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_added_tail_events_{MODEL_TAG}.csv"
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


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 25) -> str:
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


def _rank_bucket(rank: float) -> str:
    if rank <= 0:
        return "no_current_rank"
    if rank <= 3:
        return "rank_1_3"
    if rank <= 6:
        return "rank_4_6"
    return "rank_7_9"


def _candidate_bucket(candidate_count: float) -> str:
    if candidate_count <= 0:
        return "no_candidate"
    if candidate_count == 1:
        return "one_candidate"
    return "two_plus_candidates"


def _opened_bucket(opened_count: float) -> str:
    return "opened" if opened_count > 0 else "not_opened"


def _pnl_bucket(pnl: float) -> str:
    if pnl > 0:
        return "positive"
    if pnl < 0:
        return "negative"
    return "zero"


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    for path in (TRANSITION_EVENTS_PATH, SIGNAL_PERIOD_PATH, PREDICTIONS_OUTPUT_PATH, STAGE78_SUMMARY_PATH):
        _require(path)

    events = pd.read_csv(TRANSITION_EVENTS_PATH, encoding="utf-8-sig")
    periods = pd.read_csv(SIGNAL_PERIOD_PATH, encoding="utf-8-sig")
    predictions = pd.read_csv(PREDICTIONS_OUTPUT_PATH, encoding="utf-8-sig")
    summary = json.loads(STAGE78_SUMMARY_PATH.read_text(encoding="utf-8"))

    for frame, date_columns in (
        (events, ["signal_date", "next_signal_date", "previous_signal_date"]),
        (periods, ["signal_date", "next_signal_date", "previous_signal_date"]),
        (predictions, ["eval_date"]),
    ):
        for column in date_columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None).dt.normalize()

    event_numeric = [
        "current_rank",
        "previous_rank",
        "current_score",
        "period_product_net_pnl",
        "period_product_trade_count",
        "period_product_slippage",
        "candidate_count",
        "opened_count",
        "ai_blocked_count",
        "median_selected_volume",
    ]
    for column in event_numeric:
        events[column] = pd.to_numeric(events.get(column, 0.0), errors="coerce").fillna(0.0)

    period_numeric = [
        "period_net_pnl",
        "period_trade_count",
        "period_slippage",
        "added_product_net_pnl",
        "retained_product_net_pnl",
        "dropped_product_net_pnl",
        "added_count",
        "retained_count",
        "dropped_count",
    ]
    for column in period_numeric:
        periods[column] = pd.to_numeric(periods.get(column, 0.0), errors="coerce").fillna(0.0)

    prediction_numeric = [
        "predicted_product_suitability_probability",
        "future_net_pnl_60d",
        "future_rank_centered_60d",
        "market_trend_efficiency_60d",
        "market_realized_vol_60d",
        "market_range_pct_mean_60d",
        "market_volume_ratio_60d",
    ]
    for column in prediction_numeric:
        predictions[column] = pd.to_numeric(predictions.get(column, 0.0), errors="coerce").fillna(0.0)

    return events, periods, predictions, summary


def enrich_events(events: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    pred_columns = [
        "eval_date",
        "product_vt_symbol",
        "predicted_product_suitability_probability",
        "future_net_pnl_60d",
        "future_rank_centered_60d",
        "market_trend_efficiency_60d",
        "market_realized_vol_60d",
        "market_range_pct_mean_60d",
        "market_volume_ratio_60d",
    ]
    enriched = events.merge(
        predictions[pred_columns],
        left_on=["signal_date", "product_vt_symbol"],
        right_on=["eval_date", "product_vt_symbol"],
        how="left",
    )
    for column in pred_columns[2:]:
        enriched[column] = pd.to_numeric(enriched.get(column, 0.0), errors="coerce").fillna(0.0)
    enriched["rank_bucket"] = enriched["current_rank"].map(_rank_bucket)
    enriched["candidate_bucket"] = enriched["candidate_count"].map(_candidate_bucket)
    enriched["opened_bucket"] = enriched["opened_count"].map(_opened_bucket)
    enriched["pnl_bucket"] = enriched["period_product_net_pnl"].map(_pnl_bucket)
    enriched["score_type_bucket"] = np.where(
        enriched["current_score_type"].astype(str).str.contains("fixed", case=False, na=False),
        "fixed_satellite",
        "ai_probability",
    )
    enriched["steady_event"] = ~enriched["is_static_to_ai_boundary"].astype(bool)
    return enriched.sort_values(["signal_date", "transition_type", "product_vt_symbol"]).reset_index(drop=True)


def summarize_group(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    grouped = (
        df.groupby(by, dropna=False, as_index=False)
        .agg(
            event_count=("product_vt_symbol", "count"),
            product_count=("product_vt_symbol", "nunique"),
            total_product_net_pnl=("period_product_net_pnl", "sum"),
            mean_product_net_pnl=("period_product_net_pnl", "mean"),
            median_product_net_pnl=("period_product_net_pnl", "median"),
            positive_event_rate_pct=("period_product_net_pnl", lambda s: float((s > 0).mean() * 100.0)),
            zero_event_rate_pct=("period_product_net_pnl", lambda s: float((s == 0).mean() * 100.0)),
            negative_event_rate_pct=("period_product_net_pnl", lambda s: float((s < 0).mean() * 100.0)),
            opened_rate_pct=("opened_count", lambda s: float((s > 0).mean() * 100.0)),
            total_trade_count=("period_product_trade_count", "sum"),
            total_slippage=("period_product_slippage", "sum"),
            total_candidate_count=("candidate_count", "sum"),
            total_opened_count=("opened_count", "sum"),
            mean_current_rank=("current_rank", "mean"),
            mean_current_score=("current_score", "mean"),
            mean_future_rank_centered_60d=("future_rank_centered_60d", "mean"),
            mean_market_trend_efficiency_60d=("market_trend_efficiency_60d", "mean"),
            mean_market_realized_vol_60d=("market_realized_vol_60d", "mean"),
        )
        .sort_values("total_product_net_pnl", ascending=False)
    )
    return grouped.reset_index(drop=True)


def build_added_signal_summary(added_events: pd.DataFrame, periods: pd.DataFrame) -> pd.DataFrame:
    event_group = (
        added_events.groupby("signal_date", as_index=False)
        .agg(
            audited_added_count=("product_vt_symbol", "count"),
            audited_added_net_pnl=("period_product_net_pnl", "sum"),
            audited_added_opened_count=("opened_count", "sum"),
            audited_added_trade_count=("period_product_trade_count", "sum"),
            audited_added_slippage=("period_product_slippage", "sum"),
            audited_added_products=("product_vt_symbol", lambda s: ",".join(map(str, s))),
        )
    )
    merged = periods.merge(event_group, on="signal_date", how="left")
    for column in [
        "audited_added_count",
        "audited_added_net_pnl",
        "audited_added_opened_count",
        "audited_added_trade_count",
        "audited_added_slippage",
    ]:
        merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
    merged["audited_added_products"] = merged["audited_added_products"].fillna("")
    merged = merged[~merged["is_static_to_ai_boundary"].astype(bool)].copy()
    return merged.sort_values("audited_added_net_pnl", ascending=False).reset_index(drop=True)


def build_tail_events(added_events: pd.DataFrame) -> pd.DataFrame:
    worst = added_events.sort_values("period_product_net_pnl").head(15).copy()
    best = added_events.sort_values("period_product_net_pnl", ascending=False).head(15).copy()
    worst["tail_side"] = "worst"
    best["tail_side"] = "best"
    return pd.concat([best, worst], ignore_index=True)


def build_concentration(product_summary: pd.DataFrame) -> dict[str, Any]:
    total_pnl = _safe_float(product_summary["total_product_net_pnl"].sum()) if not product_summary.empty else 0.0
    positive = product_summary[product_summary["total_product_net_pnl"] > 0].sort_values(
        "total_product_net_pnl", ascending=False
    )
    top1 = _safe_float(positive["total_product_net_pnl"].iloc[0]) if not positive.empty else 0.0
    top3 = _safe_float(positive["total_product_net_pnl"].head(3).sum()) if not positive.empty else 0.0
    return {
        "total_added_net_pnl": total_pnl,
        "positive_product_count": int(len(positive)),
        "top1_positive_product": str(positive["product_vt_symbol"].iloc[0]) if not positive.empty else "",
        "top1_positive_product_pnl": top1,
        "top1_share_of_total_pnl_pct": float(top1 / total_pnl * 100.0) if total_pnl else 0.0,
        "top3_share_of_total_pnl_pct": float(top3 / total_pnl * 100.0) if total_pnl else 0.0,
    }


def build_verdict(added_summary: dict[str, Any], concentration: dict[str, Any]) -> str:
    total = _safe_float(added_summary["total_product_net_pnl"])
    positive_rate = _safe_float(added_summary["positive_event_rate_pct"])
    top1_share = _safe_float(concentration["top1_share_of_total_pnl_pct"])
    if total <= 0:
        return "STOP_ADDED_QUALITY_LINE_NO_EDGE"
    if top1_share >= 50.0 or positive_rate < 30.0:
        return "VALUABLE_BUT_CONCENTRATED_SHADOW_ONLY"
    return "BROAD_ADDED_EDGE_CONTINUE_AUDIT_ONLY"


def build_report(payload: dict[str, Any]) -> str:
    metrics = payload["stage78_metrics"]
    transition_type_summary = pd.DataFrame(payload["transition_type_summary"])
    bucket_summary = pd.DataFrame(payload["added_bucket_summary"])
    product_summary = pd.DataFrame(payload["added_product_summary"])
    signal_summary = pd.DataFrame(payload["added_signal_summary"])
    tail_events = pd.DataFrame(payload["added_tail_events"])

    return "\n".join(
        [
            f"# {MODEL_TAG}",
            "",
            "## 边界",
            "",
            "- 本阶段只审计Stage78月度AI池的新增品种质量，不修改正式策略。",
            "- 分组只使用运行前可见字段：新增/保留/剔除、当前排名、是否真实开仓、候选数、成交量。",
            "- 本阶段不提出阈值，不做A/B接入，不触发正式版本实验流程。",
            "",
            "## 结论",
            "",
            f"- 判定：`{payload['verdict']}`。",
            f"- 新增品种稳态总贡献：`{_fmt(payload['added_summary']['total_product_net_pnl'])}`。",
            f"- 新增事件正收益率：`{payload['added_summary']['positive_event_rate_pct']:.4f}%`。",
            f"- 第一大正贡献品种：`{payload['concentration']['top1_positive_product']}`，贡献占比`{payload['concentration']['top1_share_of_total_pnl_pct']:.4f}%`。",
            "- 结论含义：AI新增方向有贡献，但集中度偏高，不能直接转成新增品种过滤规则。",
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
            "## 切换类型对照",
            "",
            _to_markdown_table(
                transition_type_summary,
                [
                    "transition_type",
                    "event_count",
                    "product_count",
                    "total_product_net_pnl",
                    "positive_event_rate_pct",
                    "opened_rate_pct",
                    "total_trade_count",
                    "total_slippage",
                ],
            ),
            "",
            "## 新增品种分组审计",
            "",
            _to_markdown_table(
                bucket_summary,
                [
                    "audit_dimension",
                    "bucket",
                    "event_count",
                    "total_product_net_pnl",
                    "positive_event_rate_pct",
                    "opened_rate_pct",
                    "mean_current_rank",
                    "mean_current_score",
                ],
                max_rows=40,
            ),
            "",
            "## 新增品种贡献排行",
            "",
            _to_markdown_table(
                product_summary,
                [
                    "product_vt_symbol",
                    "event_count",
                    "total_product_net_pnl",
                    "positive_event_rate_pct",
                    "opened_rate_pct",
                    "mean_current_rank",
                    "total_trade_count",
                    "total_slippage",
                ],
                max_rows=30,
            ),
            "",
            "## 新增信号期排行",
            "",
            _to_markdown_table(
                signal_summary,
                [
                    "signal_date",
                    "added_count",
                    "audited_added_net_pnl",
                    "period_net_pnl",
                    "retained_product_net_pnl",
                    "dropped_product_net_pnl",
                    "audited_added_products",
                ],
                max_rows=20,
            ),
            "",
            "## 新增尾部事件",
            "",
            _to_markdown_table(
                tail_events,
                [
                    "tail_side",
                    "signal_date",
                    "product_vt_symbol",
                    "period_product_net_pnl",
                    "current_rank",
                    "current_score",
                    "candidate_count",
                    "opened_count",
                    "period_product_trade_count",
                ],
                max_rows=30,
            ),
            "",
            "## 判断",
            "",
            "- Stage136说“新增品种贡献大”是成立的，但Stage139显示新增贡献并不均匀。",
            "- 新增品种更像趋势地形变化的响应器，不是稳定的逐事件胜率模型。",
            "- 当前不能做新增品种阈值过滤，否则大概率会把少数大趋势行情拟合成规则。",
            "- 后续若继续AI方向，应做新增品种影子预警/归因看板，而不是直接接正式策略。",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events, periods, predictions, summary_payload = read_inputs()
    enriched = enrich_events(events, predictions)
    steady = enriched[enriched["steady_event"]].copy()
    added = steady[steady["transition_type"].eq("added")].copy()

    transition_type_summary = summarize_group(steady, ["transition_type"])
    product_summary = summarize_group(added, ["product_vt_symbol"])

    bucket_frames: list[pd.DataFrame] = []
    for column in ["rank_bucket", "candidate_bucket", "opened_bucket", "pnl_bucket", "score_type_bucket"]:
        frame = summarize_group(added, [column]).rename(columns={column: "bucket"})
        frame.insert(0, "audit_dimension", column)
        bucket_frames.append(frame)
    bucket_summary = pd.concat(bucket_frames, ignore_index=True)
    signal_summary = build_added_signal_summary(added, periods)
    tail_events = build_tail_events(added)

    added_summary_row = summarize_group(added, ["transition_type"]).iloc[0].to_dict() if not added.empty else {}
    concentration = build_concentration(product_summary)
    verdict = build_verdict(added_summary_row, concentration)

    stage78_metrics = dict(summary_payload["reference_metrics"]["full_2020_2026"])
    stage78_metrics["win_ratio_pct"] = summary_payload["experiments"][0].get("win_ratio_pct", 0.0)

    enriched.to_csv(ENRICHED_EVENTS_PATH, index=False, encoding="utf-8-sig")
    transition_type_summary.to_csv(TRANSITION_TYPE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(ADDED_BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(ADDED_PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    signal_summary.to_csv(ADDED_SIGNAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    tail_events.to_csv(ADDED_TAIL_EVENTS_PATH, index=False, encoding="utf-8-sig")

    payload: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "analysis_type": "ai_added_product_quality_audit_no_strategy_change",
        "verdict": verdict,
        "base_version": summary_payload.get("official_version", "official_stage78_defensive_v1"),
        "stage78_metrics": stage78_metrics,
        "added_summary": added_summary_row,
        "concentration": concentration,
        "transition_type_summary": transition_type_summary.to_dict(orient="records"),
        "added_bucket_summary": bucket_summary.to_dict(orient="records"),
        "added_product_summary": product_summary.to_dict(orient="records"),
        "added_signal_summary": signal_summary.to_dict(orient="records"),
        "added_tail_events": tail_events.to_dict(orient="records"),
        "parameters": {
            "exclude_static_to_ai_boundary": True,
            "rank_buckets": ["rank_1_3", "rank_4_6", "rank_7_9"],
            "candidate_buckets": ["no_candidate", "one_candidate", "two_plus_candidates"],
            "opened_buckets": ["opened", "not_opened"],
            "note": "diagnostic buckets only; not formal strategy thresholds",
        },
        "artifacts": {
            "enriched_events": str(ENRICHED_EVENTS_PATH),
            "transition_type_summary": str(TRANSITION_TYPE_SUMMARY_PATH),
            "added_bucket_summary": str(ADDED_BUCKET_SUMMARY_PATH),
            "added_product_summary": str(ADDED_PRODUCT_SUMMARY_PATH),
            "added_signal_summary": str(ADDED_SIGNAL_SUMMARY_PATH),
            "added_tail_events": str(ADDED_TAIL_EVENTS_PATH),
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
                "added_total_net_pnl": added_summary_row.get("total_product_net_pnl", 0.0),
                "top1_positive_product": concentration["top1_positive_product"],
                "top1_share_of_total_pnl_pct": concentration["top1_share_of_total_pnl_pct"],
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
