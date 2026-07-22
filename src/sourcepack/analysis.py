from __future__ import annotations

from enum import Enum


class AnalysisStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"
    UNREVIEWABLE = "UNREVIEWABLE"
