from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def readme() -> str:
    return README.read_text(encoding="utf-8")


def cli_subcommands() -> set[str]:
    tree = ast.parse((ROOT / "src" / "sourcepack" / "cli.py").read_text(encoding="utf-8"))
    commands: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_parser":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                commands.add(node.args[0].value)
    return commands


def project_claims_published_package() -> bool:
    marker = ROOT / ".sourcepack-published"
    return marker.exists() and marker.read_text(encoding="utf-8").strip().lower() in {"1", "true", "yes"}


def test_readme_does_not_claim_pypi_install_unless_published() -> None:
    text = readme()
    forbidden = ["pipx install sourcepack", "uv tool install sourcepack", "pip install sourcepack"]
    if not project_claims_published_package():
        available_sections = re.findall(r"```(?:bash)?\n(.*?)```", text, flags=re.S)
        executable_claims = "\n".join(block for block in available_sections if "planned" not in block.lower())
        for command in forbidden:
            assert command not in executable_claims


def test_readme_sourcepack_commands_use_existing_subcommands() -> None:
    text = readme()
    commands = cli_subcommands()
    for match in re.finditer(r"(?:^|[\n`])sourcepack\s+([a-z][a-z-]*)", text):
        subcommand = match.group(1)
        assert subcommand in commands, f"README references missing sourcepack subcommand: {subcommand}"


def test_readme_links_to_existing_docs_files() -> None:
    text = readme()
    for link in re.findall(r"\[[^\]]+\]\((docs/[^)#]+)(?:#[^)]+)?\)", text):
        assert (ROOT / link).exists(), f"README links to missing docs path: {link}"


def test_readme_image_paths_are_present_or_explained_as_expected_targets() -> None:
    text = readme()
    image_paths = re.findall(r"docs/assets/[^`\s)]+\.png", text)
    for image_path in image_paths:
        assert (ROOT / image_path).exists() or "expected screenshot targets" in text


def test_readme_links_reason_codes_and_reports_commands() -> None:
    text = readme()
    assert "docs/reason-codes.md" in text
    assert "sourcepack report open" in text
    assert "sourcepack report path" in text


def test_readme_dogfooding_claim_preserves_sourcepack_limitations() -> None:
    text = readme()
    assert "sourcepack diff . --ci --json" in text
    assert "committed `.sourcepack/baseline/` state" in text
    for forbidden in [
        "proves correctness",
        "proves security",
        "proves runtime success",
        "proves dependency safety",
        "proves external API truth",
        "proves user intent",
    ]:
        assert forbidden not in text.lower()


def test_demo_output_matches_quick_demo_claim() -> None:
    import os
    import subprocess
    import sys

    cp = subprocess.run(
        [sys.executable, "-m", "sourcepack.cli", "demo"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert cp.returncode == 0, cp.stdout
    text = cp.stdout
    assert "RED LIGHT: commit blocked" in text
    assert "unsupported_dependency: sourcepack/server.py imports fastapi, but fastapi is not declared." in text
    assert "PASS manifest.json" not in text


def test_readme_first_five_minutes_and_public_alpha_limits() -> None:
    text = readme()
    for required in [
        "SourcePack blocks AI-generated code changes that rely on fake repo facts.",
        "- AI coding agents can edit files that do not exist.",
        "- They can import undeclared dependencies.",
        "- They can reference missing scripts or unsupported commands.",
        "- They can reshape project structure based on prompt assumptions.",
        "- SourcePack catches those locally verifiable failures before commit or in CI.",
        "python -m pip install sourcepack",
        "sourcepack demo",
        "RED LIGHT: commit blocked",
        "unsupported_dependency",
        "sourcepack init . --auto",
        "sourcepack diff .",
        "sourcepack report open",
    ]:
        assert required in text
    claims = text.split("## What SourcePack does not claim", 1)[1].split("## Public proof links", 1)[0].strip()
    assert claims == "\n".join([
        "- does not prove code correctness",
        "- does not prove security",
        "- does not prove runtime success",
        "- does not prove semantic validity",
        "- does not prove external API truth",
        "- does not prove dependency safety",
        "- does not prove user intent",
    ])
