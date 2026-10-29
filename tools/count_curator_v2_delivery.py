#!/usr/bin/env python3
"""Count delivery checklist rows, excluding Section 11's reusable workflow contract."""

from __future__ import annotations

import re
from pathlib import Path


_SECTION = re.compile(r"^### (\d+)\.")
_DEFINITION_OF_DONE = re.compile(r"^### Definition of done$")
_CHECKBOX = re.compile(r"^- \[([ xX])\] ")
_DEFINITION_SECTION = 13
_DELIVERY_SECTIONS = frozenset((*range(11), 12, _DEFINITION_SECTION))
_ALL_PLAN_SECTIONS = frozenset((*range(13), _DEFINITION_SECTION))


def _count_rows(plan: Path, sections: frozenset[int]) -> tuple[int, int]:
    """Count top-level checklist rows in the selected plan sections."""

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

        if _DEFINITION_OF_DONE.match(line):
            section = _DEFINITION_SECTION
            continue

        heading = _SECTION.match(line)
        if heading:
            section = int(heading.group(1))
            continue

        if section not in sections:
            continue
        checkbox = _CHECKBOX.match(line)
        if checkbox:
            total += 1
            checked += checkbox.group(1).lower() == "x"

    return checked, total


def count_delivery_rows(plan: Path) -> tuple[int, int]:
    """Count delivery rows, excluding Section 11's reusable workflow contract."""
    return _count_rows(plan, _DELIVERY_SECTIONS)


def count_all_plan_rows(plan: Path) -> tuple[int, int]:
    """Count every top-level checklist row, including the Section 11 contract."""
    return _count_rows(plan, _ALL_PLAN_SECTIONS)


def main() -> None:
    plan = Path(__file__).resolve().parents[1] / "docs" / "curator-v2-plan.md"
    all_checked, all_total = count_all_plan_rows(plan)
    checked, total = count_delivery_rows(plan)
    print(
        f"Curator V2 full plan: {all_checked}/{all_total} complete; "
        f"{all_total - all_checked} open"
    )
    print(
        f"Delivery scope (sections 0–10, 12, and Definition of done; "
        f"Section 11 excluded): {checked}/{total} complete; {total - checked} open"
    )


if __name__ == "__main__":
    main()
