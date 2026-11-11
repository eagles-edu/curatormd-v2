"""Coordinate the owner-managed Codex map and VS Code User settings."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import NoReturn, cast

from .host_database_bindings import (
    DEFAULT_DATABASE_BINDINGS_PATH,
    load_project_database_bindings,
    validate_project_database_path,
)
from .project_access import ProjectBindingStartupError

SETTING = "curatormdV2.databaseBindings"
MAX_SETTINGS_BYTES = 2 * 1024 * 1024
DEFAULT_SETTINGS = Path.home() / ".config" / "Code" / "User" / "settings.json"


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate settings key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> NoReturn:
    raise ValueError("settings contain an invalid JSON constant")


def _clean_jsonc(text: str) -> tuple[str, set[int]]:
    """Mask comments and trailing commas while preserving character offsets."""

    chars = list(text)
    if chars and chars[0] == "\ufeff":
        chars[0] = " "
    comment_offsets: set[int] = set()
    index = 0
    in_string = False
    while index < len(text):
        char = text[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "/" and index + 1 < len(text) and text[index + 1] in "/*":
            start = index
            if text[index + 1] == "/":
                end = text.find("\n", index + 2)
                end = len(text) if end < 0 else end
            else:
                end = text.find("*/", index + 2)
                if end < 0:
                    raise ValueError("unterminated settings comment")
                end += 2
            for position in range(start, end):
                comment_offsets.add(position)
                if chars[position] not in "\r\n":
                    chars[position] = " "
            index = end
            continue
        index += 1
    if in_string:
        raise ValueError("unterminated settings string")
    cleaned = "".join(chars)
    in_string = False
    index = 0
    while index < len(cleaned):
        char = cleaned[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == ",":
            following = index + 1
            while following < len(cleaned) and cleaned[following].isspace():
                following += 1
            if following < len(cleaned) and cleaned[following] in "}]":
                chars[index] = " "
        index += 1
    return "".join(chars), comment_offsets


def _settings_value_span(cleaned: str) -> tuple[int, int] | None:
    """Find only the top-level binding value after the JSONC is validated."""

    decoder = json.JSONDecoder()
    index = cleaned.index("{") + 1
    while True:
        while index < len(cleaned) and cleaned[index].isspace():
            index += 1
        if index >= len(cleaned) or cleaned[index] == "}":
            return None
        key, index = decoder.raw_decode(cleaned, index)
        while cleaned[index].isspace():
            index += 1
        if cleaned[index] != ":":
            raise ValueError("invalid settings object")
        index += 1
        while cleaned[index].isspace():
            index += 1
        start = index
        _, index = decoder.raw_decode(cleaned, index)
        if key == SETTING:
            return start, index
        while cleaned[index].isspace():
            index += 1
        if cleaned[index] == "}":
            return None
        if cleaned[index] != ",":
            raise ValueError("invalid settings object")
        index += 1


def _read_settings(path: Path) -> tuple[bytes, os.stat_result]:
    if not path.is_absolute() or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("settings path must be an absolute regular file")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or info.st_size > MAX_SETTINGS_BYTES
        ):
            raise ValueError("settings file is not an owner-controlled regular file")
        chunks: list[bytes] = []
        total = 0
        while chunk := os.read(descriptor, min(65536, MAX_SETTINGS_BYTES + 1 - total)):
            total += len(chunk)
            if total > MAX_SETTINGS_BYTES:
                raise ValueError("settings file exceeds size limit")
            chunks.append(chunk)
        return b"".join(chunks), info
    finally:
        os.close(descriptor)


def _read_settings_document(data: bytes) -> tuple[str, str, dict[str, object], set[int]]:
    text = data.decode("utf-8")
    cleaned, comments = _clean_jsonc(text)
    document: object = json.loads(
        cleaned, object_pairs_hook=_unique_object, parse_constant=_reject_constant
    )
    if not isinstance(document, dict):
        raise ValueError("settings root must be an object")
    return text, cleaned, cast(dict[str, object], document), comments


def _canonical_bindings(path: Path) -> dict[str, str]:
    raw = load_project_database_bindings(path)
    if not raw:
        raise ValueError("database map must contain at least one project")
    result: dict[str, str] = {}
    for project_id, value in raw.items():
        if not isinstance(value, str):
            raise ValueError("database map contains an invalid path")
        validate_project_database_path(value)
        result[project_id] = value
    return result


def _replace_if_unchanged(path: Path, original: bytes, info: os.stat_result, updated: bytes) -> None:
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".curator-settings-", delete=False) as stream:
            temporary = stream.name
            os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode))
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        current, current_info = _read_settings(path)
        if (current_info.st_dev, current_info.st_ino) != (info.st_dev, info.st_ino) or current != original:
            raise ValueError("settings changed while preparing update; retry")
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)


def coordinate(bindings_path: Path, settings_path: Path, *, apply: bool, replace: bool) -> str:
    """Compare or synchronize User settings from the exact owner map."""

    canonical = _canonical_bindings(bindings_path)
    original, info = _read_settings(settings_path)
    if os.path.samefile(bindings_path, settings_path):
        raise ValueError("database map and VS Code settings must be different files")
    text, cleaned, document, comments = _read_settings_document(original)
    existing = document.get(SETTING, {})
    if not isinstance(existing, dict):
        raise ValueError("VS Code database bindings must be an object")
    previous = cast(dict[str, object], existing)
    if previous == canonical:
        return "in-sync"
    if not apply:
        return "drift"
    if not replace and any(key not in canonical or canonical[key] != value for key, value in previous.items()):
        raise ValueError("existing bindings conflict; use --replace-conflicts after review")
    span = _settings_value_span(cleaned)
    if span and any(span[0] <= index < span[1] for index in comments):
        raise ValueError("binding value contains comments; update it manually")
    newline = "\r\n" if "\r\n" in text else "\n"
    formatted = json.dumps(canonical, ensure_ascii=False, indent=2)
    if span:
        line_start = text.rfind("\n", 0, span[0]) + 1
        indent = text[line_start:span[0] - len(text[line_start:span[0]].lstrip())]
        formatted = formatted.replace("\n", newline + indent)
        updated = text[:span[0]] + formatted + text[span[1]:]
    else:
        start = cleaned.index("{") + 1
        formatted = formatted.replace("\n", newline + "  ")
        entry = f'{newline}  {json.dumps(SETTING)}: {formatted}'
        updated = text[:start] + entry + ("," if document else "") + text[start:]
    updated_bytes = updated.encode("utf-8")
    _read_settings_document(updated_bytes)
    if _canonical_bindings(bindings_path) != canonical:
        raise ValueError("database map changed while preparing update; retry")
    _replace_if_unchanged(settings_path, original, info, updated_bytes)
    saved, _ = _read_settings(settings_path)
    if saved != updated_bytes or _canonical_bindings(bindings_path) != canonical:
        raise ValueError("bindings changed after update; check and retry")
    return "updated"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coordinate Codex and VS Code project database bindings.")
    parser.add_argument("--map", type=Path, default=DEFAULT_DATABASE_BINDINGS_PATH)
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    parser.add_argument("--apply", action="store_true", help="update VS Code User settings from the map")
    parser.add_argument("--replace-conflicts", action="store_true", help="permit replacement or removal of existing entries")
    args = parser.parse_args(argv)
    if args.replace_conflicts and not args.apply:
        parser.error("--replace-conflicts requires --apply")
    try:
        result = coordinate(args.map.expanduser(), args.settings.expanduser(), apply=args.apply, replace=args.replace_conflicts)
    except (OSError, UnicodeError, json.JSONDecodeError):
        print("Bindings coordination failed: a file is unavailable or invalid", file=sys.stderr)
        return 2
    except (ValueError, ProjectBindingStartupError) as exc:
        print(f"Bindings coordination failed: {exc}", file=sys.stderr)
        return 2
    print(f"Curator database bindings: {result}")
    return 1 if result == "drift" else 0


if __name__ == "__main__":
    raise SystemExit(main())
