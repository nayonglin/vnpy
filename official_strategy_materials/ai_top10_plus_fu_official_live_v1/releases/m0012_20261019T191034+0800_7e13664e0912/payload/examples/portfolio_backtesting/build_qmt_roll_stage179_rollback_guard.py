from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from qmt_roll_official_live_execution_ledger import read_execution_ledger


V2_RESERVATION_EVENTS = frozenset(
    {
        "reserved",
        "final_pre_send_gate_blocked_after_reserve",
        "api_slot_reservation_blocked",
        "adapter_exception_after_reserve",
        "spool_crash_recovery_pre_send_safe_terminal",
    }
)
V2_SIDE_EFFECT_EVENTS = frozenset(
    {
        "api_slot_reserved",
        "send_order_called",
        "send_order_returned",
        "send_order_returned_empty",
        "submitted_to_ctp",
        "adapter_exception_after_send",
        "unknown_order_status_after_send",
        "residual_order_active_after_cancel",
        "residual_order_unknown_after_cancel",
        "cancel_order_called",
        "fill_reconciliation_pending",
        "order_traded_volume_observed_without_trade_detail",
        "close_volume_reconciled_without_trade_detail",
        "filled_or_part_filled",
    }
)


@dataclass(frozen=True, slots=True)
class LedgerRollbackSafety:
    disposition: str
    v2_row_count: int
    reservation_row_count: int
    side_effect_row_count: int
    side_effect_event_types: tuple[str, ...]


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_v2_row(row: dict[str, Any]) -> bool:
    fingerprint_version = row.get(
        "intent_fingerprint_version",
        row.get("fingerprint_version", 0),
    )
    try:
        if int(fingerprint_version) >= 2:
            return True
    except (TypeError, ValueError):
        pass
    return any(
        _clean(row.get(field))
        for field in (
            "spool_lease_owner",
            "spool_lease_token",
            "service_generation",
            "connection_generation",
            "api_slot_batch_id",
        )
    )


def inspect_ledger_rollback_safety(
    rows: Iterable[dict[str, Any]],
) -> LedgerRollbackSafety:
    v2_rows = [dict(row) for row in rows if _is_v2_row(row)]
    side_effect_rows = [
        row
        for row in v2_rows
        if _clean(row.get("event_type")) in V2_SIDE_EFFECT_EVENTS
    ]
    reservation_rows = [
        row
        for row in v2_rows
        if _clean(row.get("event_type")) in V2_RESERVATION_EVENTS
    ]
    if side_effect_rows:
        disposition = "v2_reader_required_reconcile_and_roll_forward"
    elif v2_rows:
        disposition = "broker_snapshot_required_keep_v2_reader"
    else:
        disposition = "v1_code_and_plist_rollback_allowed"
    return LedgerRollbackSafety(
        disposition=disposition,
        v2_row_count=len(v2_rows),
        reservation_row_count=len(reservation_rows),
        side_effect_row_count=len(side_effect_rows),
        side_effect_event_types=tuple(
            sorted({_clean(row.get("event_type")) for row in side_effect_rows})
        ),
    )


def _render_markdown(safety: LedgerRollbackSafety, ledger_path: Path) -> str:
    events = ", ".join(safety.side_effect_event_types) or "无"
    return "\n".join(
        (
            "# Stage179 Ledger 回滚闸门",
            "",
            f"- ledger: `{ledger_path}`",
            f"- disposition: `{safety.disposition}`",
            f"- V2 行数: {safety.v2_row_count}",
            f"- reservation/safe-terminal 行数: {safety.reservation_row_count}",
            f"- side-effect 行数: {safety.side_effect_row_count}",
            f"- side-effect 类型: {events}",
            "",
            "本工具只读 ledger，不修改原文件。",
        )
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args(argv)

    before = args.ledger.read_bytes() if args.ledger.exists() else b""
    safety = inspect_ledger_rollback_safety(read_execution_ledger(args.ledger))
    payload = {"ledger_path": str(args.ledger), **asdict(safety)}
    rendered_json = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered_json, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(
            _render_markdown(safety, args.ledger) + "\n",
            encoding="utf-8",
        )
    after = args.ledger.read_bytes() if args.ledger.exists() else b""
    if before != after:
        raise RuntimeError("ledger_changed_during_readonly_rollback_inspection")
    print(rendered_json, end="")


if __name__ == "__main__":
    main()
