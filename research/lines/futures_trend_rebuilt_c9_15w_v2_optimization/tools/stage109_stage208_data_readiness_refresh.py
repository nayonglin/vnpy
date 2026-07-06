from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage109"
MODEL_TAG = "stage109_stage208_data_readiness_refresh_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage109_stage208_data_readiness_refresh"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage109_stage208_data_readiness_refresh"
STAGES_DIR = LINE_DIR / "stages"

STAGE049_SCRIPT = LINE_DIR / "tools" / "stage049_stage208_true_carry_replay_gate.py"
STAGE052_SCRIPT = LINE_DIR / "tools" / "stage052_tqsdk_jd_minute_backfill.py"
STAGE091_DECISION_PATH = (
    LINE_DIR
    / "outputs"
    / "stage091_jd_margin_source_contract_matrix"
    / "rebuilt_c9_v2_stage091_jd_margin_source_contract_matrix_decision_stage091_jd_margin_source_contract_matrix_v1.json"
)

SOURCE_TABLE_PATH = OUT / f"{OUTPUT_PREFIX}_source_table_{MODEL_TAG}.csv"
CONTRACT_SPEC_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_contract_spec_audit_{MODEL_TAG}.csv"
MINUTE_COVERAGE_PATH = OUT / f"{OUTPUT_PREFIX}_minute_contract_coverage_{MODEL_TAG}.csv"
MANIFEST_COVERAGE_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_coverage_{MODEL_TAG}.csv"
NEXT_BACKFILL_PLAN_PATH = OUT / f"{OUTPUT_PREFIX}_next_backfill_plan_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

NEXT_BATCH_SIZE = 6

EXTERNAL_RESEARCH = [
    {
        "source": "DCE historical data / trading parameter pages",
        "url": "https://www.dce.com.cn/dceg/channel/list/468.html",
        "finding": "DCE publishes historical/parameter information, but margin can vary by contract and date; true ledger needs time-aligned parameters.",
    },
    {
        "source": "TqSdk historical/backtest data documentation",
        "url": "https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html",
        "finding": "TqSdk can be a historical data route, but downloaded bars still need coverage, hash and field-quality checks.",
    },
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Independent trend/carry sleeves need true accounting, costs, positions and capital constraints, not curve-only overlays.",
    },
]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return "" if pd.isna(value) else value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def _source_row(source_id: str, ready: bool, *, row_count: int = 0, blocking_reason: str = "", detail: str = "") -> dict[str, Any]:
    return {
        "source_id": source_id,
        "ready": bool(ready),
        "row_count": int(row_count),
        "blocking_reason": blocking_reason,
        "detail": detail,
    }


def build_current_readiness(s049) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source_rows = [s049.audit_current_c9_daily(), s049.audit_xsmom_signal_daily(), s049.audit_price_frame_daily()]
    product_returns = s049.load_product_returns()
    metadata = s049.load_product_metadata()
    contract_specs = s049.audit_contract_specs(product_returns, metadata)
    spec_ready = bool(contract_specs["exact_spec_ready"].astype(bool).all()) if not contract_specs.empty else False
    spec_block = ",".join(
        contract_specs.loc[~contract_specs["exact_spec_ready"].astype(bool), "product_vt_symbol"].astype(str)
    )
    source_rows.append(
        _source_row(
            "contract_specs_exact",
            spec_ready,
            row_count=len(contract_specs),
            blocking_reason=f"missing_exact_specs:{spec_block}" if spec_block else "",
            detail=f"products={len(contract_specs)}",
        )
    )
    minute_index = s049.build_minute_file_index()
    minute_coverage = s049.audit_minute_contract_coverage(product_returns["main_contract_vt"], minute_index)
    minute_ready = bool(minute_coverage["minute_file_ready"].astype(bool).all()) if not minute_coverage.empty else False
    missing_minutes = int((~minute_coverage["minute_file_ready"].astype(bool)).sum()) if not minute_coverage.empty else 0
    source_rows.append(
        _source_row(
            "current_minute_fill_bars",
            minute_ready,
            row_count=len(minute_coverage),
            blocking_reason=f"missing_minute_contracts:{missing_minutes}" if missing_minutes else "",
            detail=f"minute_file_index={len(minute_index)}",
        )
    )
    return pd.DataFrame(source_rows), contract_specs, minute_coverage


def build_manifest_refresh(s052) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = s052._read_csv(s052.MINUTE_GAP_MANIFEST_PATH)
    current_index = s052.build_minute_file_index()
    coverage = s052.audit_manifest_coverage(manifest, current_index)
    plan = s052.build_backfill_plan(manifest, current_index, NEXT_BATCH_SIZE)
    return coverage, plan


def _coverage_counts(coverage: pd.DataFrame) -> dict[str, Any]:
    if coverage.empty:
        return {"total": 0, "ready": 0, "missing": 0, "missing_by_product": {}}
    ready = coverage["minute_file_ready"].astype(bool)
    missing = coverage[~ready].copy()
    return {
        "total": int(len(coverage)),
        "ready": int(ready.sum()),
        "missing": int((~ready).sum()),
        "missing_by_product": {
            str(k): int(v) for k, v in missing.groupby("product_vt_symbol").size().sort_index().items()
        },
    }


