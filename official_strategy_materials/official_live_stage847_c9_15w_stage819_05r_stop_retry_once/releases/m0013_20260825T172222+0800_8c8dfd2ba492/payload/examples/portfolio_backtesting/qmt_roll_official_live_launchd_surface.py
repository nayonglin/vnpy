from __future__ import annotations

import hashlib
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
from typing import Any


PRODUCTION_PLIST_NAMES = (
    "local.qmt-roll.official-live.15w.c9-production-live-day-session.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-night-session.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-day-close-readonly.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-postclose-precompute.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-postclose-report.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-monthly-ai-pool.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-health.plist",
)
PRODUCTION_LABELS = tuple(
    name.removesuffix(".plist") for name in PRODUCTION_PLIST_NAMES
)
KNOWN_CONFLICTING_LABELS = (
    "local.qmt-roll.official-live.15w.c9-readonly-day-session",
    "local.qmt-roll.official-live.15w.c9-readonly-night-session",
    "local.qmt-roll.official-live.15w.c9-day-session",
    "local.qmt-roll.official-live.15w.c9-night-session",
    "local.qmt-roll.official-live.20w.stage372-day-session",
    "local.qmt-roll.official-live.20w.stage372-night-session",
    "local.qmt-roll.official-live.20w.stage372-postclose-precompute",
    "local.qmt-roll.official-live.15w.c9-readonly-postclose-precompute",
    "local.qmt-roll.official-live.15w.day-close-readonly",
    "local.qmt-roll.official-live.15w.postclose",
    "local.qmt-roll.official-live.15w.evening-report",
    "local.qmt-roll.official-live.15w.monthly-ai-pool",
    "local.qmt-roll.stage179.no-submit-direct",
    "local.qmt-roll.stage179.no-submit-supervisor",
)
OWNED_LABEL_PREFIXES = (
    "local.qmt-roll.official-live.",
    "local.qmt-roll.stage179.",
)
SAFE_PLIST_MODES = frozenset({0o600, 0o640, 0o644})
_OWNED_LABEL_RE = re.compile(
    r"local\.qmt-roll\.(?:official-live|stage179)\."
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}"
)
_SERVICE_ROW_RE = re.compile(
    r"\s*(-?\d+)\s+(-|-?\d+|\([A-Za-z]+\))\s+"
    r"(local\.qmt-roll\.(?:official-live|stage179)\."
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,199})\s*"
)


class LaunchdSurfaceError(RuntimeError):
    pass


def _is_owned_label(value: str) -> bool:
    return bool(
        value.startswith(OWNED_LABEL_PREFIXES)
        and _OWNED_LABEL_RE.fullmatch(value)
    )


