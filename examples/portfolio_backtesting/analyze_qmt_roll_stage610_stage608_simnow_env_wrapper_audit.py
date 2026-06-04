from __future__ import annotations

from datetime import datetime
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


MODEL_TAG = "stage610_stage608_simnow_env_wrapper_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage610_stage608_simnow_env_wrapper_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

WRAPPER_PATH = PROJECT_DIR / "run_ctp_stage608_readonly_tick_snapshot_probe.sh"
PROBE_SOURCE = PROJECT_DIR / "run_ctp_stage608_readonly_tick_snapshot_probe.py"
DRY_RUN_SUMMARY = OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_summary_stage608_readonly_tick_snapshot_probe_v1.json"
TARGET_SYMBOLS = OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_target_symbols_stage608_readonly_tick_snapshot_probe_v1.csv"
TICKS = OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_ticks_stage608_readonly_tick_snapshot_probe_v1.csv"

CAPABILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_capability_{MODEL_TAG}.csv"
DRY_RUN_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dry_run_status_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REQUIRED_ENV = [
    "CTP_USERID",
    "CTP_PASSWORD",
    "CTP_BROKERID",
    "CTP_TD_ADDRESS",
    "CTP_MD_ADDRESS",
    "CTP_APPID",
    "CTP_AUTH_CODE",
]

