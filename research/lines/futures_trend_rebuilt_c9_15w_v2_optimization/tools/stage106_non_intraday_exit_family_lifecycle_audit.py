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
STAGE = "Stage106"
MODEL_TAG = "stage106_non_intraday_exit_family_lifecycle_audit_v2_reviewed_canonical"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage106_non_intraday_exit_family_lifecycle_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage106_non_intraday_exit_family_lifecycle_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE094_OUT = LINE_DIR / "outputs" / "stage094_stage167_closed_lot_entry_state_audit"
STAGE094_PREFIX = "rebuilt_c9_v2_stage094_stage167_closed_lot_entry_state_audit"
STAGE094_TAG = "stage094_stage167_closed_lot_entry_state_audit_v1"
CLOSED_LOTS_PATH = STAGE094_OUT / f"{STAGE094_PREFIX}_closed_lots_{STAGE094_TAG}.csv.gz"

STAGE098_DECISION_PATH = (
    LINE_DIR
    / "outputs"
    / "stage098_carryover_component_decomposition_audit"
    / "rebuilt_c9_v2_stage098_carryover_component_decomposition_audit_decision_stage098_carryover_component_decomposition_audit_v1.json"
)
STAGE099_DECISION_PATH = (
    LINE_DIR
    / "outputs"
    / "stage099_held_trend_deterioration_audit"
    / "rebuilt_c9_v2_stage099_held_trend_deterioration_audit_decision_stage099_held_trend_deterioration_audit_v1.json"
)
STAGE101_DECISION_PATH = (
    LINE_DIR
    / "outputs"
    / "stage101_underwater_entry_quality_decomposition_audit"
    / "rebuilt_c9_v2_stage101_underwater_entry_quality_decomposition_audit_decision_stage101_underwater_entry_quality_decomposition_audit_v2_panel_dd.json"
)
STAGE105_DECISION_PATH = (
    LINE_DIR
    / "outputs"
    / "stage105_open_penetration_execution_stress_audit"
    / "rebuilt_c9_v2_stage105_open_penetration_execution_stress_audit_decision_stage105_open_penetration_execution_stress_audit_v2_reviewed_sorted_unique.json"
)

LOT_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_lot_panel_{MODEL_TAG}.csv.gz"
FAMILY_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_family_summary_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
BY_START_PATH = OUT / f"{OUTPUT_PREFIX}_by_start_{MODEL_TAG}.csv"
TOP_LOSS_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_top_loss_events_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

