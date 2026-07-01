from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parents[1]
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage164"
MODEL_TAG = "stage164_entry_context_observability_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage164_entry_context_observability_audit"

STRATEGY_PATH = PROJECT_DIR / "qmt_roll_portfolio_strategy.py"
UNIT_TEST_PATH = REPO_ROOT / "tests" / "test_qmt_entry_context_diagnostics.py"

SOURCE_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_audit_{MODEL_TAG}.csv"
OUTPUT_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_output_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

ENTRY_RISK_OUTPUTS = [
    (
        "stage830_entry_risk",
        OUTPUT_DIR / "qmt_roll_stage830_stage827_c2_broker10_margin_cap_entry_risk_stage830_stage827_c2_broker10_margin_cap_v1.csv",
    ),
    (
        "stage847_entry_risk",
        OUTPUT_DIR / "qmt_roll_stage847_stage830_c4_stop_retry_engine_entry_risk_stage847_stage830_c4_stop_retry_engine_v1.csv",
    ),
    (
        "stage901_entry_risk",
        OUTPUT_DIR / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_risk_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv",
    ),
]


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _method_block(source: str, name: str) -> str:
    pattern = re.compile(rf"^    def {re.escape(name)}\(.*?(?=^    def |\Z)", re.M | re.S)
    match = pattern.search(source)
    return match.group(0) if match else ""


def _source_audit() -> pd.DataFrame:
    source = STRATEGY_PATH.read_text(encoding="utf-8")
    sizing_block = _method_block(source, "_calculate_entry_sizing")
    entry_risk_block = _method_block(source, "_record_entry_risk_diagnostic")
    append_layer_block = _method_block(source, "_append_layer")
    entry_context_literal_count = sizing_block.count('"entry_context": entry_context')
    rows = [
        {
            "check_id": "sizing_snapshot_preserves_entry_context",
            "status": "PASS" if entry_context_literal_count >= 2 else "FAIL",
            "evidence": f"literal_count={entry_context_literal_count}",
            "detail": "fixed_size 与 risk_budget 两条 sizing 返回路径都应保留原始 entry_context。",
        },
        {
            "check_id": "entry_risk_exports_entry_context",
            "status": "PASS"
            if '"entry_context"' in entry_risk_block and 'sizing_snapshot.get("entry_context")' in entry_risk_block
            else "FAIL",
            "evidence": "entry_risk_diagnostics row includes entry_context from sizing_snapshot",
            "detail": "entry_risk 输出应有独立 entry_context 列，不能只依赖 env_gate_entry_context。",
        },
        {
            "check_id": "add_layers_have_observable_contexts",
            "status": "PASS"
            if all(item in append_layer_block for item in ["regular_add", "donchian_add", "post_quality_add"])
            else "FAIL",
            "evidence": "regular_add/donchian_add/post_quality_add literals",
            "detail": "加仓层也应在 entry_risk 中显示上下文，避免和基础开仓混在一起。",
        },
        {
            "check_id": "unit_test_exists",
            "status": "PASS" if UNIT_TEST_PATH.exists() else "FAIL",
            "evidence": str(UNIT_TEST_PATH),
            "detail": "Stage164 的观测字段契约由单测固定。",
        },
    ]
    return pd.DataFrame(rows)


def _output_audit() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label, path in ENTRY_RISK_OUTPUTS:
        row: dict[str, Any] = {
            "label": label,
            "path": str(path),
            "exists": int(path.exists()),
            "rows": 0,
            "has_entry_context_column": 0,
            "entry_context_counts": "{}",
            "note": "missing output",
        }
        if path.exists() and path.stat().st_size > 4:
            frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
            row["rows"] = int(len(frame))
            row["has_entry_context_column"] = int("entry_context" in frame.columns)
            if "entry_context" in frame.columns:
                row["entry_context_counts"] = json.dumps(
                    {
                        str(key): int(value)
                        for key, value in frame["entry_context"].astype(str).value_counts(dropna=False).items()
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                row["note"] = "current output materialized after Stage164 code"
            else:
                row["note"] = "stale output generated before Stage164 code; rerun producer to materialize column"
        rows.append(row)
    return pd.DataFrame(rows)


def _write_report(source: pd.DataFrame, outputs: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage164 Entry Context Observability Audit",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        "- 性质：只读观测性审计；不跑策略，不连接 CTP，不调用订单 API。",
        "",
        "## Decision",
        "",
        f"- decision：`{decision['decision']}`",
        f"- source_ready：`{decision['source_ready']}`",
        f"- materialized_output_ready：`{decision['materialized_output_ready']}`",
        f"- stale_output_count：`{decision['stale_output_count']}`",
        "",
        "## Source Audit",
        "",
        _md_table(source[["check_id", "status", "evidence", "detail"]], max_rows=20),
        "",
        "## Output Audit",
        "",
        _md_table(
            outputs[
                [
                    "label",
                    "exists",
                    "rows",
                    "has_entry_context_column",
                    "entry_context_counts",
                    "note",
                ]
            ],
            max_rows=20,
        ),
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
    source_ready = bool(source["status"].eq("PASS").all())
    stale_output_count = int(
        ((outputs["exists"].astype(int) == 1) & (outputs["has_entry_context_column"].astype(int) == 0)).sum()
    )
    materialized_output_ready = bool(
        len(outputs) > 0
        and (outputs["exists"].astype(int) == 1).all()
        and (outputs["has_entry_context_column"].astype(int) == 1).all()
    )
    if not source_ready:
        decision_name = "stage164_source_contract_failed"
    elif materialized_output_ready:
        decision_name = "stage164_entry_context_observability_source_and_outputs_ready"
    else:
        decision_name = "stage164_entry_context_observability_source_ready_outputs_need_rerun"

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_name,
        "source_ready": source_ready,
        "materialized_output_ready": materialized_output_ready,
        "stale_output_count": stale_output_count,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": "Skipped external search per operator constraint; local observability audit only.",
        "overfit_reflection_before": "否。Stage164 只补诊断字段，不改交易逻辑或参数。",
        "continue_value_before": "是。Stage163 已证明 reverse_entry 当前未触发但未来难观测，应先补可观测性。",
        "overfit_reflection_after": "否。新增字段只让执行路径可审计，不参与开仓、平仓或风控计算。",
        "continue_value_after": (
            "是。源码已具备 entry_context 观测能力；历史 CSV 需要重跑对应 producer 才会物化新列。"
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
