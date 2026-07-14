import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "action.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "sourcepack.yml"
EXAMPLE_WORKFLOW = ROOT / "docs" / "examples" / "sourcepack-action.yml"
WRAPPER = ROOT / "scripts" / "sourcepack_action.py"


def norm_path_for_compare(value: str) -> str:
    return os.path.normcase(os.path.normpath(value))


def read_command_json(report_dir: Path) -> list[str]:
    data = json.loads((report_dir / "sourcepack-command.json").read_text(encoding="utf-8"))
    command = data["command"]
    assert isinstance(command, list)
    assert all(isinstance(item, str) for item in command)
    return command


def load_action():
    text = ACTION.read_text(encoding="utf-8")
    data = {"inputs": {}, "runs": {"using": None, "steps": []}}
    section = None
    current_input = None
    in_steps = False
    current_step = None

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()

        if indent == 0 and line.endswith(":"):
            section = line[:-1]
            in_steps = False
            continue

        if section == "inputs" and indent == 2 and line.endswith(":"):
            current_input = line[:-1]
            data["inputs"][current_input] = {}
            continue

        if section == "inputs" and current_input and indent == 4 and ":" in line:
            key, value = line.split(":", 1)
            data["inputs"][current_input][key] = value.strip().strip("'")
            continue

        if section == "runs" and indent == 2 and line.startswith("using:"):
            data["runs"]["using"] = line.split(":", 1)[1].strip()
            continue

        if section == "runs" and indent == 2 and line == "steps:":
            in_steps = True
            continue

        if section == "runs" and in_steps and indent == 4 and line.startswith("- "):
            current_step = {}
            data["runs"]["steps"].append(current_step)
            content = line[2:]
            if ":" in content:
                key, value = content.split(":", 1)
                current_step[key] = value.strip()
            continue

        if section == "runs" and in_steps and current_step is not None and indent == 6 and ":" in line:
            key, value = line.split(":", 1)
            current_step[key] = value.strip()

    return data


def action_text() -> str:
    return ACTION.read_text(encoding="utf-8")


def run_bodies(text: str) -> list[str]:
    bodies: list[str] = []
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()

        if stripped.startswith("run:"):
            indent = len(raw) - len(raw.lstrip(" "))

            if stripped == "run: |":
                index += 1
                body: list[str] = []
                while index < len(lines):
                    body_raw = lines[index]
                    body_indent = len(body_raw) - len(body_raw.lstrip(" "))
                    if body_raw.strip() and body_indent <= indent:
                        break
                    body.append(body_raw)
                    index += 1
                bodies.append("\n".join(body))
                continue

            bodies.append(stripped.split(":", 1)[1].strip())

        index += 1

    return bodies


