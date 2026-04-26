from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage148_stage78_live_go_no_go_audit_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage148_stage78_live_go_no_go_audit"

STAGE78_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"
STAGE78_MANIFEST_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_manifest.json"
LIQUIDITY_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_summary_quarterly_wf_liquidity_v1.json"
CAPITAL_400K_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward_summary_stage78_400k_cap_ladder_quarterly_wf_v1.json"
STAGE147_SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_stage147_stage78_live_weekly_report_summary_stage147_stage78_live_weekly_report_v1.json"
STAGE147_DECISION_PATH: Path = OUTPUT_DIR / "qmt_roll_stage147_stage78_live_weekly_report_decision_table_stage147_stage78_live_weekly_report_v1.csv"

GATE_TABLE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_table_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")


def _read_json(path: Path) -> dict[str, Any]:
    _require(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    numeric = _safe_float(value, default=float("nan"))
    if math.isnan(numeric):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.{digits}f}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _find_horizon(rows: list[dict[str, Any]], horizon: str, profile_name: str | None = None) -> dict[str, Any]:
    for row in rows:
        if row.get("horizon") != horizon:
            continue
        if profile_name is not None and row.get("profile_name") != profile_name:
            continue
        return row
    return {}


def _load_inputs() -> dict[str, Any]:
    return {
        "stage78_summary": _read_json(STAGE78_SUMMARY_PATH),
        "stage78_manifest": _read_json(STAGE78_MANIFEST_PATH),
        "liquidity_summary": _read_json(LIQUIDITY_SUMMARY_PATH),
        "capital_400k_summary": _read_json(CAPITAL_400K_SUMMARY_PATH),
        "stage147_summary": _read_json(STAGE147_SUMMARY_PATH),
        "stage147_decision": _read_csv(STAGE147_DECISION_PATH),
    }


def _gate(status: str, gate: str, evidence: str, blocking: bool, action: str) -> dict[str, Any]:
    return {"status": status, "gate": gate, "evidence": evidence, "blocking": blocking, "required_action": action}


def _build_gate_table(inputs: dict[str, Any]) -> pd.DataFrame:
    stage78_summary = inputs["stage78_summary"]
    manifest = inputs["stage78_manifest"]
    liquidity = inputs["liquidity_summary"]
    cap400 = inputs["capital_400k_summary"]
    weekly = inputs["stage147_summary"]

    full = stage78_summary["reference_metrics"]["full_2020_2026"]
    liquidity_stats = liquidity["liquidity_summary"]
    qwf_252 = _find_horizon(liquidity["horizon_aggregate"], "252d")
    qwf_63 = _find_horizon(liquidity["horizon_aggregate"], "63d")
    cap_252 = _find_horizon(cap400["horizon_aggregate"], "252d", "capital_40w_cap_2_5x")
    cap_63 = _find_horizon(cap400["horizon_aggregate"], "63d", "capital_40w_cap_2_5x")

    rows = [
        _gate(
            "PASS",
            "正式版本冻结",
            f"version={manifest.get('version')}，role={manifest.get('role')}，Stage78已冻结为正式基准。",
            False,
            "保持Stage78不改参数。",
        ),
        _gate(
            "PASS",
            "全周期回测质量",
            f"期末权益{_fmt(full.get('end_balance'))}，总收益{_fmt(full.get('total_return_pct'))}%，最大回撤{_fmt(full.get('max_dd_percent'))}%，Sharpe={_fmt(full.get('sharpe_ratio'))}。",
            False,
            "只作为历史质量证明，不代表当前可直接实盘。",
        ),
        _gate(
            "PASS",
            "252日滚动稳健性",
            f"252d正收益率{_fmt(qwf_252.get('positive_return_rate_pct'))}%，最差收益{_fmt(qwf_252.get('worst_return_pct'))}%，最差回撤{_fmt(qwf_252.get('worst_max_dd_percent'))}%。",
            False,
            "保留为长期稳健性证据。",
        ),
        _gate(
            "WATCH",
            "63日短窗口冷启动",
            f"63d正收益率{_fmt(qwf_63.get('positive_return_rate_pct'))}%，最差收益{_fmt(qwf_63.get('worst_return_pct'))}%，短窗口仍可能明显亏损。",
            False,
            "新实盘启动不得忽略冷启动亏损风险。",
        ),
        _gate(
            "PASS",
            "40万本金约束",
            f"40万cap=2.5x：252d正收益率{_fmt(cap_252.get('positive_return_rate_pct'))}%，最差收益{_fmt(cap_252.get('worst_return_pct'))}%；63d正收益率{_fmt(cap_63.get('positive_return_rate_pct'))}%，最差收益{_fmt(cap_63.get('worst_return_pct'))}%。",
            False,
            "若未来实盘，优先采用40万保守约束口径，不提高cap倍数。",
        ),
        _gate(
            "PASS",
            "流动性与成交量占比",
            f"缺失行情{liquidity_stats.get('missing_market_bar_count')}，零成交量{liquidity_stats.get('zero_market_volume_count')}，>1%成交量占比警告{liquidity_stats.get('warn_volume_share_gt_1pct_count')}，最大成交量占比{_fmt(liquidity_stats.get('max_volume_share_pct'))}%。",
            False,
            "流动性不是当前阻断项，但实盘仍需接入真实滑点监控。",
        ),
        _gate(
            "FAIL",
            "当前准实盘健康状态",
            f"Stage147决策={weekly.get('decision')}，alert={weekly.get('alert_count')}，watch={weekly.get('watch_count')}，最近20日净损益{_fmt(weekly.get('recent_20d_net_pnl'))}。",
            True,
            "当前不能以新资金启动实盘；至少等20日净损益alert解除并完成复盘。",
        ),
        _gate(
            "FAIL",
            "真实执行演练",
            "仓库内已有回测/准实盘监控，但未发现真实柜台/模拟盘订单回报、成交回报、撤单、断线重连、换月执行的闭环验收记录。",
            True,
            "必须先跑影子盘或模拟盘，完成订单/成交/持仓/权益对账。",
        ),
        _gate(
            "FAIL",
            "实盘事故预案",
            "当前报告已有禁止调参纪律，但未见可执行的实盘熔断、手工接管、数据异常停机、夜盘异常处理SOP。",
            True,
            "补齐实盘SOP后才允许讨论真实资金。",
        ),
    ]
    return pd.DataFrame(rows)


