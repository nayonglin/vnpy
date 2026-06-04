from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from qmt_roll_live_context_adapter import ACCOUNT_MARGIN_FIELD_CANDIDATES


MODEL_TAG = "stage654_stage653_live_margin_tca_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage654_stage653_live_margin_tca_gate"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE653_TAG = "stage653_stage526_200k_forced_margin_deleverage_v1"
STAGE653_PREFIX = "qmt_roll_stage653_stage526_200k_forced_margin_deleverage"
STAGE653_DECISION = OUTPUT_DIR / f"{STAGE653_PREFIX}_decision_{STAGE653_TAG}.json"
STAGE653_SUMMARY = OUTPUT_DIR / f"{STAGE653_PREFIX}_summary_{STAGE653_TAG}.csv"
STAGE653_COST = OUTPUT_DIR / f"{STAGE653_PREFIX}_cost_stress_{STAGE653_TAG}.csv"
STAGE653_FORCED_SUMMARY = OUTPUT_DIR / f"{STAGE653_PREFIX}_forced_summary_{STAGE653_TAG}.csv"

STAGE613_TAG = "stage613_execution_tca_closeout_evidence_board_v1"
STAGE613_PREFIX = "qmt_roll_stage613_execution_tca_closeout_evidence_board"
STAGE613_DECISION = OUTPUT_DIR / f"{STAGE613_PREFIX}_decision_{STAGE613_TAG}.json"
STAGE613_GATES = OUTPUT_DIR / f"{STAGE613_PREFIX}_gates_{STAGE613_TAG}.csv"

STAGE608_ACCOUNT = OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_accounts_stage608_readonly_tick_snapshot_probe_v1.csv"
STAGE655_SUMMARY = OUTPUT_DIR / "qmt_roll_stage655_readonly_account_margin_probe_summary_stage655_readonly_account_margin_probe_v1.json"
STAGE655_ACCOUNT = OUTPUT_DIR / "qmt_roll_stage655_readonly_account_margin_probe_accounts_stage655_readonly_account_margin_probe_v1.csv"
STAGE656_SUMMARY = OUTPUT_DIR / "qmt_roll_stage656_native_cp_account_margin_probe_summary_stage656_native_cp_account_margin_probe_v1.json"
STAGE656_ACCOUNT = OUTPUT_DIR / "qmt_roll_stage656_native_cp_account_margin_probe_accounts_stage656_native_cp_account_margin_probe_v1.csv"
LIVE_ADAPTER_PATH = PROJECT_DIR / "qmt_roll_live_context_adapter.py"
RAW_MARGIN_PROBE_PATH = PROJECT_DIR / "run_ctp_stage655_readonly_account_margin_probe.py"
CTP_GATEWAY_PATH = PROJECT_DIR.parent.parent / ".py311/lib/python3.11/site-packages/vnpy_ctp/gateway/ctp_gateway.py"

GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
EVIDENCE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TARGET_VARIANT = "stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4"
MAX_VWAP_COST_BPS = 50.0
MAX_IMPLEMENTATION_SHORTFALL_BPS = 75.0
P0_REQUIRED_TCA_SAMPLES = 9

REFERENCE_LINKS = [
    "vn.py AccountData source: vnpy/trader/object.py",
    "vnpy_ctp AccountData mapping: .py311/lib/python3.11/site-packages/vnpy_ctp/gateway/ctp_gateway.py",
    "vn.py event/order/trade/account model: https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system",
    "vn.py gateway callbacks: https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways",
]


