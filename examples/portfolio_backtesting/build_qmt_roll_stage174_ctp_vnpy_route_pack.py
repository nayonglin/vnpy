from __future__ import annotations

import importlib.util
import json
import math
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage174_ctp_vnpy_route_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage174_ctp_vnpy_route"
STAGE172_PREFIX: str = "qmt_roll_stage172_stage78_forward_shadow_report"
STAGE172_TAG: str = "stage172_stage78_forward_shadow_report_v1"

CONFIG_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_config_{MODEL_TAG}.json"
ENV_TEMPLATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_env_template_{MODEL_TAG}.json"
FIELD_MAP_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ctp_field_map_{MODEL_TAG}.csv"
SIGNAL_CONTRACT_CHECK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_contract_check_{MODEL_TAG}.csv"
RUNBOOK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_runbook_{MODEL_TAG}.md"
SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

STAGE172_SUMMARY_PATH: Path = OUTPUT_DIR / f"{STAGE172_PREFIX}_summary_{STAGE172_TAG}.json"
STAGE172_SIGNAL_PLAN_PATH: Path = OUTPUT_DIR / f"{STAGE172_PREFIX}_signal_plan_{STAGE172_TAG}.csv"
READONLY_PROBE_PATH: Path = PROJECT_DIR / "run_ctp_stage174_readonly_probe.py"


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


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_signal_plan() -> pd.DataFrame:
    if not STAGE172_SIGNAL_PLAN_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(STAGE172_SIGNAL_PLAN_PATH, encoding="utf-8-sig")


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _build_env_template() -> dict[str, Any]:
    return {
        "security_note": "Do not commit real values. Use local shell env, launchd, Windows environment variables, or a private secrets manager.",
        "required_for_readonly_connect": {
            "CTP_USERID": "<your_investor_id>",
            "CTP_PASSWORD": "<local_secret_not_in_repo>",
            "CTP_BROKERID": "<broker_id>",
            "CTP_TD_ADDRESS": "tcp://<trade_front>:<port>",
            "CTP_MD_ADDRESS": "tcp://<market_front>:<port>",
            "CTP_APPID": "<product_name_or_appid>",
            "CTP_AUTH_CODE": "<auth_code>",
        },
        "optional": {
            "CTP_PRODUCT_INFO": "",
        },
        "first_mode": "read_only_probe_only",
        "real_order_enabled": False,
    }


