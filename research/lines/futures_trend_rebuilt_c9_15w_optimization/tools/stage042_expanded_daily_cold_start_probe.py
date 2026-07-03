from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage013_account_state_pilot_gate_engine as s013
import stage039_full_market_ai_top8_proxy as s039
import stage041_selected_daily_cold_start_probe as s041


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage042"
MODEL_TAG = "stage042_expanded_daily_cold_start_probe_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage042_expanded_daily_cold_start_probe"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage042_expanded_daily_cold_start_probe"
STAGES_DIR = LINE_DIR / "stages"

STAGE040_OUTPUT_DIR = LINE_DIR / "outputs" / "stage040_stage039_negative_window_delta_attribution"
STAGE040_PREFIX = "rebuilt_c9_stage040_stage039_negative_window_delta_attribution"
STAGE040_TAG = "stage040_stage039_negative_window_delta_attribution_v1"
STAGE040_TOP_WINDOWS_PATH = STAGE040_OUTPUT_DIR / f"{STAGE040_PREFIX}_top_windows_{STAGE040_TAG}.csv"

REQUESTED_END = pd.Timestamp("2026-06-30")
CAPITAL = 150000.0
ADD_RISK_FRACTION = 0.25
BUCKET_QUOTAS = {
    "both_negative": 16,
    "added_negative_absolute_worse": 6,
    "added_negative_denominator": 4,
    "fixed_by_stage039": 6,
}

PROBE_STARTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_starts_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s041._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s041._md_table(frame, max_rows=max_rows)