def load_wrapper():
    spec = importlib.util.spec_from_file_location("sourcepack_action", WRAPPER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_fake_sourcepack(
    bin_dir: Path,
    stdout: str,
    stderr: str = "",
    exit_code: int = 0,
    calls_file: Path | None = None,
) -> Path:
    if os.name == "nt":
        script = bin_dir / "sourcepack.py"
        lines = ["import sys"]

        if calls_file is not None:
            lines.extend(
                [
                    "from pathlib import Path",
                    f"Path({str(calls_file)!r}).write_text(' '.join(sys.argv), encoding='utf-8')",
                ]
            )

        if stdout:
            lines.append(f"sys.stdout.write({stdout!r})")
        if stderr:
            lines.append(f"sys.stderr.write({stderr!r})")

        lines.append(f"raise SystemExit({exit_code})")
        script.write_text("\n".join(lines) + "\n", encoding="utf-8")

        command = bin_dir / "sourcepack.cmd"
        command.write_text(
            f'@echo off\r\n"{sys.executable}" "%~dp0sourcepack.py" %*\r\n',
            encoding="utf-8",
        )
        return command

    command = bin_dir / "sourcepack"
    body = "#!/bin/sh\n"

    if calls_file is not None:
        body += f"printf '%s\\n' \"$0 $*\" > {calls_file}\n"
    if stdout:
        body += f"printf '%s' {shlex.quote(stdout)}\n"
    if stderr:
        body += f"printf '%s' {shlex.quote(stderr)} >&2\n"

    body += f"exit {exit_code}\n"
    command.write_text(body, encoding="utf-8")
    command.chmod(0o755)
    return command


def path_with(bin_dir: Path) -> str:
    current = os.environ.get("PATH", "")
    return f"{bin_dir}{os.pathsep}{current}" if current else str(bin_dir)


def test_action_yml_exists_and_parses_as_yaml():
    data = load_action()
    assert data["runs"]["using"] == "composite"


def test_required_inputs_exist():
    inputs = load_action()["inputs"]
    required = {
        "mode",
        "sourcepack-version",
        "python-version",
        "baseline-path",
        "report-dir",
        "json",
        "markdown",
        "sarif",
        "fail-on-warn",
        "run-doctor",
        "upload-artifact",
        "comment-pr",
    }
    assert required <= set(inputs)
    assert inputs["mode"]["default"] == "ci"
    assert inputs["baseline-path"]["default"] == ".sourcepack/baseline"
    assert inputs["comment-pr"]["default"] == "false"


def test_comment_pr_input_is_real_not_reserved_future_copy():
    comment_pr = load_action()["inputs"]["comment-pr"]
    description = comment_pr["description"].lower()
    assert "post" in description or "comment" in description
    assert "reserved" not in description
    assert "future" not in description
    assert "not implemented" not in description


def test_action_passes_comment_pr_input_to_wrapper():
    text = action_text()
    assert "COMMENT_PR: ${{ inputs.comment-pr }}" in text
    assert '--comment-pr "$COMMENT_PR"' in text
    assert "GITHUB_TOKEN: ${{ github.token }}" in text


def test_action_does_not_interpolate_inputs_inside_shell_run_bodies():
    offenders = [body for body in run_bodies(action_text()) if "${{ inputs." in body]
    assert offenders == []


def test_action_does_not_create_or_update_baseline_trust():
    text = action_text()
    forbidden = ["sourcepack init", "sourcepack baseline", "baseline --force"]
    assert [token for token in forbidden if token in text] == []


def test_action_references_version_and_conditional_doctor():
    data = load_action()
    text = action_text()
    assert "sourcepack --version" in text
    doctor_steps = [step for step in data["runs"]["steps"] if "sourcepack doctor" in str(step)]
    assert doctor_steps
    assert all("run-doctor" in step.get("if", "") for step in doctor_steps)


def test_action_verifies_baseline_before_diff_execution():
    text = action_text()
    baseline_index = text.index("SourcePack failed closed because trusted baseline state is missing")
    diff_index = text.index("sourcepack_action.py")
    assert baseline_index < diff_index
    assert "CI will not create or update trusted baseline state." in text


def test_action_writes_or_preserves_report_output():
    text = action_text()
    assert "sourcepack-report" in text
    assert "sourcepack.stderr.txt" in text
    assert "sourcepack.stdout.txt" in text
    assert "sourcepack-command.txt" in text
    assert "sourcepack-command.json" in text
    assert "upload-artifact" in text


def test_action_missing_baseline_preflight_writes_structured_command_artifact():
    text = action_text()
    assert 'cat > "$REPORT_DIR/sourcepack-command.json"' in text
    assert '"command": ["baseline preflight"]' in text
    assert "sourcepack-command.txt, sourcepack-command.json" in text


def test_action_inputs_are_documented_in_ci_docs():
    inputs = set(load_action()["inputs"])
    ci_text = (ROOT / "docs" / "ci.md").read_text(encoding="utf-8")
    missing = [name for name in sorted(inputs) if f"`{name}`" not in ci_text]
    assert missing == []


def test_ci_workflow_keeps_existing_validation_gates():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    required = [
        "push:",
        "pull_request:",
        "matrix:",
        "ubuntu-latest",
        "windows-latest",
        "python -m py_compile src/sourcepack/cli.py",
        "python -m unittest",
        "pytest -q tests/test_behavior_matrix.py",
        "pytest -q tests/test_golden_demo.py",
        "pytest -q tests/test_readme_truth.py",
        "pytest -q",
        "python tools/behavior_matrix.py",
        "python tools/behavior_matrix.py --json",
        "python tools/golden_demo.py --clean",
        "sourcepack doctor",
        "sourcepack demo",
        "python tools/release_smoke.py",
    ]
    assert [token for token in required if token not in text] == []


def test_sourcepack_workflow_limits_push_to_main_and_keeps_pr_trigger():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "on:\n  push:\n    branches: [main]\n  pull_request:\n    types: [opened, synchronize, reopened, labeled, unlabeled]" in text
    assert "pull_request:" in text
    assert "branches: [main]" in text


def test_sourcepack_workflow_pr_trigger_reruns_for_trust_label_changes():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "types: [opened, synchronize, reopened, labeled, unlabeled]" in text
    for event_type in ["opened", "synchronize", "reopened", "labeled", "unlabeled"]:
        assert event_type in text


def test_sourcepack_workflow_avoids_duplicate_unlabelled_pr_branch_push_checks():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "push:\n  pull_request:" not in text
    assert "github.event.pull_request.labels.*.name" in text
    assert "BASELINE_TRUST_LABEL_PRESENT" in text
    assert "WORKFLOW_TRUST_LABEL_PRESENT" in text
    assert "github.event.pull_request.base.sha || github.event.before" in text


def test_sourcepack_workflow_dogfoods_committed_baseline_without_creating_trust_state():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "python -B -m sourcepack.cli diff . --ci --json" in text
    assert "continue-on-error: true" not in text
    assert "shell: bash" in text
    assert "PYTHONPATH: src" in text
    assert 'PYTHONDONTWRITEBYTECODE: "1"' in text
    assert "baseline-trust-update" in text
    assert "workflow-trust-update" in text
    assert "SourcePack detected protected baseline artifact changes. This PR requires intentional trust-state review." in text
    assert "SourcePack detected workflow automation changes. This PR requires intentional workflow trust review." in text
    assert "sourcepack baseline" not in text
    assert "sourcepack init" not in text
    assert "--refresh" not in text
    assert "baseline --force" not in text


def test_sourcepack_workflow_baseline_trust_exception_is_label_gated_and_narrow():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "BASELINE_TRUST_LABEL_PRESENT" in text
    assert "contains(github.event.pull_request.labels.*.name, 'baseline-trust-update')" in text
    assert 'finding_id == "protected_artifact" and path.startswith(".sourcepack/baseline/")' in text
    assert "Protected baseline artifact changes require 'baseline-trust-update'." in text
    assert "baseline_label_present" in text
    assert "without creating, refreshing, repairing, or blessing baseline state" in text


def test_sourcepack_workflow_workflow_trust_exception_is_label_gated_and_narrow():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "WORKFLOW_TRUST_LABEL_PRESENT" in text
    assert "contains(github.event.pull_request.labels.*.name, 'workflow-trust-update')" in text
    assert 'finding_id == "workflow_change" and path.startswith(".github/workflows/")' in text
    assert "Workflow automation changes require 'workflow-trust-update'." in text
    assert "workflow_label_present" in text
    assert "workflow_change findings after reviewing the workflow diff" in text


def test_sourcepack_workflow_gate_treats_warn_and_error_as_ci_blocking():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "ci_blocking_findings" in text
    assert 'finding.get("severity") in {"error", "warn"}' in text
    assert 'report.get("findings", [])' in text


def test_sourcepack_workflow_trust_labels_do_not_cross_authorize_findings():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    baseline_missing = text.index('if protected_baseline_findings and not baseline_label_present:')
    workflow_missing = text.index('if workflow_change_findings and not workflow_label_present:')
    missing_append = text.index('missing_labels.append("baseline-trust-update")', baseline_missing)
    workflow_append = text.index('missing_labels.append("workflow-trust-update")', workflow_missing)
    assert baseline_missing < missing_append
    assert workflow_missing < workflow_append
    assert "if protected_baseline_findings and not workflow_label_present" not in text
    assert "if workflow_change_findings and not baseline_label_present" not in text


def test_sourcepack_workflow_requires_both_labels_for_mixed_trust_findings():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    baseline_check = text.index('if protected_baseline_findings and not baseline_label_present:')
    workflow_check = text.index('if workflow_change_findings and not workflow_label_present:')
    missing_labels_check = text.index('if missing_labels:', workflow_check)
    assert baseline_check < workflow_check < missing_labels_check
    assert "Missing maintainer label(s):" in text
    assert "Protected baseline artifacts requiring review:" in text
    assert "Workflow automation findings requiring review:" in text


def test_sourcepack_workflow_unexpected_warn_or_error_fails_normally():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "unexpected_findings" in text
    assert "SourcePack gate failed for findings beyond labelled trust-review classes; failing normally." in text
    assert "sys.exit(sourcepack_status)" in text


def test_sourcepack_workflow_self_dogfooding_gate_is_bash_backed():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    gate_index = text.index("SourcePack self-dogfooding gate")
    shell_index = text.index("shell: bash", gate_index)
    run_index = text.index("run: |", gate_index)
    assert shell_index < run_index


def test_sourcepack_workflow_runs_gate_before_editable_install_and_validation_gates():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    install_index = text.index("Install package and test dependencies")
    gate_index = text.index("python -B -m sourcepack.cli diff . --ci --json --exit-policy fail-only --base-ref")
    tests_index = text.index("Full pytest suite")
    assert gate_index < install_index < tests_index


def test_sourcepack_workflow_self_dogfood_judges_base_head_range():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    command = 'python -B -m sourcepack.cli diff . --ci --json --exit-policy fail-only --base-ref "$BASE_SHA" --head-ref "$HEAD_SHA" > "$report_path"'
    assert command in text
    assert 'python -B -m sourcepack.cli diff . --ci --json > "$report_path"' not in text
    assert 'BASE_SHA: ${{ github.event.pull_request.base.sha || github.event.before }}' in text
    assert 'HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}' in text
    assert 'def changed_files() -> list[str]:' in text
    assert '"diff", "--name-only", f"{base_sha}...{head_sha}"' in text
    for forbidden in ("sourcepack baseline", "sourcepack init", "baseline --force", "continue-on-error: true"):
        assert forbidden not in text


def test_sourcepack_workflow_self_dogfood_json_uses_runner_temp():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert 'report_path="$RUNNER_TEMP/sourcepack-self-dogfood.json"' in text
    assert '> "$report_path"' in text
    assert 'cat "$report_path"' in text
    assert '> sourcepack-self-dogfood.json' not in text


def test_sourcepack_workflow_inline_guard_reads_report_path_from_argv():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert 'python - "$sourcepack_status" "$report_path" <<\'PY\'' in text
    assert 'report_path = sys.argv[2]' in text
    assert 'with open(report_path, encoding="utf-8") as fh:' in text
    assert 'with open("sourcepack-self-dogfood.json"' not in text


def test_sourcepack_workflow_does_not_add_exceptions_for_new_file_or_baseline_corrupt():
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert 'finding_id == "new_file"' not in text
    assert 'finding_id == "baseline_corrupt"' not in text


def test_example_workflow_exists_and_does_not_create_baseline_during_pr():
    text = EXAMPLE_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "# pull_request:" in text
    assert "uses: ./" in text
    assert "sourcepack baseline" not in text
    assert "sourcepack init" not in text
    assert "baseline --force" not in text


def test_wrapper_resolves_sourcepack_executable_before_subprocess_run():
    text = WRAPPER.read_text(encoding="utf-8")
    assert 'shutil.which("sourcepack")' in text
    assert 'command = [sourcepack_executable, "diff", str(repo)]' in text
    assert 'command = ["sourcepack", "diff", str(repo)]' not in text


def test_wrapper_accepts_comment_pr_argument_and_has_comment_marker():
    text = WRAPPER.read_text(encoding="utf-8")
    assert 'parser.add_argument("--comment-pr"' in text
    assert "COMMENT_MARKER" in text
    assert "sourcepack-action-comment:v1" in text
    assert "_render_pr_comment" in text
    assert "_maybe_comment_pr" in text
    assert "sourcepack-pr-comment.md" in text
    assert "sourcepack-pr-comment.txt" in text


def test_wrapper_does_not_import_or_duplicate_core_judgment_logic():
    tree = WRAPPER.read_text(encoding="utf-8")
    forbidden = [
        "sourcepack.judgment",
        "sourcepack.dependencies",
        "sourcepack.baseline import",
        "def judge_",
        "def parse_unified_diff",
    ]
    assert [token for token in forbidden if token in tree] == []


def test_wrapper_py_compiles():
    subprocess.run([sys.executable, "-m", "py_compile", str(WRAPPER)], check=True)


def test_wrapper_missing_baseline_returns_nonzero_and_message(tmp_path, capsys):
    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--baseline-path", ".sourcepack/baseline", "--report-dir", "reports"])
    captured = capsys.readouterr()
    assert code != 0
    assert "SourcePack failed closed because trusted baseline state is missing" in captured.err
    assert "CI will not create or update trusted baseline state." in captured.err
    assert (tmp_path / "reports" / "sourcepack.stderr.txt").exists()


def test_wrapper_missing_baseline_markdown_is_valid(tmp_path, capsys):
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "reports"]) != 0
    _ = capsys.readouterr()
    text = (tmp_path / "reports" / "sourcepack.md").read_text(encoding="utf-8")
    assert text.count("```") % 2 == 0
    assert "SourcePack failed closed because trusted baseline state is missing" in text