def _call_launchctl(
    runner: Any,
    *arguments: str,
) -> tuple[dict[str, Any], str]:
    command = ["/bin/launchctl", *arguments]
    try:
        result = runner(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        return {
            "arguments": list(arguments),
            "exit_code": -1,
            "exception_type": type(exc).__name__,
        }, ""
    return {
        "arguments": list(arguments),
        "exit_code": int(result.returncode),
    }, str(result.stdout or "")


def _parse_state(output: str) -> tuple[str, int | None]:
    state = ""
    pid: int | None = None
    for line in output.splitlines():
        text = line.strip()
        if text.startswith("state = "):
            state = text.split("=", 1)[1].strip()
        elif text.startswith("pid = "):
            try:
                pid = int(text.split("=", 1)[1].strip())
            except ValueError:
                pid = None
    return state, pid


def _complete_root(
    output: str,
    *,
    expected_header: str,
) -> bool:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if (
        not lines
        or not re.fullmatch(
            rf"\s*{re.escape(expected_header)}\s*=\s*\{{\s*",
            lines[0],
        )
        or lines[-1].strip() != "}"
    ):
        return False
    depth = 0
    quote = ""
    escaped = False
    for character in output:
        if escaped:
            escaped = False
            continue
        if quote:
            if character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in {"\"", "'"}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not quote


def _lexical_owned_tokens(output: str) -> tuple[set[str], list[str]]:
    labels: set[str] = set()
    blockers: list[str] = []
    label_characters = frozenset(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
    )
    delimiters = frozenset(" \t\r\n=;{},()[]<>\"'")
    for prefix in OWNED_LABEL_PREFIXES:
        offset = 0
        while True:
            start = output.find(prefix, offset)
            if start < 0:
                break
            match = _OWNED_LABEL_RE.match(output, start)
            if match is None:
                blockers.append(f"owned_token_invalid:{prefix}")
                offset = start + len(prefix)
                continue
            label = match.group(0)
            preceding = output[start - 1 : start] if start else ""
            following = output[match.end() : match.end() + 1]
            if (
                (preceding and preceding in label_characters)
                or (following and following not in delimiters)
            ):
                blockers.append(f"owned_token_boundary_invalid:{label}")
            else:
                labels.add(label)
            offset = max(match.end(), start + len(prefix))
    return labels, sorted(set(blockers))


def _parse_domain_snapshot(
    output: str,
    *,
    uid_domain: str,
) -> tuple[set[str], dict[str, tuple[str, str]], list[str]]:
    blockers: list[str] = []
    if not _complete_root(output, expected_header=uid_domain):
        return set(), {}, ["domain_root_incomplete_or_header_invalid"]
    lines = output.splitlines()
    openings = [
        index
        for index, line in enumerate(lines)
        if re.fullmatch(r"\s*services\s*=\s*\{\s*", line)
    ]
    if len(openings) != 1:
        return set(), {}, ["domain_services_block_count_invalid"]
    opening = openings[0]
    indent = len(lines[opening]) - len(lines[opening].lstrip())
    closing: int | None = None
    for index in range(opening + 1, len(lines)):
        line = lines[index]
        if (
            len(line) - len(line.lstrip()) == indent
            and line.strip() == "}"
        ):
            closing = index
            break
    if closing is None:
        return set(), {}, ["domain_services_block_truncated"]

    structured: set[str] = set()
    service_rows: dict[str, tuple[str, str]] = {}
    for line in lines[opening + 1 : closing]:
        if not any(prefix in line for prefix in OWNED_LABEL_PREFIXES):
            continue
        match = _SERVICE_ROW_RE.fullmatch(line)
        if match is None or not _is_owned_label(match.group(3)):
            blockers.append("domain_owned_service_row_invalid")
            continue
        label = match.group(3)
        signature = (match.group(1), match.group(2))
        if label in service_rows:
            blockers.append(f"domain_owned_service_duplicate:{label}")
        structured.add(label)
        service_rows[label] = signature
    # `launchctl print gui/<uid>` can retain labels in top-level preference
    # maps such as `disabled services` after the corresponding service has
    # been unloaded.  Those entries are not registered services.  Keep the
    # lexical/structured cross-check fail-closed, but scope it to the exact
    # `services` block that the structured parser is validating.
    services_text = "\n".join(lines[opening + 1 : closing])
    lexical, lexical_blockers = _lexical_owned_tokens(services_text)
    blockers.extend(lexical_blockers)
    if lexical != structured:
        blockers.append("domain_owned_lexical_services_mismatch")
    return structured, service_rows, sorted(set(blockers))


def _discover_disk(directory: Path) -> dict[str, Any]:
    labels: set[str] = set()
    blockers: list[str] = []
    sources: dict[str, str] = {}
    fingerprints: dict[str, dict[str, Any]] = {}
    directory_fd = -1
    try:
        directory_fd = os.open(
            directory,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
    except FileNotFoundError:
        return {
            "labels": [],
            "blockers": [],
            "plist_names": [],
            "fingerprints": {},
        }
    except OSError as exc:
        return {
            "labels": [],
            "blockers": [f"launchagents_open_failed:{type(exc).__name__}"],
            "plist_names": [],
            "fingerprints": {},
        }
    before_directory = os.fstat(directory_fd)
    if (
        not stat.S_ISDIR(before_directory.st_mode)
        or before_directory.st_uid != os.getuid()
        or stat.S_IMODE(before_directory.st_mode) & 0o022
    ):
        os.close(directory_fd)
        return {
            "labels": [],
            "blockers": ["launchagents_directory_security_invalid"],
            "plist_names": [],
            "fingerprints": {},
        }
    try:
        with os.scandir(directory_fd) as iterator:
            entries = sorted(iterator, key=lambda item: item.name)
    except OSError as exc:
        os.close(directory_fd)
        return {
            "labels": [],
            "blockers": [f"launchagents_scandir_failed:{type(exc).__name__}"],
            "plist_names": [],
            "fingerprints": {},
        }

    plist_names: list[str] = []
    for entry in entries:
        name = entry.name
        if not name.endswith(".plist"):
            if name.startswith(OWNED_LABEL_PREFIXES):
                blockers.append(f"owned_non_plist_entry:{name}")
            continue
        plist_names.append(name)
        filename_label = name.removesuffix(".plist")
        filename_prefix = filename_label.startswith(OWNED_LABEL_PREFIXES)
        filename_owned = _is_owned_label(filename_label)
        if filename_prefix and not filename_owned:
            blockers.append(f"owned_filename_invalid:{name}")
        try:
            entry_stat = entry.stat(follow_symlinks=False)
        except OSError as exc:
            blockers.append(f"plist_lstat_failed:{name}:{type(exc).__name__}")
            continue
        if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISREG(
            entry_stat.st_mode
        ):
            blockers.append(f"plist_not_regular_no_follow:{name}")
            if filename_owned:
                labels.add(filename_label)
            continue
        descriptor = -1
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_fd,
            )
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or (before.st_dev, before.st_ino)
                != (entry_stat.st_dev, entry_stat.st_ino)
            ):
                raise LaunchdSurfaceError("plist_changed_during_open")
            mode = stat.S_IMODE(before.st_mode)
            if before.st_uid != os.getuid() or mode not in SAFE_PLIST_MODES:
                blockers.append(f"plist_security_invalid:{name}")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 1024 * 1024:
                    raise LaunchdSurfaceError("plist_oversized")
                chunks.append(chunk)
            raw = b"".join(chunks)
            after = os.fstat(descriptor)
            if (
                (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
                or after.st_size != before.st_size
                or after.st_mtime_ns != before.st_mtime_ns
                or after.st_ctime_ns != before.st_ctime_ns
                or stat.S_IMODE(after.st_mode) != mode
            ):
                raise LaunchdSurfaceError("plist_changed_during_read")
            payload = plistlib.loads(raw)
            if not isinstance(payload, dict):
                raise LaunchdSurfaceError("plist_not_dictionary")
        except Exception as exc:
            blockers.append(f"plist_uninspectable:{name}:{type(exc).__name__}")
            if filename_owned:
                labels.add(filename_label)
            continue
        finally:
            if descriptor >= 0:
                os.close(descriptor)

        payload_label = payload.get("Label")
        if not isinstance(payload_label, str):
            blockers.append(f"plist_label_invalid:{name}")
            if filename_owned:
                labels.add(filename_label)
            continue
        payload_prefix = payload_label.startswith(OWNED_LABEL_PREFIXES)
        payload_owned = _is_owned_label(payload_label)
        if payload_prefix and not payload_owned:
            blockers.append(f"owned_payload_label_invalid:{name}")
        if not (filename_owned or payload_owned):
            continue
        if filename_owned:
            labels.add(filename_label)
        if payload_owned:
            labels.add(payload_label)
        if not (
            filename_owned
            and payload_owned
            and filename_label == payload_label
        ):
            blockers.append(f"owned_filename_label_mismatch:{name}")
        if payload_owned:
            previous = sources.get(payload_label)
            if previous is not None and previous != name:
                blockers.append(f"owned_duplicate_label:{payload_label}")
            sources[payload_label] = name
        for label in {filename_label, payload_label}:
            if _is_owned_label(label):
                fingerprints[label] = {
                    "filename": name,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "mode": mode,
                    "device": before.st_dev,
                    "inode": before.st_ino,
                    "size": before.st_size,
                    "mtime_ns": before.st_mtime_ns,
                    "ctime_ns": before.st_ctime_ns,
                }

    after_directory = os.fstat(directory_fd)
    if (
        (after_directory.st_dev, after_directory.st_ino)
        != (before_directory.st_dev, before_directory.st_ino)
        or after_directory.st_mtime_ns != before_directory.st_mtime_ns
        or after_directory.st_ctime_ns != before_directory.st_ctime_ns
    ):
        blockers.append("launchagents_directory_changed_during_scan")
    try:
        path_after = directory.lstat()
    except OSError as exc:
        blockers.append(
            f"launchagents_path_restat_failed:{type(exc).__name__}"
        )
    else:
        if (
            stat.S_ISLNK(path_after.st_mode)
            or not stat.S_ISDIR(path_after.st_mode)
            or (path_after.st_dev, path_after.st_ino)
            != (before_directory.st_dev, before_directory.st_ino)
            or path_after.st_uid != before_directory.st_uid
            or stat.S_IMODE(path_after.st_mode)
            != stat.S_IMODE(before_directory.st_mode)
        ):
            blockers.append("launchagents_directory_path_changed_during_scan")
    os.close(directory_fd)
    return {
        "labels": sorted(labels),
        "blockers": sorted(set(blockers)),
        "plist_names": plist_names,
        "fingerprints": fingerprints,
    }


def _missing_output_is_exact(
    output: str,
    *,
    label: str,
    uid: int,
) -> bool:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) != 2 or lines[0] != "Bad request.":
        return False
    return bool(
        re.fullmatch(
            rf"Could not find service [\"“]{re.escape(label)}[\"”] "
            rf"in domain for user gui: {uid}",
            lines[1],
        )
    )


