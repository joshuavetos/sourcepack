#!/usr/bin/env python3
"""Thin GitHub Action wrapper for the existing SourcePack CLI."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _truthy(value: str | bool | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _verdict_from_json(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    verdict = data.get("verdict")
    return verdict if isinstance(verdict, str) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SourcePack for GitHub Actions.")
    parser.add_argument("--mode", choices=["ci", "strict", "local"], default="ci")
    parser.add_argument("--baseline-path", default=".sourcepack/baseline")
    parser.add_argument("--report-dir", default="sourcepack-report")
    parser.add_argument("--json", default="true")
    parser.add_argument("--markdown", default="true")
    parser.add_argument("--fail-on-warn", default="false")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    baseline = (repo / args.baseline_path).resolve()
    report_dir = (repo / args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    command_log = report_dir / "sourcepack-command.txt"
    stdout_log = report_dir / "sourcepack.stdout.txt"
    stderr_log = report_dir / "sourcepack.stderr.txt"
    json_report = report_dir / "sourcepack.json"
    markdown_report = report_dir / "sourcepack.md"

    if not baseline.exists():
        message = (
            f"SourcePack baseline not found: {args.baseline_path}\n"
            "CI will not create or update trusted baseline state automatically.\n"
            "Create or refresh the baseline only from a trusted maintainer-controlled workflow or local maintainer environment.\n"
        )
        _write(command_log, "baseline preflight\n")
        _write(stdout_log, "")
        _write(stderr_log, message)
        _write(markdown_report, f"# SourcePack\n\n```text\n{message}```\n")
        print(message, file=sys.stderr, end="")
        return 2

    command = ["sourcepack", "diff", str(repo)]
    if _truthy(args.json) or args.mode == "ci":
        command.append("--json")
    if args.mode == "ci":
        command.append("--ci")
    elif args.mode == "strict" or _truthy(args.fail_on_warn):
        command.append("--strict")

    _write(command_log, " ".join(command) + "\n")
    result = _run(command, repo)
    _write(stdout_log, result.stdout)
    _write(stderr_log, result.stderr)

    if _truthy(args.json):
        _write(json_report, result.stdout)

    latest_json = repo / ".sourcepack" / "reports" / "latest.json"
    if latest_json.exists():
        shutil.copyfile(latest_json, json_report)

    if _truthy(args.markdown):
        verdict = _verdict_from_json(json_report) or "UNKNOWN"
        _write(
            markdown_report,
            "# SourcePack report\n\n"
            f"Verdict: {verdict}\n\n"
            "## Command\n\n"
            f"```text\n{' '.join(command)}\n```\n\n"
            "## Output\n\n"
            f"```text\n{result.stdout}\n```\n",
        )

    if "GITHUB_STEP_SUMMARY" in os.environ and markdown_report.exists():
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(markdown_report.read_text(encoding="utf-8"))

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
