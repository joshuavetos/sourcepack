import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_existing_pythonpath = os.environ.get("PYTHONPATH")
if _existing_pythonpath:
    _parts = _existing_pythonpath.split(os.pathsep)
    if str(SRC) not in _parts:
        os.environ["PYTHONPATH"] = os.pathsep.join([str(SRC), *_parts])
else:
    os.environ["PYTHONPATH"] = str(SRC)