def classify_individual_launchctl_result(
    *,
    exit_code: int,
    output: str,
    label: str,
    uid: int,
) -> tuple[bool | None, str, int | None, str]:
    """Classify one ``launchctl print gui/<uid>/<label>`` result exactly."""

    state, pid = _parse_state(output)
    expected_header = f"gui/{uid}/{label}"
    if exit_code == 0:
        if _complete_root(output, expected_header=expected_header):
            return True, state, pid, "loaded_output_verified"
        return None, state, pid, "loaded_output_invalid"
    if exit_code == 113:
        if _missing_output_is_exact(output, label=label, uid=uid):
            return False, state, pid, "missing_output_verified"
        return None, state, pid, "missing_output_invalid"
    return None, state, pid, f"state_unknown_{exit_code}"


def inspect_owned_launchd_surface(
    *,
    launchd_install_dir: Path,
    allowed_production_labels: tuple[str, ...] = PRODUCTION_LABELS,
    known_conflicting_labels: tuple[str, ...] = KNOWN_CONFLICTING_LABELS,
    launchctl_runner: Any = subprocess.run,
    uid: int | None = None,
) -> dict[str, Any]:
    expected = set(allowed_production_labels)
    known = set(known_conflicting_labels)
    if (
        len(expected) != len(allowed_production_labels)
        or not all(_is_owned_label(label) for label in expected | known)
    ):
        raise LaunchdSurfaceError("expected_labels_invalid")
    effective_uid = os.getuid() if uid is None else uid
    domain = f"gui/{effective_uid}"
    blockers: list[str] = []
    steps: list[dict[str, Any]] = []

    disk_one = _discover_disk(launchd_install_dir)
    blockers.extend(disk_one["blockers"])
    disk_labels = set(disk_one["labels"])

    domain_one_step, domain_one_output = _call_launchctl(
        launchctl_runner,
        "print",
        domain,
    )
    steps.append({"phase": "owned_surface_domain_d1", **domain_one_step})
    launchctl_called_count = 1
    domain_one: set[str] = set()
    domain_one_rows: dict[str, tuple[str, str]] = {}
    if domain_one_step["exit_code"] != 0:
        blockers.append(f"domain_d1_unavailable:{domain_one_step['exit_code']}")
    else:
        domain_one, domain_one_rows, parse_blockers = _parse_domain_snapshot(
            domain_one_output,
            uid_domain=domain,
        )
        blockers.extend(parse_blockers)

    candidates = sorted(expected | known | disk_labels | domain_one)
    loaded: set[str] = set()
    jobs: dict[str, dict[str, Any]] = {}
    if domain_one_step["exit_code"] == 0 and not any(
        blocker.startswith(("domain_root_", "domain_services_"))
        for blocker in blockers
    ):
        for label in candidates:
            step, output = _call_launchctl(
                launchctl_runner,
                "print",
                f"{domain}/{label}",
            )
            launchctl_called_count += 1
            is_loaded, state, pid, classification = (
                classify_individual_launchctl_result(
                    exit_code=step["exit_code"],
                    output=output,
                    label=label,
                    uid=effective_uid,
                )
            )
            if is_loaded is True:
                loaded.add(label)
            elif is_loaded is None:
                blockers.append(f"job_{classification}:{label}")
            if label in domain_one and is_loaded is not True:
                blockers.append(f"domain_label_not_confirmed:{label}")
            row = {
                "label": label,
                "loaded": is_loaded,
                "state": state,
                "pid": pid,
                **step,
            }
            jobs[label] = row
            steps.append({"phase": "owned_surface_job", **row})

    domain_two_step, domain_two_output = _call_launchctl(
        launchctl_runner,
        "print",
        domain,
    )
    launchctl_called_count += 1
    steps.append({"phase": "owned_surface_domain_d2", **domain_two_step})
    domain_two: set[str] = set()
    domain_two_rows: dict[str, tuple[str, str]] = {}
    if domain_two_step["exit_code"] != 0:
        blockers.append(f"domain_d2_unavailable:{domain_two_step['exit_code']}")
    else:
        domain_two, domain_two_rows, parse_blockers = _parse_domain_snapshot(
            domain_two_output,
            uid_domain=domain,
        )
        blockers.extend(parse_blockers)
    if domain_one != domain_two or domain_one_rows != domain_two_rows:
        blockers.append("owned_domain_changed_d1_d2")
    if loaded != domain_one:
        blockers.append("individual_loaded_set_mismatch_d1")
    if loaded != domain_two:
        blockers.append("individual_loaded_set_mismatch_d2")
    domain_labels = domain_one | domain_two

    disk_two = _discover_disk(launchd_install_dir)
    blockers.extend(disk_two["blockers"])
    if (
        disk_one["labels"] != disk_two["labels"]
        or disk_one["plist_names"] != disk_two["plist_names"]
        or disk_one["fingerprints"] != disk_two["fingerprints"]
    ):
        blockers.append("owned_disk_changed_d1_d2")
    disk_labels |= set(disk_two["labels"])

    unknown_disk = disk_labels - expected - known
    unknown_domain = domain_labels - expected - known
    unknown_loaded = loaded - expected - known
    unknown = unknown_disk | unknown_domain | unknown_loaded
    blockers.extend(
        f"unknown_owned_label:{label}" for label in sorted(unknown)
    )
    return {
        "status": "verified" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "disk_owned_labels": sorted(disk_labels),
        "domain_owned_labels": sorted(domain_labels),
        "domain_d1_service_rows": {
            label: list(domain_one_rows[label])
            for label in sorted(domain_one_rows)
        },
        "domain_d2_service_rows": {
            label: list(domain_two_rows[label])
            for label in sorted(domain_two_rows)
        },
        "loaded_owned_labels": sorted(loaded),
        "unknown_disk_owned_labels": sorted(unknown_disk),
        "unknown_domain_owned_labels": sorted(unknown_domain),
        "unknown_loaded_owned_labels": sorted(unknown_loaded),
        "unknown_owned_labels": sorted(unknown),
        "known_conflicting_loaded_labels": sorted(loaded & known),
        "production_loaded_labels": sorted(loaded & expected),
        "production_disk_labels": sorted(disk_labels & expected),
        "disk_fingerprints": disk_one["fingerprints"],
        "launchctl_called_count": launchctl_called_count,
        "steps": steps,
        "jobs": jobs,
    }


