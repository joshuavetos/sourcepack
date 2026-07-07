#!/usr/bin/env python3
"""Thin GitHub Action wrapper for the existing SourcePack CLI."""
from __future__ import annotations

import argparse
import json
import os
import shlex
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


def _json_data(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _verdict_from_json(path: Path) -> str | None:
    verdict = _json_data(path).get("verdict")
    return verdict if isinstance(verdict, str) else None


def _traffic_light_from_json(path: Path) -> str | None:
    data = _json_data(path)
    for key in ("traffic_light", "trafficLight", "light"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    verdict = data.get("verdict")
    return verdict if isinstance(verdict, str) else None


def _append_step_summary(path: str | None, markdown: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as summary:
        summary.write(markdown)
        if not markdown.endswith("\n"):
            summary.write("\n")


def _artifact_list(report_dir: Path) -> list[str]:
    names = [
        "sourcepack.json",
        "sourcepack.md",
        "sourcepack.sarif.json",
        "sourcepack.stdout.txt",
        "sourcepack.stderr.txt",
        "sourcepack-command.txt",
        "sourcepack-command.json",
    ]
    return [name for name in names if (report_dir / name).exists()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SourcePack for GitHub Actions.")
    parser.add_argument("--mode", choices=["ci", "strict", "local"], default="ci")
    parser.add_argument("--baseline-path", default=".sourcepack/baseline")
    parser.add_argument("--report-dir", default="sourcepack-report")
    parser.add_argument("--json", default="true")
    parser.add_argument("--markdown", default="true")
    parser.add_argument("--sarif", default="true")
    parser.add_argument("--fail-on-warn", default="false")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    baseline = (repo / args.baseline_path).resolve()
    report_dir = (repo / args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    command_log = report_dir / "sourcepack-command.txt"
    command_json = report_dir / "sourcepack-command.json"
    stdout_log = report_dir / "sourcepack.stdout.txt"
    stderr_log = report_dir / "sourcepack.stderr.txt"
    json_report = report_dir / "sourcepack.json"
    markdown_report = report_dir / "sourcepack.md"
    sarif_report = report_dir / "sourcepack.sarif.json"

    if not baseline.exists():
        message = (
            "SourcePack failed closed because trusted baseline state is missing.\n"
            f"Missing baseline path: {args.baseline_path}\n"
            "CI will not create or update trusted baseline state.\n"
            "Create or refresh the baseline locally or in a separate trusted maintainer-controlled setup workflow.\n"
            "This is a trust-boundary behavior, not a package crash.\n"
        )
        _write(command_log, "baseline preflight\n")
        _write(command_json, json.dumps({"command": ["baseline preflight"]}, indent=2) + "\n")
        _write(stdout_log, "")
        _write(stderr_log, message)
        _write(
            markdown_report,
            "# SourcePack Action summary\n\n"
            "- Verdict: FAIL\n"
            "- Traffic light: RED LIGHT\n"
            f"- Mode: {args.mode}\n"
            f"- WARN fails in selected mode: {args.mode in {'ci', 'strict'} or _truthy(args.fail_on_warn)}\n"
            f"- Report directory: {report_dir}\n"
            "- Artifacts: sourcepack.md, sourcepack.stderr.txt, sourcepack.stdout.txt, sourcepack-command.txt, sourcepack-command.json\n"
            "- Missing baseline: SourcePack failed closed because trusted baseline state is missing. "
            "CI will not create or update trusted baseline state. Create or refresh the baseline locally "
            "or in a separate trusted maintainer-controlled setup workflow. This is a trust-boundary behavior, not a package crash.\n",
        )
        _append_step_summary(os.environ.get("GITHUB_STEP_SUMMARY"), markdown_report.read_text(encoding="utf-8"))
        print(message, file=sys.stderr, end="")
        print(f"SourcePack report directory: {report_dir}")
        return 2

    sourcepack_executable = shutil.which("sourcepack")
    if not sourcepack_executable:
        message = "SourcePack executable not found on PATH.\n"
        _write(command_log, "sourcepack lookup failed\n")
        _write(command_json, json.dumps({"command": ["sourcepack lookup failed"]}, indent=2) + "\n")
        _write(stdout_log, "")
        _write(stderr_log, message)
        print(message, file=sys.stderr, end="")
        print(f"SourcePack report directory: {report_dir}")
        return 127

    command = [sourcepack_executable, "diff", str(repo)]
    if _truthy(args.json) or args.mode == "ci":
        command.append("--json")
    if args.mode == "ci":
        command.append("--ci")
    elif args.mode == "strict" or _truthy(args.fail_on_warn):
        command.append("--strict")

    _write(command_log, shlex.join(command) + "\n")
    _write(command_json, json.dumps({"command": command}, indent=2) + "\n")

    result = _run(command, repo)

    _write(stdout_log, result.stdout)
    _write(stderr_log, result.stderr)

    if _truthy(args.json):
        _write(json_report, result.stdout)

    latest_json = repo / ".sourcepack" / "reports" / "latest.json"
    if latest_json.exists():
        shutil.copyfile(latest_json, json_report)

    latest_sarif = repo / ".sourcepack" / "reports" / "latest.sarif.json"
    sarif_status = "disabled"
    if _truthy(args.sarif):
        if latest_sarif.exists():
            shutil.copyfile(latest_sarif, sarif_report)
            sarif_status = f"copied to {sarif_report}"
        else:
            sarif_status = "enabled, but no SourcePack SARIF report was present; continuing without SARIF artifact"

    if _truthy(args.markdown):
        verdict = _verdict_from_json(json_report) or "UNKNOWN"
        traffic_light = _traffic_light_from_json(json_report) or verdict
        artifacts = _artifact_list(report_dir)
        if "sourcepack.md" not in artifacts:
            artifacts.insert(1 if "sourcepack.json" in artifacts else 0, "sourcepack.md")
        _write(
            markdown_report,
            "# SourcePack Action summary\n\n"
            f"- Verdict: {verdict}\n"
            f"- Traffic light: {traffic_light}\n"
            f"- Mode: {args.mode}\n"
            f"- WARN fails in selected mode: {args.mode in {'ci', 'strict'} or _truthy(args.fail_on_warn)}\n"
            f"- Report directory: {report_dir}\n"
            f"- Artifacts: {', '.join(artifacts) if artifacts else 'none'}\n"
            f"- SARIF passthrough: {sarif_status}\n"
            f"- Command artifact: {command_log} contains the exact command arguments used.\n\n"
            "## Command\n\n"
            f"```text\n{shlex.join(command)}\n```\n\n"
            "## Output\n\n"
            f"```text\n{result.stdout}\n```\n",
        )

    print(f"SourcePack report directory: {report_dir}")
    print(f"SourcePack artifacts: {', '.join(_artifact_list(report_dir))}")
    print(f"SourcePack SARIF passthrough: {sarif_status}")

    if markdown_report.exists():
        _append_step_summary(os.environ.get("GITHUB_STEP_SUMMARY"), markdown_report.read_text(encoding="utf-8"))

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
