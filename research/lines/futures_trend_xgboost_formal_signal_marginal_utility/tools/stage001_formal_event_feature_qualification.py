from __future__ import annotations

import argparse
import builtins
import errno
import fcntl
import gzip
import hashlib
import importlib
import importlib.util
import io
import json
import math
import os
import re
import shutil
import site
import socket
import stat
import subprocess
import sys
import threading
import traceback
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
import pandas as pd


LINE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
PORTFOLIO_DIR = PRODUCTION_ROOT / "examples/portfolio_backtesting"
SOURCE_DATABASE = PRODUCTION_ROOT / ".vntrader/database.db"
FORMAL_CURRENT = PRODUCTION_ROOT / "official_strategy_materials/CURRENT.json"
WORKSPACE_BACKTEST_OUTPUTS = WORKSPACE_ROOT / "examples/portfolio_backtesting/backtest_outputs"
FULL_MINUTE_BARS = (
    WORKSPACE_BACKTEST_OUTPUTS
    / "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_"
    "stage861_stage860_full_visual_atlas_v1.csv"
)
MAIN_CONTRACT_MAPPING = (
    WORKSPACE_BACKTEST_OUTPUTS
    / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
)
CONTRACT_METADATA = (
    WORKSPACE_BACKTEST_OUTPUTS / "tqsdk_all_futures_contract_metadata.csv"
)
PRODUCT_UNIVERSE = (
    WORKSPACE_BACKTEST_OUTPUTS
    / "qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_"
    "static18_plus_fu_universe.csv"
)
PORTFOLIO_PACKAGE_ROOT = (
    Path(sys.prefix).resolve()
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages/vnpy_portfoliostrategy"
)
SANDBOX_EXECUTABLE = Path("/usr/bin/sandbox-exec")
SANDBOX_POLICY_MODE = (
    "deny_default_read_all_write_worker_only_no_network_no_fork_v2"
)
EXPECTED_INPUT_FILE_COUNT = 1410
EXPECTED_INPUT_LOGICAL_KEY_SHA256 = (
    "a972f46932585adf1ad5bfc4f0c3d76d5b654cd587204b8c4bd0512b791aacd2"
)
WORKER_MODULE_FILE_KEYS = {
    "stage901": (
        "production_portfolio/"
        "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py"
    ),
    "live_config": "production_portfolio/qmt_roll_official_live_config.py",
    "vnpy_portfoliostrategy": "vnpy_portfoliostrategy/__init__.py",
    "feature_tool": "stage001_feature_tool",
}

STAGE = "stage001_formal_event_feature_qualification"
LINE_ID = "futures_trend_xgboost_formal_signal_marginal_utility"
AUTHORIZATION_SCOPE = "one_new_stage001_formal_event_feature_qualification_run_only"
REQUIRED_REVIEW_DECISION = "ALLOW_STAGE001_UNIQUE_RUN"
EXPECTED_PRODUCTION_HEAD = "d492ee072aa5a9d71477235d79f17d2a5db59db3"
EXPECTED_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
EXPECTED_FORMAL_STRATEGY = "ai_top10_plus_fu_official_live_v1"
EXPECTED_OFFICIAL_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
EXPECTED_FORMAL_MANIFEST_SHA256 = (
    "4d92133bd67821a421bf6017c477015e79a3a8e36889ae4eb527bb11a31956a5"
)
EXPECTED_CAPITAL = 150_000.0
START = pd.Timestamp("2020-01-02")
END = pd.Timestamp("2026-08-28")
FORMAL_RELEASE = (
    PRODUCTION_ROOT
    / "official_strategy_materials"
    / EXPECTED_FORMAL_STRATEGY
    / "releases"
    / EXPECTED_RELEASE_ID
)
FORMAL_ELIGIBILITY = FORMAL_RELEASE / "payload/ai/stage182/combined_eligibility.csv"

FEATURE_TOOL = LINE_ROOT / "tools/formal_signal_event_features.py"
WORKER_BOOTSTRAP = LINE_ROOT / "tools/stage001_worker_bootstrap.py"
PREREGISTRATION = (
    LINE_ROOT
    / "stages/20260905_0713_stage000_formal_signal_marginal_utility_preregistration.md"
)
PRE_AI_BOUNDARY_REMEDIATION = (
    LINE_ROOT
    / "stages/20260905_0751_stage000a_pre_ai_boundary_contract_remediation.md"
)
PRERUN_BLOCKER_REMEDIATION = (
    LINE_ROOT / "stages/20260905_0836_stage000b_prerun_blocker_remediation.md"
)
SECOND_PRERUN_BLOCKER_REMEDIATION = (
    LINE_ROOT
    / "stages/20260905_0910_stage000c_second_prerun_blocker_remediation.md"
)
THIRD_PRERUN_BLOCKER_REMEDIATION = (
    LINE_ROOT
    / "stages/20260905_0954_stage000d_third_prerun_blocker_remediation.md"
)
FOURTH_PRERUN_BLOCKER_REMEDIATION = (
    LINE_ROOT
    / "stages/20260905_1112_stage000e_fourth_prerun_blocker_remediation.md"
)
FOURTH_PRERUN_REVIEW = (
    LINE_ROOT / "reviews/20260905_1023_stage001_prerun_fourth_review_blocked.md"
)
FOURTH_PRERUN_DECISION = (
    LINE_ROOT
    / "reviews/20260905_1023_stage001_prerun_fourth_review_decision_blocked.json"
)
FIFTH_PRERUN_BLOCKER_REMEDIATION = (
    LINE_ROOT
    / "stages/20260905_1213_stage000f_fifth_prerun_blocker_remediation.md"
)
FIFTH_PRERUN_REVIEW = (
    LINE_ROOT / "reviews/20260905_1137_stage001_prerun_fifth_review_blocked.md"
)
FIFTH_PRERUN_DECISION = (
    LINE_ROOT
    / "reviews/20260905_1137_stage001_prerun_fifth_review_decision_blocked.json"
)
SIXTH_PRERUN_BLOCKER_REMEDIATION = (
    LINE_ROOT
    / "stages/20260905_1255_stage000g_sixth_prerun_blocker_remediation.md"
)
SIXTH_PRERUN_REVIEW = (
    LINE_ROOT / "reviews/20260905_1245_stage001_prerun_sixth_review_blocked.md"
)
SIXTH_PRERUN_DECISION = (
    LINE_ROOT
    / "reviews/20260905_1245_stage001_prerun_sixth_review_decision_blocked.json"
)
SEVENTH_PRERUN_BLOCKER_REMEDIATION = (
    LINE_ROOT
    / "stages/20260905_1334_stage000h_seventh_prerun_blocker_remediation.md"
)
SEVENTH_PRERUN_REVIEW = (
    LINE_ROOT / "reviews/20260905_1322_stage001_prerun_seventh_review_blocked.md"
)
SEVENTH_PRERUN_DECISION = (
    LINE_ROOT
    / "reviews/20260905_1322_stage001_prerun_seventh_review_decision_blocked.json"
)
EIGHTH_PRERUN_BLOCKER_REMEDIATION = (
    LINE_ROOT
    / "stages/20260905_1429_stage000i_eighth_prerun_blocker_remediation.md"
)
EIGHTH_PRERUN_REVIEW = (
    LINE_ROOT / "reviews/20260905_1416_stage001_prerun_eighth_review_blocked.md"
)
EIGHTH_PRERUN_DECISION = (
    LINE_ROOT
    / "reviews/20260905_1416_stage001_prerun_eighth_review_decision_blocked.json"
)
NINTH_PRERUN_BLOCKER_REMEDIATION = (
    LINE_ROOT
    / "stages/20260905_1513_stage000j_ninth_prerun_blocker_remediation.md"
)
NINTH_PRERUN_REVIEW = (
    LINE_ROOT / "reviews/20260905_1456_stage001_prerun_ninth_review_blocked.md"
)
NINTH_PRERUN_DECISION = (
    LINE_ROOT
    / "reviews/20260905_1456_stage001_prerun_ninth_review_decision_blocked.json"
)
TENTH_PRERUN_BLOCKER_REMEDIATION = (
    LINE_ROOT
    / "stages/20260905_1554_stage000k_tenth_prerun_blocker_remediation.md"
)
TENTH_PRERUN_REVIEW = (
    LINE_ROOT / "reviews/20260905_1533_stage001_prerun_tenth_review_blocked.md"
)
TENTH_PRERUN_DECISION = (
    LINE_ROOT
    / "reviews/20260905_1533_stage001_prerun_tenth_review_decision_blocked.json"
)
PLAN = LINE_ROOT / "plans/20260905_stage001_formal_event_feature_qualification.md"
FEATURE_TEST = LINE_ROOT / "tests/test_formal_signal_event_features.py"
RUNNER_TEST = LINE_ROOT / "tests/test_stage001_formal_event_feature_qualification.py"
PRERUN_REVIEW = LINE_ROOT / "reviews/20260905_stage001_prerun_independent_review.md"
PRERUN_DECISION = LINE_ROOT / "reviews/20260905_stage001_prerun_review_decision.json"
EXECUTION_STATE_DIR = LINE_ROOT / "stages/20260905_stage001_execution_state"
CLAIM_PATH = EXECUTION_STATE_DIR / "claim.json"
EXECUTION_EVENT_PATH = EXECUTION_STATE_DIR / "event.json"
ARTIFACT_PARENT = LINE_ROOT / "artifacts"
FINAL_DIR = ARTIFACT_PARENT / STAGE
FAILURE_DIR = ARTIFACT_PARENT / f"{STAGE}_failed"

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SENSITIVE_COUNTER_KEYS = (
    "label_value_read_count",
    "label_build_count",
    "model_fit_count",
    "prediction_count",
    "candidate_strategy_run_count",
    "holdout_read_count",
    "network_connection_count",
    "ctp_connection_count",
    "account_query_count",
    "order_api_called_count",
    "production_file_write_count",
    "sensitive_module_import_count",
    "subprocess_spawn_count",
)
STAGE001_GATE_NAMES = (
    "01_active_formal_material_identity_exact",
    "02_execution_version_and_capital_exact",
    "03_single_frozen_start_and_interval_exact",
    "04_cold_worker_isolation_and_no_checkpoint",
    "05_a1_a2_event_and_feature_reproducibility",
    "06_event_year_direction_product_coverage",
    "07_root_event_identity_and_fixed_fu_exclusion",
    "08_twelve_feature_quality",
    "09_formal_eligibility_trace_and_model_cutoff_exact",
    "10_future_and_outcome_columns_absent",
    "11_no_label_model_candidate_or_holdout_operations",
    "12_no_network_execution_or_production_operations",
    "13_input_identity_and_durable_event_ledger",
)


class Stage001Error(RuntimeError):
    pass


class NetworkBlockedError(Stage001Error):
    pass


class SensitiveOperationBlockedError(Stage001Error):
    pass


class WorkerStage001Error(Stage001Error):
    def __init__(self, message: str, receipt: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.receipt = dict(receipt or {})


_EXECUTION_EVENT_THREAD_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _stable_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _json_document_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ).encode("utf-8") + b"\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise Stage001Error(f"identity_input_not_file:{resolved}")
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": _sha256(resolved),
    }


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        offset += os.write(descriptor, payload[offset:])


def create_exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = _json_document_bytes(payload)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Stage001Error(f"exclusive_file_exists:{path.resolve()}") from exc
    try:
        _write_all(descriptor, data)
        os.fsync(descriptor)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)
    _fsync_directory(path.parent)


def _atomic_replace_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = _json_document_bytes(payload)
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        _write_all(descriptor, data)
        os.fsync(descriptor)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        os.close(descriptor)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def zero_sensitive_counters() -> dict[str, int]:
    return {key: 0 for key in SENSITIVE_COUNTER_KEYS}


def merge_sensitive_counters(
    current: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, int]:
    merged = _validate_counter_schema(current)
    observed = receipt.get("sensitive_counters", zero_sensitive_counters())
    observed_counters = _validate_counter_schema(observed)
    return {
        key: int(merged[key]) + int(observed_counters[key])
        for key in SENSITIVE_COUNTER_KEYS
    }


def monotonic_sensitive_counters(
    *snapshots: Mapping[str, Any],
) -> dict[str, int]:
    if not snapshots:
        return zero_sensitive_counters()
    validated = [_validate_counter_schema(snapshot) for snapshot in snapshots]
    return {
        key: max(snapshot[key] for snapshot in validated)
        for key in SENSITIVE_COUNTER_KEYS
    }


def _validate_counter_schema(counters: Mapping[str, Any]) -> dict[str, int]:
    if set(counters) != set(SENSITIVE_COUNTER_KEYS):
        raise Stage001Error("sensitive_counter_schema_mismatch")
    result: dict[str, int] = {}
    for key in SENSITIVE_COUNTER_KEYS:
        value = counters[key]
        if isinstance(value, bool) or int(value) != value or int(value) < 0:
            raise Stage001Error(f"sensitive_counter_invalid:{key}")
        result[key] = int(value)
    return result


def create_execution_event(
    path: Path,
    *,
    campaign_nonce: str,
    lease_id: str,
) -> None:
    _require_hex64(campaign_nonce, "campaign_nonce")
    _require_hex64(lease_id, "lease_id")
    create_exclusive_json(
        path,
        {
            "schema_version": 1,
            "stage": STAGE,
            "line_id": LINE_ID,
            "campaign_nonce": campaign_nonce,
            "lease_id": lease_id,
            "status": "claimed",
            "phase": "claim",
            "sequence": 1,
            "created_at": _now(),
            "updated_at": _now(),
            "counters": zero_sensitive_counters(),
            "error": None,
        },
    )


def create_execution_state(
    state_dir: Path,
    *,
    claim: Mapping[str, Any],
    campaign_nonce: str,
    lease_id: str,
) -> None:
    nonce = _require_hex64(campaign_nonce, "campaign_nonce")
    lease = _require_hex64(lease_id, "lease_id")
    state_dir = state_dir.resolve()
    state_dir.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state_dir.exists():
        raise Stage001Error(f"execution_state_exists:{state_dir}")
    staging = state_dir.parent / f".{state_dir.name}.{nonce}.{lease}.staging"
    if staging.exists():
        raise Stage001Error(f"execution_state_staging_exists:{staging}")
    staging.mkdir(mode=0o700)
    _fsync_directory(state_dir.parent)
    create_exclusive_json(staging / "claim.json", dict(claim))
    create_execution_event(
        staging / "event.json",
        campaign_nonce=nonce,
        lease_id=lease,
    )
    _fsync_directory(staging)
    os.replace(staging, state_dir)
    _fsync_directory(state_dir.parent)


