from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable


class RuntimeProfileError(ValueError):
    pass


class ExecutionRuntimeProfile(str, Enum):
    OFFLINE = "offline"
    PRODUCTION_READONLY = "production-readonly"
    SIMNOW = "simnow"
    BROKER_TEST = "broker-test"
    PRODUCTION_LIVE = "production-live"


class OrderScope(str, Enum):
    NONE = "none"
    READONLY = "readonly"
    TEST = "test"
    LIVE = "live"


_PROFILE_SCOPE = {
    ExecutionRuntimeProfile.OFFLINE: OrderScope.NONE,
    ExecutionRuntimeProfile.PRODUCTION_READONLY: OrderScope.READONLY,
    ExecutionRuntimeProfile.SIMNOW: OrderScope.TEST,
    ExecutionRuntimeProfile.BROKER_TEST: OrderScope.TEST,
    ExecutionRuntimeProfile.PRODUCTION_LIVE: OrderScope.LIVE,
}

_PROFILE_ENV = {
    ExecutionRuntimeProfile.OFFLINE: None,
    ExecutionRuntimeProfile.PRODUCTION_READONLY: "ctp_live.local.env",
    ExecutionRuntimeProfile.SIMNOW: "ctp_simnow.local.env",
    ExecutionRuntimeProfile.BROKER_TEST: "ctp_broker_test.local.env",
    ExecutionRuntimeProfile.PRODUCTION_LIVE: "ctp_live.local.env",
}


@dataclass(frozen=True, slots=True)
class ResolvedRuntimeProfile:
    profile: ExecutionRuntimeProfile
    order_scope: OrderScope
    repo_root: Path
    env_file: Path | None
    framework_path: tuple[Path, ...]
    output_root: Path
    state_root: Path
    spool_path: Path
    ledger_path: Path
    readiness_path: Path
    activation_receipt_path: Path

    @property
    def permits_order_api(self) -> bool:
        return self.order_scope in {OrderScope.TEST, OrderScope.LIVE}


def _coerce_profile(value: ExecutionRuntimeProfile | str) -> ExecutionRuntimeProfile:
    try:
        return (
            value
            if isinstance(value, ExecutionRuntimeProfile)
            else ExecutionRuntimeProfile(str(value))
        )
    except ValueError as exc:
        raise RuntimeProfileError(f"runtime_profile_invalid:{value}") from exc


def _coerce_scope(value: OrderScope | str) -> OrderScope:
    try:
        return value if isinstance(value, OrderScope) else OrderScope(str(value))
    except ValueError as exc:
        raise RuntimeProfileError(f"order_scope_invalid:{value}") from exc


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _resolved_paths(values: Iterable[Path]) -> tuple[Path, ...]:
    return tuple(Path(value).expanduser().resolve(strict=False) for value in values)


def resolve_runtime_profile(
    *,
    profile: ExecutionRuntimeProfile | str,
    order_scope: OrderScope | str,
    output_root: Path | str | None = None,
    protected_production_roots: Iterable[Path | str] = (),
    repo_root: Path | str | None = None,
) -> ResolvedRuntimeProfile:
    resolved_profile = _coerce_profile(profile)
    resolved_scope = _coerce_scope(order_scope)
    expected_scope = _PROFILE_SCOPE[resolved_profile]
    if resolved_scope is not expected_scope:
        raise RuntimeProfileError(
            "runtime_profile_order_scope_mismatch:"
            f"{resolved_profile.value}:{resolved_scope.value}!={expected_scope.value}"
        )

    if repo_root is None:
        repo = Path(__file__).resolve().parents[2]
    else:
        repo = Path(repo_root).expanduser().resolve(strict=False)
    project_dir = repo / "examples" / "portfolio_backtesting"
    if output_root is None:
        output = (
            project_dir
            / "backtest_outputs"
            / "stage179_runtime"
            / resolved_profile.value
        ).resolve(strict=False)
    else:
        output = Path(output_root).expanduser().resolve(strict=False)
    state = (output / "state").resolve(strict=False)
    spool = (state / "intent_spool.sqlite3").resolve(strict=False)
    ledger = (state / "execution_ledger.ndjson").resolve(strict=False)
    readiness = (state / "executor_readiness.json").resolve(strict=False)
    receipt = (state / "activation_receipt.json").resolve(strict=False)

    protected = _resolved_paths(Path(item) for item in protected_production_roots)
    for candidate in (output, state, spool, ledger, readiness, receipt):
        for production_root in protected:
            if _overlaps(candidate, production_root):
                raise RuntimeProfileError(
                    "runtime_path_overlaps_protected_production_root:"
                    f"{candidate}:{production_root}"
                )

    env_name = _PROFILE_ENV[resolved_profile]
    env_file: Path | None = None
    if env_name is not None:
        declared_env_file = project_dir / env_name
        if declared_env_file.is_symlink():
            raise RuntimeProfileError(
                f"runtime_env_symlink_forbidden:{declared_env_file}"
            )
        env_file = declared_env_file.resolve(strict=False)
    py311_lib = (repo / ".py311" / "lib").resolve(strict=False)
    formal_ctp = (
        repo
        / ".py311"
        / "lib"
        / "python3.11"
        / "site-packages"
        / "vnpy_ctp"
        / "api"
        / "libs"
    ).resolve(strict=False)
    if resolved_profile in {
        ExecutionRuntimeProfile.PRODUCTION_READONLY,
        ExecutionRuntimeProfile.PRODUCTION_LIVE,
    }:
        framework = (formal_ctp, py311_lib)
    elif resolved_profile is ExecutionRuntimeProfile.OFFLINE:
        framework = ()
    else:
        framework = (py311_lib,)

    return ResolvedRuntimeProfile(
        profile=resolved_profile,
        order_scope=resolved_scope,
        repo_root=repo,
        env_file=env_file,
        framework_path=framework,
        output_root=output,
        state_root=state,
        spool_path=spool,
        ledger_path=ledger,
        readiness_path=readiness,
        activation_receipt_path=receipt,
    )


def validate_resolved_runtime_profile(
    resolved: ResolvedRuntimeProfile,
    *,
    repo_root: Path | str,
) -> ResolvedRuntimeProfile:
    """Reject hand-built or mutated profile objects at a trust boundary."""

    if type(resolved) is not ResolvedRuntimeProfile:
        raise RuntimeProfileError("resolved_runtime_profile_type_invalid")
    if not isinstance(resolved.profile, ExecutionRuntimeProfile):
        raise RuntimeProfileError("resolved_runtime_profile_enum_invalid")
    if not isinstance(resolved.order_scope, OrderScope):
        raise RuntimeProfileError("resolved_runtime_order_scope_enum_invalid")
    canonical = resolve_runtime_profile(
        profile=resolved.profile,
        order_scope=resolved.order_scope,
        output_root=resolved.output_root,
        repo_root=repo_root,
    )
    if resolved != canonical:
        raise RuntimeProfileError("resolved_runtime_profile_fields_mismatch")
    return canonical


__all__ = [
    "ExecutionRuntimeProfile",
    "OrderScope",
    "ResolvedRuntimeProfile",
    "RuntimeProfileError",
    "resolve_runtime_profile",
    "validate_resolved_runtime_profile",
]
