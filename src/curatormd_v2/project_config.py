"""Strict repository-owned configuration for the Curator V2 project plugin."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tomllib
from typing import cast

from .content_safety import SensitiveContentError, validate_safe_text


CONFIG_FILENAME = ".curatormd-v2.toml"
PROJECT_PLUGIN_API_VERSION = 1
MAX_CONFIG_BYTES = 16 * 1024
MAX_CHECKLIST_BYTES = 1024 * 1024
MAX_PROJECT_STAGING_BYTES = 1024**4
MAX_PROJECT_STAGING_FILES = 1_000_000
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_ROOT_FIELDS = {
    "schema_version",
    "backend_api_version",
    "project_id",
    "scope",
    "checklists",
    "evidence",
    "actions",
    "staging",
    "persistence",
}


class ProjectConfigError(ValueError):
    """A project plugin config is invalid or escapes its repository boundary."""


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Validated paths and bindings owned by one consuming repository."""

    project_root: Path
    backend_api_version: int
    project_id: str
    repository_fingerprint: str
    config_sha256: str
    readable_paths: tuple[Path, ...]
    checklist_bindings: tuple[tuple[str, Path], ...]
    evidence_adapters: tuple[str, ...]
    action_adapters: tuple[str, ...]
    staging_root: Path
    staging_max_project_bytes: int | None
    staging_max_project_files: int | None
    persistence_targets: tuple[Path, ...]

    @classmethod
    def load(
        cls,
        project_root: str | Path,
        *,
        registered_evidence_adapters: frozenset[str] = frozenset(),
        registered_action_adapters: frozenset[str] = frozenset(),
    ) -> ProjectConfig:
        """Load and validate `.curatormd-v2.toml` without executing config."""

        root, root_table, config_sha256 = _read_project_document(project_root)
        backend_api_version = root_table["backend_api_version"]
        if (
            not isinstance(backend_api_version, int)
            or isinstance(backend_api_version, bool)
            or backend_api_version != PROJECT_PLUGIN_API_VERSION
        ):
            raise ProjectConfigError(
                "backend_api_version is not supported by this Curator backend"
            )
        _validate_config_values(root_table)
        project_id = _identifier(root_table["project_id"], "project_id")
        readable_paths = _load_readable_paths(root, root_table["scope"])
        checklist_bindings = _load_checklists(
            root, root_table["checklists"], readable_paths
        )
        return cls(
            project_root=root,
            backend_api_version=backend_api_version,
            project_id=project_id,
            repository_fingerprint=hashlib.sha256(
                b"curatormd-v2-project-root-v1\0" + str(root).encode("utf-8")
            ).hexdigest(),
            config_sha256=config_sha256,
            readable_paths=readable_paths,
            checklist_bindings=checklist_bindings,
            evidence_adapters=_load_evidence_adapters(
                root_table["evidence"], registered_evidence_adapters
            ),
            action_adapters=_load_action_adapters(
                root_table.get("actions"), registered_action_adapters
            ),
            staging_root=_load_staging_root(root, root_table["staging"]),
            staging_max_project_bytes=_optional_positive_limit(
                root_table["staging"], "max_project_bytes", MAX_PROJECT_STAGING_BYTES
            ),
            staging_max_project_files=_optional_positive_limit(
                root_table["staging"], "max_project_files", MAX_PROJECT_STAGING_FILES
            ),
            persistence_targets=_load_persistence_targets(
                root, root_table["persistence"]
            ),
        )

    def checklist_path(self, checklist_id: str) -> Path:
        """Resolve a configured checklist ID, rejecting unbound IDs."""

        for bound_id, path in self.checklist_bindings:
            if bound_id == checklist_id:
                relative = path.relative_to(self.project_root).as_posix()
                refreshed = _resolve_existing_path(
                    self.project_root, relative, "checklist path"
                )
                if not refreshed.is_file() or not any(
                    _is_within(refreshed, allowed) for allowed in self.readable_paths
                ):
                    raise ProjectConfigError("checklist binding no longer satisfies read scope")
                return refreshed
        raise ProjectConfigError(f"checklist is not configured: {checklist_id}")

    def checklist_snapshot(self, checklist_id: str, exact_item_text: str) -> tuple[str, str]:
        """Verify an exact task line and return its immutable file revision.

        The repository adapter reads only the configured checklist, with a
        strict byte ceiling and no-follow open. The backend stores the selected
        line plus a digest of the complete source file, never the full file.
        """

        if not exact_item_text.strip() or len(exact_item_text) > 4000:
            raise ProjectConfigError("checklist item text must contain 1-4000 characters")
        if "\n" in exact_item_text or "\r" in exact_item_text:
            raise ProjectConfigError("checklist item text must be one exact line")
        path = self.checklist_path(checklist_id)
        no_follow = getattr(os, "O_NOFOLLOW", None)
        if no_follow is None:
            raise ProjectConfigError("platform lacks no-follow checklist reads")
        read_failed = False
        decoded = ""
        try:
            descriptor = os.open(path, os.O_RDONLY | no_follow)
            with os.fdopen(descriptor, "rb") as source:
                metadata = os.fstat(source.fileno())
                if not stat.S_ISREG(metadata.st_mode):
                    raise ProjectConfigError("checklist must be a regular file")
                contents = source.read(MAX_CHECKLIST_BYTES + 1)
            if len(contents) > MAX_CHECKLIST_BYTES:
                raise ProjectConfigError(
                    f"checklist exceeds {MAX_CHECKLIST_BYTES} byte snapshot limit"
                )
        except OSError:
            read_failed = True
            contents = b""
        if read_failed:
            raise ProjectConfigError("checklist cannot be read as bounded UTF-8")
        invalid_utf8 = False
        try:
            decoded = contents.decode("utf-8")
        except UnicodeDecodeError:
            # UnicodeDecodeError retains the complete checklist snapshot.
            invalid_utf8 = True
        if invalid_utf8:
            raise ProjectConfigError("checklist cannot be read as bounded UTF-8")
        if exact_item_text not in decoded.splitlines():
            raise ProjectConfigError(
                "selected checklist item does not match an exact source line"
            )
        return f"sha256:{hashlib.sha256(contents).hexdigest()}", exact_item_text

    def validated_staging_root(self) -> Path:
        """Re-check the staging directory immediately before plugin binding."""

        relative = self.staging_root.relative_to(self.project_root).as_posix()
        refreshed = _resolve_existing_path(
            self.project_root, relative, "staging.root"
        )
        if not refreshed.is_dir():
            raise ProjectConfigError("staging.root must remain an existing directory")
        return refreshed

    def validated_persistence_target(self, target: str | Path) -> Path:
        """Revalidate one explicitly selected canonical Markdown target."""

        candidate = Path(target)
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        if candidate not in self.persistence_targets:
            raise ProjectConfigError("persistence target is not configured or allowlisted")
        relative = candidate.relative_to(self.project_root).as_posix()
        return _resolve_markdown_target(self.project_root, relative)

    def resolve_read_path(self, relative_path: str) -> Path:
        """Resolve a read-only path only under configured scope roots."""

        resolved = _resolve_existing_path(self.project_root, relative_path, "read path")
        if not any(_is_within(resolved, allowed) for allowed in self.readable_paths):
            raise ProjectConfigError("requested path is outside configured read scope")
        return resolved


