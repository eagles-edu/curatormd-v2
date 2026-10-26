#!/usr/bin/env python3
"""Count delivery checklist rows, excluding Section 11's reusable workflow contract."""

from __future__ import annotations

import re
from pathlib import Path


_SECTION = re.compile(r"^### (\d+)\.")
_CHECKBOX = re.compile(r"^- \[([ xX])\] ")
_DELIVERY_SECTIONS = frozenset((*range(11), 12))


def count_delivery_rows(plan: Path) -> tuple[int, int]:
    """Return checked and total top-level rows in delivery sections 0–10 and 12."""

    section: int | None = None
    in_fence = False
    checked = 0
    total = 0

    for line in plan.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        heading = _SECTION.match(line)
        if heading:
            section = int(heading.group(1))
            continue

        if section not in _DELIVERY_SECTIONS:
            continue
        checkbox = _CHECKBOX.match(line)
        if checkbox:
            total += 1
            checked += checkbox.group(1).lower() == "x"

    return checked, total


def main() -> None:
    plan = Path(__file__).resolve().parents[1] / "docs" / "curator-v2-plan.md"
    checked, total = count_delivery_rows(plan)
    print(
        f"Curator V2 delivery checklist (sections 0–10 and 12): "
        f"{checked}/{total} complete; {total - checked} open"
    )


if __name__ == "__main__":
    main()
