import json
import subprocess
import sys
from pathlib import Path

from sourcepack.packet import PacketWriter, SourceScanner, sha256_text


def init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "sourcepack@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "SourcePack Test"], cwd=repo, check=True)


def git_add_commit(repo: Path, *paths: str) -> None:
    subprocess.run(["git", "add", *paths], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "test fixture"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def included_paths(scanner: SourceScanner) -> list[str]:
    return [file.relative_path for file in scanner.included_files]


def ignored_reasons(scanner: SourceScanner) -> dict[str, str]:
    return {item.relative_path: item.reason for item in scanner.ignored_files}


def test_source_scanner_includes_text_and_records_ignored_reasons(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("ignored\n", encoding="utf-8")
    (tmp_path / ".hidden.py").write_text("hidden\n", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=abcdefghijklmnop\n", encoding="utf-8")
    (tmp_path / "cert.pem").write_text("pem\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"not really png")
    (tmp_path / "module.xyz").write_text("unsupported\n", encoding="utf-8")
    (tmp_path / "binary.txt").write_bytes(b"abc\x00def")

    scanner = SourceScanner(tmp_path).scan()

    assert included_paths(scanner) == ["src/app.py"]
    ignored = ignored_reasons(scanner)
    assert ignored[".git/"] == "ignored_directory"
    assert ignored[".hidden.py"] == "hidden_file"
    assert ignored[".env"] == "hidden_file"
    assert ignored["cert.pem"] == "ignored_pattern"
    assert ignored["image.png"] == "ignored_pattern"
    assert ignored["module.xyz"] == "unsupported_extension"
    assert ignored["binary.txt"] == "binary_detected"


def test_source_scanner_can_include_hidden_files_when_enabled(tmp_path):
    (tmp_path / ".hidden.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=abcdefghijklmnop\n", encoding="utf-8")

    scanner = SourceScanner(tmp_path, include_hidden=True).scan()

    assert included_paths(scanner) == [".hidden.py"]
    ignored = ignored_reasons(scanner)
    assert ignored[".env"] == "ignored_pattern"


def test_source_scanner_redacts_and_keeps_source_hash_separate_from_packet_hash(tmp_path):
    original = "api_key = abcdefghijklmnop\n"
    (tmp_path / "settings.py").write_text(original, encoding="utf-8")

    scanner = SourceScanner(tmp_path, redact=True).scan()
    included = scanner.included_files[0]

    assert "abcdefghijklmnop" not in included.content
    assert "[REDACTED:generic_api_key]" in included.content
    assert scanner.redactions[0]["file"] == "settings.py"
    assert included.source_sha256 == sha256_text(original)
    assert included.packet_sha256 == sha256_text(included.content)
    assert included.source_sha256 != included.packet_sha256



def test_source_scanner_falls_back_to_filesystem_when_git_has_no_tracked_files(tmp_path):
    init_git_repo(tmp_path)
    (tmp_path / "app.py").write_text("print('untracked initial file')\n", encoding="utf-8")

    scanner = SourceScanner(tmp_path).scan()

    assert "app.py" in included_paths(scanner)
    assert ignored_reasons(scanner).get("app.py") != "untracked_file_skipped"


def test_source_scanner_skips_untracked_files_in_empty_tracked_subdirectory(tmp_path):
    init_git_repo(tmp_path)

    (tmp_path / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    git_add_commit(tmp_path, "app.py")

    scan_root = tmp_path / "examples" / "golden" / "output" / "fail-unsupported-dependency" / "repo"
    scan_root.mkdir(parents=True)
    (scan_root / "generated.py").write_text("import fastapi\n", encoding="utf-8")

    scanner = SourceScanner(scan_root).scan()

    assert included_paths(scanner) == []
    assert ignored_reasons(scanner)["generated.py"] == "untracked_file_skipped"


def test_source_scanner_uses_tracked_files_as_trust_boundary_in_git_repo(tmp_path):
    init_git_repo(tmp_path)

    (tmp_path / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    git_add_commit(tmp_path, "app.py")

    generated = tmp_path / "examples" / "golden" / "output" / "fail-unsupported-dependency" / "repo"
    generated.mkdir(parents=True)
    (generated / "app.py").write_text("import fastapi\n", encoding="utf-8")
    (generated / "pyproject.toml").write_text("[project]\nname = 'generated'\n", encoding="utf-8")

    scanner = SourceScanner(tmp_path).scan()

    assert included_paths(scanner) == ["app.py"]

    ignored = ignored_reasons(scanner)
    assert ignored["examples/golden/output/fail-unsupported-dependency/repo/app.py"] == "untracked_file_skipped"
    assert ignored["examples/golden/output/fail-unsupported-dependency/repo/pyproject.toml"] == "untracked_file_skipped"


def test_source_scanner_preserves_existing_filesystem_behavior_outside_git_repo(tmp_path):
    (tmp_path / "tracked_by_nothing.py").write_text("print('still included outside git')\n", encoding="utf-8")
    (tmp_path / "scratch.py").write_text("print('also included outside git')\n", encoding="utf-8")

    scanner = SourceScanner(tmp_path).scan()

    assert included_paths(scanner) == ["scratch.py", "tracked_by_nothing.py"]


def test_source_scanner_includes_tracked_files_relative_to_tracked_subdirectory(tmp_path):
    init_git_repo(tmp_path)

    package = tmp_path / "packages" / "api"
    package.mkdir(parents=True)
    (package / "app.py").write_text("def app():\n    return 'api'\n", encoding="utf-8")
    (package / "untracked.py").write_text("print('generated')\n", encoding="utf-8")
    git_add_commit(tmp_path, "packages/api/app.py")

    scanner = SourceScanner(package).scan()

    assert included_paths(scanner) == ["app.py"]
    assert ignored_reasons(scanner)["untracked.py"] == "untracked_file_skipped"


def test_source_scanner_preserves_filesystem_behavior_when_git_command_fails(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text("print('included when git unavailable')\n", encoding="utf-8")

    def fail_git(*args, **kwargs):
        raise OSError("git unavailable")

    monkeypatch.setattr(subprocess, "run", fail_git)

    scanner = SourceScanner(tmp_path).scan()

    assert included_paths(scanner) == ["app.py"]
    assert ignored_reasons(scanner).get("app.py") != "untracked_file_skipped"


def test_packet_writer_does_not_derive_reality_from_untracked_generated_output(tmp_path):
    init_git_repo(tmp_path)

    (tmp_path / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    git_add_commit(tmp_path, "app.py")

    generated = tmp_path / "examples" / "golden" / "output" / "fail-unsupported-dependency" / "repo"
    generated.mkdir(parents=True)
    (generated / "app.py").write_text("import fastapi\n", encoding="utf-8")
    (generated / "pyproject.toml").write_text("[project]\nname = 'generated'\n", encoding="utf-8")

    packet = PacketWriter(tmp_path / "packet", SourceScanner(tmp_path).scan(), force=True).write_all()

    manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
    context_md = (packet / "context.md").read_text(encoding="utf-8")
    context_xml = (packet / "context.xml").read_text(encoding="utf-8")
    file_tree = (packet / "file_tree.txt").read_text(encoding="utf-8")
    reality_map = json.loads((packet / "reality_map.json").read_text(encoding="utf-8"))

    manifest_paths = {record["relative_path"] for record in manifest["included_files"]}

    assert "app.py" in manifest_paths
    assert "examples/golden/output/fail-unsupported-dependency/repo/app.py" not in manifest_paths
    assert "examples/golden/output" not in context_md
    assert "examples/golden/output" not in context_xml
    assert "[INC] examples/golden/output" not in file_tree
    assert "fastapi" not in reality_map["detected_dependencies"]
    assert "FastAPI" not in reality_map["frameworks"]
    assert "app.py" in reality_map["confirmed_files"]


def test_scanner_behavior_file_can_run_directly_under_pytest(tmp_path):
    assert sys.version_info >= (3, 11)
