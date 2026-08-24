from __future__ import annotations

from contextlib import contextmanager
import errno
import fcntl
import os
from pathlib import Path
from typing import Iterator, Literal


SUBMIT_AUTHORIZATION_LOCK_FILENAME = "stage179_submit_authorization.lock"
AuthorizationLockMode = Literal["shared", "exclusive"]


class SubmitAuthorizationLockError(RuntimeError):
    pass


class SubmitAuthorizationLockBusyError(SubmitAuthorizationLockError):
    pass


def submit_authorization_lock_path(output_root: str | Path) -> Path:
    return (
        Path(output_root).expanduser().resolve(strict=False)
        / SUBMIT_AUTHORIZATION_LOCK_FILENAME
    )


@contextmanager
def submit_authorization_lock(
    path: str | Path,
    *,
    mode: AuthorizationLockMode,
    blocking: bool = True,
) -> Iterator[None]:
    """Hold one process-wide authorization publication/execution guard.

    Publishers and revokers use ``exclusive``.  The executor uses ``shared``
    from authorization admission through the durable terminal result.  The
    caller owns the guarded operation; this module deliberately does not wrap
    authorization file reads or writes implicitly, which avoids nested-flock
    deadlocks and makes the safety boundary auditable at each call site.
    """

    if mode not in {"shared", "exclusive"}:
        raise ValueError("stage179_submit_authorization_lock_mode_invalid")
    lock_path = Path(path).expanduser().resolve(strict=False)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    descriptor = os.open(lock_path, flags, 0o600)
    operation = fcntl.LOCK_SH if mode == "shared" else fcntl.LOCK_EX
    if not blocking:
        operation |= fcntl.LOCK_NB
    locked = False
    try:
        try:
            fcntl.flock(descriptor, operation)
            locked = True
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise SubmitAuthorizationLockBusyError(
                    "stage179_submit_authorization_lock_busy"
                ) from exc
            raise SubmitAuthorizationLockError(
                "stage179_submit_authorization_lock_failed"
            ) from exc
        yield
    finally:
        try:
            if locked:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


@contextmanager
def shared_submit_authorization_lock(
    path: str | Path,
    *,
    blocking: bool = True,
) -> Iterator[None]:
    with submit_authorization_lock(path, mode="shared", blocking=blocking):
        yield


@contextmanager
def exclusive_submit_authorization_lock(
    path: str | Path,
    *,
    blocking: bool = True,
) -> Iterator[None]:
    with submit_authorization_lock(path, mode="exclusive", blocking=blocking):
        yield


__all__ = [
    "SUBMIT_AUTHORIZATION_LOCK_FILENAME",
    "SubmitAuthorizationLockBusyError",
    "SubmitAuthorizationLockError",
    "exclusive_submit_authorization_lock",
    "shared_submit_authorization_lock",
    "submit_authorization_lock",
    "submit_authorization_lock_path",
]
