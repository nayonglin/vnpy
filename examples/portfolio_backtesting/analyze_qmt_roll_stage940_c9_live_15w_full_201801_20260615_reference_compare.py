from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage940"
MODEL_TAG = "stage940_c9_live_15w_full_201801_20260615_reference_compare_v1"
OUTPUT_PREFIX = "qmt_roll_stage940_c9_live_15w_full_201801_20260615_reference_compare"

ANALYSIS_START = pd.Timestamp("2018-01-01")
ANALYSIS_END = pd.Timestamp("2026-06-15")

REFERENCE_METRICS = {
    "source": "back_log_md_repeated_official_A_arm",
    "window": "2018-01-01 -> 2026-06-15",
    "capital": 150000.0,
    "end_equity": 39176437.60,
    "total_return_pct": 26017.6251,
    "max_dd_pct": -45.0827,
    "sharpe": 1.6331,
    "total_slippage": 2730130.0,
    "total_trade_count": 787.0,
    "nonzero_daily_win_rate_pct": 53.2560,
    "max_broker10_margin_to_equity_pct": 111.7365,
    "days_over_100pct": 5.0,
}

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _metrics_for_curve(curve: pd.DataFrame) -> dict[str, Any]:
    spec = s650.CapitalVariant(
        variant=OFFICIAL_LIVE_PROFILE_NAME,
        label=f"{OFFICIAL_LIVE_ALIAS} live15w full reference rerun",
        account_capital=OFFICIAL_LIVE_CAPITAL,
        c3_capital=OFFICIAL_LIVE_CAPITAL,
        risk_multiplier=float(pd.to_numeric(curve.get("risk_multiplier", pd.Series([0.0])), errors="coerce").dropna().iloc[0]),
        product_cap_ratio=0.0,
        max_concurrent_positions=0,
        note="Stage940 reference comparison wrapper; no strategy parameter changes.",
    )
    metrics = s650._metrics(curve, spec, cost_multiplier=1.0)
    metrics["source"] = "stage940_current_rebuilt_rerun"
    metrics["stage"] = STAGE
    metrics["window"] = f"{ANALYSIS_START.date()} -> {ANALYSIS_END.date()}"
    metrics["official_live_version"] = OFFICIAL_LIVE_VERSION
    metrics["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    metrics["ai_pool_path"] = str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)
    return metrics


def _build_comparison(summary: dict[str, Any]) -> pd.DataFrame:
    metrics = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
    ]
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        current = float(summary.get(metric, np.nan))
        reference = float(REFERENCE_METRICS.get(metric, np.nan))
        rows.append(
            {
                "metric": metric,
                "reference": reference,
                "current_rerun": current,
                "delta": current - reference,
                "abs_delta": abs(current - reference),
            }
        )
    return pd.DataFrame(rows)


def _write_report(summary: dict[str, Any], comparison: pd.DataFrame, decision: dict[str, Any]) -> None:
    summary_view = pd.DataFrame([summary])[
        [
            "window",
            "end_equity",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
            "max_broker10_margin_to_equity_pct",
            "days_over_100pct",
        ]
    ]
    lines = [
        "# Stage940 C9 15万全周期旧基准对比",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前实盘版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- AI 池：`{OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        f"- 回测窗口：`{ANALYSIS_START.date()}` -> `{ANALYSIS_END.date()}`，资金 `{OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        "- 对照记录来自 `back_log.md` 多个当前官方 C9/15w 研究 A 臂：同窗口、同资金、同正式版本记录。",
        "- 不连接 CTP，不读取账户，不调用订单 API。",
        "",
        "## 当前复跑",
        "",
        _md_table(summary_view, max_rows=5),
        "",
        "## 与旧基准差异",
        "",
        _md_table(comparison, max_rows=20),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 是否一致：`{decision['consistent_with_reference']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"[stage940] running full reference compare start={ANALYSIS_START.date()} end={ANALYSIS_END.date()} "
        f"live={OFFICIAL_LIVE_VERSION}",
        flush=True,
    )
    metadata = s901.s513._metadata()
    curve, _frames, _spec = s901._run_live_c9(metadata, ANALYSIS_START, ANALYSIS_END)
    curve = curve.copy()
    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    curve["official_live_version"] = OFFICIAL_LIVE_VERSION
    curve["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    curve["analysis_start"] = ANALYSIS_START.date().isoformat()
    curve["analysis_end"] = ANALYSIS_END.date().isoformat()
    curve["ai_pool_path"] = str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)

    summary = _metrics_for_curve(curve)
    comparison = _build_comparison(summary)
    core = comparison[comparison["metric"].isin(["end_equity", "total_return_pct", "max_dd_pct", "sharpe"])]
    consistent = bool((core["abs_delta"] <= np.array([1.0, 0.01, 0.01, 0.0001])).all())
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "capital": OFFICIAL_LIVE_CAPITAL,
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "summary": summary,
        "reference_metrics": REFERENCE_METRICS,
        "comparison": comparison.to_dict(orient="records"),
        "consistent_with_reference": consistent,
        "decision": "stage940_full_reference_consistent" if consistent else "stage940_full_reference_not_consistent",
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": (
            "否。本次只按旧 full-window 基准复跑当前正式版本，不新增规则、不筛参数。"
        ),
        "continue_value_before": (
            "是。它能判断功能性重建后的全周期曲线是否仍匹配旧正式基准。"
        ),
        "overfit_reflection_after": (
            "否。本次是固定窗口一致性审计；不能用差异反向救参数或挑样本。"
        ),
        "continue_value_after": (
            "是。若不一致，需要继续追原始派生产物或旧 AI eligibility，而不是直接把当前结果当旧基准。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curve": str(CURVE_PATH),
            "comparison": str(COMPARISON_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    pd.DataFrame([summary]).to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, comparison, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
