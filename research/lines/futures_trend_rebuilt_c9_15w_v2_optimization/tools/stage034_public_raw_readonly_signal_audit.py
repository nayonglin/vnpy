from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage034"
MODEL_TAG = "stage034_public_raw_readonly_signal_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage034_public_raw_readonly_signal_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage034_public_raw_readonly_signal_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE033_DIR = LINE_DIR / "outputs" / "stage033_public_raw_numeric_binding_readiness_audit"
BINDING_ROWS_IN = (
    STAGE033_DIR
    / "rebuilt_c9_v2_stage033_public_raw_numeric_binding_readiness_audit_binding_rows_"
    "stage033_public_raw_numeric_binding_readiness_audit_v1.csv"
)

LOT_PANEL_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_signal_panel_{MODEL_TAG}.csv"
STATE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MIN_CANDIDATE_LOTS = 20
MIN_CANDIDATE_YEARS = 4
MIN_CANDIDATE_PRODUCTS = 4

HYPOTHESIS_SPECS = [
    {
        "hypothesis_id": "H1_supply_member_alignment",
        "candidate_state": "both_support",
        "expected_role": "high_quality_add_risk_context",
        "economic_hypothesis": "仓单供应压力与会员净持仓流同时支持交易方向，代表供需与资金结构同向。",
    },
    {
        "hypothesis_id": "H2_participation_without_alignment",
        "candidate_state": "not_participation_without_full_alignment",
        "expected_role": "avoid_crowded_unconfirmed_context",
        "economic_hypothesis": "成交参与上升但供需/会员未共同支持时，可能是拥挤或噪声；非该状态才可能保留右尾。",
    },
    {
        "hypothesis_id": "H3_full_support_rising_volume",
        "candidate_state": "full_support_rising_volume",
        "expected_role": "super_quality_context",
        "economic_hypothesis": "供需、会员净持仓与成交参与三者同时同向，才可能是超高质量加风险上下文。",
    },
]


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
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _num_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index)
    return _to_num(frame[column])


def _first_last_delta(frame: pd.DataFrame, value_col: str) -> tuple[float, float, float]:
    valid = frame[["preentry_trading_day_offset", value_col]].copy()
    valid["preentry_trading_day_offset"] = _to_num(valid["preentry_trading_day_offset"])
    valid[value_col] = _to_num(valid[value_col])
    valid = valid.dropna(subset=["preentry_trading_day_offset", value_col]).sort_values("preentry_trading_day_offset", ascending=False)
    if valid.empty:
        return np.nan, np.nan, np.nan
    first = float(valid[value_col].iloc[0])
    last = float(valid[value_col].iloc[-1])
    return first, last, last - first


def _state_from_support(value: float, positive_support: bool) -> str:
    if pd.isna(value):
        return "insufficient"
    if abs(float(value)) < 1e-12:
        return "neutral"
    if positive_support:
        return "support" if value > 0 else "headwind"
    return "support" if value < 0 else "headwind"


