import subprocess

from sourcepack.judgment import SourceScanner, sha256_text


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

    assert [file.relative_path for file in scanner.included_files] == ["src/app.py"]
    ignored = {item.relative_path: item.reason for item in scanner.ignored_files}
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

    assert [file.relative_path for file in scanner.included_files] == [".hidden.py"]
    ignored = {item.relative_path: item.reason for item in scanner.ignored_files}
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


def test_source_scanner_prefers_git_tracked_files_when_available(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "sourcepack@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "SourcePack Test"], cwd=tmp_path, check=True)
    (tmp_path / "app.py").write_text("print('tracked')\n", encoding="utf-8")
    (tmp_path / "scratch.py").write_text("import fastapi\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "track app"], cwd=tmp_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    scanner = SourceScanner(tmp_path).scan()

    assert [file.relative_path for file in scanner.included_files] == ["app.py"]
    ignored = {item.relative_path: item.reason for item in scanner.ignored_files}
    assert ignored["scratch.py"] == "untracked_file_skipped"
