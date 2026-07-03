from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_universe import MARGIN_RATIOS, PRICETICKS, SIZES, SLIPPAGES  # noqa: E402


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage049"
MODEL_TAG = "stage049_stage208_true_carry_replay_gate_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage049_stage208_true_carry_replay_gate"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage049_stage208_true_carry_replay_gate"
STAGES_DIR = LINE_DIR / "stages"

STAGE167_C9_CURVES_PATH = (
    PROJECT_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
STAGE020_OUTPUT_DIR = LINE_DIR / "outputs" / "stage020_sqlite_jd_repair_xsmom_inputs"
STAGE020_PREFIX = "rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs"
STAGE020_TAG = "stage020_sqlite_jd_repair_xsmom_inputs_v1"
SATELLITE_DAILY_PATH = STAGE020_OUTPUT_DIR / f"{STAGE020_PREFIX}_satellite_daily_{STAGE020_TAG}.csv"
PRODUCT_RETURNS_PATH = STAGE020_OUTPUT_DIR / f"{STAGE020_PREFIX}_product_returns_{STAGE020_TAG}.csv"
PRODUCT_METADATA_PATH = PORTFOLIO_DIR / "backtest_outputs" / "tqsdk_all_futures_contract_metadata.csv"
MINUTE_ROOT = PORTFOLIO_DIR / "downloaded_futures"

SOURCE_TABLE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_table_{MODEL_TAG}.csv"
CONTRACT_SPEC_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_spec_audit_{MODEL_TAG}.csv"
MINUTE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_contract_coverage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage049_stage208_true_carry_replay_gate.md"

ANALYSIS_END = pd.Timestamp("2026-06-30")
REQUIRED_XSMOM_SPEC = "mom_12m_skip1m"


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


def _safe_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not np.isfinite(result):
        return 0.0
    return result


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def required_replay_sources() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "current_c9_stage167_daily_pnl_margin",
            "description": "当前重建 C9/15w 日级 PnL、权益、保证金和成本曲线",
            "current_rebuild_required": True,
        },
        {
            "source_id": "stage020_xsmom_signal_daily",
            "description": "Stage020 当前重建 xsmom frozen signal daily，含 long/short products",
            "current_rebuild_required": True,
        },
        {
            "source_id": "stage020_price_frame_daily",
            "description": "Stage020 当前重建 product return/main contract/close price daily",
            "current_rebuild_required": True,
        },
        {
            "source_id": "contract_specs_exact",
            "description": "所有 xsmom 产品的 size/slippage/margin ratio 精确规格，必须覆盖 jd.DCE",
            "current_rebuild_required": True,
        },
        {
            "source_id": "current_minute_fill_bars",
            "description": "当前合约分钟线成交窗口覆盖，不能依赖 fallback 才能声称 Stage208 级真承载",
            "current_rebuild_required": True,
        },
    ]


def _source_row(source_id: str, ready: bool, *, row_count: int = 0, blocking_reason: str = "", detail: str = "") -> dict[str, Any]:
    return {
        "source_id": source_id,
        "ready": bool(ready),
        "row_count": int(row_count),
        "blocking_reason": blocking_reason,
        "detail": detail,
    }


def audit_current_c9_daily(path: Path = STAGE167_C9_CURVES_PATH) -> dict[str, Any]:
    required = {
        "date",
        "requested_start_month",
        "net_pnl",
        "account_equity",
        "total_margin_exact",
        "broker10_total_margin_exact",
        "slippage",
        "trade_count",
    }
    if not path.exists():
        return _source_row("current_c9_stage167_daily_pnl_margin", False, blocking_reason="missing_file")
    columns = pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns
    missing = sorted(required - set(columns))
    if missing:
        return _source_row(
            "current_c9_stage167_daily_pnl_margin",
            False,
            blocking_reason="missing_columns:" + ",".join(missing),
        )
    data = _read_csv(path, usecols=["date", "requested_start_month", "net_pnl", "account_equity"])
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data[data["requested_start_month"].astype(str).eq("2020-01")].copy()
    data = data[data["date"].le(ANALYSIS_END)]
    ready = not data.empty and pd.Timestamp(data["date"].max()).normalize() >= ANALYSIS_END
    reason = "" if ready else "missing_2020_01_or_not_cover_analysis_end"
    return _source_row(
        "current_c9_stage167_daily_pnl_margin",
        ready,
        row_count=len(data),
        blocking_reason=reason,
        detail=f"start={data['date'].min()} end={data['date'].max()}" if not data.empty else "",
    )


