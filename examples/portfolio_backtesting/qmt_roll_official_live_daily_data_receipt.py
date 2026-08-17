from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
from typing import Any, Mapping

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_production_assets import (
    ProductionAssetError,
    build_production_asset_inventory,
    validate_production_asset_inventory,
)
from qmt_roll_official_execution_profile import C9_15W_PROFILE
from qmt_roll_official_pending_artifact import (
    ARTIFACT_HASH_KEYS,
    validate_pending_artifact_cohort,
)


PRODUCTION_DAILY_DATA_RECEIPT_SCHEMA_VERSION = 1
PRODUCTION_DAILY_DATA_RECEIPT_KIND = (
    "stage179_c9_15w_production_daily_data_readiness"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_FIELDS = {
    "schema_version",
    "artifact_kind",
    "generated_at_utc",
    "source_commit",
    "manifest_sha256",
    "target_cutoff_date",
    "data_inventory",
    "database_asset",
    "signal_bundle",
    "receipt_sha256",
}
_DATABASE_ASSET_FIELDS = {
    "declared_path",
    "resolved_path",
    "sha256",
    "size_bytes",
    "mtime_epoch_ns",
    "quick_check",
    "max_bar_date",
}
_SIGNAL_BUNDLE_FIELDS = {
    "signal_input_root",
    "target_date",
    "execution_profile",
    "official_live_version",
    "capital",
    "capital_label",
    "cohort_id",
    "assets",
    "ai_eligibility",
    "ai_pool_eval_date",
    "bundle_sha256",
}
_SIGNAL_ASSET_FIELDS = {
    "artifact_name",
    "relative_path",
    "sha256",
    "size_bytes",
    "mtime_epoch_ns",
}


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProductionAssetError(
            f"production_daily_data_receipt_not_canonical:{exc}"
        ) from exc


def production_daily_data_receipt_digest(
    payload: Mapping[str, Any],
) -> str:
    core = {
        key: value for key, value in payload.items() if key != "receipt_sha256"
    }
    return hashlib.sha256(_canonical_json_bytes(core)).hexdigest()


def serialize_production_daily_data_receipt(
    payload: Mapping[str, Any],
) -> bytes:
    try:
        return (
            json.dumps(
                dict(payload),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProductionAssetError(
            f"production_daily_data_receipt_not_canonical:{exc}"
        ) from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _database_asset_row(path: Path | str) -> dict[str, Any]:
    candidate = Path(os.path.abspath(Path(path).expanduser()))
    components = tuple(reversed(candidate.parents)) + (candidate,)
    user_owned_scope = False
    for component in components:
        try:
            metadata = component.lstat()
        except OSError as exc:
            raise ProductionAssetError(
                "production_daily_database_component_missing"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ProductionAssetError(
                "production_daily_database_symlink_forbidden"
            )
        if metadata.st_uid == os.getuid():
            user_owned_scope = True
        if user_owned_scope:
            if metadata.st_uid != os.getuid():
                raise ProductionAssetError(
                    "production_daily_database_owner_mismatch"
                )
            if stat.S_IMODE(metadata.st_mode) & 0o022:
                raise ProductionAssetError(
                    "production_daily_database_component_writable_by_other"
                )
    parent_metadata = candidate.parent.lstat()
    metadata = candidate.lstat()
    if (
        not stat.S_ISDIR(parent_metadata.st_mode)
        or stat.S_IMODE(parent_metadata.st_mode) & 0o077
    ):
        raise ProductionAssetError(
            "production_daily_database_parent_security_invalid"
        )
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise ProductionAssetError(
            "production_daily_database_security_invalid"
        )
    resolved = candidate.resolve(strict=True)
    try:
        connection = sqlite3.connect(
            f"file:{resolved}?mode=ro",
            uri=True,
            timeout=5.0,
        )
        try:
            quick_check_row = connection.execute("PRAGMA quick_check").fetchone()
            maximum_row = connection.execute(
                "SELECT substr(max(datetime), 1, 10) FROM dbbardata"
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ProductionAssetError(
            "production_daily_database_sqlite_invalid"
        ) from exc
    quick_check = str(quick_check_row[0] if quick_check_row else "")
    max_bar_date = str(maximum_row[0] if maximum_row else "")
    if quick_check != "ok" or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", max_bar_date):
        raise ProductionAssetError(
            "production_daily_database_semantic_invalid"
        )
    return {
        "declared_path": str(candidate),
        "resolved_path": str(resolved),
        "sha256": _sha256_file(resolved),
        "size_bytes": metadata.st_size,
        "mtime_epoch_ns": metadata.st_mtime_ns,
        "quick_check": quick_check,
        "max_bar_date": max_bar_date,
    }


def _strict_signal_file(
    *,
    root: Path,
    path: Path,
    artifact_name: str,
) -> tuple[bytes, dict[str, Any]]:
    candidate = Path(os.path.abspath(path.expanduser()))
    if candidate.parent != root:
        raise ProductionAssetError(
            f"production_signal_artifact_path_invalid:{artifact_name}"
        )
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise ProductionAssetError(
            f"production_signal_artifact_missing:{artifact_name}"
        ) from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o022
    ):
        raise ProductionAssetError(
            f"production_signal_artifact_security_invalid:{artifact_name}"
        )
    raw = candidate.read_bytes()
    return raw, {
        "artifact_name": artifact_name,
        "relative_path": candidate.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": metadata.st_size,
        "mtime_epoch_ns": metadata.st_mtime_ns,
    }


def _csv_frame(raw: bytes, *, label: str) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(raw), encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()
    except Exception as exc:
        raise ProductionAssetError(
            f"production_signal_csv_invalid:{label}"
        ) from exc


def _ai_pool_max_eval_date(raw: bytes) -> str:
    frame = _csv_frame(raw, label="ai_eligibility")
    if frame.empty or "eval_date" not in frame.columns:
        raise ProductionAssetError(
            "production_signal_ai_eligibility_eval_date_missing"
        )
    values = pd.to_datetime(frame["eval_date"], errors="coerce").dropna()
    if values.empty:
        raise ProductionAssetError(
            "production_signal_ai_eligibility_eval_date_missing"
        )
    return values.max().date().isoformat()


def _signal_bundle_row(
    *,
    signal_input_root: Path | str,
    official_ai_eligibility_path: Path | str,
    target_date: str,
) -> dict[str, Any]:
    root = Path(os.path.abspath(Path(signal_input_root).expanduser()))
    try:
        root_metadata = root.lstat()
    except OSError as exc:
        raise ProductionAssetError("production_signal_input_root_missing") from exc
    if (
        stat.S_ISLNK(root_metadata.st_mode)
        or not stat.S_ISDIR(root_metadata.st_mode)
        or root_metadata.st_uid != os.getuid()
        or stat.S_IMODE(root_metadata.st_mode) & 0o022
    ):
        raise ProductionAssetError(
            "production_signal_input_root_security_invalid"
        )
    profile = replace(
        C9_15W_PROFILE,
        summary_path=root / C9_15W_PROFILE.summary_path.name,
        signal_plan_path=root / C9_15W_PROFILE.signal_plan_path.name,
        current_positions_path=root / C9_15W_PROFILE.current_positions_path.name,
        pending_orders_path=root / C9_15W_PROFILE.pending_orders_path.name,
        pending_orders_audit_path=(
            root / C9_15W_PROFILE.pending_orders_audit_path.name
        ),
    )
    audit_before_raw, audit_row = _strict_signal_file(
        root=root,
        path=profile.pending_orders_audit_path,
        artifact_name="pending_orders_audit",
    )
    artifact_specs = (
        ("official_summary", profile.summary_path),
        ("signal_plan", profile.signal_plan_path),
        ("current_positions", profile.current_positions_path),
        ("pending_orders", profile.pending_orders_path),
    )
    raw_by_name: dict[str, bytes] = {}
    asset_rows: list[dict[str, Any]] = []
    for artifact_name, path in artifact_specs:
        raw, row = _strict_signal_file(
            root=root,
            path=path,
            artifact_name=artifact_name,
        )
        raw_by_name[artifact_name] = raw
        asset_rows.append(row)
    audit_after_raw, audit_after_row = _strict_signal_file(
        root=root,
        path=profile.pending_orders_audit_path,
        artifact_name="pending_orders_audit",
    )
    if audit_before_raw != audit_after_raw or audit_row != audit_after_row:
        raise ProductionAssetError(
            "production_signal_artifact_generation_changed"
        )
    asset_rows.append(audit_row)
    try:
        decision = json.loads(raw_by_name["official_summary"].decode("utf-8"))
        audit = json.loads(audit_after_raw.decode("utf-8"))
    except Exception as exc:
        raise ProductionAssetError(
            "production_signal_json_invalid"
        ) from exc
    if not isinstance(decision, dict) or not isinstance(audit, dict):
        raise ProductionAssetError("production_signal_json_invalid")
    pending_orders = _csv_frame(
        raw_by_name["pending_orders"],
        label="pending_orders",
    )
    hashes = {
        name: hashlib.sha256(raw_by_name[name]).hexdigest()
        for name in ARTIFACT_HASH_KEYS
    }
    try:
        validate_pending_artifact_cohort(
            profile,
            target_date=target_date,
            pending_orders=pending_orders,
            audit=audit,
            artifact_hashes=hashes,
        )
    except (TypeError, ValueError) as exc:
        raise ProductionAssetError(
            f"production_signal_pending_cohort_invalid:{exc}"
        ) from exc
    expected_decision = {
        "analysis_end": target_date,
        "latest_available_data_date": target_date,
        "execution_profile": C9_15W_PROFILE.profile_key,
        "official_live_version": C9_15W_PROFILE.official_version,
        "capital": C9_15W_PROFILE.capital,
        "capital_label": C9_15W_PROFILE.capital_label,
        "shadow_replay_ai_pool_status": "valid",
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }
    if any(decision.get(key) != value for key, value in expected_decision.items()):
        raise ProductionAssetError(
            "production_signal_decision_identity_mismatch"
        )
    if decision.get("order_api_called") is not False:
        raise ProductionAssetError(
            "production_signal_decision_order_api_nonzero"
        )
    ai_audit = decision.get("ai_pool_audit")
    if (
        not isinstance(ai_audit, dict)
        or ai_audit.get("missing_required_eval_dates") != []
    ):
        raise ProductionAssetError(
            "production_signal_ai_pool_audit_invalid"
        )
    ai_path = Path(os.path.abspath(Path(official_ai_eligibility_path).expanduser()))
    ai_root = ai_path.parent
    ai_raw, ai_row = _strict_signal_file(
        root=ai_root,
        path=ai_path,
        artifact_name="ai_eligibility",
    )
    ai_hash = hashlib.sha256(ai_raw).hexdigest()
    ai_eval_date = _ai_pool_max_eval_date(ai_raw)
    decision_ai_path = Path(str(ai_audit.get("path", ""))).expanduser()
    strategy_ai_path = Path(
        str(decision.get("strategy_ai_product_pool_eligibility_path", ""))
    ).expanduser()
    try:
        decision_paths_match = (
            decision_ai_path.resolve(strict=True) == ai_path.resolve(strict=True)
            and strategy_ai_path.resolve(strict=True) == ai_path.resolve(strict=True)
        )
    except OSError:
        decision_paths_match = False
    if (
        not decision_paths_match
        or ai_audit.get("eligibility_sha256") != ai_hash
        or ai_audit.get("max_eval_date") != ai_eval_date
    ):
        raise ProductionAssetError(
            "production_signal_ai_pool_binding_mismatch"
        )
    sorted_rows = sorted(asset_rows, key=lambda row: str(row["artifact_name"]))
    core = {
        "signal_input_root": str(root),
        "target_date": target_date,
        "execution_profile": C9_15W_PROFILE.profile_key,
        "official_live_version": C9_15W_PROFILE.official_version,
        "capital": C9_15W_PROFILE.capital,
        "capital_label": C9_15W_PROFILE.capital_label,
        "cohort_id": str(audit.get("cohort_id", "")),
        "assets": sorted_rows,
        "ai_eligibility": ai_row,
        "ai_pool_eval_date": ai_eval_date,
    }
    return {
        **core,
        "bundle_sha256": hashlib.sha256(_canonical_json_bytes(core)).hexdigest(),
    }


def build_production_daily_data_receipt(
    *,
    declared_data_link: Path | str,
    expected_data_root: Path | str,
    source_commit: str,
    manifest_sha256: str,
    target_cutoff_date: str,
    production_database_path: Path | str,
    signal_input_root: Path | str,
    official_ai_eligibility_path: Path | str,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    if not _SHA256_RE.fullmatch(str(manifest_sha256)):
        raise ProductionAssetError(
            "production_daily_data_receipt_manifest_digest_invalid"
        )
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )
    inventory = build_production_asset_inventory(
        declared_data_link=declared_data_link,
        expected_data_root=expected_data_root,
        source_commit=source_commit,
        target_cutoff_date=target_cutoff_date,
        generated_at_utc=generated,
    )
    database_asset = _database_asset_row(production_database_path)
    next_session_date = str(
        inventory["semantic_freshness"]["next_trading_session_date"]
    )
    if database_asset["max_bar_date"] not in {
        target_cutoff_date,
        next_session_date,
    }:
        raise ProductionAssetError(
            "production_daily_database_target_freshness_mismatch"
        )
    signal_bundle = _signal_bundle_row(
        signal_input_root=signal_input_root,
        official_ai_eligibility_path=official_ai_eligibility_path,
        target_date=target_cutoff_date,
    )
    core: dict[str, Any] = {
        "schema_version": PRODUCTION_DAILY_DATA_RECEIPT_SCHEMA_VERSION,
        "artifact_kind": PRODUCTION_DAILY_DATA_RECEIPT_KIND,
        "generated_at_utc": generated,
        "source_commit": source_commit,
        "manifest_sha256": manifest_sha256,
        "target_cutoff_date": target_cutoff_date,
        "data_inventory": inventory,
        "database_asset": database_asset,
        "signal_bundle": signal_bundle,
    }
    return {
        **core,
        "receipt_sha256": production_daily_data_receipt_digest(core),
    }


def validate_production_daily_data_receipt_payload(
    payload: Mapping[str, Any],
    *,
    declared_data_link: Path | str,
    expected_data_root: Path | str,
    source_commit: str,
    manifest_sha256: str,
    target_cutoff_date: str,
    production_database_path: Path | str,
    signal_input_root: Path | str,
    official_ai_eligibility_path: Path | str,
    validation_at_utc: str | None = None,
) -> dict[str, Any]:
    if set(payload) != _RECEIPT_FIELDS:
        raise ProductionAssetError(
            "production_daily_data_receipt_fields_invalid"
        )
    if (
        payload.get("schema_version")
        != PRODUCTION_DAILY_DATA_RECEIPT_SCHEMA_VERSION
        or payload.get("artifact_kind") != PRODUCTION_DAILY_DATA_RECEIPT_KIND
    ):
        raise ProductionAssetError(
            "production_daily_data_receipt_schema_mismatch"
        )
    digest = payload.get("receipt_sha256")
    if (
        not isinstance(digest, str)
        or not _SHA256_RE.fullmatch(digest)
        or digest != production_daily_data_receipt_digest(payload)
    ):
        raise ProductionAssetError(
            "production_daily_data_receipt_digest_mismatch"
        )
    expected_identity = {
        "source_commit": source_commit,
        "manifest_sha256": manifest_sha256,
        "target_cutoff_date": target_cutoff_date,
    }
    if any(payload.get(key) != value for key, value in expected_identity.items()):
        raise ProductionAssetError(
            "production_daily_data_receipt_identity_mismatch"
        )
    inventory = payload.get("data_inventory")
    if not isinstance(inventory, dict):
        raise ProductionAssetError(
            "production_daily_data_receipt_inventory_invalid"
        )
    generated_at = payload.get("generated_at_utc")
    if inventory.get("generated_at_utc") != generated_at:
        raise ProductionAssetError(
            "production_daily_data_receipt_timestamp_mismatch"
        )
    observed_at = validation_at_utc or datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )
    validate_production_asset_inventory(
        inventory,
        declared_data_link=declared_data_link,
        expected_data_root=expected_data_root,
        source_commit=source_commit,
        target_cutoff_date=target_cutoff_date,
        # The inventory is a daily mutable-data receipt.  Freshness is measured
        # at validation time, never against the immutable release creation time.
        manifest_created_at_utc=observed_at,
    )
    database_asset = payload.get("database_asset")
    next_session_date = str(
        inventory["semantic_freshness"]["next_trading_session_date"]
    )
    if (
        not isinstance(database_asset, dict)
        or set(database_asset) != _DATABASE_ASSET_FIELDS
        or database_asset != _database_asset_row(production_database_path)
        or database_asset.get("max_bar_date")
        not in {target_cutoff_date, next_session_date}
    ):
        raise ProductionAssetError(
            "production_daily_database_receipt_mismatch"
        )
    signal_bundle = payload.get("signal_bundle")
    if (
        not isinstance(signal_bundle, dict)
        or set(signal_bundle) != _SIGNAL_BUNDLE_FIELDS
        or any(
            not isinstance(row, dict) or set(row) != _SIGNAL_ASSET_FIELDS
            for row in signal_bundle.get("assets", [])
        )
        or not isinstance(signal_bundle.get("ai_eligibility"), dict)
        or set(signal_bundle["ai_eligibility"]) != _SIGNAL_ASSET_FIELDS
        or signal_bundle
        != _signal_bundle_row(
            signal_input_root=signal_input_root,
            official_ai_eligibility_path=official_ai_eligibility_path,
            target_date=target_cutoff_date,
        )
    ):
        raise ProductionAssetError(
            "production_daily_signal_bundle_mismatch"
        )
    return dict(payload)


def _read_private_receipt(path: Path) -> bytes:
    candidate = Path(os.path.abspath(path.expanduser()))
    try:
        parent_metadata = candidate.parent.lstat()
        metadata = candidate.lstat()
    except OSError as exc:
        raise ProductionAssetError(
            "production_daily_data_receipt_missing"
        ) from exc
    if (
        stat.S_ISLNK(parent_metadata.st_mode)
        or not stat.S_ISDIR(parent_metadata.st_mode)
        or parent_metadata.st_uid != os.getuid()
        or stat.S_IMODE(parent_metadata.st_mode) & 0o077
    ):
        raise ProductionAssetError(
            "production_daily_data_receipt_parent_security_invalid"
        )
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise ProductionAssetError(
            "production_daily_data_receipt_security_invalid"
        )
    try:
        return candidate.read_bytes()
    except OSError as exc:
        raise ProductionAssetError(
            "production_daily_data_receipt_read_failed"
        ) from exc


def load_and_validate_production_daily_data_receipt(
    path: Path | str,
    *,
    declared_data_link: Path | str,
    expected_data_root: Path | str,
    source_commit: str,
    manifest_sha256: str,
    target_cutoff_date: str,
    production_database_path: Path | str,
    signal_input_root: Path | str,
    official_ai_eligibility_path: Path | str,
    validation_at_utc: str | None = None,
) -> dict[str, Any]:
    raw = _read_private_receipt(Path(path))
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ProductionAssetError(
            "production_daily_data_receipt_json_invalid"
        ) from exc
    if not isinstance(payload, dict):
        raise ProductionAssetError(
            "production_daily_data_receipt_json_invalid"
        )
    if raw != serialize_production_daily_data_receipt(payload):
        raise ProductionAssetError(
            "production_daily_data_receipt_bytes_not_canonical"
        )
    return validate_production_daily_data_receipt_payload(
        payload,
        declared_data_link=declared_data_link,
        expected_data_root=expected_data_root,
        source_commit=source_commit,
        manifest_sha256=manifest_sha256,
        target_cutoff_date=target_cutoff_date,
        production_database_path=production_database_path,
        signal_input_root=signal_input_root,
        official_ai_eligibility_path=official_ai_eligibility_path,
        validation_at_utc=validation_at_utc,
    )


def write_production_daily_data_receipt(
    path: Path | str,
    payload: Mapping[str, Any],
) -> None:
    destination = Path(os.path.abspath(Path(path).expanduser()))
    try:
        parent_metadata = destination.parent.lstat()
    except OSError as exc:
        raise ProductionAssetError(
            "production_daily_data_receipt_parent_missing"
        ) from exc
    if (
        stat.S_ISLNK(parent_metadata.st_mode)
        or not stat.S_ISDIR(parent_metadata.st_mode)
        or parent_metadata.st_uid != os.getuid()
        or stat.S_IMODE(parent_metadata.st_mode) & 0o077
    ):
        raise ProductionAssetError(
            "production_daily_data_receipt_parent_security_invalid"
        )
    encoded = serialize_production_daily_data_receipt(payload)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        parent_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        temporary.unlink(missing_ok=True)


def build_and_write_production_daily_data_receipt(
    *,
    output_path: Path | str,
    declared_data_link: Path | str,
    expected_data_root: Path | str,
    source_commit: str,
    manifest_sha256: str,
    target_cutoff_date: str,
    production_database_path: Path | str,
    signal_input_root: Path | str,
    official_ai_eligibility_path: Path | str,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    payload = build_production_daily_data_receipt(
        declared_data_link=declared_data_link,
        expected_data_root=expected_data_root,
        source_commit=source_commit,
        manifest_sha256=manifest_sha256,
        target_cutoff_date=target_cutoff_date,
        production_database_path=production_database_path,
        signal_input_root=signal_input_root,
        official_ai_eligibility_path=official_ai_eligibility_path,
        generated_at_utc=generated_at_utc,
    )
    validation_at = str(payload["generated_at_utc"])
    validate_production_daily_data_receipt_payload(
        payload,
        declared_data_link=declared_data_link,
        expected_data_root=expected_data_root,
        source_commit=source_commit,
        manifest_sha256=manifest_sha256,
        target_cutoff_date=target_cutoff_date,
        production_database_path=production_database_path,
        signal_input_root=signal_input_root,
        official_ai_eligibility_path=official_ai_eligibility_path,
        validation_at_utc=validation_at,
    )
    write_production_daily_data_receipt(output_path, payload)
    return load_and_validate_production_daily_data_receipt(
        output_path,
        declared_data_link=declared_data_link,
        expected_data_root=expected_data_root,
        source_commit=source_commit,
        manifest_sha256=manifest_sha256,
        target_cutoff_date=target_cutoff_date,
        production_database_path=production_database_path,
        signal_input_root=signal_input_root,
        official_ai_eligibility_path=official_ai_eligibility_path,
        validation_at_utc=validation_at,
    )


def initialize_production_database_from_sqlite_backup(
    *,
    source_path: Path | str,
    destination_path: Path | str,
) -> None:
    """Create the stable project-local database via SQLite online backup.

    A byte copy of a database that another process may have open can capture an
    inconsistent point in time.  SQLite's backup API supplies a transactionally
    consistent snapshot and the destination is only published after quick_check.
    """

    source = Path(os.path.abspath(Path(source_path).expanduser()))
    destination = Path(os.path.abspath(Path(destination_path).expanduser()))
    if destination.exists() or destination.is_symlink():
        raise ProductionAssetError(
            "production_database_initial_destination_exists"
        )
    try:
        source_metadata = source.lstat()
        parent_metadata = destination.parent.lstat()
    except OSError as exc:
        raise ProductionAssetError(
            "production_database_initial_path_missing"
        ) from exc
    if (
        stat.S_ISLNK(source_metadata.st_mode)
        or not stat.S_ISREG(source_metadata.st_mode)
        or source_metadata.st_uid != os.getuid()
        or stat.S_IMODE(source_metadata.st_mode) & 0o022
    ):
        raise ProductionAssetError(
            "production_database_initial_source_security_invalid"
        )
    if (
        stat.S_ISLNK(parent_metadata.st_mode)
        or not stat.S_ISDIR(parent_metadata.st_mode)
        or parent_metadata.st_uid != os.getuid()
        or stat.S_IMODE(parent_metadata.st_mode) & 0o077
    ):
        raise ProductionAssetError(
            "production_database_initial_parent_security_invalid"
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".sqlite-backup",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        source_connection = sqlite3.connect(
            f"file:{source.resolve(strict=True)}?mode=ro",
            uri=True,
            timeout=30.0,
        )
        destination_connection = sqlite3.connect(str(temporary), timeout=30.0)
        try:
            source_connection.backup(destination_connection)
            destination_connection.commit()
            quick_check = destination_connection.execute(
                "PRAGMA quick_check"
            ).fetchone()
            if not quick_check or str(quick_check[0]) != "ok":
                raise ProductionAssetError(
                    "production_database_initial_quick_check_failed"
                )
        finally:
            destination_connection.close()
            source_connection.close()
        temporary.chmod(0o600)
        file_fd = os.open(temporary, os.O_RDONLY)
        try:
            os.fsync(file_fd)
        finally:
            os.close(file_fd)
        os.replace(temporary, destination)
        parent_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        try:
            if _database_asset_row(destination).get("quick_check") != "ok":
                raise ProductionAssetError(
                    "production_database_initial_post_write_validation_failed"
                )
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    finally:
        temporary.unlink(missing_ok=True)


__all__ = [
    "PRODUCTION_DAILY_DATA_RECEIPT_KIND",
    "PRODUCTION_DAILY_DATA_RECEIPT_SCHEMA_VERSION",
    "build_and_write_production_daily_data_receipt",
    "build_production_daily_data_receipt",
    "initialize_production_database_from_sqlite_backup",
    "load_and_validate_production_daily_data_receipt",
    "production_daily_data_receipt_digest",
    "serialize_production_daily_data_receipt",
    "validate_production_daily_data_receipt_payload",
    "write_production_daily_data_receipt",
]
