import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "action.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "sourcepack.yml"
EXAMPLE_WORKFLOW = ROOT / "docs" / "examples" / "sourcepack-action.yml"
WRAPPER = ROOT / "scripts" / "sourcepack_action.py"


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
    assert "upload-artifact" in text


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


def test_example_workflow_exists_and_does_not_create_baseline_during_pr():
    text = EXAMPLE_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "# pull_request:" in text
    assert "uses: ./" in text
    assert "sourcepack baseline" not in text
    assert "sourcepack init" not in text
    assert "baseline --force" not in text


def load_wrapper():
    spec = importlib.util.spec_from_file_location("sourcepack_action", WRAPPER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_wrapper_missing_baseline_returns_nonzero_and_message(tmp_path, capsys):
    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--baseline-path", ".sourcepack/baseline", "--report-dir", "reports"])
    captured = capsys.readouterr()
    assert code != 0
    assert "SourcePack failed closed because trusted baseline state is missing" in captured.err
    assert "CI will not create or update trusted baseline state." in captured.err
    assert (tmp_path / "reports" / "sourcepack.stderr.txt").exists()


def test_wrapper_creates_report_dir_and_captures_command_output(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\"}'\necho err >&2\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    code = module.main(["--repo", str(tmp_path), "--baseline-path", ".sourcepack/baseline", "--report-dir", "reports"])
    assert code == 0
    report_dir = tmp_path / "reports"
    assert (report_dir / "sourcepack-command.txt").read_text(encoding="utf-8").startswith("sourcepack diff")
    assert "PASS" in (report_dir / "sourcepack.stdout.txt").read_text(encoding="utf-8")
    assert "err" in (report_dir / "sourcepack.stderr.txt").read_text(encoding="utf-8")
    assert (report_dir / "sourcepack.json").exists()
    assert (report_dir / "sourcepack.md").exists()


def os_path() -> str:
    import os

    return os.environ.get("PATH", "")


def test_wrapper_fail_on_warn_is_explicit_in_command(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"WARN\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    code = module.main([
        "--repo", str(tmp_path),
        "--baseline-path", ".sourcepack/baseline",
        "--report-dir", "reports",
        "--mode", "local",
        "--fail-on-warn", "true",
    ])
    assert code == 0
    command = (tmp_path / "reports" / "sourcepack-command.txt").read_text(encoding="utf-8")
    assert "--strict" in command


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


def test_wrapper_sarif_true_copies_existing_latest_sarif(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    reports = tmp_path / ".sourcepack" / "reports"
    reports.mkdir(parents=True)
    (reports / "latest.sarif.json").write_text('{"version":"2.1.0"}', encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
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
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "false"]) == 0
    assert not (tmp_path / "out" / "sourcepack.sarif.json").exists()
    (reports / "latest.sarif.json").unlink()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out2", "--sarif", "true"]) == 0
    assert not (tmp_path / "out2" / "sourcepack.sarif.json").exists()


def test_wrapper_missing_baseline_markdown_is_valid(tmp_path, capsys):
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "reports"]) != 0
    _ = capsys.readouterr()
    text = (tmp_path / "reports" / "sourcepack.md").read_text(encoding="utf-8")
    assert text.count("```") % 2 == 0
    assert "SourcePack failed closed because trusted baseline state is missing" in text


def test_action_inputs_are_documented_in_ci_docs():
    inputs = set(load_action()["inputs"])
    ci_text = (ROOT / "docs" / "ci.md").read_text(encoding="utf-8")
    missing = [name for name in sorted(inputs) if f"`{name}`" not in ci_text]
    assert missing == []


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


def test_wrapper_reports_paths_sarif_missing_and_step_summary(tmp_path, monkeypatch, capsys):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\",\"traffic_light\":\"GREEN\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
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
    forbidden_claims = ["proves correctness", "proves security", "proves runtime success", "proves external API truth", "proves user intent"]
    assert [claim for claim in forbidden_claims if claim in summary_text] == []


def test_wrapper_sarif_disabled_summary_does_not_claim_sarif(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    reports = tmp_path / ".sourcepack" / "reports"
    reports.mkdir(parents=True)
    (reports / "latest.sarif.json").write_text('{"version":"2.1.0"}', encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out", "--sarif", "false"]) == 0
    summary = (tmp_path / "out" / "sourcepack.md").read_text(encoding="utf-8")
    assert "SARIF passthrough: disabled" in summary
    assert not (tmp_path / "out" / "sourcepack.sarif.json").exists()


def test_wrapper_preserves_exact_command_and_delegates_to_cli(tmp_path, monkeypatch):
    baseline = tmp_path / ".sourcepack" / "baseline"
    baseline.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"
    fake = bin_dir / "sourcepack"
    fake.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$0 $*\" > {calls}\necho '{{\"verdict\":\"PASS\"}}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out", "--mode", "strict"]) == 0
    command = (tmp_path / "out" / "sourcepack-command.txt").read_text(encoding="utf-8").strip()
    assert command == f"sourcepack diff {tmp_path} --json --strict"
    assert f"diff {tmp_path} --json --strict" in calls.read_text(encoding="utf-8")


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
    fake = bin_dir / "sourcepack"
    fake.write_text("#!/bin/sh\necho '{\"verdict\":\"PASS\"}'\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os_path()}")
    module = load_wrapper()
    assert module.main(["--repo", str(tmp_path), "--report-dir", "out"]) == 0
    assert sorted(p.relative_to(baseline) for p in baseline.rglob("*")) == before_baseline
    assert sorted(p.relative_to(prompt) for p in prompt.rglob("*")) == before_prompt
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    assert ".sourcepack/prompt" not in wrapper_text
    assert "prompt" not in wrapper_text.lower()
