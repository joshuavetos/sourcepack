"""Command resolver and CLI command modules."""


import configparser
import json
import re
from dataclasses import dataclass
from pathlib import Path

from sourcepack.analysis import AnalysisStatus

COMMAND_SCHEMA_VERSION = "sourcepack.command_resolver.v2"
COMPOSE_FILES = ("compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml")


@dataclass(frozen=True)
class CommandResolution:
    verdict: str
    reason_code: str | None
    command: str
    evidence_source: str | None = None
    message: str = ""
    analysis_status: str | None = None
    evidence_class: str | None = None
    trust_status: str | None = None
    modified_by_patch: bool = False

    def to_dict(self) -> dict:
        return {
            "schema_version": COMMAND_SCHEMA_VERSION,
            "verdict": self.verdict,
            "reason_code": self.reason_code,
            "command": self.command,
            "evidence_source": self.evidence_source,
            "message": self.message,
            "analysis_status": self.analysis_status,
            "evidence_class": self.evidence_class,
            "trust_status": self.trust_status,
            "modified_by_patch": self.modified_by_patch,
        }


def _safe(root: Path, rel: str) -> Path | None:
    p = (root / rel).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        return None
    return p


def _read_json(path: Path) -> tuple[dict | None, bool]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, False
    return parsed if isinstance(parsed, dict) else None, isinstance(parsed, dict)


def _read_json_from_text(text: str) -> tuple[dict | None, bool]:
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None, False
    return parsed if isinstance(parsed, dict) else None, isinstance(parsed, dict)


def _make_targets(text: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"^([A-Za-z0-9_.-][^\s:=]*)\s*:(?!=)", text, re.M)}


def _just_targets(text: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"^([A-Za-z0-9_.-]+)\s*:", text, re.M)}


def _taskfile_targets(data: dict) -> set[str]:
    tasks = data.get("tasks") if isinstance(data, dict) else None
    return set(tasks.keys()) if isinstance(tasks, dict) else set()


