from __future__ import annotations

import re
from pathlib import Path

from sourcepack.reason_codes import canonical_reason_codes

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reason-codes.md"


def documented_codes() -> set[str]:
    text = DOC.read_text(encoding="utf-8")
    return set(re.findall(r"^## ([a-z0-9_]+)$", text, flags=re.MULTILINE))


def test_reason_code_docs_include_every_canonical_code() -> None:
    assert set(canonical_reason_codes()) <= documented_codes()


def test_reason_code_docs_do_not_include_unknown_codes() -> None:
    assert documented_codes() <= set(canonical_reason_codes())


def test_reason_code_docs_preserve_non_claims() -> None:
    text = DOC.read_text(encoding="utf-8")
    for phrase in [
        "does not prove code correctness",
        "does not prove dependency safety",
        "does not prove runtime success",
        "does not prove semantic validity",
    ]:
        assert phrase in text
