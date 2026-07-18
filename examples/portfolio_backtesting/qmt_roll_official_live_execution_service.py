from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
import fcntl
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
    expire_due_intents,
    lease_next,
    transition_intent,
    wakeup_socket_path,
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


class IntentSpool(Protocol):
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

    def reconnect(self) -> None: ...

    def execute_spool_lease(
        self,
        *,
        lease: Any,
        hard_deadline_monotonic: float,
    ) -> ExecutionResult: ...

    def close(self) -> None: ...


class SQLiteIntentSpool:
    """Small transition adapter over the Task7 SQLite spool contract."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

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
        expected = "sending"
        if result.disposition == "sent":
            target = "sent"
        elif result.disposition == "side_effect_unknown":
            target = "side_effect_unknown"
        else:
            target = "blocked"
        return transition_intent(
            self.connection,
            intent_id=lease.intent.intent_id,
            owner_id=lease.intent.lease_owner,
            lease_token=lease.lease_token,
            expected_state=expected,
            new_state=target,
            ledger_disposition=result.disposition,
            last_error=";".join(result.blockers),
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
                    spool.expire_due(
                        now_epoch_ns=now_epoch,
                        now_monotonic_ns=now_monotonic_ns,
                        clock_domain_id=domain_id,
                    )
                    dequeue_started_monotonic_ns = int(monotonic_ns_now())
                    lease = spool.lease_next(
                        owner_id=service_generation,
                        now_epoch_ns=now_epoch,
                        now_monotonic_ns=now_monotonic_ns,
                        clock_domain_id=domain_id,
                        lease_seconds=lease_seconds,
                    )
                    dequeue_completed_monotonic_ns = int(monotonic_ns_now())
                    dequeue_sla_exceeded = (
                        dequeue_completed_monotonic_ns
                        - dequeue_started_monotonic_ns
                        > int(float(max_dequeue_seconds) * 1_000_000_000)
                    )
                    if lease is None:
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

                    dequeued_monotonic_ns = int(monotonic_ns_now())
                    hard_deadline_ns = min(
                        int(lease.intent.deadline_monotonic_ns),
                        dequeued_monotonic_ns
                        + int(float(dequeue_to_send_seconds) * 1_000_000_000),
                    )
                    marked = spool.mark_sending(
                        lease,
                        now_epoch_ns=int(epoch_ns()),
                        now_monotonic_ns=int(monotonic_ns_now()),
                        clock_domain_id=domain_id,
                    )
                    marked_state = str(getattr(marked, "state", "sending"))
                    if marked_state != "sending":
                        # The durable CAS itself can expire an open or block a
                        # close if the deadline crossed after dequeue.
                        continue
                    if dequeue_sla_exceeded:
                        result = ExecutionResult.blocked(
                            lease.intent.intent_id,
                            "stage179_execution_deadline_exceeded:executor_dequeue_sla",
                        )
                    elif dequeued_monotonic_ns >= hard_deadline_ns:
                        result = _deadline_result(lease)
                    else:
                        result = session.execute_spool_lease(
                            lease=lease,
                            hard_deadline_monotonic=hard_deadline_ns / 1e9,
                        )
                    spool.mark_result(
                        lease,
                        result,
                        now_epoch_ns=int(epoch_ns()),
                        now_monotonic_ns=int(monotonic_ns_now()),
                        clock_domain_id=domain_id,
                    )
                    publish_readiness(
                        paths.readiness_path,
                        session.readiness_lease(now_epoch_ns=int(epoch_ns())),
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
