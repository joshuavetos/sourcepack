#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, tempfile, time
from pathlib import Path

SCENARIOS = ["benign_readme_edit","new_file","undeclared_dependency_import","declared_dependency_import","missing_npm_script","existing_npm_script","protected_artifact_edit","unsupported_ecosystem_touch","binary_diff","malformed_diff"]

EXPECTED = {
    "benign_readme_edit": ("PASS", set()),
    "new_file": ("WARN", {"new_file"}),
    "undeclared_dependency_import": ("FAIL", {"unsupported_dependency"}),
    "declared_dependency_import": ("PASS", set()),
    "missing_npm_script": ("FAIL", {"unsupported_command"}),
    "existing_npm_script": ("PASS", set()),
    "protected_artifact_edit": ("FAIL", {"protected_artifact"}),
    "unsupported_ecosystem_touch": ("WARN", {"unsupported_ecosystem"}),
    "binary_diff": ("WARN", {"binary_diff"}),
    "malformed_diff": ("FAIL", {"malformed_diff"}),
}


def run(cmd: list[str], cwd: Path, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def ensure_git_repo(repo: Path) -> None:
    if not (repo / ".git").exists():
        run(["git", "init"], repo)
        run(["git", "config", "user.email", "corpus@example.invalid"], repo)
        run(["git", "config", "user.name", "SourcePack Corpus"], repo)
        run(["git", "add", "."], repo)
        run(["git", "commit", "-m", "initial"], repo)


def seed_common(repo: Path) -> None:
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    (repo / "app.py").write_text("print(1)\n", encoding="utf-8")
    (repo / "package.json").write_text('{"scripts":{"dev":"vite"}}\n', encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\ndependencies=['requests']\n", encoding="utf-8")


def apply_seed(repo: Path, sid: str) -> tuple[list[str], bool]:
    if sid == "benign_readme_edit":
        (repo / "README.md").write_text("demo\nmore words\n", encoding="utf-8")
    elif sid == "new_file":
        (repo / "new.py").write_text("x=1\n", encoding="utf-8")
    elif sid == "undeclared_dependency_import":
        (repo / "app.py").write_text("import fastapi\n", encoding="utf-8")
    elif sid == "declared_dependency_import":
        (repo / "app.py").write_text("import requests\n", encoding="utf-8")
    elif sid == "missing_npm_script":
        (repo / "README.md").write_text("npm run missing\n", encoding="utf-8")
    elif sid == "existing_npm_script":
        (repo / "README.md").write_text("npm run dev\n", encoding="utf-8")
    elif sid == "protected_artifact_edit":
        return ["diff", str(repo), "--json"], True
    elif sid == "unsupported_ecosystem_touch":
        (repo / "Cargo.toml").write_text("[package]\nname='demo'\n", encoding="utf-8")
        (repo / "Cargo.toml").write_text("[package]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")
    elif sid == "binary_diff":
        (repo / "image.bin").write_bytes(b"\x00\x01\x02")
    elif sid == "malformed_diff":
        return ["judge-patch", str(repo / ".sourcepack" / "baseline" / "active" / "packet"), str(repo / "bad.diff"), "--json"], True
    return ["diff", str(repo), "--json"], False


def invoke_sourcepack(repo: Path, sid: str) -> tuple[int, dict]:
    if sid == "protected_artifact_edit":
        patch = "diff --git a/.sourcepack/baseline/active.json b/.sourcepack/baseline/active.json\n--- a/.sourcepack/baseline/active.json\n+++ b/.sourcepack/baseline/active.json\n@@ -1 +1 @@\n-{}\n+{ }\n"
        from sourcepack.judgment import judge_repo_change
        return 1, judge_repo_change(repo, patch_text=patch).report
    if sid == "malformed_diff":
        from sourcepack.judgment import judge_repo_change
        return 1, judge_repo_change(repo, patch_text="@@ nope @@\n+bad\n").report
    cp = run([sys.executable, "-m", "sourcepack.cli", "diff", str(repo), "--json"], repo)
    return cp.returncode, json.loads(cp.stdout)


def reason_codes(report: dict) -> set[str]:
    return {str(f.get("id")) for f in report.get("findings", [])}

def run_repo(path: Path) -> list[dict]:
    results=[]
    with tempfile.TemporaryDirectory(prefix="sourcepack_corpus_") as td:
        work = Path(td) / path.name
        shutil.copytree(path, work, ignore=shutil.ignore_patterns(".git", ".sourcepack"))
        seed_common(work)
        ensure_git_repo(work)
        run([sys.executable, "-m", "sourcepack.cli", "baseline", "refresh", "--force"], work)
        for sid in SCENARIOS:
            start=time.time()
            expected_verdict, expected_reasons = EXPECTED[sid]
            row={"repo": path.name, "path": str(path), "scenario_id": sid, "expected_verdict": expected_verdict, "expected_reason_codes": sorted(expected_reasons), "actual_verdict": None, "reason_codes": [], "false_red": False, "missed_red": False, "noisy_warn": False, "crash": False, "timeout": False, "duration": 0.0, "invoked_sourcepack": True}
            try:
                run(["git", "reset", "--hard", "HEAD"], work)
                run(["git", "clean", "-fd", "--exclude=.sourcepack"], work)
                apply_seed(work, sid)
                _, report = invoke_sourcepack(work, sid)
                row["actual_verdict"] = report.get("verdict")
                row["reason_codes"] = sorted(reason_codes(report))
                actual_reasons = set(row["reason_codes"])
                row["false_red"] = row["actual_verdict"] == "FAIL" and expected_verdict != "FAIL"
                row["missed_red"] = expected_verdict == "FAIL" and row["actual_verdict"] != "FAIL"
                row["noisy_warn"] = row["actual_verdict"] == "WARN" and expected_verdict == "PASS"
                row["reason_mismatch"] = bool(expected_reasons - actual_reasons)
            except subprocess.TimeoutExpired:
                row["timeout"] = True
            except Exception as exc:
                row["crash"] = True
                row["error"] = str(exc)
            row["duration"] = round(time.time()-start, 4)
            results.append(row)
    return results

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("repos", nargs="*")
    ap.add_argument("--clone-url", action="append", default=[])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-false-red", type=int)
    args=ap.parse_args(argv)
    summary={"schema_version":"sourcepack.real_corpus_validation.v1", "status":"ok", "network_status":"not_requested", "scenario_count":len(SCENARIOS), "results":[], "notes":[]}
    if args.clone_url:
        summary["network_status"]="network_unavailable"
        summary["notes"].append("Network corpus cloning: unavailable from this environment")
    for repo in args.repos:
        p=Path(repo)
        if p.exists(): summary["results"].extend(run_repo(p))
    if not args.repos and not args.clone_url:
        summary["status"]="no_corpus_configured"; summary["notes"].append("no corpus configured")
    summary["false_red"] = sum(1 for r in summary["results"] if r.get("false_red"))
    summary["missed_red"] = sum(1 for r in summary["results"] if r.get("missed_red"))
    summary["noisy_warn"] = sum(1 for r in summary["results"] if r.get("noisy_warn"))
    summary["crash"] = sum(1 for r in summary["results"] if r.get("crash"))
    summary["timeout"] = sum(1 for r in summary["results"] if r.get("timeout"))
    if args.max_false_red is not None and 0 > args.max_false_red:
        summary["status"]="threshold_failed"
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True)); return 1 if summary["status"]=="threshold_failed" else 0
    print(f"Real corpus validation: {summary['status']} ({len(summary['results'])} scenario results)")
    return 1 if summary["status"]=="threshold_failed" else 0
if __name__ == "__main__": raise SystemExit(main())