def make_decision(
    source_table: pd.DataFrame,
    contract_specs: pd.DataFrame,
    minute_coverage: pd.DataFrame,
    manifest_coverage: pd.DataFrame,
    plan: pd.DataFrame,
    stage091: dict[str, Any],
) -> dict[str, Any]:
    source_blocking = source_table[~source_table["ready"].astype(bool)].copy()
    contract_blocking = contract_specs[~contract_specs["exact_spec_ready"].astype(bool)].copy()
    manifest_counts = _coverage_counts(manifest_coverage)
    missing_contracts = minute_coverage[~minute_coverage["minute_file_ready"].astype(bool)].copy()
    margin_ready = bool(stage091.get("ready_for_true_ledger_replay", False))
    ready_for_true = bool(source_blocking.empty and contract_blocking.empty and manifest_counts["missing"] == 0 and margin_ready)
    if ready_for_true:
        decision = "stage109_stage208_data_ready_for_true_ledger"
        next_step = "读取 version-ab-experiment 预声明 A/B/C 后，进入 Stage208 true carry 最小真实承载验证。"
        continue_after = "有"
        continue_reason = "分钟、规格和保证金阻塞已消除，可以一次性证伪或验证独立收益腿。"
    else:
        decision = "stage109_stage208_data_still_blocked_batch4_and_margin_needed"
        next_step = (
            "继续小批量补 `next_backfill_plan` 的分钟合约；同时必须获取 DCE 注册门户或授权 vendor 的 "
            "`jd_contract_daily_margin_history`，否则禁止 true ledger replay。"
        )
        continue_after = "有"
        continue_reason = "这是当前剩余少数结构性路线；但未补保证金前不能跑策略回测。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "ready_for_true_ledger_replay": ready_for_true,
        "source_blocking_ids": ",".join(source_blocking["source_id"].astype(str).tolist()) if not source_blocking.empty else "",
        "current_minute_contract_missing": int((~minute_coverage["minute_file_ready"].astype(bool)).sum()),
        "manifest_missing": int(manifest_counts["missing"]),
        "manifest_jd_missing": int(manifest_counts["missing_by_product"].get("jd.DCE", 0)),
        "contract_spec_blocking_count": int(len(contract_blocking)),
        "stage091_decision": str(stage091.get("decision", "")),
        "stage091_accepted_route_count": int(stage091.get("accepted_route_count", 0) or 0),
        "jd_margin_history_ready": margin_ready,
        "next_batch_contract_count": int(len(plan)),
        "next_batch_contracts": plan["contract_vt"].astype(str).tolist() if "contract_vt" in plan else [],
        "next_batch_jd_contract_count": int(plan.get("product_vt_symbol", pd.Series(dtype=str)).astype(str).eq("jd.DCE").sum())
        if not plan.empty
        else 0,
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine_run": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "formal_ab_triggered": False,
        "external_research_judgment": (
            "DCE/供应商路线能提供历史行情或交易参数，但保证金会按合约和日期变化；"
            "独立 xsmom/carry sleeve 只有在分钟成交和逐日保证金都通过验收后才可回测。"
        ),
        "overfit_reflection_before": "否。本阶段只刷新数据依赖，不看收益、不调策略参数。",
        "overfit_reflection_after": (
            "否。结论仍是数据阻塞；强行用默认保证金或 fallback 分钟线回测才会形成隐性过拟合。"
        ),
        "continue_value_before": "有。Stage108 已停止 base_stop 延迟退出，结构性路线回到独立收益腿数据就绪。",
        "continue_value_after": continue_after + "。" + continue_reason,
        "next_step": next_step,
    }


