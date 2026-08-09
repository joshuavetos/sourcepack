from __future__ import annotations

import re
from pathlib import Path


_PACKET_ARTIFACT_NAMES = frozenset({
    "ai_instructions.md", "context.md", "context.xml", "file_inventory.json",
    "file_tree.txt", "ignored_files.txt", "manifest.json", "reality_map.json",
    "receipt.json", "redactions.json", "token_report.json",
})
_PROMPT_ARTIFACTS = frozenset({
    ".sourcepack/prompt/ai_instructions.md",
    ".sourcepack/prompt/prompt.md",
    ".sourcepack/prompt/reality_map.json",
})
_REPORT_ARTIFACTS = frozenset({
    ".sourcepack/reports/latest.json", ".sourcepack/reports/latest.md",
    ".sourcepack/reports/latest.html", ".sourcepack/reports/latest.sarif.json",
    ".sourcepack/reports/latest_diff.json", ".sourcepack/reports/latest_prompt.json",
    ".sourcepack/reports/latest_baseline.json",
})
_ARCHIVED_REPORT = re.compile(r"^\.sourcepack/reports/archive/\d{8}T\d{12}Z_(?:report|diff|prompt|baseline|auto)\.(?:json|md)$")
_TEMP_REPORT = re.compile(r"^\.sourcepack/reports/\.latest\.json\.\d+\.tmp$")


def sourcepack_paths(repo: str | Path) -> dict[str, Path]:
    root = Path(repo).resolve()
    base = root / ".sourcepack"
    baseline = base / "baseline"
    prompt = base / "prompt"
    reports = base / "reports"
    return {
        "root": root,
        "base": base,
        "current": base / "current",  # legacy compatibility marker only
        "baseline": baseline,
        "packet": baseline / "packet",
        "baseline_meta": baseline / "metadata.json",
        "prompt_dir": prompt,
        "prompt_packet": prompt / "packet",
        "prompt_reality": prompt / "reality_map.json",
        "prompt_instructions": prompt / "ai_instructions.md",
        "reports": reports,
        "archive": reports / "archive",
        "reality": baseline / "reality_map.json",
        "instructions": baseline / "ai_instructions.md",
        "prompt": prompt / "prompt.md",
        "state": base / "state",
        "stale_marker": base / "state" / "baseline_stale.json",
        "latest_json": reports / "latest.json",
        "latest_md": reports / "latest.md",
        "latest_html": reports / "latest.html",
        "latest_sarif": reports / "latest.sarif.json",
        "latest_diff_json": reports / "latest_diff.json",
        "latest_prompt_json": reports / "latest_prompt.json",
        "latest_baseline_json": reports / "latest_baseline.json",
        "builds": baseline / "builds",
        "active_pointer": baseline / "active.json",
        "baseline_lock": base / "state" / "baseline.lock",
    }


def ensure_sourcepack_dirs(repo: str | Path) -> dict[str, Path]:
    paths = sourcepack_paths(repo)
    paths["baseline"].mkdir(parents=True, exist_ok=True)
    paths["prompt_dir"].mkdir(parents=True, exist_ok=True)
    paths["current"].mkdir(parents=True, exist_ok=True)
    paths["reports"].mkdir(parents=True, exist_ok=True)
    paths["archive"].mkdir(parents=True, exist_ok=True)
    paths["state"].mkdir(parents=True, exist_ok=True)
    return paths


def operational_sourcepack_artifact_path(path: str) -> bool:
    """Return whether a path is non-authority output from an operational owner."""
    normalized = path.replace("\\", "/").removeprefix("./")
    return bool(
        normalized in _PROMPT_ARTIFACTS
        or normalized in _REPORT_ARTIFACTS
        or _ARCHIVED_REPORT.fullmatch(normalized)
        or _TEMP_REPORT.fullmatch(normalized)
        or normalized in {
            ".sourcepack/state/baseline.lock",
            ".sourcepack/state/baseline_stale.json",
        }
        or normalized.removeprefix(".sourcepack/prompt/packet/") in _PACKET_ARTIFACT_NAMES
    )


def ensure_gitignore_entry(repo: str | Path) -> tuple[bool, str | None]:
    path = Path(repo) / ".gitignore"
    try:
        if not path.exists():
            path.write_text(".sourcepack/\n", encoding="utf-8")
            return True, None
        data = path.read_bytes()
        text = data.decode("utf-8")
        if any(line.strip() in {".sourcepack", ".sourcepack/", ".sourcepack/*"} for line in text.splitlines()):
            return False, None
        newline = "\r\n" if b"\r\n" in data else "\n"
        addition = ("" if text.endswith(("\n", "\r\n")) or not text else newline) + ".sourcepack/" + newline
        path.write_text(text + addition, encoding="utf-8", newline="")
        return True, None
    except Exception as exc:
        return False, str(exc)
