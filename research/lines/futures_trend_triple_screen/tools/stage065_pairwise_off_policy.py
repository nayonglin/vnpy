"""Shared pairwise-free research policy; importing it requires only stdlib.

This module does not run accounts, qualify data, load models or replace monthly
AI eligibility. Call after the frozen runtime has been configured.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

Arm = Literal["A_OFF", "B_OFF"]
OFF_SETTINGS: Mapping[str, bool | int | float] = MappingProxyType({
    "enable_selection_pairwise_v2": False,
    "enable_selection_pairwise_v2_catastrophic_veto": False,
    "enable_selection_pairwise_v2_catastrophic_hard_filter": False,
    "enable_selection_pairwise_v2_volume_tilt": False,
    "selection_pairwise_volume_tilt_strength": 0.0,
    "selection_pairwise_volume_tilt_long_strength": 0.0,
    "selection_pairwise_volume_tilt_short_strength": 0.0,
    "incremental_margin_budget_gate_protected_selection_rank": 0,
})


def _arm(arm: Arm) -> None:
    if arm not in ("A_OFF", "B_OFF"):
        raise ValueError("pairwise_off_unregistered_arm")


def _policy_sha256() -> str:
    return hashlib.sha256(json.dumps(dict(OFF_SETTINGS), sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _effective_reference(reference: Mapping[str, Any]) -> tuple[dict, dict]:
    # Only omitted OFF keys are filled, from the actual native MRO declarations.
    # Never allow a missing field to silently compare equal to None.
    from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import (
        QmtRollPortfolioStrategyStage847C9StopRetry as native,
    )
    result = deepcopy(dict(reference))
    defaults = {}
    for key in OFF_SETTINGS:
        if key not in result:
            if not hasattr(native, key):
                raise ValueError("settings_native_default_missing:" + key)
            defaults[key] = result[key] = getattr(native, key)
    return result, defaults


def make_off_profile(formal_profile: Mapping[str, Any], arm: Arm) -> dict:
    """Project AFTER official override assembly, without changing economics."""
    _arm(arm)
    spec = formal_profile["spec"]
    result = dict(formal_profile)
    result["spec"] = replace(spec, overrides={**spec.overrides, **OFF_SETTINGS})
    result["research_arm"] = arm
    return result


def expected_off_settings(reference: Mapping[str, Any]) -> dict:
    reference, _ = _effective_reference(reference)
    return {**reference, **OFF_SETTINGS}


def check_settings_delta(reference: Mapping, requested: Mapping, actual: Mapping,
                         *, shared: Path, reference_shared: Path) -> dict:
    """Require the entire requested and effective snapshot, with eight allowed keys.

    Shared empty-input roots use the unchanged Stage022 normalizer. Unknown
    keys, removed fields and other paths remain material differences.
    """
    from stage022_run_c0_qualified_wait import normalize_reference
    effective_reference, defaults = _effective_reference(reference)
    expected = {**effective_reference, **OFF_SETTINGS}
    normalize = lambda value: normalize_reference(dict(value), shared, reference_shared)
    normalized_expected = normalize(expected)
    for label, observed in (("requested", requested), ("actual", actual)):
        normalized = normalize(observed)
        if normalized != normalized_expected:
            differing = sorted(key for key in set(normalized) | set(normalized_expected)
                if key not in normalized or key not in normalized_expected
                or normalized[key] != normalized_expected[key])
            raise ValueError("settings_" + label + "_drift:" + ",".join(differing))
        for key, value in OFF_SETTINGS.items():
            if isinstance(value, bool) and observed[key] is not value:
                raise ValueError("settings_" + label + "_policy_type:" + key)
    changes = {key: {"reference": effective_reference[key], "off": expected[key]}
        for key in OFF_SETTINGS if effective_reference[key] != expected[key]}
    return dict(actual_settings_match_off_expected=True, allowed_keys=sorted(OFF_SETTINGS),
        changed_keys=sorted(changes), changes=changes, declared_defaults_used=defaults,
        non_off_differences=[], requested_key_count=len(requested), actual_key_count=len(actual),
        eight_key_policy_sha256=_policy_sha256())


def disabled_pairwise_preflight() -> dict:
    """A disabled branch, not a fabricated successful model smoke test."""
    return dict(schema="stage065_disabled_pairwise_policy_v1",
        status="disabled_by_shared_pairwise_free_policy", model_loads=0,
        model_predictions=0, model_fits=0, eight_key_policy_sha256=_policy_sha256(),
        fallback="metadata_sorted_product_insertion_order", rank_protection=False)


def check_effective_off_policy(strategy: object) -> dict:
    effective = {}
    for key, expected in OFF_SETTINGS.items():
        if not hasattr(strategy, key):
            raise ValueError("effective_off_attribute_missing:" + key)
        value = getattr(strategy, key)
        if value != expected or (isinstance(expected, bool) and value is not expected):
            raise ValueError("effective_off_attribute_drift:" + key)
        effective[key] = value
    for key in ("selection_pairwise_runtime", "ai_path_damage_runtime"):
        if not hasattr(strategy, key) or getattr(strategy, key) is not None:
            raise ValueError("effective_off_runtime_present:" + key)
        effective[key] = None
    if getattr(strategy, "enable_ai_path_damage_risk_discount", None) is not False:
        raise ValueError("effective_off_other_model_enabled")
    if getattr(strategy, "stage827_require_complete_minutes", None) is not True:
        raise ValueError("effective_off_strict_minute_gate_changed")
    effective.update(enable_ai_path_damage_risk_discount=False,
        stage827_require_complete_minutes=True,
        enable_ai_product_pool_filter=getattr(strategy, "enable_ai_product_pool_filter"),
        ai_product_pool_eligibility_path=getattr(strategy, "ai_product_pool_eligibility_path"))
    return dict(status="passed_effective_pairwise_off", effective=effective,
        eight_key_policy_sha256=_policy_sha256())


def select_account_classes(arm: Arm, native_strategy: type, native_engine: type,
                           *, weekly=None, fi=None, next_days=None, qualify=None) -> tuple[type, type]:
    _arm(arm)
    if arm == "A_OFF":
        return native_strategy, native_engine
    if weekly is None or fi is None or next_days is None or not callable(qualify):
        raise ValueError("pairwise_off_b_dependencies_missing")
    from stage035_b_ts_strategy import build_b_strategy
    from stage028_ordered_engine import build_ordered_engine
    return (build_b_strategy(native_strategy, weekly, fi, next_days),
        build_ordered_engine(native_engine, qualify))