def _build_config(env: dict[str, Any], stage172_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "is_strategy_change": False,
        "is_backtest": False,
        "strategy": {
            "version": OFFICIAL_STAGE78_VERSION,
            "role": OFFICIAL_STAGE78_ROLE,
            "signal_truth_source": "Stage172 frozen Stage78 forward shadow report",
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "vnpy_available": _module_available("vnpy"),
            "vnpy_ctp_available": _module_available("vnpy_ctp"),
            "vnpy_ctastrategy_available": _module_available("vnpy_ctastrategy"),
            "vnpy_portfoliostrategy_available": _module_available("vnpy_portfoliostrategy"),
        },
        "ctp_route_decision": {
            "preferred_for_domestic_futures": True,
            "qmt_role": "optional_readonly_backup_or_stock_side_tool",
            "ctp_role": "primary_candidate_for_futures_account_reconcile_and_future_execution",
            "current_gate": "build_readonly_probe_before_any_order",
            "real_order_enabled": False,
            "manual_confirm_required_before_orders": True,
        },
        "credential_policy": env,
        "stage172_snapshot": {
            "target_date": stage172_summary.get("target_date", ""),
            "signal_count": stage172_summary.get("target_signal_count", 0),
            "risk_level": stage172_summary.get("risk_snapshot", {}).get("risk_level", ""),
            "allow_real_new_orders": stage172_summary.get("risk_snapshot", {}).get("allow_real_new_orders", 0),
            "risk_reasons": stage172_summary.get("risk_snapshot", {}).get("reasons", []),
        },
        "outputs": {
            "config": str(CONFIG_PATH),
            "env_template": str(ENV_TEMPLATE_PATH),
            "field_map": str(FIELD_MAP_PATH),
            "signal_contract_check": str(SIGNAL_CONTRACT_CHECK_PATH),
            "runbook": str(RUNBOOK_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "readonly_probe_script": str(READONLY_PROBE_PATH),
        },
    }


def _build_field_map() -> pd.DataFrame:
    rows = [
        {"domain": "ctp_env", "source_field": "CTP_USERID", "target_field": "用户名", "required": 1, "note": "InvestorID; keep local only."},
        {"domain": "ctp_env", "source_field": "CTP_PASSWORD", "target_field": "密码", "required": 1, "note": "Never store in repo or chat."},
        {"domain": "ctp_env", "source_field": "CTP_BROKERID", "target_field": "经纪商代码", "required": 1, "note": "SimNow often uses 9999; real broker differs."},
        {"domain": "ctp_env", "source_field": "CTP_TD_ADDRESS", "target_field": "交易服务器", "required": 1, "note": "tcp://host:port"},
        {"domain": "ctp_env", "source_field": "CTP_MD_ADDRESS", "target_field": "行情服务器", "required": 1, "note": "tcp://host:port"},
        {"domain": "ctp_env", "source_field": "CTP_APPID", "target_field": "产品名称", "required": 1, "note": "Also called AppID/product name by brokers."},
        {"domain": "ctp_env", "source_field": "CTP_AUTH_CODE", "target_field": "授权编码", "required": 1, "note": "Broker-provided auth code."},
        {"domain": "stage78_signal", "source_field": "vt_symbol", "target_field": "vn.py ContractData.vt_symbol", "required": 1, "note": "Example MA609.CZCE."},
        {"domain": "stage78_signal", "source_field": "direction", "target_field": "OrderRequest.direction", "required": 1, "note": "Only mapping for future paper/manual order preview; not called now."},
        {"domain": "stage78_signal", "source_field": "offset", "target_field": "OrderRequest.offset", "required": 1, "note": "Close semantics need SHFE close_today/close_yesterday audit before live."},
        {"domain": "ctp_account", "source_field": "AccountData.balance", "target_field": "shadow_account_balance", "required": 1, "note": "Read-only reconcile."},
        {"domain": "ctp_account", "source_field": "AccountData.available", "target_field": "available_cash", "required": 1, "note": "Read-only reconcile."},
        {"domain": "ctp_position", "source_field": "PositionData.volume", "target_field": "actual_position_volume", "required": 1, "note": "Compare with Stage78 target position."},
        {"domain": "ctp_position", "source_field": "PositionData.yd_volume", "target_field": "yesterday_position_volume", "required": 1, "note": "Important for close_today/close_yesterday."},
        {"domain": "ctp_trade", "source_field": "TradeData", "target_field": "actual_fill_ledger", "required": 1, "note": "Read-only fill comparison after manual/sim order."},
    ]
    return pd.DataFrame(rows)


def _build_signal_contract_check(signal_plan: pd.DataFrame) -> pd.DataFrame:
    if signal_plan.empty:
        return pd.DataFrame(
            columns=["vt_symbol", "symbol", "exchange", "offset", "direction", "volume", "check_status", "note"]
        )
    rows: list[dict[str, Any]] = []
    for row in signal_plan.itertuples(index=False):
        vt_symbol = str(getattr(row, "vt_symbol", ""))
        symbol = ""
        exchange = ""
        if "." in vt_symbol:
            symbol, exchange = vt_symbol.split(".", 1)
        offset = str(getattr(row, "offset", ""))
        direction = str(getattr(row, "direction", ""))
        note = "close signal; live route must verify actual long/short position and today/yesterday split"
        rows.append(
            {
                "vt_symbol": vt_symbol,
                "symbol": symbol,
                "exchange": exchange,
                "offset": offset,
                "direction": direction,
                "volume": _safe_float(getattr(row, "volume", 0.0)),
                "check_status": "mapping_ready_probe_required",
                "note": note,
            }
        )
    return pd.DataFrame(rows)


def _write_runbook(config: dict[str, Any]) -> None:
    lines = [
        "# Stage174 CTP/vn.py只读接入Runbook",
        "",
        "## 当前结论",
        "",
        "- CTP/vn.py是第78国内期货实盘执行的主候选路线。",
        "- 当前只允许只读探针，不允许真实下单。",
        f"- 当前环境 `vnpy_ctp` 可用：`{config['runtime']['vnpy_ctp_available']}`",
        "",
        "## 本机环境变量",
        "",
        "不要把真实值写进仓库或聊天。示例：",
        "",
        "```bash",
        "export CTP_USERID='your_id'",
        "export CTP_PASSWORD='local_secret'",
        "export CTP_BROKERID='9999_or_real_broker'",
        "export CTP_TD_ADDRESS='tcp://host:port'",
        "export CTP_MD_ADDRESS='tcp://host:port'",
        "export CTP_APPID='your_appid'",
        "export CTP_AUTH_CODE='your_auth_code'",
        "```",
        "",
        "## 只读探针",
        "",
        "默认只检测环境，不连接：",
        "",
        "```bash",
        ".py311/bin/python examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py",
        "```",
        "",
        "确认已安装 `vnpy_ctp` 且环境变量齐全后，才允许尝试连接：",
        "",
        "```bash",
        ".py311/bin/python examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py --connect --wait-seconds 30",
        "```",
        "",
        "## 禁止项",
        "",
        "- 禁止在Stage174调用 `send_order`。",
        "- 禁止保存真实密码到 `connect_ctp.json`、repo、研究记录或聊天。",
        "- 禁止在没有20-60个交易日影子对账前开启自动下单。",
        "",
        "## 下一步验收",
        "",
        "- 账户事件至少返回1条。",
        "- 持仓事件能和Stage78目标持仓表按 `vt_symbol + direction` 对齐。",
        "- 委托/成交事件即使为空，也必须能稳定输出空表。",
        "- 对 `Close` 信号必须先校验平今/平昨拆分。",
    ]
    RUNBOOK_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_report(config: dict[str, Any], field_map: pd.DataFrame, signal_check: pd.DataFrame) -> None:
    stage172 = config["stage172_snapshot"]
    lines = [
        "# Stage174 CTP/vn.py实盘路线可行性包",
        "",
        "## 定位",
        "",
        "- 本阶段不是策略版本，不修改Stage78参数，不触发A/B。",
        "- 目标是把实盘接口路线从QMT优先切到CTP/vn.py优先，并准备只读探针。",
        "",
        "## 环境检测",
        "",
        f"- Python：`{config['runtime']['python']}`",
        f"- 平台：`{config['runtime']['platform']}`",
        f"- vn.py可用：`{config['runtime']['vnpy_available']}`",
        f"- vnpy_ctp可用：`{config['runtime']['vnpy_ctp_available']}`",
        f"- vnpy_ctastrategy可用：`{config['runtime']['vnpy_ctastrategy_available']}`",
        f"- vnpy_portfoliostrategy可用：`{config['runtime']['vnpy_portfoliostrategy_available']}`",
        "",
        "## Stage172信号快照",
        "",
        f"- 目标日：`{stage172['target_date']}`",
        f"- 信号数：`{stage172['signal_count']}`",
        f"- 风险级别：`{stage172['risk_level']}`",
        f"- 是否允许真实新增开仓：`{stage172['allow_real_new_orders']}`",
        f"- 风险原因：`{stage172['risk_reasons']}`",
        "",
        "## CTP字段映射",
        "",
        _to_markdown_table(field_map, ["domain", "source_field", "target_field", "required", "note"], 40),
        "",
        "## 信号合约检查",
        "",
        _to_markdown_table(signal_check, ["vt_symbol", "symbol", "exchange", "offset", "direction", "volume", "check_status", "note"], 40),
        "",
        "## 结论",
        "",
        "- CTP/vn.py路线值得作为第78期货实盘主路线推进。",
        "- 当前仓库缺 `vnpy_ctp`，所以本机只能先生成只读接入包；安装和真实连接要等你提供CTP仿真或实盘环境。",
        "- 第一阶段只允许账户、持仓、委托、成交、合约只读对账，不允许任何自动下单。",
        "",
        "## 反思",
        "",
        "- 运行前过拟合反思：否。接口路线评估不改变策略参数。",
        "- 运行后过拟合反思：否。输出的是执行接入模板和字段映射。",
        "- 运行前继续价值反思：是。第78现在缺真实账户执行闭环。",
        "- 运行后继续价值反思：是。下一步是安装/配置 `vnpy_ctp` 并跑只读探针。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage172_summary = _read_json(STAGE172_SUMMARY_PATH)
    signal_plan = _read_signal_plan()
    env_template = _build_env_template()
    config = _build_config(env_template, stage172_summary)
    field_map = _build_field_map()
    signal_check = _build_signal_contract_check(signal_plan)

    ENV_TEMPLATE_PATH.write_text(json.dumps(env_template, ensure_ascii=False, indent=2), encoding="utf-8")
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    field_map.to_csv(FIELD_MAP_PATH, index=False, encoding="utf-8-sig")
    signal_check.to_csv(SIGNAL_CONTRACT_CHECK_PATH, index=False, encoding="utf-8-sig")
    _write_runbook(config)

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": config["generated_at"],
        "is_strategy_change": False,
        "is_backtest": False,
        "route_decision": config["ctp_route_decision"],
        "runtime": config["runtime"],
        "stage172_snapshot": config["stage172_snapshot"],
        "field_map_rows": int(len(field_map)),
        "signal_contract_check_rows": int(len(signal_check)),
        "judgement": {
            "overfit_before": "否。Stage174只做实盘接口路线和只读对账包。",
            "continue_before": "是。第78进入真实资金前必须先打通账户/持仓/成交对账。",
            "overfit_after": "否。没有改参数，也没有根据收益重选策略。",
            "continue_after": "是。下一步安装/配置vnpy_ctp并跑只读探针。",
        },
        "outputs": config["outputs"],
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(config, field_map, signal_check)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
