from __future__ import annotations

import csv
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo


PRODUCTION_ASSET_INVENTORY_SCHEMA_VERSION = 1
PRODUCTION_ASSET_INVENTORY_KIND = "stage179_production_data_asset_inventory"
PRODUCTION_ASSET_INVENTORY_MAX_FUTURE_SKEW = timedelta(minutes=5)
PRODUCTION_TRADING_TIMEZONE = ZoneInfo("Asia/Shanghai")
PRODUCTION_REQUIRED_DATA_ASSETS = (
    "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv",
    "qmt_roll_stage173_forward_main_contract_data_update_contract_bar_status_"
    "stage173_forward_main_contract_data_update_v1.csv",
    "qmt_roll_stage173_forward_main_contract_data_update_summary_"
    "stage173_forward_main_contract_data_update_v1.json",
    "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_"
    "stage861_stage860_full_visual_atlas_v1.csv",
)
MAPPING_ASSET = PRODUCTION_REQUIRED_DATA_ASSETS[0]
STAGE173_STATUS_ASSET = PRODUCTION_REQUIRED_DATA_ASSETS[1]
STAGE173_SUMMARY_ASSET = PRODUCTION_REQUIRED_DATA_ASSETS[2]
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_INVENTORY_FIELDS = {
    "schema_version",
    "artifact_kind",
    "generated_at_utc",
    "source_commit",
    "declared_data_link",
    "resolved_data_root",
    "target_cutoff_date",
    "assets",
    "semantic_freshness",
    "asset_tree_fingerprint",
    "inventory_sha256",
}
_ASSET_FIELDS = {
    "relative_path",
    "sha256",
    "size_bytes",
    "mtime_epoch_ns",
}
_SEMANTIC_FIELDS = {
    "mapping_max_date",
    "stage173_status_max_date",
    "stage173_summary_max_saved_date",
    "stage173_summary_mapping_max_date",
    "forward_calendar_source",
    "forward_calendar_completed_target_date",
    "next_trading_session_date",
    "forward_calendar_dates_sha256",
}
_COMPLETED_TARGET_DATE_SEMANTIC_FIELDS = {
    "stage173_status_max_date",
    "stage173_summary_max_saved_date",
    "forward_calendar_completed_target_date",
}
_MAPPING_MAX_DATE_SEMANTIC_FIELDS = {
    "mapping_max_date",
    "stage173_summary_mapping_max_date",
}


class ProductionAssetError(ValueError):
    pass


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
            f"production_asset_not_canonical:{exc}"
        ) from exc


def production_asset_inventory_digest(payload: Mapping[str, Any]) -> str:
    core = {
        key: value for key, value in payload.items() if key != "inventory_sha256"
    }
    return hashlib.sha256(_canonical_json_bytes(core)).hexdigest()


def serialize_production_asset_inventory(payload: Mapping[str, Any]) -> bytes:
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
            f"production_asset_not_canonical:{exc}"
        ) from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _assert_guarded_components(
    path: Path,
    *,
    allow_leaf_symlink: bool,
    error_prefix: str,
) -> None:
    candidate = _lexical_absolute(path)
    components = tuple(reversed(candidate.parents)) + (candidate,)
    user_owned_scope = False
    for component in components:
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ProductionAssetError(
                f"{error_prefix}_component_lstat_failed"
            ) from exc
        is_leaf = component == candidate
        if stat.S_ISLNK(metadata.st_mode):
            if is_leaf and allow_leaf_symlink:
                continue
            raise ProductionAssetError(
                f"{error_prefix}_ancestor_symlink_forbidden"
            )
        if metadata.st_uid == os.getuid():
            user_owned_scope = True
        if user_owned_scope:
            if metadata.st_uid != os.getuid():
                raise ProductionAssetError(
                    f"{error_prefix}_ancestor_owner_mismatch"
                )
            if stat.S_ISDIR(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) & 0o022:
                raise ProductionAssetError(
                    f"{error_prefix}_ancestor_writable_by_other"
                )