def _date_key(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _bucket_frames(top_windows: pd.DataFrame) -> dict[str, pd.DataFrame]:
    data = top_windows.copy()
    data["start_date"] = pd.to_datetime(data["start_date"], errors="coerce").dt.normalize()
    data["stage039_return_pct"] = pd.to_numeric(data["stage039_return_pct"], errors="coerce")
    data["stage013_return_pct"] = pd.to_numeric(data["stage013_return_pct"], errors="coerce")
    data["stage039_absolute_end_ge_stage013"] = pd.to_numeric(
        data.get("stage039_absolute_end_ge_stage013", 0), errors="coerce"
    ).fillna(0)
    data = data.dropna(subset=["start_date", "stage039_return_pct", "stage013_return_pct"])
    added = data[data["window_class"].eq("added_negative_by_stage039")]
    return {
        "both_negative": data[data["window_class"].eq("both_negative")].sort_values("stage039_return_pct"),
        "added_negative_absolute_worse": added[added["stage039_absolute_end_ge_stage013"].eq(0)].sort_values(
            "stage039_return_pct"
        ),
        "added_negative_denominator": added[added["stage039_absolute_end_ge_stage013"].eq(1)].sort_values(
            "stage039_return_pct"
        ),
        "fixed_by_stage039": data[data["window_class"].eq("fixed_by_stage039")].sort_values("stage013_return_pct"),
    }


def _append_unique_starts(
    rows: list[dict[str, Any]],
    seen: set[str],
    frame: pd.DataFrame,
    bucket: str,
    quota: int,
) -> None:
    added = 0
    for _, row in frame.iterrows():
        key = _date_key(row["start_date"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "probe_rank": len(rows) + 1,
                "requested_start": key,
                "probe_bucket": bucket,
                "source_window_class": str(row.get("window_class", "")),
                "source_stage039_return_pct": float(row.get("stage039_return_pct", np.nan)),
                "source_stage013_return_pct": float(row.get("stage013_return_pct", np.nan)),
                "source_stage039_absolute_end_ge_stage013": int(row.get("stage039_absolute_end_ge_stage013", 0) or 0),
            }
        )
        added += 1
        if added >= quota:
            return


def _select_expanded_probe_start_dates(
    top_windows: pd.DataFrame,
    bucket_quotas: dict[str, int] = BUCKET_QUOTAS,
) -> pd.DataFrame:
    buckets = _bucket_frames(top_windows)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for bucket, quota in bucket_quotas.items():
        _append_unique_starts(rows, seen, buckets.get(bucket, pd.DataFrame()), bucket, int(quota))
    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(
            columns=[
                "probe_rank",
                "requested_start",
                "probe_bucket",
                "source_window_class",
                "source_stage039_return_pct",
                "source_stage013_return_pct",
                "source_stage039_absolute_end_ge_stage013",
            ]
        )
    result["probe_rank"] = np.arange(1, len(result) + 1)
    return result


def _prepare_curve_frame(curve: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    result = s041._prepare_curve_frame(curve, start)
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    return result


def _aggregate_probe_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    def numeric(group: pd.DataFrame, column: str) -> pd.Series:
        if column not in group.columns:
            return pd.Series(dtype=float)
        return pd.to_numeric(group[column], errors="coerce")

    rows: list[dict[str, Any]] = []
    for variant, group in summary.groupby("variant", sort=True):
        negative = numeric(group, "negative_count").fillna(0).gt(0)
        rows.append(
            {
                "variant": variant,
                "probe_start_count": int(group["requested_start"].nunique()),
                "negative_probe_start_count": int(negative.sum()),
                "window_count": int(numeric(group, "window_count").fillna(0).sum()),
                "negative_count": int(numeric(group, "negative_count").fillna(0).sum()),
                "min_return_pct": float(numeric(group, "min_return_pct").min()),
                "to_final_min_return_pct": float(numeric(group, "to_final_return_pct").min()),
                "end_equity_min": float(numeric(group, "end_equity").min()),
                "max_dd_min_pct": float(numeric(group, "max_dd_pct").min()),
                "sharpe_median": float(numeric(group, "sharpe").median()),
            }
        )
    return pd.DataFrame(rows)


def _run_probe() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    top_windows = pd.read_csv(STAGE040_TOP_WINDOWS_PATH, encoding="utf-8-sig")
    probe_starts = _select_expanded_probe_start_dates(top_windows)
    if probe_starts.empty:
        raise ValueError("no probe starts selected")
    metadata = s013.s901.s513._metadata()
    predictions = pd.read_csv(s039.PREDICTIONS_PATH, encoding="utf-8-sig", parse_dates=["eval_date"])
    curve_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    lot_delta_frames: list[pd.DataFrame] = []
    for idx, row in probe_starts.iterrows():
        start = pd.Timestamp(row["requested_start"]).normalize()
        print(
            f"[stage042] running daily cold start {idx + 1}/{len(probe_starts)} "
            f"start={_date_key(start)} bucket={row['probe_bucket']}",
            flush=True,
        )
        combined, frames, _spec = s013._run_live_stage013(metadata, start, REQUESTED_END)
        base_curve = _prepare_curve_frame(combined, start)
        closed = s041._closed_lots_from_frames(frames, metadata, start)
        lot_deltas = s041._stage039_lot_deltas(closed, predictions)
        proxy_curve, unmatched = s039._build_proxy_curves(
            base_curve[["requested_start_month", "date", "account_equity"]].copy(),
            lot_deltas,
        )
        proxy_curve["requested_start"] = _date_key(start)
        proxy_curve["probe_bucket"] = row["probe_bucket"]
        proxy_curve["stage042_unmatched_delta_dates"] = int(unmatched)
        curve_frames.append(proxy_curve)
        if not lot_deltas.empty:
            lot_deltas["requested_start"] = _date_key(start)
            lot_deltas["probe_bucket"] = row["probe_bucket"]
            lot_deltas["stage042_unmatched_delta_dates"] = int(unmatched)
            lot_delta_frames.append(lot_deltas)
        stage013_audit = s041._audit_curve_from_actual_start(
            _date_key(start),
            "stage013_daily_cold_start_engine",
            proxy_curve[["date", "account_equity"]].rename(columns={"account_equity": "equity"}),
        )
        stage042_audit = s041._audit_curve_from_actual_start(
            _date_key(start),
            "stage042_daily_cold_start_stage039_ai_top8_proxy",
            proxy_curve[["date", "stage039_account_equity"]].rename(columns={"stage039_account_equity": "equity"}),
        )
        for audit in (stage013_audit, stage042_audit):
            audit["probe_bucket"] = row["probe_bucket"]
            audit["source_stage039_return_pct"] = row["source_stage039_return_pct"]
            audit["source_stage013_return_pct"] = row["source_stage013_return_pct"]
        summary_rows.extend([stage013_audit, stage042_audit])
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    lot_deltas = pd.concat(lot_delta_frames, ignore_index=True, sort=False) if lot_delta_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    aggregate = _aggregate_probe_summary(summary)
    return probe_starts, summary, aggregate, curves, lot_deltas


def _decision(probe_starts: pd.DataFrame, summary: pd.DataFrame, aggregate: pd.DataFrame, lot_deltas: pd.DataFrame) -> dict[str, Any]:
    def metric(variant: str, column: str, default: Any = np.nan) -> Any:
        rows = aggregate[aggregate["variant"].eq(variant)]
        if rows.empty or column not in rows.columns:
            return default
        return rows.iloc[0][column]

    stage013_negative_starts = int(metric("stage013_daily_cold_start_engine", "negative_probe_start_count", 0))
    stage042_negative_starts = int(metric("stage042_daily_cold_start_stage039_ai_top8_proxy", "negative_probe_start_count", 0))
    probe_count = int(len(probe_starts))
    if stage013_negative_starts == 0 and stage042_negative_starts == 0:
        decision = "stage042_expanded_probe_no_negative_starts_needs_broader_grid"
        continue_after = "有。扩展探针未复现负窗口，但仍不是全量日级证明，需要更宽日级网格。"
    elif stage042_negative_starts < stage013_negative_starts:
        decision = "stage042_ai_top8_proxy_partially_reduces_negative_daily_starts_not_goal"
        continue_after = "有。AI top8 对部分日级起点有缓冲，但未清零，下一步应定位剩余负起点共同状态或账户外层。"
    else:
        decision = "stage042_expanded_probe_confirms_left_tail_persistent_not_ai_top8_solved"
        continue_after = "有。扩展日级样本仍有持续左尾，下一步应转账户外层/真正外生源，或扩大全量日级网格确认分布。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "audit_type": "expanded_exact_daily_cold_start_true_engine_probe_with_stage039_closed_lot_proxy",
        "probe_start_count": probe_count,
        "probe_bucket_counts": probe_starts["probe_bucket"].value_counts().sort_index().to_dict(),
        "stage013_negative_probe_start_count": stage013_negative_starts,
        "stage042_negative_probe_start_count": stage042_negative_starts,
        "stage013_min_return_pct": float(metric("stage013_daily_cold_start_engine", "min_return_pct")),
        "stage042_min_return_pct": float(metric("stage042_daily_cold_start_stage039_ai_top8_proxy", "min_return_pct")),
        "stage013_to_final_min_return_pct": float(metric("stage013_daily_cold_start_engine", "to_final_min_return_pct")),
        "stage042_to_final_min_return_pct": float(
            metric("stage042_daily_cold_start_stage039_ai_top8_proxy", "to_final_min_return_pct")
        ),
        "selected_lots": int(len(lot_deltas)),
        "selected_realized_pnl": float(pd.to_numeric(lot_deltas.get("realized_pnl", pd.Series(dtype=float)), errors="coerce").sum())
        if not lot_deltas.empty
        else 0.0,
        "stage042_proxy_delta_pnl": float(
            pd.to_numeric(lot_deltas.get("stage039_proxy_delta_pnl", pd.Series(dtype=float)), errors="coerce").sum()
        )
        if not lot_deltas.empty
        else 0.0,
        "strategy_changed": False,
        "true_engine": True,
        "proxy_overlay": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Managed futures / trend-following literature commonly emphasizes target volatility, drawdown duration, "
            "correlation/volatility regimes and portfolio-level risk budgeting. Stage042 therefore expands true daily "
            "cold-start evidence instead of optimizing a new date/product/topN rule."
        ),
        "overfit_reflection_before": (
            "否。Stage042 是分层扩展探针，不新增交易规则、不按结果改参数；风险在于样本仍来自失败窗口，因此只能用于诊断。"
        ),
        "overfit_reflection_after": (
            "否。本阶段只扩大真实日级冷启动证据；若据此写日期、品种、方向或 topN 过滤才会过拟合。"
        ),
        "continue_value_before": "有。用户目标是任意日级起点，必须从少量探针扩展到更宽样本。",
        "continue_value_after": continue_after,
        "outputs": {
            "probe_starts": str(PROBE_STARTS_PATH),
            "summary": str(SUMMARY_PATH),
            "aggregate": str(AGGREGATE_PATH),
            "curves": str(CURVES_PATH),
            "lot_deltas": str(LOT_DELTAS_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    probe_starts: pd.DataFrame,
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    lot_deltas: pd.DataFrame,
) -> None:
    lines = [
        "# Stage042 - 扩展独立日级冷启动探针",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：分层选定日期真实 Stage013 引擎冷启动 + Stage039 closed-lot proxy；不改 C9，不连接 CTP，不调用下单。",
        "",
        "## 核心结果",
        "",
        f"- 探针起点数：`{decision['probe_start_count']}`；bucket 分布 `{decision['probe_bucket_counts']}`。",
        f"- Stage013 有负结束日的探针起点：`{decision['stage013_negative_probe_start_count']}`。",
        f"- Stage042 proxy 有负结束日的探针起点：`{decision['stage042_negative_probe_start_count']}`。",
        f"- Stage013 探针最差收益：`{decision['stage013_min_return_pct']:.4f}%`；到 2026-06-30 最差 `{decision['stage013_to_final_min_return_pct']:.4f}%`。",
        f"- Stage042 proxy 探针最差收益：`{decision['stage042_min_return_pct']:.4f}%`；到 2026-06-30 最差 `{decision['stage042_to_final_min_return_pct']:.4f}%`。",
        f"- Stage042 选中 lots：`{decision['selected_lots']}`；proxy delta `{decision['stage042_proxy_delta_pnl']:,.2f}`。",
        "",
        "## 探针起点",
        "",
        _md_table(probe_starts, max_rows=60),
        "",
        "## 聚合审计",
        "",
        _md_table(aggregate, max_rows=20),
        "",
        "## 探针审计",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## lot delta 摘要",
        "",
        _md_table(
            lot_deltas[
                [
                    "requested_start",
                    "probe_bucket",
                    "product",
                    "direction",
                    "entry_date",
                    "exit_date",
                    "realized_pnl",
                    "stage039_proxy_delta_pnl",
                ]
            ]
            if not lot_deltas.empty
            else lot_deltas,
            max_rows=40,
        ),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], probe_starts: pd.DataFrame, aggregate: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage042_expanded_daily_cold_start_probe.md"
    lines = [
        "# Stage042 - 扩展独立日级冷启动探针",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage042_expanded_daily_cold_start_probe.py`",
        f"- 新增参数：分层探针 quota `{BUCKET_QUOTAS}`；不新增交易参数。",
        "- 修改参数：无，Stage013/Stage039/官方 C9 配置未改。",
        "- 删除参数：无。",
        "- 新增回测结果：扩展日级冷启动真引擎探针 + Stage039 top8 closed-lot proxy。",
        "- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## 结果",
        "",
        f"- 探针起点数：`{decision['probe_start_count']}`。",
        f"- bucket 分布：`{decision['probe_bucket_counts']}`。",
        f"- Stage013 有负结束日的探针起点：`{decision['stage013_negative_probe_start_count']}`。",
        f"- Stage042 proxy 有负结束日的探针起点：`{decision['stage042_negative_probe_start_count']}`。",
        f"- Stage013 探针最差收益：`{decision['stage013_min_return_pct']:.4f}%`。",
        f"- Stage042 proxy 探针最差收益：`{decision['stage042_min_return_pct']:.4f}%`。",
        f"- Stage042 proxy delta：`{decision['stage042_proxy_delta_pnl']:,.2f}`。",
        "",
        "## 探针起点",
        "",
        _md_table(probe_starts, max_rows=60),
        "",
        "## 聚合审计",
        "",
        _md_table(aggregate, max_rows=20),
        "",
        "## 输出",
        "",
        f"- probe_starts：`{PROBE_STARTS_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- aggregate：`{AGGREGATE_PATH}`",
        f"- curves：`{CURVES_PATH}`",
        f"- lot_deltas：`{LOT_DELTAS_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    probe_starts, summary, aggregate, curves, lot_deltas = _run_probe()
    decision = _decision(probe_starts, summary, aggregate, lot_deltas)
    probe_starts.to_csv(PROBE_STARTS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, probe_starts, summary, aggregate, lot_deltas)
    stage_record = _write_stage_record(decision, probe_starts, aggregate)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