def test_wrapper_missing_baseline_explains_fail_closed_trust_boundary(tmp_path, capsys):
    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--baseline-path", ".sourcepack/baseline", "--report-dir", "reports"])
    captured = capsys.readouterr()
    assert code != 0
    text = captured.err + (tmp_path / "reports" / "sourcepack.stderr.txt").read_text(encoding="utf-8")
    assert "SourcePack failed closed because trusted baseline state is missing" in text
    assert "CI will not create or update trusted baseline state" in text
    assert "Create or refresh the baseline locally or in a separate trusted maintainer-controlled setup workflow" in text
    assert "This is a trust-boundary behavior, not a package crash" in text


def test_wrapper_creates_report_dir_and_captures_command_output(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = write_fake_sourcepack(bin_dir, stdout='{"verdict":"PASS"}\n', stderr='err\n')
    monkeypatch.setenv("PATH", path_with(bin_dir))

    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--baseline-path", ".sourcepack/baseline", "--report-dir", "reports"])

    assert code == 0
    report_dir = tmp_path / "reports"
    command = read_command_json(report_dir)
    assert norm_path_for_compare(command[0]) == norm_path_for_compare(str(fake))
    assert command[1:3] == ["diff", str(tmp_path.resolve())]
    assert "PASS" in (report_dir / "sourcepack.stdout.txt").read_text(encoding="utf-8")
    assert "err" in (report_dir / "sourcepack.stderr.txt").read_text(encoding="utf-8")
    assert (report_dir / "sourcepack.json").exists()
    assert (report_dir / "sourcepack.md").exists()


def test_wrapper_uses_which_resolved_fake_sourcepack_command(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls_file = tmp_path / "calls.txt"
    fake = write_fake_sourcepack(bin_dir, stdout='{"verdict":"PASS"}\n', calls_file=calls_file)
    monkeypatch.setenv("PATH", path_with(bin_dir))

    module = load_wrapper()
    resolved = module.shutil.which("sourcepack")
    assert resolved is not None
    assert norm_path_for_compare(resolved) == norm_path_for_compare(str(fake))

    code = module.main(
        [
            "--repo",
            str(tmp_path),
            "--baseline-path",
            ".sourcepack/baseline",
            "--report-dir",
            "reports",
        ]
    )

    assert code == 0
    assert calls_file.exists()
    command = read_command_json(tmp_path / "reports")
    assert norm_path_for_compare(command[0]) == norm_path_for_compare(str(fake))


def test_wrapper_fail_on_warn_is_explicit_in_command(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_sourcepack(bin_dir, stdout='{"verdict":"WARN"}\n')
    monkeypatch.setenv("PATH", path_with(bin_dir))

    module = load_wrapper()
    code = module.main(
        [
            "--repo",
            str(tmp_path),
            "--baseline-path",
            ".sourcepack/baseline",
            "--report-dir",
            "reports",
            "--mode",
            "local",
            "--fail-on-warn",
            "true",
        ]
    )

    assert code == 0
    command = read_command_json(tmp_path / "reports")
    assert "--strict" in command


def test_wrapper_preserves_exact_command_and_delegates_to_cli(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"
    fake = write_fake_sourcepack(bin_dir, stdout='{"verdict":"PASS"}\n', calls_file=calls)
    monkeypatch.setenv("PATH", path_with(bin_dir))

    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out", "--mode", "strict"]) == 0

    command = read_command_json(tmp_path / "out")
    assert norm_path_for_compare(command[0]) == norm_path_for_compare(str(fake))
    assert command[1:] == ["diff", str(tmp_path.resolve()), "--json", "--strict"]
    assert f"diff {tmp_path} --json --strict" in calls.read_text(encoding="utf-8")


def test_wrapper_sarif_true_copies_existing_latest_sarif(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    reports = tmp_path / ".sourcepack" / "reports"
    reports.mkdir(parents=True)
    (reports / "latest.sarif.json").write_text('{"version":"2.1.0"}', encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_sourcepack(bin_dir, stdout='{"verdict":"PASS"}\n')
    monkeypatch.setenv("PATH", path_with(bin_dir))

    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "true"])

    assert code == 0
    assert (tmp_path / "out" / "sourcepack.sarif.json").read_text(encoding="utf-8") == '{"version":"2.1.0"}'


def test_wrapper_sarif_false_and_missing_sarif_do_not_fail_or_copy(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    reports = tmp_path / ".sourcepack" / "reports"
    reports.mkdir(parents=True)
    (reports / "latest.sarif.json").write_text('{"version":"2.1.0"}', encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_sourcepack(bin_dir, stdout='{"verdict":"PASS"}\n')
    monkeypatch.setenv("PATH", path_with(bin_dir))

    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "false"]) == 0
    assert not (tmp_path / "out" / "sourcepack.sarif.json").exists()

    (reports / "latest.sarif.json").unlink()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out2", "--sarif", "true"]) == 0
    assert not (tmp_path / "out2" / "sourcepack.sarif.json").exists()


def test_wrapper_reports_paths_sarif_missing_and_step_summary(tmp_path, monkeypatch, capsys):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_sourcepack(bin_dir, stdout='{"verdict":"PASS","traffic_light":"GREEN"}\n')
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("PATH", path_with(bin_dir))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "reports", "--sarif", "true"]) == 0
    captured = capsys.readouterr()

    assert str(tmp_path / "reports") in captured.out
    assert "enabled, but no SourcePack SARIF report was present" in captured.out
    assert not (tmp_path / "reports" / "sourcepack.sarif.json").exists()

    summary_text = summary.read_text(encoding="utf-8")
    assert "Verdict: PASS" in summary_text
    assert "Traffic light: GREEN" in summary_text
    assert "Mode: ci" in summary_text
    assert "WARN fails in selected mode: True" in summary_text
    assert f"Report directory: {tmp_path / 'reports'}" in summary_text
    assert "SARIF passthrough: enabled, but no SourcePack SARIF report was present" in summary_text
    assert summary_text.count("```") % 2 == 0

    forbidden_claims = [
        "proves correctness",
        "proves security",
        "proves runtime success",
        "proves external API truth",
        "proves user intent",
    ]
    assert [claim for claim in forbidden_claims if claim in summary_text] == []


def test_wrapper_sarif_disabled_summary_does_not_claim_sarif(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    reports = tmp_path / ".sourcepack" / "reports"
    reports.mkdir(parents=True)
    (reports / "latest.sarif.json").write_text('{"version":"2.1.0"}', encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_sourcepack(bin_dir, stdout='{"verdict":"PASS"}\n')
    monkeypatch.setenv("PATH", path_with(bin_dir))

    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "false"]) == 0

    summary = (tmp_path / "out" / "sourcepack.md").read_text(encoding="utf-8")
    assert "SARIF passthrough: disabled" in summary
    assert not (tmp_path / "out" / "sourcepack.sarif.json").exists()


def test_wrapper_does_not_create_baseline_or_use_prompt_as_authority(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    prompt = tmp_path / ".sourcepack" / "prompt"
    prompt.mkdir(parents=True)
    (prompt / "context.md").write_text("fake authority", encoding="utf-8")
    before_baseline = sorted(p.relative_to(baseline) for p in baseline.rglob("*"))
    before_prompt = sorted(p.relative_to(prompt) for p in prompt.rglob("*"))

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_sourcepack(bin_dir, stdout='{"verdict":"PASS"}\n')
    monkeypatch.setenv("PATH", path_with(bin_dir))

    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out"]) == 0
    assert sorted(p.relative_to(baseline) for p in baseline.rglob("*")) == before_baseline
    assert sorted(p.relative_to(prompt) for p in prompt.rglob("*")) == before_prompt

    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    assert ".sourcepack/prompt" not in wrapper_text
    assert "prompt" not in wrapper_text.lower()


def test_composite_action_like_run_writes_artifacts_command_summary_and_sarif(tmp_path, monkeypatch, capsys):
    module = load_wrapper()
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    source_reports = tmp_path / ".sourcepack" / "reports"
    source_reports.mkdir(parents=True)
    (source_reports / "latest.sarif.json").write_text('{"version":"2.1.0","runs":[]}', encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    executed: list[list[str]] = []

    def fake_run(command, cwd):
        executed.append(command)
        (source_reports / "latest.json").write_text(
            '{"verdict":"PASS","traffic_light":"green","findings":[]}',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout='{"verdict":"PASS","traffic_light":"green"}\n', stderr="")

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module.shutil, "which", lambda name: "sourcepack" if name == "sourcepack" else None)

    code = module.main(
        [
            "--repo",
            str(tmp_path),
            "--baseline-path",
            ".sourcepack/baseline",
            "--report-dir",
            "action-report",
            "--mode",
            "ci",
            "--json",
            "true",
            "--markdown",
            "true",
            "--sarif",
            "true",
            "--fail-on-warn",
            "false",
        ]
    )
    captured = capsys.readouterr()
    report_dir = tmp_path / "action-report"
    expected_command = ["sourcepack", "diff", str(tmp_path.resolve()), "--json", "--ci"]

    assert code == 0
    assert executed == [expected_command]
    assert report_dir.is_dir()

    for artifact in [
        "sourcepack.json",
        "sourcepack.md",
        "sourcepack.stdout.txt",
        "sourcepack.stderr.txt",
        "sourcepack-command.txt",
        "sourcepack-command.json",
        "sourcepack.sarif.json",
    ]:
        assert (report_dir / artifact).exists(), artifact

    assert read_command_json(report_dir) == expected_command
    assert (report_dir / "sourcepack-command.txt").read_text(encoding="utf-8") == shlex.join(expected_command) + "\n"
    assert (report_dir / "sourcepack.sarif.json").read_text(encoding="utf-8") == '{"version":"2.1.0","runs":[]}'

    markdown = (report_dir / "sourcepack.md").read_text(encoding="utf-8")
    summary_text = summary.read_text(encoding="utf-8")

    for text in (markdown, summary_text):
        assert "- Verdict: PASS" in text
        assert "- Traffic light: green" in text
        assert "- Mode: ci" in text
        assert "- WARN fails in selected mode: True" in text
        assert f"- Report directory: {report_dir}" in text
        assert "sourcepack.json" in text
        assert "sourcepack.md" in text
        assert "sourcepack.stdout.txt" in text
        assert "sourcepack.stderr.txt" in text
        assert "sourcepack-command.txt" in text
        assert "sourcepack.sarif.json" in text
        assert "- SARIF passthrough: copied to" in text
        assert text.count("```") % 2 == 0

    assert "SourcePack SARIF passthrough: copied to" in captured.out


def test_composite_action_like_missing_sarif_is_reported_nonfatal(tmp_path, monkeypatch, capsys):
    module = load_wrapper()
    (tmp_path / ".sourcepack" / "baseline").mkdir(parents=True)
    (tmp_path / ".sourcepack" / "reports").mkdir(parents=True)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    executed: list[list[str]] = []

    def fake_run(command, cwd):
        executed.append(command)
        return subprocess.CompletedProcess(command, 0, stdout='{"verdict":"PASS"}\n', stderr="")

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module.shutil, "which", lambda name: "sourcepack" if name == "sourcepack" else None)

    code = module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "true"])
    captured = capsys.readouterr()

    assert code == 0
    assert len(executed) == 1
    assert not (tmp_path / "out" / "sourcepack.sarif.json").exists()
    assert "enabled, but no SourcePack SARIF report was present; continuing without SARIF artifact" in captured.out
    assert "enabled, but no SourcePack SARIF report was present; continuing without SARIF artifact" in summary.read_text(encoding="utf-8")


