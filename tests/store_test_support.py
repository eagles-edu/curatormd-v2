"""Test helpers for patching store globals after implementation extraction."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from importlib import import_module
from typing import Any, Generator
from unittest.mock import DEFAULT, patch


@contextmanager
def patch_store_symbol(
    symbol: str, new: Any = DEFAULT, **patch_kwargs: Any
) -> Generator[None, None, None]:
    """Patch one store global in every extracted module that owns a copy."""

    module_names = [
        "curatormd_v2.store",
        "curatormd_v2.store_support_00",
        "curatormd_v2.store_support_01",
    ]
    module_names.extend(
        f"curatormd_v2.store_operations_{index:02d}" for index in range(15)
    )
    with ExitStack() as stack:
        patched = 0
        for module_name in module_names:
            module = import_module(module_name)
            if hasattr(module, symbol):
                stack.enter_context(
                    patch.object(module, symbol, new, **patch_kwargs)
                )
                patched += 1
        if not patched:
            raise AttributeError(f"store symbol is not available: {symbol}")
        yield