def _load_readable_paths(root: Path, value: object) -> tuple[Path, ...]:
    scope = _table(value, "scope")
    _fields(scope, {"read_paths"})
    paths = tuple(
        _resolve_existing_path(root, item, "read_paths")
        for item in _string_list(scope["read_paths"], "scope.read_paths")
    )
    _unique_paths(paths, "scope.read_paths")
    if not paths:
        raise ProjectConfigError("scope.read_paths must contain at least one path")
    return paths


def _read_project_document(
    project_root: str | Path,
) -> tuple[Path, dict[str, object], str]:
    supplied_root = Path(project_root).expanduser()
    if supplied_root.is_symlink() or not supplied_root.is_dir():
        raise ProjectConfigError("project_root must be a real existing directory")
    root = supplied_root.resolve(strict=True)
    git_marker = root / ".git"
    if git_marker.is_symlink() or not (git_marker.is_dir() or git_marker.is_file()):
        raise ProjectConfigError("project_root must be the root of a Git repository")
    config_path = root / CONFIG_FILENAME
    if config_path.is_symlink() or not config_path.is_file():
        raise ProjectConfigError(f"missing regular project config: {CONFIG_FILENAME}")
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise ProjectConfigError("platform lacks no-follow project config reads")
    read_failed = False
    try:
        descriptor = os.open(config_path, os.O_RDONLY | no_follow)
        with os.fdopen(descriptor, "rb") as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise ProjectConfigError("project config must be a regular file")
            if metadata.st_uid != root.stat().st_uid:
                raise ProjectConfigError(
                    "project config owner must match the repository root owner"
                )
            if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise ProjectConfigError(
                    "project config must not be group- or world-writable"
                )
            encoded = source.read(MAX_CONFIG_BYTES + 1)
    except OSError:
        read_failed = True
        encoded = b""
    if read_failed:
        raise ProjectConfigError("project config is not valid UTF-8 TOML")
    if len(encoded) > MAX_CONFIG_BYTES:
        raise ProjectConfigError(f"config exceeds {MAX_CONFIG_BYTES} bytes")
    parse_failed = False
    document: object = {}
    try:
        document = tomllib.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        # Both decoder exceptions retain some or all of the original config.
        parse_failed = True
    if parse_failed:
        raise ProjectConfigError("project config is not valid UTF-8 TOML")
    root_table = _table(document, "root")
    _fields(root_table, _ROOT_FIELDS, optional=frozenset({"actions"}))
    version = root_table["schema_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
        raise ProjectConfigError("schema_version must be integer 1")
    return root, root_table, hashlib.sha256(encoded).hexdigest()


def _validate_config_values(value: object) -> None:
    """Reject recognizable credentials/PII without echoing config values."""

    if isinstance(value, str):
        try:
            validate_safe_text(value, "project config value")
        except SensitiveContentError as exc:
            raise ProjectConfigError(str(exc)) from exc
        return
    if isinstance(value, dict):
        for key, item in cast(dict[object, object], value).items():
            if isinstance(key, str):
                _validate_config_values(key)
            _validate_config_values(item)
        return
    if isinstance(value, list):
        for item in cast(list[object], value):
            _validate_config_values(item)


def _load_checklists(
    root: Path, value: object, readable_paths: tuple[Path, ...]
) -> tuple[tuple[str, Path], ...]:
    table = _table(value, "checklists")
    bindings: list[tuple[str, Path]] = []
    for checklist_id, relative_path in table.items():
        _identifier(checklist_id, "checklist ID")
        resolved = _resolve_existing_path(root, relative_path, "checklists")
        if not resolved.is_file():
            raise ProjectConfigError(f"checklist must be a file: {relative_path}")
        if not any(_is_within(resolved, allowed) for allowed in readable_paths):
            raise ProjectConfigError(
                f"checklist {checklist_id} is outside scope.read_paths"
            )
        bindings.append((checklist_id, resolved))
    return tuple(sorted(bindings))


def _load_evidence_adapters(
    value: object, registered_evidence_adapters: frozenset[str]
) -> tuple[str, ...]:
    table = _table(value, "evidence")
    _fields(table, {"adapters"})
    adapters = tuple(
        _identifier(item, "evidence adapter")
        for item in _string_list(table["adapters"], "evidence.adapters")
    )
    if len(adapters) != len(set(adapters)):
        raise ProjectConfigError("evidence.adapters must not contain duplicates")
    unknown = set(adapters) - registered_evidence_adapters
    if unknown:
        raise ProjectConfigError(
            "unregistered evidence adapters: " + ", ".join(sorted(unknown))
        )
    return adapters


def _load_action_adapters(
    value: object, registered_action_adapters: frozenset[str]
) -> tuple[str, ...]:
    """Load the opt-in action allowlist; omission means read-only by default."""

    if value is None:
        return ()
    table = _table(value, "actions")
    _fields(table, {"adapters"})
    adapters = tuple(
        _identifier(item, "action adapter")
        for item in _string_list(table["adapters"], "actions.adapters")
    )
    if len(adapters) != len(set(adapters)):
        raise ProjectConfigError("actions.adapters must not contain duplicates")
    unknown = set(adapters) - registered_action_adapters
    if unknown:
        raise ProjectConfigError(
            "unregistered action adapters: " + ", ".join(sorted(unknown))
        )
    return adapters


def _load_staging_root(root: Path, value: object) -> Path:
    table = _table(value, "staging")
    _fields(
        table,
        {"root", "max_project_bytes", "max_project_files"},
        optional=frozenset({"max_project_bytes", "max_project_files"}),
    )
    staging_root = _resolve_existing_path(root, table["root"], "staging.root")
    if not staging_root.is_dir() or staging_root == root:
        raise ProjectConfigError("staging.root must be a subdirectory of the project")
    return staging_root


def _optional_positive_limit(
    staging_value: object, key: str, maximum: int
) -> int | None:
    """Read an optional bounded integer staging budget from the local config."""

    table = _table(staging_value, "staging")
    value = table.get(key)
    if value is None:
        return None
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= maximum
    ):
        raise ProjectConfigError(f"staging.{key} must be an integer from 1 to {maximum}")
    return value