def write_report(
    source_table: pd.DataFrame,
    contract_specs: pd.DataFrame,
    minute_coverage: pd.DataFrame,
    manifest_coverage: pd.DataFrame,
    plan: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    missing_minutes = minute_coverage[~minute_coverage["minute_file_ready"].astype(bool)].copy()
    missing_manifest = manifest_coverage[~manifest_coverage["minute_file_ready"].astype(bool)].copy()
    missing_specs = contract_specs[~contract_specs["exact_spec_ready"].astype(bool)].copy()
    report = f"""# {STAGE} Stage208 Data Readiness Refresh

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：当前目标不应继续从 base_stop 事后收益救参；Stage208/xsmom 真承载是独立收益腿方向，但仍必须 data-first。

## Decision

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## Source Table

{_md_table(source_table)}

## Missing Contract Specs

{_md_table(missing_specs, 80)}

## Missing Minute Coverage

{_md_table(missing_minutes, 120)}

## Manifest Missing

{_md_table(missing_manifest, 120)}

## Next Backfill Plan

{_md_table(plan, 80)}

## 过拟合反思

- 运行前：{decision['overfit_reflection_before']}
- 运行后：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前：{decision['continue_value_before']}
- 运行后：{decision['continue_value_after']}

## 输出

- source_table：`{SOURCE_TABLE_PATH}`
- contract_spec_audit：`{CONTRACT_SPEC_AUDIT_PATH}`
- minute_coverage：`{MINUTE_COVERAGE_PATH}`
- manifest_coverage：`{MANIFEST_COVERAGE_PATH}`
- next_backfill_plan：`{NEXT_BACKFILL_PLAN_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    source_table: pd.DataFrame,
    contract_specs: pd.DataFrame,
    minute_coverage: pd.DataFrame,
    manifest_coverage: pd.DataFrame,
    plan: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage109_stage208_data_readiness_refresh.md"
    missing_minutes = minute_coverage[~minute_coverage["minute_file_ready"].astype(bool)].copy()
    missing_manifest = manifest_coverage[~manifest_coverage["minute_file_ready"].astype(bool)].copy()
    missing_specs = contract_specs[~contract_specs["exact_spec_ready"].astype(bool)].copy()
    text = f"""# Stage109 Stage208 数据就绪刷新

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区：`{ROOT}`
- 阶段性质：只读数据就绪刷新；不回测收益、不改策略、不连接 CTP、不调用订单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：DCE historical/trading parameter pages、TqSdk historical/backtest docs、pysystemtrade backtesting docs。
- 我的判断：Stage208/xsmom 真承载仍是结构性方向，但必须先补分钟成交窗口和 JD 逐日保证金；不能用默认保证金或旧输出替代。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage109_stage208_data_readiness_refresh.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：`NEXT_BATCH_SIZE={NEXT_BATCH_SIZE}`。
- 修改参数：无正式策略参数。
- 删除参数：无。

## 结果摘要

- 决策：`{decision['decision']}`
- ready_for_true_ledger_replay：`{decision['ready_for_true_ledger_replay']}`
- source_blocking_ids：`{decision['source_blocking_ids'] or '无'}`
- current_minute_contract_missing：`{decision['current_minute_contract_missing']}`
- manifest_missing：`{decision['manifest_missing']}`
- manifest_jd_missing：`{decision['manifest_jd_missing']}`
- contract_spec_blocking_count：`{decision['contract_spec_blocking_count']}`
- jd_margin_history_ready：`{decision['jd_margin_history_ready']}`
- next_batch_contract_count：`{decision['next_batch_contract_count']}`
- next_batch_contracts：`{decision['next_batch_contracts']}`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Source Table

{_md_table(source_table)}

## Missing Contract Specs

{_md_table(missing_specs, 80)}

## Missing Minute Coverage

{_md_table(missing_minutes, 120)}

## Manifest Missing

{_md_table(missing_manifest, 120)}

## Next Backfill Plan

{_md_table(plan, 80)}

## 标准回测指标

- 期末权益：不适用，本阶段只读数据依赖未重跑策略。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 后续规划和 TODO

- {decision['next_step']}

## 过拟合反思

- 运行前：{decision['overfit_reflection_before']}
- 运行后：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前：{decision['continue_value_before']}
- 运行后：{decision['continue_value_after']}

## 输出

- 报告：`{REPORT_PATH}`
- source_table：`{SOURCE_TABLE_PATH}`
- contract_spec_audit：`{CONTRACT_SPEC_AUDIT_PATH}`
- minute_coverage：`{MINUTE_COVERAGE_PATH}`
- manifest_coverage：`{MANIFEST_COVERAGE_PATH}`
- next_backfill_plan：`{NEXT_BACKFILL_PLAN_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    s049 = _load_module(STAGE049_SCRIPT, "stage049_stage208_true_carry_replay_gate")
    s052 = _load_module(STAGE052_SCRIPT, "stage052_tqsdk_jd_minute_backfill")
    stage091 = json.loads(STAGE091_DECISION_PATH.read_text(encoding="utf-8")) if STAGE091_DECISION_PATH.exists() else {}
    input_audit = _input_audit([STAGE049_SCRIPT, STAGE052_SCRIPT, STAGE091_DECISION_PATH, s052.MINUTE_GAP_MANIFEST_PATH])
    if not bool(input_audit["exists"].all()):
        raise FileNotFoundError("Stage109 input missing")
    source_table, contract_specs, minute_coverage = build_current_readiness(s049)
    manifest_coverage, plan = build_manifest_refresh(s052)
    decision = make_decision(source_table, contract_specs, minute_coverage, manifest_coverage, plan, stage091)

    source_table.to_csv(SOURCE_TABLE_PATH, index=False, encoding="utf-8-sig")
    contract_specs.to_csv(CONTRACT_SPEC_AUDIT_PATH, index=False, encoding="utf-8-sig")
    minute_coverage.to_csv(MINUTE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    manifest_coverage.to_csv(MANIFEST_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    plan.to_csv(NEXT_BACKFILL_PLAN_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(source_table, contract_specs, minute_coverage, manifest_coverage, plan, decision)
    stage_path = write_stage_record(source_table, contract_specs, minute_coverage, manifest_coverage, plan, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"[stage109] report={REPORT_PATH}")
    print(f"[stage109] stage_record={stage_path}")


if __name__ == "__main__":
    main()
