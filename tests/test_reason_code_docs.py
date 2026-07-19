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

# ``change_supported`` is a Workbench presentation label for canonical PASS
# with no blocking findings. It must not be added to canonical reason-code
# registries or emitted as a report finding.
PUBLIC_REASON_CODE_ALLOWLIST = {"change_supported", "input_schema_version"}


def test_public_docs_do_not_reference_new_command_reason_code() -> None:
    public_paths = [ROOT / "README.md", ROOT / "docs" / "ci.md", ROOT / "docs" / "reason-codes.md", ROOT / "src" / "sourcepack" / "workbench_static" / "index.html"]
    for path in public_paths:
        assert "new_command" not in path.read_text(encoding="utf-8"), str(path)


def test_readme_backtick_reason_codes_are_canonical_or_allowlisted() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    codes = set(re.findall(r"`([a-z][a-z0-9_]+)`", text))
    likely_codes = {code for code in codes if "_" in code}
    assert likely_codes <= set(canonical_reason_codes()) | PUBLIC_REASON_CODE_ALLOWLIST