def _load_persistence_targets(root: Path, value: object) -> tuple[Path, ...]:
    table = _table(value, "persistence")
    _fields(table, {"targets"})
    targets = tuple(
        _resolve_markdown_target(root, item)
        for item in _string_list(table["targets"], "persistence.targets")
    )
    _unique_paths(targets, "persistence.targets")
    if not targets:
        raise ProjectConfigError(
            "persistence.targets must name at least one Markdown file"
        )
    return targets


def _table(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in cast(dict[object, object], value)
    ):
        raise ProjectConfigError(f"{name} must be a TOML table")
    return cast(dict[str, object], value)


def _fields(
    table: dict[str, object],
    expected: set[str],
    *,
    optional: frozenset[str] = frozenset(),
) -> None:
    required = expected - optional
    if not required <= table.keys() or not table.keys() <= expected:
        missing = sorted(required - table.keys())
        extra = sorted(table.keys() - expected)
        raise ProjectConfigError(f"invalid config fields; missing={missing}, extra={extra}")


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise ProjectConfigError(f"{name} must be a bounded opaque identifier")
    return value


def _string_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) for item in cast(list[object], value)
    ):
        raise ProjectConfigError(f"{name} must be an array of strings")
    return tuple(cast(list[str], value))


def _relative_parts(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ProjectConfigError(f"{name} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if (
        not path.parts
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ProjectConfigError(f"{name} must not escape the repository")
    return path.parts


def _resolve_existing_path(root: Path, value: object, name: str) -> Path:
    parts = _relative_parts(value, name)
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ProjectConfigError(f"{name} must not traverse symlinks")
    try:
        resolved = current.resolve(strict=True)
    except OSError as exc:
        raise ProjectConfigError(f"{name} does not exist: {value}") from exc
    if not _is_within(resolved, root) or resolved == root:
        raise ProjectConfigError(f"{name} must stay below the repository root")
    return resolved


def _resolve_markdown_target(root: Path, value: object) -> Path:
    parts = _relative_parts(value, "persistence.targets")
    if not parts[-1].endswith(".md"):
        raise ProjectConfigError("persistence targets must be Markdown files")
    target = root.joinpath(*parts)
    current = root
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ProjectConfigError("persistence target parent must not be a symlink")
    if not current.is_dir():
        raise ProjectConfigError("persistence target parent must already exist")
    if target.is_symlink():
        raise ProjectConfigError("persistence target must not be a symlink")
    if target.exists() and not target.is_file():
        raise ProjectConfigError("persistence target must be a regular file")
    parent = current.resolve(strict=True)
    resolved = parent / target.name
    if not _is_within(resolved, root):
        raise ProjectConfigError("persistence target must stay below the repository root")
    return resolved


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _unique_paths(paths: tuple[Path, ...], name: str) -> None:
    if len(paths) != len(set(paths)):
        raise ProjectConfigError(f"{name} must not contain duplicate paths")
