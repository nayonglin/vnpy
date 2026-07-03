from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage050"
MODEL_TAG = "stage050_jd_true_carry_data_manifest_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage050_jd_true_carry_data_manifest"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage050_jd_true_carry_data_manifest"
STAGES_DIR = LINE_DIR / "stages"

STAGE049_OUTPUT_DIR = LINE_DIR / "outputs" / "stage049_stage208_true_carry_replay_gate"
STAGE049_PREFIX = "rebuilt_c9_v2_stage049_stage208_true_carry_replay_gate"
STAGE049_TAG = "stage049_stage208_true_carry_replay_gate_v1"
STAGE020_OUTPUT_DIR = LINE_DIR / "outputs" / "stage020_sqlite_jd_repair_xsmom_inputs"
STAGE020_PREFIX = "rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs"
STAGE020_TAG = "stage020_sqlite_jd_repair_xsmom_inputs_v1"

MINUTE_COVERAGE_PATH = STAGE049_OUTPUT_DIR / f"{STAGE049_PREFIX}_minute_contract_coverage_{STAGE049_TAG}.csv"
CONTRACT_SPEC_AUDIT_PATH = STAGE049_OUTPUT_DIR / f"{STAGE049_PREFIX}_contract_spec_audit_{STAGE049_TAG}.csv"
PRODUCT_RETURNS_PATH = STAGE020_OUTPUT_DIR / f"{STAGE020_PREFIX}_product_returns_{STAGE020_TAG}.csv"

MINUTE_GAP_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_gap_manifest_{MODEL_TAG}.csv"
CONTRACT_SPEC_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_spec_manifest_{MODEL_TAG}.csv"
SOURCE_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_contract_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage050_jd_true_carry_data_manifest.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        if np.isnan(result) or np.isinf(result):
            return None
        return result
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def build_minute_gap_manifest(missing_coverage: pd.DataFrame, product_returns: pd.DataFrame) -> pd.DataFrame:
    missing = missing_coverage.copy()
    missing = missing[~missing["minute_file_ready"].astype(bool)].copy()
    prices = product_returns.copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    rows: list[dict[str, Any]] = []
    for row in missing.itertuples(index=False):
        contract = str(row.contract_vt)
        product = str(row.product_vt_symbol)
        span = prices[prices["main_contract_vt"].astype(str).eq(contract)].copy()
        start = pd.Timestamp(span["date"].min()).date().isoformat() if not span.empty else ""
        end = pd.Timestamp(span["date"].max()).date().isoformat() if not span.empty else ""
        rows.append(
            {
                "contract_vt": contract,
                "product_vt_symbol": product,
                "request_start_date": start,
                "request_end_date": end,
                "observed_price_rows": int(len(span)),
                "required_bar_interval": "1m",
                "required_fields": "bar_datetime,open,high,low,close,volume,open_oi,close_oi,source_file_hash",
                "preferred_source": "tqsdk_or_vendor_historical_minute",
                "acceptance_rule": "no_fallback_fill_for_2100_2105_or_0900_0905_window",
                "priority": "P0_jd_true_carry_blocker" if product == "jd.DCE" else "P1_tail_contract_gap",
            }
        )
    return pd.DataFrame(rows).sort_values(["priority", "product_vt_symbol", "contract_vt"]).reset_index(drop=True)


def build_contract_spec_manifest(contract_specs: pd.DataFrame) -> pd.DataFrame:
    blocked = contract_specs[~contract_specs["exact_spec_ready"].astype(bool)].copy()
    rows: list[dict[str, Any]] = []
    for row in blocked.itertuples(index=False):
        product = str(row.product_vt_symbol)
        static_status = "size_tick_ready_from_dce_contract" if product == "jd.DCE" else "static_spec_partial"
        rows.append(
            {
                "product_vt_symbol": product,
                "current_size": float(getattr(row, "size", 0.0)),
                "current_price_tick": float(getattr(row, "price_tick", 0.0)),
                "current_slippage": float(getattr(row, "slippage", 0.0)),
                "current_margin_ratio": float(getattr(row, "margin_ratio", 0.0)),
                "blocking_reason": str(getattr(row, "blocking_reason", "")),
                "static_spec_status": static_status,
                "required_margin_granularity": "contract_daily",
                "required_fields": "contract_vt,trade_date,exchange_margin_ratio,broker_margin_ratio,source_system,source_file_hash,publish_or_effective_time",
                "preferred_source": "broker_statement_or_vendor_contract_margin_history",
                "acceptance_rule": "margin_ratio_must_be_time_aligned_and_not_default_filled",
                "priority": "P0_jd_margin_blocker" if product == "jd.DCE" else "P1_contract_spec_gap",
            }
        )
    return pd.DataFrame(rows).sort_values(["priority", "product_vt_symbol"]).reset_index(drop=True)


def build_source_contract() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dataset_id": "jd_and_tail_contract_minute_1m_history",
                "purpose": "Stage208 true carry current C9 no-fallback fill replay",
                "required_time_range": "per contract request_start_date to request_end_date",
                "required_fields": "bar_datetime,vt_symbol,open,high,low,close,volume,open_oi,close_oi,source_file_hash",
                "pit_rule": "bar_datetime must be exchange timestamp; no future-published patched values",
                "acceptance_test": "all Stage049 missing contracts present in 21:00-21:05 or 09:00-09:05 fill windows when orders exist",
            },
            {
                "dataset_id": "jd_contract_daily_margin_history",
                "purpose": "Stage208 true carry current C9 broker10 margin gate",
                "required_time_range": "2020-01-02 to 2026-06-30 for each jd main contract used by Stage020",
                "required_fields": "contract_vt,trade_date,exchange_margin_ratio,broker_margin_ratio,source_system,source_file_hash,publish_or_effective_time",
                "pit_rule": "margin ratio must be effective on or before trade_date",
                "acceptance_test": "no jd.DCE margin ratio rows default-filled in Stage049 contract spec audit",
            },
        ]
    )


