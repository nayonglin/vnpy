from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION


PROJECT_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = PROJECT_DIR.parents[1]
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage176_ctp_mac_native_route_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage176_ctp_mac_native_route"

SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RUNBOOK_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_runbook_{MODEL_TAG}.md"
CHECKLIST_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checklist_{MODEL_TAG}.csv"

PROBE_WRAPPER_PATH: Path = PROJECT_DIR / "run_ctp_stage176_mac_readonly_probe.sh"
VNPY_CTP_API_DIR: Path = PROJECT_ROOT / ".py311/lib/python3.11/site-packages/vnpy_ctp/api"
VNPY_CTP_LIBS_DIR: Path = VNPY_CTP_API_DIR / "libs"


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return ""


def _gateway_import_status() -> dict[str, Any]:
    try:
        from vnpy_ctp import CtpGateway

        return {
            "ok": True,
            "default_name": getattr(CtpGateway, "default_name", ""),
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "default_name": "",
            "error": repr(exc),
        }


def _codesign_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    result = subprocess.run(
        ["codesign", "--verify", "--verbose=1", str(path)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return "valid"
    return (result.stderr or result.stdout or "invalid").strip()


def _build_checklist(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "step": 1,
            "item": "固定vnpy_ctp版本为6.7.2.1",
            "status": "done" if summary["runtime"]["vnpy_ctp_version"] == "6.7.2.1" else "needs_fix",
            "note": "最新版6.7.11.4在当前Mac arm64编译失败。",
        },
        {
            "step": 2,
            "item": "补齐framework二进制并做ad-hoc签名",
            "status": "done" if summary["framework_status"]["md_codesign"] == "valid" and summary["framework_status"]["td_codesign"] == "valid" else "needs_fix",
            "note": "从包内Mach-O库复制到framework期望位置。",
        },
        {
            "step": 3,
            "item": "通过wrapper设置DYLD_FRAMEWORK_PATH后导入CtpGateway",
            "status": "done" if summary["gateway_import"]["ok"] else "needs_fix",
            "note": "使用run_ctp_stage176_mac_readonly_probe.sh启动探针。",
        },
        {
            "step": 4,
            "item": "配置SimNow或实盘CTP环境变量",
            "status": "pending_user",
            "note": "凭证不进入repo或聊天。",
        },
        {
            "step": 5,
            "item": "运行只读连接探针",
            "status": "waiting_for_ctp_env",
            "note": "bash run_ctp_stage176_mac_readonly_probe.sh --connect --wait-seconds 30",
        },
    ]
    return pd.DataFrame(rows)


def _write_runbook(summary: dict[str, Any]) -> None:
    lines = [
        "# Stage176 Mac原生CTP只读Runbook",
        "",
        "## 当前结论",
        "",
        "- 最终在Mac上跑第78实盘是可以继续推进的，但需要固定 `vnpy_ctp==6.7.2.1`。",
        "- 当前Mac已经完成安装、framework补齐、ad-hoc签名和 `CtpGateway` 导入验证。",
        "- 连接账号前仍只允许只读探针，不允许自动下单。",
        "",
        "## 固定版本",
        "",
        "```bash",
        ".py311/bin/python -m pip install 'vnpy_ctp==6.7.2.1'",
        "```",
        "",
        "## Framework修复",
        "",
        "```bash",
        "cp .py311/lib/python3.11/site-packages/vnpy_ctp/api/libs/libthostmduserapi_se.a .py311/lib/python3.11/site-packages/vnpy_ctp/api/libs/thostmduserapi_se.framework/Versions/A/thostmduserapi_se",
        "cp .py311/lib/python3.11/site-packages/vnpy_ctp/api/libs/libthosttraderapi_se.a .py311/lib/python3.11/site-packages/vnpy_ctp/api/libs/thosttraderapi_se.framework/Versions/A/thosttraderapi_se",
        "codesign --force --sign - .py311/lib/python3.11/site-packages/vnpy_ctp/api/libs/thostmduserapi_se.framework/Versions/A/thostmduserapi_se",
        "codesign --force --sign - .py311/lib/python3.11/site-packages/vnpy_ctp/api/libs/thosttraderapi_se.framework/Versions/A/thosttraderapi_se",
        "```",
        "",
        "## 只读探针",
        "",
        "默认不连接：",
        "",
        "```bash",
        "bash examples/portfolio_backtesting/run_ctp_stage176_mac_readonly_probe.sh",
        "```",
        "",
        "配置CTP环境变量后才连接：",
        "",
        "```bash",
        "bash examples/portfolio_backtesting/run_ctp_stage176_mac_readonly_probe.sh --connect --wait-seconds 30",
        "```",
        "",
        "## 安全边界",
        "",
        "- Stage176不调用 `send_order`。",
        "- 没有20-60个交易日影子对账前，不允许自动下单。",
        "- CTP账号通常不是天然只读，必须靠代码闸门和券商权限共同约束。",
    ]
    RUNBOOK_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_report(summary: dict[str, Any], checklist: pd.DataFrame) -> None:
    lines = [
        "# Stage176 Mac原生CTP路线验证",
        "",
        "## 结论",
        "",
        "- 用户目标改为最终在Mac上跑实盘后，Mac路线重新评估。",
        "- `vnpy_ctp==6.7.11.4` 当前Mac arm64编译失败。",
        "- `vnpy_ctp==6.7.2.1` 当前Mac arm64可编译安装。",
        "- 补齐framework二进制并ad-hoc签名后，`CtpGateway`可导入。",
        "- 下一关不是系统问题，而是CTP账号环境变量和SimNow/期货公司前置连接测试。",
        "",
        "## 环境状态",
        "",
        f"- 平台：`{summary['runtime']['platform']}`",
        f"- Python：`{summary['runtime']['python']}`",
        f"- vnpy_ctp版本：`{summary['runtime']['vnpy_ctp_version']}`",
        f"- CtpGateway导入：`{summary['gateway_import']['ok']}`",
        f"- 导入错误：`{summary['gateway_import']['error']}`",
        f"- 行情framework签名：`{summary['framework_status']['md_codesign']}`",
        f"- 交易framework签名：`{summary['framework_status']['td_codesign']}`",
        "",
        "## Checklist",
        "",
        checklist.to_markdown(index=False),
        "",
        "## 反思",
        "",
        "- 运行前过拟合反思：否。Mac执行环境验证不改变策略参数。",
        "- 运行后过拟合反思：否。只是固定依赖版本和动态库加载方式。",
        "- 运行前继续价值反思：是。用户明确希望最终Mac实盘。",
        "- 运行后继续价值反思：是。Mac原生路线已经从安装层推进到连接层。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    md_bin = VNPY_CTP_LIBS_DIR / "thostmduserapi_se.framework/Versions/A/thostmduserapi_se"
    td_bin = VNPY_CTP_LIBS_DIR / "thosttraderapi_se.framework/Versions/A/thosttraderapi_se"
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
            "vnpy_ctp_version": _package_version("vnpy_ctp"),
        },
        "framework_status": {
            "libs_dir": str(VNPY_CTP_LIBS_DIR),
            "md_binary": str(md_bin),
            "td_binary": str(td_bin),
            "md_exists": md_bin.exists(),
            "td_exists": td_bin.exists(),
            "md_codesign": _codesign_status(md_bin),
            "td_codesign": _codesign_status(td_bin),
        },
        "gateway_import": _gateway_import_status(),
        "decision": {
            "mac_native_route": "continue",
            "pin_version": "vnpy_ctp==6.7.2.1",
            "use_wrapper": str(PROBE_WRAPPER_PATH),
            "next_gate": "ctp_env_and_readonly_connect",
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "runbook": str(RUNBOOK_PATH),
            "checklist": str(CHECKLIST_PATH),
            "probe_wrapper": str(PROBE_WRAPPER_PATH),
        },
    }
    checklist = _build_checklist(summary)
    checklist.to_csv(CHECKLIST_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_runbook(summary)
    _write_report(summary, checklist)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
