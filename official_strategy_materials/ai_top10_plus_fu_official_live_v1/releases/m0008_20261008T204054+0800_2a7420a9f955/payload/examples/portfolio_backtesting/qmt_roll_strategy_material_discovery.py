from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Iterable

from qmt_roll_strategy_material_manifest import MaterialRole


class MaterialDiscoveryError(RuntimeError):
    """Raised when formal strategy dependencies are incomplete or unsafe."""


@dataclass(frozen=True)
class MaterialDeclaration:
    source_path: Path
    logical_path: str
    role: MaterialRole
    reproducibility_required: bool = True
    source_kind: str = "repo"


@dataclass(frozen=True)
class GitPathState:
    tracked: bool
    ignored: bool


@dataclass(frozen=True)
class DiscoveryResult:
    declarations: tuple[MaterialDeclaration, ...]
    repo_paths: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


_SECRET_RE = re.compile(r"(?:^|[._/\-])(password|passwd|secret|credential|token|private[_-]?key|\.env)(?:$|[._/\-])", re.I)


def _git(repo_root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def git_path_state(repo_root: Path, path: Path) -> GitPathState:
    repo = repo_root.resolve(strict=True)
    candidate = path if path.is_absolute() else repo / path
    try:
        relative = candidate.resolve(strict=False).relative_to(repo).as_posix()
    except ValueError:
        return GitPathState(tracked=False, ignored=False)
    tracked = _git(repo, "ls-files", "--error-unmatch", "--", relative).returncode == 0
    ignored = _git(repo, "check-ignore", "--quiet", "--", relative).returncode == 0
    return GitPathState(tracked=tracked, ignored=ignored)


def _module_candidates(repo: Path, current: Path, module: str, level: int = 0) -> tuple[Path, ...]:
    parts = tuple(part for part in module.split(".") if part)
    roots: list[Path] = []
    if level:
        base = current.parent
        for _ in range(max(0, level - 1)):
            base = base.parent
        roots.append(base)
    else:
        roots.extend((current.parent, repo, repo / "examples/portfolio_backtesting"))
    candidates: list[Path] = []
    for root in roots:
        if parts:
            candidates.append(root.joinpath(*parts).with_suffix(".py"))
            candidates.append(root.joinpath(*parts, "__init__.py"))
        else:
            candidates.append(root / "__init__.py")
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        normalized = candidate.resolve(strict=False)
        if normalized not in seen:
            unique.append(normalized)
            seen.add(normalized)
    return tuple(unique)


def _resolve_import(repo: Path, current: Path, module: str, level: int = 0) -> Path | None:
    for candidate in _module_candidates(repo, current, module, level):
        if candidate.is_file():
            try:
                candidate.relative_to(repo)
            except ValueError:
                continue
            return candidate
    return None


def resolve_local_import_closure(
    repo_root: Path,
    entrypoints: Iterable[Path],
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    repo = repo_root.resolve(strict=True)
    pending: list[Path] = []
    unresolved: list[str] = []
    for entrypoint in entrypoints:
        candidate = entrypoint if entrypoint.is_absolute() else repo / entrypoint
        if not candidate.is_file():
            unresolved.append(f"entrypoint_missing:{entrypoint}")
            continue
        pending.append(candidate.resolve())

    visited: set[Path] = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        try:
            tree = ast.parse(current.read_text(encoding="utf-8"), filename=str(current))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            unresolved.append(f"python_dependency_parse_failed:{current.relative_to(repo).as_posix()}:{type(exc).__name__}")
            continue
        for node in ast.walk(tree):
            imported: list[Path] = []
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = _resolve_import(repo, current, alias.name)
                    if target:
                        imported.append(target)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                target = _resolve_import(repo, current, module, node.level)
                if target:
                    imported.append(target)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    child_name = ".".join(part for part in (module, alias.name) if part)
                    child = _resolve_import(repo, current, child_name, node.level)
                    if child:
                        imported.append(child)
            elif isinstance(node, ast.Call):
                function = node.func
                is_dynamic_import = (
                    isinstance(function, ast.Name)
                    and function.id == "__import__"
                ) or (
                    isinstance(function, ast.Attribute)
                    and isinstance(function.value, ast.Name)
                    and function.value.id == "importlib"
                    and function.attr == "import_module"
                )
                if is_dynamic_import:
                    if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                        unresolved.append(
                            f"unresolved_dynamic_import:{current.relative_to(repo).as_posix()}:{getattr(node, 'lineno', 0)}"
                        )
                    else:
                        target = _resolve_import(repo, current, node.args[0].value)
                        if target:
                            imported.append(target)
            pending.extend(path for path in imported if path not in visited)
    return (
        tuple(sorted(path.relative_to(repo) for path in visited)),
        tuple(sorted(set(unresolved))),
    )


def validate_declaration(
    repo_root: Path,
    declaration: MaterialDeclaration,
    state: GitPathState,
) -> tuple[str, ...]:
    repo = repo_root.resolve(strict=True)
    source = declaration.source_path if declaration.source_path.is_absolute() else repo / declaration.source_path
    blockers: list[str] = []
    logical = PurePosixPath(declaration.logical_path)
    if not declaration.logical_path or logical.is_absolute() or ".." in logical.parts:
        blockers.append(f"invalid_logical_path:{declaration.logical_path}")
    if _SECRET_RE.search(source.as_posix()) or _SECRET_RE.search(declaration.logical_path):
        blockers.append(f"secret_material_forbidden:{declaration.logical_path}")
    if source.is_symlink():
        blockers.append(f"symlink_material_forbidden:{declaration.logical_path}")
    if not source.is_file():
        blockers.append(f"material_source_missing:{declaration.logical_path}")
        return tuple(blockers)
    try:
        source.resolve().relative_to(repo)
        inside_repo = True
    except ValueError:
        inside_repo = False
    if declaration.source_kind == "promotion_source":
        if declaration.role in {MaterialRole.RUNTIME_CODE, MaterialRole.STRATEGY_CONFIG}:
            blockers.append(f"external_runtime_dependency:{declaration.logical_path}")
        return tuple(blockers)
    if declaration.source_kind != "repo":
        blockers.append(f"unknown_source_kind:{declaration.source_kind}")
    if not inside_repo:
        blockers.append(f"repo_external_material:{declaration.logical_path}")
    if declaration.reproducibility_required and state.ignored:
        blockers.append(f"ignored_decision_asset:{declaration.logical_path}")
    if declaration.reproducibility_required and not state.tracked:
        blockers.append(f"untracked_formal_material:{declaration.logical_path}")
    return tuple(blockers)


def deduplicate_and_sort_declarations(
    declarations: Iterable[MaterialDeclaration],
    blockers: list[str] | None = None,
) -> tuple[MaterialDeclaration, ...]:
    output: dict[str, MaterialDeclaration] = {}
    sink = blockers if blockers is not None else []
    for declaration in declarations:
        existing = output.get(declaration.logical_path)
        if existing is not None and existing != declaration:
            sink.append(f"duplicate_material_logical_path:{declaration.logical_path}")
            continue
        output[declaration.logical_path] = declaration
    return tuple(output[key] for key in sorted(output))


def discover_materials(
    *,
    repo_root: Path,
    entrypoints: Iterable[Path],
    declared_paths: Iterable[Path],
    config_assets: Iterable[MaterialDeclaration],
    ai_artifacts: Iterable[MaterialDeclaration],
) -> DiscoveryResult:
    repo = repo_root.resolve(strict=True)
    import_paths, unresolved = resolve_local_import_closure(repo, entrypoints)
    declarations = list(config_assets) + list(ai_artifacts)
    runtime_paths = sorted({*map(Path, declared_paths), *import_paths}, key=lambda path: path.as_posix())
    declarations.extend(
        MaterialDeclaration(
            source_path=repo / relative,
            logical_path=relative.as_posix(),
            role=(
                MaterialRole.STRATEGY_CONFIG
                if "config" in relative.name.lower()
                else MaterialRole.RUNTIME_CODE
            ),
        )
        for relative in runtime_paths
    )
    blockers = list(unresolved)
    normalized = deduplicate_and_sort_declarations(declarations, blockers)
    for declaration in normalized:
        blockers.extend(
            validate_declaration(repo, declaration, git_path_state(repo, declaration.source_path))
        )
    repo_paths: list[str] = []
    for item in normalized:
        if item.source_kind != "repo":
            continue
        source = item.source_path if item.source_path.is_absolute() else repo / item.source_path
        try:
            repo_paths.append(source.resolve(strict=False).relative_to(repo).as_posix())
        except ValueError:
            continue
    return DiscoveryResult(
        declarations=normalized,
        repo_paths=tuple(sorted(set(repo_paths))),
        blockers=tuple(sorted(set(blockers))),
        warnings=(),
    )


def assert_discovery_publishable(result: DiscoveryResult) -> None:
    if result.blockers:
        raise MaterialDiscoveryError(";".join(result.blockers))
