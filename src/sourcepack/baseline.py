from __future__ import annotations


def protected_baseline_path(path: str) -> bool:
    p = path.replace("\\", "/").lstrip("./")
    return p.startswith(".sourcepack/baseline/")