def resolve_command(root: str | Path, command: str, *, added_manifests: dict[str, str] | None = None) -> CommandResolution:
    root = Path(root).resolve(); added_manifests = added_manifests or {}; command = command.strip()
    parts = command.split()
    if not parts:
        return CommandResolution(
            "WARN", "command_check_inconclusive", command, message="empty command",
            analysis_status=AnalysisStatus.UNKNOWN.value,
            evidence_class="analysis_state", trust_status="unknown",
        )
    if len(parts) >= 3 and parts[0] == "npm" and parts[1] == "run":
        script = parts[2]
        pj = _safe(root, "package.json")
        if "package.json" in added_manifests:
            proposed, valid = _read_json_from_text(added_manifests["package.json"])
            if not valid:
                return CommandResolution(
                    "FAIL", "manifest_parse_failure", command, "package.json",
                    "proposed command evidence could not be parsed",
                    AnalysisStatus.UNREVIEWABLE.value, "analysis_state", "invalid", True,
                )
            if script in (proposed.get("scripts") or {}):
                return CommandResolution(
                    "WARN", "declared_command", command, "package.json", "script added in patch",
                    AnalysisStatus.UNKNOWN.value, "proposed_state", "untrusted_until_accepted", True,
                )
        if not pj or not pj.exists():
            return CommandResolution(
                "WARN", "command_manifest_missing", command, "package.json", "package.json missing",
                AnalysisStatus.UNKNOWN.value, "analysis_state", "missing", False,
            )
        data, valid = _read_json(pj)
        if not valid:
            return CommandResolution(
                "FAIL", "manifest_parse_failure", command, "package.json",
                "command evidence could not be parsed",
                AnalysisStatus.UNREVIEWABLE.value, "analysis_state", "invalid", False,
            )
        if script in (data.get("scripts") or {}):
            return CommandResolution(
                "PASS", None, command, "package.json", "script present",
                AnalysisStatus.SUPPORTED.value, "command_manifest", "trusted_preexisting", False,
            )
        return CommandResolution(
            "FAIL", "unsupported_command", command, "package.json", "npm script missing",
            AnalysisStatus.UNSUPPORTED.value, "command_manifest", "trusted_preexisting", False,
        )
    if len(parts) >= 3 and parts[0] == "docker" and parts[1] == "compose":
        for name in COMPOSE_FILES:
            p = _safe(root, name)
            if p and p.exists():
                return CommandResolution("PASS", None, command, name, "compose file present")
        return CommandResolution("FAIL", "unsupported_command", command, ",".join(COMPOSE_FILES), "compose file missing")
    if parts[0] == "make" and len(parts) >= 2:
        p = _safe(root, "Makefile")
        if not p or not p.exists():
            return CommandResolution("WARN", "command_manifest_missing", command, "Makefile", "Makefile missing")
        targets = _make_targets(p.read_text(encoding="utf-8", errors="ignore"))
        return CommandResolution("PASS", None, command, "Makefile", "target present") if parts[1] in targets else CommandResolution("FAIL", "unsupported_command", command, "Makefile", "Make target missing")
    if parts[0] == "just" and len(parts) >= 2:
        p = _safe(root, "justfile") or _safe(root, "Justfile")
        if not p or not p.exists():
            return CommandResolution("WARN", "command_manifest_missing", command, "justfile", "justfile missing")
        targets = _just_targets(p.read_text(encoding="utf-8", errors="ignore"))
        return CommandResolution("PASS", None, command, str(p.name), "recipe present") if parts[1] in targets else CommandResolution("FAIL", "unsupported_command", command, str(p.name), "recipe missing")
    if parts[0] == "task" and len(parts) >= 2:
        for name in ("Taskfile.yml", "Taskfile.yaml"):
            p = _safe(root, name)
            if p and p.exists():
                try:
                    import yaml  # type: ignore
                    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                except Exception:
                    data = _simple_taskfile_parse(p.read_text(encoding="utf-8", errors="ignore"))
                targets = _taskfile_targets(data)
                return CommandResolution("PASS", None, command, name, "task present") if parts[1] in targets else CommandResolution("FAIL", "unsupported_command", command, name, "task missing")
        return CommandResolution("WARN", "command_manifest_missing", command, "Taskfile.yml", "Taskfile missing")
    if parts[0] in {"pytest", "py.test"} or (len(parts) >= 3 and parts[0] == "python" and parts[1] == "-m" and parts[2] == "pytest"):
        has_tests = any((root / name).exists() for name in ("tests", "test", "pytest.ini"))
        if has_tests:
            return CommandResolution("PASS", None, command, "tests", "pytest evidence present")
        pyproject = _safe(root, "pyproject.toml")
        requirements = list(root.glob("requirements*.txt"))
        manifest_text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in ([pyproject] if pyproject and pyproject.exists() else []) + requirements)
        if re.search(r"(?im)\bpytest\b", manifest_text):
            return CommandResolution("PASS", None, command, "python dependency manifest", "pytest dependency present")
        return CommandResolution("FAIL", "unsupported_command", command, "tests/pytest.ini/pyproject.toml", "pytest project evidence missing")
    if parts[0] == "tox" and "-e" in parts:
        env = parts[parts.index("-e") + 1] if parts.index("-e") + 1 < len(parts) else ""
        p = _safe(root, "tox.ini")
        if not p or not p.exists():
            return CommandResolution("WARN", "command_check_inconclusive", command, "tox.ini", "tox.ini missing")
        cp = configparser.ConfigParser(); cp.read(p)
        raw = cp.get("tox", "envlist", fallback="")
        if "{" in raw or "}" in raw or not raw:
            return CommandResolution("WARN", "command_check_inconclusive", command, "tox.ini", "dynamic or missing envlist")
        envs = {e.strip() for e in re.split(r"[,\n]", raw) if e.strip()}
        return CommandResolution("PASS", None, command, "tox.ini", "env present") if env in envs else CommandResolution("FAIL", "unsupported_command", command, "tox.ini", "tox env missing")
    if parts[0] == "nox" and "-s" in parts:
        session = parts[parts.index("-s") + 1] if parts.index("-s") + 1 < len(parts) else ""
        p = _safe(root, "noxfile.py")
        if not p or not p.exists():
            return CommandResolution("WARN", "command_manifest_missing", command, "noxfile.py", "noxfile missing")
        text = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"@nox\.session(?:\([^)]*\))?\s*\ndef\s+" + re.escape(session) + r"\b", text):
            return CommandResolution("PASS", None, command, "noxfile.py", "session present")
        return CommandResolution("WARN", "command_check_inconclusive", command, "noxfile.py", "dynamic or missing nox session")
    return CommandResolution(
        "WARN", "command_check_inconclusive", command, message="command parser unsupported",
        analysis_status=AnalysisStatus.UNKNOWN.value,
        evidence_class="analysis_state", trust_status="unknown",
    )


def _simple_taskfile_parse(text: str) -> dict:
    tasks: dict[str, dict] = {}
    in_tasks = False
    for line in text.splitlines():
        if re.match(r"^tasks:\s*$", line):
            in_tasks = True; continue
        if in_tasks:
            m = re.match(r"^\s{2}([A-Za-z0-9_.-]+):", line)
            if m: tasks[m.group(1)] = {}
    return {"tasks": tasks}
