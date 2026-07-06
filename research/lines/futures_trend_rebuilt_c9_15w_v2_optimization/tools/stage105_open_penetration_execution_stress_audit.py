from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage105"
MODEL_TAG = "stage105_open_penetration_execution_stress_audit_v2_reviewed_sorted_unique"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage105_open_penetration_execution_stress_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage105_open_penetration_execution_stress_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE104_OUT = LINE_DIR / "outputs" / "stage104_intraday_stop_minute_path_slippage_audit"
STAGE104_PREFIX = "rebuilt_c9_v2_stage104_intraday_stop_minute_path_slippage_audit"
STAGE104_TAG = "stage104_intraday_stop_minute_path_slippage_audit_v2_reviewed_unique_gate"
STAGE104_EVENT_PANEL_PATH = STAGE104_OUT / f"{STAGE104_PREFIX}_event_panel_{STAGE104_TAG}.csv.gz"
STAGE104_DECISION_PATH = STAGE104_OUT / f"{STAGE104_PREFIX}_decision_{STAGE104_TAG}.json"

STRESS_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_stress_panel_{MODEL_TAG}.csv.gz"
PHYSICAL_EVENT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_physical_event_summary_{MODEL_TAG}.csv"
BY_START_PATH = OUT / f"{OUTPUT_PREFIX}_by_start_{MODEL_TAG}.csv"
BY_EXIT_REASON_PATH = OUT / f"{OUTPUT_PREFIX}_by_exit_reason_{MODEL_TAG}.csv"
BY_SYMBOL_PATH = OUT / f"{OUTPUT_PREFIX}_by_symbol_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

EXTERNAL_RESEARCH = [
    {
        "source": "Charles Schwab stop orders and price gaps",
        "url": "https://www.schwab.com/learn/story/3-order-types-market-limit-and-stop-orders",
        "finding": "A stop order becomes a market order after trigger; with gaps it may execute materially away from the stop price.",
    },
    {
        "source": "Backtrader order execution documentation",
        "url": "https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/",
        "finding": "Backtesting stop execution must distinguish open penetration from intrabar touch.",
    },
    {
        "source": "CFTC Stop Orders in Select Futures Markets",
        "url": "https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf",
        "finding": "Futures stop-market slippage can be significant and should be separately stress-tested.",
    },
    {
        "source": "backtesting.py GitHub discussion #1295",
        "url": "https://github.com/kernc/backtesting.py/discussions/1295",
        "finding": "Open/next-bar limitations in backtesting engines can alter same-bar stop-loss interpretation.",
    },
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, (str, bytes)):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
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


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    return pd.Series(default, index=frame.index, dtype=float)


