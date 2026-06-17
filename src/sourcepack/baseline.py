from __future__ import annotations
from pathlib import Path


def protected_baseline_path(path: str) -> bool:
    p = path.replace("\\", "/").lstrip("./")
    return p.startswith(".sourcepack/baseline/")


def validate_baseline(repo: str | Path) -> dict:
    from .judgment import validate_baseline as _impl
    return _impl(repo)


def resolve_active_baseline(repo: str | Path) -> dict:
    from .judgment import resolve_active_baseline as _impl
    return _impl(repo)


def build_current_baseline(repo: str | Path, quiet: bool = False, fail_stage: str | None = None):
    from .judgment import build_current_baseline as _impl
    return _impl(repo, quiet=quiet, fail_stage=fail_stage)


def baseline_report_fields(status: dict) -> dict:
    from .judgment import baseline_report_fields as _impl
    return _impl(status)
