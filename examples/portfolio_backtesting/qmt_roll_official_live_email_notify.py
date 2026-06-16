from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DEFAULT_ENV_FILE = PROJECT_DIR / "official_live_email.local.env"
EMAIL_AUDIT_LOG_PATH = OUTPUT_DIR / "qmt_roll_official_live_email_notifications.ndjson"

ENV_PREFIX = "OFFICIAL_LIVE_EMAIL_"
CONFIRM_SEND_EMAIL_TEXT = "I_UNDERSTAND_THIS_SENDS_OFFICIAL_LIVE_EMAIL"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[;,]", value) if item.strip()]


def _clean_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.startswith(ENV_PREFIX):
            continue
        values[key] = _clean_env_value(value)
    return values


def _merged_env(env_file: Path | None = None) -> dict[str, str]:
    path = env_file or Path(os.getenv("OFFICIAL_LIVE_EMAIL_ENV_FILE", str(DEFAULT_ENV_FILE)))
    values = _load_env_file(path)
    for key, value in os.environ.items():
        if key.startswith(ENV_PREFIX):
            values[key] = value
    return values


def _int_value(value: str | None, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _mask_address(value: str) -> str:
    if "@" not in value:
        return value[:2] + "***" if value else ""
    local, domain = value.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "***"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}"


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", text.strip())[:80].strip("_")
    return slug or "notification"


@dataclass(frozen=True)
class OfficialLiveEmailConfig:
    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    sender: str
    recipients: tuple[str, ...]
    cc: tuple[str, ...]
    use_ssl: bool
    starttls: bool
    smtp_auth: bool
    timeout_seconds: int
    dry_run: bool
    attach_files: bool
    max_attachment_bytes: int
    env_file: Path

    @property
    def missing_required(self) -> list[str]:
        missing: list[str] = []
        if not self.smtp_host:
            missing.append("OFFICIAL_LIVE_EMAIL_SMTP_HOST")
        if not self.sender:
            missing.append("OFFICIAL_LIVE_EMAIL_FROM")
        if not self.recipients:
            missing.append("OFFICIAL_LIVE_EMAIL_TO")
        if self.smtp_auth and not self.smtp_user:
            missing.append("OFFICIAL_LIVE_EMAIL_SMTP_USER")
        if self.smtp_auth and not self.smtp_password:
            missing.append("OFFICIAL_LIVE_EMAIL_SMTP_PASSWORD")
        return missing

    @property
    def masked(self) -> dict[str, Any]:
        return {
            "enabled": int(self.enabled),
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_user": _mask_address(self.smtp_user),
            "from": _mask_address(self.sender),
            "to_count": len(self.recipients),
            "cc_count": len(self.cc),
            "use_ssl": int(self.use_ssl),
            "starttls": int(self.starttls),
            "smtp_auth": int(self.smtp_auth),
            "timeout_seconds": self.timeout_seconds,
            "dry_run": int(self.dry_run),
            "attach_files": int(self.attach_files),
            "attachment_policy": "key_summary_only_no_attachments",
            "max_attachment_bytes": self.max_attachment_bytes,
            "env_file": str(self.env_file.resolve()),
            "env_file_exists": int(self.env_file.exists()),
            "missing_required": self.missing_required,
        }


def load_official_live_email_config(env_file: Path | None = None) -> OfficialLiveEmailConfig:
    path = env_file or Path(os.getenv("OFFICIAL_LIVE_EMAIL_ENV_FILE", str(DEFAULT_ENV_FILE)))
    values = _merged_env(path)
    port = _int_value(values.get("OFFICIAL_LIVE_EMAIL_SMTP_PORT"), 465)
    use_ssl = _truthy(values.get("OFFICIAL_LIVE_EMAIL_USE_SSL")) or (
        "OFFICIAL_LIVE_EMAIL_USE_SSL" not in values and port == 465
    )
    starttls = _truthy(values.get("OFFICIAL_LIVE_EMAIL_STARTTLS")) or (
        "OFFICIAL_LIVE_EMAIL_STARTTLS" not in values and port == 587 and not use_ssl
    )
    smtp_auth = not str(values.get("OFFICIAL_LIVE_EMAIL_SMTP_AUTH", "1")).strip().lower() in {"0", "false", "no", "off"}
    return OfficialLiveEmailConfig(
        enabled=_truthy(values.get("OFFICIAL_LIVE_EMAIL_ENABLED")),
        smtp_host=values.get("OFFICIAL_LIVE_EMAIL_SMTP_HOST", "").strip(),
        smtp_port=port,
        smtp_user=values.get("OFFICIAL_LIVE_EMAIL_SMTP_USER", "").strip(),
        smtp_password=values.get("OFFICIAL_LIVE_EMAIL_SMTP_PASSWORD", ""),
        sender=values.get("OFFICIAL_LIVE_EMAIL_FROM", values.get("OFFICIAL_LIVE_EMAIL_SMTP_USER", "")).strip(),
        recipients=tuple(_split_addresses(values.get("OFFICIAL_LIVE_EMAIL_TO"))),
        cc=tuple(_split_addresses(values.get("OFFICIAL_LIVE_EMAIL_CC"))),
        use_ssl=use_ssl,
        starttls=starttls,
        smtp_auth=smtp_auth,
        timeout_seconds=_int_value(values.get("OFFICIAL_LIVE_EMAIL_TIMEOUT_SECONDS"), 15),
        dry_run=_truthy(values.get("OFFICIAL_LIVE_EMAIL_DRY_RUN")),
        attach_files=False,
        max_attachment_bytes=_int_value(values.get("OFFICIAL_LIVE_EMAIL_MAX_ATTACHMENT_BYTES"), 5_000_000),
        env_file=path,
    )