def make_stage050_decision(minute_manifest: pd.DataFrame, spec_manifest: pd.DataFrame) -> dict[str, Any]:
    if minute_manifest.empty:
        jd_minutes = 0
    elif "product_vt_symbol" in minute_manifest.columns:
        jd_minutes = int(minute_manifest["product_vt_symbol"].astype(str).eq("jd.DCE").sum())
    else:
        jd_minutes = int(minute_manifest["contract_vt"].astype(str).str.startswith("jd").sum())
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": "stage050_jd_true_carry_data_manifest_ready_no_strategy_candidate",
        "minute_gap_contract_count": int(len(minute_manifest)),
        "jd_minute_gap_contract_count": jd_minutes,
        "contract_spec_request_count": int(len(spec_manifest)),
        "ready_for_true_ledger_replay": False,
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine_run": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "formal_ab_triggered": False,
        "external_research_judgment": (
            "DCE 官方合约信息可确认鸡蛋交易单位与最小变动价位，但交易保证金可按市场情况调整；"
            "因此 Stage208 级真承载必须补历史合约分钟线和逐日保证金，不可用静态最低保证金或默认比例替代。"
        ),
        "overfit_reflection_before": "否。本阶段只把 Stage049 阻塞转成数据请求，不产生策略收益曲线。",
        "overfit_reflection_after": "否。清单要求 source_hash、PIT 时间和无默认填充，避免后续用隐性假设救结果。",
        "continue_value_before": "有。Stage049 已把真承载阻塞定位到 jd 规格和分钟线，下一步必须 data-first。",
        "continue_value_after": (
            "有但依赖外部/授权数据。拿到清单里的分钟线和保证金历史前，不应继续 xsmom 真承载回测。"
        ),
        "outputs": {
            "minute_gap_manifest": str(MINUTE_GAP_MANIFEST_PATH),
            "contract_spec_manifest": str(CONTRACT_SPEC_MANIFEST_PATH),
            "source_contract": str(SOURCE_CONTRACT_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    minute_manifest: pd.DataFrame,
    spec_manifest: pd.DataFrame,
    source_contract: pd.DataFrame,
) -> None:
    lines = [
        "# Stage050 jd 真承载数据补齐清单",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：数据获取 manifest；不回测收益，不改策略，不连接 CTP，不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- DCE 官方合约页显示鸡蛋交易单位为 `5吨/手`，报价单位为 `元/500千克`，最小变动价位为 `1元/500千克`。",
        "- DCE 同时说明交易保证金可根据市场情况调整；所以当前缺口不是 size/tick，而是历史逐日/逐合约保证金。",
        "- 我的判断：若要满足用户“基础池加鸡蛋 + 真承载证据”，必须先补分钟和保证金数据合同，不能用默认比例硬跑。",
        "",
        "## Minute Gap Manifest",
        "",
        _md_table(minute_manifest, max_rows=120),
        "",
        "## Contract Spec Manifest",
        "",
        _md_table(spec_manifest, max_rows=40),
        "",
        "## Source Contract",
        "",
        _md_table(source_contract),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(
    decision: dict[str, Any],
    minute_manifest: pd.DataFrame,
    spec_manifest: pd.DataFrame,
    source_contract: pd.DataFrame,
) -> None:
    jd_minutes = minute_manifest[minute_manifest["product_vt_symbol"].astype(str).eq("jd.DCE")].copy()
    text = f"""# Stage050 jd 真承载数据补齐清单

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：数据获取 manifest；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：DCE 鸡蛋期货/期权合约页与交易参数说明。
- 我的判断：DCE 官方合约信息足以确认鸡蛋 size/tick 口径，但保证金会按市场情况调整；当前不能用静态最低保证金或默认 `0.12` 当作 Stage208 级真承载证据。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage050_jd_true_carry_data_manifest.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage050_jd_true_carry_data_manifest.py`
- 新增参数：无交易参数
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- minute_gap_contract_count：`{decision['minute_gap_contract_count']}`
- jd_minute_gap_contract_count：`{decision['jd_minute_gap_contract_count']}`
- contract_spec_request_count：`{decision['contract_spec_request_count']}`
- ready_for_true_ledger_replay：`False`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## JD Minute Gap

{_md_table(jd_minutes, max_rows=80)}

## Contract Spec Manifest

{_md_table(spec_manifest, max_rows=40)}

## Source Contract

{_md_table(source_contract)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- minute_gap_manifest：`{MINUTE_GAP_MANIFEST_PATH}`
- contract_spec_manifest：`{CONTRACT_SPEC_MANIFEST_PATH}`
- source_contract：`{SOURCE_CONTRACT_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    minute_coverage = _read_csv(MINUTE_COVERAGE_PATH)
    contract_specs = _read_csv(CONTRACT_SPEC_AUDIT_PATH)
    product_returns = _read_csv(PRODUCT_RETURNS_PATH)
    minute_manifest = build_minute_gap_manifest(minute_coverage, product_returns)
    spec_manifest = build_contract_spec_manifest(contract_specs)
    source_contract = build_source_contract()
    decision = make_stage050_decision(minute_manifest, spec_manifest)

    minute_manifest.to_csv(MINUTE_GAP_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    spec_manifest.to_csv(CONTRACT_SPEC_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    source_contract.to_csv(SOURCE_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, minute_manifest, spec_manifest, source_contract)
    _write_stage_record(decision, minute_manifest, spec_manifest, source_contract)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