def build_lot_signal_panel(binding_rows: pd.DataFrame) -> pd.DataFrame:
    rows = binding_rows.copy()
    rows["numeric_binding_ready"] = rows["numeric_binding_ready"].astype(str).str.lower().isin(["true", "1", "1.0"])
    rows = rows[rows["numeric_binding_ready"]].copy()
    rows["entry_date"] = pd.to_datetime(rows["entry_date"], errors="coerce").dt.normalize()
    rows["realized_pnl"] = _to_num(rows.get("realized_pnl", 0.0)).fillna(0.0)
    rows["right_tail_top10"] = _to_num(rows.get("right_tail_top10", 0)).fillna(0).astype(int)

    panel_rows: list[dict[str, Any]] = []
    for lot_id, group in rows.groupby("lot_id", sort=True):
        base = group.iloc[0]
        direction = str(base.get("direction", ""))
        direction_sign = 1.0 if direction == "long" else -1.0 if direction == "short" else np.nan

        member = group[group["source_family"].astype(str).eq("member_rank")].copy()
        warehouse = group[group["source_family"].astype(str).eq("warehouse")].copy()
        member["member_net_oi"] = _to_num(member.get("member_rank_long_oi_sum", np.nan)) - _to_num(
            member.get("member_rank_short_oi_sum", np.nan)
        )
        member_net_first, member_net_last, member_net_delta = _first_last_delta(member, "member_net_oi")
        volume_first, volume_last, volume_delta = _first_last_delta(member, "member_rank_volume_sum")

        warehouse["warehouse_qty"] = _num_column(warehouse, "warehouse_receipt_qty_sum").combine_first(
            _num_column(warehouse, "warehouse_wbill_qty_sum")
        )
        warehouse_first, warehouse_last, warehouse_delta = _first_last_delta(warehouse, "warehouse_qty")

        member_directional_delta = direction_sign * member_net_delta if not pd.isna(direction_sign) else np.nan
        supply_directional_delta = direction_sign * warehouse_delta if not pd.isna(direction_sign) else np.nan
        supply_state = _state_from_support(supply_directional_delta, positive_support=False)
        member_state = _state_from_support(member_directional_delta, positive_support=True)
        if pd.isna(volume_delta):
            volume_state = "insufficient"
        elif volume_delta > 0:
            volume_state = "rising"
        elif volume_delta < 0:
            volume_state = "falling"
        else:
            volume_state = "flat"

        if supply_state == "support" and member_state == "support":
            h1 = "both_support"
        elif supply_state == "headwind" and member_state == "headwind":
            h1 = "both_headwind"
        elif "insufficient" in {supply_state, member_state}:
            h1 = "insufficient"
        else:
            h1 = "mixed_or_neutral"

        h2 = (
            "participation_without_full_alignment"
            if volume_state == "rising" and h1 != "both_support"
            else "not_participation_without_full_alignment"
            if volume_state != "insufficient"
            else "insufficient"
        )
        h3 = "full_support_rising_volume" if h1 == "both_support" and volume_state == "rising" else "not_full_support_rising_volume"
        if h1 == "insufficient" or volume_state == "insufficient":
            h3 = "insufficient"

        panel_rows.append(
            {
                "lot_id": str(lot_id),
                "vt_symbol": str(base.get("vt_symbol", "")),
                "product_root": str(base.get("product_root", "")),
                "direction": direction,
                "entry_date": base.get("entry_date"),
                "entry_year": int(pd.Timestamp(base.get("entry_date")).year) if pd.notna(base.get("entry_date")) else 0,
                "realized_pnl": float(base.get("realized_pnl", 0.0)),
                "right_tail_top10": int(base.get("right_tail_top10", 0)),
                "direction_sign": direction_sign,
                "member_net_oi_first": member_net_first,
                "member_net_oi_last": member_net_last,
                "member_net_oi_delta_7d": member_net_delta,
                "member_net_oi_directional_delta": member_directional_delta,
                "member_volume_first": volume_first,
                "member_volume_last": volume_last,
                "member_volume_delta_7d": volume_delta,
                "warehouse_qty_first": warehouse_first,
                "warehouse_qty_last": warehouse_last,
                "warehouse_qty_delta_7d": warehouse_delta,
                "supply_directional_delta": supply_directional_delta,
                "supply_state": supply_state,
                "member_net_oi_state": member_state,
                "member_volume_state": volume_state,
                "H1_supply_member_alignment": h1,
                "H2_participation_without_alignment": h2,
                "H3_full_support_rising_volume": h3,
                "strategy_rule_allowed": False,
                "true_engine_allowed": False,
            }
        )
    return pd.DataFrame(panel_rows).sort_values(["entry_date", "lot_id"]).reset_index(drop=True)