def test_composite_action_like_sarif_disabled_does_not_imply_produced_artifact(tmp_path, monkeypatch, capsys):
    module = load_wrapper()
    (tmp_path / ".sourcepack" / "baseline").mkdir(parents=True)
    reports = tmp_path / ".sourcepack" / "reports"
    reports.mkdir(parents=True)
    (reports / "latest.sarif.json").write_text('{"version":"2.1.0"}', encoding="utf-8")

    def fake_run(command, cwd):
        return subprocess.CompletedProcess(command, 0, stdout='{"verdict":"PASS"}\n', stderr="")

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module.shutil, "which", lambda name: "sourcepack" if name == "sourcepack" else None)

    code = module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "false"])
    captured = capsys.readouterr()
    markdown = (tmp_path / "out" / "sourcepack.md").read_text(encoding="utf-8")

    assert code == 0
    assert not (tmp_path / "out" / "sourcepack.sarif.json").exists()
    assert "SourcePack SARIF passthrough: disabled" in captured.out
    assert "- SARIF passthrough: disabled" in markdown
    assert "sourcepack.sarif.json" not in markdown


def test_composite_action_like_prompt_context_does_not_satisfy_missing_baseline(tmp_path, monkeypatch, capsys):
    module = load_wrapper()
    prompt_dir = tmp_path / ".sourcepack" / "prompt"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "context.md").write_text("# non-authoritative prompt guidance\n", encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    invoked: list[list[str]] = []

    def fake_run(command, cwd):
        invoked.append(command)
        return subprocess.CompletedProcess(command, 0, stdout='{"verdict":"PASS"}\n', stderr="")

    monkeypatch.setattr(module, "_run", fake_run)

    code = module.main(["--repo", str(tmp_path), "--baseline-path", ".sourcepack/baseline", "--report-dir", "out"])
    captured = capsys.readouterr()

    assert code != 0
    assert invoked == []
    assert not (tmp_path / ".sourcepack" / "baseline").exists()

    combined = (
        captured.err
        + summary.read_text(encoding="utf-8")
        + (tmp_path / "out" / "sourcepack.stderr.txt").read_text(encoding="utf-8")
    )
    assert "SourcePack failed closed because trusted baseline state is missing" in combined
    assert "CI will not create or update trusted baseline state." in combined
    assert "Create or refresh the baseline locally or in a separate trusted maintainer-controlled setup workflow." in combined
    assert "not a package crash" in combined

    command_log = (tmp_path / "out" / "sourcepack-command.txt").read_text(encoding="utf-8")
    assert command_log == "baseline preflight\n"
    assert "sourcepack baseline" not in command_log
    assert "sourcepack init" not in command_log
    assert "refresh" not in command_log
    assert "repair" not in command_log
    assert "bless" not in command_log


def test_wrapper_comment_pr_false_does_not_create_comment_artifacts(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_sourcepack(bin_dir, stdout='{"verdict":"PASS","traffic_light":"GREEN","findings":[]}\n')
    monkeypatch.setenv("PATH", path_with(bin_dir))

    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out", "--comment-pr", "false"]) == 0

    assert not (tmp_path / "out" / "sourcepack-pr-comment.md").exists()
    assert not (tmp_path / "out" / "sourcepack-pr-comment.txt").exists()


def test_wrapper_comment_pr_renders_body_and_records_missing_event_skip(tmp_path, monkeypatch, capsys):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    source_reports = tmp_path / ".sourcepack" / "reports"
    source_reports.mkdir(parents=True)
    (source_reports / "latest.json").write_text(
        json.dumps(
            {
                "verdict": "FAIL",
                "traffic_light": "RED LIGHT",
                "findings": [
                    {
                        "id": "unsupported_dependency",
                        "severity": "error",
                        "path": "app.py",
                        "message": "app.py imports fastapi, but fastapi is not declared.",
                    },
                    {
                        "id": "execution_evidence_missing",
                        "severity": "warn",
                        "path": "README.md",
                        "message": "tests passed claim has no SourcePack execution-ledger receipt.",
                    },
                ],
                "blockers": [
                    {
                        "id": "unsupported_dependency",
                        "severity": "error",
                        "path": "app.py",
                        "message": "app.py imports fastapi, but fastapi is not declared.",
                    }
                ],
                "warnings": [
                    {
                        "id": "execution_evidence_missing",
                        "severity": "warn",
                        "path": "README.md",
                        "message": "tests passed claim has no SourcePack execution-ledger receipt.",
                    }
                ],
                "checked": ["trusted_baseline", "dependency_manifest", "command_manifest"],
                "not_checked": ["code correctness", "runtime behavior", "security"],
            }
        ),
        encoding="utf-8",
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_sourcepack(bin_dir, stdout='{"verdict":"FAIL","traffic_light":"RED LIGHT"}\n', exit_code=2)
    monkeypatch.setenv("PATH", path_with(bin_dir))
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--report-dir", "out", "--comment-pr", "true"])
    captured = capsys.readouterr()

    assert code == 2
    comment = (tmp_path / "out" / "sourcepack-pr-comment.md").read_text(encoding="utf-8")
    status = (tmp_path / "out" / "sourcepack-pr-comment.txt").read_text(encoding="utf-8")

    assert "<!-- sourcepack-action-comment:v1 -->" in comment
    assert "## SourcePack result" in comment
    assert "**RED LIGHT / FAIL**" in comment
    assert "unsupported_dependency" in comment
    assert "execution_evidence_missing" in comment
    assert "trusted_baseline" in comment
    assert "dependency_manifest" in comment
    assert "code correctness" in comment
    assert "runtime behavior" in comment
    assert "SourcePack does not prove code correctness" in comment
    assert "semantic validity" in comment
    assert "external API truth" in comment
    assert "dependency safety" in comment
    assert "user intent" in comment
    assert "skipped: no pull_request number in GITHUB_EVENT_PATH" in status
    assert "SourcePack PR comment: skipped: no pull_request number in GITHUB_EVENT_PATH" in captured.out


def test_wrapper_comment_pr_missing_token_skips_without_changing_verdict(tmp_path, monkeypatch, capsys):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    event = tmp_path / "event.json"
    event.write_text('{"pull_request":{"number":42}}', encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_sourcepack(bin_dir, stdout='{"verdict":"WARN","traffic_light":"YELLOW LIGHT","findings":[]}\n', exit_code=1)
    monkeypatch.setenv("PATH", path_with(bin_dir))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--report-dir", "out", "--comment-pr", "true"])
    captured = capsys.readouterr()

    assert code == 1
    assert (tmp_path / "out" / "sourcepack-pr-comment.md").exists()
    assert "skipped: missing GITHUB_TOKEN or GH_TOKEN" in (tmp_path / "out" / "sourcepack-pr-comment.txt").read_text(encoding="utf-8")
    assert "SourcePack PR comment: skipped: missing GITHUB_TOKEN or GH_TOKEN" in captured.out


def test_wrapper_comment_pr_updates_existing_marker_comment(tmp_path, monkeypatch):
    module = load_wrapper()
    event = tmp_path / "event.json"
    event.write_text('{"pull_request":{"number":7}}', encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_API_URL", "https://api.example.test")

    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request(method, url, token, payload=None):
        calls.append((method, url, payload))
        if method == "GET":
            return [
                {
                    "id": 123,
                    "body": "old body\n<!-- sourcepack-action-comment:v1 -->\n",
                }
            ]
        if method == "PATCH":
            return {"id": 123}
        raise AssertionError(f"unexpected method {method}")

    monkeypatch.setattr(module, "_github_api_request", fake_request)

    status = module._post_or_update_pr_comment("new SourcePack body")

    assert status == "updated: issue comment 123"
    assert calls == [
        ("GET", "https://api.example.test/repos/owner/repo/issues/7/comments", None),
        (
            "PATCH",
            "https://api.example.test/repos/owner/repo/issues/comments/123",
            {"body": "new SourcePack body"},
        ),
    ]


def test_wrapper_comment_pr_creates_comment_when_marker_is_absent(tmp_path, monkeypatch):
    module = load_wrapper()
    event = tmp_path / "event.json"
    event.write_text('{"number":8}', encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_API_URL", "https://api.example.test")

    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request(method, url, token, payload=None):
        calls.append((method, url, payload))
        if method == "GET":
            return [{"id": 555, "body": "unrelated comment"}]
        if method == "POST":
            return {"id": 556}
        raise AssertionError(f"unexpected method {method}")

    monkeypatch.setattr(module, "_github_api_request", fake_request)

    status = module._post_or_update_pr_comment("new SourcePack body")

    assert status == "created: issue comment 556"
    assert calls == [
        ("GET", "https://api.example.test/repos/owner/repo/issues/8/comments", None),
        (
            "POST",
            "https://api.example.test/repos/owner/repo/issues/8/comments",
            {"body": "new SourcePack body"},
        ),
    ]


def test_wrapper_comment_pr_api_failure_records_status_without_masking_core_result(tmp_path, monkeypatch, capsys):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    event = tmp_path / "event.json"
    event.write_text('{"pull_request":{"number":12}}', encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_sourcepack(bin_dir, stdout='{"verdict":"PASS","traffic_light":"GREEN","findings":[]}\n', exit_code=0)
    monkeypatch.setenv("PATH", path_with(bin_dir))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    module = load_wrapper()

    def broken_request(method, url, token, payload=None):
        raise OSError("network down")

    monkeypatch.setattr(module, "_github_api_request", broken_request)

    code = module.main(["--repo", str(tmp_path), "--report-dir", "out", "--comment-pr", "true"])
    captured = capsys.readouterr()

    assert code == 0
    assert (tmp_path / "out" / "sourcepack-pr-comment.md").exists()
    status = (tmp_path / "out" / "sourcepack-pr-comment.txt").read_text(encoding="utf-8")
    assert "failed:" in status
    assert "network down" in status
    assert "SourcePack PR comment: failed:" in captured.out


def test_comment_pr_body_is_compact_and_does_not_dump_full_stdout(tmp_path):
    module = load_wrapper()
    report = tmp_path / "sourcepack.json"
    markdown = tmp_path / "sourcepack.md"
    command = tmp_path / "sourcepack-command.txt"
    markdown.write_text("# summary\n", encoding="utf-8")
    command.write_text("sourcepack diff . --json --ci\n", encoding="utf-8")
    report.write_text(
        json.dumps(
            {
                "verdict": "FAIL",
                "traffic_light": "RED LIGHT",
                "findings": [
                    {
                        "id": f"unsupported_dependency_{index}",
                        "severity": "error",
                        "path": f"file_{index}.py",
                        "message": "missing dependency",
                    }
                    for index in range(25)
                ],
                "checked": ["trusted_baseline"],
                "not_checked": ["security"],
            }
        ),
        encoding="utf-8",
    )

    body = module._render_pr_comment(
        json_report=report,
        markdown_report=markdown,
        command_log=command,
        sarif_status="disabled",
        mode="ci",
        fail_on_warn=True,
    )

    assert "<!-- sourcepack-action-comment:v1 -->" in body
    assert "unsupported_dependency_0" in body
    assert "unsupported_dependency_19" in body
    assert "unsupported_dependency_20" not in body
    assert "5 additional finding(s) omitted from PR comment" in body
    assert "sourcepack diff . --json --ci" in body
    assert "Full markdown summary is available" in body
    assert body.count("```") % 2 == 0


def test_gitattributes_marks_sourcepack_baseline_binary():
    text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert ".sourcepack/baseline/** -text" in text.splitlines()