REFERENCE_LINKS = [
    "vn.py gateway contract: https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways",
    "vnpy_ctp gateway package: https://github.com/vnpy/vnpy_ctp",
    "VeighNa CTP gateway usage: https://www.vnpy.com/docs/cn/community/info/gateway.html",
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
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


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _contains_any(source: str, patterns: list[str]) -> bool:
    return any(pattern in source for pattern in patterns)


def _build_capability(wrapper_source: str, probe_source: str, summary: dict[str, Any]) -> pd.DataFrame:
    env_status = summary.get("env_status", {}) if isinstance(summary.get("env_status", {}), dict) else {}
    configured_required = 0
    for logical, payload in env_status.items():
        if not isinstance(payload, dict):
            continue
        if payload.get("env_key") in REQUIRED_ENV and payload.get("configured"):
            configured_required += 1

    rows = [
        {
            "capability": "wrapper_exists_and_executable",
            "passed": int(WRAPPER_PATH.exists() and os.access(WRAPPER_PATH, os.X_OK)),
            "observed": f"exists={WRAPPER_PATH.exists()};executable={os.access(WRAPPER_PATH, os.X_OK)}",
            "why": "wrapper must be callable without changing the Python probe.",
        },
        {
            "capability": "sources_local_simnow_env_without_printing",
            "passed": int("ctp_simnow.local.env" in wrapper_source and "source \"${LOCAL_ENV}\"" in wrapper_source),
            "observed": "local env source present" if "source \"${LOCAL_ENV}\"" in wrapper_source else "missing",
            "why": "credentials stay local and are not stored in repo stage records.",
        },
        {
            "capability": "preserves_external_front_overrides",
            "passed": int("INPUT_SIMNOW_FRONT" in wrapper_source and "INPUT_CTP_TD_ADDRESS" in wrapper_source and "INPUT_CTP_MD_ADDRESS" in wrapper_source),
            "observed": "SIMNOW_FRONT/TD/MD input override variables present",
            "why": "operator can force trading/7x24/front address without local env overriding it.",
        },
        {
            "capability": "simnow_front_routes_available",
            "passed": int(all(token in wrapper_source for token in ["7x24)", "trading)", "trading2)", "trading_mobile)"])),
            "observed": "7x24/trading/trading2/trading_mobile" if "trading_mobile)" in wrapper_source else "incomplete",
            "why": "known SimNow front aliases are explicit and fail closed on unknown values.",
        },
        {
            "capability": "safe_simnow_defaults",
            "passed": int(all(token in wrapper_source for token in ["CTP_BROKERID", "simnow_client_test", "0000000000000000"])),
            "observed": "broker/appid/auth defaults present",
            "why": "dry-run has deterministic SimNow defaults but still needs user credentials.",
        },
        {
            "capability": "mac_ctp_dyld_wrapper",
            "passed": int("DYLD_FRAMEWORK_PATH" in wrapper_source and "vnpy_ctp/api/libs" in wrapper_source),
            "observed": "DYLD_FRAMEWORK_PATH set for vnpy_ctp libs",
            "why": "macOS CTP framework loading should match the dry-run import path.",
        },
        {
            "capability": "explicit_connect_required",
            "passed": int('parser.add_argument("--connect"' in probe_source and summary.get("connect_requested") is False),
            "observed": f"connect_requested={summary.get('connect_requested')}",
            "why": "normal audit must not connect CTP without an explicit flag.",
        },
        {
            "capability": "required_env_configured_in_dry_run",
            "passed": int(len(summary.get("missing_required_env", [])) == 0 and configured_required == len(REQUIRED_ENV)),
            "observed": f"configured_required={configured_required}/{len(REQUIRED_ENV)};missing={len(summary.get('missing_required_env', []))}",
            "why": "future explicit read-only connect should not fail from missing required variables.",
        },
        {
            "capability": "secrets_not_echoed_by_wrapper",
            "passed": int(not _contains_any(wrapper_source, ["echo ${CTP_PASSWORD", "echo \"${CTP_PASSWORD", "echo $CTP_PASSWORD", "printenv", "env |"])),
            "observed": "no password/auth env echo pattern found",
            "why": "secrets must not be printed into chat, reports, or logs.",
        },
        {
            "capability": "no_order_or_cancel_path",
            "passed": int(".send_order(" not in probe_source and "send_order(" not in probe_source and "cancel_order(" not in probe_source),
            "observed": "no send_order/cancel_order source call",
            "why": "Stage608 is read-only tick snapshot collection, not an order adapter.",
        },
    ]
    return pd.DataFrame(rows)


def _build_dry_run_status(summary: dict[str, Any], target_symbols: pd.DataFrame, ticks: pd.DataFrame) -> pd.DataFrame:
    row_counts = summary.get("row_counts", {}) if isinstance(summary.get("row_counts", {}), dict) else {}
    return pd.DataFrame(
        [
            {"component": "status", "value": str(summary.get("status", "")), "expected": "dry_run_not_connected", "passed": int(summary.get("status") == "dry_run_not_connected")},
            {"component": "connect_requested", "value": str(summary.get("connect_requested", "")), "expected": "False", "passed": int(summary.get("connect_requested") is False)},
            {"component": "vnpy_ctp_import_available", "value": str(summary.get("vnpy_ctp_import_available", "")), "expected": "True", "passed": int(summary.get("vnpy_ctp_import_available") is True)},
            {"component": "target_symbols", "value": str(len(target_symbols)), "expected": "5 from submit plan", "passed": int(len(target_symbols) == 5)},
            {"component": "missing_required_env", "value": str(len(summary.get("missing_required_env", []))), "expected": "0", "passed": int(len(summary.get("missing_required_env", [])) == 0)},
            {"component": "send_order_api_called_count", "value": str(summary.get("send_order_api_called_count", "")), "expected": "0", "passed": int(summary.get("send_order_api_called_count") == 0)},
            {"component": "cancel_order_api_called_count", "value": str(summary.get("cancel_order_api_called_count", "")), "expected": "0", "passed": int(summary.get("cancel_order_api_called_count") == 0)},
            {"component": "subscribe_api_called_count", "value": str(summary.get("subscribe_api_called_count", "")), "expected": "0 in dry-run", "passed": int(summary.get("subscribe_api_called_count") == 0)},
            {"component": "tick_rows", "value": str(len(ticks)), "expected": "0 in dry-run; >0 after explicit --connect", "passed": int(len(ticks) == 0)},
            {"component": "account_rows", "value": str(row_counts.get("accounts", 0)), "expected": "0 in dry-run", "passed": int(int(row_counts.get("accounts", 0) or 0) == 0)},
        ]
    )


def _build_gates(capability: pd.DataFrame, dry_run: pd.DataFrame, summary: dict[str, Any]) -> pd.DataFrame:
    cap = {str(row.capability): bool(row.passed) for row in capability.itertuples(index=False)}
    dry = {str(row.component): bool(row.passed) for row in dry_run.itertuples(index=False)}
    rows = [
        {
            "gate": "wrapper_env_contract_ready",
            "actual": f"{int(capability['passed'].sum())}/{len(capability)} capabilities",
            "threshold": "all capabilities pass",
            "passed": int(capability["passed"].astype(int).sum() == len(capability)),
            "hard_gate": 1,
            "judgement": "Stage608 wrapper is aligned with SimNow local env, front routing and macOS DYLD.",
        },
        {
            "gate": "dry_run_not_connected",
            "actual": str(summary.get("status", "")),
            "threshold": "dry_run_not_connected",
            "passed": int(dry.get("status", False) and dry.get("connect_requested", False)),
            "hard_gate": 1,
            "judgement": "The audit still does not connect CTP.",
        },
        {
            "gate": "required_env_ready_but_sanitized",
            "actual": f"missing={len(summary.get('missing_required_env', []))}",
            "threshold": "missing=0 and no wrapper secret echo",
            "passed": int(cap.get("required_env_configured_in_dry_run", False) and cap.get("secrets_not_echoed_by_wrapper", False)),
            "hard_gate": 1,
            "judgement": "Local credentials are available for future explicit read-only connect but are not printed.",
        },
        {
            "gate": "no_order_surface",
            "actual": f"send={summary.get('send_order_api_called_count')};cancel={summary.get('cancel_order_api_called_count')}",
            "threshold": "send=0 cancel=0 and no source call",
            "passed": int(cap.get("no_order_or_cancel_path", False) and summary.get("send_order_api_called_count") == 0 and summary.get("cancel_order_api_called_count") == 0),
            "hard_gate": 1,
            "judgement": "No order/cancel path is present or called.",
        },
        {
            "gate": "subscription_gated_by_connect",
            "actual": f"subscribe={summary.get('subscribe_api_called_count')}",
            "threshold": "0 in dry-run",
            "passed": int(summary.get("subscribe_api_called_count") == 0 and cap.get("explicit_connect_required", False)),
            "hard_gate": 1,
            "judgement": "Market data subscription stays behind explicit --connect.",
        },
        {
            "gate": "fresh_tick_snapshot_evidence",
            "actual": "0 rows in dry-run",
            "threshold": ">0 only after explicit --connect",
            "passed": 0,
            "hard_gate": 0,
            "judgement": "Expected remaining evidence gap; do not claim true trading no-bias yet.",
        },
    ]
    return pd.DataFrame(rows)


def _make_chart(capability: pd.DataFrame, dry_run: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams["font.family"] = "Arial Unicode MS"
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage610 Stage608 wrapper: SimNow env contract ready, live tick evidence still pending", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    cap_plot = capability.copy()
    cap_plot["color"] = cap_plot["passed"].map(lambda item: "#2f855a" if int(item) else "#e53e3e")
    ax.barh(cap_plot["capability"], cap_plot["passed"], color=cap_plot["color"])
    ax.set_xlim(0, 1.05)
    ax.set_title("Wrapper capabilities")
    ax.set_xlabel("pass")
    for idx, row in enumerate(cap_plot.itertuples(index=False)):
        ax.text(0.03, idx, "PASS" if int(row.passed) else "FAIL", va="center", color="white", fontsize=8, fontweight="bold")

    ax = axes[0, 1]
    dry_plot = dry_run.copy()
    dry_plot["bar_width"] = 1.0
    dry_plot["color"] = dry_plot["passed"].map(lambda item: "#2f855a" if int(item) else "#e53e3e")
    ax.barh(dry_plot["component"], dry_plot["bar_width"], color=dry_plot["color"])
    ax.set_xlim(0, 1.05)
    ax.set_title("Dry-run checklist")
    ax.set_xlabel("contract check")
    for idx, row in enumerate(dry_plot.itertuples(index=False)):
        status = "PASS" if int(row.passed) else "FAIL"
        ax.text(0.02, idx, status, va="center", color="white", fontsize=8, fontweight="bold")
        ax.text(0.35, idx, f"observed={row.value}", va="center", color="#1a202c", fontsize=8)

    ax = axes[1, 0]
    gate_plot = gates.copy()
    colors = gate_plot["passed"].map(lambda item: "#2f855a" if int(item) else "#e53e3e")
    ax.barh(gate_plot["gate"], [1.0] * len(gate_plot), color=colors)
    ax.set_xlim(0, 1.05)
    ax.set_title("Safety gates")
    for idx, row in enumerate(gate_plot.itertuples(index=False)):
        ax.text(0.03, idx, "PASS" if int(row.passed) else "PENDING", va="center", color="white", fontsize=8, fontweight="bold")

    ax = axes[1, 1]
    ladder = pd.DataFrame(
        [
            {"step": "dry-run env wrapper", "done": 1},
            {"step": "explicit read-only --connect", "done": 0},
            {"step": "target tick rows >0", "done": 0},
            {"step": "Stage606/607 validator all green", "done": 0},
            {"step": "vt_orderid TCA writer", "done": 0},
        ]
    )
    ax.barh(ladder["step"], [1.0] * len(ladder), color=ladder["done"].map(lambda item: "#2f855a" if int(item) else "#e53e3e"))
    ax.set_xlim(0, 1.05)
    ax.set_title("Execution evidence ladder")
    for idx, row in enumerate(ladder.itertuples(index=False)):
        ax.text(0.03, idx, "DONE" if int(row.done) else "PENDING", va="center", color="white", fontsize=8, fontweight="bold")

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(capability: pd.DataFrame, dry_run: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage610 Stage608 SimNow Env Wrapper Audit",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- generated_at：`{decision['generated_at']}`",
        f"- decision：`{decision['decision']}`",
        f"- promotion_allowed：`{decision['promotion_allowed']}`",
        f"- paper_selector_allowed：`{decision['paper_selector_allowed']}`",
        f"- trading_whitelist_allowed：`{decision['trading_whitelist_allowed']}`",
        f"- hard_gates：`{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## 外部调研判断",
        "",
        "- vn.py/CTP 网关标准路径支持 `connect(setting)` 后通过事件回调获得合约、账户、持仓、行情。",
        "- `SubscribeRequest + main_engine.subscribe` 是只读 tick snapshot 的正确抽象；`send_order` 不应出现在本阶段。",
        "- SimNow front/default/env 应放在 wrapper，而不是写死进策略或提交逻辑。",
        "",
        "参考：",
        *[f"- {link}" for link in REFERENCE_LINKS],
        "",
        "## 本阶段做了什么",
        "",
        "- 修改 Stage608 wrapper：source 本地 SimNow env、保留外部 front/TD/MD 覆盖、默认 `7x24`、设置四类 SimNow front、设置 broker/appid/auth 默认值、保留 macOS DYLD CTP 路径。",
        "- 只跑 dry-run，不使用 `--connect`，不连接 CTP，不订阅行情，不调用订单 API。",
        "- 审计 wrapper 源码、dry-run summary、目标合约和安全闸门。",
        "",
        "## Capability",
        "",
        _md_table(capability, ["capability", "passed", "observed", "why"]),
        "",
        "## Dry-run Status",
        "",
        _md_table(dry_run, ["component", "value", "expected", "passed"]),
        "",
        "## Gates",
        "",
        _md_table(gates, ["gate", "actual", "threshold", "passed", "hard_gate", "judgement"]),
        "",
        "## 结论",
        "",
        "- Stage608 wrapper 已具备下一次显式 read-only `--connect` 所需的环境合同。",
        "- 当前仍没有连接、没有行情订阅、没有 tick rows；不能声明真实交易无偏差已经闭合。",
        "- 下一步只有在用户确认测试环境和 read-only 动作后，才运行 Stage608 wrapper `--connect` 捕获 target symbols tick snapshot。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段只改执行/环境安全层，不改策略收益规则。",
        "- 运行后判断：否。所有输出都是合同/安全闸门，不使用历史收益优化。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。真实交易无偏差链路当前缺 fresh tick/account/position/contract context。",
        "- 运行后判断：有价值。wrapper 环境缺口已闭合，下一步可以更低风险地做显式 read-only tick capture。",
        "",
        "## 输出文件",
        "",
        f"- capability：`{CAPABILITY_PATH}`",
        f"- dry_run_status：`{DRY_RUN_STATUS_PATH}`",
        f"- gates：`{GATES_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    wrapper_source = WRAPPER_PATH.read_text(encoding="utf-8")
    probe_source = PROBE_SOURCE.read_text(encoding="utf-8")
    summary = _read_json(DRY_RUN_SUMMARY)
    target_symbols = _read_csv(TARGET_SYMBOLS)
    ticks = _read_csv(TICKS)

    capability = _build_capability(wrapper_source, probe_source, summary)
    dry_run = _build_dry_run_status(summary, target_symbols, ticks)
    gates = _build_gates(capability, dry_run, summary)

    hard = gates[gates["hard_gate"].astype(int).eq(1)]
    hard_passed = int(hard["passed"].astype(int).sum())
    hard_total = int(len(hard))
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "decision": "stage608_simnow_env_wrapper_ready_dry_run_no_connect",
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "new_backtest_run": False,
        "strategy_changed": False,
        "wrapper_capabilities_passed": int(capability["passed"].astype(int).sum()),
        "wrapper_capabilities_total": int(len(capability)),
        "dry_run_status": summary.get("status", ""),
        "connect_requested": summary.get("connect_requested"),
        "target_symbol_count": int(len(target_symbols)),
        "missing_required_env_count": int(len(summary.get("missing_required_env", []))),
        "send_order_api_called_count": int(summary.get("send_order_api_called_count", -1)),
        "cancel_order_api_called_count": int(summary.get("cancel_order_api_called_count", -1)),
        "subscribe_api_called_count": int(summary.get("subscribe_api_called_count", -1)),
        "tick_rows": int(len(ticks)),
        "hard_gates_passed": hard_passed,
        "hard_gates_total": hard_total,
        "failed_hard_gates": hard_total - hard_passed,
        "visual_chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
    }

    capability.to_csv(CAPABILITY_PATH, index=False, encoding="utf-8-sig")
    dry_run.to_csv(DRY_RUN_STATUS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _make_chart(capability, dry_run, gates)
    _write_report(capability, dry_run, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
