from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage163"
MODEL_TAG = "stage163_reverse_entry_broker10_cap_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage163_reverse_entry_broker10_cap_audit"

STRATEGY_PATH = PROJECT_DIR / "qmt_roll_portfolio_strategy.py"
STAGE830_PATH = PROJECT_DIR / "analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap.py"

SOURCE_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_audit_{MODEL_TAG}.csv"
OUTPUT_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_output_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


OUTPUT_FILES = [
    (
        "stage830_entry_candidates",
        OUTPUT_DIR / "qmt_roll_stage830_stage827_c2_broker10_margin_cap_entry_candidates_stage830_stage827_c2_broker10_margin_cap_v1.csv",
    ),
    (
        "stage830_entry_risk",
        OUTPUT_DIR / "qmt_roll_stage830_stage827_c2_broker10_margin_cap_entry_risk_stage830_stage827_c2_broker10_margin_cap_v1.csv",
    ),
    (
        "stage830_trade_events",
        OUTPUT_DIR / "qmt_roll_stage830_stage827_c2_broker10_margin_cap_trade_events_stage830_stage827_c2_broker10_margin_cap_v1.csv",
    ),
    (
        "stage830_cap_events",
        OUTPUT_DIR / "qmt_roll_stage830_stage827_c2_broker10_margin_cap_cap_events_stage830_stage827_c2_broker10_margin_cap_v1.csv",
    ),
    (
        "stage847_entry_candidates",
        OUTPUT_DIR / "qmt_roll_stage847_stage830_c4_stop_retry_engine_entry_candidates_stage847_stage830_c4_stop_retry_engine_v1.csv",
    ),
    (
        "stage847_entry_risk",
        OUTPUT_DIR / "qmt_roll_stage847_stage830_c4_stop_retry_engine_entry_risk_stage847_stage830_c4_stop_retry_engine_v1.csv",
    ),
    (
        "stage847_trade_events",
        OUTPUT_DIR / "qmt_roll_stage847_stage830_c4_stop_retry_engine_trade_events_stage847_stage830_c4_stop_retry_engine_v1.csv",
    ),
    (
        "stage901_entry_candidates",
        OUTPUT_DIR / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_candidates_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv",
    ),
    (
        "stage901_entry_risk",
        OUTPUT_DIR / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_risk_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv",
    ),
    (
        "stage901_trade_events",
        OUTPUT_DIR / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_trade_events_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv",
    ),
]


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _extract_function_block(text: str, function_name: str) -> str:
    pattern = re.compile(rf"^    def {re.escape(function_name)}\(.*?(?=^    def |\Z)", re.M | re.S)
    match = pattern.search(text)
    return match.group(0) if match else ""


def _source_audit() -> pd.DataFrame:
    strategy_text = STRATEGY_PATH.read_text(encoding="utf-8")
    stage830_text = STAGE830_PATH.read_text(encoding="utf-8")
    close_block = _extract_function_block(strategy_text, "_close_all_layers_and_set_flat_target")
    reserved_block = _extract_function_block(strategy_text, "_reserved_margin_in_use")
    stage830_sizing_block = _extract_function_block(stage830_text, "_calculate_entry_sizing")

    candidate_snapshot_context_literals = re.findall(
        r"_record_entry_candidate_snapshot\([\s\S]{0,1800}?entry_context=\"([^\"]+)\"",
        strategy_text,
    )
    reverse_sizing_call_count = len(re.findall(r"entry_context=\"reverse_entry\"", strategy_text))
    source_rows = [
        {
            "check_id": "base_strategy_has_reverse_entry_call_sites",
            "status": "PASS" if reverse_sizing_call_count >= 2 else "FAIL",
            "evidence": f"reverse_entry sizing call literals={reverse_sizing_call_count}",
            "detail": "基础策略在 long->short 和 short->long 反手路径中直接调用 _calculate_entry_sizing(entry_context=\"reverse_entry\")。",
        },
        {
            "check_id": "flat_entry_candidate_snapshot_only",
            "status": "WARN" if set(candidate_snapshot_context_literals) == {"flat_entry"} else "PASS",
            "evidence": json.dumps(candidate_snapshot_context_literals, ensure_ascii=False),
            "detail": "当前 _record_entry_candidate_snapshot 只覆盖 flat_entry；reverse_entry 若未来触发，不能只靠 entry_candidates 观察。",
        },
        {
            "check_id": "stage830_cap_explicit_flat_only",
            "status": "PASS" if "entry_context != \"flat_entry\"" in stage830_sizing_block and "not_flat_entry" in stage830_sizing_block else "FAIL",
            "evidence": "entry_context != \"flat_entry\" -> reason not_flat_entry -> return sizing",
            "detail": "Stage830 broker10 cap 当前显式只对 flat_entry 生效，非 flat_entry 会直接返回未调整 sizing。",
        },
        {
            "check_id": "reverse_close_target_does_not_update_margin_immediately",
            "status": "WARN"
            if "self.set_target(contract_vt_symbol, 0)" in close_block and "total_margin_in_use" not in close_block
            else "PASS",
            "evidence": "close target sets target 0; no total_margin_in_use assignment in close block",
            "detail": "反手先设置平仓 target，但 sizing 发生时 total_margin_in_use 不一定已经扣掉旧仓保证金。",
        },
        {
            "check_id": "reserved_margin_formula_counts_current_margin_plus_pending",
            "status": "WARN"
            if "self.total_margin_in_use + self.pending_margin_reservation" in reserved_block
            else "FAIL",
            "evidence": "_reserved_margin_in_use = total_margin_in_use + pending_margin_reservation",
            "detail": "如果直接把 flat-entry broker10 cap 套到 reverse_entry，可能把待平旧仓保证金和待开新仓保证金双算。",
        },
    ]
    return pd.DataFrame(source_rows)