def summarize_signal_states(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if panel.empty:
        return pd.DataFrame()
    for spec in HYPOTHESIS_SPECS:
        hypothesis = spec["hypothesis_id"]
        for state, group in panel.groupby(hypothesis, sort=True):
            yearly = group.groupby("entry_year", as_index=False).agg(year_pnl=("realized_pnl", "sum"))
            rows.append(
                {
                    "hypothesis_id": hypothesis,
                    "hypothesis_state": state,
                    "expected_role": spec["expected_role"],
                    "economic_hypothesis": spec["economic_hypothesis"],
                    "lot_count": int(group["lot_id"].nunique()),
                    "product_count": int(group["product_root"].nunique()),
                    "year_count": int(group["entry_year"].nunique()),
                    "net_pnl": float(group["realized_pnl"].sum()),
                    "mean_pnl": float(group["realized_pnl"].mean()),
                    "bad_lot_count": int((group["realized_pnl"] < 0).sum()),
                    "bad_lot_rate": float((group["realized_pnl"] < 0).mean()),
                    "right_tail_lot_count": int(group["right_tail_top10"].sum()),
                    "positive_year_count": int((yearly["year_pnl"] > 0).sum()),
                    "min_year_pnl": float(yearly["year_pnl"].min()) if not yearly.empty else np.nan,
                    "max_year_pnl": float(yearly["year_pnl"].max()) if not yearly.empty else np.nan,
                    "candidate_state": spec["candidate_state"],
                    "is_candidate_state": state == spec["candidate_state"],
                    "strategy_rule_allowed": False,
                    "true_engine_allowed": False,
                }
            )
    return pd.DataFrame(rows).sort_values(["hypothesis_id", "hypothesis_state"]).reset_index(drop=True)


def evaluate_readonly_candidates(state_summary: pd.DataFrame) -> pd.DataFrame:
    if state_summary.empty:
        return pd.DataFrame()
    out = state_summary.copy()
    out["sample_gate_pass"] = (
        out["lot_count"].ge(MIN_CANDIDATE_LOTS)
        & out["year_count"].ge(MIN_CANDIDATE_YEARS)
        & out["product_count"].ge(MIN_CANDIDATE_PRODUCTS)
    )
    out["pnl_gate_pass"] = out["net_pnl"].gt(0) & out["min_year_pnl"].ge(0)
    out["right_tail_protected"] = out["right_tail_lot_count"].gt(0)
    out["readonly_candidate_allowed"] = (
        out["is_candidate_state"]
        & out["sample_gate_pass"]
        & out["pnl_gate_pass"]
        & out["right_tail_protected"]
        & ~out["strategy_rule_allowed"].astype(bool)
        & ~out["true_engine_allowed"].astype(bool)
    )
    reasons: list[str] = []
    for row in out.to_dict("records"):
        blocked: list[str] = []
        if not bool(row["is_candidate_state"]):
            blocked.append("not_predeclared_candidate_state")
        if not bool(row["sample_gate_pass"]):
            blocked.append("sample_gate_failed")
        if not bool(row["pnl_gate_pass"]):
            blocked.append("pnl_or_min_year_gate_failed")
        if not bool(row["right_tail_protected"]):
            blocked.append("right_tail_not_protected")
        reasons.append(",".join(blocked))
    out["candidate_blocking_reasons"] = reasons
    return out


def make_readonly_signal_decision(panel: pd.DataFrame, candidates: pd.DataFrame) -> dict[str, Any]:
    readonly_count = int(candidates["readonly_candidate_allowed"].astype(bool).sum()) if not candidates.empty else 0
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": (
            "stage034_public_raw_readonly_candidates_found_need_proxy_audit_no_rule"
            if readonly_count > 0
            else "stage034_public_raw_readonly_signal_no_stable_candidate_no_rule"
        ),
        "best_next_direction": (
            "fixed_candidate_proxy_audit_no_true_engine"
            if readonly_count > 0
            else "stop_public_raw_signal_or_wait_external_data"
        ),
        "lot_count": int(panel["lot_id"].nunique()) if not panel.empty and "lot_id" in panel.columns else 0,
        "readonly_candidate_count": readonly_count,
        "immediate_strategy_candidate_count": 0,
        "proxy_audit_allowed_next": readonly_count > 0,
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Inventory, carry and hedging-pressure literature supports theory-grounded commodity signals, "
            "but Stage034 still treats them as predeclared read-only states. A proxy/engine stage is allowed only "
            "if cross-year, cross-product and right-tail gates pass."
        ),
        "overfit_reflection_before": (
            "否。Stage034 预声明固定经济语义和闸门，不按结果新增阈值、日期、品种或方向。"
        ),
        "overfit_reflection_after": (
            "否。输出最多是 readonly candidate；策略规则、true engine、A/B 和订单 API 仍全部禁止。"
        ),
        "continue_value_before": (
            "有。Stage033 已证明数值字段 ready，本阶段判断是否有值得继续 proxy 的稳定外生信息。"
        ),
        "continue_value_after": (
            "有候选则进入固定 proxy audit；无候选则停止公开 raw 策略化路线，转授权 orderflow/期权链/执行回放。"
        ),
    }


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _write_report(decision: dict[str, Any], candidates: pd.DataFrame, state_summary: pd.DataFrame) -> None:
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage034 公开 raw 只读信号审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- lot_count：`{decision['lot_count']}`",
        f"- readonly_candidate_count：`{decision['readonly_candidate_count']}`",
        f"- proxy_audit_allowed_next：`{decision['proxy_audit_allowed_next']}`",
        "- 本阶段不回测、不写真引擎、不触发 A/B、不调用订单 API。",
        "",
        "## Candidate Summary",
        "",
        _md_table(candidates, max_rows=80),
        "",
        "## State Summary",
        "",
        _md_table(state_summary, max_rows=120),
        "",
        "## 外部调研与判断",
        "",
        "- 商品库存、carry、hedging pressure 和理论约束的 ML 特征都有公开研究支持，但都要求跨样本、跨品种、右尾保护和经济语义先行。",
        "- 本阶段没有使用收益反推新阈值；只检查预声明状态是否值得进入下一步固定 proxy。",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{timestamp}_stage034_public_raw_readonly_signal_audit.md"
    lines = [
        "# Stage034 公开 raw 只读信号审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{decision['generated_at']}",
        "- 阶段性质：只读信号稳定性审计；不回测、不改策略、不连接 CTP、不调用下单",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 参考库存/basis/carry、hedging pressure、商品期货理论约束机器学习相关公开资料。",
        "- 我的判断：公开 raw 数值字段有经济语义，但只有通过固定跨年/跨品种/右尾闸门后，才值得做下一步 proxy；本阶段不直接产生策略。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(PROJECT_DIR)}`",
        "- 新增测试：`tests/test_rebuilt_c9_v2_stage034_public_raw_readonly_signal_audit.py`",
        "- 新增参数：`MIN_CANDIDATE_LOTS=20`、`MIN_CANDIDATE_YEARS=4`、`MIN_CANDIDATE_PRODUCTS=4`；这些是只读样本门槛，不是交易参数。",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 结果",
        "",
        f"- lot_count：`{decision['lot_count']}`",
        f"- readonly_candidate_count：`{decision['readonly_candidate_count']}`",
        f"- immediate_strategy_candidate_count：`{decision['immediate_strategy_candidate_count']}`",
        f"- proxy_audit_allowed_next：`{decision['proxy_audit_allowed_next']}`",
        f"- 决策：`{decision['decision']}`",
        f"- 下一方向：`{decision['best_next_direction']}`",
        "",
        "## 输出文件",
        "",
        f"- lot_signal_panel：`{LOT_PANEL_OUT}`",
        f"- state_summary：`{STATE_SUMMARY_OUT}`",
        f"- candidate_summary：`{CANDIDATE_SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        f"- report：`{REPORT_OUT}`",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前判断：{decision['overfit_reflection_before']}",
        f"- 运行后判断：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前判断：{decision['continue_value_before']}",
        f"- 运行后判断：{decision['continue_value_after']}",
        "",
        "## 合入建议",
        "",
        "- 更新本线 `LINE.md`：是。",
        "- 更新 `research/registry.md`：是。",
        "- 追加根目录 `memory.md/back_log.md`：否，除非下一步 proxy/engine 有重要突破。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    binding_rows = _read_csv(BINDING_ROWS_IN)
    panel = build_lot_signal_panel(binding_rows)
    state_summary = summarize_signal_states(panel)
    candidates = evaluate_readonly_candidates(state_summary)
    decision = make_readonly_signal_decision(panel, candidates)

    panel.to_csv(LOT_PANEL_OUT, index=False, encoding="utf-8-sig")
    state_summary.to_csv(STATE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    candidates.to_csv(CANDIDATE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    _write_report(decision, candidates, state_summary)
    stage_record = _write_stage_record(decision)

    decision["outputs"] = {
        "lot_signal_panel": LOT_PANEL_OUT,
        "state_summary": STATE_SUMMARY_OUT,
        "candidate_summary": CANDIDATE_SUMMARY_OUT,
        "decision": DECISION_OUT,
        "report": REPORT_OUT,
        "stage_record": stage_record,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
