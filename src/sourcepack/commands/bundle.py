from __future__ import annotations

import json
from pathlib import Path

from sourcepack.evidence_bundle import create_bundle, render_bundle_verify_human, verify_bundle


def register(subparsers) -> None:
    bundle_cmd = subparsers.add_parser("bundle", help="create and verify local evidence bundles")
    bundle_subs = bundle_cmd.add_subparsers(dest="bundle_command")
    bundle_create = bundle_subs.add_parser("create")
    bundle_create.add_argument("report_path")
    bundle_create.add_argument("--ledger", required=True)
    bundle_create.add_argument("--out")
    bundle_create.add_argument("--json", action="store_true")
    bundle_verify = bundle_subs.add_parser("verify")
    bundle_verify.add_argument("bundle_path")
    bundle_verify.add_argument("--json", action="store_true")


def cli_bundle(args) -> int:
    if args.bundle_command == "create":
        manifest = create_bundle(args.report_path, args.ledger, output_path=args.out)
        if args.json:
            print(json.dumps(manifest, indent=2, sort_keys=True))
        else:
            print(f"Bundle written: {args.out or str(Path(args.report_path).with_suffix('.bundle.json'))}")
            print(f"Bundle ID: {manifest.get('bundle_id')}")
            print(f"Artifacts: {len(manifest.get('artifacts', []))}")
            events = manifest.get("events", {})
            print(
                "Events: "
                f"report_created={1 if events.get('report_created') else 0} "
                f"parent_chain={len(events.get('parent_chain', []))} "
                f"fail_detected={len(events.get('fail_detected', []))} "
                f"overrides={len(events.get('overrides', []))}"
            )
        return 0 if manifest.get("creation_verification", {}).get("status") == "PASS" else 1
    if args.bundle_command == "verify":
        result = verify_bundle(args.bundle_path)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(render_bundle_verify_human({"bundle_id": args.bundle_path, "verification": result}), end="")
        return 0 if result.get("status") == "PASS" else 1
    return 1