def _safe_div(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return np.nan
    return float(numerator / denominator)


def load_inputs() -> tuple[pd.DataFrame, dict[str, Any]]:
    decision = json.loads(STAGE104_DECISION_PATH.read_text(encoding="utf-8"))
    if decision.get("model_tag") != STAGE104_TAG:
        raise ValueError(f"Unexpected Stage104 tag: {decision.get('model_tag')}")
    if decision.get("strategy_changed") or decision.get("true_engine_run"):
        raise ValueError("Stage104 input must be a read-only audit output")
    data = pd.read_csv(STAGE104_EVENT_PANEL_PATH, encoding="utf-8-sig")
    for column in [
        "entry_price",
        "exit_price",
        "planned_stop_price",
        "minute_first_hit_open",
        "volume",
        "size",
        "realized_pnl",
        "direction_sign",
        "minute_first_hit_open_adverse_points",
        "adverse_slippage_cash_vs_planned_stop",
    ]:
        data[column] = _numeric(data, column)
    for column in ["entry_date", "exit_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    bool_cols = ["minute_first_hit_open_beyond_stop", "minute_hit_coverage_ready", "minute_any_hit_planned_stop"]
    for column in bool_cols:
        data[column] = data[column].astype(str).str.lower().isin({"true", "1", "yes"})
    return data, decision


def build_stress_panel(data: pd.DataFrame) -> pd.DataFrame:
    panel = data.copy()
    open_event = panel["minute_first_hit_open_beyond_stop"].astype(bool)
    panel["open_penetration_event"] = open_event
    panel["stress_fill_price"] = panel["exit_price"]
    panel.loc[open_event, "stress_fill_price"] = panel.loc[open_event, "minute_first_hit_open"]
    panel["stress_delta_pnl_vs_actual"] = (
        panel["direction_sign"] * (panel["stress_fill_price"] - panel["exit_price"]) * panel["volume"] * panel["size"]
    )
    panel.loc[~open_event, "stress_delta_pnl_vs_actual"] = 0.0
    panel["stress_realized_pnl"] = panel["realized_pnl"] + panel["stress_delta_pnl_vs_actual"]
    panel["stress_is_worse_than_actual"] = panel["stress_delta_pnl_vs_actual"].lt(0.0)
    panel["open_penetration_stress_loss_abs"] = (-panel["stress_delta_pnl_vs_actual"]).clip(lower=0.0)
    panel["open_penetration_stress_gain"] = panel["stress_delta_pnl_vs_actual"].clip(lower=0.0)
    return panel


def build_physical_event_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    sort_cols = ["physical_event_key", "requested_start_month"]
    for key, group in panel.sort_values(sort_cols).groupby("physical_event_key", dropna=False, sort=True):
        open_group = group[group["open_penetration_event"]].copy()
        first = group.iloc[0]
        worst = group.loc[group["stress_delta_pnl_vs_actual"].idxmin()]
        rows.append(
            {
                "physical_event_key": key,
                "vt_symbol": first.get("vt_symbol", ""),
                "direction": first.get("direction", ""),
                "entry_date": first.get("entry_date"),
                "exit_date": first.get("exit_date"),
                "exit_reason": first.get("exit_reason", ""),
                "row_count": int(len(group)),
                "start_count": int(group["requested_start_month"].nunique()),
                "open_penetration_rows": int(len(open_group)),
                "has_open_penetration": bool(len(open_group) > 0),
                "first_representative_start": first.get("requested_start_month", ""),
                "first_representative_stress_delta": float(first["stress_delta_pnl_vs_actual"]),
                "worst_representative_start": worst.get("requested_start_month", ""),
                "worst_representative_stress_delta": float(worst["stress_delta_pnl_vs_actual"]),
                "row_stress_delta_sum": float(group["stress_delta_pnl_vs_actual"].sum()),
                "row_stress_loss_abs_sum": float(group["open_penetration_stress_loss_abs"].sum()),
                "row_stress_gain_sum": float(group["open_penetration_stress_gain"].sum()),
                "realized_pnl_sum": float(group["realized_pnl"].sum()),
                "stress_realized_pnl_sum": float(group["stress_realized_pnl"].sum()),
            }
        )
    return pd.DataFrame(rows)


def summarize(panel: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in panel.groupby(group_cols, dropna=False, sort=True):
        key_tuple = key if isinstance(key, tuple) else (key,)
        row = {col: key_tuple[idx] for idx, col in enumerate(group_cols)}
        unique_group = group.sort_values(["physical_event_key", "requested_start_month"]).drop_duplicates(
            "physical_event_key"
        )
        stress = group["stress_delta_pnl_vs_actual"]
        stress_unique = unique_group["stress_delta_pnl_vs_actual"]
        row.update(
            {
                "rows": int(len(group)),
                "unique_physical_events": int(group["physical_event_key"].nunique()),
                "open_penetration_rows": int(group["open_penetration_event"].sum()),
                "open_penetration_unique_events": int(unique_group["open_penetration_event"].sum()),
                "stress_delta_pnl_sum": float(stress.sum()),
                "stress_loss_abs_sum": float((-stress.clip(upper=0.0)).sum()),
                "stress_gain_sum": float(stress.clip(lower=0.0).sum()),
                "unique_first_stress_delta_sum": float(stress_unique.sum()),
                "unique_first_stress_loss_abs_sum": float((-stress_unique.clip(upper=0.0)).sum()),
                "unique_first_stress_gain_sum": float(stress_unique.clip(lower=0.0).sum()),
                "realized_pnl_sum": float(group["realized_pnl"].sum()),
                "stress_realized_pnl_sum": float(group["stress_realized_pnl"].sum()),
                "stress_to_actual_pnl_abs_ratio": _safe_div(
                    float((-stress.clip(upper=0.0)).sum()), float(abs(group["realized_pnl"].sum()))
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def make_decision(panel: pd.DataFrame, physical: pd.DataFrame, stage104_decision: dict[str, Any]) -> dict[str, Any]:
    stress_sum = float(panel["stress_delta_pnl_vs_actual"].sum())
    stress_loss_abs = float(panel["open_penetration_stress_loss_abs"].sum())
    stress_gain = float(panel["open_penetration_stress_gain"].sum())
    open_rows = panel[panel["open_penetration_event"]].copy()
    open_unique = physical[physical["has_open_penetration"].astype(bool)].copy()
    unique_first_stress_sum = float(physical["first_representative_stress_delta"].sum())
    unique_first_loss_abs = float((-physical["first_representative_stress_delta"].clip(upper=0.0)).sum())
    unique_worst_stress_sum = float(physical["worst_representative_stress_delta"].sum())
    unique_worst_loss_abs = float((-physical["worst_representative_stress_delta"].clip(upper=0.0)).sum())
    top_unique_loss = float((-open_unique["worst_representative_stress_delta"].clip(upper=0.0)).max()) if len(open_unique) else 0.0
    top_unique_loss_share = _safe_div(top_unique_loss, unique_worst_loss_abs)
    row_material = stress_loss_abs >= 250_000
    unique_material = unique_worst_loss_abs >= 150_000
    broad_unique = bool(len(open_unique) >= 8 and open_unique["vt_symbol"].nunique() >= 8 and top_unique_loss_share <= 0.35)
    concentrated_warning = bool(len(open_unique) > 0 and (not broad_unique))
    if row_material and unique_material and broad_unique:
        decision = "stage105_open_penetration_execution_stress_broad_material_for_proxy_stress"
        candidate_rule_count = 1
        best_candidate = "fixed_open_penetration_execution_stress"
        next_step = (
            "只允许做一次固定执行压力 proxy，把开盘穿越 fill stress 叠加到多周期曲线；"
            "不得扫止损倍数、时间、品种、方向或阈值。"
        )
        continue_after = "有"
        continue_reason = "开盘穿越压力既 material 又宽样本，可能影响水下期真实体验。"
        overfit_after = "否但进入高风险区。后续只能做预声明执行压力，不可做收益型参数搜索。"
    else:
        decision = "stage105_open_penetration_execution_stress_concentrated_warning_no_rule_candidate"
        candidate_rule_count = 0
        best_candidate = ""
        next_step = (
            "不做开盘穿越规则优化；仅把该压力作为 execution stress caveat。"
            "继续转向非日内止损的账户层暴露、持仓趋势衰退或组合相关性。"
        )
        continue_after = "有但需换主问题"
        continue_reason = "开盘穿越压力存在但集中于少数物理事件，直接做规则容易过拟合。"
        overfit_after = "否。固定 open-penetration 代理和预声明宽样本闸门，结果不够宽时停止。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "candidate_rule_count": candidate_rule_count,
        "best_candidate": best_candidate,
        "stage104_decision": str(stage104_decision.get("decision", "")),
        "stage104_open_penetration_warning": bool(stage104_decision.get("open_penetration_warning", False)),
        "rows": int(len(panel)),
        "unique_physical_events": int(panel["physical_event_key"].nunique()),
        "open_penetration_rows": int(len(open_rows)),
        "open_penetration_unique_events": int(len(open_unique)),
        "open_penetration_unique_symbols": int(open_unique["vt_symbol"].nunique()) if len(open_unique) else 0,
        "row_stress_delta_pnl_sum": stress_sum,
        "row_stress_loss_abs_sum": stress_loss_abs,
        "row_stress_gain_sum": stress_gain,
        "unique_first_stress_delta_sum": unique_first_stress_sum,
        "unique_first_stress_loss_abs_sum": unique_first_loss_abs,
        "unique_worst_stress_delta_sum": unique_worst_stress_sum,
        "unique_worst_stress_loss_abs_sum": unique_worst_loss_abs,
        "top_unique_loss_share": top_unique_loss_share,
        "row_material": row_material,
        "unique_material": unique_material,
        "broad_unique": broad_unique,
        "concentrated_warning": concentrated_warning,
        "promote_to_proxy": False,
        "promote_to_true_engine": False,
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": next_step,
        "overfit_after": overfit_after,
        "continue_after": continue_after,
        "continue_reason": continue_reason,
    }


def write_report(
    stress_panel: pd.DataFrame,
    physical: pd.DataFrame,
    by_start: pd.DataFrame,
    by_exit_reason: pd.DataFrame,
    by_symbol: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    top_rows = stress_panel.sort_values("stress_delta_pnl_vs_actual").head(40)
    top_physical = physical.sort_values("worst_representative_stress_delta").head(40)
    report = f"""# {STAGE} Open Penetration Execution Stress Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：网上和 GitHub 的通用结论一致，开盘跳空/穿越时 stop-market 的真实成交可能偏离 stop；但本地策略是否需要改，只能看本地事件是否 material 且宽样本。本阶段只做固定执行压力，不做止损参数优化。

## Decision

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## By Start

{_md_table(by_start, 120)}

## By Exit Reason

{_md_table(by_exit_reason)}

## By Symbol

{_md_table(by_symbol.sort_values("stress_delta_pnl_sum"), 120)}

## Physical Event Summary

{_md_table(top_physical, 80)}

## Top Row Stress

{_md_table(top_rows[[
        "requested_start_month",
        "vt_symbol",
        "entry_date",
        "exit_date",
        "direction",
        "exit_reason",
        "entry_price",
        "planned_stop_price",
        "exit_price",
        "minute_first_hit_open",
        "volume",
        "size",
        "realized_pnl",
        "stress_delta_pnl_vs_actual",
        "stress_realized_pnl",
    ]], 60)}

## 统计口径

- 输入：Stage104 v2 event panel；不重新读取交易引擎，不跑 true engine。
- open penetration：Stage104 标记的 `minute_first_hit_open_beyond_stop=True`。
- stress fill：只在 open penetration 行，把执行价替换为 `minute_first_hit_open`；其他行保持当前 `exit_price`，因此本阶段只隔离开盘穿越压力。
- delta：`direction_sign * (stress_fill_price - exit_price) * volume * size`；负值表示 stop-market 开盘成交代理比当前回测更差。
- unique physical event：按 `physical_event_key` 聚合，报告 first representative 与 worst representative，避免把多起点重复当成独立证据。
- 候选闸门：行级额外压力 `>=250,000`、去重 worst representative 额外压力 `>=150,000`，且 unique 事件/品种足够宽、最大单事件占比 `<=35%`。

## 过拟合反思

- 运行前：否。Stage104 已固定 open penetration warning，本阶段只做执行压力，不扫参数。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。它回答开盘穿越是否值得做执行层 proxy。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- stress_panel：`{STRESS_PANEL_PATH}`
- physical_event_summary：`{PHYSICAL_EVENT_SUMMARY_PATH}`
- by_start：`{BY_START_PATH}`
- by_exit_reason：`{BY_EXIT_REASON_PATH}`
- by_symbol：`{BY_SYMBOL_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    physical: pd.DataFrame,
    by_start: pd.DataFrame,
    by_exit_reason: pd.DataFrame,
    by_symbol: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage105_open_penetration_execution_stress_audit.md"
    text = f"""# Stage105 开盘穿越执行压力审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区：`{ROOT}`
- 阶段性质：只读执行压力；不改策略、不跑 true engine
- 是否重要突破：否
- 是否触发A/B：否，本阶段未产生策略候选

## 外部调研与判断

- 参考资料：Charles Schwab stop/gap、Backtrader order execution、CFTC futures stop orders、backtesting.py GitHub discussion。
- 我的判断：开盘穿越确实是 stop-market 执行风险，但是否能作为策略优化，必须看 material + breadth；不能因为少数事故事件就调止损倍数。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage105_open_penetration_execution_stress_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：只读审计闸门：行级额外压力 `250,000`、去重 worst 额外压力 `150,000`、最大单事件占比 `35%`。
- 修改参数：无正式策略参数。
- 删除参数：无。

## 回测/审计参数

- 输入：`{STAGE104_EVENT_PANEL_PATH}`
- Stage104 decision：`{decision['stage104_decision']}`
- true engine：未运行。
- 订单 API：`0`
- CTP：未连接。

## 结果摘要

- 决策：`{decision['decision']}`
- 样本行数：`{decision['rows']}`
- 去重物理事件数：`{decision['unique_physical_events']}`
- 开盘穿越行数：`{decision['open_penetration_rows']}`
- 开盘穿越去重物理事件数：`{decision['open_penetration_unique_events']}`
- 开盘穿越去重品种数：`{decision['open_penetration_unique_symbols']}`
- 行级 stress delta：`{decision['row_stress_delta_pnl_sum']:,.2f}`
- 行级 stress loss abs：`{decision['row_stress_loss_abs_sum']:,.2f}`
- 去重 first stress delta：`{decision['unique_first_stress_delta_sum']:,.2f}`
- 去重 first stress loss abs：`{decision['unique_first_stress_loss_abs_sum']:,.2f}`
- 去重 worst stress delta：`{decision['unique_worst_stress_delta_sum']:,.2f}`
- 去重 worst stress loss abs：`{decision['unique_worst_stress_loss_abs_sum']:,.2f}`
- 最大单事件 loss share：`{decision['top_unique_loss_share']:.4f}`
- row_material：`{decision['row_material']}`
- unique_material：`{decision['unique_material']}`
- broad_unique：`{decision['broad_unique']}`
- 候选规则数：`{decision['candidate_rule_count']}`

## By Start

{_md_table(by_start, 120)}

## By Exit Reason

{_md_table(by_exit_reason)}

## Top Physical Events

{_md_table(physical.sort_values("worst_representative_stress_delta").head(40), 80)}

## 标准回测指标

- 期末权益：不适用，本阶段只读执行压力未重跑策略。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用；本阶段统计 stop-market 开盘穿越代理压力。
- 总交易次数：不适用。
- 胜率：不适用。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 后续规划和 TODO

- {decision['next_step']}

## 过拟合反思

- 运行前：否，固定 open penetration 代理，不扫阈值/倍数/品种/方向。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有，确认执行压力是否值得进入 proxy stress。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- 报告：`{REPORT_PATH}`
- stress_panel：`{STRESS_PANEL_PATH}`
- physical_event_summary：`{PHYSICAL_EVENT_SUMMARY_PATH}`
- by_start：`{BY_START_PATH}`
- by_exit_reason：`{BY_EXIT_REASON_PATH}`
- by_symbol：`{BY_SYMBOL_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    input_audit = _input_audit([STAGE104_EVENT_PANEL_PATH, STAGE104_DECISION_PATH])
    if not bool(input_audit["exists"].all()):
        raise FileNotFoundError("Stage104 v2 input missing")
    data, stage104_decision = load_inputs()
    stress_panel = build_stress_panel(data)
    physical = build_physical_event_summary(stress_panel)
    by_start = summarize(stress_panel, ["requested_start_month"]).sort_values("requested_start_month")
    by_exit_reason = summarize(stress_panel, ["exit_reason"]).sort_values("stress_delta_pnl_sum")
    by_symbol = summarize(stress_panel, ["vt_symbol"]).sort_values("stress_delta_pnl_sum")
    decision = make_decision(stress_panel, physical, stage104_decision)

    stress_panel.to_csv(STRESS_PANEL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    physical.to_csv(PHYSICAL_EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    by_start.to_csv(BY_START_PATH, index=False, encoding="utf-8-sig")
    by_exit_reason.to_csv(BY_EXIT_REASON_PATH, index=False, encoding="utf-8-sig")
    by_symbol.to_csv(BY_SYMBOL_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(stress_panel, physical, by_start, by_exit_reason, by_symbol, decision)
    stage_path = write_stage_record(physical, by_start, by_exit_reason, by_symbol, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"[stage105] report={REPORT_PATH}")
    print(f"[stage105] stage_record={stage_path}")


if __name__ == "__main__":
    main()
