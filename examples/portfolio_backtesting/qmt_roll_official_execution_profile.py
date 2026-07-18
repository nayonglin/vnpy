from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from typing import Any


OUTPUT_DIR = Path(
    os.environ.get(
        "OFFICIAL_LIVE_OUTPUT_DIR",
        str(Path(__file__).resolve().parent / "backtest_outputs"),
    )
).expanduser().resolve(strict=False)
SIGNAL_INPUT_DIR = Path(
    os.environ.get("OFFICIAL_LIVE_SIGNAL_INPUT_DIR", str(OUTPUT_DIR))
).expanduser().resolve(strict=False)


class ExecutionStrategyMode(str, Enum):
    """Strategy semantics accepted by the shared execution reliability layer."""

    STAGE372_20W = "stage372-20w"
    C9_15W_HISTORICAL = "c9-15w-historical"


@dataclass(frozen=True)
class OfficialExecutionProfile:
    profile_key: str
    official_version: str
    alias: str
    source_stage: str
    capital: float
    capital_label: str
    summary_path: Path
    signal_plan_path: Path
    current_positions_path: Path
    pending_orders_path: Path
    pending_orders_audit_path: Path
    allowed_intent_sources: tuple[str, ...]
    intraday_stop_retry_enabled: bool

    def __post_init__(self) -> None:
        if not self.profile_key or not self.official_version or not self.alias:
            raise ValueError("execution_profile_identity_missing")
        if not self.source_stage or self.capital <= 0 or not self.capital_label:
            raise ValueError("execution_profile_identity_invalid")
        if not self.allowed_intent_sources:
            raise ValueError("execution_profile_intent_sources_empty")
        if len(set(self.allowed_intent_sources)) != len(
            self.allowed_intent_sources
        ):
            raise ValueError("execution_profile_intent_sources_duplicate")


def _artifact_paths(
    prefix: str,
    model_tag: str,
) -> tuple[Path, Path, Path, Path, Path]:
    return (
        SIGNAL_INPUT_DIR / f"{prefix}_decision_{model_tag}.json",
        SIGNAL_INPUT_DIR / f"{prefix}_signal_plan_{model_tag}.csv",
        SIGNAL_INPUT_DIR / f"{prefix}_current_positions_{model_tag}.csv",
        SIGNAL_INPUT_DIR / f"{prefix}_pending_orders_{model_tag}.csv",
        SIGNAL_INPUT_DIR / f"{prefix}_pending_orders_audit_{model_tag}.json",
    )


(
    _STAGE372_SUMMARY_PATH,
    _STAGE372_SIGNAL_PLAN_PATH,
    _STAGE372_CURRENT_POSITIONS_PATH,
    _STAGE372_PENDING_ORDERS_PATH,
    _STAGE372_PENDING_ORDERS_AUDIT_PATH,
) = _artifact_paths(
    "qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow",
    "stage659_stage372_2026_ytd_latest_ai_shadow_v1",
)

STAGE372_20W_PROFILE = OfficialExecutionProfile(
    profile_key=ExecutionStrategyMode.STAGE372_20W.value,
    official_version="official_live_stage372_20w_recovery_sleeve",
    alias="Stage372-20w",
    source_stage="Stage372",
    capital=200_000.0,
    capital_label="20w",
    summary_path=_STAGE372_SUMMARY_PATH,
    signal_plan_path=_STAGE372_SIGNAL_PLAN_PATH,
    current_positions_path=_STAGE372_CURRENT_POSITIONS_PATH,
    pending_orders_path=_STAGE372_PENDING_ORDERS_PATH,
    pending_orders_audit_path=_STAGE372_PENDING_ORDERS_AUDIT_PATH,
    allowed_intent_sources=("stage260_stage372_daily",),
    intraday_stop_retry_enabled=False,
)

(
    _C9_SUMMARY_PATH,
    _C9_SIGNAL_PLAN_PATH,
    _C9_CURRENT_POSITIONS_PATH,
    _C9_PENDING_ORDERS_PATH,
    _C9_PENDING_ORDERS_AUDIT_PATH,
) = _artifact_paths(
    "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow",
    "stage901_stage847_c9_2026_ytd_live_shadow_v1",
)

C9_15W_HISTORICAL_PROFILE = OfficialExecutionProfile(
    profile_key=ExecutionStrategyMode.C9_15W_HISTORICAL.value,
    official_version="official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
    alias="Stage847-C9-15w",
    source_stage="Stage847/Stage928",
    capital=150_000.0,
    capital_label="15w",
    summary_path=_C9_SUMMARY_PATH,
    signal_plan_path=_C9_SIGNAL_PLAN_PATH,
    current_positions_path=_C9_CURRENT_POSITIONS_PATH,
    pending_orders_path=_C9_PENDING_ORDERS_PATH,
    pending_orders_audit_path=_C9_PENDING_ORDERS_AUDIT_PATH,
    allowed_intent_sources=(
        "stage901_pending_order",
        "stage904_c9_intraday_close",
        "stage904_c9_intraday_retry_open",
    ),
    intraday_stop_retry_enabled=True,
)

_PROFILES = {
    profile.profile_key: profile
    for profile in (STAGE372_20W_PROFILE, C9_15W_HISTORICAL_PROFILE)
}


def resolve_execution_profile(
    value: str | ExecutionStrategyMode = ExecutionStrategyMode.STAGE372_20W,
) -> OfficialExecutionProfile:
    key = value.value if isinstance(value, ExecutionStrategyMode) else str(value)
    try:
        return _PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"execution_profile_unknown:{key}") from exc


def assert_profile_identity(
    profile: OfficialExecutionProfile,
    *,
    official_version: Any,
    capital: Any,
    capital_label: Any,
) -> None:
    if str(official_version).strip() != profile.official_version:
        raise ValueError(
            "execution_profile_version_mismatch:"
            f"{official_version}!={profile.official_version}"
        )
    if isinstance(capital, bool) or type(capital) not in (int, float):
        raise ValueError("execution_profile_capital_invalid")
    if float(capital) != profile.capital:
        raise ValueError(
            "execution_profile_capital_mismatch:"
            f"{capital}!={profile.capital}"
        )
    if str(capital_label).strip() != profile.capital_label:
        raise ValueError(
            "execution_profile_capital_label_mismatch:"
            f"{capital_label}!={profile.capital_label}"
        )


def assert_intent_source_allowed(
    profile: OfficialExecutionProfile,
    source: Any,
) -> None:
    normalized = str(source).strip()
    if normalized not in profile.allowed_intent_sources:
        raise ValueError(
            "intent_source_not_allowed_for_execution_profile:"
            f"{normalized}:{profile.profile_key}"
        )


__all__ = [
    "C9_15W_HISTORICAL_PROFILE",
    "ExecutionStrategyMode",
    "OfficialExecutionProfile",
    "STAGE372_20W_PROFILE",
    "assert_intent_source_allowed",
    "assert_profile_identity",
    "resolve_execution_profile",
]