def _strict_owned_directory(path: Path, *, error_prefix: str) -> Path:
    declared = _lexical_absolute(path)
    _assert_guarded_components(
        declared,
        allow_leaf_symlink=False,
        error_prefix=error_prefix,
    )
    try:
        metadata = declared.lstat()
    except OSError as exc:
        raise ProductionAssetError(f"{error_prefix}_missing") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ProductionAssetError(f"{error_prefix}_invalid")
    if metadata.st_uid != os.getuid():
        raise ProductionAssetError(f"{error_prefix}_owner_mismatch")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        raise ProductionAssetError(f"{error_prefix}_writable_by_other")
    return declared.resolve(strict=True)


def validate_production_data_link(
    *,
    declared_data_link: Path | str,
    expected_data_root: Path | str,
) -> Path:
    link = _lexical_absolute(Path(declared_data_link))
    _assert_guarded_components(
        link,
        allow_leaf_symlink=True,
        error_prefix="production_data_link",
    )
    expected_root = _strict_owned_directory(
        Path(expected_data_root),
        error_prefix="production_data_root",
    )
    try:
        metadata = link.lstat()
    except OSError as exc:
        raise ProductionAssetError("production_data_link_missing") from exc
    if not stat.S_ISLNK(metadata.st_mode):
        raise ProductionAssetError("production_data_link_not_symlink")
    if metadata.st_uid != os.getuid():
        raise ProductionAssetError("production_data_link_owner_mismatch")
    try:
        observed_root = link.resolve(strict=True)
    except OSError as exc:
        raise ProductionAssetError("production_data_link_broken") from exc
    if observed_root != expected_root:
        raise ProductionAssetError("production_data_link_target_mismatch")
    return observed_root


def validate_production_venv_link(
    *,
    declared_venv_link: Path | str,
    expected_venv_root: Path | str,
) -> tuple[Path, Path, tuple[Path, Path]]:
    """Validate the only runtime symlink allowed inside the stable deploy.

    The leaf ``.py311`` link may point at the exact main-repository venv.  Its
    executable and formal CTP framework roots are then checked independently;
    no other deploy ancestor is permitted to be a symlink.
    """

    link = _lexical_absolute(Path(declared_venv_link))
    _assert_guarded_components(
        link,
        allow_leaf_symlink=True,
        error_prefix="production_venv_link",
    )
    expected_root = _strict_owned_directory(
        Path(expected_venv_root),
        error_prefix="production_venv_root",
    )
    try:
        link_metadata = link.lstat()
    except OSError as exc:
        raise ProductionAssetError("production_venv_link_missing") from exc
    if not stat.S_ISLNK(link_metadata.st_mode):
        raise ProductionAssetError("production_venv_link_not_symlink")
    if link_metadata.st_uid != os.getuid():
        raise ProductionAssetError("production_venv_link_owner_mismatch")
    try:
        observed_root = link.resolve(strict=True)
    except OSError as exc:
        raise ProductionAssetError("production_venv_link_broken") from exc
    if observed_root != expected_root:
        raise ProductionAssetError("production_venv_link_target_mismatch")

    python_link = link / "bin" / "python"
    try:
        python_link_metadata = python_link.lstat()
        python_executable = python_link.resolve(strict=True)
        python_metadata = python_executable.lstat()
    except OSError as exc:
        raise ProductionAssetError(
            "production_venv_python_missing"
        ) from exc
    if python_link_metadata.st_uid != os.getuid():
        raise ProductionAssetError("production_venv_python_owner_mismatch")
    if (
        not python_executable.is_relative_to(expected_root)
        or not stat.S_ISREG(python_metadata.st_mode)
        or python_metadata.st_uid != os.getuid()
        or stat.S_IMODE(python_metadata.st_mode) & 0o022
        or not (stat.S_IMODE(python_metadata.st_mode) & 0o100)
    ):
        raise ProductionAssetError(
            "production_venv_python_security_invalid"
        )

    py311_lib = expected_root / "lib"
    formal_ctp = (
        expected_root
        / "lib"
        / "python3.11"
        / "site-packages"
        / "vnpy_ctp"
        / "api"
        / "libs"
    )
    for name, directory in (
        ("py311_lib", py311_lib),
        ("formal_ctp", formal_ctp),
    ):
        _assert_guarded_components(
            directory,
            allow_leaf_symlink=False,
            error_prefix=f"production_venv_{name}",
        )
        try:
            metadata = directory.lstat()
        except OSError as exc:
            raise ProductionAssetError(
                f"production_venv_{name}_missing"
            ) from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise ProductionAssetError(
                f"production_venv_{name}_security_invalid"
            )
    for framework_name in (
        "thostmduserapi_se.framework",
        "thosttraderapi_se.framework",
    ):
        framework = formal_ctp / framework_name
        try:
            metadata = framework.lstat()
        except OSError as exc:
            raise ProductionAssetError(
                f"production_venv_formal_framework_missing:{framework_name}"
            ) from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise ProductionAssetError(
                f"production_venv_formal_framework_security_invalid:{framework_name}"
            )
    return observed_root, python_executable, (formal_ctp, py311_lib)


