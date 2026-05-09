from __future__ import annotations

import importlib.util
import json
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage175_ctp_readonly_deployment_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage175_ctp_readonly_deployment"
STAGE174_PREFIX: str = "qmt_roll_stage174_ctp_vnpy_route"
STAGE174_TAG: str = "stage174_ctp_vnpy_route_v1"
STAGE174_PROBE_PREFIX: str = "qmt_roll_stage174_ctp_vnpy_readonly_probe"
STAGE174_PROBE_TAG: str = "stage174_ctp_vnpy_readonly_probe_v1"

SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHECKLIST_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checklist_{MODEL_TAG}.csv"
ENV_EXAMPLE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_env_examples_{MODEL_TAG}.md"
BROKER_REQUEST_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_broker_request_template_{MODEL_TAG}.md"
BOOTSTRAP_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bootstrap_commands_{MODEL_TAG}.md"

STAGE174_SUMMARY_PATH: Path = OUTPUT_DIR / f"{STAGE174_PREFIX}_summary_{STAGE174_TAG}.json"
STAGE174_PROBE_SUMMARY_PATH: Path = OUTPUT_DIR / f"{STAGE174_PROBE_PREFIX}_summary_{STAGE174_PROBE_TAG}.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _build_checklist() -> pd.DataFrame:
    rows = [
        {
            "step": 1,
            "owner": "user",
            "item": "向期货公司确认已开通CTP API/程序化接入权限",
            "required": 1,
            "status": "pending_user",
            "note": "实盘账号需要客户经理提供BrokerID、交易前置、行情前置、AppID、AuthCode。",
        },
        {
            "step": 2,
            "owner": "user",
            "item": "优先准备SimNow或期货公司仿真账号",
            "required": 1,
            "status": "pending_user",
            "note": "不要第一步直接连接实盘资金账号。",
        },
        {
            "step": 3,
            "owner": "user",
            "item": "准备Windows或Ubuntu运行环境",
            "required": 1,
            "status": "pending_user",
            "note": "当前Mac arm64安装vnpy_ctp失败，不建议继续硬磨。",
        },
        {
            "step": 4,
            "owner": "agent",
            "item": "安装vn.py和vnpy_ctp",
            "required": 1,
            "status": "blocked_by_runtime",
            "note": "在Windows/Ubuntu执行bootstrap命令。",
        },
        {
            "step": 5,
            "owner": "user",
            "item": "把CTP凭证配置为本机环境变量",
            "required": 1,
            "status": "pending_user",
            "note": "不要写入repo、聊天、研究记录。",
        },
        {
            "step": 6,
            "owner": "agent",
            "item": "运行Stage174只读探针dry-run",
            "required": 1,
            "status": "ready",
            "note": "先确认vnpy_ctp和环境变量可见。",
        },
        {
            "step": 7,
            "owner": "agent",
            "item": "运行Stage174只读探针--connect",
            "required": 1,
            "status": "waiting_for_ctp_env",
            "note": "只监听账户、持仓、合约、委托、成交，不调用send_order。",
        },
        {
            "step": 8,
            "owner": "agent",
            "item": "生成第78信号 vs CTP持仓对账日报",
            "required": 1,
            "status": "next_after_probe",
            "note": "必须先拿到账户/持仓事件。",
        },
    ]
    return pd.DataFrame(rows)


