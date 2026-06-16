from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path

from sourcepack.cli import patch_report_to_traffic, sha256_text

MUST_RED = "MUST_RED"
MUST_NOT_RED = "MUST_NOT_RED"
MUST_YELLOW = "MUST_YELLOW"
MAY_YELLOW_OR_GREEN = "MAY_YELLOW_OR_GREEN"
MUST_FAIL_CLOSED = "MUST_FAIL_CLOSED"


@dataclass(frozen=True)
class Scenario:
    name: str
    files: dict[str, str]
    patch: str
    expectation: str
    expected_id: str | None = None
    forbidden_ids: set[str] = field(default_factory=set)
    repo_shape: str = ""
    summary: str = ""


def unified_patch(path: str, old: str, new: str, new_file: bool = False, deleted: bool = False) -> str:
    old_lines = [] if new_file else old.splitlines()
    new_lines = [] if deleted else new.splitlines()
    body = "\n".join(difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="")) + "\n"
    prefix = f"diff --git a/{path} b/{path}\n"
    if new_file:
        prefix += "new file mode 100644\n"
    if deleted:
        prefix += "deleted file mode 100644\n"
    return prefix + body


def multi_patch(parts: list[tuple[str, str, str]]) -> str:
    return "".join(unified_patch(path, old, new) for path, old, new in parts)


def write_packet(tmp_path: Path, files: dict[str, str]) -> Path:
    packet = tmp_path / "packet"
    packet.mkdir()
    included = []
    context = ["# SourcePack Context", ""]
    for rel, content in sorted(files.items()):
        included.append({"relative_path": rel, "sha256": sha256_text(content), "extension": Path(rel).suffix})
        context.extend([f"## File: {rel}", "", "Content:", content.rstrip("\n"), "---", ""])
    manifest = {"included_files": included}
    (packet / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (packet / "context.md").write_text("\n".join(context), encoding="utf-8")
    (packet / "reality_map.json").write_text(json.dumps({"supported_commands": []}), encoding="utf-8")
    (packet / "receipt.json").write_text(json.dumps({"hashes": {}}), encoding="utf-8")
    return packet


def summarize(report: dict) -> dict:
    traffic = patch_report_to_traffic(report)
    findings = traffic.get("findings", [])
    return {
        "verdict": traffic.get("verdict"),
        "light": traffic.get("light"),
        "reason_type": traffic.get("reason_type"),
        "finding_ids": {f.get("id") for f in findings},
        "unsupported_dependencies": set(report.get("unsupported_dependencies", [])),
        "unsupported_commands": set(report.get("unsupported_commands", [])),
        "protected_artifact_modifications": set(report.get("protected_artifact_modifications", [])),
        "warnings": traffic.get("warnings", []),
        "uncertainties": report.get("uncertainties", []),
        "binary_diffs": set(report.get("binary_diffs", [])),
        "raw": report,
    }


def assert_expectation(scenario: Scenario, report: dict) -> None:
    s = summarize(report)
    msg = (
        f"scenario={scenario.name}\nrepo_shape={scenario.repo_shape}\nsummary={scenario.summary}\n"
        f"expected={scenario.expectation} expected_id={scenario.expected_id}\n"
        f"actual={s['verdict']} ids={sorted(s['finding_ids'])}\nfields={s}"
    )
    if scenario.expectation == MUST_RED:
        assert s["verdict"] == "FAIL", msg
        assert scenario.expected_id in s["finding_ids"], msg
    elif scenario.expectation == MUST_NOT_RED:
        assert s["verdict"] != "FAIL", msg
        assert not (scenario.forbidden_ids & s["finding_ids"]), msg
    elif scenario.expectation == MUST_YELLOW:
        assert s["verdict"] == "WARN", msg
        assert scenario.expected_id in s["finding_ids"], msg
    elif scenario.expectation == MAY_YELLOW_OR_GREEN:
        assert s["verdict"] in {"PASS", "WARN"}, msg
    elif scenario.expectation == MUST_FAIL_CLOSED:
        assert s["verdict"] == "FAIL", msg
        assert scenario.expected_id in s["finding_ids"], msg
    else:
        raise AssertionError(f"Unknown expectation {scenario.expectation}")