def _strict_asset_rows(
    *,
    data_root: Path,
    relative_paths: Iterable[str | Path],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in relative_paths:
        relative = Path(raw)
        if relative.is_absolute() or ".." in relative.parts:
            raise ProductionAssetError(f"production_asset_path_invalid:{raw}")
        normalized = relative.as_posix()
        if normalized in seen:
            raise ProductionAssetError(
                f"production_asset_path_duplicate:{normalized}"
            )
        seen.add(normalized)
        candidate = data_root / relative
        _assert_guarded_components(
            candidate,
            allow_leaf_symlink=False,
            error_prefix=f"production_asset:{normalized}",
        )
        try:
            metadata = candidate.lstat()
        except OSError as exc:
            raise ProductionAssetError(
                f"production_asset_missing:{normalized}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ProductionAssetError(
                f"production_asset_not_regular:{normalized}"
            )
        if metadata.st_uid != os.getuid():
            raise ProductionAssetError(
                f"production_asset_owner_mismatch:{normalized}"
            )
        if stat.S_IMODE(metadata.st_mode) & 0o022:
            raise ProductionAssetError(
                f"production_asset_writable_by_other:{normalized}"
            )
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(data_root):
            raise ProductionAssetError(
                f"production_asset_outside_root:{normalized}"
            )
        rows.append(
            {
                "relative_path": normalized,
                "sha256": _sha256_file(resolved),
                "size_bytes": metadata.st_size,
                "mtime_epoch_ns": metadata.st_mtime_ns,
            }
        )
    return sorted(rows, key=lambda row: str(row["relative_path"]))


def _csv_max_date(path: Path, column: str) -> str:
    maximum = ""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                value = str(row.get(column, "")).strip()[:10]
                if _DATE_RE.fullmatch(value) and value > maximum:
                    maximum = value
    except (OSError, csv.Error) as exc:
        raise ProductionAssetError(
            f"production_asset_date_scan_failed:{path.name}"
        ) from exc
    return maximum


def _semantic_freshness(data_root: Path) -> dict[str, str]:
    mapping_max = _csv_max_date(data_root / MAPPING_ASSET, "date")
    status_max = _csv_max_date(data_root / STAGE173_STATUS_ASSET, "max_date")
    try:
        summary = json.loads(
            (data_root / STAGE173_SUMMARY_ASSET).read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise ProductionAssetError(
            "production_asset_stage173_summary_invalid"
        ) from exc
    if not isinstance(summary, dict):
        raise ProductionAssetError("production_asset_stage173_summary_invalid")
    mapping_update = summary.get("mapping_update")
    if not isinstance(mapping_update, dict):
        mapping_update = {}
    forward_calendar = summary.get("forward_trading_calendar")
    if not isinstance(forward_calendar, dict):
        forward_calendar = {}
    return {
        "mapping_max_date": mapping_max,
        "stage173_status_max_date": status_max,
        "stage173_summary_max_saved_date": str(
            summary.get("max_saved_date", "")
        )[:10],
        "stage173_summary_mapping_max_date": str(
            mapping_update.get("combined_max_date", "")
        )[:10],
        "forward_calendar_source": str(forward_calendar.get("source", "")),
        "forward_calendar_completed_target_date": str(
            forward_calendar.get("completed_target_date", "")
        )[:10],
        "next_trading_session_date": str(
            forward_calendar.get("next_trading_session_date", "")
        )[:10],
        "forward_calendar_dates_sha256": str(
            forward_calendar.get("trading_dates_sha256", "")
        ),
    }


def _validate_semantic_freshness(
    semantic: Mapping[str, str],
    *,
    target_cutoff_date: str,
) -> None:
    if any(
        semantic.get(field_name) != target_cutoff_date
        for field_name in _COMPLETED_TARGET_DATE_SEMANTIC_FIELDS
    ):
        raise ProductionAssetError("production_asset_target_freshness_mismatch")
    next_session_date = str(semantic.get("next_trading_session_date", ""))
    if (
        semantic.get("forward_calendar_source") != "tqsdk.TqContCalendar"
        or not _DATE_RE.fullmatch(next_session_date)
        or next_session_date <= target_cutoff_date
        or not _SHA256_RE.fullmatch(
            str(semantic.get("forward_calendar_dates_sha256", ""))
        )
    ):
        raise ProductionAssetError("production_asset_forward_calendar_invalid")
    mapping_dates = {
        str(semantic.get(field_name, ""))
        for field_name in _MAPPING_MAX_DATE_SEMANTIC_FIELDS
    }
    if len(mapping_dates) != 1 or mapping_dates.pop() not in {
        target_cutoff_date,
        next_session_date,
    }:
        raise ProductionAssetError("production_asset_target_freshness_mismatch")


def build_production_asset_inventory(
    *,
    declared_data_link: Path | str,
    expected_data_root: Path | str,
    source_commit: str,
    target_cutoff_date: str,
    generated_at_utc: str,
    asset_paths: Iterable[str | Path] = PRODUCTION_REQUIRED_DATA_ASSETS,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", str(source_commit)):
        raise ProductionAssetError("production_asset_source_commit_invalid")
    if not _DATE_RE.fullmatch(str(target_cutoff_date)):
        raise ProductionAssetError("production_asset_target_cutoff_invalid")
    data_root = validate_production_data_link(
        declared_data_link=declared_data_link,
        expected_data_root=expected_data_root,
    )
    rows = _strict_asset_rows(data_root=data_root, relative_paths=asset_paths)
    required = set(PRODUCTION_REQUIRED_DATA_ASSETS)
    observed = {str(row["relative_path"]) for row in rows}
    if not required.issubset(observed):
        raise ProductionAssetError("production_asset_required_files_missing")
    semantic = _semantic_freshness(data_root)
    _validate_semantic_freshness(
        semantic,
        target_cutoff_date=target_cutoff_date,
    )
    core: dict[str, Any] = {
        "schema_version": PRODUCTION_ASSET_INVENTORY_SCHEMA_VERSION,
        "artifact_kind": PRODUCTION_ASSET_INVENTORY_KIND,
        "generated_at_utc": generated_at_utc,
        "source_commit": source_commit,
        "declared_data_link": str(_lexical_absolute(Path(declared_data_link))),
        "resolved_data_root": str(data_root),
        "target_cutoff_date": target_cutoff_date,
        "assets": rows,
        "semantic_freshness": semantic,
        "asset_tree_fingerprint": hashlib.sha256(
            _canonical_json_bytes(rows)
        ).hexdigest(),
    }
    return {**core, "inventory_sha256": production_asset_inventory_digest(core)}


def validate_production_asset_inventory(
    payload: Mapping[str, Any],
    *,
    declared_data_link: Path | str,
    expected_data_root: Path | str,
    source_commit: str,
    target_cutoff_date: str,
    manifest_created_at_utc: str,
) -> dict[str, Any]:
    if set(payload) != _INVENTORY_FIELDS:
        raise ProductionAssetError("production_asset_inventory_fields_invalid")
    if (
        payload.get("schema_version") != PRODUCTION_ASSET_INVENTORY_SCHEMA_VERSION
        or payload.get("artifact_kind") != PRODUCTION_ASSET_INVENTORY_KIND
    ):
        raise ProductionAssetError("production_asset_inventory_schema_mismatch")
    digest = payload.get("inventory_sha256")
    if (
        not isinstance(digest, str)
        or not _SHA256_RE.fullmatch(digest)
        or digest != production_asset_inventory_digest(payload)
    ):
        raise ProductionAssetError("production_asset_inventory_digest_mismatch")
    if payload.get("source_commit") != source_commit:
        raise ProductionAssetError("production_asset_source_commit_mismatch")
    data_root = validate_production_data_link(
        declared_data_link=declared_data_link,
        expected_data_root=expected_data_root,
    )
    if (
        payload.get("declared_data_link")
        != str(_lexical_absolute(Path(declared_data_link)))
        or payload.get("resolved_data_root") != str(data_root)
        or payload.get("target_cutoff_date") != target_cutoff_date
    ):
        raise ProductionAssetError("production_asset_inventory_identity_mismatch")
    try:
        generated_at = datetime.fromisoformat(
            str(payload.get("generated_at_utc", "")).replace("Z", "+00:00")
        )
        manifest_at = datetime.fromisoformat(
            manifest_created_at_utc.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ProductionAssetError(
            "production_asset_inventory_timestamp_invalid"
        ) from exc
    if (
        not str(payload.get("generated_at_utc", "")).endswith("Z")
        or not manifest_created_at_utc.endswith("Z")
        or generated_at.utcoffset() != timedelta(0)
        or manifest_at.utcoffset() != timedelta(0)
        or generated_at > manifest_at + PRODUCTION_ASSET_INVENTORY_MAX_FUTURE_SKEW
    ):
        raise ProductionAssetError(
            "production_asset_inventory_timestamp_invalid"
        )
    rows = payload.get("assets")
    if (
        not isinstance(rows, list)
        or any(not isinstance(row, dict) or set(row) != _ASSET_FIELDS for row in rows)
        or rows != sorted(rows, key=lambda row: str(row.get("relative_path", "")))
    ):
        raise ProductionAssetError("production_asset_inventory_rows_invalid")
    expected_rows = _strict_asset_rows(
        data_root=data_root,
        relative_paths=[str(row.get("relative_path", "")) for row in rows],
    )
    if rows != expected_rows:
        raise ProductionAssetError("production_asset_inventory_bytes_mismatch")
    required = set(PRODUCTION_REQUIRED_DATA_ASSETS)
    if not required.issubset({str(row["relative_path"]) for row in rows}):
        raise ProductionAssetError("production_asset_required_files_missing")
    expected_fingerprint = hashlib.sha256(
        _canonical_json_bytes(expected_rows)
    ).hexdigest()
    if payload.get("asset_tree_fingerprint") != expected_fingerprint:
        raise ProductionAssetError(
            "production_asset_inventory_tree_fingerprint_mismatch"
        )
    semantic = payload.get("semantic_freshness")
    if not isinstance(semantic, dict) or set(semantic) != _SEMANTIC_FIELDS:
        raise ProductionAssetError("production_asset_semantic_freshness_invalid")
    current_semantic = _semantic_freshness(data_root)
    if semantic != current_semantic:
        raise ProductionAssetError("production_asset_target_freshness_mismatch")
    _validate_semantic_freshness(
        current_semantic,
        target_cutoff_date=target_cutoff_date,
    )
    next_session = datetime.strptime(
        str(current_semantic["next_trading_session_date"]),
        "%Y-%m-%d",
    ).date()
    validation_wall_date = manifest_at.astimezone(
        PRODUCTION_TRADING_TIMEZONE
    ).date()
    if validation_wall_date > next_session:
        raise ProductionAssetError(
            "production_asset_inventory_trading_session_expired"
        )
    return dict(payload)


__all__ = [
    "PRODUCTION_REQUIRED_DATA_ASSETS",
    "ProductionAssetError",
    "build_production_asset_inventory",
    "production_asset_inventory_digest",
    "serialize_production_asset_inventory",
    "validate_production_asset_inventory",
    "validate_production_data_link",
    "validate_production_venv_link",
]
