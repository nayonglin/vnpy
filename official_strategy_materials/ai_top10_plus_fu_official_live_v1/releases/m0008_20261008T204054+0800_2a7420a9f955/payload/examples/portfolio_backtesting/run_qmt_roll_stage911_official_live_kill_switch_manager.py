from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_phase_d_config import KILL_SWITCH_PATH
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage911_official_live_kill_switch_manager_v1"
OUTPUT_PREFIX = "qmt_roll_stage911_official_live_kill_switch_manager"
CLEAR_CONFIRM_TEXT = "I_UNDERSTAND_THIS_CLEARS_PHASE_D_KILL_SWITCH"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "audit_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_audit_{run_id}_{MODEL_TAG}.csv",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _active(payload: dict[str, Any]) -> bool:
    return bool(payload.get("enabled", False) or payload.get("kill_switch_active", False))


def _build_payload(action: str, reason: str, actor: str, previous: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history = previous.get("history", []) if isinstance(previous.get("history"), list) else []
    history.append(
        {
            "action": action,
            "reason": reason,
            "actor": actor,
            "at": now,
            "previous_active": _active(previous),
        }
    )
    if action == "enable":
        return {
            "enabled": True,
            "kill_switch_active": True,
            "reason": reason,
            "actor": actor,
            "updated_at": now,
            "history": history[-50:],
        }
    if action == "clear":
        return {
            "enabled": False,
            "kill_switch_active": False,
            "reason": reason,
            "actor": actor,
            "updated_at": now,
            "history": history[-50:],
        }
    return previous


def _build_report(summary: dict[str, Any], audit: pd.DataFrame) -> str:
    audit_md = audit.to_markdown(index=False) if not audit.empty else "_empty_"
    return "\n".join(
        [
            "# Stage911 Official Live Kill Switch Manager",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 请求动作：`{summary['action']}`",
            f"- kill switch active：`{summary['kill_switch_active_after']}`",
            f"- 状态：`{summary['manager_status']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## Audit",
            "",
            audit_md,
            "",
            "## 说明",
            "",
            "- Stage911 只管理本地 Phase D kill switch 文件，不连接 CTP，不提交委托。",
            "- 清除 kill switch 必须提供确认文本，启用和查看不需要确认。",
            "- kill switch active 时，Stage903/Stage910 必须 fail-closed。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D kill switch manager.")
    parser.add_argument("--action", choices=["status", "enable", "clear"], default="status")
    parser.add_argument("--reason", default="")
    parser.add_argument("--actor", default="codex")
    parser.add_argument("--confirm-clear", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    before = _read_json(KILL_SWITCH_PATH)
    before_active = _active(before)
    manager_status = "status_only"
    after = before

    if args.action == "enable":
        reason = args.reason or "manual_phase_d_kill_switch_enable"
        after = _build_payload("enable", reason, args.actor, before)
        _write_json(KILL_SWITCH_PATH, after)
        manager_status = "kill_switch_enabled"
    elif args.action == "clear":
        if args.confirm_clear != CLEAR_CONFIRM_TEXT:
            manager_status = "clear_blocked_confirmation_missing"
        else:
            reason = args.reason or "manual_phase_d_kill_switch_clear"
            after = _build_payload("clear", reason, args.actor, before)
            _write_json(KILL_SWITCH_PATH, after)
            manager_status = "kill_switch_cleared"

    after_active = _active(after)
    audit = pd.DataFrame(
        [
            {
                "action": args.action,
                "manager_status": manager_status,
                "kill_switch_active_before": int(before_active),
                "kill_switch_active_after": int(after_active),
                "reason": args.reason,
                "actor": args.actor,
                "kill_switch_path": str(KILL_SWITCH_PATH.resolve()),
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        ]
    )
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "action": args.action,
        "manager_status": manager_status,
        "kill_switch_path": str(KILL_SWITCH_PATH.resolve()),
        "kill_switch_active_before": before_active,
        "kill_switch_active_after": after_active,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。kill switch 是执行运维控制，不改策略参数。",
            "continue_before": "是。全自动必须有可审计的手动熔断入口。",
            "overfit_after": "否。只改变本地熔断状态，不反馈策略。",
            "continue_after": "是。下一步应跑 Stage903/Stage910 验证 kill switch fail-closed。",
        },
    }
    audit.to_csv(paths["audit_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, audit), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