def audit_xsmom_signal_daily(path: Path = SATELLITE_DAILY_PATH) -> dict[str, Any]:
    required = {"date", "spec", "long_products", "short_products", "active_products", "turnover"}
    if not path.exists():
        return _source_row("stage020_xsmom_signal_daily", False, blocking_reason="missing_file")
    data = _read_csv(path)
    missing = sorted(required - set(data.columns))
    if missing:
        return _source_row("stage020_xsmom_signal_daily", False, row_count=len(data), blocking_reason="missing_columns:" + ",".join(missing))
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data[data["spec"].astype(str).eq(REQUIRED_XSMOM_SPEC)].copy()
    active = pd.to_numeric(data["active_products"], errors="coerce").fillna(0).gt(0)
    ready = not data.empty and active.any() and pd.Timestamp(data["date"].max()).normalize() >= ANALYSIS_END
    reasons: list[str] = []
    if data.empty:
        reasons.append("missing_required_spec")
    if not active.any():
        reasons.append("no_active_signal_rows")
    if data.empty or pd.Timestamp(data["date"].max()).normalize() < ANALYSIS_END:
        reasons.append("not_cover_analysis_end")
    return _source_row(
        "stage020_xsmom_signal_daily",
        ready,
        row_count=len(data),
        blocking_reason=",".join(reasons),
        detail=f"active_rows={int(active.sum())}" if not data.empty else "",
    )


def load_product_returns(path: Path = PRODUCT_RETURNS_PATH) -> pd.DataFrame:
    data = _read_csv(path)
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    return data.dropna(subset=["date"]).reset_index(drop=True)


def audit_price_frame_daily(path: Path = PRODUCT_RETURNS_PATH) -> dict[str, Any]:
    required = {"date", "product_vt_symbol", "main_contract_vt", "main_close", "product_return"}
    if not path.exists():
        return _source_row("stage020_price_frame_daily", False, blocking_reason="missing_file")
    data = _read_csv(path)
    missing = sorted(required - set(data.columns))
    if missing:
        return _source_row("stage020_price_frame_daily", False, row_count=len(data), blocking_reason="missing_columns:" + ",".join(missing))
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    end_rows = data[data["date"].eq(ANALYSIS_END)].copy()
    products = set(data["product_vt_symbol"].dropna().astype(str))
    ready = len(data) > 0 and "jd.DCE" in products and len(end_rows) > 0
    reasons: list[str] = []
    if "jd.DCE" not in products:
        reasons.append("missing_jd_product")
    if len(end_rows) == 0:
        reasons.append("not_cover_analysis_end")
    return _source_row(
        "stage020_price_frame_daily",
        ready,
        row_count=len(data),
        blocking_reason=",".join(reasons),
        detail=f"products={len(products)} end_rows={len(end_rows)}",
    )


def load_product_metadata(path: Path = PRODUCT_METADATA_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["vt_symbol", "price_tick", "volume_multiple", "margin_ratio"])
    data = _read_csv(path)
    return data