def _audit_csv(path: Path, label: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "label": label,
        "path": str(path),
        "exists": int(path.exists()),
        "rows": 0,
        "reverse_string_hits": 0,
        "entry_context_counts": "{}",
        "stage830_cap_reason_counts": "{}",
    }
    if not path.exists() or path.stat().st_size <= 4:
        return row
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    row["rows"] = int(len(frame))
    hits = 0
    for column in frame.columns:
        series = frame[column].astype(str)
        hits += int(series.str.contains("reverse", case=False, na=False).sum())
    row["reverse_string_hits"] = hits
    if "entry_context" in frame.columns:
        row["entry_context_counts"] = json.dumps(
            {str(key): int(value) for key, value in frame["entry_context"].astype(str).value_counts(dropna=False).items()},
            ensure_ascii=False,
            sort_keys=True,
        )
    reason_cols = [col for col in frame.columns if col.endswith("broker10_margin_cap_reason")]
    if reason_cols:
        counts: dict[str, int] = {}
        for col in reason_cols:
            for key, value in frame[col].astype(str).value_counts(dropna=False).items():
                counts[str(key)] = counts.get(str(key), 0) + int(value)
        row["stage830_cap_reason_counts"] = json.dumps(counts, ensure_ascii=False, sort_keys=True)
    return row


def _output_audit() -> pd.DataFrame:
    return pd.DataFrame([_audit_csv(path, label) for label, path in OUTPUT_FILES])


def _write_report(source: pd.DataFrame, outputs: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage163 Reverse Entry Broker10 Cap Audit",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        "- 性质：只读源码/输出审计；不改策略参数，不连接 CTP，不调用订单 API。",
        "",
        "## Decision",
        "",
        f"- decision：`{decision['decision']}`",
        f"- current_bug_reproduced：`{decision['current_bug_reproduced']}`",
        f"- reverse_hits_total：`{decision['reverse_hits_total']}`",
        f"- recommended_next：{decision['recommended_next']}",
        "",
        "## Source Audit",
        "",
        _md_table(source[["check_id", "status", "evidence", "detail"]], max_rows=20),
        "",
        "## Output Audit",
        "",
        _md_table(outputs[["label", "exists", "rows", "reverse_string_hits", "entry_context_counts", "stage830_cap_reason_counts"]], max_rows=40),
        "",
        "## Outputs",
        "",
        f"- source_audit：`{SOURCE_AUDIT_PATH}`",
        f"- output_audit：`{OUTPUT_AUDIT_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    source = _source_audit()
    outputs = _output_audit()
    reverse_hits_total = int(outputs["reverse_string_hits"].sum()) if not outputs.empty else 0
    fail_count = int(source["status"].eq("FAIL").sum())
    warn_count = int(source["status"].eq("WARN").sum())
    current_bug_reproduced = bool(reverse_hits_total > 0)
    decision_name = (
        "stage163_reverse_entry_current_output_hit_requires_manual_review"
        if current_bug_reproduced
        else "stage163_reverse_entry_not_current_bug_but_guard_required"
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_name,
        "current_bug_reproduced": current_bug_reproduced,
        "reverse_hits_total": reverse_hits_total,
        "source_fail_count": fail_count,
        "source_warn_count": warn_count,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": "Skipped external search per operator constraint; local source/output audit only.",
        "overfit_reflection_before": "否。Stage163 审计 execution path，不改收益参数。",
        "continue_value_before": "是。Stage162 WARN 指向 reverse_entry cap 边界，需要确认是不是实际 bug。",
        "overfit_reflection_after": "否。结论来自源码时序和当前输出是否命中 reverse，不使用收益反推。",
        "continue_value_after": (
            "是。当前未复现 reverse 交易错，但应补 reverse 观测或显式 fail-closed guard；不能盲目把 flat cap 套到 reverse。"
        ),
        "recommended_next": (
            "先补 reverse_entry 的 entry_candidate/entry_risk 可观测性；若要启用 broker10 cap，必须用 post-close margin "
            "projection 或 fail-closed reverse guard，不能复用当前 flat-entry projected formula。"
        ),
        "outputs": {
            "source_audit": str(SOURCE_AUDIT_PATH),
            "output_audit": str(OUTPUT_AUDIT_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SOURCE_AUDIT_PATH.write_text(source.to_csv(index=False), encoding="utf-8-sig")
    OUTPUT_AUDIT_PATH.write_text(outputs.to_csv(index=False), encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(source, outputs, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(source.to_string(index=False))
    print(outputs.to_string(index=False))


if __name__ == "__main__":
    main()
