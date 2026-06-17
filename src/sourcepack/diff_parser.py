from __future__ import annotations


def normalize_diff_path(path: str) -> tuple[str, bool]:
    from .cli import _normalize_diff_path as _impl
    return _impl(path)


def parse_unified_diff(text: str):
    from .cli import parse_unified_diff as _impl
    return _impl(text)

PatchFileChange = None  # exported dynamically by parse users through sourcepack.cli compatibility
