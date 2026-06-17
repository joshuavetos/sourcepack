from __future__ import annotations

class SourcePackError(Exception):
    """Base class for typed SourcePack core failures."""

class BaselineMissingError(SourcePackError):
    pass

class BaselineCorruptError(SourcePackError):
    pass

class MalformedDiffError(SourcePackError):
    pass

class UnsafePathError(SourcePackError):
    pass

class UnsupportedEcosystemError(SourcePackError):
    pass
