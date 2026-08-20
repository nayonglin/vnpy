from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass, is_dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import tempfile
import time
from typing import Any, Protocol

from qmt_roll_official_live_intent_spool import (
    IntentLease,
    LeaseRecoveryEvidence,
    SpoolTransitionError,
    expire_due_intents,
    expired_inflight_leases,
    lease_next,
    recover_expired_lease,
    reconcile_side_effect_unknown,
    side_effect_unknown_leases,
    transition_intent,
    wakeup_socket_path,
)
from qmt_roll_official_live_execution_ledger import (
    read_execution_ledger,
    recover_expired_spool_lease,
    valid_post_api_slot_no_native_safe_terminal,
)
from qmt_roll_official_live_time import system_clock_domain_id


READINESS_SCHEMA_VERSION = 1
DEFAULT_DEQUEUE_TO_SEND_SECONDS = 20.0
DEFAULT_POLL_SECONDS = 0.1
DEFAULT_LEASE_SECONDS = 3.0


class ExecutorServiceError(RuntimeError):
    pass


class ExecutorAlreadyRunningError(ExecutorServiceError):
    pass


@dataclass(frozen=True, slots=True)
class TdReadinessLease:
    service_generation: str
    connection_generation: str
    runtime_profile: str
    official_version: str
    capital: float
    issued_epoch_ns: int
    expires_epoch_ns: int
    last_complete_startup_bundle_epoch_ns: int
    service_kind: str = ""
    send_order_api_called_count: int = 0
    cancel_order_api_called_count: int = 0
    order_api_called_count: int = 0
    order_api_evidence_complete: int = 0


@dataclass(frozen=True, slots=True)
class ExecutorServicePaths:
    spool_path: Path
    wake_socket_path: Path
    readiness_path: Path
    singleton_lock_path: Path
    ledger_path: Path

    @classmethod
    def for_spool(
        cls,
        *,
        spool_path: str | Path,
        ledger_path: str | Path,
        readiness_path: str | Path | None = None,
        singleton_lock_path: str | Path | None = None,
    ) -> ExecutorServicePaths:
        spool = Path(spool_path).expanduser().resolve(strict=False)
        parent = spool.parent
        return cls(
            spool_path=spool,
            wake_socket_path=wakeup_socket_path(spool),
            readiness_path=(
                Path(readiness_path).expanduser().resolve(strict=False)
                if readiness_path is not None
                else parent / "executor_readiness.json"
            ),
            singleton_lock_path=(
                Path(singleton_lock_path).expanduser().resolve(strict=False)
                if singleton_lock_path is not None
                else parent / "executor.lock"
            ),
            ledger_path=Path(ledger_path).expanduser().resolve(strict=False),
        )


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    intent_id: str
    disposition: str
    ledger_fingerprint: str
    api_slot_batch_id: str
    blockers: tuple[str, ...]
    send_order_call_count: int
    cancel_order_call_count: int
    safe_terminal_record_checksum: str = ""

    @classmethod
    def blocked(
        cls,
        intent_id: str,
        blocker: str,
        *,
        disposition: str = "blocked",
    ) -> ExecutionResult:
        return cls(
            intent_id=str(intent_id),
            disposition=disposition,
            ledger_fingerprint="",
            api_slot_batch_id="",
            blockers=(str(blocker),),
            send_order_call_count=0,
            cancel_order_call_count=0,
        )

    @classmethod
    def no_side_effect_retryable(
        cls,
        intent_id: str,
        *,
        ledger_fingerprint: str,
        blockers: tuple[str, ...] | list[str],
    ) -> ExecutionResult:
        return cls(
            intent_id=str(intent_id),
            disposition="no_side_effect_retryable",
            ledger_fingerprint=str(ledger_fingerprint),
            api_slot_batch_id="",
            blockers=tuple(str(item) for item in blockers if str(item)),
            send_order_call_count=0,
            cancel_order_call_count=0,
        )

    @classmethod
    def post_slot_no_native_retryable(
        cls,
        intent_id: str,
        *,
        ledger_fingerprint: str,
        api_slot_batch_id: str,
        blockers: tuple[str, ...] | list[str],
        safe_terminal_record_checksum: str = "",
    ) -> ExecutionResult:
        return cls(
            intent_id=str(intent_id),
            disposition="post_slot_no_native_retryable",
            ledger_fingerprint=str(ledger_fingerprint),
            api_slot_batch_id=str(api_slot_batch_id),
            blockers=tuple(str(item) for item in blockers if str(item)),
            send_order_call_count=0,
            cancel_order_call_count=0,
            safe_terminal_record_checksum=str(safe_terminal_record_checksum),
        )


