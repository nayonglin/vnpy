from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import plistlib
import stat
from typing import Any, Iterable


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_ALLOWED_ROOT = (
    Path("/Users/bytedance/Desktop/person/vnpy")
    / "examples/portfolio_backtesting/backtest_outputs/stage179_c9_15w"
)
DEFAULT_PLISTS = (
    PROJECT_DIR
    / "launchd/local.qmt-roll.official-live.15w.c9-readonly-day-session.plist",
    PROJECT_DIR
    / "launchd/local.qmt-roll.official-live.15w.c9-readonly-night-session.plist",
    PROJECT_DIR
    / "launchd/local.qmt-roll.official-live.15w.c9-readonly-postclose-precompute.plist",
)
_DIRECTORY_ENV_KEYS = {
    "OFFICIAL_LIVE_OUTPUT_DIR",
    "OFFICIAL_LIVE_SIGNAL_INPUT_DIR",
}
_RUNTIME_ROOT_FLAG = "--stage179-runtime-root"
_PLAN_SEAL = object()


@dataclass(frozen=True, slots=True, init=False)
class DirectoryProvisionPlan:
    allowed_root: Path
    plist_paths: tuple[Path, ...]
    directories: tuple[Path, ...]
    _seal: object


def _bounded_directory(value: Any, *, allowed_root: Path) -> Path:
    candidate = Path(str(value)).expanduser().resolve(strict=False)
    if not candidate.is_relative_to(allowed_root):
        raise ValueError(
            "c9_launchd_directory_outside_allowed_root:"
            f"{candidate}"
        )
    return candidate


def _collect_required_directories(
    plist_paths: Iterable[Path | str],
    *,
    allowed_root: Path | str,
) -> tuple[Path, ...]:
    root = Path(allowed_root).expanduser().resolve(strict=False)
    required: set[Path] = {root}
    for raw_path in plist_paths:
        plist_path = Path(raw_path).expanduser().resolve(strict=True)
        try:
            payload = plistlib.loads(plist_path.read_bytes())
        except Exception as exc:
            raise ValueError(
                f"c9_launchd_plist_unreadable:{plist_path}"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError(f"c9_launchd_plist_invalid:{plist_path}")
        for key in ("StandardOutPath", "StandardErrorPath"):
            value = payload.get(key)
            if value:
                required.add(
                    _bounded_directory(
                        Path(str(value)).parent,
                        allowed_root=root,
                    )
                )
        environment = payload.get("EnvironmentVariables", {})
        if isinstance(environment, dict):
            for key in _DIRECTORY_ENV_KEYS:
                value = environment.get(key)
                if value:
                    required.add(
                        _bounded_directory(value, allowed_root=root)
                    )
        arguments = payload.get("ProgramArguments", [])
        if isinstance(arguments, list) and _RUNTIME_ROOT_FLAG in arguments:
            index = arguments.index(_RUNTIME_ROOT_FLAG)
            if index + 1 >= len(arguments):
                raise ValueError(
                    f"c9_launchd_runtime_root_missing:{plist_path}"
                )
            required.add(
                _bounded_directory(
                    arguments[index + 1],
                    allowed_root=root,
                )
            )
    return tuple(sorted(required, key=str))


def build_directory_provision_plan() -> DirectoryProvisionPlan:
    allowed_root = DEFAULT_ALLOWED_ROOT.expanduser().resolve(strict=False)
    plist_paths = tuple(
        path.expanduser().resolve(strict=True) for path in DEFAULT_PLISTS
    )
    directories = _collect_required_directories(
        plist_paths,
        allowed_root=allowed_root,
    )
    plan = object.__new__(DirectoryProvisionPlan)
    object.__setattr__(plan, "allowed_root", allowed_root)
    object.__setattr__(plan, "plist_paths", plist_paths)
    object.__setattr__(plan, "directories", directories)
    object.__setattr__(plan, "_seal", _PLAN_SEAL)
    return plan


def _validate_plan(plan: DirectoryProvisionPlan) -> None:
    canonical = build_directory_provision_plan()
    if (
        not isinstance(plan, DirectoryProvisionPlan)
        or getattr(plan, "_seal", None) is not _PLAN_SEAL
        or plan != canonical
    ):
        raise ValueError("c9_launchd_directory_plan_not_canonical")


def _permission_mismatches(paths: Iterable[Path]) -> list[dict[str, str]]:
    return [
        {
            "path": str(path),
            "observed_mode": oct(stat.S_IMODE(path.stat().st_mode)),
            "required_mode": "0o750",
        }
        for path in paths
        if path.is_dir() and stat.S_IMODE(path.stat().st_mode) != 0o750
    ]


def provision_directories(
    plan: DirectoryProvisionPlan,
    *,
    create: bool,
) -> dict[str, Any]:
    _validate_plan(plan)
    required = plan.directories
    missing_before = [str(path) for path in required if not path.is_dir()]
    for path in required:
        if path.exists() and not path.is_dir():
            raise ValueError(f"c9_launchd_directory_not_directory:{path}")
    permission_mismatches_before = _permission_mismatches(required)
    created: list[str] = []
    if create:
        for path in required:
            if not path.exists():
                path.mkdir(parents=True, mode=0o750, exist_ok=True)
                created.append(str(path))
            path.chmod(0o750)
    missing_after = [str(path) for path in required if not path.is_dir()]
    permission_mismatches = _permission_mismatches(required)
    if missing_after:
        status = "directories_missing"
    elif permission_mismatches:
        status = "directories_permission_mismatch"
    else:
        status = "directories_ready"
    return {
        "status": status,
        "mode": "create" if create else "check",
        "required_count": len(required),
        "missing_before": missing_before,
        "missing_after": missing_after,
        "created": created,
        "created_count": len(created),
        "permission_mismatches_before": permission_mismatches_before,
        "permission_mismatches": permission_mismatches,
        "launchctl_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Check or create only directories used by dormant C9/15w "
            "production-readonly LaunchAgents. This never calls launchctl."
        )
    )
    parser.add_argument("--mode", choices=("check", "create"), default="check")
    args = parser.parse_args()
    plan = build_directory_provision_plan()
    summary = provision_directories(plan, create=args.mode == "create")
    summary.update(
        {
            "allowed_root": str(plan.allowed_root),
            "plists": [str(path) for path in plan.plist_paths],
            "required_directories": [str(path) for path in plan.directories],
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
