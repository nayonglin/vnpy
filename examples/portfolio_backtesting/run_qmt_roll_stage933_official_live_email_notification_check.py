from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_email_notify import (
    CONFIRM_SEND_EMAIL_TEXT,
    load_official_live_email_config,
    send_official_live_email_notification,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live email notification config check and smoke sender.")
    parser.add_argument("--mode", choices=["config-check", "dry-run", "send-test"], default="config-check")
    parser.add_argument("--env-file", default="")
    parser.add_argument("--confirm-send-email", default="")
    args = parser.parse_args()

    env_file = Path(args.env_file) if args.env_file else None
    if args.mode == "dry-run":
        os.environ["OFFICIAL_LIVE_EMAIL_ENABLED"] = "1"
        os.environ["OFFICIAL_LIVE_EMAIL_DRY_RUN"] = "1"
    elif args.mode == "send-test":
        if args.confirm_send_email != CONFIRM_SEND_EMAIL_TEXT:
            raise SystemExit(f"send-test requires --confirm-send-email {CONFIRM_SEND_EMAIL_TEXT}")
        os.environ["OFFICIAL_LIVE_EMAIL_DRY_RUN"] = "0"

    config = load_official_live_email_config(env_file)
    summary: dict[str, object] = {
        "model_tag": "stage933_official_live_email_notification_check_v1",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": args.mode,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "config": config.masked,
        "judgement": {
            "overfit_before": "否。Stage933 只验证通知链路，不改策略参数。",
            "continue_before": "是。实盘自动化需要独立可观测告警通道。",
            "overfit_after": "否。邮件发送结果不会反馈到 C9 参数或信号。",
            "continue_after": "是。配置通过后应由 Stage929/930/931/932 自动落邮件审计。",
        },
    }

    if args.mode in {"dry-run", "send-test"}:
        notification = send_official_live_email_notification(
            subject=f"[C9/15w][email-check] {args.mode}",
            body="\n".join(
                [
                    "C9/15w 官方实盘邮件通知链路测试。",
                    f"mode: {args.mode}",
                    f"generated_at: {summary['generated_at']}",
                    f"official_live: {OFFICIAL_LIVE_VERSION} / {OFFICIAL_LIVE_ALIAS}",
                    "",
                    "这封邮件不代表策略信号，不触发下单。",
                ]
            ),
            event_type="stage933_email_check",
            severity="info",
            metadata={"mode": args.mode},
            env_file=env_file,
        )
        summary["notification"] = notification

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