class IntentSpool(Protocol):
    def recover_expired(self, **kwargs: Any) -> Any: ...

    def expire_due(self, **kwargs: Any) -> Any: ...

    def lease_next(self, **kwargs: Any) -> Any: ...

    def mark_sending(self, lease: Any, **kwargs: Any) -> Any: ...

    def mark_result(
        self,
        lease: Any,
        result: ExecutionResult,
        **kwargs: Any,
    ) -> Any: ...


class ExecutionSession(Protocol):
    def connect(self) -> None: ...

    def readiness_lease(self, *, now_epoch_ns: int) -> TdReadinessLease: ...

    def transport_blockers(self) -> list[str]: ...

    def pre_lease_blockers(self) -> list[str]: ...

    def pre_lease_authorized_intents(self) -> Mapping[str, str] | None: ...

    def lease_execution_guard(self) -> Any: ...

    def reconnect(self) -> None: ...

    def execute_spool_lease(
        self,
        *,
        lease: Any,
        hard_deadline_monotonic: float,
        api_slot_durable: Callable[[str], bool] | None = None,
    ) -> ExecutionResult: ...

    def close(self) -> None: ...


class SQLiteIntentSpool:
    """Small transition adapter over the Task7 SQLite spool contract."""

    def __init__(
        self,
        connection: Any,
        *,
        ledger_path: str | Path | None = None,
        close_retry_after_cancel_seconds: int = 30,
    ) -> None:
        self.connection = connection
        self.ledger_path = (
            Path(ledger_path).expanduser().resolve(strict=False)
            if ledger_path is not None
            else None
        )
        self.close_retry_after_cancel_seconds = max(
            1,
            int(close_retry_after_cancel_seconds),
        )

    @staticmethod
    def _ledger_inputs(lease: IntentLease) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = dict(lease.intent.payload)
        raw_order_request = payload.get("order_request")
        if not isinstance(raw_order_request, dict):
            raise ExecutorServiceError("spool_recovery_order_request_missing")
        order_request = dict(raw_order_request)
        row = dict(payload)
        row["order_request_json"] = json.dumps(
            order_request,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for key in (
            "vt_symbol",
            "symbol",
            "exchange",
            "direction",
            "offset",
            "price",
            "volume",
        ):
            if key in order_request:
                row[key] = order_request[key]
        return row, order_request

    def recover_expired(self, **kwargs: Any) -> list[str]:
        if self.ledger_path is None:
            return []
        leases = expired_inflight_leases(self.connection, **kwargs)
        classified: list[tuple[IntentLease, Any]] = []
        for lease in leases:
            row, order_request = self._ledger_inputs(lease)
            decision = recover_expired_spool_lease(
                target_date=lease.intent.target_date,
                row=row,
                order_request=order_request,
                spool_lease_owner=lease.intent.lease_owner,
                spool_lease_token=lease.lease_token,
                close_retry_after_cancel_seconds=(
                    self.close_retry_after_cancel_seconds
                ),
                path=self.ledger_path,
            )
            classified.append((lease, decision))
        recovered_states: list[str] = []
        if classified:
            # All per-lease classification/append operations finish before
            # one shared evidence snapshot.  This avoids O(expired_count)
            # full-ledger reads while keeping every spool CAS tied to durable
            # decision evidence.
            ledger_rows = read_execution_ledger(self.ledger_path)
            last_checksum = str(
                (ledger_rows[-1] if ledger_rows else {}).get(
                    "record_checksum", ""
                )
            )
            if len(last_checksum) != 64:
                last_checksum = hashlib.sha256(
                    json.dumps(
                        ledger_rows,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    ).encode("utf-8")
                ).hexdigest()
            for lease, decision in classified:
                spool_disposition = {
                    "requeue_pre_send": "no_side_effect",
                    "reconcile_only_side_effect_unknown": "unknown",
                    "reconciled": "reconciled",
                    "blocked_ledger_integrity": "blocked_ledger_integrity",
                }.get(decision.disposition, "unknown")
                recovered_states.append(
                    recover_expired_lease(
                        self.connection,
                        evidence=LeaseRecoveryEvidence(
                            intent_id=lease.intent.intent_id,
                            lease_owner=lease.intent.lease_owner,
                            lease_token=lease.lease_token,
                            ledger_disposition=spool_disposition,
                            ledger_fingerprint=decision.intent_fingerprint,
                            ledger_watermark=len(ledger_rows),
                            ledger_checksum_sha256=last_checksum,
                        ),
                        **kwargs,
                    )
                )

        # A prior run may already have persisted an unknown result before its
        # terminal broker query/trade callbacks arrived.  Revisit every such
        # row, including historical target dates: only exact fingerprint +
        # retained lease proof may CAS it terminal, and no path requeues it.
        unknown_decisions: list[tuple[IntentLease, Any]] = []
        for lease in side_effect_unknown_leases(self.connection):
            row, order_request = self._ledger_inputs(lease)
            decision = recover_expired_spool_lease(
                target_date=lease.intent.target_date,
                row=row,
                order_request=order_request,
                spool_lease_owner=lease.intent.lease_owner,
                spool_lease_token=lease.lease_token,
                close_retry_after_cancel_seconds=(
                    self.close_retry_after_cancel_seconds
                ),
                path=self.ledger_path,
            )
            if decision.disposition == "reconciled":
                unknown_decisions.append((lease, decision))
        if unknown_decisions:
            ledger_rows = read_execution_ledger(self.ledger_path)
            last_checksum = str(
                (ledger_rows[-1] if ledger_rows else {}).get(
                    "record_checksum", ""
                )
            )
            if len(last_checksum) != 64:
                last_checksum = hashlib.sha256(
                    json.dumps(
                        ledger_rows,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    ).encode("utf-8")
                ).hexdigest()
            for lease, decision in unknown_decisions:
                reconciled = reconcile_side_effect_unknown(
                    self.connection,
                    evidence=LeaseRecoveryEvidence(
                        intent_id=lease.intent.intent_id,
                        lease_owner=lease.intent.lease_owner,
                        lease_token=lease.lease_token,
                        ledger_disposition="reconciled",
                        ledger_fingerprint=decision.intent_fingerprint,
                        ledger_watermark=len(ledger_rows),
                        ledger_checksum_sha256=last_checksum,
                    ),
                    **kwargs,
                )
                recovered_states.append(reconciled.state)
        return recovered_states

    def expire_due(self, **kwargs: Any) -> Any:
        return expire_due_intents(self.connection, **kwargs)

    def lease_next(self, **kwargs: Any) -> IntentLease | None:
        return lease_next(self.connection, **kwargs)

    def mark_sending(self, lease: IntentLease, **kwargs: Any) -> Any:
        return transition_intent(
            self.connection,
            intent_id=lease.intent.intent_id,
            owner_id=lease.intent.lease_owner,
            lease_token=lease.lease_token,
            expected_state="leased",
            new_state="sending",
            **kwargs,
        )

    def mark_result(
        self,
        lease: IntentLease,
        result: ExecutionResult,
        **kwargs: Any,
    ) -> Any:
        expected = "sending" if result.api_slot_batch_id else "leased"
        if result.disposition == "no_side_effect_retryable":
            if (
                result.api_slot_batch_id
                or result.send_order_call_count != 0
                or result.cancel_order_call_count != 0
                or not result.ledger_fingerprint
            ):
                target = "blocked"
                result_error = (
                    "invalid_no_side_effect_retryable_result_fail_closed"
                )
            else:
                target = "ready"
                result_error = ";".join(result.blockers)
        elif result.disposition == "post_slot_no_native_retryable":
            terminal_valid = False
            if self.ledger_path is not None and result.safe_terminal_record_checksum:
                rows = read_execution_ledger(self.ledger_path)
                terminal_index = next(
                    (
                        index
                        for index, row in enumerate(rows)
                        if row.get("record_checksum")
                        == result.safe_terminal_record_checksum
                        and row.get("event_type")
                        == "post_api_slot_no_native_safe_terminal"
                        and row.get("target_date") == lease.intent.target_date
                        and row.get("intent_id") == lease.intent.intent_id
                        and row.get("intent_payload_sha256")
                        == lease.intent.payload_sha256
                        and row.get("intent_fingerprint")
                        == result.ledger_fingerprint
                        and row.get("spool_lease_owner")
                        == lease.intent.lease_owner
                        and row.get("spool_lease_token") == lease.lease_token
                        and row.get("api_slot_batch_id")
                        == result.api_slot_batch_id
                    ),
                    None,
                )
                if terminal_index is not None:
                    terminal_valid = valid_post_api_slot_no_native_safe_terminal(
                        rows, rows[terminal_index]
                    )
            if (
                not result.api_slot_batch_id
                or result.send_order_call_count != 0
                or result.cancel_order_call_count != 0
                or not result.ledger_fingerprint
                or not terminal_valid
            ):
                target = "blocked"
                result_error = "invalid_post_slot_no_native_retryable_result_fail_closed"
            else:
                target = "ready"
                result_error = ";".join(result.blockers)
        elif result.disposition == "sent":
            target = "sent"
            result_error = ";".join(result.blockers)
        elif result.disposition == "side_effect_unknown":
            target = "side_effect_unknown"
            result_error = ";".join(result.blockers)
        elif result.disposition == "expired":
            target = "expired"
            result_error = ";".join(result.blockers)
        else:
            target = "blocked"
            result_error = ";".join(result.blockers)
        return transition_intent(
            self.connection,
            intent_id=lease.intent.intent_id,
            owner_id=lease.intent.lease_owner,
            lease_token=lease.lease_token,
            expected_state=expected,
            new_state=target,
            ledger_disposition=result.disposition,
            last_error=result_error,
            **kwargs,
        )


def _atomic_json_replace(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def publish_readiness(path: str | Path, lease: TdReadinessLease) -> None:
    if not is_dataclass(lease) or type(lease) is not TdReadinessLease:
        raise ExecutorServiceError("readiness_lease_type_invalid")
    if lease.expires_epoch_ns <= lease.issued_epoch_ns:
        raise ExecutorServiceError("readiness_lease_expiry_invalid")
    _atomic_json_replace(
        Path(path),
        {
            "schema_version": READINESS_SCHEMA_VERSION,
            "status": "ready",
            **asdict(lease),
        },
    )


def revoke_readiness(
    path: str | Path,
    *,
    service_generation: str,
    reason: str,
    revoked_epoch_ns: int | None = None,
) -> None:
    _atomic_json_replace(
        Path(path),
        {
            "schema_version": READINESS_SCHEMA_VERSION,
            "status": "revoked",
            "service_generation": str(service_generation),
            "reason": str(reason),
            "revoked_epoch_ns": (
                time.time_ns() if revoked_epoch_ns is None else int(revoked_epoch_ns)
            ),
        },
    )


@contextmanager
def singleton_executor_lock(path: str | Path) -> Iterator[None]:
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ExecutorAlreadyRunningError("stage179_executor_already_running") from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


@contextmanager
def _wakeup_socket(path: Path) -> Iterator[socket.socket | None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink(missing_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        server.setblocking(False)
        server.bind(str(path))
    except OSError:
        try:
            server.close()  # type: ignore[possibly-undefined]
        except (NameError, OSError):
            pass
        yield None
        return
    try:
        yield server
    finally:
        server.close()
        path.unlink(missing_ok=True)


def _wait_for_work(
    wake_socket: socket.socket | None,
    *,
    poll_seconds: float,
    sleeper: Callable[[float], None],
) -> None:
    if wake_socket is None:
        sleeper(poll_seconds)
        return
    readable, _, _ = select.select([wake_socket], [], [], poll_seconds)
    if readable:
        try:
            while wake_socket.recv(4096):
                pass
        except BlockingIOError:
            pass


def _runtime_profile_value(runtime: Any) -> str:
    profile = getattr(runtime, "profile", "")
    return str(getattr(profile, "value", profile))


def _deadline_result(lease: Any) -> ExecutionResult:
    intent = lease.intent
    disposition = "expired" if str(intent.intent_kind) == "open" else "blocked"
    return ExecutionResult.blocked(
        intent.intent_id,
        "stage179_execution_deadline_exceeded:executor_dequeued",
        disposition=disposition,
    )


def serve_executor(
    *,
    paths: ExecutorServicePaths,
    spool: IntentSpool,
    backend_factory: Callable[[], ExecutionSession],
    runtime: Any,
    stop_requested: Callable[[], bool],
    epoch_ns: Callable[[], int] = time.time_ns,
    monotonic: Callable[[], float] = time.monotonic,
    monotonic_ns: Callable[[], int] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    readiness_heartbeat_seconds: float = 1.0,
    max_dequeue_seconds: float = 0.5,
    dequeue_to_send_seconds: float = DEFAULT_DEQUEUE_TO_SEND_SECONDS,
    lease_seconds: float = DEFAULT_LEASE_SECONDS,
    clock_domain_id: str | None = None,
) -> int:
    """Own one warm transport and execute durable leases until stopped.

    The socket is only a latency hint.  Every miss is recovered by the bounded
    poll, while the spool remains the durable source of truth.
    """

    if poll_seconds <= 0 or poll_seconds > 0.5:
        raise ExecutorServiceError("executor_poll_seconds_out_of_range")
    if dequeue_to_send_seconds <= 0:
        raise ExecutorServiceError("dequeue_to_send_seconds_invalid")
    if readiness_heartbeat_seconds <= 0:
        raise ExecutorServiceError("readiness_heartbeat_seconds_invalid")
    if max_dequeue_seconds <= 0:
        raise ExecutorServiceError("max_dequeue_seconds_invalid")
    domain_id = system_clock_domain_id() if clock_domain_id is None else str(clock_domain_id)
    monotonic_ns_now = (
        time.monotonic_ns
        if monotonic_ns is None and monotonic is time.monotonic
        else monotonic_ns or (lambda: int(monotonic() * 1_000_000_000))
    )

    service_generation = ""
    session: ExecutionSession | None = None
    with singleton_executor_lock(paths.singleton_lock_path):
        with _wakeup_socket(paths.wake_socket_path) as wake_socket:
            try:
                session = backend_factory()
                session.connect()
                initial_lease = session.readiness_lease(now_epoch_ns=epoch_ns())
                service_generation = initial_lease.service_generation
                if initial_lease.runtime_profile != _runtime_profile_value(runtime):
                    raise ExecutorServiceError(
                        "readiness_runtime_profile_mismatch:"
                        f"{initial_lease.runtime_profile}!={_runtime_profile_value(runtime)}"
                    )
                publish_readiness(paths.readiness_path, initial_lease)
                last_readiness_publish_monotonic = float(monotonic())

                while not stop_requested():
                    transport_blockers = session.transport_blockers()
                    if transport_blockers:
                        revoke_readiness(
                            paths.readiness_path,
                            service_generation=service_generation,
                            reason="transport_invalidated:"
                            + ";".join(transport_blockers),
                            revoked_epoch_ns=int(epoch_ns()),
                        )
                        session.reconnect()
                        reconnected_lease = session.readiness_lease(
                            now_epoch_ns=int(epoch_ns())
                        )
                        if (
                            reconnected_lease.service_generation
                            != service_generation
                        ):
                            raise ExecutorServiceError(
                                "service_generation_changed_on_reconnect"
                            )
                        publish_readiness(
                            paths.readiness_path,
                            reconnected_lease,
                        )
                        last_readiness_publish_monotonic = float(monotonic())
                    now_epoch = int(epoch_ns())
                    now_monotonic_ns = int(monotonic_ns_now())
                    recover_expired = getattr(spool, "recover_expired", None)
                    if callable(recover_expired):
                        recover_expired(
                            now_epoch_ns=now_epoch,
                            now_monotonic_ns=now_monotonic_ns,
                            clock_domain_id=domain_id,
                        )
                    spool.expire_due(
                        now_epoch_ns=now_epoch,
                        now_monotonic_ns=now_monotonic_ns,
                        clock_domain_id=domain_id,
                    )
                    guard_factory = getattr(
                        session,
                        "lease_execution_guard",
                        None,
                    )
                    guard = (
                        guard_factory()
                        if callable(guard_factory)
                        else nullcontext()
                    )
                    wait_for_work = False
                    completed_lease = False
                    # Production holds the submit-authorization shared flock
                    # across admission, the spool CAS, every final gate/API
                    # call, and the durable terminal transition.  Publishers
                    # and revokers take the matching exclusive flock, so an
                    # admitted record cannot be swapped mid-attempt.
                    with guard:
                        pre_lease_blockers = session.pre_lease_blockers()
                        if pre_lease_blockers:
                            wait_for_work = True
                        else:
                            authorized_provider = getattr(
                                session,
                                "pre_lease_authorized_intents",
                                None,
                            )
                            authorized_intents = (
                                authorized_provider()
                                if callable(authorized_provider)
                                else None
                            )
                            dequeue_started_monotonic_ns = int(
                                monotonic_ns_now()
                            )
                            lease = spool.lease_next(
                                owner_id=service_generation,
                                now_epoch_ns=now_epoch,
                                now_monotonic_ns=now_monotonic_ns,
                                clock_domain_id=domain_id,
                                lease_seconds=lease_seconds,
                                authorized_intents=authorized_intents,
                            )
                            dequeue_completed_monotonic_ns = int(
                                monotonic_ns_now()
                            )
                            dequeue_sla_exceeded = (
                                dequeue_completed_monotonic_ns
                                - dequeue_started_monotonic_ns
                                > int(
                                    float(max_dequeue_seconds)
                                    * 1_000_000_000
                                )
                            )
                            if lease is None:
                                wait_for_work = True
                            else:
                                dequeued_monotonic_ns = int(
                                    monotonic_ns_now()
                                )
                                hard_deadline_ns = min(
                                    int(lease.intent.deadline_monotonic_ns),
                                    dequeued_monotonic_ns
                                    + int(
                                        float(dequeue_to_send_seconds)
                                        * 1_000_000_000
                                    ),
                                )
                                if dequeue_sla_exceeded:
                                    result = ExecutionResult.blocked(
                                        lease.intent.intent_id,
                                        "stage179_execution_deadline_exceeded:"
                                        "executor_dequeue_sla",
                                    )
                                elif dequeued_monotonic_ns >= hard_deadline_ns:
                                    result = _deadline_result(lease)
                                else:
                                    def mark_api_slot_durable(
                                        _batch_id: str,
                                        leased: Any = lease,
                                    ) -> bool:
                                        marked = spool.mark_sending(
                                            leased,
                                            now_epoch_ns=int(epoch_ns()),
                                            now_monotonic_ns=int(
                                                monotonic_ns_now()
                                            ),
                                            clock_domain_id=domain_id,
                                        )
                                        return (
                                            str(
                                                getattr(
                                                    marked,
                                                    "state",
                                                    "sending",
                                                )
                                            )
                                            == "sending"
                                        )

                                    result = session.execute_spool_lease(
                                        lease=lease,
                                        hard_deadline_monotonic=(
                                            hard_deadline_ns / 1e9
                                        ),
                                        api_slot_durable=mark_api_slot_durable,
                                    )
                                try:
                                    spool.mark_result(
                                        lease,
                                        result,
                                        now_epoch_ns=int(epoch_ns()),
                                        now_monotonic_ns=int(
                                            monotonic_ns_now()
                                        ),
                                        clock_domain_id=domain_id,
                                    )
                                except SpoolTransitionError:
                                    if not result.api_slot_batch_id:
                                        raise
                                    # The durable API slot is the safety
                                    # boundary.  A lost spool CAS must never
                                    # trigger another send; leave the lease for
                                    # bounded ledger recovery.
                                completed_lease = True

                    if wait_for_work:
                        if (
                            float(monotonic())
                            - last_readiness_publish_monotonic
                            >= readiness_heartbeat_seconds
                        ):
                            publish_readiness(
                                paths.readiness_path,
                                session.readiness_lease(
                                    now_epoch_ns=int(epoch_ns())
                                ),
                            )
                            last_readiness_publish_monotonic = float(monotonic())
                        _wait_for_work(
                            wake_socket,
                            poll_seconds=poll_seconds,
                            sleeper=sleeper,
                        )
                        continue
                    if completed_lease:
                        publish_readiness(
                            paths.readiness_path,
                            session.readiness_lease(
                                now_epoch_ns=int(epoch_ns())
                            ),
                        )
                        last_readiness_publish_monotonic = float(monotonic())
            finally:
                if session is not None:
                    try:
                        revoke_readiness(
                            paths.readiness_path,
                            service_generation=service_generation or "startup-failed",
                            reason="executor_stopped",
                            revoked_epoch_ns=int(epoch_ns()),
                        )
                    finally:
                        session.close()
    return 0


__all__ = [
    "DEFAULT_DEQUEUE_TO_SEND_SECONDS",
    "DEFAULT_LEASE_SECONDS",
    "DEFAULT_POLL_SECONDS",
    "ExecutionResult",
    "ExecutorAlreadyRunningError",
    "ExecutorServiceError",
    "ExecutorServicePaths",
    "SQLiteIntentSpool",
    "TdReadinessLease",
    "publish_readiness",
    "revoke_readiness",
    "serve_executor",
    "singleton_executor_lock",
]
