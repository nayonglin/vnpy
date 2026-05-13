from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage253_simnow_failure_triage_v1"
OUTPUT_PREFIX = "qmt_roll_stage253_simnow_failure_triage"

READONLY_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json"
NETWORK_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage179_simnow_network_probe_summary_stage179_simnow_network_probe_v1.json"
STAGE247_PATH = PROJECT_DIR.parent.parent / "research/lines/futures_trend/stages/20260512_1540_stage247_simnow_readonly_snapshot_retest.md"
STAGE248_PATH = PROJECT_DIR.parent.parent / "research/lines/futures_trend/stages/20260512_1601_stage248_confirmed_flat_position_gate.md"
LOCAL_ENV_PATH = PROJECT_DIR / "ctp_simnow.local.env"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _masked_env_status() -> dict[str, Any]:
    status: dict[str, Any] = {"exists": LOCAL_ENV_PATH.exists(), "keys": {}}
    if not LOCAL_ENV_PATH.exists():
        return status
    for raw in LOCAL_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if key in {"CTP_USERID", "CTP_BROKERID"} and len(value) > 4:
            shown = f"{value[:2]}***{value[-2:]} len={len(value)}"
        elif key in {"CTP_PASSWORD", "CTP_APPID", "CTP_AUTH_CODE"}:
            shown = f"configured={bool(value)} len={len(value)}"
        else:
            shown = value
        status["keys"][key] = shown
    return status


def _history_success_flags() -> dict[str, bool]:
    text = "\n".join([_read_text(STAGE247_PATH), _read_text(STAGE248_PATH)])
    return {
        "historical_readonly_snapshots_received": "readonly_snapshots_received" in text,
        "historical_td_login_success": "交易服务器登录成功" in text or "交易服务器：连接成功、授权验证成功、登录成功" in text,
        "historical_confirmed_flat": "position_snapshot_state=confirmed_flat" in text or "`position_snapshot_state=confirmed_flat`" in text,
    }


def _network_fronts(network_summary: dict[str, Any]) -> dict[str, Any]:
    results = network_summary.get("results", [])
    reachable = sorted({row.get("front", "") for row in results if row.get("ok")})
    refused = sorted({row.get("front", "") for row in results if "ConnectionRefusedError" in str(row.get("error", ""))})
    timeout = sorted({row.get("front", "") for row in results if "TimeoutError" in str(row.get("error", ""))})
    return {
        "reachable_fronts": reachable,
        "connection_refused_fronts": refused,
        "timeout_fronts": timeout,
    }


def _diagnose(readonly_summary: dict[str, Any], network_summary: dict[str, Any], history: dict[str, bool]) -> list[dict[str, Any]]:
    log_analysis = readonly_summary.get("log_analysis", {})
    network = _network_fronts(network_summary)
    findings: list[dict[str, Any]] = []

    findings.append(
        {
            "item": "本地 vn.py/vnpy_ctp 运行链路",
            "evidence": f"gateway_import={readonly_summary.get('gateway_import', {})}",
            "judgement": "基本排除",
            "reason": "历史上同一 Mac wrapper 已经拿到交易登录、结算确认、合约和账户快照。",
        }
    )
    findings.append(
        {
            "item": "网络可达性",
            "evidence": json.dumps(network, ensure_ascii=False),
            "judgement": "部分阻塞",
            "reason": "当前只有 7x24_182 可达；第一套交易环境当前 Connection refused，旧 180.* 前置超时。",
        }
    )
    findings.append(
        {
            "item": "AppID/AuthCode/认证链路",
            "evidence": f"td_auth_success={log_analysis.get('td_auth_success')}",
            "judgement": "大概率不是主因",
            "reason": "最新 7x24 探针已到交易服务器授权验证成功，随后才在交易登录阶段失败。",
        }
    )
    findings.append(
        {
            "item": "7x24 交易账号/密码/环境匹配",
            "evidence": str(readonly_summary.get("failure_reason", "")),
            "judgement": "当前第一嫌疑",
            "reason": "行情登录和交易认证成功，但交易登录返回 code=3 `CTP:不合法的登录`，且历史 Stage215 也出现同一模式。",
        }
    )
    findings.append(
        {
            "item": "第一套交易环境账号",
            "evidence": json.dumps(history, ensure_ascii=False),
            "judgement": "历史曾成功，当前不可复验",
            "reason": "Stage247/248 证明 trading 前置曾成功；当前 30001/30011 网络拒绝连接，无法判断账号是否仍可用。",
        }
    )
    return findings


def _to_markdown(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_empty_"
    return pd.DataFrame(rows).to_markdown(index=False)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    network_summary = _read_json(NETWORK_SUMMARY_PATH)
    env_status = _masked_env_status()
    history = _history_success_flags()
    findings = _diagnose(readonly_summary, network_summary, history)

    root_cause = "7x24账号/密码/环境生效状态不匹配；第一套交易前置当前网络不可用，无法作为替代验证。"
    next_tests = [
        "不要继续反复登录 7x24，避免触发连续失败限制。",
        "等第一套交易前置 30001/30011 可达时，优先重跑 SIMNOW_FRONT=trading 的 Stage251。",
        "若必须使用 7x24，请在 SimNow 官网确认该资金账号已开通/生效 7x24 或第二套环境，且密码是该环境对应密码。",
        "确认后再重跑 Stage251；Stage251 未通过前，不写真实 submit adapter。",
    ]

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root_cause": root_cause,
        "env_status": env_status,
        "history": history,
        "network": _network_fronts(network_summary),
        "readonly_status": readonly_summary.get("status", ""),
        "readonly_failure_reason": readonly_summary.get("failure_reason", ""),
        "findings": findings,
        "next_tests": next_tests,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "judgement": {
            "overfit_before": "否。故障定位只分析执行环境，不改策略参数。",
            "continue_before": "是。必须把登录失败根因收敛清楚，才能讨论 SimNow 下单。",
            "overfit_after": "否。本阶段不影响回测收益。",
            "continue_after": "是，但下一步需要用户确认 SimNow 7x24/第二套环境账号状态。",
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Stage253 SimNow Failure Triage",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 根因判断：`{root_cause}`",
        f"- 最新只读状态：`{summary['readonly_status']}`",
        f"- 最新失败原因：`{summary['readonly_failure_reason']}`",
        "",
        "## 关键定位",
        "",
        _to_markdown(findings),
        "",
        "## 下一步测试",
        "",
        *[f"- {item}" for item in next_tests],
        "",
        "## 配置可见性（已脱敏）",
        "",
        "```json",
        json.dumps(env_status, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 说明",
        "",
        "- 本阶段不连接服务器，不触发登录，不调用下单 API。",
        "- 当前结论不是“策略不能跑”，而是“SimNow 账号/前置还没稳定通过提交前门禁”。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary["outputs"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
