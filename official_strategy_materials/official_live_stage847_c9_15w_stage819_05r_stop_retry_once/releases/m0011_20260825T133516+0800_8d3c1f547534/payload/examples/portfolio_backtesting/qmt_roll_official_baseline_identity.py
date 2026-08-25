from __future__ import annotations

import ast
from dataclasses import dataclass
import json
from pathlib import Path
import re

from qmt_roll_official_strategy_material_resolver import (
    ActiveMaterialError,
    load_active_material_release,
    resolve_active_material,
    unique_inventory_row,
    verify_material_file,
)


OFFICIAL_CONFIG_LOGICAL_PATH = (
    "examples/portfolio_backtesting/qmt_roll_official_live_config.py"
)


class OfficialBaselineIdentityError(RuntimeError):
    """Raised when formal source, material, and active-pointer identities diverge."""


@dataclass(frozen=True)
class OfficialBaselineIdentity:
    strategy_version: str
    ruleset_version: str
    source_commit: str
    material_release_id: str
    release_commit: str
    manifest_sha256: str


def ruleset_version_from_config(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise OfficialBaselineIdentityError("official_config_not_regular")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise OfficialBaselineIdentityError("official_config_parse_failed") from exc

    values: list[str] = []
    for node in tree.body:
        value: ast.expr | None = None
        names: tuple[str, ...] = ()
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = (node.target.id,)
            value = node.value
        elif isinstance(node, ast.Assign):
            names = tuple(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
            value = node.value
        if "OFFICIAL_LIVE_RULESET_VERSION" not in names:
            continue
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            raise OfficialBaselineIdentityError("official_ruleset_version_not_literal")
        values.append(value.value)
    if len(values) != 1 or not values[0]:
        raise OfficialBaselineIdentityError("official_ruleset_version_not_unique")
    return values[0]


def _current_payload(repo_root: Path) -> dict[str, object]:
    path = repo_root / "official_strategy_materials" / "CURRENT.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfficialBaselineIdentityError("official_current_invalid") from exc
    if not isinstance(payload, dict):
        raise OfficialBaselineIdentityError("official_current_invalid")
    return payload


def load_official_baseline_identity(repo_root: Path) -> OfficialBaselineIdentity:
    try:
        repo = repo_root.resolve(strict=True)
        active = load_active_material_release(
            repo / "official_strategy_materials" / "CURRENT.json",
            repo_root=repo,
        )
        payload_config = resolve_active_material(
            active,
            logical_path=OFFICIAL_CONFIG_LOGICAL_PATH,
        )
    except (OSError, ActiveMaterialError) as exc:
        raise OfficialBaselineIdentityError(str(exc)) from exc

    ruleset_version = ruleset_version_from_config(payload_config)
    source_commit = str(active.manifest["source_commit"])
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise OfficialBaselineIdentityError("official_source_commit_invalid")

    current = _current_payload(repo)
    if "ruleset_version" in current and current["ruleset_version"] != ruleset_version:
        raise OfficialBaselineIdentityError("current_ruleset_version_mismatch")
    if "source_commit" in current and current["source_commit"] != source_commit:
        raise OfficialBaselineIdentityError("current_source_commit_mismatch")
    return OfficialBaselineIdentity(
        strategy_version=active.strategy_version,
        ruleset_version=ruleset_version,
        source_commit=source_commit,
        material_release_id=active.release_id,
        release_commit=active.release_commit,
        manifest_sha256=str(active.manifest["manifest_sha256"]),
    )


def assert_official_checkout_matches_active_material(
    repo_root: Path,
) -> OfficialBaselineIdentity:
    repo = repo_root.resolve(strict=True)
    identity = load_official_baseline_identity(repo)
    top_level_config = repo / OFFICIAL_CONFIG_LOGICAL_PATH
    top_level_ruleset = ruleset_version_from_config(top_level_config)
    if top_level_ruleset != identity.ruleset_version:
        raise OfficialBaselineIdentityError("top_level_ruleset_mismatch")

    try:
        active = load_active_material_release(
            repo / "official_strategy_materials" / "CURRENT.json",
            repo_root=repo,
        )
        row = unique_inventory_row(active.manifest, OFFICIAL_CONFIG_LOGICAL_PATH)
        verify_material_file(top_level_config, row)
    except ActiveMaterialError as exc:
        raise OfficialBaselineIdentityError("top_level_config_payload_mismatch") from exc
    return identity