def _assert_execution_lock_anchor_current(
    descriptor: int,
    state_dir: Path,
) -> None:
    locked = os.fstat(descriptor)
    try:
        current = os.stat(state_dir, follow_symlinks=False)
    except OSError as exc:
        raise Stage001Error("execution_event_lock_anchor_drift") from exc
    if (
        not stat.S_ISDIR(locked.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or (locked.st_dev, locked.st_ino) != (current.st_dev, current.st_ino)
    ):
        raise Stage001Error("execution_event_lock_anchor_drift")


def _locked_file_identity(identity: os.stat_result) -> tuple[int, ...]:
    return (
        int(identity.st_dev),
        int(identity.st_ino),
        int(identity.st_mode),
        int(identity.st_size),
        int(identity.st_mtime_ns),
        int(identity.st_ctime_ns),
    )


def _read_locked_regular_file_bytes(
    directory_descriptor: int,
    name: str,
    *,
    error_prefix: str,
) -> bytes:
    if not name or name in {".", ".."} or Path(name).name != name:
        raise Stage001Error(f"{error_prefix}_path_invalid")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=directory_descriptor)
    except FileNotFoundError as exc:
        raise Stage001Error(f"{error_prefix}_missing") from exc
    except OSError as exc:
        raise Stage001Error(f"{error_prefix}_unreadable") from exc
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        while True:
            block = os.read(descriptor, 64 * 1024)
            if not block:
                break
            chunks.append(block)
        data = b"".join(chunks)
        after = os.fstat(descriptor)
        try:
            current = os.stat(
                name,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise Stage001Error(f"{error_prefix}_replaced") from exc
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(after.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or _locked_file_identity(before) != _locked_file_identity(after)
            or _locked_file_identity(after) != _locked_file_identity(current)
            or len(data) != int(after.st_size)
        ):
            raise Stage001Error(f"{error_prefix}_replaced")
        return data
    except OSError as exc:
        raise Stage001Error(f"{error_prefix}_unreadable") from exc
    finally:
        os.close(descriptor)


def _read_locked_json_mapping(
    directory_descriptor: int,
    name: str,
    *,
    error_prefix: str,
) -> tuple[dict[str, Any], bytes]:
    data = _read_locked_regular_file_bytes(
        directory_descriptor,
        name,
        error_prefix=error_prefix,
    )
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage001Error(f"{error_prefix}_invalid") from exc
    if not isinstance(payload, Mapping):
        raise Stage001Error(f"{error_prefix}_invalid")
    return dict(payload), data


def _read_current_execution_claim(
    event_path: Path,
    *,
    lock_descriptor: int,
    campaign_nonce: str | None = None,
    lease_id: str | None = None,
    expected_claim: Mapping[str, Any] | None = None,
    expected_claim_bytes: bytes | None = None,
) -> tuple[dict[str, Any], bytes]:
    state_dir = event_path.parent
    _assert_execution_lock_anchor_current(lock_descriptor, state_dir)
    payload, data = _read_locked_json_mapping(
        lock_descriptor,
        "claim.json",
        error_prefix="execution_event_claim",
    )
    if (
        payload.get("schema_version") != 1
        or payload.get("stage") != STAGE
        or payload.get("line_id") != LINE_ID
        or payload.get("replay_permitted") is not False
        or HEX64.fullmatch(str(payload.get("campaign_nonce", ""))) is None
        or HEX64.fullmatch(str(payload.get("lease_id", ""))) is None
    ):
        raise Stage001Error("execution_event_claim_binding_mismatch")
    if campaign_nonce is not None and payload.get("campaign_nonce") != campaign_nonce:
        raise Stage001Error("execution_event_claim_binding_mismatch")
    if lease_id is not None and payload.get("lease_id") != lease_id:
        raise Stage001Error("execution_event_claim_binding_mismatch")
    if expected_claim is not None:
        expected_bytes = (
            _json_document_bytes(expected_claim)
            if expected_claim_bytes is None
            else expected_claim_bytes
        )
        if dict(payload) != dict(expected_claim) or data != expected_bytes:
            raise Stage001Error("execution_event_claim_binding_mismatch")
    return dict(payload), data


def _read_current_execution_event(
    path: Path,
    *,
    lock_descriptor: int,
) -> tuple[dict[str, Any], bytes, str]:
    _assert_execution_lock_anchor_current(lock_descriptor, path.parent)
    base, base_bytes = _read_locked_json_mapping(
        lock_descriptor,
        path.name,
        error_prefix="execution_event",
    )
    try:
        base_sequence = int(base.get("sequence", 0))
        _validate_counter_schema(base.get("counters", {}))
    except (Stage001Error, TypeError, ValueError) as exc:
        raise Stage001Error("execution_event_journal_chain_invalid") from exc
    if (
        base_sequence != 1
        or base.get("schema_version") != 1
        or base.get("stage") != STAGE
        or base.get("line_id") != LINE_ID
        or HEX64.fullmatch(str(base.get("campaign_nonce", ""))) is None
        or HEX64.fullmatch(str(base.get("lease_id", ""))) is None
        or base.get("status") not in {"claimed", "failed"}
    ):
        raise Stage001Error("execution_event_journal_chain_invalid")

    pattern = _execution_event_entry_pattern(path.name)
    by_sequence: dict[int, tuple[str, str]] = {}
    prefix = f"{path.stem}.seq-"
    for name in os.listdir(lock_descriptor):
        match = pattern.fullmatch(name)
        if match is None:
            if name.startswith(prefix) and name.endswith(path.suffix):
                raise Stage001Error("execution_event_journal_entry_name_invalid")
            continue
        sequence = int(match.group("sequence"))
        previous_sha256 = match.group("previous_sha256")
        if sequence < 2 or sequence in by_sequence:
            raise Stage001Error("execution_event_journal_sequence_ambiguous")
        by_sequence[sequence] = (name, previous_sha256)

    if by_sequence and sorted(by_sequence) != list(
        range(2, max(by_sequence) + 1)
    ):
        raise Stage001Error("execution_event_journal_sequence_gap")

    previous = base
    previous_bytes = base_bytes
    previous_name = path.name
    for sequence in sorted(by_sequence):
        name, recorded_previous_sha256 = by_sequence[sequence]
        if recorded_previous_sha256 != hashlib.sha256(previous_bytes).hexdigest():
            raise Stage001Error("execution_event_journal_chain_invalid")
        current, current_bytes = _read_locked_json_mapping(
            lock_descriptor,
            name,
            error_prefix="execution_event_journal_entry",
        )
        try:
            previous_counters = _validate_counter_schema(previous.get("counters", {}))
            current_counters = _validate_counter_schema(current.get("counters", {}))
        except Stage001Error as exc:
            raise Stage001Error("execution_event_journal_chain_invalid") from exc
        allowed_transitions = {
            "claimed": {"running", "failed"},
            "running": {"running", "completed", "failed"},
            "completed": set(),
            "failed": {"failed"},
        }
        immutable_fields = (
            "schema_version",
            "stage",
            "line_id",
            "campaign_nonce",
            "lease_id",
            "created_at",
        )
        if (
            int(current.get("sequence", 0)) != sequence
            or any(current.get(key) != base.get(key) for key in immutable_fields)
            or current.get("status")
            not in allowed_transitions.get(str(previous.get("status", "")), set())
            or any(
                current_counters[key] < previous_counters[key]
                for key in SENSITIVE_COUNTER_KEYS
            )
        ):
            raise Stage001Error("execution_event_journal_chain_invalid")
        previous = current
        previous_bytes = current_bytes
        previous_name = name
    return previous, previous_bytes, previous_name


def _execution_event_entry_pattern(event_name: str) -> re.Pattern[str]:
    path = Path(event_name)
    return re.compile(
        rf"{re.escape(path.stem)}\.seq-(?P<sequence>[0-9]{{20}})\."
        rf"prev-(?P<previous_sha256>[0-9a-f]{{64}}){re.escape(path.suffix)}"
    )


def _execution_event_entry_name(
    event_name: str,
    sequence: int,
    previous_sha256: str,
) -> str:
    path = Path(event_name)
    if (
        path.name != event_name
        or int(sequence) < 2
        or HEX64.fullmatch(str(previous_sha256)) is None
    ):
        raise Stage001Error("execution_event_journal_entry_name_invalid")
    return (
        f"{path.stem}.seq-{int(sequence):020d}."
        f"prev-{previous_sha256}{path.suffix}"
    )


def read_execution_event(path: Path) -> dict[str, Any]:
    with _execution_event_lock(path) as lock_descriptor:
        event, _, _ = _read_current_execution_event(
            path,
            lock_descriptor=lock_descriptor,
        )
        return event


@contextmanager
def _execution_event_lock(
    path: Path,
    *,
    expected_claim: Mapping[str, Any] | None = None,
):
    state_dir = path.parent
    with _EXECUTION_EVENT_THREAD_LOCK:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(
            os,
            "O_NOFOLLOW",
            0,
        )
        try:
            descriptor = os.open(state_dir, flags)
        except OSError as exc:
            raise Stage001Error(
                f"execution_event_lock_failed:{state_dir.absolute()}"
            ) from exc
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            except OSError as exc:
                raise Stage001Error(
                    f"execution_event_lock_failed:{state_dir.absolute()}"
                ) from exc
            _assert_execution_lock_anchor_current(descriptor, state_dir)
            _read_current_execution_claim(
                path,
                lock_descriptor=descriptor,
                expected_claim=expected_claim,
            )
            try:
                yield descriptor
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _next_execution_event(
    current: Mapping[str, Any],
    *,
    campaign_nonce: str,
    lease_id: str,
    status: str,
    phase: str,
    counters: Mapping[str, Any],
    error: str | None,
    details: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if status not in {"claimed", "running", "completed", "failed"}:
        raise Stage001Error(f"execution_event_status_invalid:{status}")
    if (
        current.get("campaign_nonce") != campaign_nonce
        or current.get("lease_id") != lease_id
    ):
        raise Stage001Error("execution_event_binding_mismatch")
    current_status = str(current.get("status", ""))
    allowed_transitions = {
        "claimed": {"running", "failed"},
        "running": {"running", "completed", "failed"},
        "completed": set(),
        "failed": {"failed"},
    }
    if status not in allowed_transitions.get(current_status, set()):
        if current_status in {"completed", "failed"}:
            raise Stage001Error("execution_event_terminal_transition_invalid")
        raise Stage001Error(
            f"execution_event_transition_invalid:{current_status}:{status}"
        )
    current_counters = _validate_counter_schema(current.get("counters", {}))
    next_counters = _validate_counter_schema(counters)
    for key in SENSITIVE_COUNTER_KEYS:
        if next_counters[key] < current_counters[key]:
            raise Stage001Error(f"execution_event_counter_regression:{key}")
    updated = dict(current)
    updated.update(
        {
            "status": status,
            "phase": str(phase),
            "sequence": int(current.get("sequence", 0)) + 1,
            "updated_at": _now(),
            "counters": next_counters,
            "error": error,
        }
    )
    if details is not None:
        updated["details"] = dict(details)
    return updated


def _execution_event_before_replace_hook(
    _path: Path,
    _lock_descriptor: int,
) -> None:
    return None


def _atomic_append_execution_event_locked(
    path: Path,
    *,
    lock_descriptor: int,
    expected_current: Mapping[str, Any],
    expected_current_bytes: bytes,
    expected_current_entry: str,
    expected_claim: Mapping[str, Any],
    expected_claim_bytes: bytes,
    payload: Mapping[str, Any],
) -> None:
    state_dir = path.parent
    event_name = path.name
    if not event_name or event_name in {".", ".."}:
        raise Stage001Error("execution_event_path_invalid")
    next_sequence = int(payload.get("sequence", 0))
    if next_sequence != int(expected_current.get("sequence", 0)) + 1:
        raise Stage001Error("execution_event_journal_sequence_invalid")
    next_name = _execution_event_entry_name(
        event_name,
        next_sequence,
        hashlib.sha256(expected_current_bytes).hexdigest(),
    )
    _assert_execution_lock_anchor_current(lock_descriptor, state_dir)
    temporary_name = (
        f".{event_name}.{os.getpid()}.{threading.get_ident()}."
        f"{os.urandom(8).hex()}.tmp"
    )
    data = _json_document_bytes(payload)
    descriptor = os.open(
        temporary_name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
        dir_fd=lock_descriptor,
    )
    try:
        _write_all(descriptor, data)
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
    except BaseException:
        try:
            os.unlink(temporary_name, dir_fd=lock_descriptor)
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(descriptor)

    try:
        _execution_event_before_replace_hook(path, lock_descriptor)
        _assert_execution_lock_anchor_current(lock_descriptor, state_dir)
        _read_current_execution_claim(
            path,
            lock_descriptor=lock_descriptor,
            expected_claim=expected_claim,
            expected_claim_bytes=expected_claim_bytes,
        )
        current, current_bytes, current_entry = _read_current_execution_event(
            path,
            lock_descriptor=lock_descriptor,
        )
        if (
            current != dict(expected_current)
            or current_bytes != expected_current_bytes
            or current_entry != expected_current_entry
        ):
            raise Stage001Error("execution_event_compare_and_swap_mismatch")
        _assert_execution_lock_anchor_current(lock_descriptor, state_dir)
        try:
            os.link(
                temporary_name,
                next_name,
                src_dir_fd=lock_descriptor,
                dst_dir_fd=lock_descriptor,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise Stage001Error("execution_event_compare_and_swap_mismatch") from exc
        os.fsync(lock_descriptor)
        os.unlink(temporary_name, dir_fd=lock_descriptor)
        os.fsync(lock_descriptor)
        _assert_execution_lock_anchor_current(lock_descriptor, state_dir)
        _read_current_execution_claim(
            path,
            lock_descriptor=lock_descriptor,
            expected_claim=expected_claim,
            expected_claim_bytes=expected_claim_bytes,
        )
        committed, committed_bytes, committed_entry = _read_current_execution_event(
            path,
            lock_descriptor=lock_descriptor,
        )
        if (
            committed != dict(payload)
            or committed_bytes != data
            or committed_entry != next_name
        ):
            raise Stage001Error("execution_event_commit_verification_failed")
    finally:
        try:
            os.unlink(temporary_name, dir_fd=lock_descriptor)
        except FileNotFoundError:
            pass


def _replace_execution_event_if_matches_locked(
    path: Path,
    *,
    lock_descriptor: int,
    expected_current: Mapping[str, Any],
    expected_claim: Mapping[str, Any],
    campaign_nonce: str,
    lease_id: str,
    status: str,
    phase: str,
    counters: Mapping[str, Any],
    error: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    _, claim_bytes = _read_current_execution_claim(
        path,
        lock_descriptor=lock_descriptor,
        campaign_nonce=campaign_nonce,
        lease_id=lease_id,
        expected_claim=expected_claim,
    )
    current, current_bytes, current_entry = _read_current_execution_event(
        path,
        lock_descriptor=lock_descriptor,
    )
    if (
        current != dict(expected_current)
        or current_bytes != _json_document_bytes(expected_current)
    ):
        raise Stage001Error("execution_event_compare_and_swap_mismatch")
    updated = _next_execution_event(
        current,
        campaign_nonce=campaign_nonce,
        lease_id=lease_id,
        status=status,
        phase=phase,
        counters=counters,
        error=error,
        details=details,
    )
    _atomic_append_execution_event_locked(
        path,
        lock_descriptor=lock_descriptor,
        expected_current=current,
        expected_current_bytes=current_bytes,
        expected_current_entry=current_entry,
        expected_claim=expected_claim,
        expected_claim_bytes=claim_bytes,
        payload=updated,
    )


def update_execution_event(
    path: Path,
    *,
    campaign_nonce: str,
    lease_id: str,
    status: str,
    phase: str,
    counters: Mapping[str, Any],
    error: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    with _execution_event_lock(path) as lock_descriptor:
        claim, claim_bytes = _read_current_execution_claim(
            path,
            lock_descriptor=lock_descriptor,
        )
        current, current_bytes, current_entry = _read_current_execution_event(
            path,
            lock_descriptor=lock_descriptor,
        )
        updated = _next_execution_event(
            current,
            campaign_nonce=campaign_nonce,
            lease_id=lease_id,
            status=status,
            phase=phase,
            counters=counters,
            error=error,
            details=details,
        )
        if (
            claim.get("campaign_nonce") != campaign_nonce
            or claim.get("lease_id") != lease_id
        ):
            raise Stage001Error("execution_event_claim_binding_mismatch")
        _atomic_append_execution_event_locked(
            path,
            lock_descriptor=lock_descriptor,
            expected_current=current,
            expected_current_bytes=current_bytes,
            expected_current_entry=current_entry,
            expected_claim=claim,
            expected_claim_bytes=claim_bytes,
            payload=updated,
        )


def _require_hex64(value: Any, field: str) -> str:
    text = str(value)
    if HEX64.fullmatch(text) is None:
        raise Stage001Error(f"authorization_{field}_invalid")
    return text


def _parse_timestamp(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise Stage001Error(f"authorization_{field}_invalid") from exc
    if parsed.tzinfo is None:
        raise Stage001Error(f"authorization_{field}_not_timezone_aware")
    return parsed.astimezone(timezone.utc)


def validate_authorization(
    authorization: Mapping[str, Any],
    expected_bound_files: Mapping[str, Path],
    *,
    expected_input_contract_sha256: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if authorization.get("schema_version") != 1:
        raise Stage001Error("authorization_schema_version_mismatch")
    if authorization.get("stage") != STAGE:
        raise Stage001Error("authorization_stage_mismatch")
    if authorization.get("scope") != AUTHORIZATION_SCOPE:
        raise Stage001Error("authorization_scope_mismatch")
    if authorization.get("decision") != REQUIRED_REVIEW_DECISION:
        raise Stage001Error("authorization_review_decision_mismatch")
    nonce = _require_hex64(authorization.get("campaign_nonce"), "campaign_nonce")
    lease_id = _require_hex64(authorization.get("lease_id"), "lease_id")
    issued_at = _parse_timestamp(authorization.get("issued_at"), "issued_at")
    expires_at = _parse_timestamp(authorization.get("expires_at"), "expires_at")
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if instant < issued_at:
        raise Stage001Error("authorization_not_yet_valid")
    if instant >= expires_at:
        raise Stage001Error("authorization_expired")
    if expires_at <= issued_at:
        raise Stage001Error("authorization_lease_window_invalid")

    observed = authorization.get("bound_files")
    if not isinstance(observed, Mapping):
        raise Stage001Error("authorization_bound_files_not_mapping")
    if set(observed) != set(expected_bound_files):
        raise Stage001Error("authorization_bound_file_keys_mismatch")
    for key, expected_path in sorted(expected_bound_files.items()):
        item = observed[key]
        if not isinstance(item, Mapping):
            raise Stage001Error(f"authorization_bound_file_invalid:{key}")
        expected = expected_path.resolve(strict=True)
        if Path(str(item.get("path", ""))).resolve() != expected:
            raise Stage001Error(f"authorization_bound_file_path_mismatch:{key}")
        expected_sha = str(item.get("sha256", ""))
        if HEX64.fullmatch(expected_sha) is None or _sha256(expected) != expected_sha:
            raise Stage001Error(f"authorization_bound_file_drift:{key}")

    if expected_input_contract_sha256 is not None:
        supplied = str(authorization.get("input_file_contract_sha256", ""))
        if supplied != expected_input_contract_sha256:
            raise Stage001Error("authorization_input_contract_mismatch")
    return {
        "campaign_nonce": nonce,
        "lease_id": lease_id,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


def worker_environment(
    _base: Mapping[str, str],
    runtime_root: Path,
    worker_id: str,
) -> dict[str, str]:
    if worker_id not in {"A1", "A2"}:
        raise Stage001Error(f"worker_id_invalid:{worker_id}")
    root = runtime_root.resolve()
    tmp = root / "tmp"
    mpl = root / "mplconfig"
    home = root / "home"
    for directory in (root, tmp, mpl, home, root / ".vntrader"):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
    return {
        "HOME": str(home),
        "LANG": "C",
        "LC_ALL": "C",
        "MPLCONFIGDIR": str(mpl),
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "PATH": "/usr/bin:/bin",
        "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR": "1",
        "TMPDIR": str(tmp),
        "VECLIB_MAXIMUM_THREADS": "1",
    }


def _canonical_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "event_id" in result.columns:
        result.sort_values("event_id", inplace=True, kind="mergesort")
    result.reset_index(drop=True, inplace=True)
    return result


def compare_worker_frames(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    atol: float = 1e-12,
) -> dict[str, Any]:
    if tuple(left.columns) != tuple(right.columns) or left.shape != right.shape:
        raise Stage001Error(
            f"worker_frame_shape_mismatch:{left.shape}:{right.shape}"
        )
    first = _canonical_frame(left)
    second = _canonical_frame(right)
    if "event_id" in first.columns and not first["event_id"].astype(str).equals(
        second["event_id"].astype(str)
    ):
        raise Stage001Error("worker_event_identity_mismatch")

    max_abs_diff = 0.0
    for column in first.columns:
        left_column = first[column]
        right_column = second[column]
        if pd.api.types.is_numeric_dtype(left_column) and pd.api.types.is_numeric_dtype(
            right_column
        ):
            left_values = left_column.to_numpy(dtype=float)
            right_values = right_column.to_numpy(dtype=float)
            close = np.isclose(
                left_values,
                right_values,
                rtol=0.0,
                atol=atol,
                equal_nan=True,
            )
            if not bool(close.all()):
                raise Stage001Error(f"worker_numeric_mismatch:{column}")
            finite = np.isfinite(left_values) & np.isfinite(right_values)
            if finite.any():
                max_abs_diff = max(
                    max_abs_diff,
                    float(np.max(np.abs(left_values[finite] - right_values[finite]))),
                )
        else:
            equal = left_column.fillna("<NA>").astype(str).equals(
                right_column.fillna("<NA>").astype(str)
            )
            if not equal:
                raise Stage001Error(f"worker_value_mismatch:{column}")
    return {
        "passed": True,
        "row_count": int(len(first)),
        "column_count": int(len(first.columns)),
        "max_abs_numeric_diff": max_abs_diff,
        "atol": float(atol),
        "canonical_sha256_a1": _frame_sha256(first),
        "canonical_sha256_a2": _frame_sha256(second),
    }


def _frame_sha256(frame: pd.DataFrame) -> str:
    csv = frame.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    ).encode("utf-8")
    return hashlib.sha256(csv).hexdigest()


def assert_identity_stable(before: Mapping[str, Any], after: Mapping[str, Any]) -> None:
    before_files = before.get("files")
    after_files = after.get("files")
    if not isinstance(before_files, Mapping) or not isinstance(after_files, Mapping):
        raise Stage001Error("input_identity_files_missing")
    if set(before_files) != set(after_files):
        raise Stage001Error("input_identity_keys_drift")
    identity_fields = ("path", "size", "mtime_ns", "sha256")
    for name in sorted(before_files):
        first = before_files[name]
        second = after_files[name]
        if not isinstance(first, Mapping) or not isinstance(second, Mapping):
            raise Stage001Error(f"input_identity_item_invalid:{name}")
        for field in identity_fields:
            if first.get(field) != second.get(field):
                raise Stage001Error(f"input_identity_item_drift:{name}:{field}")
    if before.get("runtime") != after.get("runtime"):
        raise Stage001Error("input_runtime_item_drift")
    if before.get("formal_identity") != after.get("formal_identity"):
        raise Stage001Error("input_formal_identity_drift")
    keys = ("file_contract_sha256", "runtime_contract_sha256")
    changed = [key for key in keys if before.get(key) != after.get(key)]
    if changed:
        raise Stage001Error(f"input_identity_contract_drift:{','.join(changed)}")


WORKER_SUCCESS_RECEIPT_FIELDS = frozenset(
    {
        "worker_id",
        "campaign_nonce",
        "lease_id",
        "pid",
        "python_executable",
        "python_version",
        "cwd",
        "runtime_root",
        "database",
        "setting",
        "tmpdir",
        "mplconfigdir",
        "home",
        "sys_path",
        "source_file_contract_sha256",
        "checkpoint_reuse_count",
        "sensitive_counters",
        "started_at",
        "completed_at",
        "status",
        "analysis_start",
        "analysis_end",
        "capital",
        "official_live_version",
        "baseline_replay_count",
        "network_connection_attempt_count",
        "modules",
        "sandbox_enforced",
        "sandbox_policy_mode",
        "sandbox_launch_executable",
        "sandbox_profile",
        "worker_capability",
        "bootstrap_attestation",
        "sensitive_guard_enforced",
        "event_count",
        "event_feature_sha256",
        "event_feature_file",
        "formal_identity",
        "feature_path",
    }
)
RAW_WORKER_SUCCESS_RECEIPT_FIELDS = frozenset(
    WORKER_SUCCESS_RECEIPT_FIELDS - {"feature_path"}
)
FILE_IDENTITY_FIELDS = frozenset({"path", "size", "mtime_ns", "sha256"})
WORKER_CAPABILITY_FIELDS = frozenset(
    {
        "schema_version",
        "stage",
        "line_id",
        "campaign_nonce",
        "lease_id",
        "worker_id",
        "capability_nonce",
        "attempt_dir",
        "runtime_root",
        "output_dir",
        "input_manifest_path",
        "input_manifest_sha256",
        "sandbox_executable_path",
        "sandbox_executable_sha256",
        "sandbox_policy_mode",
        "sandbox_profile_path",
        "sandbox_profile_sha256",
        "sandbox_probe_path",
        "bootstrap_path",
        "bootstrap_sha256",
        "runner_path",
        "runner_sha256",
        "python_executable",
        "isolated_startup_sys_path",
        "approved_sys_path",
        "worker_environment",
        "parent_channel_secret_sha256",
        "claim_path",
        "event_path",
        "issued_at",
        "replay_permitted",
    }
)
BOOTSTRAP_ATTESTATION_FIELDS = frozenset(
    {
        "schema_version",
        "attestation_type",
        "stage",
        "line_id",
        "campaign_nonce",
        "lease_id",
        "worker_id",
        "capability_nonce",
        "pid",
        "python_executable",
        "python_version",
        "interpreter_flags",
        "startup_sys_path",
        "approved_sys_path",
        "effective_sys_path",
        "pre_import_forbidden_modules",
        "worker_environment_sha256",
        "parent_channel_secret_sha256",
        "bootstrap_path",
        "bootstrap_sha256",
        "runner_path",
        "runner_sha256",
        "sandbox_probe",
        "attested_at",
    }
)
BOOTSTRAP_INTERPRETER_FLAGS = {
    "isolated": 1,
    "ignore_environment": 1,
    "no_site": 1,
    "no_user_site": 1,
    "safe_path": True,
    "dont_write_bytecode": 1,
}
BOOTSTRAP_SANDBOX_PROBE_FIELDS = frozenset({"path", "write_denied", "errno"})
RELATIVE_FILE_IDENTITY_FIELDS = frozenset(
    {"relative_path", "size", "mtime_ns", "sha256"}
)
PORTABLE_WORKER_RECEIPT_FIELDS = frozenset(
    set(WORKER_SUCCESS_RECEIPT_FIELDS)
    | {
        "receipt_schema_version",
        "receipt_type",
        "raw_worker_receipt",
        "raw_worker_receipt_sha256",
        "worker_log_published",
    }
)
PORTABLE_RECEIPT_FIELDS = frozenset(
    {"schema_version", "receipt_type", "workers"}
)
EPHEMERAL_PATH_FIELDS = frozenset(
    {"ephemeral_relative_path", "removed_after_publish"}
)
PORTABLE_DATABASE_FIELDS = frozenset(
    {
        "ephemeral_relative_path",
        "size",
        "mtime_ns",
        "sha256",
        "source_input_logical_key",
        "verified_before_cleanup",
        "removed_after_publish",
    }
)
SUCCESS_SUMMARY_FIELDS = frozenset(
    {
        "schema_version",
        "stage",
        "line_id",
        "created_at",
        "campaign_nonce",
        "lease_id",
        "analysis_start",
        "analysis_end",
        "cold_worker_count",
        "baseline_replay_count",
        "formal_identity",
        "worker_comparison",
        "worker_isolation",
        "feature_qualification",
        "stage001_gates",
        "sensitive_counters",
        "decision",
        "trains_model",
        "reads_or_builds_labels",
        "publishes_backtest_performance",
        "independent_postrun_review_required",
        "replay_permitted",
    }
)
INPUT_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "stage",
        "created_at",
        "formal_identity",
        "files",
        "input_file_count",
        "input_logical_key_sha256",
        "file_contract_sha256",
        "runtime",
        "runtime_contract_sha256",
    }
)
FORMAL_IDENTITY_FIELDS = frozenset(
    {
        "formal_release_id",
        "formal_strategy",
        "official_live_version",
        "formal_material_manifest_sha256",
        "capital",
        "release_path",
        "manifest_file_sha256",
        "eligibility_path",
        "eligibility_sha256",
    }
)
EXECUTION_CLAIM_FIELDS = frozenset(
    {
        "schema_version",
        "stage",
        "line_id",
        "scope",
        "campaign_nonce",
        "lease_id",
        "authorization_path",
        "authorization_sha256",
        "authorization_payload_sha256",
        "input_file_contract_sha256",
        "claimed_at",
        "replay_permitted",
    }
)
EXECUTION_EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "stage",
        "line_id",
        "campaign_nonce",
        "lease_id",
        "status",
        "phase",
        "sequence",
        "created_at",
        "updated_at",
        "counters",
        "error",
        "details",
    }
)
SUCCESS_PUBLISH_EVENT_DETAIL_FIELDS = frozenset(
    {
        "decision",
        "event_count",
        "event_feature_sha256",
        "summary_payload_sha256",
        "input_file_contract_sha256",
        "runtime_contract_sha256",
        "authorization_payload_sha256",
        "claim_payload_sha256",
        "stage_gates_passed",
        "attempt_dir",
        "final_dir",
    }
)
SUCCESS_COMPLETED_EVENT_DETAIL_FIELDS = frozenset(
    set(SUCCESS_PUBLISH_EVENT_DETAIL_FIELDS)
    | {
        "publishing_event_sha256",
        "summary_file_sha256",
        "artifact_manifest_sha256",
        "attempt_cleanup_completed",
        "attempt_cleanup_error",
    }
)
AUTHORIZATION_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "stage",
        "scope",
        "decision",
        "campaign_nonce",
        "lease_id",
        "issued_at",
        "expires_at",
        "bound_files",
        "input_file_contract_sha256",
    }
)
SUCCESS_BUNDLE_FILE_SET = frozenset(
    {
        "event_features.csv.gz",
        "event_coverage.csv",
        "feature_diagnostics.csv",
        "input_manifest.json",
        "input_identities.json",
        "worker_receipts.json",
        "authorization_receipt.json",
        "execution_claim.json",
        "execution_event.json",
        "summary.json",
        "report.md",
        "artifact_manifest.json",
        *(
            f"workers/{worker_id}/{filename}"
            for worker_id in ("A1", "A2")
            for filename in (
                "worker_receipt.raw.json",
                "vt_setting.json",
                "stage001.sb",
                "worker_capability.consumed.json",
                "event_features.csv",
            )
        ),
    }
)


def _receipt_timestamp(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise Stage001Error(f"worker_timestamp_invalid:{field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Stage001Error(f"worker_timestamp_not_aware:{field}")
    return parsed


def _assert_receipt_file_identity(
    identity: Any,
    *,
    label: str,
) -> tuple[Path, dict[str, Any]]:
    if not isinstance(identity, Mapping):
        raise Stage001Error(f"worker_{label}_receipt_missing")
    if set(identity) != FILE_IDENTITY_FIELDS:
        raise Stage001Error(f"worker_{label}_identity_schema_invalid")
    try:
        path = Path(str(identity["path"])).resolve(strict=True)
        observed = _file_identity(path)
    except (KeyError, OSError, RuntimeError) as exc:
        raise Stage001Error(f"worker_{label}_file_missing") from exc
    if dict(identity) != observed:
        raise Stage001Error(f"worker_{label}_identity_drift")
    return path, observed


def evaluate_worker_isolation(
    receipts: Iterable[Mapping[str, Any]],
    *,
    expected_source_contract_sha256: str,
    expected_database_sha256: str,
    expected_python_executable: Path,
    expected_modules: Mapping[str, str],
    expected_formal_identity: Mapping[str, Any],
    expected_campaign_nonce: str,
    expected_lease_id: str,
) -> dict[str, Any]:
    items = list(receipts)
    if len(items) != 2 or {item.get("worker_id") for item in items} != {"A1", "A2"}:
        raise Stage001Error("worker_receipt_pair_invalid")
    by_id = {str(item["worker_id"]): item for item in items}
    first = by_id["A1"]
    second = by_id["A2"]
    for item in (first, second):
        missing = sorted(WORKER_SUCCESS_RECEIPT_FIELDS - set(item))
        extra = sorted(set(item) - WORKER_SUCCESS_RECEIPT_FIELDS)
        if missing or extra:
            raise Stage001Error(
                "worker_receipt_schema_invalid:"
                f"{item.get('worker_id')}:missing={','.join(missing)}:"
                f"extra={','.join(extra)}"
            )
    if int(first.get("pid", 0)) <= 0 or int(second.get("pid", 0)) <= 0:
        raise Stage001Error("worker_pid_invalid")
    if int(first["pid"]) == int(second["pid"]):
        raise Stage001Error("worker_process_not_distinct")
    if first.get("sys_path") != second.get("sys_path") or not isinstance(
        first.get("sys_path"), list
    ) or not first.get("sys_path"):
        raise Stage001Error("worker_sys_path_drift")

    path_fields = ("runtime_root", "tmpdir", "mplconfigdir", "home")
    for field in path_fields:
        values = [str(item.get(field, "")) for item in (first, second)]
        if not all(values) or len(set(values)) != 2:
            raise Stage001Error(f"worker_path_not_distinct:{field}")
    event_shas: set[str] = set()
    event_counts: set[int] = set()
    for item in (first, second):
        worker_id = str(item["worker_id"])
        if (
            item.get("campaign_nonce") != expected_campaign_nonce
            or item.get("lease_id") != expected_lease_id
        ):
            raise Stage001Error("worker_campaign_binding_drift")
        if item.get("status") != "completed":
            raise Stage001Error("worker_status_not_completed")
        started = _receipt_timestamp(item.get("started_at"), "started_at")
        completed = _receipt_timestamp(item.get("completed_at"), "completed_at")
        if completed < started:
            raise Stage001Error("worker_timestamp_order_invalid")
        if dict(item.get("formal_identity", {})) != dict(expected_formal_identity):
            raise Stage001Error("worker_formal_identity_drift")

        runtime = Path(str(item["runtime_root"])).resolve(strict=True)
        if Path(str(item.get("cwd", ""))).resolve() != runtime:
            raise Stage001Error("worker_cwd_not_runtime")
        if Path(str(item.get("python_executable", ""))).resolve() != Path(
            expected_python_executable
        ).resolve():
            raise Stage001Error("worker_python_executable_drift")
        if item.get("python_version") != sys.version:
            raise Stage001Error("worker_python_version_drift")
        for field in ("tmpdir", "mplconfigdir", "home"):
            path = Path(str(item[field])).resolve()
            if runtime != path and runtime not in path.parents:
                raise Stage001Error(f"worker_path_outside_runtime:{field}")

        database = item.get("database")
        if isinstance(database, Mapping) and database.get("sha256") != expected_database_sha256:
            raise Stage001Error("worker_database_sha_mismatch")
        database_path, _ = _assert_receipt_file_identity(database, label="database")
        if runtime not in database_path.parents:
            raise Stage001Error("worker_database_outside_runtime")

        setting = item.get("setting")
        empty_setting_sha = hashlib.sha256(b"{}\n").hexdigest()
        if isinstance(setting, Mapping) and setting.get("sha256") != empty_setting_sha:
            raise Stage001Error("worker_setting_sha_mismatch")
        setting_path, _ = _assert_receipt_file_identity(setting, label="setting")
        if runtime not in setting_path.parents:
            raise Stage001Error("worker_setting_outside_runtime")
        if setting_path.read_bytes() != b"{}\n":
            raise Stage001Error("worker_setting_content_mismatch")

        if int(item.get("checkpoint_reuse_count", -1)) != 0:
            raise Stage001Error("worker_checkpoint_reuse_detected")
        if item.get("analysis_start") != START.date().isoformat() or item.get(
            "analysis_end"
        ) != END.date().isoformat():
            raise Stage001Error("worker_analysis_interval_drift")
        if float(item.get("capital", -1.0)) != EXPECTED_CAPITAL:
            raise Stage001Error("worker_capital_receipt_drift")
        if item.get("official_live_version") != EXPECTED_OFFICIAL_VERSION:
            raise Stage001Error("worker_official_version_receipt_drift")
        if item.get("source_file_contract_sha256") != expected_source_contract_sha256:
            raise Stage001Error("worker_source_contract_drift")
        if int(item.get("baseline_replay_count", -1)) != 1:
            raise Stage001Error("worker_baseline_replay_count_invalid")
        if int(item.get("network_connection_attempt_count", -1)) != 0:
            raise Stage001Error("worker_network_attempt_detected")
        if item.get("sensitive_guard_enforced") is not True:
            raise Stage001Error("worker_sensitive_guard_missing")
        if item.get("sandbox_enforced") is not True:
            raise Stage001Error("worker_sandbox_missing")
        if item.get("sandbox_policy_mode") != SANDBOX_POLICY_MODE:
            raise Stage001Error("worker_sandbox_policy_drift")
        if Path(str(item.get("sandbox_launch_executable", ""))).resolve() != SANDBOX_EXECUTABLE.resolve():
            raise Stage001Error("worker_sandbox_executable_drift")
        profile_path, _ = _assert_receipt_file_identity(
            item.get("sandbox_profile"),
            label="sandbox_profile",
        )
        if profile_path.parent != runtime.parent:
            raise Stage001Error("worker_sandbox_profile_path_invalid")
        capability_path, _ = _assert_receipt_file_identity(
            item.get("worker_capability"),
            label="capability",
        )
        if capability_path != runtime.parent / "worker_capability.consumed.json":
            raise Stage001Error("worker_capability_receipt_path_invalid")
        capability_payload = json.loads(capability_path.read_text(encoding="utf-8"))
        if (
            not isinstance(capability_payload, Mapping)
            or set(capability_payload) != WORKER_CAPABILITY_FIELDS
            or capability_payload.get("schema_version") != 2
            or capability_payload.get("campaign_nonce") != expected_campaign_nonce
            or capability_payload.get("lease_id") != expected_lease_id
            or capability_payload.get("worker_id") != worker_id
            or capability_payload.get("replay_permitted") is not False
        ):
            raise Stage001Error("worker_capability_receipt_binding_drift")
        bootstrap_attestation = _validate_bootstrap_receipt_binding(
            capability_payload,
            item.get("bootstrap_attestation"),
        )
        if (
            bootstrap_attestation.get("pid") != item.get("pid")
            or bootstrap_attestation.get("python_executable")
            != item.get("python_executable")
            or bootstrap_attestation.get("python_version") != item.get("python_version")
            or bootstrap_attestation.get("effective_sys_path") != item.get("sys_path")
        ):
            raise Stage001Error("worker_bootstrap_receipt_drift")
        modules = item.get("modules")
        if not isinstance(modules, Mapping) or dict(modules) != dict(expected_modules):
            raise Stage001Error("worker_module_receipt_drift")
        counters = _validate_counter_schema(item.get("sensitive_counters", {}))
        if any(counters.values()):
            raise Stage001Error("worker_sensitive_counter_nonzero")

        feature_path = Path(str(item.get("feature_path", ""))).resolve(strict=True)
        recorded_feature_path, _ = _assert_receipt_file_identity(
            item.get("event_feature_file"),
            label="event_feature",
        )
        if recorded_feature_path != feature_path:
            raise Stage001Error("worker_event_feature_path_mismatch")
        features = pd.read_csv(feature_path, float_precision="round_trip")
        event_count = int(item.get("event_count", 0))
        if event_count <= 0 or len(features) != event_count:
            raise Stage001Error("worker_event_count_mismatch")
        event_sha = str(item.get("event_feature_sha256", ""))
        if HEX64.fullmatch(event_sha) is None or _frame_sha256(features) != event_sha:
            raise Stage001Error("worker_event_feature_sha_mismatch")
        event_counts.add(event_count)
        event_shas.add(event_sha)

    if first.get("sys_path") != second.get("sys_path") or not isinstance(
        first.get("sys_path"), list
    ) or not first.get("sys_path"):
        raise Stage001Error("worker_sys_path_drift")
    if len(event_counts) != 1 or len(event_shas) != 1:
        raise Stage001Error("worker_event_receipt_drift")
    return {
        "passed": True,
        "worker_ids": ["A1", "A2"],
        "distinct_pid": True,
        "distinct_runtime_root": True,
        "distinct_tmpdir": True,
        "distinct_mplconfigdir": True,
        "distinct_home": True,
        "database_sha256": expected_database_sha256,
        "event_count": next(iter(event_counts)),
        "event_feature_sha256": next(iter(event_shas)),
        "checkpoint_reuse_count": 0,
        "baseline_replay_count_per_worker": 1,
        "network_connection_attempt_count": 0,
        "sandbox_policy_mode": SANDBOX_POLICY_MODE,
        "sensitive_guard_enforced": True,
    }


def execution_ledger_is_durable(campaign_nonce: str, lease_id: str) -> bool:
    try:
        with _execution_event_lock(EXECUTION_EVENT_PATH) as lock_descriptor:
            claim, _ = _read_current_execution_claim(
                EXECUTION_EVENT_PATH,
                lock_descriptor=lock_descriptor,
            )
            event, _, _ = _read_current_execution_event(
                EXECUTION_EVENT_PATH,
                lock_descriptor=lock_descriptor,
            )
            event_pattern = _execution_event_entry_pattern(
                EXECUTION_EVENT_PATH.name
            )
            ledger_names = [
                CLAIM_PATH.name,
                EXECUTION_EVENT_PATH.name,
                *sorted(
                    name
                    for name in os.listdir(lock_descriptor)
                    if event_pattern.fullmatch(name) is not None
                ),
            ]
            for name in ledger_names:
                item = os.stat(
                    name,
                    dir_fd=lock_descriptor,
                    follow_symlinks=False,
                )
                if not stat.S_ISREG(item.st_mode) or item.st_mode & 0o777 != 0o600:
                    return False
    except (OSError, Stage001Error):
        return False
    return bool(
        claim.get("campaign_nonce") == campaign_nonce
        and claim.get("lease_id") == lease_id
        and claim.get("replay_permitted") is False
        and event.get("campaign_nonce") == campaign_nonce
        and event.get("lease_id") == lease_id
        and event.get("status") == "running"
        and int(event.get("sequence", 0)) >= 2
    )


def _staging_binding(staging: Path) -> tuple[str, str]:
    prefix = f".{EXECUTION_STATE_DIR.name}."
    suffix = ".staging"
    name = staging.name
    if not name.startswith(prefix) or not name.endswith(suffix):
        raise Stage001Error("execution_state_staging_name_invalid")
    body = name[len(prefix) : -len(suffix)]
    parts = body.split(".")
    if (
        len(parts) != 2
        or HEX64.fullmatch(parts[0]) is None
        or HEX64.fullmatch(parts[1]) is None
    ):
        raise Stage001Error("execution_state_staging_binding_name_invalid")
    return parts[0], parts[1]


def _read_state_json(path: Path) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _claim_matches_binding(
    claim: Mapping[str, Any] | None,
    nonce: str,
    lease_id: str,
) -> bool:
    return bool(
        claim
        and claim.get("schema_version") == 1
        and claim.get("stage") == STAGE
        and claim.get("line_id") == LINE_ID
        and claim.get("campaign_nonce") == nonce
        and claim.get("lease_id") == lease_id
        and claim.get("replay_permitted") is False
    )


def _event_matches_binding(
    event: Mapping[str, Any] | None,
    nonce: str,
    lease_id: str,
) -> bool:
    if not event:
        return False
    try:
        _validate_counter_schema(event.get("counters", {}))
        sequence = int(event.get("sequence", 0))
    except (Stage001Error, TypeError, ValueError):
        return False
    return bool(
        event.get("schema_version") == 1
        and event.get("stage") == STAGE
        and event.get("line_id") == LINE_ID
        and event.get("campaign_nonce") == nonce
        and event.get("lease_id") == lease_id
        and event.get("status") in {"claimed", "running", "completed", "failed"}
        and sequence >= 1
    )


def _quarantine_state_file(path: Path) -> None:
    if not path.exists():
        return
    candidate = path.with_name(f"{path.name}.corrupt")
    index = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.corrupt.{index}")
        index += 1
    os.replace(path, candidate)
    os.chmod(candidate, 0o600)


def _create_recovered_claim(path: Path, nonce: str, lease_id: str) -> None:
    create_exclusive_json(
        path,
        {
            "schema_version": 1,
            "stage": STAGE,
            "line_id": LINE_ID,
            "campaign_nonce": nonce,
            "lease_id": lease_id,
            "replay_permitted": False,
            "recovered_from_incomplete_staging": True,
        },
    )


def _create_recovered_failure_event(path: Path, nonce: str, lease_id: str) -> None:
    now = _now()
    create_exclusive_json(
        path,
        {
            "schema_version": 1,
            "stage": STAGE,
            "line_id": LINE_ID,
            "campaign_nonce": nonce,
            "lease_id": lease_id,
            "status": "failed",
            "phase": "recovered_incomplete_execution_state_staging",
            "sequence": 1,
            "created_at": now,
            "updated_at": now,
            "counters": zero_sensitive_counters(),
            "error": "incomplete_execution_state_staging",
        },
    )


def _recover_execution_state_staging() -> bool:
    if EXECUTION_STATE_DIR.exists():
        return False
    pattern = f".{EXECUTION_STATE_DIR.name}.*.staging"
    candidates = sorted(EXECUTION_STATE_DIR.parent.glob(pattern))
    if not candidates:
        return False
    if len(candidates) != 1:
        raise Stage001Error("execution_state_staging_ambiguous")
    staging = candidates[0]
    nonce, lease_id = _staging_binding(staging)
    claim_path = staging / "claim.json"
    event_path = staging / "event.json"
    claim = _read_state_json(claim_path)
    event = _read_state_json(event_path)
    claim_valid = _claim_matches_binding(claim, nonce, lease_id)
    event_valid = _event_matches_binding(event, nonce, lease_id)
    if not claim_valid:
        _quarantine_state_file(claim_path)
        _create_recovered_claim(claim_path, nonce, lease_id)
    else:
        os.chmod(claim_path, 0o600)
    if not event_valid:
        _quarantine_state_file(event_path)
        _create_recovered_failure_event(event_path, nonce, lease_id)
    else:
        os.chmod(event_path, 0o600)
    _fsync_tree(staging)
    os.replace(staging, EXECUTION_STATE_DIR)
    _fsync_directory(EXECUTION_STATE_DIR.parent)
    return True


def reconcile_execution_state() -> dict[str, Any]:
    recovered_staging = _recover_execution_state_staging()
    if not EXECUTION_STATE_DIR.is_dir():
        return {"reconciled": False, "recovered_staging": recovered_staging}
    if not CLAIM_PATH.is_file() or not EXECUTION_EVENT_PATH.is_file():
        raise Stage001Error("execution_state_files_missing")
    with _execution_event_lock(EXECUTION_EVENT_PATH) as lock_descriptor:
        claim, _ = _read_current_execution_claim(
            EXECUTION_EVENT_PATH,
            lock_descriptor=lock_descriptor,
        )
        event, _, _ = _read_current_execution_event(
            EXECUTION_EVENT_PATH,
            lock_descriptor=lock_descriptor,
        )
    nonce = _require_hex64(claim.get("campaign_nonce"), "campaign_nonce")
    lease_id = _require_hex64(claim.get("lease_id"), "lease_id")
    if (
        event.get("campaign_nonce") != nonce
        or event.get("lease_id") != lease_id
        or claim.get("replay_permitted") is not False
    ):
        raise Stage001Error("execution_state_binding_invalid")
    counters = _validate_counter_schema(event.get("counters", {}))
    if FINAL_DIR.exists() and FAILURE_DIR.exists():
        raise Stage001Error("execution_terminal_conflict")
    if not FINAL_DIR.exists() and not FAILURE_DIR.exists():
        recovered_failure_counters = _recover_failure_bundle_staging(
            campaign_nonce=nonce,
            lease_id=lease_id,
            sensitive_counters=counters,
            event_phase=str(event.get("phase", "unknown")),
        )
        if recovered_failure_counters is not None:
            counters = monotonic_sensitive_counters(
                counters,
                recovered_failure_counters,
            )
    if FINAL_DIR.exists() and not FINAL_DIR.is_dir():
        raise Stage001Error("execution_success_terminal_not_directory")
    if FINAL_DIR.is_dir():
        if event.get("status") == "failed":
            raise Stage001Error("execution_terminal_state_conflict")
        evidence = _validate_success_bundle(
            FINAL_DIR,
            expected_claim=claim,
            revalidate_current_inputs=True,
            revalidate_current_authorization=True,
        )
        publishing_event = evidence["publishing_event"]
        current_success_status = _validate_current_success_event(
            event,
            publishing_event=publishing_event,
            root=FINAL_DIR,
        )
        if current_success_status == "running":
            cleanup = {
                "attempt_cleanup_completed": True,
                "attempt_cleanup_error": None,
            }
            attempt_path = Path(
                str(publishing_event["details"]["attempt_dir"])
            ).resolve(strict=False)
            if attempt_path.exists():
                try:
                    shutil.rmtree(attempt_path)
                    _fsync_directory(attempt_path.parent)
                except OSError as exc:
                    cleanup = {
                        "attempt_cleanup_completed": False,
                        "attempt_cleanup_error": f"{type(exc).__name__}:{exc}",
                    }
            _complete_success_publication(
                claim=claim,
                publishing_event=publishing_event,
                counters=counters,
                cleanup=cleanup,
            )
        return {
            "reconciled": current_success_status == "running" or recovered_staging,
            "recovered_staging": recovered_staging,
            "terminal": "completed",
        }
    if FAILURE_DIR.exists() and not FAILURE_DIR.is_dir():
        raise Stage001Error("execution_failure_terminal_not_directory")
    if FAILURE_DIR.is_dir():
        if event.get("status") == "completed":
            raise Stage001Error("execution_terminal_state_conflict")
        failure_receipt = _validate_failure_bundle(
            FAILURE_DIR,
            campaign_nonce=nonce,
            lease_id=lease_id,
        )
        merged_counters = monotonic_sensitive_counters(
            counters,
            failure_receipt["sensitive_counters"],
        )
        if event.get("status") != "failed" or merged_counters != counters:
            update_execution_event(
                EXECUTION_EVENT_PATH,
                campaign_nonce=nonce,
                lease_id=lease_id,
                status="failed",
                phase="recovered_published_failure",
                counters=merged_counters,
                error="recovered_existing_failure_bundle",
            )
        return {
            "reconciled": (
                event.get("status") != "failed"
                or recovered_staging
                or merged_counters != counters
            ),
            "recovered_staging": recovered_staging,
            "terminal": "failed",
        }

    error = Stage001Error(
        f"recovered_interrupted_execution:{event.get('phase', 'unknown')}"
    )
    _publish_failure_bundle(
        None,
        error=error,
        campaign_nonce=nonce,
        lease_id=lease_id,
        phase="recovered_interrupted_execution",
        input_before=None,
        sensitive_counters=counters,
    )
    update_execution_event(
        EXECUTION_EVENT_PATH,
        campaign_nonce=nonce,
        lease_id=lease_id,
        status="failed",
        phase="recovered_interrupted_execution",
        counters=counters,
        error=f"{type(error).__name__}:{error}",
    )
    return {
        "reconciled": True,
        "recovered_staging": recovered_staging,
        "terminal": "failed",
    }


def evaluate_stage001_gates(
    *,
    formal_identity_exact: bool,
    execution_identity_exact: bool,
    interval_exact: bool,
    worker_isolation: Mapping[str, Any],
    feature_qualification: Mapping[str, Any],
    worker_comparison: Mapping[str, Any],
    identity_stable: bool,
    eligibility_trace_exact: bool,
    fixed_fu_cutoff_excluded: bool,
    forbidden_output_columns_absent: bool,
    production_unchanged: bool,
    event_ledger_durable: bool,
    sensitive_counters: Mapping[str, Any],
) -> dict[str, Any]:
    counters = _validate_counter_schema(sensitive_counters)
    feature_gates = feature_qualification.get("gates")
    if not isinstance(feature_gates, Mapping):
        raise Stage001Error("feature_qualification_gates_missing")
    coverage_names = (
        "event_count_min",
        "full_year_coverage_min",
        "direction_coverage_min",
        "product_coverage_min",
    )
    root_names = (
        "event_identity_unique",
        "root_open_semantics",
        "fixed_fu_excluded",
    )
    feature_names = (
        "all_features_finite",
        "all_features_nonconstant",
        "high_cardinality_feature_count",
    )
    gates = {
        STAGE001_GATE_NAMES[0]: bool(formal_identity_exact),
        STAGE001_GATE_NAMES[1]: bool(execution_identity_exact),
        STAGE001_GATE_NAMES[2]: bool(interval_exact),
        STAGE001_GATE_NAMES[3]: worker_isolation.get("passed") is True,
        STAGE001_GATE_NAMES[4]: worker_comparison.get("passed") is True,
        STAGE001_GATE_NAMES[5]: all(feature_gates.get(name) is True for name in coverage_names),
        STAGE001_GATE_NAMES[6]: all(feature_gates.get(name) is True for name in root_names),
        STAGE001_GATE_NAMES[7]: bool(
            feature_qualification.get("passed") is True
            and all(feature_gates.get(name) is True for name in feature_names)
        ),
        STAGE001_GATE_NAMES[8]: bool(
            eligibility_trace_exact and fixed_fu_cutoff_excluded
        ),
        STAGE001_GATE_NAMES[9]: bool(forbidden_output_columns_absent),
        STAGE001_GATE_NAMES[10]: all(
            counters[key] == 0
            for key in (
                "label_value_read_count",
                "label_build_count",
                "model_fit_count",
                "prediction_count",
                "candidate_strategy_run_count",
                "holdout_read_count",
                "sensitive_module_import_count",
            )
        ),
        STAGE001_GATE_NAMES[11]: bool(production_unchanged)
        and all(
            counters[key] == 0
            for key in (
                "network_connection_count",
                "ctp_connection_count",
                "account_query_count",
                "order_api_called_count",
                "production_file_write_count",
                "subprocess_spawn_count",
            )
        ),
        STAGE001_GATE_NAMES[12]: bool(identity_stable and event_ledger_durable),
    }
    return {
        "passed": bool(all(gates.values())),
        "gates": gates,
        "sensitive_counters": counters,
    }


def _fsync_tree(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    for path in sorted(
        [item for item in root.rglob("*") if item.is_dir()],
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        _fsync_directory(path)
    _fsync_directory(root)


def atomic_publish_directory(source: Path, final: Path) -> None:
    if final.exists():
        raise Stage001Error(f"final_directory_exists:{final.resolve()}")
    if not source.is_dir():
        raise Stage001Error(f"publish_source_missing:{source}")
    if source.parent.resolve() != final.parent.resolve():
        raise Stage001Error("publish_requires_same_parent")
    _fsync_tree(source)
    os.replace(source, final)
    _fsync_directory(final.parent)


def _load_feature_module():
    spec = importlib.util.spec_from_file_location(
        "formal_signal_event_features_stage001",
        FEATURE_TOOL,
    )
    if spec is None or spec.loader is None:
        raise Stage001Error("feature_module_load_spec_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_directory(root: Path) -> Path:
    marker = root / ".git"
    if marker.is_dir():
        return marker.resolve()
    if not marker.is_file():
        raise Stage001Error(f"git_marker_missing:{root}")
    text = marker.read_text(encoding="utf-8").strip()
    prefix = "gitdir: "
    if not text.startswith(prefix):
        raise Stage001Error(f"git_marker_invalid:{marker}")
    value = Path(text[len(prefix) :])
    if not value.is_absolute():
        value = marker.parent / value
    return value.resolve(strict=True)


def _read_git_head_without_process(root: Path) -> str:
    git_dir = _git_directory(root)
    head_text = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if HEX40.fullmatch(head_text) is not None:
        return head_text
    prefix = "ref: "
    if not head_text.startswith(prefix):
        raise Stage001Error(f"git_head_invalid:{git_dir / 'HEAD'}")
    reference = head_text[len(prefix) :]
    direct = git_dir / reference
    if direct.is_file():
        return direct.read_text(encoding="utf-8").strip()
    common_dir = git_dir
    common_marker = git_dir / "commondir"
    if common_marker.is_file():
        common_value = Path(common_marker.read_text(encoding="utf-8").strip())
        common_dir = (
            common_value
            if common_value.is_absolute()
            else (git_dir / common_value).resolve(strict=True)
        )
    shared = common_dir / reference
    if shared.is_file():
        return shared.read_text(encoding="utf-8").strip()
    packed_refs = common_dir / "packed-refs"
    if packed_refs.is_file():
        for line in packed_refs.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith(("#", "^")):
                continue
            digest, name = line.split(" ", 1)
            if name == reference:
                return digest
    raise Stage001Error(f"git_reference_missing:{reference}")


def repository_state() -> dict[str, Any]:
    production_head = _read_git_head_without_process(PRODUCTION_ROOT)
    if production_head != EXPECTED_PRODUCTION_HEAD:
        raise Stage001Error(f"production_head_drift:{production_head}")
    return {
        "production_head": production_head,
        "repository_discovery": "direct_git_metadata_no_process",
        "production_inputs_individually_bound": True,
        "workspace_vnpy_inputs_individually_bound": True,
    }


def _import_production_context() -> dict[str, Any]:
    production_path = str(PORTFOLIO_DIR.resolve())
    if production_path not in sys.path:
        sys.path.insert(0, production_path)
    guard_key = "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"
    previous_guard = os.environ.get(guard_key)
    os.environ[guard_key] = "1"
    try:
        s901 = importlib.import_module(
            "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow"
        )
        live_config = importlib.import_module("qmt_roll_official_live_config")
        contract_metadata = importlib.import_module("contract_metadata")
        portfolio_package = importlib.import_module("vnpy_portfoliostrategy")
    finally:
        if previous_guard is None:
            os.environ.pop(guard_key, None)
        else:
            os.environ[guard_key] = previous_guard
    return {
        "s901": s901,
        "live_config": live_config,
        "contract_metadata": contract_metadata,
        "portfolio_package": portfolio_package,
    }


CORRELATION_TRACE_FIELDS = (
    "same_direction_correlation_candidate_return_count",
    "same_direction_correlation_min_required_count",
    "same_direction_correlation_candidate_history_available",
    "same_direction_correlation_active_count_recomputed",
    "same_direction_correlation_corr_count_recomputed",
    "same_direction_correlation_max_corr_recomputed",
    "same_direction_correlation_trace_exact",
)


def _independent_correlation_trace(
    strategy: Any,
    *,
    contract_vt_symbol: str,
    direction: str,
    history: pd.DataFrame,
    entry_context: str,
    original_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    enabled = int(
        bool(strategy.enable_same_direction_correlation_gate)
        and entry_context == "flat_entry"
    )
    lookback = max(5, int(strategy.same_direction_correlation_gate_lookback or 20))
    min_required = max(5, lookback // 2)
    candidate_returns = strategy._history_return_vector(history, lookback)
    candidate_count = int(len(candidate_returns))
    candidate_available = int(enabled == 1 and candidate_count >= min_required)

    active_symbols: list[str] = []
    corr_values: list[float] = []
    for state in strategy.states.values():
        active_contract = str(getattr(state, "contract_vt_symbol", "") or "")
        if not active_contract or active_contract == contract_vt_symbol:
            continue
        if str(getattr(state, "direction", "")) != direction:
            continue
        if strategy.get_pos(active_contract) == 0:
            continue
        active_symbols.append(active_contract)
        if not candidate_available:
            continue
        active_am = strategy.ams.get(active_contract)
        if active_am is None or not active_am.inited:
            continue
        active_history = strategy._build_history_df(active_am)
        active_returns = strategy._history_return_vector(active_history, lookback)
        pair_length = min(candidate_count, len(active_returns))
        if pair_length < min_required:
            continue
        corr_matrix = np.corrcoef(
            candidate_returns[-pair_length:],
            active_returns[-pair_length:],
        )
        corr_value = float(corr_matrix[0, 1])
        if math.isfinite(corr_value):
            corr_values.append(corr_value)

    recomputed_max = max(corr_values) if corr_values else 0.0
    source_active = int(
        original_snapshot.get("same_direction_correlation_active_count", -1)
    )
    source_count = int(
        original_snapshot.get("same_direction_correlation_corr_count", -1)
    )
    source_max = float(
        original_snapshot.get("same_direction_correlation_max_corr", math.nan)
    )
    trace_exact = int(
        int(original_snapshot.get("same_direction_correlation_gate_enabled", -1))
        == enabled
        and candidate_available == 1
        and source_active == len(active_symbols)
        and source_count == len(corr_values)
        and math.isfinite(source_max)
        and math.isclose(source_max, recomputed_max, rel_tol=0.0, abs_tol=1e-12)
    )
    return {
        "same_direction_correlation_candidate_return_count": candidate_count,
        "same_direction_correlation_min_required_count": min_required,
        "same_direction_correlation_candidate_history_available": candidate_available,
        "same_direction_correlation_active_count_recomputed": len(active_symbols),
        "same_direction_correlation_corr_count_recomputed": len(corr_values),
        "same_direction_correlation_max_corr_recomputed": recomputed_max,
        "same_direction_correlation_trace_exact": trace_exact,
    }


def _install_correlation_trace_instrumentation(strategy_class: type[Any]):
    snapshot_name = "_same_direction_correlation_gate_snapshot"
    record_name = "_record_entry_candidate_snapshot"
    original_snapshot = getattr(strategy_class, snapshot_name)
    original_record = getattr(strategy_class, record_name)
    local_snapshot = strategy_class.__dict__.get(snapshot_name)
    local_record = strategy_class.__dict__.get(record_name)

    def traced_snapshot(self: Any, **kwargs: Any) -> dict[str, Any]:
        snapshot = dict(original_snapshot(self, **kwargs))
        snapshot.update(
            _independent_correlation_trace(
                self,
                contract_vt_symbol=str(kwargs["contract_vt_symbol"]),
                direction=str(kwargs["direction"]),
                history=kwargs["history"],
                entry_context=str(kwargs["entry_context"]),
                original_snapshot=snapshot,
            )
        )
        return snapshot

    def traced_record(self: Any, **kwargs: Any) -> Any:
        before = len(self.entry_candidate_snapshots)
        result = original_record(self, **kwargs)
        if len(self.entry_candidate_snapshots) != before + 1:
            raise Stage001Error("correlation_trace_candidate_record_count_drift")
        sizing = kwargs.get("sizing_snapshot")
        if not isinstance(sizing, Mapping):
            raise Stage001Error("correlation_trace_sizing_snapshot_missing")
        missing = [field for field in CORRELATION_TRACE_FIELDS if field not in sizing]
        if missing:
            raise Stage001Error(
                f"correlation_trace_fields_missing:{','.join(missing)}"
            )
        row = self.entry_candidate_snapshots[-1]
        for field in CORRELATION_TRACE_FIELDS:
            row[field] = sizing[field]
        return result

    setattr(strategy_class, snapshot_name, traced_snapshot)
    setattr(strategy_class, record_name, traced_record)

    def restore() -> None:
        if local_snapshot is None:
            delattr(strategy_class, snapshot_name)
        else:
            setattr(strategy_class, snapshot_name, local_snapshot)
        if local_record is None:
            delattr(strategy_class, record_name)
        else:
            setattr(strategy_class, record_name, local_record)

    return restore


def _active_formal_identity() -> dict[str, Any]:
    current = json.loads(FORMAL_CURRENT.read_text(encoding="utf-8"))
    observed = {
        "formal_release_id": str(current.get("release_id", "")),
        "formal_strategy": str(current.get("strategy_version", "")),
        "official_live_version": EXPECTED_OFFICIAL_VERSION,
        "formal_material_manifest_sha256": str(current.get("manifest_sha256", "")),
        "capital": EXPECTED_CAPITAL,
    }
    expected = {
        "formal_release_id": EXPECTED_RELEASE_ID,
        "formal_strategy": EXPECTED_FORMAL_STRATEGY,
        "official_live_version": EXPECTED_OFFICIAL_VERSION,
        "formal_material_manifest_sha256": EXPECTED_FORMAL_MANIFEST_SHA256,
        "capital": EXPECTED_CAPITAL,
    }
    if observed != expected:
        raise Stage001Error(f"formal_identity_drift:{observed}")
    release = FORMAL_RELEASE
    manifest = release / "manifest.json"
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    if manifest_payload.get("manifest_sha256") != EXPECTED_FORMAL_MANIFEST_SHA256:
        raise Stage001Error("formal_manifest_identity_mismatch")
    if manifest_payload.get("release_id") != EXPECTED_RELEASE_ID:
        raise Stage001Error("formal_manifest_release_id_mismatch")
    if manifest_payload.get("strategy_version") != EXPECTED_FORMAL_STRATEGY:
        raise Stage001Error("formal_manifest_strategy_mismatch")
    eligibility = FORMAL_ELIGIBILITY.resolve(strict=True)
    if release.resolve() not in eligibility.parents:
        raise Stage001Error("formal_eligibility_outside_active_release")
    observed["release_path"] = str(release.resolve())
    observed["manifest_file_sha256"] = _sha256(manifest)
    observed["eligibility_path"] = str(eligibility)
    observed["eligibility_sha256"] = _sha256(eligibility)
    return observed


def _add_tree_files(
    files: dict[str, Path],
    *,
    prefix: str,
    root: Path,
    suffixes: set[str] | None,
) -> None:
    if not root.is_dir():
        raise Stage001Error(f"identity_tree_missing:{prefix}:{root}")
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if suffixes is not None and path.suffix not in suffixes:
            continue
        files[f"{prefix}/{path.relative_to(root).as_posix()}"] = path


def _startup_hook_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for index, root_value in enumerate(site.getsitepackages()):
        root = Path(root_value).resolve()
        for path in sorted(root.glob("*.pth")):
            files[f"python_site_pth/{index}/{path.name}"] = path
    pyvenv = Path(sys.prefix) / "pyvenv.cfg"
    if pyvenv.is_file():
        files["python_pyvenv_cfg"] = pyvenv
    return files


def collect_input_files() -> dict[str, Path]:
    formal = _active_formal_identity()
    files: dict[str, Path] = {
        "source_database": SOURCE_DATABASE,
        "sandbox_executable": SANDBOX_EXECUTABLE,
        "full_minute_bars": FULL_MINUTE_BARS,
        "main_contract_mapping": MAIN_CONTRACT_MAPPING,
        "contract_metadata": CONTRACT_METADATA,
        "product_universe": PRODUCT_UNIVERSE,
        "formal_current": FORMAL_CURRENT,
        "formal_eligibility": Path(formal["eligibility_path"]),
        "stage001_runner": Path(__file__).resolve(),
        "stage001_worker_bootstrap": WORKER_BOOTSTRAP,
        "stage001_feature_tool": FEATURE_TOOL,
        "stage001_preregistration": PREREGISTRATION,
        "stage001_pre_ai_boundary_remediation": PRE_AI_BOUNDARY_REMEDIATION,
        "stage001_plan": PLAN,
        "stage001_feature_tests": FEATURE_TEST,
        "stage001_runner_tests": RUNNER_TEST,
        "python_executable": Path(sys.executable).resolve(),
    }
    files.update(_startup_hook_files())
    _add_tree_files(
        files,
        prefix="production_portfolio",
        root=PORTFOLIO_DIR,
        suffixes={".py"},
    )
    _add_tree_files(
        files,
        prefix="formal_release",
        root=Path(formal["release_path"]),
        suffixes=None,
    )
    _add_tree_files(
        files,
        prefix="workspace_vnpy_core",
        root=WORKSPACE_ROOT / "vnpy",
        suffixes={".py"},
    )
    _add_tree_files(
        files,
        prefix="vnpy_portfoliostrategy",
        root=PORTFOLIO_PACKAGE_ROOT,
        suffixes={".py", ".so", ".dylib"},
    )
    for name, path in files.items():
        if not path.is_file():
            raise Stage001Error(f"identity_input_missing:{name}:{path}")
    validate_input_inventory(files)
    return files


def logical_key_contract_sha256(files: Mapping[str, Path]) -> str:
    return hashlib.sha256(
        _stable_json_bytes(sorted(str(name) for name in files))
    ).hexdigest()


def validate_input_inventory(files: Mapping[str, Path]) -> None:
    if len(files) != EXPECTED_INPUT_FILE_COUNT:
        raise Stage001Error(
            f"input_inventory_count_mismatch:{len(files)}:{EXPECTED_INPUT_FILE_COUNT}"
        )
    observed = logical_key_contract_sha256(files)
    if observed != EXPECTED_INPUT_LOGICAL_KEY_SHA256:
        raise Stage001Error(
            "input_inventory_logical_key_contract_mismatch:"
            f"{observed}:{EXPECTED_INPUT_LOGICAL_KEY_SHA256}"
        )


def file_contract_payload(files: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    required = ("path", "size", "mtime_ns", "sha256")
    result: dict[str, Any] = {}
    for name, value in sorted(files.items()):
        if not isinstance(value, Mapping) or any(field not in value for field in required):
            raise Stage001Error(f"input_identity_item_invalid:{name}")
        result[str(name)] = {field: value[field] for field in required}
    return result


def expected_worker_modules(input_manifest: Mapping[str, Any]) -> dict[str, str]:
    files = input_manifest.get("files")
    if not isinstance(files, Mapping):
        raise Stage001Error("input_manifest_files_missing")
    result: dict[str, str] = {}
    for module_name, file_key in WORKER_MODULE_FILE_KEYS.items():
        identity = files.get(file_key)
        if not isinstance(identity, Mapping) or not str(identity.get("path", "")):
            raise Stage001Error(f"worker_module_input_missing:{module_name}:{file_key}")
        result[module_name] = str(Path(str(identity["path"])).resolve())
    return result


def _runtime_contract() -> dict[str, Any]:
    uname = os.uname()
    return {
        "python_version": sys.version,
        "python_implementation": sys.implementation.name,
        "python_executable": str(Path(sys.executable).resolve()),
        "platform": {
            "os_name": os.name,
            "sys_platform": sys.platform,
            "sysname": uname.sysname,
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
        },
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "repository": repository_state(),
    }


def build_input_manifest(*, enforce_network_block: bool = True) -> dict[str, Any]:
    if enforce_network_block:
        with _NetworkBlock() as network:
            manifest = build_input_manifest(enforce_network_block=False)
        if network.attempts:
            raise Stage001Error("input_manifest_network_attempt_detected")
        return manifest
    files = {
        name: _file_identity(path)
        for name, path in sorted(collect_input_files().items())
    }
    file_contract = file_contract_payload(files)
    runtime = _runtime_contract()
    return {
        "schema_version": 1,
        "stage": STAGE,
        "created_at": _now(),
        "formal_identity": _active_formal_identity(),
        "files": files,
        "input_file_count": len(files),
        "input_logical_key_sha256": logical_key_contract_sha256(files),
        "file_contract_sha256": hashlib.sha256(
            _stable_json_bytes(file_contract)
        ).hexdigest(),
        "runtime": runtime,
        "runtime_contract_sha256": hashlib.sha256(
            _stable_json_bytes(runtime)
        ).hexdigest(),
    }


def _validate_input_manifest_payload(
    manifest: Mapping[str, Any],
    *,
    label: str,
    require_frozen_count: bool,
) -> dict[str, Any]:
    if set(manifest) != INPUT_MANIFEST_FIELDS:
        raise Stage001Error(f"{label}_schema_invalid")
    if manifest.get("schema_version") != 1 or manifest.get("stage") != STAGE:
        raise Stage001Error(f"{label}_identity_invalid")
    try:
        _receipt_timestamp(manifest.get("created_at"), f"{label}_created_at")
    except Stage001Error as exc:
        raise Stage001Error(f"{label}_timestamp_invalid") from exc

    formal = manifest.get("formal_identity")
    if not isinstance(formal, Mapping) or set(formal) != FORMAL_IDENTITY_FIELDS:
        raise Stage001Error(f"{label}_formal_identity_schema_invalid")
    if (
        formal.get("formal_release_id") != EXPECTED_RELEASE_ID
        or formal.get("formal_strategy") != EXPECTED_FORMAL_STRATEGY
        or formal.get("official_live_version") != EXPECTED_OFFICIAL_VERSION
        or formal.get("formal_material_manifest_sha256")
        != EXPECTED_FORMAL_MANIFEST_SHA256
        or float(formal.get("capital", -1.0)) != EXPECTED_CAPITAL
        or not Path(str(formal.get("release_path", ""))).is_absolute()
        or not Path(str(formal.get("eligibility_path", ""))).is_absolute()
        or HEX64.fullmatch(str(formal.get("manifest_file_sha256", ""))) is None
        or HEX64.fullmatch(str(formal.get("eligibility_sha256", ""))) is None
    ):
        raise Stage001Error(f"{label}_formal_identity_invalid")

    files = manifest.get("files")
    if not isinstance(files, Mapping) or not files:
        raise Stage001Error(f"{label}_files_invalid")
    for name, identity in files.items():
        if (
            not str(name)
            or not isinstance(identity, Mapping)
            or set(identity) != FILE_IDENTITY_FIELDS
            or not Path(str(identity.get("path", ""))).is_absolute()
            or isinstance(identity.get("size"), bool)
            or int(identity.get("size", -1)) < 0
            or isinstance(identity.get("mtime_ns"), bool)
            or int(identity.get("mtime_ns", -1)) < 0
            or HEX64.fullmatch(str(identity.get("sha256", ""))) is None
        ):
            raise Stage001Error(f"{label}_file_identity_invalid:{name}")
    input_count = int(manifest.get("input_file_count", -1))
    logical_sha = logical_key_contract_sha256(files)
    file_contract_sha = hashlib.sha256(
        _stable_json_bytes(file_contract_payload(files))
    ).hexdigest()
    if (
        input_count != len(files)
        or manifest.get("input_logical_key_sha256") != logical_sha
        or manifest.get("file_contract_sha256") != file_contract_sha
    ):
        raise Stage001Error(f"{label}_file_contract_invalid")
    if require_frozen_count and (
        input_count != EXPECTED_INPUT_FILE_COUNT
        or logical_sha != EXPECTED_INPUT_LOGICAL_KEY_SHA256
    ):
        raise Stage001Error(f"{label}_frozen_inventory_invalid")

    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping) or not runtime:
        raise Stage001Error(f"{label}_runtime_invalid")
    runtime_sha = hashlib.sha256(_stable_json_bytes(runtime)).hexdigest()
    if manifest.get("runtime_contract_sha256") != runtime_sha:
        raise Stage001Error(f"{label}_runtime_contract_invalid")
    return dict(manifest)


def _assert_current_input_manifest_matches(recorded: Mapping[str, Any]) -> None:
    _validate_input_manifest_payload(
        recorded,
        label="success_recorded_input",
        require_frozen_count=True,
    )
    current = build_input_manifest()
    _validate_input_manifest_payload(
        current,
        label="success_current_input",
        require_frozen_count=True,
    )
    try:
        assert_identity_stable(recorded, current)
    except Stage001Error as exc:
        raise Stage001Error("success_current_input_identity_drift") from exc
    if (
        recorded.get("input_file_count") != current.get("input_file_count")
        or recorded.get("input_logical_key_sha256")
        != current.get("input_logical_key_sha256")
    ):
        raise Stage001Error("success_current_input_identity_drift")


def authorization_bound_files() -> dict[str, Path]:
    return {
        "line": LINE_ROOT / "LINE.md",
        "preregistration": PREREGISTRATION,
        "pre_ai_boundary_remediation": PRE_AI_BOUNDARY_REMEDIATION,
        "prerun_blocker_remediation": PRERUN_BLOCKER_REMEDIATION,
        "second_prerun_blocker_remediation": SECOND_PRERUN_BLOCKER_REMEDIATION,
        "third_prerun_blocker_remediation": THIRD_PRERUN_BLOCKER_REMEDIATION,
        "fourth_prerun_blocker_remediation": FOURTH_PRERUN_BLOCKER_REMEDIATION,
        "fourth_prerun_review": FOURTH_PRERUN_REVIEW,
        "fourth_prerun_decision": FOURTH_PRERUN_DECISION,
        "fifth_prerun_blocker_remediation": FIFTH_PRERUN_BLOCKER_REMEDIATION,
        "fifth_prerun_review": FIFTH_PRERUN_REVIEW,
        "fifth_prerun_decision": FIFTH_PRERUN_DECISION,
        "sixth_prerun_blocker_remediation": SIXTH_PRERUN_BLOCKER_REMEDIATION,
        "sixth_prerun_review": SIXTH_PRERUN_REVIEW,
        "sixth_prerun_decision": SIXTH_PRERUN_DECISION,
        "seventh_prerun_blocker_remediation": SEVENTH_PRERUN_BLOCKER_REMEDIATION,
        "seventh_prerun_review": SEVENTH_PRERUN_REVIEW,
        "seventh_prerun_decision": SEVENTH_PRERUN_DECISION,
        "eighth_prerun_blocker_remediation": EIGHTH_PRERUN_BLOCKER_REMEDIATION,
        "eighth_prerun_review": EIGHTH_PRERUN_REVIEW,
        "eighth_prerun_decision": EIGHTH_PRERUN_DECISION,
        "ninth_prerun_blocker_remediation": NINTH_PRERUN_BLOCKER_REMEDIATION,
        "ninth_prerun_review": NINTH_PRERUN_REVIEW,
        "ninth_prerun_decision": NINTH_PRERUN_DECISION,
        "tenth_prerun_blocker_remediation": TENTH_PRERUN_BLOCKER_REMEDIATION,
        "tenth_prerun_review": TENTH_PRERUN_REVIEW,
        "tenth_prerun_decision": TENTH_PRERUN_DECISION,
        "plan": PLAN,
        "feature_tool": FEATURE_TOOL,
        "runner": Path(__file__).resolve(),
        "worker_bootstrap": WORKER_BOOTSTRAP,
        "feature_tests": FEATURE_TEST,
        "runner_tests": RUNNER_TEST,
        "prerun_review": PRERUN_REVIEW,
        "prerun_decision": PRERUN_DECISION,
    }


def validate_prerun_decision() -> dict[str, Any]:
    decision = json.loads(PRERUN_DECISION.read_text(encoding="utf-8"))
    if decision.get("decision") != REQUIRED_REVIEW_DECISION:
        raise Stage001Error("prerun_review_decision_not_allowed")
    if decision.get("allowed") is not True:
        raise Stage001Error("prerun_review_not_allowed")
    severities = decision.get("severity_counts")
    if not isinstance(severities, Mapping):
        raise Stage001Error("prerun_review_severity_counts_missing")
    for key in ("P0", "P1", "P2"):
        if int(severities.get(key, -1)) != 0:
            raise Stage001Error(f"prerun_review_{key.lower()}_not_zero")
    return decision


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_deterministic_gzip_csv(path: Path, frame: pd.DataFrame) -> None:
    data = frame.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    ).encode("utf-8")
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
            stream.write(data)


def _prepare_worker_runtime(
    worker_dir: Path,
    *,
    expected_database_sha256: str,
) -> Path:
    runtime = worker_dir / "runtime"
    trader = runtime / ".vntrader"
    trader.mkdir(parents=True, exist_ok=False, mode=0o700)
    target_database = trader / "database.db"
    shutil.copy2(SOURCE_DATABASE, target_database)
    os.chmod(target_database, 0o600)
    if _sha256(target_database) != expected_database_sha256:
        raise Stage001Error("worker_database_copy_sha_mismatch")
    # The historical replay consumes only local files. An empty setting prevents
    # data-feed credentials from entering the isolated worker runtime.
    setting = trader / "vt_setting.json"
    setting.write_text("{}\n", encoding="utf-8")
    os.chmod(setting, 0o600)
    return runtime


def _worker_runtime_receipt(
    worker_id: str,
    runtime_root: Path,
    *,
    source_contract_sha256: str,
    campaign_nonce: str,
    lease_id: str,
    worker_capability: Mapping[str, Any],
    capability_payload: Mapping[str, Any],
    bootstrap_attestation: Mapping[str, Any],
) -> dict[str, Any]:
    sandbox_profile = Path(
        str(capability_payload["sandbox_profile_path"])
    ).resolve(strict=True)
    if _sha256(sandbox_profile) != capability_payload.get("sandbox_profile_sha256"):
        raise Stage001Error("worker_sandbox_profile_capability_drift")
    return {
        "worker_id": worker_id,
        "campaign_nonce": campaign_nonce,
        "lease_id": lease_id,
        "pid": os.getpid(),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": sys.version,
        "cwd": str(Path.cwd().resolve()),
        "runtime_root": str(runtime_root.resolve()),
        "database": _file_identity(runtime_root / ".vntrader/database.db"),
        "setting": _file_identity(runtime_root / ".vntrader/vt_setting.json"),
        "tmpdir": os.environ.get("TMPDIR", ""),
        "mplconfigdir": os.environ.get("MPLCONFIGDIR", ""),
        "home": os.environ.get("HOME", ""),
        "sys_path": list(sys.path),
        "source_file_contract_sha256": source_contract_sha256,
        "checkpoint_reuse_count": 0,
        "sensitive_counters": zero_sensitive_counters(),
        "sandbox_enforced": bootstrap_attestation.get("sandbox_probe", {}).get(
            "write_denied"
        )
        is True,
        "sandbox_policy_mode": capability_payload["sandbox_policy_mode"],
        "sandbox_launch_executable": capability_payload["sandbox_executable_path"],
        "sandbox_profile": _file_identity(sandbox_profile),
        "worker_capability": dict(worker_capability),
        "bootstrap_attestation": dict(bootstrap_attestation),
        "sensitive_guard_enforced": False,
    }


class _NetworkBlock:
    def __init__(self) -> None:
        self.attempts = 0
        self._originals: dict[str, Any] = {}

    def __enter__(self) -> "_NetworkBlock":
        self._originals = {
            "connect": socket.socket.connect,
            "connect_ex": socket.socket.connect_ex,
            "create_connection": socket.create_connection,
            "getaddrinfo": socket.getaddrinfo,
            "gethostbyname": socket.gethostbyname,
            "gethostbyname_ex": socket.gethostbyname_ex,
            "gethostbyaddr": socket.gethostbyaddr,
        }
        owner = self

        def blocked_connect(*_args: Any, **_kwargs: Any) -> None:
            owner.attempts += 1
            raise NetworkBlockedError("worker_network_connection_forbidden")

        socket.socket.connect = blocked_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = blocked_connect  # type: ignore[method-assign]
        socket.create_connection = blocked_connect
        socket.getaddrinfo = blocked_connect
        socket.gethostbyname = blocked_connect
        socket.gethostbyname_ex = blocked_connect
        socket.gethostbyaddr = blocked_connect
        return self

    def __exit__(self, *_args: Any) -> None:
        socket.socket.connect = self._originals["connect"]  # type: ignore[method-assign]
        socket.socket.connect_ex = self._originals["connect_ex"]  # type: ignore[method-assign]
        socket.create_connection = self._originals["create_connection"]
        socket.getaddrinfo = self._originals["getaddrinfo"]
        socket.gethostbyname = self._originals["gethostbyname"]
        socket.gethostbyname_ex = self._originals["gethostbyname_ex"]
        socket.gethostbyaddr = self._originals["gethostbyaddr"]


def _sandbox_profile_text(worker_root: Path) -> str:
    allowed = json.dumps(str(worker_root.resolve()), ensure_ascii=True)
    return "\n".join(
        (
            "(version 1)",
            "(deny default)",
            "(allow process-exec)",
            "(deny process-fork)",
            "(allow sysctl-read)",
            "(allow mach-lookup)",
            "(allow file-read*)",
            f"(allow file-write* (subpath {allowed}))",
            '(allow file-write* (literal "/dev/null"))',
            "(deny network*)",
            "",
        )
    )


def write_worker_sandbox_profile(worker_root: Path) -> Path:
    root = worker_root.resolve(strict=True)
    profile = root / "stage001.sb"
    payload = _sandbox_profile_text(root).encode("utf-8")
    descriptor = os.open(profile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _write_all(descriptor, payload)
        os.fsync(descriptor)
    except BaseException:
        profile.unlink(missing_ok=True)
        raise
    finally:
        os.close(descriptor)
    _fsync_directory(root)
    return profile


def sandboxed_command(profile: Path, command: Iterable[str]) -> list[str]:
    profile = profile.resolve(strict=True)
    if not SANDBOX_EXECUTABLE.is_file():
        raise Stage001Error(f"sandbox_executable_missing:{SANDBOX_EXECUTABLE}")
    arguments = [str(value) for value in command]
    if not arguments:
        raise Stage001Error("sandbox_command_empty")
    return [str(SANDBOX_EXECUTABLE), "-f", str(profile), *arguments]


def isolated_startup_sys_path() -> list[str]:
    prefix = Path(sys.prefix).resolve()
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return [
        str(prefix / "lib" / f"python{sys.version_info.major}{sys.version_info.minor}.zip"),
        str(prefix / "lib" / version),
        str(prefix / "lib" / version / "lib-dynload"),
    ]


def approved_worker_sys_path() -> list[str]:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    paths = [
        Path(sys.prefix).resolve() / "lib" / version / "site-packages",
        WORKSPACE_ROOT.resolve(),
    ]
    resolved = [str(path.resolve(strict=True)) for path in paths]
    if len(set(resolved)) != len(resolved):
        raise Stage001Error("worker_approved_sys_path_duplicate")
    return resolved


def worker_bootstrap_command(
    worker_id: str,
    *,
    runtime_root: Path,
    output_dir: Path,
    input_manifest_path: Path,
    capability_path: Path,
) -> list[str]:
    if worker_id not in {"A1", "A2"}:
        raise Stage001Error(f"worker_id_invalid:{worker_id}")
    return [
        str(Path(sys.executable).resolve()),
        "-I",
        "-S",
        "-B",
        str(WORKER_BOOTSTRAP.resolve(strict=True)),
        "--worker",
        worker_id,
        "--runtime-root",
        str(runtime_root.resolve(strict=True)),
        "--worker-output",
        str(output_dir.resolve(strict=False)),
        "--expected-manifest",
        str(input_manifest_path.resolve(strict=True)),
        "--worker-capability",
        str(capability_path.resolve(strict=True)),
    ]


def _sensitive_python_call_counter(
    module_name: str,
    function_name: str,
) -> str | None:
    module_lower = module_name.lower()
    function_lower = function_name.lower()
    if module_lower.startswith(("sklearn", "xgboost", "lightgbm", "catboost")):
        if function_lower == "fit" or function_lower.endswith("_fit"):
            return "model_fit_count"
        if function_lower in {"predict", "predict_proba", "inplace_predict"}:
            return "prediction_count"
    if "ctp" in module_lower or "gateway" in module_lower:
        if function_lower in {
            "send_order",
            "cancel_order",
            "reqorderinsert",
            "reqorderaction",
        }:
            return "order_api_called_count"
        if function_lower in {
            "query_account",
            "query_position",
            "reqqrytradingaccount",
            "reqqryinvestorposition",
        }:
            return "account_query_count"
        if function_lower in {"connect", "reconnect", "reqauthenticate", "requserlogin"}:
            return "ctp_connection_count"
    if "label" in function_lower and function_lower.startswith(("build", "make", "create")):
        return "label_build_count"
    if module_lower.startswith(("train_qmt_roll_ai", "validate_qmt_roll_ai")):
        return "candidate_strategy_run_count"
    return None


class _SensitiveOperationGuard:
    _forbidden_import_prefixes = (
        "xgboost",
        "sklearn",
        "lightgbm",
        "catboost",
        "vnpy_ctp",
        "vnpy.gateway.ctp",
    )
    _label_data_suffixes = {
        ".csv",
        ".json",
        ".parquet",
        ".feather",
        ".pkl",
        ".pickle",
    }
    _os_process_entrypoints = (
        "system",
        "popen",
        "posix_spawn",
        "posix_spawnp",
        "fork",
        "forkpty",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
    )

    def __init__(self, allowed_write_roots: Iterable[Path]) -> None:
        self.allowed_write_roots = tuple(
            Path(path).resolve() for path in allowed_write_roots
        )
        if not self.allowed_write_roots:
            raise Stage001Error("sensitive_guard_allowed_write_roots_empty")
        self.counters = zero_sensitive_counters()
        self._original_import: Any = None
        self._original_builtin_open: Any = None
        self._original_io_open: Any = None
        self._original_popen: Any = None
        self._original_os_process_functions: dict[str, Any] = {}
        self._original_fork_exec: Any = None
        self._previous_profile: Any = None
        self._previous_thread_profile: Any = None
        self._active = False
        self._blocking = False

    def _block(self, counter: str, reason: str) -> None:
        if not self._blocking:
            self._blocking = True
            self.counters[counter] += 1
        raise SensitiveOperationBlockedError(f"sensitive_operation_forbidden:{reason}")

    @staticmethod
    def _resolve_path(value: Any) -> Path | None:
        if isinstance(value, int):
            return None
        try:
            path = Path(os.fsdecode(value)).expanduser()
        except (TypeError, ValueError):
            return None
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve(strict=False)

    def _check_open(self, file: Any, mode: str) -> None:
        path = self._resolve_path(file)
        if path is None:
            return
        write_mode = any(token in str(mode) for token in ("w", "a", "x", "+"))
        if write_mode:
            allowed = any(
                path == root or root in path.parents for root in self.allowed_write_roots
            )
            if not allowed:
                self._block("production_file_write_count", f"file_write:{path}")
            return
        lower_name = path.name.lower()
        if path.suffix.lower() not in self._label_data_suffixes:
            return
        if "holdout" in lower_name:
            self._block("holdout_read_count", f"holdout_read:{path}")
        if any(token in lower_name for token in ("label", "outcome", "target")):
            self._block("label_value_read_count", f"label_read:{path}")

    def _guarded_builtin_open(self, file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        self._check_open(file, mode)
        return self._original_builtin_open(file, mode, *args, **kwargs)

    def _guarded_io_open(self, file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        self._check_open(file, mode)
        return self._original_io_open(file, mode, *args, **kwargs)

    def _guarded_import(
        self,
        name: str,
        globals: Mapping[str, Any] | None = None,
        locals: Mapping[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        lowered = str(name).lower()
        if lowered.startswith(self._forbidden_import_prefixes) or lowered.startswith(
            ("train_qmt_roll_ai", "validate_qmt_roll_ai")
        ):
            self._block("sensitive_module_import_count", f"import:{name}")
        return self._original_import(name, globals, locals, fromlist, level)

    def _guarded_popen(self, *_args: Any, **_kwargs: Any) -> Any:
        self._block("subprocess_spawn_count", "subprocess")

    def _guarded_process_entrypoint(self, *_args: Any, **_kwargs: Any) -> Any:
        self._block("subprocess_spawn_count", "subprocess")

    def _profile(self, frame: Any, event: str, argument: Any) -> None:
        if self._blocking:
            return
        module_name = ""
        function_name = ""
        if event == "call":
            module_name = str(frame.f_globals.get("__name__", ""))
            function_name = str(frame.f_code.co_name)
        elif event == "c_call":
            module_name = str(getattr(argument, "__module__", ""))
            function_name = str(getattr(argument, "__name__", ""))
        else:
            return
        counter = _sensitive_python_call_counter(module_name, function_name)
        if counter is not None:
            self._block(counter, f"call:{module_name}.{function_name}")

    def assert_no_sensitive_modules_loaded(self) -> None:
        loaded = sorted(
            name
            for name in sys.modules
            if str(name).lower().startswith(self._forbidden_import_prefixes)
        )
        if loaded:
            self._block(
                "sensitive_module_import_count",
                f"preloaded:{','.join(loaded[:5])}",
            )

    def __enter__(self) -> "_SensitiveOperationGuard":
        self._original_import = builtins.__import__
        self._original_builtin_open = builtins.open
        self._original_io_open = io.open
        self._original_popen = subprocess.Popen
        self._original_os_process_functions = {
            name: getattr(os, name)
            for name in self._os_process_entrypoints
            if hasattr(os, name)
        }
        self._original_fork_exec = getattr(subprocess, "_fork_exec", None)
        self._previous_profile = sys.getprofile()
        self._previous_thread_profile = threading.getprofile()
        builtins.__import__ = self._guarded_import
        builtins.open = self._guarded_builtin_open
        io.open = self._guarded_io_open
        subprocess.Popen = self._guarded_popen
        for name in self._original_os_process_functions:
            setattr(os, name, self._guarded_process_entrypoint)
        if self._original_fork_exec is not None:
            subprocess._fork_exec = self._guarded_process_entrypoint
        self._active = True
        sys.setprofile(self._profile)
        threading.setprofile(self._profile)
        return self

    def __exit__(self, *_args: Any) -> None:
        sys.setprofile(self._previous_profile)
        threading.setprofile(self._previous_thread_profile)
        builtins.__import__ = self._original_import
        builtins.open = self._original_builtin_open
        io.open = self._original_io_open
        subprocess.Popen = self._original_popen
        for name, function in self._original_os_process_functions.items():
            setattr(os, name, function)
        if self._original_fork_exec is not None:
            subprocess._fork_exec = self._original_fork_exec
        self._active = False


def _verify_worker_source_manifest(expected: Mapping[str, Any]) -> dict[str, Any]:
    observed = build_input_manifest(enforce_network_block=False)
    if observed["file_contract_sha256"] != expected.get("file_contract_sha256"):
        raise Stage001Error("worker_source_file_contract_drift")
    if observed["formal_identity"] != expected.get("formal_identity"):
        raise Stage001Error("worker_formal_identity_drift")
    return observed


def _issue_worker_capability(
    worker_id: str,
    *,
    attempt_dir: Path,
    runtime_root: Path,
    output_dir: Path,
    input_manifest_path: Path,
    sandbox_profile: Path,
    campaign_nonce: str,
    lease_id: str,
    counters: Mapping[str, Any],
) -> tuple[Path, str]:
    if worker_id not in {"A1", "A2"}:
        raise Stage001Error("worker_capability_worker_invalid")
    nonce = _require_hex64(campaign_nonce, "campaign_nonce")
    lease = _require_hex64(lease_id, "lease_id")
    attempt = attempt_dir.resolve(strict=True)
    expected_attempt = ARTIFACT_PARENT.resolve() / f".{STAGE}_{nonce[:12]}"
    if attempt != expected_attempt:
        raise Stage001Error("worker_capability_attempt_path_invalid")
    worker_root = (attempt / "workers" / worker_id).resolve(strict=True)
    runtime = runtime_root.resolve(strict=True)
    output = output_dir.resolve(strict=False)
    manifest = input_manifest_path.resolve(strict=True)
    profile = sandbox_profile.resolve(strict=True)
    if runtime != worker_root / "runtime":
        raise Stage001Error("worker_capability_runtime_path_invalid")
    if output != worker_root / "output" or output.exists():
        raise Stage001Error("worker_capability_output_path_invalid")
    if manifest != attempt / "input_manifest.json":
        raise Stage001Error("worker_capability_manifest_path_invalid")
    if profile != worker_root / "stage001.sb":
        raise Stage001Error("worker_capability_profile_path_invalid")
    sandbox_probe = attempt / f".sandbox_probe_{worker_id}"
    if sandbox_probe.exists():
        raise Stage001Error("worker_capability_sandbox_probe_exists")

    expected_phase = f"worker_{worker_id.lower()}"
    parent_channel_secret = os.urandom(32).hex()
    environment = worker_environment({}, runtime, worker_id)
    capability = worker_root / "worker_capability.json"
    with _execution_event_lock(EXECUTION_EVENT_PATH) as lock_descriptor:
        claim, _ = _read_current_execution_claim(
            EXECUTION_EVENT_PATH,
            lock_descriptor=lock_descriptor,
        )
        event, event_bytes, _ = _read_current_execution_event(
            EXECUTION_EVENT_PATH,
            lock_descriptor=lock_descriptor,
        )
        if not _claim_matches_binding(claim, nonce, lease):
            raise Stage001Error("worker_capability_claim_binding_invalid")
        if not _event_matches_binding(event, nonce, lease):
            raise Stage001Error("worker_capability_event_binding_invalid")
        if event.get("status") != "running" or event.get("phase") != expected_phase:
            raise Stage001Error("worker_capability_event_phase_invalid")
        registered_event_path = EXECUTION_EVENT_PATH.with_name(
            _execution_event_entry_name(
                EXECUTION_EVENT_PATH.name,
                int(event["sequence"]) + 1,
                hashlib.sha256(event_bytes).hexdigest(),
            )
        ).resolve(strict=False)
        create_exclusive_json(
            capability,
            {
                "schema_version": 2,
                "stage": STAGE,
                "line_id": LINE_ID,
                "campaign_nonce": nonce,
                "lease_id": lease,
                "worker_id": worker_id,
                "capability_nonce": os.urandom(32).hex(),
                "attempt_dir": str(attempt),
                "runtime_root": str(runtime),
                "output_dir": str(output),
                "input_manifest_path": str(manifest),
                "input_manifest_sha256": _sha256(manifest),
                "sandbox_executable_path": str(
                    SANDBOX_EXECUTABLE.resolve(strict=True)
                ),
                "sandbox_executable_sha256": _sha256(
                    SANDBOX_EXECUTABLE.resolve(strict=True)
                ),
                "sandbox_policy_mode": SANDBOX_POLICY_MODE,
                "sandbox_profile_path": str(profile),
                "sandbox_profile_sha256": _sha256(profile),
                "sandbox_probe_path": str(sandbox_probe),
                "bootstrap_path": str(WORKER_BOOTSTRAP.resolve(strict=True)),
                "bootstrap_sha256": _sha256(WORKER_BOOTSTRAP.resolve(strict=True)),
                "runner_path": str(Path(__file__).resolve()),
                "runner_sha256": _sha256(Path(__file__).resolve()),
                "python_executable": str(Path(sys.executable).resolve()),
                "isolated_startup_sys_path": isolated_startup_sys_path(),
                "approved_sys_path": approved_worker_sys_path(),
                "worker_environment": environment,
                "parent_channel_secret_sha256": hashlib.sha256(
                    parent_channel_secret.encode("ascii")
                ).hexdigest(),
                "claim_path": str(CLAIM_PATH.resolve(strict=True)),
                "event_path": str(registered_event_path),
                "issued_at": _now(),
                "replay_permitted": False,
            },
        )
        identity = _file_identity(capability)
        payload = json.loads(capability.read_text(encoding="utf-8"))
        _replace_execution_event_if_matches_locked(
            EXECUTION_EVENT_PATH,
            lock_descriptor=lock_descriptor,
            expected_current=event,
            expected_claim=claim,
            campaign_nonce=nonce,
            lease_id=lease,
            status="running",
            phase=expected_phase,
            counters=counters,
            details={
                "worker_id": worker_id,
                "worker_capability": identity,
                "capability_nonce": payload["capability_nonce"],
                "attempt_dir": str(attempt),
                "runtime_root": str(runtime),
                "output_dir": str(output),
                "input_manifest_path": str(manifest),
                "sandbox_profile_path": str(profile),
                "bootstrap_path": str(WORKER_BOOTSTRAP.resolve(strict=True)),
                "bootstrap_sha256": _sha256(WORKER_BOOTSTRAP.resolve(strict=True)),
                "parent_channel_secret_sha256": payload[
                    "parent_channel_secret_sha256"
                ],
                "claim_path": str(CLAIM_PATH.resolve(strict=True)),
                "event_path": str(registered_event_path),
            },
        )
        registered_event_path.resolve(strict=True)
    return capability, parent_channel_secret


def _worker_interpreter_flags() -> dict[str, Any]:
    return {
        "isolated": int(sys.flags.isolated),
        "ignore_environment": int(sys.flags.ignore_environment),
        "no_site": int(sys.flags.no_site),
        "no_user_site": int(sys.flags.no_user_site),
        "safe_path": bool(sys.flags.safe_path),
        "dont_write_bytecode": int(sys.flags.dont_write_bytecode),
    }


def _validate_bootstrap_receipt_binding(
    capability: Mapping[str, Any],
    attestation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if attestation is None:
        raise Stage001Error("worker_bootstrap_attestation_required")
    if set(attestation) != BOOTSTRAP_ATTESTATION_FIELDS:
        raise Stage001Error("worker_bootstrap_attestation_schema_invalid")
    environment = capability.get("worker_environment")
    if not isinstance(environment, Mapping):
        raise Stage001Error("worker_capability_environment_invalid")
    environment_sha = hashlib.sha256(
        _stable_json_bytes(dict(environment))
    ).hexdigest()
    probe = attestation.get("sandbox_probe")
    if not isinstance(probe, Mapping) or set(probe) != BOOTSTRAP_SANDBOX_PROBE_FIELDS:
        raise Stage001Error("worker_bootstrap_sandbox_probe_schema_invalid")
    expected_effective_sys_path = [
        *list(capability.get("isolated_startup_sys_path", [])),
        *list(capability.get("approved_sys_path", [])),
    ]
    if (
        attestation.get("schema_version") != 1
        or attestation.get("attestation_type")
        != "isolated_pre_import_sandbox_bootstrap"
        or attestation.get("stage") != STAGE
        or attestation.get("line_id") != LINE_ID
        or attestation.get("campaign_nonce") != capability.get("campaign_nonce")
        or attestation.get("lease_id") != capability.get("lease_id")
        or attestation.get("worker_id") != capability.get("worker_id")
        or attestation.get("capability_nonce") != capability.get("capability_nonce")
        or not isinstance(attestation.get("pid"), int)
        or int(attestation["pid"]) <= 0
        or attestation.get("python_executable") != capability.get("python_executable")
        or attestation.get("interpreter_flags") != BOOTSTRAP_INTERPRETER_FLAGS
        or attestation.get("startup_sys_path")
        != capability.get("isolated_startup_sys_path")
        or attestation.get("approved_sys_path") != capability.get("approved_sys_path")
        or attestation.get("effective_sys_path") != expected_effective_sys_path
        or attestation.get("pre_import_forbidden_modules") != []
        or attestation.get("worker_environment_sha256") != environment_sha
        or attestation.get("parent_channel_secret_sha256")
        != capability.get("parent_channel_secret_sha256")
        or attestation.get("bootstrap_path") != capability.get("bootstrap_path")
        or attestation.get("bootstrap_sha256") != capability.get("bootstrap_sha256")
        or attestation.get("runner_path") != capability.get("runner_path")
        or attestation.get("runner_sha256") != capability.get("runner_sha256")
        or probe.get("path") != capability.get("sandbox_probe_path")
        or probe.get("write_denied") is not True
        or probe.get("errno") not in {errno.EPERM, errno.EACCES}
    ):
        raise Stage001Error("worker_bootstrap_attestation_binding_invalid")
    _parse_timestamp(attestation.get("attested_at"), "bootstrap_attested_at")
    return dict(attestation)


def _validate_bootstrap_attestation(
    capability: Mapping[str, Any],
    attestation: Mapping[str, Any] | None,
    parent_channel_secret: str | None,
) -> dict[str, Any]:
    if parent_channel_secret is None:
        raise Stage001Error("worker_bootstrap_attestation_required")
    secret = str(parent_channel_secret)
    if HEX64.fullmatch(secret) is None:
        raise Stage001Error("worker_parent_channel_secret_invalid")
    secret_sha = hashlib.sha256(secret.encode("ascii")).hexdigest()
    if capability.get("parent_channel_secret_sha256") != secret_sha:
        raise Stage001Error("worker_parent_channel_secret_mismatch")
    return _validate_bootstrap_receipt_binding(capability, attestation)


def _assert_current_bootstrap_process(
    capability: Mapping[str, Any],
    attestation: Mapping[str, Any],
) -> None:
    if (
        attestation.get("pid") != os.getpid()
        or attestation.get("python_executable")
        != str(Path(sys.executable).resolve())
        or attestation.get("python_version") != sys.version
        or _worker_interpreter_flags() != BOOTSTRAP_INTERPRETER_FLAGS
        or list(sys.path) != attestation.get("effective_sys_path")
        or dict(os.environ) != capability.get("worker_environment")
    ):
        raise Stage001Error("worker_bootstrap_current_process_invalid")


def _consume_worker_capability(
    args: argparse.Namespace,
    *,
    parent_channel_secret: str | None = None,
    bootstrap_attestation: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if bootstrap_attestation is None or parent_channel_secret is None:
        raise Stage001Error("worker_bootstrap_attestation_required")
    if args.worker_capability is None:
        raise Stage001Error("worker_capability_required")
    try:
        capability_path = args.worker_capability.resolve(strict=True)
        payload = json.loads(capability_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Stage001Error("worker_capability_unreadable") from exc
    if not isinstance(payload, Mapping) or set(payload) != WORKER_CAPABILITY_FIELDS:
        raise Stage001Error("worker_capability_schema_invalid")
    worker_id = str(args.worker)
    nonce = _require_hex64(payload.get("campaign_nonce"), "campaign_nonce")
    lease = _require_hex64(payload.get("lease_id"), "lease_id")
    if (
        payload.get("schema_version") != 2
        or payload.get("stage") != STAGE
        or payload.get("line_id") != LINE_ID
        or payload.get("worker_id") != worker_id
        or payload.get("replay_permitted") is not False
        or HEX64.fullmatch(str(payload.get("capability_nonce", ""))) is None
    ):
        raise Stage001Error("worker_capability_identity_invalid")

    attempt = Path(str(payload["attempt_dir"])).resolve(strict=True)
    worker_root = (attempt / "workers" / worker_id).resolve(strict=True)
    runtime = Path(str(payload["runtime_root"])).resolve(strict=True)
    output = Path(str(payload["output_dir"])).resolve(strict=False)
    manifest = Path(str(payload["input_manifest_path"])).resolve(strict=True)
    profile = Path(str(payload["sandbox_profile_path"])).resolve(strict=True)
    if attempt.name != f".{STAGE}_{nonce[:12]}":
        raise Stage001Error("worker_capability_attempt_path_invalid")
    if capability_path != worker_root / "worker_capability.json":
        raise Stage001Error("worker_capability_file_path_invalid")
    if runtime != worker_root / "runtime" or args.runtime_root.resolve(strict=True) != runtime:
        raise Stage001Error("worker_capability_runtime_path_invalid")
    if output != worker_root / "output" or args.worker_output.resolve(strict=False) != output:
        raise Stage001Error("worker_capability_output_path_invalid")
    if output.exists():
        raise Stage001Error("worker_output_exists_before_capability")
    if manifest != attempt / "input_manifest.json" or args.expected_manifest.resolve(strict=True) != manifest:
        raise Stage001Error("worker_capability_manifest_path_invalid")
    if _sha256(manifest) != payload.get("input_manifest_sha256"):
        raise Stage001Error("worker_capability_manifest_sha_drift")
    sandbox_executable = Path(
        str(payload["sandbox_executable_path"])
    ).resolve(strict=True)
    if (
        sandbox_executable != SANDBOX_EXECUTABLE.resolve(strict=True)
        or _sha256(sandbox_executable) != payload.get("sandbox_executable_sha256")
        or payload.get("sandbox_policy_mode") != SANDBOX_POLICY_MODE
    ):
        raise Stage001Error("worker_capability_sandbox_executable_drift")
    if profile != worker_root / "stage001.sb":
        raise Stage001Error("worker_capability_profile_path_invalid")
    if _sha256(profile) != payload.get("sandbox_profile_sha256"):
        raise Stage001Error("worker_capability_profile_sha_drift")
    probe = Path(str(payload["sandbox_probe_path"])).resolve(strict=False)
    if probe != attempt / f".sandbox_probe_{worker_id}" or probe.exists():
        raise Stage001Error("worker_capability_sandbox_probe_invalid")
    bootstrap = Path(str(payload["bootstrap_path"])).resolve(strict=True)
    if (
        bootstrap != WORKER_BOOTSTRAP.resolve(strict=True)
        or _sha256(bootstrap) != payload.get("bootstrap_sha256")
    ):
        raise Stage001Error("worker_capability_bootstrap_drift")
    if Path(str(payload["runner_path"])).resolve() != Path(__file__).resolve() or _sha256(
        Path(__file__).resolve()
    ) != payload.get("runner_sha256"):
        raise Stage001Error("worker_capability_runner_drift")
    if (
        Path(str(payload["python_executable"])).resolve(strict=True)
        != Path(sys.executable).resolve()
        or payload.get("isolated_startup_sys_path") != isolated_startup_sys_path()
        or payload.get("approved_sys_path") != approved_worker_sys_path()
        or payload.get("worker_environment")
        != worker_environment({}, runtime, worker_id)
    ):
        raise Stage001Error("worker_capability_bootstrap_runtime_drift")
    if Path.cwd().resolve() != runtime:
        raise Stage001Error("worker_cwd_not_runtime_root")
    attestation = _validate_bootstrap_attestation(
        payload,
        bootstrap_attestation,
        parent_channel_secret,
    )
    _assert_current_bootstrap_process(payload, attestation)

    claim_path = Path(str(payload["claim_path"])).resolve(strict=True)
    event_path = Path(str(payload["event_path"])).resolve(strict=True)
    claim = _read_state_json(claim_path)
    event = _read_state_json(event_path)
    expected_phase = f"worker_{worker_id.lower()}"
    if not _claim_matches_binding(claim, nonce, lease):
        raise Stage001Error("worker_capability_claim_binding_invalid")
    if not _event_matches_binding(event, nonce, lease):
        raise Stage001Error("worker_capability_event_binding_invalid")
    details = event.get("details")
    if (
        event.get("status") != "running"
        or event.get("phase") != expected_phase
        or not isinstance(details, Mapping)
        or details.get("worker_id") != worker_id
        or details.get("capability_nonce") != payload["capability_nonce"]
        or details.get("worker_capability") != _file_identity(capability_path)
        or details.get("bootstrap_path") != payload["bootstrap_path"]
        or details.get("bootstrap_sha256") != payload["bootstrap_sha256"]
        or details.get("parent_channel_secret_sha256")
        != payload["parent_channel_secret_sha256"]
        or details.get("claim_path") != str(claim_path)
        or details.get("event_path") != str(event_path)
    ):
        raise Stage001Error("worker_capability_not_registered")

    consumed = worker_root / "worker_capability.consumed.json"
    if consumed.exists():
        raise Stage001Error("worker_capability_already_consumed")
    os.replace(capability_path, consumed)
    _fsync_directory(worker_root)
    return dict(payload), _file_identity(consumed)


def _worker_main(_args: argparse.Namespace) -> int:
    raise Stage001Error("worker_bootstrap_attestation_required")


def _bootstrap_worker_main(
    args: argparse.Namespace,
    *,
    parent_channel_secret: str,
    bootstrap_attestation: Mapping[str, Any],
) -> int:
    worker_id = str(args.worker)
    runtime_root = args.runtime_root.resolve(strict=True)
    output_dir = args.worker_output.resolve()
    capability, consumed_capability_identity = _consume_worker_capability(
        args,
        parent_channel_secret=parent_channel_secret,
        bootstrap_attestation=bootstrap_attestation,
    )
    output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)

    expected_manifest = json.loads(
        args.expected_manifest.read_text(encoding="utf-8")
    )
    receipt = _worker_runtime_receipt(
        worker_id,
        runtime_root,
        source_contract_sha256=str(expected_manifest["file_contract_sha256"]),
        campaign_nonce=str(capability["campaign_nonce"]),
        lease_id=str(capability["lease_id"]),
        worker_capability=consumed_capability_identity,
        capability_payload=capability,
        bootstrap_attestation=bootstrap_attestation,
    )
    receipt["started_at"] = _now()
    network = _NetworkBlock()
    sensitive_guard = _SensitiveOperationGuard((runtime_root, output_dir))
    try:
        try:
            with network:
                _verify_worker_source_manifest(expected_manifest)
                sensitive_guard.assert_no_sensitive_modules_loaded()
                with sensitive_guard:
                    receipt["sensitive_guard_enforced"] = True
                    context = _import_production_context()
                    formal = _active_formal_identity()
                    metadata = context["s901"].s513._metadata()
                    receipt["modules"] = {
                        "stage901": str(Path(context["s901"].__file__).resolve()),
                        "live_config": str(
                            Path(context["live_config"].__file__).resolve()
                        ),
                        "vnpy_portfoliostrategy": str(
                            Path(context["portfolio_package"].__file__).resolve()
                        ),
                        "feature_tool": str(FEATURE_TOOL.resolve()),
                    }
                    strategy_class = (
                        context["s901"].s847.QmtRollPortfolioStrategyStage847C9StopRetry
                    )
                    restore_correlation_trace = _install_correlation_trace_instrumentation(
                        strategy_class
                    )
                    try:
                        combined, frames, live_spec = context["s901"]._run_live_c9(
                            metadata,
                            START,
                            END,
                        )
                    finally:
                        restore_correlation_trace()
                    if float(live_spec.capital.account_capital) != EXPECTED_CAPITAL:
                        raise Stage001Error("worker_capital_drift")
                    if str(live_spec.profile) != str(
                        context["live_config"].OFFICIAL_LIVE_PROFILE_NAME
                    ):
                        raise Stage001Error("worker_profile_drift")
                    candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
                    del combined, frames, live_spec
                    if candidates.empty:
                        raise Stage001Error("worker_entry_candidates_empty")
                    eligibility = pd.read_csv(formal["eligibility_path"])
                    feature_module = _load_feature_module()
                    features = feature_module.build_formal_root_event_features(
                        candidates,
                        eligibility,
                        formal,
                    )
                    del candidates, eligibility, metadata
        finally:
            receipt["network_connection_attempt_count"] = int(network.attempts)
            receipt["sensitive_counters"] = dict(sensitive_guard.counters)
            receipt["sensitive_counters"]["network_connection_count"] += int(
                network.attempts
            )
        if network.attempts != 0:
            raise Stage001Error("worker_network_attempt_detected")
        if any(receipt["sensitive_counters"].values()):
            raise Stage001Error("worker_sensitive_operation_attempt_detected")
        feature_path = output_dir / "event_features.csv"
        features.to_csv(
            feature_path,
            index=False,
            lineterminator="\n",
            float_format="%.17g",
        )
        receipt.update(
            {
                "status": "completed",
                "completed_at": _now(),
                "analysis_start": START.date().isoformat(),
                "analysis_end": END.date().isoformat(),
                "capital": EXPECTED_CAPITAL,
                "official_live_version": EXPECTED_OFFICIAL_VERSION,
                "baseline_replay_count": 1,
                "event_count": int(len(features)),
                "event_feature_sha256": _frame_sha256(features),
                "event_feature_file": _file_identity(feature_path),
                "formal_identity": formal,
            }
        )
        _write_json(output_dir / "receipt.json", receipt)
        return 0
    except BaseException as exc:
        receipt.update(
            {
                "status": "failed",
                "completed_at": _now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        _write_json(output_dir / "failure_receipt.json", receipt)
        raise


def _run_worker(
    worker_id: str,
    attempt_dir: Path,
    input_manifest_path: Path,
    input_manifest: Mapping[str, Any],
    *,
    campaign_nonce: str,
    lease_id: str,
    counters: Mapping[str, Any],
) -> dict[str, Any]:
    worker_dir = attempt_dir / "workers" / worker_id
    worker_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    runtime = _prepare_worker_runtime(
        worker_dir,
        expected_database_sha256=str(
            input_manifest["files"]["source_database"]["sha256"]
        ),
    )
    output = worker_dir / "output"
    sandbox_profile = write_worker_sandbox_profile(worker_dir)
    environment = worker_environment(os.environ, runtime, worker_id)
    capability, parent_channel_secret = _issue_worker_capability(
        worker_id,
        attempt_dir=attempt_dir,
        runtime_root=runtime,
        output_dir=output,
        input_manifest_path=input_manifest_path,
        sandbox_profile=sandbox_profile,
        campaign_nonce=campaign_nonce,
        lease_id=lease_id,
        counters=counters,
    )
    log_path = worker_dir / "worker.log"
    worker_command = worker_bootstrap_command(
        worker_id,
        runtime_root=runtime,
        output_dir=output,
        input_manifest_path=input_manifest_path,
        capability_path=capability,
    )
    command = sandboxed_command(sandbox_profile, worker_command)
    with log_path.open("wb") as log:
        completed = subprocess.run(
            command,
            cwd=runtime,
            env=environment,
            input=f"{parent_channel_secret}\n".encode("ascii"),
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log.flush()
        os.fsync(log.fileno())
    if completed.returncode != 0:
        failure = output / "failure_receipt.json"
        failure_receipt = (
            json.loads(failure.read_text(encoding="utf-8"))
            if failure.is_file()
            else {}
        )
        error = failure_receipt.get("error", f"returncode={completed.returncode}")
        raise WorkerStage001Error(
            f"worker_failed:{worker_id}:{error}",
            failure_receipt,
        )
    receipt_path = output / "receipt.json"
    feature_path = output / "event_features.csv"
    if not receipt_path.is_file() or not feature_path.is_file():
        raise Stage001Error(f"worker_output_missing:{worker_id}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "completed" or receipt.get("worker_id") != worker_id:
        raise Stage001Error(f"worker_receipt_invalid:{worker_id}")
    if capability.exists():
        raise Stage001Error(f"worker_capability_not_consumed:{worker_id}")
    receipt["feature_path"] = str(feature_path)
    return receipt


def _coverage_frame(metrics: Mapping[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {"dimension": "all", "key": "event_count", "count": metrics["event_count"]},
        {"dimension": "all", "key": "product_count", "count": metrics["product_count"]},
    ]
    rows.extend(
        {"dimension": "year", "key": key, "count": value}
        for key, value in metrics["yearly_counts"].items()
    )
    rows.extend(
        {"dimension": "direction", "key": key, "count": value}
        for key, value in metrics["direction_counts"].items()
    )
    return pd.DataFrame(rows)


def _feature_diagnostics_frame(metrics: Mapping[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"feature": key, "unique_count": value}
            for key, value in metrics["feature_unique_counts"].items()
        ]
    )


def _artifact_manifest(directory: Path) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        relative = path.relative_to(directory).as_posix()
        identity = _file_identity(path)
        files[relative] = {
            "relative_path": relative,
            "size": identity["size"],
            "sha256": identity["sha256"],
        }
    contract = {
        name: {"size": item["size"], "sha256": item["sha256"]}
        for name, item in files.items()
    }
    return {
        "schema_version": 1,
        "stage": STAGE,
        "files": files,
        "file_contract_sha256": hashlib.sha256(
            _stable_json_bytes(contract)
        ).hexdigest(),
    }


def _report(summary: Mapping[str, Any]) -> str:
    qualification = summary["feature_qualification"]
    metrics = qualification["metrics"]
    gates = summary["stage001_gates"]["gates"]
    gate_lines = [
        f"- {name}: `{'PASS' if passed else 'FAIL'}`"
        for name, passed in gates.items()
    ]
    return "\n".join(
        [
            "# Stage001 正式根事件与决策时点特征资格结果",
            "",
            f"- 决策：`{summary['decision']}`",
            f"- 正式版本：`{summary['formal_identity']['official_live_version']}`",
            f"- 正式AI材料：`{summary['formal_identity']['formal_release_id']}`",
            f"- 区间：`{summary['analysis_start']} -> {summary['analysis_end']}`",
            f"- 双冷启动：`A1/A2`，事件 `{metrics['event_count']}` 条，产品 `{metrics['product_count']}` 个。",
            "- 本阶段只发布根事件和12项决策时点特征；不发布收益、回撤、交易或未来结果。",
            "- 标签读取、标签构造、模型fit、预测、候选策略、holdout、联网、CTP、账户、订单和生产写入计数均为0。",
            "",
            "## 硬门",
            "",
            *gate_lines,
            "",
            "## 判断",
            "",
            (
                "事件级研究对象通过数据资格门；仅允许进入独立结果复核，不能据此声称XGBoost有效或接入正式版本。"
                if summary["stage001_gates"]["passed"]
                else "至少一项冻结资格门失败；本研究线按预注册闭线，不得调门、删样本或同线重跑。"
            ),
            "",
        ]
    )


def _relative_artifact_identity(path: Path, root: Path) -> dict[str, Any]:
    identity = _file_identity(path)
    return {
        "relative_path": path.resolve(strict=True).relative_to(
            root.resolve(strict=True)
        ).as_posix(),
        "size": identity["size"],
        "mtime_ns": identity["mtime_ns"],
        "sha256": identity["sha256"],
    }


def _attempt_relative_path(path: Any, attempt_dir: Path, label: str) -> str:
    try:
        resolved = Path(str(path)).resolve(strict=True)
        return resolved.relative_to(attempt_dir.resolve(strict=True)).as_posix()
    except (OSError, RuntimeError, ValueError) as exc:
        raise Stage001Error(f"portable_receipt_path_invalid:{label}") from exc


def _copy_worker_evidence(
    source: Path,
    *,
    publish: Path,
    relative_path: Path,
) -> dict[str, Any]:
    destination = publish / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copy2(source, destination)
    os.chmod(destination, 0o600)
    return _relative_artifact_identity(destination, publish)


def _read_json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Stage001Error(f"{label}_unreadable") from exc
    if not isinstance(payload, Mapping):
        raise Stage001Error(f"{label}_not_mapping")
    return dict(payload)


def _read_json_mapping_bytes_once(
    path: Path,
    label: str,
) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Stage001Error(f"{label}_unreadable") from exc
    if not isinstance(payload, Mapping):
        raise Stage001Error(f"{label}_not_mapping")
    return dict(payload), hashlib.sha256(raw).hexdigest()


def _validate_relative_artifact_identity(
    identity: Any,
    *,
    root: Path,
    label: str,
) -> Path:
    if not isinstance(identity, Mapping) or set(identity) != RELATIVE_FILE_IDENTITY_FIELDS:
        raise Stage001Error(f"portable_relative_identity_schema_invalid:{label}")
    relative_text = str(identity.get("relative_path", ""))
    relative = PurePosixPath(relative_text)
    if (
        not relative_text
        or relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
    ):
        raise Stage001Error(f"portable_relative_path_invalid:{label}")
    try:
        path = root.joinpath(*relative.parts).resolve(strict=True)
        observed = _relative_artifact_identity(path, root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise Stage001Error(f"portable_relative_file_missing:{label}") from exc
    if dict(identity) != observed:
        raise Stage001Error(f"portable_relative_identity_drift:{label}")
    return path


def _lexical_attempt_relative_path(
    value: Any,
    attempt_root: Path,
    label: str,
) -> str:
    path = Path(str(value))
    if not path.is_absolute():
        raise Stage001Error(f"portable_raw_path_not_absolute:{label}")
    try:
        return path.resolve(strict=False).relative_to(
            attempt_root.resolve(strict=False)
        ).as_posix()
    except (OSError, RuntimeError, ValueError) as exc:
        raise Stage001Error(f"portable_raw_path_outside_attempt:{label}") from exc


def _copy_receipt_identity_evidence(
    identity: Any,
    *,
    expected_source: Path,
    label: str,
    publish: Path,
    relative_path: Path,
) -> dict[str, Any]:
    source, _ = _assert_receipt_file_identity(identity, label=label)
    if source != expected_source.resolve(strict=True):
        raise Stage001Error(f"portable_evidence_source_drift:{label}")
    return _copy_worker_evidence(
        source,
        publish=publish,
        relative_path=relative_path,
    )


def _portable_bootstrap_attestation(
    attestation: Mapping[str, Any],
    attempt_dir: Path,
) -> dict[str, Any]:
    portable = json.loads(json.dumps(attestation, ensure_ascii=True, allow_nan=False))
    probe = portable.get("sandbox_probe")
    if not isinstance(probe, Mapping):
        raise Stage001Error("portable_bootstrap_probe_missing")
    probe = dict(probe)
    probe["path"] = {
        "ephemeral_relative_path": _lexical_attempt_relative_path(
            probe.get("path"),
            attempt_dir,
            "bootstrap_sandbox_probe",
        ),
        "removed_after_publish": True,
    }
    portable["sandbox_probe"] = probe
    return portable


def _portable_worker_receipts(
    attempt_dir: Path,
    publish: Path,
    receipts: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    workers: list[dict[str, Any]] = []
    for receipt in sorted(receipts, key=lambda item: str(item.get("worker_id", ""))):
        worker_id = str(receipt.get("worker_id", ""))
        if worker_id not in {"A1", "A2"}:
            raise Stage001Error("portable_receipt_worker_invalid")
        if set(receipt) != WORKER_SUCCESS_RECEIPT_FIELDS:
            raise Stage001Error(f"portable_parent_receipt_schema_invalid:{worker_id}")
        worker_root = attempt_dir / "workers" / worker_id
        raw_source = worker_root / "output" / "receipt.json"
        raw_receipt = _read_json_mapping(raw_source, "portable_raw_receipt")
        if set(raw_receipt) != RAW_WORKER_SUCCESS_RECEIPT_FIELDS:
            raise Stage001Error(f"portable_raw_receipt_schema_invalid:{worker_id}")
        expected_parent = dict(raw_receipt)
        expected_parent["feature_path"] = str(receipt["feature_path"])
        if expected_parent != dict(receipt):
            raise Stage001Error(f"portable_raw_receipt_drift:{worker_id}")

        portable = json.loads(json.dumps(receipt, ensure_ascii=True, allow_nan=False))
        portable["receipt_schema_version"] = 2
        portable["receipt_type"] = "portable_post_cleanup"
        portable["bootstrap_attestation"] = _portable_bootstrap_attestation(
            receipt["bootstrap_attestation"],
            attempt_dir,
        )

        for field in ("cwd", "runtime_root", "tmpdir", "mplconfigdir", "home"):
            portable[field] = {
                "ephemeral_relative_path": _attempt_relative_path(
                    receipt[field],
                    attempt_dir,
                    field,
                ),
                "removed_after_publish": True,
            }

        database = receipt["database"]
        database_relative = _attempt_relative_path(
            database["path"],
            attempt_dir,
            "database",
        )
        portable["database"] = {
            "ephemeral_relative_path": database_relative,
            "size": int(database["size"]),
            "mtime_ns": int(database["mtime_ns"]),
            "sha256": str(database["sha256"]),
            "source_input_logical_key": "source_database",
            "verified_before_cleanup": True,
            "removed_after_publish": True,
        }

        evidence_root = Path("workers") / worker_id
        portable["setting"] = _copy_receipt_identity_evidence(
            receipt["setting"],
            expected_source=worker_root / "runtime/.vntrader/vt_setting.json",
            label="setting",
            publish=publish,
            relative_path=evidence_root / "vt_setting.json",
        )
        portable["sandbox_profile"] = _copy_receipt_identity_evidence(
            receipt["sandbox_profile"],
            expected_source=worker_root / "stage001.sb",
            label="sandbox_profile",
            publish=publish,
            relative_path=evidence_root / "stage001.sb",
        )
        portable["event_feature_file"] = _copy_receipt_identity_evidence(
            receipt["event_feature_file"],
            expected_source=worker_root / "output/event_features.csv",
            label="event_feature",
            publish=publish,
            relative_path=evidence_root / "event_features.csv",
        )
        portable["feature_path"] = portable["event_feature_file"]["relative_path"]
        portable["worker_capability"] = _copy_receipt_identity_evidence(
            receipt["worker_capability"],
            expected_source=worker_root / "worker_capability.consumed.json",
            label="capability",
            publish=publish,
            relative_path=evidence_root / "worker_capability.consumed.json",
        )
        portable["raw_worker_receipt"] = _copy_worker_evidence(
            raw_source,
            publish=publish,
            relative_path=evidence_root / "worker_receipt.raw.json",
        )
        portable["raw_worker_receipt_sha256"] = portable["raw_worker_receipt"][
            "sha256"
        ]
        portable["worker_log_published"] = False
        if set(portable) != PORTABLE_WORKER_RECEIPT_FIELDS:
            raise Stage001Error(f"portable_receipt_schema_invalid:{worker_id}")
        workers.append(portable)
    return {
        "schema_version": 2,
        "receipt_type": "portable_post_cleanup",
        "workers": workers,
    }


def _assert_portable_copy_matches_raw(
    portable_identity: Any,
    raw_identity: Any,
    *,
    root: Path,
    expected_relative_path: str,
    label: str,
) -> Path:
    path = _validate_relative_artifact_identity(
        portable_identity,
        root=root,
        label=label,
    )
    if not isinstance(raw_identity, Mapping) or set(raw_identity) != FILE_IDENTITY_FIELDS:
        raise Stage001Error(f"portable_raw_identity_schema_invalid:{label}")
    if portable_identity["relative_path"] != expected_relative_path:
        raise Stage001Error(f"portable_evidence_relative_path_drift:{label}")
    for field in ("size", "mtime_ns", "sha256"):
        if portable_identity[field] != raw_identity[field]:
            raise Stage001Error(f"portable_evidence_identity_drift:{label}:{field}")
    return path


def _validate_portable_worker_receipts(
    root: Path,
    *,
    input_manifest: Mapping[str, Any],
    expected_campaign_nonce: str,
    expected_lease_id: str,
) -> dict[str, Any]:
    files = input_manifest.get("files")
    if not isinstance(files, Mapping):
        raise Stage001Error("success_worker_input_files_missing")
    try:
        expected_database_sha256 = str(files["source_database"]["sha256"])
        expected_python_executable = Path(
            str(files["python_executable"]["path"])
        ).resolve(strict=False)
        sandbox_identity = files["sandbox_executable"]
        bootstrap_identity = files["stage001_worker_bootstrap"]
        runner_identity = files["stage001_runner"]
    except (KeyError, TypeError) as exc:
        raise Stage001Error("success_worker_input_identity_missing") from exc
    expected_source_contract_sha256 = str(
        input_manifest.get("file_contract_sha256", "")
    )
    expected_formal_identity = input_manifest.get("formal_identity")
    if not isinstance(expected_formal_identity, Mapping):
        raise Stage001Error("success_worker_formal_identity_missing")
    expected_modules = expected_worker_modules(input_manifest)
    input_manifest_sha256 = _sha256(root / "input_manifest.json")
    expected_attempt = (
        ARTIFACT_PARENT.resolve()
        / f".{STAGE}_{expected_campaign_nonce[:12]}"
    ).resolve(strict=False)

    payload = _read_json_mapping(root / "worker_receipts.json", "portable_receipts")
    if set(payload) != PORTABLE_RECEIPT_FIELDS:
        raise Stage001Error("portable_receipts_schema_invalid")
    if payload.get("schema_version") != 2 or payload.get(
        "receipt_type"
    ) != "portable_post_cleanup":
        raise Stage001Error("portable_receipts_identity_invalid")
    workers = payload.get("workers")
    if not isinstance(workers, list) or len(workers) != 2:
        raise Stage001Error("portable_receipt_pair_invalid")
    if [item.get("worker_id") for item in workers if isinstance(item, Mapping)] != [
        "A1",
        "A2",
    ]:
        raise Stage001Error("portable_receipt_worker_pair_invalid")

    transformed_fields = {
        "cwd",
        "runtime_root",
        "tmpdir",
        "mplconfigdir",
        "home",
        "database",
        "setting",
        "sandbox_profile",
        "worker_capability",
        "bootstrap_attestation",
        "event_feature_file",
    }
    expected_worker_files: set[str] = set()
    validated_workers: list[dict[str, Any]] = []
    event_frames: dict[str, pd.DataFrame] = {}
    worker_pids: set[int] = set()
    worker_paths: dict[str, set[str]] = {
        field: set()
        for field in ("runtime_root", "tmpdir", "mplconfigdir", "home")
    }
    worker_sys_paths: list[list[Any]] = []
    capability_nonces: set[str] = set()
    parent_channel_hashes: set[str] = set()
    for item in sorted(workers, key=lambda value: str(value.get("worker_id", ""))):
        if not isinstance(item, Mapping):
            raise Stage001Error("portable_receipt_item_not_mapping")
        portable = dict(item)
        worker_id = str(portable.get("worker_id", ""))
        if set(portable) != PORTABLE_WORKER_RECEIPT_FIELDS:
            raise Stage001Error(f"portable_receipt_schema_invalid:{worker_id}")
        if (
            portable.get("receipt_schema_version") != 2
            or portable.get("receipt_type") != "portable_post_cleanup"
            or portable.get("worker_log_published") is not False
        ):
            raise Stage001Error(f"portable_receipt_identity_invalid:{worker_id}")

        evidence_root = f"workers/{worker_id}"
        expected_worker_files.update(
            {
                f"{evidence_root}/worker_receipt.raw.json",
                f"{evidence_root}/vt_setting.json",
                f"{evidence_root}/stage001.sb",
                f"{evidence_root}/worker_capability.consumed.json",
                f"{evidence_root}/event_features.csv",
            }
        )
        raw_path = _validate_relative_artifact_identity(
            portable.get("raw_worker_receipt"),
            root=root,
            label=f"{worker_id}:raw_worker_receipt",
        )
        if portable["raw_worker_receipt"]["relative_path"] != (
            f"{evidence_root}/worker_receipt.raw.json"
        ):
            raise Stage001Error(f"portable_raw_receipt_path_drift:{worker_id}")
        if portable.get("raw_worker_receipt_sha256") != portable[
            "raw_worker_receipt"
        ]["sha256"]:
            raise Stage001Error(f"portable_raw_receipt_sha_drift:{worker_id}")
        raw = _read_json_mapping(raw_path, "portable_raw_receipt")
        if set(raw) != RAW_WORKER_SUCCESS_RECEIPT_FIELDS:
            raise Stage001Error(f"portable_raw_receipt_schema_invalid:{worker_id}")
        if raw.get("worker_id") != worker_id:
            raise Stage001Error(f"portable_raw_receipt_worker_drift:{worker_id}")

        runtime_source = Path(str(raw.get("runtime_root", ""))).resolve(strict=False)
        try:
            attempt_source = runtime_source.parents[2]
        except IndexError as exc:
            raise Stage001Error(f"portable_raw_runtime_path_invalid:{worker_id}") from exc
        expected_worker_source = attempt_source / "workers" / worker_id
        if attempt_source != expected_attempt:
            raise Stage001Error(f"success_worker_attempt_path_drift:{worker_id}")
        if runtime_source != expected_worker_source / "runtime":
            raise Stage001Error(f"portable_raw_runtime_path_invalid:{worker_id}")
        expected_portable_bootstrap = _portable_bootstrap_attestation(
            raw.get("bootstrap_attestation", {}),
            attempt_source,
        )
        if portable.get("bootstrap_attestation") != expected_portable_bootstrap:
            raise Stage001Error(
                f"portable_bootstrap_attestation_drift:{worker_id}"
            )
        if str(attempt_source) in json.dumps(portable, sort_keys=True):
            raise Stage001Error(f"portable_receipt_leaks_attempt_path:{worker_id}")

        for field in ("cwd", "runtime_root", "tmpdir", "mplconfigdir", "home"):
            expected_pointer = {
                "ephemeral_relative_path": _lexical_attempt_relative_path(
                    raw[field],
                    attempt_source,
                    f"{worker_id}:{field}",
                ),
                "removed_after_publish": True,
            }
            if (
                not isinstance(portable[field], Mapping)
                or set(portable[field]) != EPHEMERAL_PATH_FIELDS
                or dict(portable[field]) != expected_pointer
            ):
                raise Stage001Error(f"portable_ephemeral_path_drift:{worker_id}:{field}")

        raw_database = raw.get("database")
        if not isinstance(raw_database, Mapping) or set(raw_database) != FILE_IDENTITY_FIELDS:
            raise Stage001Error(f"portable_raw_database_schema_invalid:{worker_id}")
        expected_database = {
            "ephemeral_relative_path": _lexical_attempt_relative_path(
                raw_database["path"],
                attempt_source,
                f"{worker_id}:database",
            ),
            "size": int(raw_database["size"]),
            "mtime_ns": int(raw_database["mtime_ns"]),
            "sha256": str(raw_database["sha256"]),
            "source_input_logical_key": "source_database",
            "verified_before_cleanup": True,
            "removed_after_publish": True,
        }
        if (
            not isinstance(portable["database"], Mapping)
            or set(portable["database"]) != PORTABLE_DATABASE_FIELDS
            or dict(portable["database"]) != expected_database
            or portable["database"]["sha256"] != expected_database_sha256
        ):
            raise Stage001Error(f"portable_database_attestation_drift:{worker_id}")

        copied_paths: dict[str, Path] = {}
        for field, filename in (
            ("setting", "vt_setting.json"),
            ("sandbox_profile", "stage001.sb"),
            ("worker_capability", "worker_capability.consumed.json"),
            ("event_feature_file", "event_features.csv"),
        ):
            copied_paths[field] = _assert_portable_copy_matches_raw(
                portable[field],
                raw[field],
                root=root,
                expected_relative_path=f"{evidence_root}/{filename}",
                label=f"{worker_id}:{field}",
            )

        if copied_paths["setting"].read_bytes() != b"{}\n":
            raise Stage001Error(f"portable_setting_content_drift:{worker_id}")
        capability = _read_json_mapping(
            copied_paths["worker_capability"],
            "portable_worker_capability",
        )
        if set(capability) != WORKER_CAPABILITY_FIELDS:
            raise Stage001Error(f"portable_worker_capability_schema_invalid:{worker_id}")
        expected_environment = {
            "HOME": str(runtime_source / "home"),
            "LANG": "C",
            "LC_ALL": "C",
            "MPLCONFIGDIR": str(runtime_source / "mplconfig"),
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "PATH": "/usr/bin:/bin",
            "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR": "1",
            "TMPDIR": str(runtime_source / "tmp"),
            "VECLIB_MAXIMUM_THREADS": "1",
        }
        expected_capability_paths = {
            "attempt_dir": attempt_source,
            "runtime_root": runtime_source,
            "output_dir": expected_worker_source / "output",
            "input_manifest_path": attempt_source / "input_manifest.json",
            "sandbox_executable_path": Path(
                str(sandbox_identity.get("path", ""))
            ).resolve(strict=False),
            "sandbox_profile_path": expected_worker_source / "stage001.sb",
            "sandbox_probe_path": attempt_source / f".sandbox_probe_{worker_id}",
            "bootstrap_path": Path(
                str(bootstrap_identity.get("path", ""))
            ).resolve(strict=False),
            "runner_path": Path(
                str(runner_identity.get("path", ""))
            ).resolve(strict=False),
            "claim_path": CLAIM_PATH.resolve(strict=False),
        }
        capability_paths_exact = all(
            Path(str(capability.get(field, ""))).resolve(strict=False) == expected
            for field, expected in expected_capability_paths.items()
        )
        capability_event_path = Path(
            str(capability.get("event_path", ""))
        ).resolve(strict=False)
        capability_event_match = _execution_event_entry_pattern(
            EXECUTION_EVENT_PATH.name
        ).fullmatch(capability_event_path.name)
        expected_event_sequence = 3 if worker_id == "A1" else 5
        capability_event_path_exact = bool(
            capability_event_path.parent == EXECUTION_STATE_DIR.resolve(strict=False)
            and capability_event_match is not None
            and int(capability_event_match.group("sequence"))
            == expected_event_sequence
        )
        capability_nonce = str(capability.get("capability_nonce", ""))
        parent_channel_hash = str(
            capability.get("parent_channel_secret_sha256", "")
        )
        if (
            capability.get("schema_version") != 2
            or capability.get("stage") != STAGE
            or capability.get("line_id") != LINE_ID
            or capability.get("campaign_nonce") != expected_campaign_nonce
            or capability.get("lease_id") != expected_lease_id
            or capability.get("worker_id") != worker_id
            or HEX64.fullmatch(capability_nonce) is None
            or capability.get("replay_permitted") is not False
            or not capability_paths_exact
            or not capability_event_path_exact
            or capability.get("input_manifest_sha256") != input_manifest_sha256
            or capability.get("sandbox_executable_sha256")
            != sandbox_identity.get("sha256")
            or capability.get("sandbox_policy_mode") != SANDBOX_POLICY_MODE
            or capability.get("sandbox_profile_sha256")
            != portable["sandbox_profile"]["sha256"]
            or capability.get("bootstrap_sha256")
            != bootstrap_identity.get("sha256")
            or capability.get("runner_sha256") != runner_identity.get("sha256")
            or Path(str(capability.get("python_executable", ""))).resolve(
                strict=False
            )
            != expected_python_executable
            or capability.get("worker_environment") != expected_environment
            or HEX64.fullmatch(parent_channel_hash) is None
        ):
            raise Stage001Error(f"portable_worker_capability_binding_drift:{worker_id}")
        _receipt_timestamp(
            capability.get("issued_at"),
            f"{worker_id}:capability_issued_at",
        )
        bootstrap_attestation = _validate_bootstrap_receipt_binding(
            capability,
            raw.get("bootstrap_attestation"),
        )
        if (
            bootstrap_attestation.get("pid") != raw.get("pid")
            or bootstrap_attestation.get("python_executable")
            != raw.get("python_executable")
            or bootstrap_attestation.get("python_version") != raw.get("python_version")
            or bootstrap_attestation.get("effective_sys_path") != raw.get("sys_path")
        ):
            raise Stage001Error(
                f"portable_worker_bootstrap_receipt_drift:{worker_id}"
            )

        if raw.get("campaign_nonce") != expected_campaign_nonce or raw.get(
            "lease_id"
        ) != expected_lease_id:
            raise Stage001Error(f"success_worker_campaign_binding_drift:{worker_id}")
        if raw.get("status") != "completed":
            raise Stage001Error(f"success_worker_status_not_completed:{worker_id}")
        if raw.get("analysis_start") != START.date().isoformat() or raw.get(
            "analysis_end"
        ) != END.date().isoformat():
            raise Stage001Error(f"success_worker_interval_drift:{worker_id}")
        capital = raw.get("capital")
        if (
            isinstance(capital, bool)
            or not isinstance(capital, (int, float))
            or not math.isfinite(float(capital))
            or float(capital) != EXPECTED_CAPITAL
        ):
            raise Stage001Error(f"success_worker_capital_drift:{worker_id}")
        if raw.get("official_live_version") != EXPECTED_OFFICIAL_VERSION:
            raise Stage001Error(f"success_worker_official_version_drift:{worker_id}")
        if raw.get("formal_identity") != dict(expected_formal_identity):
            raise Stage001Error(f"success_worker_formal_identity_drift:{worker_id}")
        if raw.get("source_file_contract_sha256") != expected_source_contract_sha256:
            raise Stage001Error(f"success_worker_source_contract_drift:{worker_id}")
        if raw.get("baseline_replay_count") != 1:
            raise Stage001Error(
                f"success_worker_baseline_replay_count_invalid:{worker_id}"
            )
        if raw.get("checkpoint_reuse_count") != 0:
            raise Stage001Error(f"success_worker_checkpoint_reuse_detected:{worker_id}")
        if raw.get("network_connection_attempt_count") != 0:
            raise Stage001Error(f"success_worker_network_attempt_detected:{worker_id}")
        if raw.get("sandbox_enforced") is not True:
            raise Stage001Error(f"success_worker_sandbox_missing:{worker_id}")
        if raw.get("sandbox_policy_mode") != SANDBOX_POLICY_MODE:
            raise Stage001Error(f"success_worker_sandbox_policy_drift:{worker_id}")
        if Path(str(raw.get("sandbox_launch_executable", ""))).resolve(
            strict=False
        ) != Path(str(sandbox_identity.get("path", ""))).resolve(strict=False):
            raise Stage001Error(f"success_worker_sandbox_executable_drift:{worker_id}")
        if raw.get("sensitive_guard_enforced") is not True:
            raise Stage001Error(f"success_worker_sensitive_guard_missing:{worker_id}")
        counters = _validate_counter_schema(raw.get("sensitive_counters", {}))
        if any(counters.values()):
            raise Stage001Error(f"success_worker_sensitive_counter_nonzero:{worker_id}")
        if raw.get("modules") != expected_modules:
            raise Stage001Error(f"success_worker_module_drift:{worker_id}")
        if Path(str(raw.get("python_executable", ""))).resolve(
            strict=False
        ) != expected_python_executable:
            raise Stage001Error(f"success_worker_python_executable_drift:{worker_id}")
        runtime = input_manifest.get("runtime")
        if not isinstance(runtime, Mapping) or raw.get("python_version") != runtime.get(
            "python_version"
        ):
            raise Stage001Error(f"success_worker_python_version_drift:{worker_id}")
        if Path(str(raw.get("cwd", ""))).resolve(strict=False) != runtime_source:
            raise Stage001Error(f"success_worker_cwd_drift:{worker_id}")

        try:
            pid = int(raw.get("pid", 0))
        except (TypeError, ValueError) as exc:
            raise Stage001Error(f"success_worker_pid_invalid:{worker_id}") from exc
        if isinstance(raw.get("pid"), bool) or pid <= 0 or pid != raw.get("pid"):
            raise Stage001Error(f"success_worker_pid_invalid:{worker_id}")
        worker_pids.add(pid)
        sys_path = raw.get("sys_path")
        if not isinstance(sys_path, list) or not sys_path or not all(
            isinstance(value, str) and value for value in sys_path
        ):
            raise Stage001Error(f"success_worker_sys_path_invalid:{worker_id}")
        worker_sys_paths.append(list(sys_path))
        for field in worker_paths:
            value = str(raw.get(field, ""))
            if not value or not Path(value).is_absolute():
                raise Stage001Error(f"success_worker_path_invalid:{worker_id}:{field}")
            worker_paths[field].add(value)
        if Path(str(raw.get("tmpdir", ""))).resolve(strict=False) != (
            runtime_source / "tmp"
        ) or Path(str(raw.get("mplconfigdir", ""))).resolve(strict=False) != (
            runtime_source / "mplconfig"
        ) or Path(str(raw.get("home", ""))).resolve(strict=False) != (
            runtime_source / "home"
        ):
            raise Stage001Error(f"success_worker_runtime_layout_drift:{worker_id}")

        raw_database = raw["database"]
        if (
            raw_database.get("sha256") != expected_database_sha256
            or Path(str(raw_database.get("path", ""))).resolve(strict=False)
            != runtime_source / ".vntrader/database.db"
        ):
            raise Stage001Error(f"success_worker_database_drift:{worker_id}")
        if Path(str(raw["setting"].get("path", ""))).resolve(strict=False) != (
            runtime_source / ".vntrader/vt_setting.json"
        ):
            raise Stage001Error(f"success_worker_setting_path_drift:{worker_id}")
        if Path(str(raw["sandbox_profile"].get("path", ""))).resolve(
            strict=False
        ) != expected_worker_source / "stage001.sb":
            raise Stage001Error(f"success_worker_sandbox_profile_drift:{worker_id}")
        if Path(str(raw["worker_capability"].get("path", ""))).resolve(
            strict=False
        ) != expected_worker_source / "worker_capability.consumed.json":
            raise Stage001Error(f"success_worker_capability_path_drift:{worker_id}")

        started = _receipt_timestamp(raw.get("started_at"), f"{worker_id}:started_at")
        completed = _receipt_timestamp(
            raw.get("completed_at"),
            f"{worker_id}:completed_at",
        )
        issued = _receipt_timestamp(
            capability.get("issued_at"),
            f"{worker_id}:capability_issued_at",
        )
        attested = _receipt_timestamp(
            bootstrap_attestation.get("attested_at"),
            f"{worker_id}:bootstrap_attested_at",
        )
        if not (issued <= attested <= started <= completed):
            raise Stage001Error(f"success_worker_timestamp_order_invalid:{worker_id}")

        event_frame = pd.read_csv(
            copied_paths["event_feature_file"],
            float_precision="round_trip",
        )
        if len(event_frame) != int(raw.get("event_count", -1)):
            raise Stage001Error(f"portable_event_count_drift:{worker_id}")
        if len(event_frame) <= 0:
            raise Stage001Error(f"success_worker_event_count_invalid:{worker_id}")
        _load_feature_module()._validate_output_schema(event_frame)
        if _frame_sha256(event_frame) != raw.get("event_feature_sha256"):
            raise Stage001Error(f"portable_event_frame_sha_drift:{worker_id}")
        if portable.get("feature_path") != portable["event_feature_file"][
            "relative_path"
        ]:
            raise Stage001Error(f"portable_feature_path_drift:{worker_id}")

        for field in RAW_WORKER_SUCCESS_RECEIPT_FIELDS - transformed_fields:
            if portable.get(field) != raw.get(field):
                raise Stage001Error(f"portable_raw_field_drift:{worker_id}:{field}")
        capability_nonces.add(capability_nonce)
        parent_channel_hashes.add(parent_channel_hash)
        validated_workers.append(dict(portable))
        event_frames[worker_id] = event_frame

    if len(worker_pids) != 2:
        raise Stage001Error("success_worker_process_not_distinct")
    for field, values in worker_paths.items():
        if len(values) != 2:
            raise Stage001Error(f"success_worker_path_not_distinct:{field}")
    if len(worker_sys_paths) != 2 or worker_sys_paths[0] != worker_sys_paths[1]:
        raise Stage001Error("success_worker_sys_path_drift")
    if len(capability_nonces) != 2:
        raise Stage001Error("success_worker_capability_nonce_not_distinct")
    if len(parent_channel_hashes) != 2:
        raise Stage001Error("success_worker_parent_channel_not_distinct")
    workers_root = root / "workers"
    observed_worker_files = {
        path.relative_to(root).as_posix()
        for path in workers_root.rglob("*")
        if path.is_file()
    }
    if observed_worker_files != expected_worker_files:
        raise Stage001Error("portable_worker_evidence_file_set_drift")
    comparison = compare_worker_frames(
        event_frames["A1"],
        event_frames["A2"],
        atol=1e-12,
    )
    event_counts = {int(item["event_count"]) for item in validated_workers}
    event_shas = {str(item["event_feature_sha256"]) for item in validated_workers}
    if len(event_counts) != 1 or len(event_shas) != 1:
        raise Stage001Error("success_worker_event_receipt_drift")
    isolation = {
        "passed": True,
        "worker_ids": ["A1", "A2"],
        "distinct_pid": True,
        "distinct_runtime_root": True,
        "distinct_tmpdir": True,
        "distinct_mplconfigdir": True,
        "distinct_home": True,
        "database_sha256": expected_database_sha256,
        "event_count": next(iter(event_counts)),
        "event_feature_sha256": next(iter(event_shas)),
        "checkpoint_reuse_count": 0,
        "baseline_replay_count_per_worker": 1,
        "network_connection_attempt_count": 0,
        "sandbox_policy_mode": SANDBOX_POLICY_MODE,
        "sensitive_guard_enforced": True,
    }
    return {
        "receipt": payload,
        "workers": validated_workers,
        "worker_comparison": comparison,
        "worker_isolation": isolation,
        "event_frames": event_frames,
    }


def _success_publish_event_details(
    *,
    features: pd.DataFrame,
    summary: Mapping[str, Any],
    input_before: Mapping[str, Any],
    authorization: Mapping[str, Any],
    claim: Mapping[str, Any],
) -> dict[str, Any]:
    nonce = _require_hex64(claim.get("campaign_nonce"), "campaign_nonce")
    return {
        "decision": summary.get("decision"),
        "event_count": int(len(features)),
        "event_feature_sha256": _frame_sha256(features),
        "summary_payload_sha256": hashlib.sha256(
            _stable_json_bytes(summary)
        ).hexdigest(),
        "input_file_contract_sha256": input_before.get("file_contract_sha256"),
        "runtime_contract_sha256": input_before.get("runtime_contract_sha256"),
        "authorization_payload_sha256": hashlib.sha256(
            _stable_json_bytes(authorization)
        ).hexdigest(),
        "claim_payload_sha256": hashlib.sha256(
            _stable_json_bytes(claim)
        ).hexdigest(),
        "stage_gates_passed": summary.get("stage001_gates", {}).get("passed"),
        "attempt_dir": str(
            (ARTIFACT_PARENT.resolve() / f".{STAGE}_{nonce[:12]}").resolve()
        ),
        "final_dir": str(FINAL_DIR.resolve()),
    }


def _validate_success_publishing_event(
    event: Mapping[str, Any],
    *,
    features: pd.DataFrame,
    summary: Mapping[str, Any],
    input_before: Mapping[str, Any],
    authorization: Mapping[str, Any],
    claim: Mapping[str, Any],
) -> dict[str, Any]:
    if set(event) != EXECUTION_EVENT_FIELDS:
        raise Stage001Error("success_execution_event_schema_invalid")
    counters = _validate_counter_schema(event.get("counters", {}))
    expected_details = _success_publish_event_details(
        features=features,
        summary=summary,
        input_before=input_before,
        authorization=authorization,
        claim=claim,
    )
    details = event.get("details")
    if (
        event.get("schema_version") != 1
        or event.get("stage") != STAGE
        or event.get("line_id") != LINE_ID
        or event.get("campaign_nonce") != claim.get("campaign_nonce")
        or event.get("lease_id") != claim.get("lease_id")
        or event.get("status") != "running"
        or event.get("phase") != "publishing_success"
        or int(event.get("sequence", -1)) != 6
        or event.get("error") is not None
        or any(counters.values())
        or not isinstance(details, Mapping)
        or set(details) != SUCCESS_PUBLISH_EVENT_DETAIL_FIELDS
        or dict(details) != expected_details
    ):
        raise Stage001Error("success_execution_event_binding_invalid")
    created = _receipt_timestamp(event.get("created_at"), "event_created_at")
    updated = _receipt_timestamp(event.get("updated_at"), "event_updated_at")
    if updated < created:
        raise Stage001Error("success_execution_event_timestamp_invalid")
    return dict(event)


def _success_completed_event_details(
    root: Path,
    publishing_event: Mapping[str, Any],
    *,
    attempt_cleanup_completed: bool,
    attempt_cleanup_error: str | None,
) -> dict[str, Any]:
    details = publishing_event.get("details")
    if not isinstance(details, Mapping):
        raise Stage001Error("success_execution_event_details_missing")
    return {
        **dict(details),
        "publishing_event_sha256": hashlib.sha256(
            _stable_json_bytes(publishing_event)
        ).hexdigest(),
        "summary_file_sha256": _sha256(root / "summary.json"),
        "artifact_manifest_sha256": _sha256(root / "artifact_manifest.json"),
        "attempt_cleanup_completed": bool(attempt_cleanup_completed),
        "attempt_cleanup_error": attempt_cleanup_error,
    }


def _validate_current_success_event(
    current: Mapping[str, Any],
    *,
    publishing_event: Mapping[str, Any],
    root: Path,
) -> str:
    if current.get("status") == "running":
        if dict(current) != dict(publishing_event):
            raise Stage001Error("success_current_running_event_drift")
        return "running"
    if set(current) != EXECUTION_EVENT_FIELDS:
        raise Stage001Error("success_current_completed_event_schema_invalid")
    details = current.get("details")
    if not isinstance(details, Mapping) or set(details) != SUCCESS_COMPLETED_EVENT_DETAIL_FIELDS:
        raise Stage001Error("success_current_completed_event_details_invalid")
    cleanup_completed = details.get("attempt_cleanup_completed")
    cleanup_error = details.get("attempt_cleanup_error")
    if not isinstance(cleanup_completed, bool) or (
        cleanup_error is not None and not isinstance(cleanup_error, str)
    ):
        raise Stage001Error("success_current_completed_event_cleanup_invalid")
    expected_details = _success_completed_event_details(
        root,
        publishing_event,
        attempt_cleanup_completed=cleanup_completed,
        attempt_cleanup_error=cleanup_error,
    )
    counters = _validate_counter_schema(current.get("counters", {}))
    if (
        current.get("schema_version") != 1
        or current.get("stage") != STAGE
        or current.get("line_id") != LINE_ID
        or current.get("campaign_nonce") != publishing_event.get("campaign_nonce")
        or current.get("lease_id") != publishing_event.get("lease_id")
        or current.get("status") != "completed"
        or current.get("phase") != "published"
        or int(current.get("sequence", -1))
        != int(publishing_event.get("sequence", -2)) + 1
        or current.get("created_at") != publishing_event.get("created_at")
        or current.get("error") is not None
        or any(counters.values())
        or dict(details) != expected_details
    ):
        raise Stage001Error("success_current_completed_event_binding_invalid")
    published_at = _receipt_timestamp(
        publishing_event.get("updated_at"),
        "publishing_event_updated_at",
    )
    completed_at = _receipt_timestamp(
        current.get("updated_at"),
        "completed_event_updated_at",
    )
    if completed_at < published_at:
        raise Stage001Error("success_current_completed_event_timestamp_invalid")
    return "completed"


def _validate_success_claim_and_authorization(
    root: Path,
    *,
    input_before: Mapping[str, Any],
    expected_claim: Mapping[str, Any] | None,
    revalidate_current_authorization: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    claim = _read_json_mapping(root / "execution_claim.json", "success_execution_claim")
    authorization = _read_json_mapping(
        root / "authorization_receipt.json",
        "success_authorization_receipt",
    )
    if set(claim) != EXECUTION_CLAIM_FIELDS:
        raise Stage001Error("success_execution_claim_schema_invalid")
    if set(authorization) != AUTHORIZATION_RECEIPT_FIELDS:
        raise Stage001Error("success_authorization_schema_invalid")
    if expected_claim is not None and claim != dict(expected_claim):
        raise Stage001Error("success_execution_claim_state_drift")

    nonce = _require_hex64(claim.get("campaign_nonce"), "campaign_nonce")
    lease = _require_hex64(claim.get("lease_id"), "lease_id")
    authorization_payload_sha = hashlib.sha256(
        _stable_json_bytes(authorization)
    ).hexdigest()
    if (
        claim.get("schema_version") != 1
        or claim.get("stage") != STAGE
        or claim.get("line_id") != LINE_ID
        or claim.get("scope") != AUTHORIZATION_SCOPE
        or claim.get("replay_permitted") is not False
        or not Path(str(claim.get("authorization_path", ""))).is_absolute()
        or HEX64.fullmatch(str(claim.get("authorization_sha256", ""))) is None
        or HEX64.fullmatch(str(claim.get("authorization_payload_sha256", ""))) is None
        or claim.get("input_file_contract_sha256")
        != input_before.get("file_contract_sha256")
    ):
        raise Stage001Error("success_execution_claim_binding_invalid")
    try:
        claimed = _parse_timestamp(claim.get("claimed_at"), "claimed_at")
    except Stage001Error as exc:
        raise Stage001Error("success_execution_claim_timestamp_invalid") from exc

    bound_files = authorization.get("bound_files")
    bound_files_valid = bool(bound_files) and isinstance(bound_files, Mapping)
    if bound_files_valid:
        for item in bound_files.values():
            if (
                not isinstance(item, Mapping)
                or set(item) != {"path", "sha256"}
                or not Path(str(item.get("path", ""))).is_absolute()
                or HEX64.fullmatch(str(item.get("sha256", ""))) is None
            ):
                bound_files_valid = False
                break
    if (
        authorization.get("schema_version") != 1
        or authorization.get("stage") != STAGE
        or authorization.get("scope") != AUTHORIZATION_SCOPE
        or authorization.get("decision") != REQUIRED_REVIEW_DECISION
        or authorization.get("campaign_nonce") != nonce
        or authorization.get("lease_id") != lease
        or authorization.get("input_file_contract_sha256")
        != input_before.get("file_contract_sha256")
        or claim.get("authorization_payload_sha256") != authorization_payload_sha
        or not bound_files_valid
    ):
        raise Stage001Error("success_authorization_binding_invalid")
    try:
        issued = _parse_timestamp(authorization.get("issued_at"), "issued_at")
        expires = _parse_timestamp(authorization.get("expires_at"), "expires_at")
    except Stage001Error as exc:
        raise Stage001Error("success_authorization_timestamp_invalid") from exc
    if expires <= issued or not (issued <= claimed < expires):
        raise Stage001Error("success_authorization_window_invalid")
    if revalidate_current_authorization:
        try:
            current_authorization_path = Path(
                str(claim["authorization_path"])
            ).resolve(strict=True)
        except (KeyError, OSError, RuntimeError) as exc:
            raise Stage001Error("success_current_authorization_missing") from exc
        current_authorization, current_authorization_sha256 = (
            _read_json_mapping_bytes_once(
                current_authorization_path,
                "success_current_authorization",
            )
        )
        if current_authorization_sha256 != claim.get("authorization_sha256"):
            raise Stage001Error("success_current_authorization_identity_drift")
        if current_authorization != authorization:
            raise Stage001Error("success_current_authorization_payload_drift")
        try:
            validate_authorization(
                current_authorization,
                authorization_bound_files(),
                expected_input_contract_sha256=str(
                    input_before["file_contract_sha256"]
                ),
                now=claimed,
            )
        except Stage001Error as exc:
            raise Stage001Error("success_current_authorization_invalid") from exc
    return claim, authorization


def _validate_success_summary(
    root: Path,
    *,
    summary: Mapping[str, Any],
    claim: Mapping[str, Any],
    input_before: Mapping[str, Any],
    features: pd.DataFrame,
    worker_evidence: Mapping[str, Any],
) -> None:
    if set(summary) != SUCCESS_SUMMARY_FIELDS:
        raise Stage001Error("success_summary_schema_invalid")
    nonce = str(claim["campaign_nonce"])
    lease = str(claim["lease_id"])
    formal_identity = input_before.get("formal_identity")
    counters = _validate_counter_schema(summary.get("sensitive_counters", {}))
    if (
        summary.get("schema_version") != 1
        or summary.get("stage") != STAGE
        or summary.get("line_id") != LINE_ID
        or summary.get("campaign_nonce") != nonce
        or summary.get("lease_id") != lease
        or summary.get("analysis_start") != START.date().isoformat()
        or summary.get("analysis_end") != END.date().isoformat()
        or summary.get("cold_worker_count") != 2
        or summary.get("baseline_replay_count") != 2
        or summary.get("formal_identity") != formal_identity
        or summary.get("trains_model") is not False
        or summary.get("reads_or_builds_labels") is not False
        or summary.get("publishes_backtest_performance") is not False
        or summary.get("independent_postrun_review_required") is not True
        or summary.get("replay_permitted") is not False
        or any(counters.values())
    ):
        raise Stage001Error("success_summary_binding_invalid")
    try:
        _receipt_timestamp(summary.get("created_at"), "summary_created_at")
    except Stage001Error as exc:
        raise Stage001Error("success_summary_timestamp_invalid") from exc

    feature_module = _load_feature_module()
    feature_module._validate_output_schema(features)
    observed_qualification = feature_module.evaluate_feature_qualification(features)
    if summary.get("feature_qualification") != observed_qualification:
        raise Stage001Error("success_summary_feature_qualification_drift")

    event_sha = _frame_sha256(features)
    event_count = int(len(features))
    workers = worker_evidence.get("workers")
    if not isinstance(workers, list) or len(workers) != 2:
        raise Stage001Error("success_worker_receipt_pair_invalid")
    for worker in workers:
        if (
            not isinstance(worker, Mapping)
            or worker.get("campaign_nonce") != nonce
            or worker.get("lease_id") != lease
            or worker.get("formal_identity") != formal_identity
            or worker.get("event_count") != event_count
            or worker.get("event_feature_sha256") != event_sha
        ):
            raise Stage001Error("success_worker_receipt_binding_invalid")

    comparison = worker_evidence.get("worker_comparison")
    isolation = worker_evidence.get("worker_isolation")
    if not isinstance(comparison, Mapping) or summary.get(
        "worker_comparison"
    ) != dict(comparison):
        raise Stage001Error("success_summary_worker_comparison_drift")
    if not isinstance(isolation, Mapping) or summary.get(
        "worker_isolation"
    ) != dict(isolation):
        raise Stage001Error("success_summary_worker_isolation_drift")

    expected_stage_gates = evaluate_stage001_gates(
        formal_identity_exact=True,
        execution_identity_exact=True,
        interval_exact=True,
        worker_isolation=isolation,
        feature_qualification=observed_qualification,
        worker_comparison=comparison,
        identity_stable=True,
        eligibility_trace_exact=True,
        fixed_fu_cutoff_excluded=True,
        forbidden_output_columns_absent=True,
        production_unchanged=True,
        event_ledger_durable=True,
        sensitive_counters=counters,
    )
    stage_gates = summary.get("stage001_gates")
    if stage_gates != expected_stage_gates:
        raise Stage001Error("success_summary_stage_gates_drift")
    expected_decision = (
        "stage001_formal_event_feature_qualification_pass_require_independent_review"
        if expected_stage_gates["passed"]
        else "stage001_formal_event_feature_qualification_fail_close_no_rerun"
    )
    if summary.get("decision") != expected_decision:
        raise Stage001Error("success_summary_decision_drift")

    if (root / "report.md").read_text(encoding="utf-8") != _report(summary):
        raise Stage001Error("success_report_drift")
    try:
        pd.testing.assert_frame_equal(
            pd.read_csv(root / "event_coverage.csv"),
            _coverage_frame(observed_qualification["metrics"]),
            check_dtype=False,
        )
        pd.testing.assert_frame_equal(
            pd.read_csv(root / "feature_diagnostics.csv"),
            _feature_diagnostics_frame(observed_qualification["metrics"]),
            check_dtype=False,
        )
    except (OSError, ValueError, AssertionError) as exc:
        raise Stage001Error("success_diagnostic_frames_drift") from exc


def _validate_success_bundle(
    root: Path,
    *,
    expected_claim: Mapping[str, Any] | None = None,
    revalidate_current_inputs: bool = True,
    revalidate_current_authorization: bool = True,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    observed_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if observed_files != SUCCESS_BUNDLE_FILE_SET:
        raise Stage001Error("success_file_set_drift")
    input_manifest = _read_json_mapping(
        root / "input_manifest.json",
        "success_input_manifest",
    )
    _validate_input_manifest_payload(
        input_manifest,
        label="success_input_manifest",
        require_frozen_count=False,
    )
    identities = _read_json_mapping(
        root / "input_identities.json",
        "success_input_identities",
    )
    if set(identities) != {"before", "after"}:
        raise Stage001Error("success_input_identities_schema_invalid")
    input_before = identities["before"]
    input_after = identities["after"]
    if not isinstance(input_before, Mapping) or not isinstance(input_after, Mapping):
        raise Stage001Error("success_input_identities_item_invalid")
    _validate_input_manifest_payload(
        input_before,
        label="success_input_before",
        require_frozen_count=False,
    )
    _validate_input_manifest_payload(
        input_after,
        label="success_input_after",
        require_frozen_count=False,
    )
    if input_manifest != dict(input_before):
        raise Stage001Error("success_input_manifest_before_drift")
    assert_identity_stable(input_before, input_after)
    if (
        input_before.get("input_file_count") != input_after.get("input_file_count")
        or input_before.get("input_logical_key_sha256")
        != input_after.get("input_logical_key_sha256")
    ):
        raise Stage001Error("success_input_inventory_drift")
    if revalidate_current_inputs:
        _assert_current_input_manifest_matches(input_before)
    try:
        before_sha = str(identities["before"]["files"]["source_database"]["sha256"])
        after_sha = str(identities["after"]["files"]["source_database"]["sha256"])
    except (KeyError, TypeError) as exc:
        raise Stage001Error("success_source_database_identity_missing") from exc
    if HEX64.fullmatch(before_sha) is None or before_sha != after_sha:
        raise Stage001Error("success_source_database_identity_drift")
    claim, authorization = _validate_success_claim_and_authorization(
        root,
        input_before=input_before,
        expected_claim=expected_claim,
        revalidate_current_authorization=revalidate_current_authorization,
    )
    try:
        features = pd.read_csv(
            root / "event_features.csv.gz",
            compression="gzip",
            float_precision="round_trip",
        )
    except (OSError, ValueError) as exc:
        raise Stage001Error("success_event_features_unreadable") from exc
    worker_evidence = _validate_portable_worker_receipts(
        root,
        input_manifest=input_before,
        expected_campaign_nonce=str(claim["campaign_nonce"]),
        expected_lease_id=str(claim["lease_id"]),
    )
    worker_shas = {
        str(item.get("event_feature_sha256", ""))
        for item in worker_evidence["workers"]
    }
    worker_counts = {
        int(item.get("event_count", -1))
        for item in worker_evidence["workers"]
    }
    if worker_shas != {_frame_sha256(features)} or worker_counts != {len(features)}:
        raise Stage001Error("success_event_feature_sha_drift")
    summary = _read_json_mapping(root / "summary.json", "success_summary")
    _validate_success_summary(
        root,
        summary=summary,
        claim=claim,
        input_before=input_before,
        features=features,
        worker_evidence=worker_evidence,
    )
    publishing_event = _read_json_mapping(
        root / "execution_event.json",
        "success_execution_event",
    )
    _validate_success_publishing_event(
        publishing_event,
        features=features,
        summary=summary,
        input_before=input_before,
        authorization=authorization,
        claim=claim,
    )
    manifest = _read_json_mapping(
        root / "artifact_manifest.json",
        "success_artifact_manifest",
    )
    if manifest != _artifact_manifest(root):
        raise Stage001Error("success_artifact_manifest_drift")
    return {
        **worker_evidence,
        "input_manifest": input_manifest,
        "authorization": authorization,
        "claim": claim,
        "publishing_event": publishing_event,
        "summary": summary,
    }


def _publish_success_bundle(
    attempt_dir: Path,
    *,
    features: pd.DataFrame,
    summary: Mapping[str, Any],
    input_before: Mapping[str, Any],
    input_after: Mapping[str, Any],
    worker_receipts: list[Mapping[str, Any]],
    authorization: Mapping[str, Any],
    claim: Mapping[str, Any],
    execution_event: Mapping[str, Any],
) -> dict[str, Any]:
    attempt_input_manifest = _read_json_mapping(
        attempt_dir / "input_manifest.json",
        "attempt_input_manifest",
    )
    if attempt_input_manifest != dict(input_before):
        raise Stage001Error("attempt_input_manifest_drift")
    _validate_input_manifest_payload(
        input_before,
        label="publish_input_before",
        require_frozen_count=False,
    )
    _validate_input_manifest_payload(
        input_after,
        label="publish_input_after",
        require_frozen_count=False,
    )
    assert_identity_stable(input_before, input_after)
    _validate_success_publishing_event(
        execution_event,
        features=features,
        summary=summary,
        input_before=input_before,
        authorization=authorization,
        claim=claim,
    )
    publish = ARTIFACT_PARENT / f"{attempt_dir.name}.publish"
    publish.mkdir(parents=True, exist_ok=False, mode=0o700)
    _write_deterministic_gzip_csv(publish / "event_features.csv.gz", features)
    _coverage_frame(summary["feature_qualification"]["metrics"]).to_csv(
        publish / "event_coverage.csv",
        index=False,
        lineterminator="\n",
    )
    _feature_diagnostics_frame(summary["feature_qualification"]["metrics"]).to_csv(
        publish / "feature_diagnostics.csv",
        index=False,
        lineterminator="\n",
    )
    shutil.copyfile(attempt_dir / "input_manifest.json", publish / "input_manifest.json")
    _write_json(
        publish / "input_identities.json",
        {"before": input_before, "after": input_after},
    )
    _write_json(
        publish / "worker_receipts.json",
        _portable_worker_receipts(attempt_dir, publish, worker_receipts),
    )
    _write_json(publish / "authorization_receipt.json", authorization)
    _write_json(publish / "execution_claim.json", claim)
    _write_json(publish / "execution_event.json", execution_event)
    _write_json(publish / "summary.json", summary)
    (publish / "report.md").write_text(_report(summary), encoding="utf-8")
    _write_json(publish / "artifact_manifest.json", _artifact_manifest(publish))

    _validate_success_bundle(
        publish,
        expected_claim=claim,
        revalidate_current_inputs=True,
        revalidate_current_authorization=True,
    )
    atomic_publish_directory(publish, FINAL_DIR)
    _validate_success_bundle(
        FINAL_DIR,
        expected_claim=claim,
        revalidate_current_inputs=True,
        revalidate_current_authorization=True,
    )
    cleanup = {
        "attempt_cleanup_completed": True,
        "attempt_cleanup_error": None,
    }
    try:
        shutil.rmtree(attempt_dir)
        _fsync_directory(attempt_dir.parent)
    except OSError as exc:
        cleanup = {
            "attempt_cleanup_completed": False,
            "attempt_cleanup_error": f"{type(exc).__name__}:{exc}",
        }
    _validate_success_bundle(
        FINAL_DIR,
        expected_claim=claim,
        revalidate_current_inputs=True,
        revalidate_current_authorization=True,
    )
    return cleanup


def _complete_success_publication(
    *,
    claim: Mapping[str, Any],
    publishing_event: Mapping[str, Any],
    counters: Mapping[str, Any],
    cleanup: Mapping[str, Any],
) -> None:
    if set(cleanup) != {
        "attempt_cleanup_completed",
        "attempt_cleanup_error",
    }:
        raise Stage001Error("success_cleanup_schema_invalid")
    cleanup_completed = cleanup["attempt_cleanup_completed"]
    cleanup_error = cleanup["attempt_cleanup_error"]
    if not isinstance(cleanup_completed, bool) or (
        cleanup_error is not None and not isinstance(cleanup_error, str)
    ):
        raise Stage001Error("success_cleanup_value_invalid")
    if cleanup_completed and cleanup_error is not None:
        raise Stage001Error("success_cleanup_result_inconsistent")
    if not cleanup_completed and not cleanup_error:
        raise Stage001Error("success_cleanup_result_inconsistent")
    validated_counters = _validate_counter_schema(counters)
    if any(validated_counters.values()):
        raise Stage001Error("success_completion_sensitive_counters_nonzero")

    with _execution_event_lock(
        EXECUTION_EVENT_PATH,
        expected_claim=claim,
    ) as lock_descriptor:
        evidence = _validate_success_bundle(
            FINAL_DIR,
            expected_claim=claim,
            revalidate_current_inputs=True,
            revalidate_current_authorization=True,
        )
        if evidence.get("publishing_event") != dict(publishing_event):
            raise Stage001Error("success_publishing_event_drift_before_completion")
        current_event, _, _ = _read_current_execution_event(
            EXECUTION_EVENT_PATH,
            lock_descriptor=lock_descriptor,
        )
        current_status = _validate_current_success_event(
            current_event,
            publishing_event=publishing_event,
            root=FINAL_DIR,
        )
        if current_status == "completed":
            return
        if current_status != "running":
            raise Stage001Error("success_event_not_running_before_completion")
        _replace_execution_event_if_matches_locked(
            EXECUTION_EVENT_PATH,
            lock_descriptor=lock_descriptor,
            expected_current=publishing_event,
            expected_claim=claim,
            campaign_nonce=str(claim["campaign_nonce"]),
            lease_id=str(claim["lease_id"]),
            status="completed",
            phase="published",
            counters=validated_counters,
            details=_success_completed_event_details(
                FINAL_DIR,
                publishing_event,
                attempt_cleanup_completed=cleanup_completed,
                attempt_cleanup_error=cleanup_error,
            ),
        )
        completed_event, _, _ = _read_current_execution_event(
            EXECUTION_EVENT_PATH,
            lock_descriptor=lock_descriptor,
        )
        _validate_current_success_event(
            completed_event,
            publishing_event=publishing_event,
            root=FINAL_DIR,
        )


FAILURE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "stage",
        "line_id",
        "campaign_nonce",
        "lease_id",
        "failed_at",
        "failure_phase",
        "error_type",
        "error",
        "sensitive_counters",
        "replay_permitted",
        "qualification_claim_permitted",
        "input_before",
    }
)


def _failure_publish_fault_point(_phase: str) -> None:
    return None


def _failure_staging_path(campaign_nonce: str, lease_id: str) -> Path:
    nonce = _require_hex64(campaign_nonce, "campaign_nonce")
    lease = _require_hex64(lease_id, "lease_id")
    return ARTIFACT_PARENT / f".{FAILURE_DIR.name}.{nonce}.{lease}.staging"


def _failure_staging_binding(staging: Path) -> tuple[str, str]:
    prefix = f".{FAILURE_DIR.name}."
    suffix = ".staging"
    if not staging.name.startswith(prefix) or not staging.name.endswith(suffix):
        raise Stage001Error("failure_staging_name_invalid")
    body = staging.name[len(prefix) : -len(suffix)]
    parts = body.split(".")
    if (
        len(parts) != 2
        or HEX64.fullmatch(parts[0]) is None
        or HEX64.fullmatch(parts[1]) is None
    ):
        raise Stage001Error("failure_staging_binding_name_invalid")
    return parts[0], parts[1]


def _failure_receipt_payload(
    *,
    error: BaseException,
    campaign_nonce: str,
    lease_id: str,
    phase: str,
    input_before: Mapping[str, Any] | None,
    sensitive_counters: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "stage": STAGE,
        "line_id": LINE_ID,
        "campaign_nonce": _require_hex64(campaign_nonce, "campaign_nonce"),
        "lease_id": _require_hex64(lease_id, "lease_id"),
        "failed_at": _now(),
        "failure_phase": str(phase),
        "error_type": type(error).__name__,
        "error": str(error),
        "sensitive_counters": _validate_counter_schema(sensitive_counters),
        "replay_permitted": False,
        "qualification_claim_permitted": False,
        "input_before": input_before,
    }


def _failure_receipt_matches(
    receipt: Mapping[str, Any] | None,
    *,
    campaign_nonce: str,
    lease_id: str,
) -> bool:
    if not receipt or set(receipt) != FAILURE_RECEIPT_FIELDS:
        return False
    try:
        counters = _validate_counter_schema(receipt.get("sensitive_counters", {}))
    except Stage001Error:
        return False
    return bool(
        receipt.get("schema_version") == 1
        and receipt.get("stage") == STAGE
        and receipt.get("line_id") == LINE_ID
        and receipt.get("campaign_nonce") == campaign_nonce
        and receipt.get("lease_id") == lease_id
        and receipt.get("replay_permitted") is False
        and receipt.get("qualification_claim_permitted") is False
        and set(counters) == set(SENSITIVE_COUNTER_KEYS)
    )


def _validate_failure_bundle(
    root: Path,
    *,
    campaign_nonce: str,
    lease_id: str,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    receipt = _read_json_mapping(
        root / "failure_receipt.json",
        "failure_receipt",
    )
    if not _failure_receipt_matches(
        receipt,
        campaign_nonce=campaign_nonce,
        lease_id=lease_id,
    ):
        raise Stage001Error("failure_receipt_binding_invalid")
    manifest = _read_json_mapping(
        root / "artifact_manifest.json",
        "failure_artifact_manifest",
    )
    if manifest != _artifact_manifest(root):
        raise Stage001Error("failure_artifact_manifest_drift")
    return receipt


def _quarantine_failure_file(path: Path) -> None:
    if not path.exists():
        return
    candidate = path.with_name(f"{path.name}.interrupted")
    index = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.interrupted.{index}")
        index += 1
    os.replace(path, candidate)
    if candidate.is_file():
        os.chmod(candidate, 0o600)
    _fsync_directory(path.parent)


def _recover_failure_bundle_staging(
    *,
    campaign_nonce: str,
    lease_id: str,
    sensitive_counters: Mapping[str, Any],
    event_phase: str,
) -> dict[str, int] | None:
    if FAILURE_DIR.exists():
        return None
    pattern = f".{FAILURE_DIR.name}.*.staging"
    candidates = sorted(ARTIFACT_PARENT.glob(pattern))
    if not candidates:
        return None
    if len(candidates) != 1:
        raise Stage001Error("failure_staging_ambiguous")
    staging = candidates[0]
    nonce, lease = _failure_staging_binding(staging)
    if nonce != campaign_nonce or lease != lease_id:
        raise Stage001Error("failure_staging_binding_mismatch")

    event_counters = _validate_counter_schema(sensitive_counters)
    receipt_path = staging / "failure_receipt.json"
    receipt = _read_state_json(receipt_path)
    if _failure_receipt_matches(
        receipt,
        campaign_nonce=nonce,
        lease_id=lease,
    ):
        receipt_counters = _validate_counter_schema(receipt["sensitive_counters"])
        merged_counters = monotonic_sensitive_counters(
            event_counters,
            receipt_counters,
        )
        if merged_counters != receipt_counters:
            updated_receipt = dict(receipt)
            updated_receipt["sensitive_counters"] = merged_counters
            _atomic_replace_json(receipt_path, updated_receipt)
        else:
            os.chmod(receipt_path, 0o600)
    else:
        merged_counters = event_counters
        _quarantine_failure_file(receipt_path)
        create_exclusive_json(
            receipt_path,
            _failure_receipt_payload(
                error=Stage001Error(
                    f"recovered_interrupted_failure_publish:{event_phase}"
                ),
                campaign_nonce=nonce,
                lease_id=lease,
                phase="recovered_interrupted_failure_bundle_publish",
                input_before=None,
                sensitive_counters=merged_counters,
            ),
        )
    manifest_path = staging / "artifact_manifest.json"
    existing_manifest = _read_state_json(manifest_path)
    if existing_manifest != _artifact_manifest(staging):
        _quarantine_failure_file(manifest_path)
        _atomic_replace_json(manifest_path, _artifact_manifest(staging))
    _validate_failure_bundle(
        staging,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    _fsync_tree(staging)
    atomic_publish_directory(staging, FAILURE_DIR)
    _validate_failure_bundle(
        FAILURE_DIR,
        campaign_nonce=nonce,
        lease_id=lease,
    )
    return merged_counters


def _persist_failure_counters_before_publish(
    *,
    campaign_nonce: str,
    lease_id: str,
    phase: str,
    sensitive_counters: Mapping[str, Any],
) -> dict[str, int]:
    counters = _validate_counter_schema(sensitive_counters)
    if not EXECUTION_EVENT_PATH.is_file():
        return counters
    event = read_execution_event(EXECUTION_EVENT_PATH)
    if not _event_matches_binding(event, campaign_nonce, lease_id):
        raise Stage001Error("failure_publish_event_binding_invalid")
    current_status = str(event.get("status", ""))
    if current_status == "completed":
        raise Stage001Error("failure_publish_after_completed_forbidden")
    current_counters = _validate_counter_schema(event.get("counters", {}))
    merged = monotonic_sensitive_counters(current_counters, counters)
    next_status = "failed" if current_status == "failed" else "running"
    if merged != current_counters or current_status == "claimed":
        update_execution_event(
            EXECUTION_EVENT_PATH,
            campaign_nonce=campaign_nonce,
            lease_id=lease_id,
            status=next_status,
            phase=f"failure_bundle_publish:{phase}",
            counters=merged,
            error=event.get("error"),
        )
    return merged


def _publish_failure_bundle(
    attempt_dir: Path | None,
    *,
    error: BaseException,
    campaign_nonce: str,
    lease_id: str,
    phase: str,
    input_before: Mapping[str, Any] | None,
    sensitive_counters: Mapping[str, Any],
) -> None:
    nonce = _require_hex64(campaign_nonce, "campaign_nonce")
    lease = _require_hex64(lease_id, "lease_id")
    counters = _persist_failure_counters_before_publish(
        campaign_nonce=nonce,
        lease_id=lease,
        phase=phase,
        sensitive_counters=sensitive_counters,
    )
    if FAILURE_DIR.exists():
        _validate_failure_bundle(
            FAILURE_DIR,
            campaign_nonce=nonce,
            lease_id=lease,
        )
        return
    ARTIFACT_PARENT.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = _failure_staging_path(nonce, lease)
    if staging.exists():
        _recover_failure_bundle_staging(
            campaign_nonce=nonce,
            lease_id=lease,
            sensitive_counters=counters,
            event_phase=phase,
        )
    else:
        staging.mkdir(mode=0o700)
        _fsync_directory(ARTIFACT_PARENT)
        _failure_publish_fault_point("after_staging_mkdir")
        create_exclusive_json(
            staging / "failure_receipt.json",
            _failure_receipt_payload(
                error=error,
                campaign_nonce=nonce,
                lease_id=lease,
                phase=phase,
                input_before=input_before,
                sensitive_counters=counters,
            ),
        )
        _failure_publish_fault_point("after_receipt_write")
        create_exclusive_json(
            staging / "artifact_manifest.json",
            _artifact_manifest(staging),
        )
        _failure_publish_fault_point("after_manifest_write")
        _validate_failure_bundle(
            staging,
            campaign_nonce=nonce,
            lease_id=lease,
        )
        _fsync_tree(staging)
        _failure_publish_fault_point("after_pre_rename_fsync")
        atomic_publish_directory(staging, FAILURE_DIR)
        _failure_publish_fault_point("after_atomic_rename")
        _validate_failure_bundle(
            FAILURE_DIR,
            campaign_nonce=nonce,
            lease_id=lease,
        )
    if attempt_dir is not None and attempt_dir.exists():
        try:
            shutil.rmtree(attempt_dir)
            _fsync_directory(attempt_dir.parent)
        except OSError:
            pass


def run_stage001(authorization_path: Path) -> dict[str, Any]:
    reconcile_execution_state()
    for path in (EXECUTION_STATE_DIR, FINAL_DIR, FAILURE_DIR):
        if path.exists():
            raise Stage001Error(f"stage001_already_consumed_or_published:{path}")
    validate_prerun_decision()
    input_before = build_input_manifest()
    authorization, authorization_sha256 = _read_json_mapping_bytes_once(
        authorization_path,
        "stage001_authorization",
    )
    binding = validate_authorization(
        authorization,
        authorization_bound_files(),
        expected_input_contract_sha256=str(input_before["file_contract_sha256"]),
    )
    nonce = binding["campaign_nonce"]
    lease_id = binding["lease_id"]
    claim = {
        "schema_version": 1,
        "stage": STAGE,
        "line_id": LINE_ID,
        "scope": AUTHORIZATION_SCOPE,
        "campaign_nonce": nonce,
        "lease_id": lease_id,
        "authorization_path": str(authorization_path.resolve()),
        "authorization_sha256": authorization_sha256,
        "authorization_payload_sha256": hashlib.sha256(
            _stable_json_bytes(authorization)
        ).hexdigest(),
        "input_file_contract_sha256": input_before["file_contract_sha256"],
        "claimed_at": _now(),
        "replay_permitted": False,
    }
    create_execution_state(
        EXECUTION_STATE_DIR,
        claim=claim,
        campaign_nonce=nonce,
        lease_id=lease_id,
    )

    attempt_dir: Path | None = None
    phase = "preflight"
    counters = zero_sensitive_counters()
    try:
        ARTIFACT_PARENT.mkdir(parents=True, exist_ok=True)
        attempt_dir = ARTIFACT_PARENT / f".{STAGE}_{nonce[:12]}"
        attempt_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        input_manifest_path = attempt_dir / "input_manifest.json"
        _write_json(input_manifest_path, input_before)
        update_execution_event(
            EXECUTION_EVENT_PATH,
            campaign_nonce=nonce,
            lease_id=lease_id,
            status="running",
            phase="worker_a1",
            counters=counters,
        )
        phase = "worker_a1"
        receipt_a1 = _run_worker(
            "A1",
            attempt_dir,
            input_manifest_path,
            input_before,
            campaign_nonce=nonce,
            lease_id=lease_id,
            counters=counters,
        )
        counters = merge_sensitive_counters(counters, receipt_a1)
        phase = "worker_a2"
        update_execution_event(
            EXECUTION_EVENT_PATH,
            campaign_nonce=nonce,
            lease_id=lease_id,
            status="running",
            phase=phase,
            counters=counters,
            details={"a1_event_count": receipt_a1["event_count"]},
        )
        receipt_a2 = _run_worker(
            "A2",
            attempt_dir,
            input_manifest_path,
            input_before,
            campaign_nonce=nonce,
            lease_id=lease_id,
            counters=counters,
        )
        counters = merge_sensitive_counters(counters, receipt_a2)
        phase = "qualification"
        isolation = evaluate_worker_isolation(
            [receipt_a1, receipt_a2],
            expected_source_contract_sha256=str(input_before["file_contract_sha256"]),
            expected_database_sha256=str(
                input_before["files"]["source_database"]["sha256"]
            ),
            expected_python_executable=Path(
                input_before["files"]["python_executable"]["path"]
            ),
            expected_modules=expected_worker_modules(input_before),
            expected_formal_identity=input_before["formal_identity"],
            expected_campaign_nonce=nonce,
            expected_lease_id=lease_id,
        )
        features_a1 = pd.read_csv(
            receipt_a1["feature_path"],
            float_precision="round_trip",
        )
        features_a2 = pd.read_csv(
            receipt_a2["feature_path"],
            float_precision="round_trip",
        )
        comparison = compare_worker_frames(features_a1, features_a2, atol=1e-12)
        feature_module = _load_feature_module()
        qualification = feature_module.evaluate_feature_qualification(features_a1)
        forbidden_absent = not any(
            token in column.lower()
            for column in features_a1.columns
            for token in feature_module.FORBIDDEN_OUTPUT_TOKENS
        )
        fixed_fu_excluded = not features_a1["product_vt_symbol"].astype(str).eq(
            feature_module.FIXED_PRODUCT
        ).any()
        input_after = build_input_manifest()
        assert_identity_stable(input_before, input_after)
        repository_state()
        stage_gates = evaluate_stage001_gates(
            formal_identity_exact=input_before["formal_identity"]
            == input_after["formal_identity"],
            execution_identity_exact=all(
                receipt.get("official_live_version") == EXPECTED_OFFICIAL_VERSION
                and float(receipt.get("capital", -1.0)) == EXPECTED_CAPITAL
                for receipt in (receipt_a1, receipt_a2)
            ),
            interval_exact=all(
                receipt.get("analysis_start") == START.date().isoformat()
                and receipt.get("analysis_end") == END.date().isoformat()
                for receipt in (receipt_a1, receipt_a2)
            ),
            worker_isolation=isolation,
            feature_qualification=qualification,
            worker_comparison=comparison,
            identity_stable=True,
            eligibility_trace_exact=True,
            fixed_fu_cutoff_excluded=bool(fixed_fu_excluded),
            forbidden_output_columns_absent=bool(forbidden_absent),
            production_unchanged=True,
            event_ledger_durable=execution_ledger_is_durable(nonce, lease_id),
            sensitive_counters=counters,
        )
        decision = (
            "stage001_formal_event_feature_qualification_pass_require_independent_review"
            if stage_gates["passed"]
            else "stage001_formal_event_feature_qualification_fail_close_no_rerun"
        )
        summary = {
            "schema_version": 1,
            "stage": STAGE,
            "line_id": LINE_ID,
            "created_at": _now(),
            "campaign_nonce": nonce,
            "lease_id": lease_id,
            "analysis_start": START.date().isoformat(),
            "analysis_end": END.date().isoformat(),
            "cold_worker_count": 2,
            "baseline_replay_count": 2,
            "formal_identity": input_before["formal_identity"],
            "worker_comparison": comparison,
            "worker_isolation": isolation,
            "feature_qualification": qualification,
            "stage001_gates": stage_gates,
            "sensitive_counters": counters,
            "decision": decision,
            "trains_model": False,
            "reads_or_builds_labels": False,
            "publishes_backtest_performance": False,
            "independent_postrun_review_required": True,
            "replay_permitted": False,
        }
        phase = "publishing_success"
        update_execution_event(
            EXECUTION_EVENT_PATH,
            campaign_nonce=nonce,
            lease_id=lease_id,
            status="running",
            phase=phase,
            counters=counters,
            details=_success_publish_event_details(
                features=features_a1,
                summary=summary,
                input_before=input_before,
                authorization=authorization,
                claim=claim,
            ),
        )
        publishing_event = read_execution_event(
            EXECUTION_EVENT_PATH,
        )
        cleanup = _publish_success_bundle(
            attempt_dir,
            features=features_a1,
            summary=summary,
            input_before=input_before,
            input_after=input_after,
            worker_receipts=[receipt_a1, receipt_a2],
            authorization=authorization,
            claim=claim,
            execution_event=publishing_event,
        )
        _complete_success_publication(
            claim=claim,
            publishing_event=publishing_event,
            counters=counters,
            cleanup=cleanup,
        )
        return summary
    except BaseException as exc:
        if isinstance(exc, WorkerStage001Error):
            counters = merge_sensitive_counters(counters, exc.receipt)
        elif isinstance(exc, NetworkBlockedError):
            counters["network_connection_count"] += 1
        if FINAL_DIR.is_dir():
            try:
                reconcile_execution_state()
            except BaseException as reconcile_exc:
                raise Stage001Error(
                    "stage001_success_bundle_published_event_update_incomplete:"
                    f"initial={type(exc).__name__}:{exc}:"
                    "reconcile="
                    f"{type(reconcile_exc).__name__}:{reconcile_exc}"
                ) from reconcile_exc
            raise Stage001Error(
                "stage001_success_bundle_published_event_update_incomplete"
            ) from exc
        failure_publish_error: BaseException | None = None
        try:
            _publish_failure_bundle(
                attempt_dir,
                error=exc,
                campaign_nonce=nonce,
                lease_id=lease_id,
                phase=phase,
                input_before=input_before,
                sensitive_counters=counters,
            )
        except BaseException as publish_exc:
            failure_publish_error = publish_exc
        event_update_error: BaseException | None = None
        try:
            update_execution_event(
                EXECUTION_EVENT_PATH,
                campaign_nonce=nonce,
                lease_id=lease_id,
                status="failed",
                phase=phase,
                counters=counters,
                error=f"{type(exc).__name__}:{exc}",
            )
        except BaseException as update_exc:
            event_update_error = update_exc
        if failure_publish_error is not None or event_update_error is not None:
            publish_detail = (
                "none"
                if failure_publish_error is None
                else f"{type(failure_publish_error).__name__}:{failure_publish_error}"
            )
            update_detail = (
                "none"
                if event_update_error is None
                else f"{type(event_update_error).__name__}:{event_update_error}"
            )
            cause = event_update_error or failure_publish_error
            raise Stage001Error(
                "stage001_failure_handling_incomplete:"
                f"initial={type(exc).__name__}:{exc}:"
                f"failure_publish={publish_detail}:"
                f"event_update={update_detail}"
            ) from cause
        raise


def verify_only() -> dict[str, Any]:
    recovery = reconcile_execution_state()
    review = validate_prerun_decision()
    manifest = build_input_manifest()
    result = {
        "stage": STAGE,
        "verified_at": _now(),
        "review_decision": review["decision"],
        "file_contract_sha256": manifest["file_contract_sha256"],
        "runtime_contract_sha256": manifest["runtime_contract_sha256"],
        "formal_identity": manifest["formal_identity"],
        "recovery": recovery,
        "claim_exists": CLAIM_PATH.exists(),
        "final_exists": FINAL_DIR.exists(),
        "failure_exists": FAILURE_DIR.exists(),
    }
    if any((result["claim_exists"], result["final_exists"], result["failure_exists"])):
        raise Stage001Error("verify_only_stage_already_consumed")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=STAGE)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--worker", choices=("A1", "A2"), help=argparse.SUPPRESS)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--runtime-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--expected-manifest", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-capability", type=Path, help=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.worker:
        required = (
            args.runtime_root,
            args.worker_output,
            args.expected_manifest,
            args.worker_capability,
        )
        if any(value is None for value in required):
            raise Stage001Error("worker_arguments_missing")
        return _worker_main(args)
    if args.verify_only:
        print(json.dumps(verify_only(), ensure_ascii=False, indent=2))
        return 0
    if args.authorization is None:
        raise Stage001Error("authorization_argument_required")
    result = run_stage001(args.authorization.resolve(strict=True))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
