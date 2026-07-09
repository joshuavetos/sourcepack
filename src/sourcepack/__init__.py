from __future__ import annotations

import os
from pathlib import Path

__version__ = "1.10.0a3"

# Keep subprocess-based development/test invocations runnable from temporary
# repositories before the package is installed. Installed packages do not need
# this, but local `python -m sourcepack.cli` smoke tests spawned from another
# cwd do.
_src_root = str(Path(__file__).resolve().parents[1])
_pythonpath = os.environ.get("PYTHONPATH")
if _pythonpath:
    _parts = _pythonpath.split(os.pathsep)
    if _src_root not in _parts:
        os.environ["PYTHONPATH"] = os.pathsep.join([_src_root, *_parts])
else:
    os.environ["PYTHONPATH"] = _src_root