def _write_env_examples() -> None:
    lines = [
        "# Stage175 CTP环境变量示例",
        "",
        "不要把真实值写入仓库或聊天。以下只保留占位符。",
        "",
        "## Windows PowerShell",
        "",
        "当前终端临时设置：",
        "",
        "```powershell",
        "$env:CTP_USERID='your_investor_id'",
        "$env:CTP_PASSWORD='local_secret'",
        "$env:CTP_BROKERID='9999_or_real_broker'",
        "$env:CTP_TD_ADDRESS='tcp://host:port'",
        "$env:CTP_MD_ADDRESS='tcp://host:port'",
        "$env:CTP_APPID='your_appid'",
        "$env:CTP_AUTH_CODE='your_auth_code'",
        "```",
        "",
        "用户级持久设置：",
        "",
        "```powershell",
        "[Environment]::SetEnvironmentVariable('CTP_USERID', 'your_investor_id', 'User')",
        "[Environment]::SetEnvironmentVariable('CTP_PASSWORD', 'local_secret', 'User')",
        "[Environment]::SetEnvironmentVariable('CTP_BROKERID', '9999_or_real_broker', 'User')",
        "[Environment]::SetEnvironmentVariable('CTP_TD_ADDRESS', 'tcp://host:port', 'User')",
        "[Environment]::SetEnvironmentVariable('CTP_MD_ADDRESS', 'tcp://host:port', 'User')",
        "[Environment]::SetEnvironmentVariable('CTP_APPID', 'your_appid', 'User')",
        "[Environment]::SetEnvironmentVariable('CTP_AUTH_CODE', 'your_auth_code', 'User')",
        "```",
        "",
        "## Ubuntu bash",
        "",
        "```bash",
        "export CTP_USERID='your_investor_id'",
        "export CTP_PASSWORD='local_secret'",
        "export CTP_BROKERID='9999_or_real_broker'",
        "export CTP_TD_ADDRESS='tcp://host:port'",
        "export CTP_MD_ADDRESS='tcp://host:port'",
        "export CTP_APPID='your_appid'",
        "export CTP_AUTH_CODE='your_auth_code'",
        "```",
        "",
        "## SimNow常用仿真占位",
        "",
        "- `CTP_BROKERID=9999`",
        "- `CTP_APPID=simnow_client_test`",
        "- `CTP_AUTH_CODE=0000000000000000`",
        "- 第一组：`CTP_TD_ADDRESS=tcp://180.168.146.187:10201`，`CTP_MD_ADDRESS=tcp://180.168.146.187:10211`",
        "- 第二组：`CTP_TD_ADDRESS=tcp://180.168.146.187:10202`，`CTP_MD_ADDRESS=tcp://180.168.146.187:10212`",
        "- 7x24测试：`CTP_TD_ADDRESS=tcp://180.168.146.187:10130`，`CTP_MD_ADDRESS=tcp://180.168.146.187:10131`",
    ]
    ENV_EXAMPLE_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_broker_request_template() -> None:
    lines = [
        "# 给期货公司客户经理的CTP开通信息清单",
        "",
        "请帮我确认/提供以下信息，用于量化程序只读接入测试，初期不自动下单：",
        "",
        "1. 是否已开通CTP API/程序化接入权限。",
        "2. 投资者账号/用户名（InvestorID）。",
        "3. 经纪商代码（BrokerID）。",
        "4. 交易前置地址和端口（Trade Front），请确认是否需要 `tcp://` 前缀。",
        "5. 行情前置地址和端口（Market Front）。",
        "6. 产品名称/AppID。",
        "7. 授权编码/AuthCode。",
        "8. 是否有独立仿真环境，仿真账号与实盘账号是否共用密码。",
        "9. 是否存在查询权限/只读权限账号；如果没有，是否允许普通CTP账号做只读程序连接。",
        "10. 连接时间限制、夜盘支持情况、结算单确认要求。",
        "11. 是否支持Linux服务器连接；如只支持Windows请说明。",
        "",
        "安全要求：账号密码不通过聊天工具发送，优先电话/柜台/官方安全渠道确认。",
    ]
    BROKER_REQUEST_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_bootstrap_commands() -> None:
    lines = [
        "# Stage175 CTP只读环境Bootstrap命令",
        "",
        "## Windows PowerShell",
        "",
        "```powershell",
        "py -3.11 -m venv .venv",
        ".\\.venv\\Scripts\\Activate.ps1",
        "python -m pip install -U pip",
        "python -m pip install vnpy vnpy_ctp pandas numpy",
        "python examples\\portfolio_backtesting\\run_ctp_stage174_readonly_probe.py",
        "python examples\\portfolio_backtesting\\run_ctp_stage174_readonly_probe.py --connect --wait-seconds 30",
        "```",
        "",
        "## Ubuntu bash",
        "",
        "```bash",
        "python3.11 -m venv .venv",
        "source .venv/bin/activate",
        "python -m pip install -U pip",
        "python -m pip install vnpy vnpy_ctp pandas numpy",
        "python examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py",
        "python examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py --connect --wait-seconds 30",
        "```",
        "",
        "## 当前Mac结论",
        "",
        "本机尝试安装 `vnpy_ctp 6.7.11.4` 失败：macOS arm64从源码编译时出现CTP类型缺失错误，",
        "例如 `CThostFtdcInvestorInfoCommRecField`、`CThostFtdcCombLegField`、`CThostFtdcInputOffsetSettingField` 未定义。",
        "因此当前Mac不作为CTP实盘/仿真连接机。",
    ]
    BOOTSTRAP_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_report(summary: dict[str, Any], checklist: pd.DataFrame) -> None:
    lines = [
        "# Stage175 CTP实盘只读环境部署包",
        "",
        "## 结论",
        "",
        "- 第78国内期货实盘接口路线继续优先选择 CTP/vn.py。",
        "- 当前Mac环境不适合继续硬装 `vnpy_ctp`；应准备Windows或Ubuntu作为CTP连接机。",
        "- 第一环境建议用SimNow或期货公司仿真，不直接连实盘资金账号。",
        "- 真实账号密码不进入仓库、不进入聊天、不进入研究记录。",
        "",
        "## 当前环境",
        "",
        f"- 平台：`{summary['runtime']['platform']}`",
        f"- Python：`{summary['runtime']['python']}`",
        f"- vn.py可用：`{summary['runtime']['vnpy_available']}`",
        f"- vnpy_ctp可用：`{summary['runtime']['vnpy_ctp_available']}`",
        f"- vnpy_ctp安装尝试：`{summary['mac_install_attempt']['status']}`",
        "",
        "## Checklist",
        "",
        checklist.to_markdown(index=False),
        "",
        "## 关键安全边界",
        "",
        "- Stage174/175只读探针不得调用 `send_order`。",
        "- 没有20-60个交易日影子对账前，不允许自动下单。",
        "- CTP账号天然未必只读，所谓只读主要由代码和权限控制共同实现。",
        "",
        "## 下一步",
        "",
        "1. 你先决定用SimNow仿真还是期货公司仿真。",
        "2. 准备Windows/Ubuntu机器或云主机。",
        "3. 在该机器设置环境变量并安装 `vnpy_ctp`。",
        "4. 跑 `run_ctp_stage174_readonly_probe.py --connect --wait-seconds 30`。",
        "5. 拿到账户/持仓/合约事件后，再做第78信号 vs CTP持仓对账日报。",
        "",
        "## 反思",
        "",
        "- 运行前过拟合反思：否。部署环境验证不改变策略参数。",
        "- 运行后过拟合反思：否。Mac安装失败只是工程约束，不影响策略结果。",
        "- 运行前继续价值反思：是。真实对账必须有CTP只读环境。",
        "- 运行后继续价值反思：是。现在阻塞项已明确为运行环境和CTP凭证。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage174_summary = _read_json(STAGE174_SUMMARY_PATH)
    stage174_probe_summary = _read_json(STAGE174_PROBE_SUMMARY_PATH)
    checklist = _build_checklist()
    checklist.to_csv(CHECKLIST_PATH, index=False, encoding="utf-8-sig")
    _write_env_examples()
    _write_broker_request_template()
    _write_bootstrap_commands()

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "is_strategy_change": False,
        "is_backtest": False,
        "strategy": {
            "version": OFFICIAL_STAGE78_VERSION,
            "role": OFFICIAL_STAGE78_ROLE,
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "vnpy_available": _module_available("vnpy"),
            "vnpy_ctp_available": _module_available("vnpy_ctp"),
        },
        "stage174_route_status": stage174_summary.get("route_decision", {}),
        "stage174_probe_status": stage174_probe_summary.get("status", ""),
        "mac_install_attempt": {
            "command": ".py311/bin/python -m pip install vnpy_ctp",
            "version_attempted": "6.7.11.4",
            "status": "failed_on_macos_arm64_source_build",
            "short_reason": "CTP mac headers/source mismatch; unknown CThostFtdc* types during clang build.",
            "decision": "do_not_continue_ctp_install_on_current_mac; use Windows or Ubuntu connection host.",
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "checklist": str(CHECKLIST_PATH),
            "env_examples": str(ENV_EXAMPLE_PATH),
            "broker_request": str(BROKER_REQUEST_PATH),
            "bootstrap_commands": str(BOOTSTRAP_PATH),
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, checklist)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