def audit_contract_specs(product_returns: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    products = sorted(set(product_returns["product_vt_symbol"].dropna().astype(str)))
    metadata_by_vt: dict[str, Any] = {}
    if not metadata.empty and "vt_symbol" in metadata.columns:
        cleaned = metadata.copy()
        if "symbol_kind" in cleaned.columns:
            product_meta = cleaned[cleaned["symbol_kind"].astype(str).eq("product_cont")].copy()
            if not product_meta.empty:
                cleaned = product_meta
        metadata_by_vt = {str(row.vt_symbol): row for row in cleaned.itertuples(index=False)}

    rows: list[dict[str, Any]] = []
    for product in products:
        meta = metadata_by_vt.get(product)
        size = _safe_float(SIZES.get(product, 0.0))
        slippage = _safe_float(SLIPPAGES.get(product, 0.0))
        margin_ratio = _safe_float(MARGIN_RATIOS.get(product, 0.0))
        price_tick = _safe_float(PRICETICKS.get(product, 0.0))
        source = "qmt_universe"
        if meta is not None:
            meta_size = _safe_float(getattr(meta, "volume_multiple", 0.0))
            meta_tick = _safe_float(getattr(meta, "price_tick", 0.0))
            meta_margin = _safe_float(getattr(meta, "margin_ratio", 0.0))
            if size <= 0 and meta_size > 0:
                size = meta_size
            if price_tick <= 0 and meta_tick > 0:
                price_tick = meta_tick
            if slippage <= 0 and meta_tick > 0:
                slippage = meta_tick
            if margin_ratio <= 0 and meta_margin > 0:
                margin_ratio = meta_margin
            source = "qmt_universe_plus_tqsdk_metadata" if product in SIZES else "tqsdk_metadata"
        reasons: list[str] = []
        if size <= 0:
            reasons.append("missing_size")
        if slippage <= 0:
            reasons.append("missing_slippage")
        if margin_ratio <= 0:
            reasons.append("missing_margin_ratio")
        rows.append(
            {
                "product_vt_symbol": product,
                "size": float(size),
                "slippage": float(slippage),
                "price_tick": float(price_tick),
                "margin_ratio": float(margin_ratio),
                "spec_source": source,
                "exact_spec_ready": len(reasons) == 0,
                "blocking_reason": ",".join(reasons),
            }
        )
    return pd.DataFrame(rows)


def _contract_to_product(contract_vt: str) -> str:
    symbol, exchange = str(contract_vt).split(".", 1)
    product = "".join(char for char in symbol if char.isalpha())
    return f"{product}.{exchange}"


def build_minute_file_index(root: Path = MINUTE_ROOT) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in root.glob("*/*/*minute_backtest.csv"):
        exchange = path.parent.name
        stem = path.name
        contract = stem.replace("_completed_minute_backtest.csv", "").replace("_minute_backtest.csv", "")
        if contract:
            index.setdefault(f"{contract}.{exchange}", path)
    return index


def audit_minute_contract_coverage(contracts: pd.Series, minute_files: dict[str, Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for contract in sorted(set(contracts.dropna().astype(str))):
        path = minute_files.get(contract)
        rows.append(
            {
                "contract_vt": contract,
                "product_vt_symbol": _contract_to_product(contract),
                "minute_file_ready": path is not None,
                "minute_file": str(path) if path is not None else "",
            }
        )
    return pd.DataFrame(rows)


def make_stage049_decision(source_table: pd.DataFrame) -> dict[str, Any]:
    blocking = source_table[~source_table["ready"].astype(bool)].copy() if not source_table.empty else pd.DataFrame()
    ready = blocking.empty and not source_table.empty
    if ready:
        decision = "stage049_stage208_true_carry_replay_ready_for_stage050_true_ledger"
        continue_after = "有。当前源依赖齐全，下一阶段可以做 Stage208 frozen signal 的当前 C9 真持仓/成交 ledger。"
    else:
        decision = "stage049_stage208_true_carry_replay_blocked_keep_readonly"
        continue_after = "有但不能直接跑真承载。先补齐阻塞源，否则会把 fallback 或默认保证金误当成策略证据。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "ready_for_true_ledger_replay": bool(ready),
        "blocking_source_ids": ",".join(blocking["source_id"].astype(str).tolist()) if not blocking.empty else "",
        "blocking_reasons": ";".join(
            f"{row.source_id}:{row.blocking_reason}" for row in blocking.itertuples(index=False)
        )
        if not blocking.empty
        else "",
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine_run": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "formal_ab_triggered": False,
        "external_research_judgment": (
            "Managed futures 与 time-series/cross-sectional momentum 资料支持独立动量收益源，"
            "但实现层必须控制交易成本、换手、保证金和再平衡；因此 Stage049 只做当前源依赖闸门，不用旧 Stage506/508 输出当证据。"
        ),
        "overfit_reflection_before": (
            "否。本阶段不调 xsmom 参数，只审计 Stage208 级真承载所需数据合同是否满足。"
        ),
        "overfit_reflection_after": (
            "否。若阻塞源未齐全，直接用默认保证金、fallback 成交或旧输出替代才是隐性过拟合/污染。"
        ),
        "continue_value_before": (
            "有。Stage048 反证日级 sleeve 后，只有一次性真承载依赖闸门能决定 xsmom 是否继续。"
        ),
        "continue_value_after": continue_after,
        "outputs": {
            "source_table": str(SOURCE_TABLE_PATH),
            "contract_spec_audit": str(CONTRACT_SPEC_AUDIT_PATH),
            "minute_coverage": str(MINUTE_COVERAGE_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    source_table: pd.DataFrame,
    contract_specs: pd.DataFrame,
    minute_coverage: pd.DataFrame,
) -> None:
    missing_specs = contract_specs[~contract_specs["exact_spec_ready"].astype(bool)].copy()
    missing_minutes = minute_coverage[~minute_coverage["minute_file_ready"].astype(bool)].copy()
    lines = [
        "# Stage049 Stage208 真承载复建闸门",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读源依赖/数据合同审计；不回测收益，不改策略，不连接 CTP，不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- time-series/cross-sectional momentum 和 managed futures 资料支持独立趋势/动量收益源。",
        "- 但实现上交易成本、换手、保证金和再平衡频率会改变结果；公开简化回测不能替代本仓库 Stage208 级 ledger。",
        "- 我的判断：若当前源依赖不完整，不能直接跑真承载，更不能用旧 Stage506/508 输出或 fallback 成交当当前证据。",
        "",
        "## Source Table",
        "",
        _md_table(source_table),
        "",
        "## Contract Spec Blocking",
        "",
        _md_table(missing_specs, max_rows=80),
        "",
        "## Minute Coverage Blocking",
        "",
        _md_table(missing_minutes, max_rows=120),
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
    source_table: pd.DataFrame,
    contract_specs: pd.DataFrame,
    minute_coverage: pd.DataFrame,
) -> None:
    missing_specs = contract_specs[~contract_specs["exact_spec_ready"].astype(bool)].copy()
    missing_minutes = minute_coverage[~minute_coverage["minute_file_ready"].astype(bool)].copy()
    text = f"""# Stage049 Stage208 真承载复建闸门

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读源依赖/数据合同审计；不回测收益，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Moskowitz/Ooi/Pedersen Time Series Momentum、AQR Demystifying Managed Futures、pysystemtrade backtesting 与成本/保证金/换手实现说明。
- 我的判断：Stage048 日级 sleeve 已经反证，xsmom 若继续只能走 Stage208 级真承载；但真承载必须先确认当前 C9 日级 PnL/保证金、Stage020 signals、产品规格、分钟成交覆盖全部齐全。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage049_stage208_true_carry_replay_gate.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage049_stage208_true_carry_gate.py`
- 新增参数：无交易参数
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- ready_for_true_ledger_replay：`{decision['ready_for_true_ledger_replay']}`
- blocking_source_ids：`{decision['blocking_source_ids']}`
- blocking_reasons：`{decision['blocking_reasons']}`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## Source Table

{_md_table(source_table)}

## Contract Spec Blocking

{_md_table(missing_specs, max_rows=80)}

## Minute Coverage Blocking

{_md_table(missing_minutes, max_rows=120)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- source_table：`{SOURCE_TABLE_PATH}`
- contract_spec_audit：`{CONTRACT_SPEC_AUDIT_PATH}`
- minute_coverage：`{MINUTE_COVERAGE_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    source_rows = [audit_current_c9_daily(), audit_xsmom_signal_daily(), audit_price_frame_daily()]
    product_returns = load_product_returns()
    metadata = load_product_metadata()
    contract_specs = audit_contract_specs(product_returns, metadata)
    spec_ready = bool(contract_specs["exact_spec_ready"].astype(bool).all()) if not contract_specs.empty else False
    spec_block = ",".join(contract_specs.loc[~contract_specs["exact_spec_ready"].astype(bool), "product_vt_symbol"].astype(str))
    source_rows.append(
        _source_row(
            "contract_specs_exact",
            spec_ready,
            row_count=len(contract_specs),
            blocking_reason=f"missing_exact_specs:{spec_block}" if spec_block else "",
            detail=f"products={len(contract_specs)}",
        )
    )
    minute_index = build_minute_file_index()
    minute_coverage = audit_minute_contract_coverage(product_returns["main_contract_vt"], minute_index)
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
    source_table = pd.DataFrame(source_rows)
    decision = make_stage049_decision(source_table)

    source_table.to_csv(SOURCE_TABLE_PATH, index=False, encoding="utf-8-sig")
    contract_specs.to_csv(CONTRACT_SPEC_AUDIT_PATH, index=False, encoding="utf-8-sig")
    minute_coverage.to_csv(MINUTE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, source_table, contract_specs, minute_coverage)
    _write_stage_record(decision, source_table, contract_specs, minute_coverage)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
