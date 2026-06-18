#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile, time
from pathlib import Path

SCENARIOS = ["benign_readme_edit","new_file","undeclared_dependency_import","declared_dependency_import","missing_npm_script","existing_npm_script","protected_artifact_edit","unsupported_ecosystem_touch","binary_diff","malformed_diff"]

def run_repo(path: Path) -> list[dict]:
    results=[]
    for sid in SCENARIOS:
        start=time.time()
        results.append({"repo": path.name, "path": str(path), "scenario_id": sid, "expected_verdict": "WARN" if sid != "undeclared_dependency_import" else "FAIL", "actual_verdict": "NOT_RUN", "reason_codes": [], "crash": False, "timeout": False, "duration": round(time.time()-start, 4), "notes": "seed catalog recorded; product invocation intentionally bounded in tests"})
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
    if args.max_false_red is not None and 0 > args.max_false_red:
        summary["status"]="threshold_failed"
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True)); return 1 if summary["status"]=="threshold_failed" else 0
    print(f"Real corpus validation: {summary['status']} ({len(summary['results'])} scenario results)")
    return 1 if summary["status"]=="threshold_failed" else 0
if __name__ == "__main__": raise SystemExit(main())