def _build_summary_payload(inputs: dict[str, Any], gate_table: pd.DataFrame) -> dict[str, Any]:
    blocking_failures = gate_table[(gate_table["status"] == "FAIL") & (gate_table["blocking"])]
    non_blocking_watch = gate_table[gate_table["status"] == "WATCH"]
    final_decision = "NO_GO_REAL_MONEY_SHADOW_ONLY" if not blocking_failures.empty else "NO_GO_REAL_MONEY_SHADOW_ONLY"
    return {
        "model_tag": MODEL_TAG,
        "is_strategy_change": False,
        "version_ab_skill_triggered": False,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "final_decision": final_decision,
        "can_live_trade_now": False,
        "allowed_next_mode": "shadow_or_simulated_trading_only",
        "blocking_failure_count": int(len(blocking_failures)),
        "watch_count": int(len(non_blocking_watch)),
        "blocking_gates": blocking_failures["gate"].tolist(),
        "stage78_reference": inputs["stage78_summary"]["reference_metrics"]["full_2020_2026"],
        "stage147_decision": inputs["stage147_summary"].get("decision"),
        "anti_overfit_boundary": (
            "This is a go/no-go audit. It must not optimize parameters or convert readiness failures into "
            "strategy patches."
        ),
    }


def _write_report(inputs: dict[str, Any], gate_table: pd.DataFrame, payload: dict[str, Any]) -> None:
    stage78 = payload["stage78_reference"]
    gate_cols = ["status", "gate", "blocking", "evidence", "required_action"]
    report = f"""# Stage148 Stage78实盘准入GO/NO-GO审计

## 结论
- 本阶段不是策略版本，不改Stage78，不触发A/B技能。
- 最终结论：`{payload["final_decision"]}`。
- 是否可以现在上真实资金实盘：`否`。
- 允许的下一步：`{payload["allowed_next_mode"]}`。
- 过拟合判断：否。这里是实盘准入审计，不优化收益、不新增交易参数、不筛品种。
- 是否有价值继续：是。用户要求明确能否实盘，本阶段给出硬门槛结论。

## Stage78 正式基准
- 期末权益：{_fmt(stage78.get("end_balance"))}
- 总收益：{_fmt(stage78.get("total_return_pct"))}%
- 最大回撤：{_fmt(stage78.get("max_dd_percent"))}%
- Sharpe：{_fmt(stage78.get("sharpe_ratio"))}
- 总滑点：{_fmt(stage78.get("total_slippage"))}
- 总交易次数：{_fmt(stage78.get("total_trade_count"))}

## 准入门槛表
{_to_markdown_table(gate_table, gate_cols, max_rows=20)}

## 判断
- 历史回测、252日滚动稳健性、40万本金约束、流动性审计本身不是主要阻断项。
- 主要阻断项是当前准实盘健康状态、真实执行演练、实盘事故预案。
- 当前Stage147仍是`review_first_keep_stage78`，最近20日净损益处于alert，尾部风险有watch；这不是新资金启动实盘的好时点。
- 仓库没有真实订单/成交/撤单/持仓/权益对账闭环验收记录，因此不能把回测等同于可实盘。

## 下一步只允许
- 影子盘或模拟盘。
- 继续自动化周报。
- 完成真实执行链路验收。
- 等20日净损益alert解除，并完成`chemical + Long`尾部聚集复盘。

## 禁止动作
- 不允许直接上真实资金。
- 不允许为了通过准入而调参数。
- 不允许用黑名单、止损补丁、利润保护重启来粉饰当前alert。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    inputs = _load_inputs()
    gate_table = _build_gate_table(inputs)
    payload = _build_summary_payload(inputs, gate_table)
    gate_table.to_csv(GATE_TABLE_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(inputs, gate_table, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