def _build_message(
    *,
    config: OfficialLiveEmailConfig,
    subject: str,
    body: str,
    severity: str,
    event_type: str,
    attachments: list[Path],
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.sender
    message["To"] = ", ".join(config.recipients)
    if config.cc:
        message["Cc"] = ", ".join(config.cc)
    message["Date"] = datetime.now().astimezone().strftime("%a, %d %b %Y %H:%M:%S %z")
    message["X-Official-Live-Event"] = event_type
    message["X-Official-Live-Severity"] = severity
    message["X-Official-Live-Generated-At"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message.set_content(body)
    return message


def _send_message(config: OfficialLiveEmailConfig, message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if config.use_ssl:
        with smtplib.SMTP_SSL(
            config.smtp_host,
            config.smtp_port,
            timeout=config.timeout_seconds,
            context=context,
        ) as smtp:
            if config.smtp_auth:
                smtp.login(config.smtp_user, config.smtp_password)
            smtp.send_message(message)
        return
    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=config.timeout_seconds) as smtp:
        smtp.ehlo()
        if config.starttls:
            smtp.starttls(context=context)
            smtp.ehlo()
        if config.smtp_auth:
            smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(message)


def _write_audit(result: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with EMAIL_AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")


def send_official_live_email_notification(
    *,
    subject: str,
    body: str,
    event_type: str,
    severity: str = "info",
    attachments: list[str | Path] | None = None,
    metadata: dict[str, Any] | None = None,
    env_file: Path | None = None,
) -> dict[str, Any]:
    config = load_official_live_email_config(env_file)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result: dict[str, Any] = {
        "generated_at": generated_at,
        "event_type": event_type,
        "severity": severity,
        "subject": subject,
        "email_enabled": int(config.enabled),
        "email_status": "disabled",
        "config": config.masked,
        "metadata": metadata or {},
        "audit_log": str(EMAIL_AUDIT_LOG_PATH.resolve()),
    }
    if not config.enabled:
        _write_audit(result)
        return result

    missing = config.missing_required
    if missing:
        result["email_status"] = "blocked_missing_config"
        result["missing_required"] = missing
        _write_audit(result)
        return result

    paths = [Path(item) for item in (attachments or [])]
    body_for_email = body.rstrip()
    referenced_files: list[dict[str, Any]] = []
    missing_files: list[dict[str, Any]] = []
    for item in paths:
        path = Path(item)
        if path.exists() and path.is_file():
            referenced_files.append({"path": str(path.resolve()), "bytes": path.stat().st_size})
        else:
            missing_files.append({"path": str(path), "reason": "missing_or_not_file"})
    result["attachment_policy"] = "key_summary_only_no_attachments"
    result["attached_files"] = []
    result["skipped_attachments"] = [
        {"path": str(Path(item).resolve()) if Path(item).exists() else str(item), "reason": "attachments_disabled_key_summary_only"}
        for item in paths
    ]
    result["referenced_files"] = referenced_files
    result["missing_referenced_files"] = missing_files
    result["inline_files"] = []
    result["skipped_inline_files"] = []

    try:
        message = _build_message(
            config=config,
            subject=subject,
            body=body_for_email,
            severity=severity,
            event_type=event_type,
            attachments=[],
        )
        if config.dry_run:
            dry_run_path = OUTPUT_DIR / f"qmt_roll_official_live_email_dry_run_{datetime.now():%Y%m%d_%H%M%S}_{_safe_slug(event_type)}.eml"
            dry_run_path.write_bytes(bytes(message))
            result["email_status"] = "dry_run_written"
            result["dry_run_eml"] = str(dry_run_path.resolve())
        else:
            _send_message(config, message)
            result["email_status"] = "sent"
            result["sent_to_count"] = len(config.recipients) + len(config.cc)
    except Exception as exc:
        result["email_status"] = "send_failed"
        result["error"] = repr(exc)
    _write_audit(result)
    return result
