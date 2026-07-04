from __future__ import annotations

from types import MappingProxyType
from typing import Final


PY_IMPORT_ALIASES: Final = MappingProxyType(
    {
        "yaml": "pyyaml",
        "cv2": "opencv-python",
        "pil": "pillow",
        "sklearn": "scikit-learn",
        "bs4": "beautifulsoup4",
        "dotenv": "python-dotenv",
        "jwt": "pyjwt",
        "dateutil": "python-dateutil",
    }
)