EXTERNAL_RESEARCH = [
    {
        "source": "Rob Carver, Dynamic trend following",
        "url": "https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html",
        "finding": "Discrete trend systems separate entry, adjustment and exit rules; exit changes need lifecycle attribution before rule changes.",
    },
    {
        "source": "PriceActionLab trend-following stop-loss discussion",
        "url": "https://www.priceactionlab.com/Blog/2023/04/trend-following-stop-loss/",
        "finding": "Stop-loss changes can materially alter trade count, drawdown and right-tail retention, so loss-source evidence alone is insufficient for promotion.",
    },
    {
        "source": "freqtrade backtesting documentation",
        "url": "https://github.com/freqtrade/freqtrade/blob/develop/docs/backtesting.md",
        "finding": "Exit reason by itself does not imply positive or negative trade quality; realized lifecycle evidence is needed.",
    },
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Backtest attribution should separate signal, sizing, position accounting, costs and instrument returns before changing logic.",
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


def _read_decision(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"missing": str(path)}


def _exit_family(exit_reason: Any) -> str:
    if pd.isna(exit_reason):
        return "other"
    text = str(exit_reason)
    if "stage847_intraday" in text or "stage827_intraday" in text:
        return "intraday_stop"
    if "base_stop" in text:
        return "base_stop"
    if "prev2day_stop" in text:
        return "prev2day_stop"
    if "ma_stop" in text:
        return "ma_stop"
    if "risk_cluster" in text or "forced_margin" in text:
        return "risk_deleverage"
    if "rollover" in text:
        return "rollover"
    if "rsi_partial" in text:
        return "partial_exit"
    return "other"


def load_lots() -> tuple[pd.DataFrame, dict[str, Any]]:
    lots = pd.read_csv(CLOSED_LOTS_PATH, encoding="utf-8-sig")
    for column in [
        "realized_pnl",
        "r_multiple",
        "risk_multiplier",
        "loss_streak",
        "active_positions_before",
        "ai_product_pool_rank",
        "selected_volume",
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "holding_calendar_days",
        "portfolio_drawdown_pct",
        "stop_distance",
    ]:
        lots[column] = _numeric(lots, column)
    for column in ["entry_date", "exit_date"]:
        lots[column] = pd.to_datetime(lots[column], errors="coerce").dt.normalize()
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    lots["exit_reason"] = lots["exit_reason"].where(lots["exit_reason"].notna(), "missing_exit_reason")
    lots["exit_family"] = lots["exit_reason"].map(_exit_family)
    key_cols = ["vt_symbol", "entry_date", "exit_date", "direction", "entry_price", "exit_price", "exit_reason"]
    lots["physical_event_key"] = lots[key_cols].astype(str).agg("|".join, axis=1)
    lots["holding_bucket"] = pd.cut(
        lots["holding_calendar_days"].fillna(-1),
        bins=[-2, 0, 2, 5, 10, 20, 40, 10_000],
        labels=["0d", "1_2d", "3_5d", "6_10d", "11_20d", "21_40d", "gt40d"],
        right=True,
    ).astype(str)
    lots["entry_dd_bucket"] = pd.cut(
        lots["portfolio_drawdown_pct"].fillna(-1),
        bins=[-2, 0.0, 0.10, 0.20, 0.30, 10.0],
        labels=["dd0", "dd0_10", "dd10_20", "dd20_30", "dd_ge30"],
        right=False,
    ).astype(str)
    lots["exit_family_direction"] = lots["exit_family"].astype(str) + ":" + lots["direction"].astype(str)
    metadata = {
        "stage098_decision": _read_decision(STAGE098_DECISION_PATH),
        "stage099_decision": _read_decision(STAGE099_DECISION_PATH),
        "stage101_decision": _read_decision(STAGE101_DECISION_PATH),
        "stage105_decision": _read_decision(STAGE105_DECISION_PATH),
    }
    return lots, metadata


def summarize_group(frame: pd.DataFrame, group_name: str, group_value: str) -> dict[str, Any]:
    data = frame.copy()
    unique = data.sort_values(["physical_event_key", "requested_start_month"]).drop_duplicates("physical_event_key")
    pnl = data["realized_pnl"]
    unique_pnl = unique["realized_pnl"]
    by_start = data.groupby("requested_start_month")["realized_pnl"].sum()
    neg_abs = float(-pnl[pnl.lt(0)].sum()) if len(pnl) else 0.0
    unique_neg_abs = float(-unique_pnl[unique_pnl.lt(0)].sum()) if len(unique_pnl) else 0.0
    top_unique_loss = float((-unique_pnl.clip(upper=0.0)).max()) if len(unique_pnl) else 0.0
    return {
        "group_name": group_name,
        "group_value": group_value,
        "rows": int(len(data)),
        "start_count": int(data["requested_start_month"].nunique()) if len(data) else 0,
        "unique_physical_events": int(data["physical_event_key"].nunique()) if len(data) else 0,
        "symbol_count": int(data["vt_symbol"].nunique()) if len(data) else 0,
        "pnl_sum": float(pnl.sum()) if len(pnl) else 0.0,
        "positive_pnl_sum": float(pnl[pnl.gt(0)].sum()) if len(pnl) else 0.0,
        "negative_pnl_abs_sum": neg_abs,
        "unique_first_pnl_sum": float(unique_pnl.sum()) if len(unique_pnl) else 0.0,
        "unique_first_negative_abs_sum": unique_neg_abs,
        "negative_start_count": int(by_start.lt(0).sum()) if len(by_start) else 0,
        "negative_start_rate": _safe_div(float(by_start.lt(0).sum()), float(len(by_start))),
        "start_pnl_min": float(by_start.min()) if len(by_start) else np.nan,
        "start_pnl_median": float(by_start.median()) if len(by_start) else np.nan,
        "start_pnl_max": float(by_start.max()) if len(by_start) else np.nan,
        "top_unique_loss_share": _safe_div(top_unique_loss, unique_neg_abs),
    }


def build_summaries(lots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    family_rows: list[dict[str, Any]] = []
    condition_rows: list[dict[str, Any]] = []
    by_start_rows: list[dict[str, Any]] = []

    for col in ["exit_family", "exit_reason", "exit_family_direction"]:
        for value, group in lots.groupby(col, dropna=False, sort=True):
            row = summarize_group(group, col, str(value))
            row["candidate_scope"] = col in {"exit_reason", "exit_family_direction"}
            row["is_intraday"] = bool(group["exit_family"].astype(str).eq("intraday_stop").all())
            row["is_followup_audit_candidate"] = bool(
                row["candidate_scope"]
                and not row["is_intraday"]
                and row["pnl_sum"] <= -1_000_000.0
                and row["unique_first_pnl_sum"] <= -300_000.0
                and row["rows"] >= 50
                and row["unique_physical_events"] >= 20
                and row["start_count"] >= 8
                and row["negative_start_rate"] >= 0.65
                and (
                    pd.isna(row["top_unique_loss_share"])
                    or float(row["top_unique_loss_share"]) <= 0.35
                )
            )
            if col == "exit_reason":
                row["canonical_candidate"] = str(value)
            elif col == "exit_family_direction":
                row["canonical_candidate"] = "long_base_stop" if str(value) == "base_stop:long" else str(value)
            else:
                row["canonical_candidate"] = str(value)
            if col == "exit_family":
                family_rows.append(row)
            condition_rows.append(row)
            start_group = group.groupby("requested_start_month", as_index=False)["realized_pnl"].sum()
            for item in start_group.itertuples(index=False):
                by_start_rows.append(
                    {
                        "group_name": col,
                        "group_value": str(value),
                        "requested_start_month": item.requested_start_month,
                        "pnl_sum": float(item.realized_pnl),
                    }
                )

    diagnostics = [
        ("exit_family_direction_holding_bucket", ["exit_family_direction", "holding_bucket"]),
        ("exit_family_direction_entry_dd_bucket", ["exit_family_direction", "entry_dd_bucket"]),
    ]
    for name, cols in diagnostics:
        for key, group in lots.groupby(cols, dropna=False, sort=True):
            value = "|".join(map(str, key if isinstance(key, tuple) else (key,)))
            row = summarize_group(group, name, value)
            row["candidate_scope"] = False
            row["is_intraday"] = bool(group["exit_family"].astype(str).eq("intraday_stop").all())
            row["is_followup_audit_candidate"] = False
            condition_rows.append(row)

    top_loss = lots.sort_values("realized_pnl").head(120).copy()
    keep_cols = [
        "requested_start_month",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "holding_calendar_days",
        "holding_bucket",
        "entry_dd_bucket",
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "r_multiple",
        "exit_reason",
        "exit_family",
        "risk_multiplier",
        "loss_streak",
        "active_positions_before",
        "ai_product_pool_rank",
        "selected_volume",
        "physical_event_key",
    ]
    return (
        pd.DataFrame(family_rows).sort_values("pnl_sum"),
        pd.DataFrame(condition_rows).sort_values(["is_followup_audit_candidate", "pnl_sum"], ascending=[False, True]),
        pd.DataFrame(by_start_rows).sort_values(["group_name", "group_value", "requested_start_month"]),
        top_loss[[col for col in keep_cols if col in top_loss.columns]].copy(),
    )


def make_decision(condition_summary: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, Any]:
    candidates = condition_summary[condition_summary["is_followup_audit_candidate"].astype(bool)].copy()
    unique_candidate_count = int(candidates["canonical_candidate"].nunique()) if not candidates.empty else 0
    candidate_aliases: dict[str, list[str]] = {}
    if not candidates.empty:
        for canonical, group in candidates.groupby("canonical_candidate", dropna=False, sort=True):
            candidate_aliases[str(canonical)] = group["group_value"].astype(str).tolist()
    if not candidates.empty:
        best = candidates.sort_values(["pnl_sum", "unique_first_pnl_sum"]).iloc[0].to_dict()
        decision = "stage106_non_intraday_exit_family_broad_loss_source_for_followup_audit"
        next_step = (
            f"只允许对 `{best['group_value']}` 做一次 post-exit continuation/stop语义归因；"
            "不得直接改 base stop 或扫止损倍数、品种、方向、日期。"
        )
        continue_after = "有"
        continue_reason = "存在非日内退出族的宽样本负贡献，可作为下一阶段只读归因对象。"
        overfit_after = "否但需谨慎。Stage106 只把宽样本退出族送入下一层归因，不直接生成交易规则。"
        best_candidate = str(best["group_value"])
        candidate_rule_count = int(len(candidates))
    else:
        decision = "stage106_no_non_intraday_exit_family_followup_candidate"
        next_step = "停止按 exit_reason/holding/dd 可见字段救参；转向外生信息源或账户级组合层。"
        continue_after = "有但需换大方向"
        continue_reason = "非日内退出族没有形成足够宽的下一层归因候选。"
        overfit_after = "否。固定退出族/方向/生命周期汇总，没有按窗口或阈值搜索。"
        best_candidate = ""
        candidate_rule_count = 0
        best = {}
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "candidate_rule_count": candidate_rule_count,
        "unique_candidate_count": unique_candidate_count,
        "candidate_aliases": candidate_aliases,
        "best_candidate": best_candidate,
        "best_candidate_rows": int(best.get("rows", 0) or 0),
        "best_candidate_start_count": int(best.get("start_count", 0) or 0),
        "best_candidate_unique_physical_events": int(best.get("unique_physical_events", 0) or 0),
        "best_candidate_pnl_sum": float(best.get("pnl_sum", 0.0) or 0.0),
        "best_candidate_unique_first_pnl_sum": float(best.get("unique_first_pnl_sum", 0.0) or 0.0),
        "best_candidate_negative_start_rate": float(best.get("negative_start_rate", np.nan)),
        "best_candidate_top_unique_loss_share": float(best.get("top_unique_loss_share", np.nan)),
        "stage098_decision": str(metadata["stage098_decision"].get("decision", "")),
        "stage099_decision": str(metadata["stage099_decision"].get("decision", "")),
        "stage101_decision": str(metadata["stage101_decision"].get("decision", "")),
        "stage105_decision": str(metadata["stage105_decision"].get("decision", "")),
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
    family_summary: pd.DataFrame,
    condition_summary: pd.DataFrame,
    by_start: pd.DataFrame,
    top_loss: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    candidates = condition_summary[condition_summary["is_followup_audit_candidate"].astype(bool)].copy()
    selected_by_start = by_start[by_start["group_value"].eq(decision.get("best_candidate", ""))].copy()
    report = f"""# {STAGE} Non-Intraday Exit Family Lifecycle Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：exit_reason 只能说明触发器，不代表该触发器该被取消。Stage106 只找宽样本负贡献来源，用于下一层 post-exit/stop 语义审计，不直接改策略。

## Decision

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## Follow-up Candidates

{_md_table(candidates, 40)}

## Family Summary

{_md_table(family_summary, 80)}

## Condition Summary

{_md_table(condition_summary, 120)}

## Best Candidate By Start

{_md_table(selected_by_start, 80)}

## Top Loss Lots

{_md_table(top_loss, 120)}

## 统计口径

- 输入：Stage094 closed lots；不重新跑策略，不读取交易网关。
- 去重物理事件：`vt_symbol|entry_date|exit_date|direction|entry_price|exit_price|exit_reason`。
- 候选范围：只允许 `exit_reason` 和 `exit_family:direction` 层级进入下一阶段 follow-up audit；holding bucket 和 DD bucket 只作诊断，防止阈值救参。
- follow-up 闸门：非 intraday、PnL `<= -1,000,000`、去重代表 PnL `<= -300,000`、行数 `>=50`、去重事件 `>=20`、起点 `>=8`、负起点率 `>=65%`、最大单一去重亏损占比 `<=35%`。
- 本阶段不是 proxy，不改 stop；若出现候选，下一步也只能做一次固定 post-exit continuation/stop 语义归因。

## 过拟合反思

- 运行前：否。固定退出族/方向生命周期分解，避免在已失败的账户状态或 EOD 趋势字段上救参。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。Stage098/099/101 指向 carryover holding，但未定位到可进入下一层归因的退出族。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- lot_panel：`{LOT_PANEL_PATH}`
- family_summary：`{FAMILY_SUMMARY_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- by_start：`{BY_START_PATH}`
- top_loss_events：`{TOP_LOSS_EVENTS_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    family_summary: pd.DataFrame,
    condition_summary: pd.DataFrame,
    by_start: pd.DataFrame,
    top_loss: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage106_non_intraday_exit_family_lifecycle_audit.md"
    candidates = condition_summary[condition_summary["is_followup_audit_candidate"].astype(bool)].copy()
    selected_by_start = by_start[by_start["group_value"].eq(decision.get("best_candidate", ""))].copy()
    text = f"""# Stage106 非日内退出族生命周期审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区：`{ROOT}`
- 阶段性质：只读归因；不改策略、不跑 true engine
- 是否重要突破：否，属于下一层归因候选筛查
- 是否触发A/B：否，本阶段没有可合入策略候选

## 外部调研与判断

- 参考资料：Rob Carver dynamic trend following、PriceActionLab stop-loss trend-following discussion、freqtrade backtesting docs、pysystemtrade backtesting docs。
- 我的判断：exit_reason 不能直接等于策略 bug；必须先证明宽样本、非集中、跨起点负贡献，再进入下一层 post-exit 归因。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage106_non_intraday_exit_family_lifecycle_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：只读候选闸门：PnL `-1,000,000`、去重代表 PnL `-300,000`、行数 `50`、去重事件 `20`、起点 `8`、负起点率 `65%`、最大单事件占比 `35%`。
- 修改参数：无正式策略参数。
- 删除参数：无。

## 回测/审计参数

- 输入：`{CLOSED_LOTS_PATH}`
- 上游结论：Stage098 carryover holding dominates、Stage099 no held trend deterioration candidate、Stage101 no underwater entry candidate、Stage105 open penetration concentrated warning。
- true engine：未运行。
- 订单 API：`0`
- CTP：未连接。

## 结果摘要

- 决策：`{decision['decision']}`
- 候选数：`{decision['candidate_rule_count']}`
- canonical 候选数：`{decision['unique_candidate_count']}`
- 候选别名：`{decision['candidate_aliases']}`
- 最佳候选：`{decision['best_candidate'] or '无'}`
- 最佳候选行数：`{decision['best_candidate_rows']}`
- 最佳候选起点数：`{decision['best_candidate_start_count']}`
- 最佳候选去重物理事件：`{decision['best_candidate_unique_physical_events']}`
- 最佳候选 PnL：`{decision['best_candidate_pnl_sum']:,.2f}`
- 最佳候选去重代表 PnL：`{decision['best_candidate_unique_first_pnl_sum']:,.2f}`
- 最佳候选负起点率：`{decision['best_candidate_negative_start_rate']:.4f}`
- 最佳候选最大单事件亏损占比：`{decision['best_candidate_top_unique_loss_share']:.4f}`

## Follow-up Candidates

{_md_table(candidates, 40)}

## Family Summary

{_md_table(family_summary, 80)}

## Best Candidate By Start

{_md_table(selected_by_start, 80)}

## Top Loss Lots

{_md_table(top_loss, 80)}

## 标准回测指标

- 期末权益：不适用，本阶段只读归因未重跑策略。
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

- 运行前：否，固定退出族/方向生命周期分解，不扫品种、方向、日期或阈值。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有，用于决定下一步是否还值得沿非日内退出继续。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- 报告：`{REPORT_PATH}`
- lot_panel：`{LOT_PANEL_PATH}`
- family_summary：`{FAMILY_SUMMARY_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- by_start：`{BY_START_PATH}`
- top_loss_events：`{TOP_LOSS_EVENTS_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    source_paths = [
        CLOSED_LOTS_PATH,
        STAGE098_DECISION_PATH,
        STAGE099_DECISION_PATH,
        STAGE101_DECISION_PATH,
        STAGE105_DECISION_PATH,
    ]
    input_audit = _input_audit(source_paths)
    if not bool(input_audit[input_audit["path"].eq(str(CLOSED_LOTS_PATH))]["exists"].all()):
        raise FileNotFoundError(CLOSED_LOTS_PATH)
    lots, metadata = load_lots()
    family_summary, condition_summary, by_start, top_loss = build_summaries(lots)
    decision = make_decision(condition_summary, metadata)

    lots.to_csv(LOT_PANEL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    family_summary.to_csv(FAMILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    by_start.to_csv(BY_START_PATH, index=False, encoding="utf-8-sig")
    top_loss.to_csv(TOP_LOSS_EVENTS_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(family_summary, condition_summary, by_start, top_loss, decision)
    stage_path = write_stage_record(family_summary, condition_summary, by_start, top_loss, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"[stage106] report={REPORT_PATH}")
    print(f"[stage106] stage_record={stage_path}")


if __name__ == "__main__":
    main()
