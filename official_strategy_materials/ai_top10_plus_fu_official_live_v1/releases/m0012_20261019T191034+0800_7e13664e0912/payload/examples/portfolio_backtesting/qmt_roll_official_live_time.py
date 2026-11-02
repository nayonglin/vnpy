from __future__ import annotations

import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import platform
from typing import Protocol
import time


_CLOCK_DOMAIN_MAX_BYTES = 256
_SYSTEM_CLOCK_DOMAIN_ID: str | None = None


def _validated_clock_domain(value: object) -> str:
    if not isinstance(value, str):
        raise RuntimeError("clock_domain_id_must_be_text")
    normalized = value.strip()
    if not normalized:
        raise RuntimeError("clock_domain_id_must_not_be_empty")
    if any(ord(character) < 32 for character in normalized):
        raise RuntimeError("clock_domain_id_contains_control_character")
    try:
        encoded = normalized.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise RuntimeError("clock_domain_id_must_be_utf8") from exc
    if len(encoded) > _CLOCK_DOMAIN_MAX_BYTES:
        raise RuntimeError(
            "clock_domain_id_too_long:"
            f"{len(encoded)}>{_CLOCK_DOMAIN_MAX_BYTES}"
        )
    return normalized


def _linux_boot_id() -> str:
    try:
        return (Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8")).strip()
    except (OSError, UnicodeError):
        return ""


def _darwin_boot_session_uuid() -> str:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        sysctlbyname = libc.sysctlbyname
        sysctlbyname.argtypes = (
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p,
            ctypes.c_size_t,
        )
        sysctlbyname.restype = ctypes.c_int
        size = ctypes.c_size_t(0)
        name = b"kern.bootsessionuuid"
        if sysctlbyname(name, None, ctypes.byref(size), None, 0) != 0:
            return ""
        if size.value <= 1 or size.value > 1024:
            return ""
        buffer = ctypes.create_string_buffer(size.value)
        if sysctlbyname(name, buffer, ctypes.byref(size), None, 0) != 0:
            return ""
        return buffer.value.decode("utf-8").strip()
    except (AttributeError, OSError, UnicodeError, ValueError):
        return ""


def system_clock_domain_id() -> str:
    """Return one boot-stable identity shared by local exec'ed processes."""

    global _SYSTEM_CLOCK_DOMAIN_ID
    if _SYSTEM_CLOCK_DOMAIN_ID is not None:
        return _SYSTEM_CLOCK_DOMAIN_ID
    system = platform.system().lower()
    boot_id = _linux_boot_id() if system == "linux" else ""
    if system == "darwin":
        boot_id = _darwin_boot_session_uuid()
    if not boot_id:
        raise RuntimeError(
            "system_clock_domain_unavailable:"
            f"platform={system or 'unknown'}"
        )
    domain = f"{system}-boot:{_validated_clock_domain(boot_id)}"
    _SYSTEM_CLOCK_DOMAIN_ID = _validated_clock_domain(domain)
    return _SYSTEM_CLOCK_DOMAIN_ID


class Clock(Protocol):
    """Injectable wall/monotonic clock used by the live execution pipeline."""

    def epoch_ns(self) -> int:
        """Return Unix epoch time in nanoseconds."""

    def monotonic_ns(self) -> int:
        """Return process-local monotonic time in nanoseconds."""

    def sleep(self, seconds: float) -> None:
        """Sleep for the requested duration."""

    def clock_domain_id(self) -> str:
        """Return a boot-stable domain shared by comparable monotonic clocks."""


@dataclass(frozen=True, slots=True)
class SystemClock:
    def epoch_ns(self) -> int:
        return time.time_ns()

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def clock_domain_id(self) -> str:
        return system_clock_domain_id()


def utc_iso_from_epoch_ns(epoch_ns: int) -> str:
    """Format one epoch sample as an aware UTC timestamp without resampling."""

    seconds, nanoseconds = divmod(int(epoch_ns), 1_000_000_000)
    instant = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return f"{instant:%Y-%m-%dT%H:%M:%S}.{nanoseconds:09d}Z"
