from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_baseline_lifecycle_documents_trust_separation_and_ci_rules() -> None:
    text = read("docs/baseline-lifecycle.md")
    required = [
        ".sourcepack/baseline/",
        ".sourcepack/prompt/",
        "Prompt context cannot prove",
        "CI must not run `sourcepack init`",
        "CI will not create or update trusted baseline state automatically.",
        "Generating baseline inside untrusted PR CI.",
        "Using SourcePack as proof of runtime correctness.",
        "Using SourcePack as a dependency safety scanner.",
    ]
    for phrase in required:
        assert phrase in text


def test_release_checklist_has_required_sections() -> None:
    text = read("docs/release-checklist.md").lower()
    sections = [
        "preflight gates",
        "build wheel/sdist",
        "wheel install smoke",
        "sdist install smoke",
        "sourcepack console smoke",
        "github action wrapper smoke",
        "real-corpus local smoke",
        "behavior matrix smoke",
        "readme truth check",
        "version/provenance capture",
        "pypi publish steps as manual checklist only",
        "rollback notes",
    ]
    for section in sections:
        assert f"## {section}" in text


def test_public_alpha_readiness_documents_non_claims_and_limitations() -> None:
    text = read("docs/public-alpha-readiness.md")
    for claim in [
        "Code correctness.",
        "Security.",
        "Dependency safety.",
        "Runtime success.",
        "Semantic validity.",
        "External API truth.",
        "User intent.",
    ]:
        assert claim in text
    for limitation in [
        "Unsupported ecosystems remain WARN/YELLOW.",
        "Baseline must be maintained intentionally.",
        "CI must not create trust state.",
        "Local evidence can only verify local evidence.",
        "Real repos may expose layout cases not yet covered.",
    ]:
        assert limitation in text