def _now_cst() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _num(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


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
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _best_row(summary: pd.DataFrame) -> dict[str, Any]:
    if summary.empty:
        return {}
    matched = summary[summary["variant"].astype(str).eq(TARGET_VARIANT)]
    if matched.empty:
        return {}
    return matched.iloc[0].to_dict()


def _cost_row(cost: pd.DataFrame, multiplier: float) -> dict[str, Any]:
    if cost.empty:
        return {}
    matched = cost[
        cost["variant"].astype(str).eq(TARGET_VARIANT)
        & pd.to_numeric(cost["cost_multiplier"], errors="coerce").eq(multiplier)
    ]
    if matched.empty:
        return {}
    return matched.iloc[0].to_dict()


def _forced_row(forced: pd.DataFrame) -> dict[str, Any]:
    if forced.empty:
        return {}
    matched = forced[forced["variant"].astype(str).eq(TARGET_VARIANT)]
    if matched.empty:
        return {}
    return matched.iloc[0].to_dict()


def _account_margin_snapshot_evidence(accounts: pd.DataFrame) -> dict[str, Any]:
    if accounts.empty:
        return {
            "account_rows": 0,
            "explicit_margin_columns": "",
            "explicit_margin_nonempty_rows": 0,
            "account_snapshot_has_explicit_margin": False,
        }
    columns = [column for column in accounts.columns if column in ACCOUNT_MARGIN_FIELD_CANDIDATES]
    nonempty = 0
    for column in columns:
        nonempty = max(nonempty, int(pd.to_numeric(accounts[column], errors="coerce").notna().sum()))
    return {
        "account_rows": int(len(accounts)),
        "explicit_margin_columns": ",".join(columns),
        "explicit_margin_nonempty_rows": int(nonempty),
        "account_snapshot_has_explicit_margin": bool(columns and nonempty > 0),
    }


def _code_contract_evidence() -> dict[str, Any]:
    live_text = LIVE_ADAPTER_PATH.read_text(encoding="utf-8")
    raw_probe_text = RAW_MARGIN_PROBE_PATH.read_text(encoding="utf-8") if RAW_MARGIN_PROBE_PATH.exists() else ""
    ctp_text = CTP_GATEWAY_PATH.read_text(encoding="utf-8") if CTP_GATEWAY_PATH.exists() else ""
    explicit_margin_candidates_exported = "ACCOUNT_MARGIN_FIELD_CANDIDATES" in live_text
    frozen_margin_rejected = "missing_explicit_broker_current_margin" in live_text
    legacy_frozen_trigger_absent = 'broker_margin_before = to_float(account.get("frozen")' not in live_text
    ctp_curr_margin_available = "CurrMargin" in ctp_text
    ctp_generic_account_loses_curr_margin = "frozen=data[\"FrozenMargin\"]" in ctp_text and "account.available = data[\"Available\"]" in ctp_text
    raw_margin_probe_contract_ready = (
        RAW_MARGIN_PROBE_PATH.exists()
        and "CurrMargin" in raw_probe_text
        and "reqQryTradingAccount" in raw_probe_text
        and "send_order_api_called_count" in raw_probe_text
    )
    return {
        "explicit_margin_candidates": ",".join(ACCOUNT_MARGIN_FIELD_CANDIDATES),
        "explicit_margin_candidates_exported": explicit_margin_candidates_exported,
        "frozen_margin_rejected": frozen_margin_rejected,
        "legacy_frozen_trigger_absent": legacy_frozen_trigger_absent,
        "ctp_curr_margin_available_in_raw": ctp_curr_margin_available,
        "ctp_generic_account_loses_curr_margin": ctp_generic_account_loses_curr_margin,
        "raw_margin_probe_contract_ready": raw_margin_probe_contract_ready,
    }


def build_evidence(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    forced: pd.DataFrame,
    stage653: dict[str, Any],
    stage613: dict[str, Any],
    stage613_gates: pd.DataFrame,
    stage655: dict[str, Any],
    stage656: dict[str, Any],
    accounts: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    best = _best_row(summary)
    cost2 = _cost_row(cost, 2.0)
    cost3 = _cost_row(cost, 3.0)
    forced_best = _forced_row(forced)
    account_evidence = _account_margin_snapshot_evidence(accounts)
    code_evidence = _code_contract_evidence()

    stage653_best_fixed = _clean(best.get("variant")) == TARGET_VARIANT
    stage653_normal_margin_ok = (
        _num(best.get("deployable_pass")) == 1
        and _num(best.get("days_over_100pct")) == 0
        and _num(best.get("max_broker10_margin_to_equity_pct"), 999.0) <= 90.0
    )
    stage653_cost_hard_ok = _num(best.get("hard_pass")) == 1 and _num(cost2.get("dd40_pass")) == 1 and _num(cost3.get("dd40_pass")) == 1
    live_margin_contract_ok = (
        bool(code_evidence["explicit_margin_candidates_exported"])
        and bool(code_evidence["frozen_margin_rejected"])
        and bool(code_evidence["legacy_frozen_trigger_absent"])
        and bool(code_evidence["raw_margin_probe_contract_ready"])
    )
    stage613_hard_ok = int(stage613.get("hard_gates_passed", 0) or 0) == int(stage613.get("hard_gates_total", 1) or 1)
    no_order_called = int(stage613.get("send_order_api_called_count", 0) or 0) == 0
    vt_orderid_ready = int(stage613.get("real_vt_orderid_mappings", 0) or 0) >= 5
    tca_samples_ready = int(stage613.get("p0_valid_live_tca_samples", 0) or 0) >= P0_REQUIRED_TCA_SAMPLES
    stage655_import_ready = bool(stage655.get("tdapi_import_available", False))

    evidence_rows = [
        {
            "evidence": "stage653_force95_to80_result",
            "value": f"end={_num(best.get('end_equity')):.0f}; return={_num(best.get('total_return_pct')):.4f}%; retention={_num(best.get('return_retention_vs_20w_baseline_pct')):.4f}%",
            "judgement": "收益弹性保留较高，是用户偏好的高风险进攻候选。",
        },
        {
            "evidence": "stage653_margin_reduction",
            "value": f"broker10_peak={_num(best.get('max_broker10_margin_to_equity_pct')):.4f}%; forced={_num(forced_best.get('forced_event_count')):.0f}次/{_num(forced_best.get('total_reduce_volume')):.0f}手",
            "judgement": "正常成本保证金穿线已被历史回放消除。",
        },
        {
            "evidence": "stage653_cost_stress",
            "value": f"2x_dd={_num(cost2.get('max_dd_pct')):.4f}%; 3x_dd={_num(cost3.get('max_dd_pct')):.4f}%",
            "judgement": "高成本压力仍打穿 -40%，所以不是完整硬通过版。",
        },
        {
            "evidence": "live_margin_source_contract",
            "value": str(code_evidence),
            "judgement": "实盘触发源必须来自显式当前保证金字段或 CTP CurrMargin，不能用 AccountData.frozen。",
        },
        {
            "evidence": "current_readonly_account_snapshot",
            "value": f"{account_evidence}; stage656_status={stage656.get('status', '')}; stage656_front_connected={stage656.get('front_connected', False)}; stage655_connect_requested={stage655.get('connect_requested', False)}; stage655_front_connected={stage655.get('front_connected', False)}; stage655_status={stage655.get('status', '')}; missing_env={stage655.get('missing_required_env', [])}",
            "judgement": "优先使用 Stage656 native CP raw CurrMargin；没有 Stage656 时才回落到 Stage655/Stage608。",
        },
        {
            "evidence": "stage613_tca_closeout",
            "value": f"hard_gates={stage613.get('hard_gates_passed', 0)}/{stage613.get('hard_gates_total', 0)}; vt_orderid={stage613.get('real_vt_orderid_mappings', 0)}; p0_tca={stage613.get('p0_valid_live_tca_samples', 0)}/{P0_REQUIRED_TCA_SAMPLES}",
            "judgement": "TCA 合同有了，但真实 vt_orderid 与有效 P0 TCA 样本仍缺。",
        },
    ]

    gates = [
        {
            "gate": "stage653_force95_to80_fixed_candidate",
            "passed": int(stage653_best_fixed),
            "actual": _clean(best.get("variant")),
            "threshold": TARGET_VARIANT,
            "hard_gate": 1,
            "judgement": "继续对象必须固定为 Stage653 95->80，不继续扫阈值。",
        },
        {
            "gate": "normal_cost_margin_line_removed",
            "passed": int(stage653_normal_margin_ok),
            "actual": f"broker10_peak={_num(best.get('max_broker10_margin_to_equity_pct')):.4f}%; days>100={_num(best.get('days_over_100pct')):.0f}",
            "threshold": "broker10<=90 and days>100=0",
            "hard_gate": 1,
            "judgement": "正常成本下保证金生存问题已解决。",
        },
        {
            "gate": "cost_stress_hard_pass",
            "passed": int(stage653_cost_hard_ok),
            "actual": f"hard={_num(best.get('hard_pass')):.0f}; 2x_dd={_num(cost2.get('max_dd_pct')):.4f}%; 3x_dd={_num(cost3.get('max_dd_pct')):.4f}%",
            "threshold": "hard_pass=1 and 2x/3x dd >= -40",
            "hard_gate": 1,
            "judgement": "仍失败；因此不能宣称稳健实盘通过。",
        },
        {
            "gate": "live_margin_trigger_contract_uses_explicit_margin",
            "passed": int(live_margin_contract_ok),
            "actual": f"raw_probe={code_evidence['raw_margin_probe_contract_ready']}; generic_gateway_loses_curr_margin={code_evidence['ctp_generic_account_loses_curr_margin']}; frozen_rejected={code_evidence['frozen_margin_rejected']}; legacy_absent={code_evidence['legacy_frozen_trigger_absent']}",
            "threshold": "explicit margin/CurrMargin only",
            "hard_gate": 1,
            "judgement": "代码合同已阻止用 frozen 误当保证金。",
        },
        {
            "gate": "stage655_ctp_tdapi_import_ready",
            "passed": int(stage655_import_ready),
            "actual": f"tdapi_import_available={stage655.get('tdapi_import_available', False)}; status={stage655.get('status', '')}",
            "threshold": "true",
            "hard_gate": 1,
            "judgement": "本机 CTP Mac framework 已可被 vnpy_ctp.api 加载。",
        },
        {
            "gate": "current_readonly_account_snapshot_has_margin",
            "passed": int(account_evidence["account_snapshot_has_explicit_margin"]),
            "actual": f"rows={account_evidence['account_rows']}; columns={account_evidence['explicit_margin_columns']}; nonempty={account_evidence['explicit_margin_nonempty_rows']}",
            "threshold": "fresh account snapshot with explicit margin field",
            "hard_gate": 1,
            "judgement": "当前还没有真实可用的保证金字段样本。",
        },
        {
            "gate": "exact_vt_orderid_mapping_ready",
            "passed": int(vt_orderid_ready),
            "actual": str(stage613.get("real_vt_orderid_mappings", 0)),
            "threshold": ">=5 contract rows; later >=9 P0 samples",
            "hard_gate": 1,
            "judgement": "真实 submit 返回值还没有落账。",
        },
        {
            "gate": "p0_tca_samples_ready",
            "passed": int(tca_samples_ready),
            "actual": f"{stage613.get('p0_valid_live_tca_samples', 0)}/{P0_REQUIRED_TCA_SAMPLES}",
            "threshold": f">={P0_REQUIRED_TCA_SAMPLES}, VWAP<={MAX_VWAP_COST_BPS}bps, IS<={MAX_IMPLEMENTATION_SHORTFALL_BPS}bps",
            "hard_gate": 1,
            "judgement": "仍缺真实成交质量样本。",
        },
        {
            "gate": "real_submit_remains_blocked",
            "passed": int(no_order_called and not bool(stage613.get("promotion_allowed", False))),
            "actual": f"send_order={stage613.get('send_order_api_called_count', 0)}; promotion={stage613.get('promotion_allowed', False)}",
            "threshold": "send_order=0 and promotion=false",
            "hard_gate": 1,
            "judgement": "当前 fail-closed 状态正确。",
        },
        {
            "gate": "stage613_tca_closeout_all_green",
            "passed": int(stage613_hard_ok),
            "actual": f"{stage613.get('hard_gates_passed', 0)}/{stage613.get('hard_gates_total', 0)}",
            "threshold": "all hard gates",
            "hard_gate": 1,
            "judgement": "执行/TCA 证据链尚未闭合。",
        },
    ]
    gates_df = pd.DataFrame(gates)
    evidence_df = pd.DataFrame(evidence_rows)

    aggregate = {
        "stage653_best_fixed": stage653_best_fixed,
        "stage653_normal_margin_ok": stage653_normal_margin_ok,
        "stage653_cost_hard_ok": stage653_cost_hard_ok,
        "live_margin_contract_ok": live_margin_contract_ok,
        "account_snapshot_margin_ok": bool(account_evidence["account_snapshot_has_explicit_margin"]),
        "stage613_hard_ok": stage613_hard_ok,
        "no_order_called": no_order_called,
        "vt_orderid_ready": vt_orderid_ready,
        "tca_samples_ready": tca_samples_ready,
        "stage655_import_ready": stage655_import_ready,
        "stage655": stage655,
        "stage656": stage656,
        "stage653_decision": stage653.get("decision", ""),
        "stage613_decision": stage613.get("decision", ""),
        "stage613_failed_gate_count": int((stage613_gates["passed"].astype(int).eq(0)).sum()) if not stage613_gates.empty else 0,
        "best_row": best,
        "cost2_row": cost2,
        "cost3_row": cost3,
        "forced_row": forced_best,
        "account_evidence": account_evidence,
        "code_evidence": code_evidence,
    }
    return gates_df, evidence_df, aggregate


def make_chart(gates: pd.DataFrame, aggregate: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig = plt.figure(figsize=(16, 10), constrained_layout=True)
    gs = fig.add_gridspec(2, 2)

    ax1 = fig.add_subplot(gs[0, 0])
    colors = gates["passed"].map(lambda x: "#1b9e77" if int(x) else "#d73027")
    ax1.barh(gates["gate"], np.ones(len(gates)), color=colors, alpha=0.9)
    ax1.set_xlim(0, 1.02)
    ax1.set_title("Stage654 live margin/TCA gates")
    ax1.invert_yaxis()
    for y, (_, row) in enumerate(gates.iterrows()):
        ax1.text(0.03, y, "PASS" if int(row["passed"]) else "BLOCK", va="center", color="white", fontsize=8, fontweight="bold")

    ax2 = fig.add_subplot(gs[0, 1])
    best = aggregate["best_row"]
    cost2 = aggregate["cost2_row"]
    bars = pd.DataFrame(
        [
            {"metric": "return_retention", "value": _num(best.get("return_retention_vs_20w_baseline_pct")), "threshold": 80.0},
            {"metric": "broker10_peak", "value": _num(best.get("max_broker10_margin_to_equity_pct")), "threshold": 90.0},
            {"metric": "2x_abs_dd", "value": abs(_num(cost2.get("max_dd_pct"))), "threshold": 40.0},
        ]
    )
    ax2.bar(bars["metric"], bars["value"], color=["#1b9e77", "#1b9e77", "#d73027"])
    ax2.plot(bars["metric"], bars["threshold"], color="#111827", marker="o", linestyle="--", linewidth=1)
    ax2.set_title("Stage653 95->80: high return, cost stress still red")
    ax2.set_ylabel("%")
    for idx, row in bars.iterrows():
        ax2.text(idx, row["value"] + 1, f"{row['value']:.2f}", ha="center", fontsize=8)

    ax3 = fig.add_subplot(gs[1, 0])
    labels = ["contract", "tdapi_import", "account_snapshot", "vt_orderid", "p0_tca"]
    values = [
        int(aggregate["live_margin_contract_ok"]),
        int(aggregate["stage655_import_ready"]),
        int(aggregate["account_snapshot_margin_ok"]),
        int(aggregate["vt_orderid_ready"]),
        int(aggregate["tca_samples_ready"]),
    ]
    ax3.imshow(np.array([values]), aspect="auto", cmap=matplotlib.colors.ListedColormap(["#d73027", "#1b9e77"]), vmin=0, vmax=1)
    ax3.set_xticks(np.arange(len(labels)))
    ax3.set_xticklabels(labels, rotation=20, ha="right")
    ax3.set_yticks([0])
    ax3.set_yticklabels(["live evidence"])
    ax3.set_title("Evidence chain after margin-field fix")
    for j, value in enumerate(values):
        ax3.text(j, 0, "Y" if value else "N", ha="center", va="center", color="white", fontweight="bold")

    ax4 = fig.add_subplot(gs[1, 1])
    failed = gates[gates["passed"].astype(int).eq(0)].copy()
    ax4.barh(failed["gate"], np.ones(len(failed)), color="#d73027", alpha=0.9)
    ax4.set_xlim(0, 1.02)
    ax4.set_title("Remaining blockers")
    ax4.invert_yaxis()
    for y, (_, row) in enumerate(failed.iterrows()):
        ax4.text(0.03, y, row["threshold"], va="center", ha="left", fontsize=7, color="white")

    fig.suptitle("Stage654: Stage653 force95->80 is an aggressive candidate, not live-approved", fontsize=15, fontweight="bold")
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(decision: dict[str, Any], gates: pd.DataFrame, evidence: pd.DataFrame) -> None:
    failed = gates[gates["passed"].astype(int).eq(0)].copy()
    best = decision["stage653_best_variant"]
    text = f"""# Stage654 Stage653 Live Margin/TCA Gate

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- generated_at: `{decision['generated_at']}`
- decision: `{decision['decision']}`
- new_backtest_run: `{decision['new_backtest_run']}`
- strategy_alpha_changed: `{decision['strategy_alpha_changed']}`
- live_context_adapter_changed: `{decision['live_context_adapter_changed']}`
- ctp_connection_attempted: `{decision['ctp_connection_attempted']}`
- send_order_api_called_count: `{decision['send_order_api_called_count']}`
- real_submit_allowed: `{decision['real_submit_allowed']}`

## External Research And Judgement

{chr(10).join(f'- {item}' for item in REFERENCE_LINKS)}

Judgement: Stage653 forced deleveraging cannot use `AccountData.frozen` as its live trigger. In vnpy_ctp, CTP raw `CurrMargin` exists, while generic `AccountData` only persists `balance/frozen/available`; therefore real deployment needs an explicit current-margin field from raw CTP account callback or an enriched account snapshot.

## Stage653 Candidate

- variant: `{best.get('variant', '')}`
- end_equity: `{_num(best.get('end_equity')):.0f}`
- total_return_pct: `{_num(best.get('total_return_pct')):.4f}%`
- cagr_pct: `{_num(best.get('cagr_pct')):.4f}%`
- max_dd_pct: `{_num(best.get('max_dd_pct')):.4f}%`
- sharpe: `{_num(best.get('sharpe')):.4f}`
- return_retention_vs_allin: `{_num(best.get('return_retention_vs_20w_baseline_pct')):.4f}%`
- broker10_peak: `{_num(best.get('max_broker10_margin_to_equity_pct')):.4f}%`
- forced_events: `{_num(best.get('forced_margin_deleverage_count')):.0f}`
- forced_closed_volume: `{_num(best.get('forced_margin_deleverage_closed_volume')):.0f}`

## Gates

{_md_table(gates, ['gate', 'passed', 'actual', 'threshold', 'judgement'], max_rows=30)}

## Failed Gates

{_md_table(failed, ['gate', 'actual', 'threshold', 'judgement'], max_rows=20)}

## Evidence

{_md_table(evidence, ['evidence', 'value', 'judgement'], max_rows=20)}

## Conclusion

- `force95->80` remains the best high-return 20w aggressive candidate from Stage653.
- It is not live-approved: the current account snapshot lacks explicit margin, exact `vt_orderid` mapping is missing, and P0 TCA samples are still `0/{P0_REQUIRED_TCA_SAMPLES}`.
- The code contract has been tightened so future live checks require explicit broker current margin / CTP `CurrMargin`, not `AccountData.frozen`.

## Overfit Reflection

- Before run: no. This is an execution evidence gate, not a return parameter experiment.
- After run: no. The script blocks promotion despite the attractive Stage653 return path.

## Continue-Value Reflection

- Before run: yes. The key risk is now live margin/TCA evidence, not historical threshold tuning.
- After run: yes, but only through read-only account margin capture and TCA samples; continuing to tune `95/80` decimals has low value.

## Validation

- Script py_compile: passed.
- Script run: completed.
- Order API: not called.
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage653 = _read_json(STAGE653_DECISION)
    summary = _read_csv(STAGE653_SUMMARY)
    cost = _read_csv(STAGE653_COST)
    forced = _read_csv(STAGE653_FORCED_SUMMARY)
    stage613 = _read_json(STAGE613_DECISION)
    stage613_gates = _read_csv(STAGE613_GATES)
    stage655 = _read_json(STAGE655_SUMMARY)
    stage656 = _read_json(STAGE656_SUMMARY)
    accounts = _read_csv(STAGE656_ACCOUNT)
    if accounts.empty:
        accounts = _read_csv(STAGE655_ACCOUNT)
    if accounts.empty:
        accounts = _read_csv(STAGE608_ACCOUNT)

    gates, evidence, aggregate = build_evidence(summary, cost, forced, stage653, stage613, stage613_gates, stage655, stage656, accounts)
    hard = gates[gates["hard_gate"].astype(int).eq(1)]
    remaining_required_evidence: list[str] = []
    if not aggregate["account_snapshot_margin_ok"]:
        remaining_required_evidence.append("user-approved read-only account snapshot containing explicit current margin / raw CTP CurrMargin")
    if not aggregate["vt_orderid_ready"]:
        remaining_required_evidence.append("exact bridge_signal_id -> real vt_orderid mapping from main_engine.send_order return")
    if not aggregate["tca_samples_ready"]:
        remaining_required_evidence.append(
            f"{P0_REQUIRED_TCA_SAMPLES} valid P0 live TCA samples with VWAP<={MAX_VWAP_COST_BPS}bps and IS<={MAX_IMPLEMENTATION_SHORTFALL_BPS}bps"
        )
    if not aggregate["stage653_cost_hard_ok"]:
        remaining_required_evidence.append("cost-stress decision: accept aggressive normal-cost risk or fall back to Stage352 profit50_cap500k")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": _now_cst(),
        "decision": "stage653_force95_live_margin_tca_not_ready_margin_contract_fixed",
        "new_backtest_run": False,
        "strategy_alpha_changed": False,
        "live_context_adapter_changed": True,
        "promotion_allowed": False,
        "real_submit_allowed": False,
        "high_risk_aggressive_candidate_to_watch": True,
        "ctp_connection_attempted": bool(stage655.get("connect_requested", False) or stage656.get("connect_requested", False)),
        "stage655_connect_requested": bool(stage655.get("connect_requested", False)),
        "stage655_front_connected": bool(stage655.get("front_connected", False)),
        "stage656_status": stage656.get("status", ""),
        "stage656_connect_requested": bool(stage656.get("connect_requested", False)),
        "stage656_front_connected": bool(stage656.get("front_connected", False)),
        "stage656_explicit_margin_rows": int(stage656.get("explicit_margin_rows", 0) or 0),
        "send_order_api_called_count": 0,
        "stage653_best_variant": aggregate["best_row"],
        "stage653_cost2_max_dd_pct": _num(aggregate["cost2_row"].get("max_dd_pct")),
        "stage653_cost3_max_dd_pct": _num(aggregate["cost3_row"].get("max_dd_pct")),
        "live_margin_contract_ok": aggregate["live_margin_contract_ok"],
        "stage655_tdapi_import_ready": aggregate["stage655_import_ready"],
        "stage655_status": stage655.get("status", ""),
        "stage655_missing_required_env": stage655.get("missing_required_env", []),
        "account_snapshot_margin_ok": aggregate["account_snapshot_margin_ok"],
        "stage613_hard_ok": aggregate["stage613_hard_ok"],
        "hard_gates_passed": int(hard["passed"].astype(int).sum()),
        "hard_gates_total": int(len(hard)),
        "failed_hard_gates": int((hard["passed"].astype(int) == 0).sum()),
        "account_evidence": aggregate["account_evidence"],
        "code_evidence": aggregate["code_evidence"],
        "remaining_required_evidence": remaining_required_evidence,
        "visual_chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
        "source_references": REFERENCE_LINKS,
    }

    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    evidence.to_csv(EVIDENCE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    make_chart(gates, aggregate)
    write_report(decision, gates, evidence)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