def validate_exact_owned_launchd_surface(
    *,
    launchd_install_dir: Path,
    allowed_production_labels: tuple[str, ...] = PRODUCTION_LABELS,
    known_conflicting_labels: tuple[str, ...] = KNOWN_CONFLICTING_LABELS,
    launchctl_runner: Any = subprocess.run,
    uid: int | None = None,
) -> dict[str, Any]:
    report = inspect_owned_launchd_surface(
        launchd_install_dir=launchd_install_dir,
        allowed_production_labels=allowed_production_labels,
        known_conflicting_labels=known_conflicting_labels,
        launchctl_runner=launchctl_runner,
        uid=uid,
    )
    expected = set(allowed_production_labels)
    disk = set(report["disk_owned_labels"])
    domain = set(report["domain_owned_labels"])
    loaded = set(report["loaded_owned_labels"])
    blockers = list(report["blockers"])
    if disk != expected:
        blockers.append("disk_not_exact_production")
    if domain != expected:
        blockers.append("domain_not_exact_production")
    if loaded != expected:
        blockers.append("loaded_not_exact_production")
    return {
        **report,
        "status": "verified_exact" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "disk_exact_production": disk == expected,
        "domain_exact_production": domain == expected,
        "loaded_exact_production": loaded == expected,
    }
