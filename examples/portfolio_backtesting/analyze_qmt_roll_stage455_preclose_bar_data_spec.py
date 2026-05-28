from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
STRATEGY_PATH = PROJECT_DIR / "qmt_roll_portfolio_strategy.py"
ENGINE_PATH = PROJECT_DIR / "run_qmt_roll_backtest.py"
STAGE154_SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage454_preclose_signal_bar_data_readiness_summary_stage454_preclose_signal_bar_data_readiness_v1.csv"
)
STAGE154_DOWNLOAD_PLAN_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage454_preclose_signal_bar_data_readiness_download_plan_stage454_preclose_signal_bar_data_readiness_v1.csv"
)

MODEL_TAG = "stage455_preclose_bar_data_spec_v1"
OUTPUT_PREFIX = "qmt_roll_stage455_preclose_bar_data_spec"
LINE_ID = "futures_trend_drawdown30_preserve_return"

DEPENDENCY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dependency_refs_{MODEL_TAG}.csv"
DEPENDENCY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dependency_summary_{MODEL_TAG}.csv"
DATA_SPEC_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_data_spec_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


BAR_FIELD_RE = re.compile(r"(?P<object>[A-Za-z_][A-Za-z0-9_]*)\.(?P<field>open_price|high_price|low_price|close_price)")
HISTORY_FIELD_RE = re.compile(
    r"(?P<object>history|market_data_df|df|row|today|yesterday|entry_source|channel_source|recent3|prev2_window)"
    r"\[[\"'](?P<field>open|high|low|close|volume|open_interest)[\"']\]"
)
AM_ARRAY_RE = re.compile(
    r"am\.(?P<field>open_array|high_array|low_array|close_array|volume_array|open_interest_array)"
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _current_function(line: str, previous: str) -> str:
    stripped = line.strip()
    if stripped.startswith("def "):
        return stripped.split("(", 1)[0].replace("def ", "").strip()
    return previous


def _collect_refs(path: Path, source_name: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    current_func = ""
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        current_func = _current_function(line, current_func)
        stripped = line.strip()
        for match in BAR_FIELD_RE.finditer(line):
            rows.append(
                {
                    "source": source_name,
                    "line": line_no,
                    "function": current_func,
                    "dependency_type": "bar_field",
                    "object": match.group("object"),
                    "field": match.group("field"),
                    "normalized_field": match.group("field").replace("_price", ""),
                    "code": stripped[:220],
                }
            )
        for match in HISTORY_FIELD_RE.finditer(line):
            rows.append(
                {
                    "source": source_name,
                    "line": line_no,
                    "function": current_func,
                    "dependency_type": "history_or_dataframe_column",
                    "object": match.group("object"),
                    "field": match.group("field"),
                    "normalized_field": match.group("field"),
                    "code": stripped[:220],
                }
            )
        for match in AM_ARRAY_RE.finditer(line):
            field = match.group("field")
            rows.append(
                {
                    "source": source_name,
                    "line": line_no,
                    "function": current_func,
                    "dependency_type": "array_manager_field",
                    "object": "am",
                    "field": field,
                    "normalized_field": field.replace("_array", ""),
                    "code": stripped[:220],
                }
            )
    return pd.DataFrame(rows)


def _dependency_summary(refs: pd.DataFrame) -> pd.DataFrame:
    if refs.empty:
        return pd.DataFrame()
    return (
        refs.groupby(["dependency_type", "normalized_field"], dropna=False)
        .agg(reference_count=("line", "count"), function_count=("function", "nunique"))
        .reset_index()
        .sort_values(["dependency_type", "reference_count", "normalized_field"], ascending=[True, False, True])
    )


def _data_spec(stage154_summary: pd.DataFrame) -> pd.DataFrame:
    lower_bound_coverage = float(stage154_summary["coverage_rate"].iloc[0]) if not stage154_summary.empty else float("nan")
    return pd.DataFrame(
        [
            {
                "spec_id": "A_fill_only_sensitivity",
                "purpose": "只替换成交价，继续使用完整日线bar生成信号。",
                "required_data": "订单合约在成交窗口的分钟代理价。",
                "promotion_allowed": 0,
                "why": "信号仍然使用收盘后完整日K，不能证明可部署；只能做执行敏感性审计。",
                "stage154_relation": "Stage151-153已经覆盖，均不晋级。",
            },
            {
                "spec_id": "B_close_only_preclose_signal",
                "purpose": "把当天close替换为预收盘close，但保留日线open/high/low/volume/OI。",
                "required_data": "每个主力合约日的冻结时点close和成交窗口价格。",
                "promotion_allowed": 0,
                "why": "当前策略使用当天open/high/low/volume/open_interest；只替换close会留下字段级未来信息。",
                "stage154_relation": "14:55-15:00覆盖率18.5936%只是该口径的最低覆盖，仍不足。",
            },
            {
                "spec_id": "C_full_preclose_daily_bar",
                "purpose": "构造策略在冻结时点真实可见的当日合成bar，并在同一预声明窗口成交。",
                "required_data": "每个主力合约交易日从本交易日开始到冻结时点的1分钟open/high/low/close/volume/open_interest；夜盘品种需包含归属该交易日的夜盘分钟。",
                "promotion_allowed": 1,
                "why": "这是唯一能闭合信号可见时间、bar字段和成交价的一致预收盘回放规格。",
                "stage154_relation": f"Stage154只审计14:55-15:00下界，当前下界覆盖率{lower_bound_coverage:.4%}；完整规格需要更多分钟数据。",
            },
            {
                "spec_id": "D_confirmed_daily_signal_next_event",
                "purpose": "等日线bar完全确认后，在下一真实可交易事件成交。",
                "required_data": "下一夜盘/日盘开盘分钟代理价，或真实委托回报。",
                "promotion_allowed": 1,
                "why": "时间语义干净，但 Stage141-143 已显示日线next-open路径回撤极差，需作为风险边界而非当前优化主线。",
                "stage154_relation": "不依赖Stage154预收盘覆盖；属于另一条延迟成交规格。",
            },
        ]
    )


def _stage154_summary() -> pd.DataFrame:
    if not STAGE154_SUMMARY_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(STAGE154_SUMMARY_PATH)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    strategy_refs = _collect_refs(STRATEGY_PATH, "qmt_roll_portfolio_strategy.py")
    engine_refs = _collect_refs(ENGINE_PATH, "run_qmt_roll_backtest.py")
    refs = pd.concat([strategy_refs, engine_refs], ignore_index=True)
    refs.to_csv(DEPENDENCY_PATH, index=False, encoding="utf-8-sig")

    dependency_summary = _dependency_summary(refs)
    dependency_summary.to_csv(DEPENDENCY_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    stage154 = _stage154_summary()
    data_spec = _data_spec(stage154)
    data_spec.to_csv(DATA_SPEC_PATH, index=False, encoding="utf-8-sig")

    current_bar_fields = set(refs.loc[refs["normalized_field"].isin(["open", "high", "low", "close"]), "normalized_field"])
    volume_oi_fields = set(refs.loc[refs["normalized_field"].isin(["volume", "open_interest"]), "normalized_field"])
    required_stage154_keys = int(stage154["required_key_count"].iloc[0]) if not stage154.empty else 0
    covered_stage154_keys = int(stage154["covered_key_count"].iloc[0]) if not stage154.empty else 0
    missing_stage154_keys = int(stage154["missing_key_count"].iloc[0]) if not stage154.empty else 0
    stage154_coverage = float(stage154["coverage_rate"].iloc[0]) if not stage154.empty else float("nan")

    summary = pd.DataFrame(
        [
            {
                "model_tag": MODEL_TAG,
                "strategy_ref_count": int(len(strategy_refs)),
                "engine_ref_count": int(len(engine_refs)),
                "uses_current_bar_ohlc": int({"open", "high", "low", "close"}.issubset(current_bar_fields)),
                "uses_volume_open_interest": int({"volume", "open_interest"}.issubset(volume_oi_fields)),
                "stage154_required_key_count": required_stage154_keys,
                "stage154_covered_key_count": covered_stage154_keys,
                "stage154_missing_key_count": missing_stage154_keys,
                "stage154_lower_bound_coverage_rate": stage154_coverage,
                "promotion_ready": 0,
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": "Stage155",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "full_preclose_ohlc_volume_oi_required_before_replay_no_alpha_optimization",
        "promotion_candidate": "none",
        "required_spec_for_future_promotion": "C_full_preclose_daily_bar",
        "stage154_required_key_count": required_stage154_keys,
        "stage154_covered_key_count": covered_stage154_keys,
        "stage154_missing_key_count": missing_stage154_keys,
        "stage154_lower_bound_coverage_rate": stage154_coverage,
        "outputs": {
            "dependency_refs": str(DEPENDENCY_PATH),
            "dependency_summary": str(DEPENDENCY_SUMMARY_PATH),
            "data_spec": str(DATA_SPEC_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "按C_full_preclose_daily_bar定义分片补主力合约交易日分钟OHLCVOI，再做信号bar和成交价一致的真实路径回放。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    top_refs = refs[
        refs["function"].isin(
            [
                "on_bars",
                "_generate_signal",
                "_calculate_entry_sizing",
                "_open_position",
                "_append_layer",
                "_update_layer_stop",
                "_apply_atr_mid_stop",
                "_entry_stop_price",
                "_check_regular_add_conditions",
                "_check_donchian_add_conditions",
                "_open_interest_risk_mode",
                "_volume_open_interest_risk_mode",
                "new_bars",
                "cross_limit_order_on_close",
            ]
        )
    ].copy()
    report = "\n".join(
        [
            "# Stage155 预收盘一致回放数据规格审计",
            "",
            f"- 生成时间：{decision['generated_at']}",
            "- 阶段性质：执行语义规格审计；不新增策略、不修改 Stage079/C3 交易规则。",
            "- 决策标签：`full_preclose_ohlc_volume_oi_required_before_replay_no_alpha_optimization`。",
            "",
            "## 外部调研判断",
            "",
            "- ML4T execution semantics 明确 same-bar close execution 对生产策略有 look-ahead 风险。",
            "- Backtrader 默认强调信号后通常在下一bar执行，cheat-on-close 是特殊模拟口径。",
            "- NautilusTrader 文档强调事件按时间顺序处理并校验bar时间戳约定。",
            "- TqSdk 支持 `get_kline_serial(..., 60)` 获取1分钟K，也支持回测中多行情序列。",
            "- 本地判断：一致预收盘回放必须先统一信号可见时间、策略看到的bar字段和成交价格。",
            "",
            "## 策略字段依赖摘要",
            "",
            _md_table(dependency_summary),
            "",
            "## 关键代码依赖样本",
            "",
            _md_table(top_refs[["source", "line", "function", "dependency_type", "field", "code"]], max_rows=40),
            "",
            "## 数据规格",
            "",
            _md_table(data_spec),
            "",
            "## Stage154覆盖下界",
            "",
            _md_table(summary),
            "",
            "## 结论",
            "",
            "- 当前不能再做只换成交价、只换close的预收盘候选晋级。",
            "- 未来如要晋级，必须采用 `C_full_preclose_daily_bar`：用交易日开始至冻结时点的分钟数据合成当日可见OHLC、volume、open_interest，再用同一预声明窗口成交。",
            "- Stage154 的 `14:55-15:00` 覆盖率 `18.5936%` 只是最低下界；完整规格的数据量更大，下一步应先做分片补数据可行性，而不是继续调 alpha。",
            "",
            "## 过拟合与继续价值反思",
            "",
            "- 过拟合：否。本阶段只降低执行语义自由度，不看收益曲线、不筛样本。",
            "- 继续价值：是。只有完成这个规格，后续3个月/6个月体验改善才有真实部署含义。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
