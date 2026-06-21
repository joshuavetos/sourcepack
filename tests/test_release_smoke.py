from __future__ import annotations

import io
import importlib
import runpy
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import release_smoke


def _write_wheel(path: Path, *, version: str = "1.2.3", name: str = "sourcepack", forbidden: bool = False, outside_forbidden: bool = False) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for member in release_smoke.WHEEL_REQUIRED_FILES:
            text = "content\n"
            if member.endswith(".env"):
                text = release_smoke.DEMO_ENV_MARKER + "\n"
            if forbidden and member.endswith("fake_ai_answer.md"):
                text += "ghp_bad_placeholder\n"
            zf.writestr(member, text)
        zf.writestr("sourcepack/examples/demo_repo/sourcepack/cli.py", "print('demo')\n")
        zf.writestr("sourcepack/examples/demo_repo/tests/test_verify.py", "def test_ok(): pass\n")
        if outside_forbidden:
            zf.writestr("sourcepack/detectors/token_detector.py", "OPENAI_API_KEY = 'intentional test string'\n")
        zf.writestr(f"sourcepack-{version}.dist-info/METADATA", f"Name: {name}\nVersion: {version}\n")


def _write_sdist(path: Path, *, version: str = "1.2.3", name: str = "sourcepack", missing_tests: bool = False, forbidden: bool = False, outside_forbidden: bool = False) -> None:
    with tarfile.open(path, "w:gz") as tf:
        files = {member: "content\n" for member in release_smoke.SDIST_REQUIRED_FILES}
        files["src/sourcepack/examples/demo_repo/.env"] = release_smoke.DEMO_ENV_MARKER + "\n"
        files["src/sourcepack/examples/demo_repo/sourcepack/cli.py"] = "print('demo')\n"
        if not missing_tests:
            files["src/sourcepack/examples/demo_repo/tests/test_verify.py"] = "def test_ok(): pass\n"
        if forbidden:
            files["src/sourcepack/examples/fake_ai_answer.md"] += "ghp_bad_placeholder\n"
        if outside_forbidden:
            files["src/sourcepack/detectors/token_detector.py"] = "OPENAI_API_KEY = 'intentional test string'\n"
        files["PKG-INFO"] = f"Name: {name}\nVersion: {version}\n"
        for inner, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(f"sourcepack-{version}/{inner}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def test_collect_dist_artifacts_returns_sorted_concrete_paths(tmp_path: Path) -> None:
    (tmp_path / "b.tar.gz").write_text("b")
    (tmp_path / "a.whl").write_text("a")
    (tmp_path / "nested").mkdir()

    assert release_smoke.collect_dist_artifacts(tmp_path) == [tmp_path / "a.whl", tmp_path / "b.tar.gz"]


def test_collect_dist_artifacts_rejects_no_artifacts(tmp_path: Path) -> None:
    with pytest.raises(release_smoke.ReleaseSmokeError, match="no built artifacts"):
        release_smoke.collect_dist_artifacts(tmp_path)


def test_build_clean_artifacts_invokes_twine_with_concrete_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_clean(root: Path) -> None:
        pass

    def fake_run(cmd: list[str], cwd: Path = release_smoke.ROOT, *, check: bool = True) -> subprocess.CompletedProcess[str]:
        commands.append(cmd)
        if cmd[:3] == [sys.executable, "-m", "build"]:
            tmp_path.mkdir(exist_ok=True)
            (tmp_path / "sourcepack-1.2.3-py3-none-any.whl").write_text("wheel")
            (tmp_path / "sourcepack-1.2.3.tar.gz").write_text("sdist")
        return subprocess.CompletedProcess(cmd, 0, "")

    monkeypatch.setattr(release_smoke, "DIST", tmp_path)
    monkeypatch.setattr(release_smoke, "clean_build_outputs", fake_clean)
    monkeypatch.setattr(release_smoke, "run", fake_run)

    release_smoke.build_clean_artifacts()

    twine_cmd = commands[-1]
    assert twine_cmd[:4] == [sys.executable, "-m", "twine", "check"]
    assert "dist/*" not in twine_cmd
    assert twine_cmd[4:] == [str(tmp_path / "sourcepack-1.2.3-py3-none-any.whl"), str(tmp_path / "sourcepack-1.2.3.tar.gz")]


def test_verify_expected_artifacts_accepts_matching_wheel_and_sdist_metadata(tmp_path: Path) -> None:
    wheel = tmp_path / "sourcepack-1.2.3-py3-none-any.whl"
    sdist = tmp_path / "sourcepack-1.2.3.tar.gz"
    _write_wheel(wheel)
    _write_sdist(sdist)

    assert release_smoke.verify_expected_artifacts(tmp_path) == ("1.2.3", wheel, sdist)


def test_verify_expected_artifacts_rejects_wheel_sdist_metadata_version_mismatch(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "sourcepack-1.2.3-py3-none-any.whl", version="1.2.3")
    _write_sdist(tmp_path / "sourcepack-1.2.3.tar.gz", version="9.9.9")

    with pytest.raises(release_smoke.ReleaseSmokeError, match="does not match sdist metadata version"):
        release_smoke.verify_expected_artifacts(tmp_path)


def test_verify_expected_artifacts_rejects_sdist_package_name_mismatch(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "sourcepack-1.2.3-py3-none-any.whl")
    _write_sdist(tmp_path / "sourcepack-1.2.3.tar.gz", name="wrongname")

    with pytest.raises(release_smoke.ReleaseSmokeError, match="sdist metadata package name mismatch"):
        release_smoke.verify_expected_artifacts(tmp_path)


def test_verify_expected_artifacts_rejects_artifact_filename_version_mismatch(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "sourcepack-1.2.3-py3-none-any.whl")
    _write_sdist(tmp_path / "sourcepack-9.9.9.tar.gz")

    with pytest.raises(release_smoke.ReleaseSmokeError, match="artifact names do not match"):
        release_smoke.verify_expected_artifacts(tmp_path)


def test_clean_build_outputs_removes_root_egg_info_only(tmp_path: Path) -> None:
    (tmp_path / "dist").mkdir()
    (tmp_path / "build").mkdir()
    root_egg = tmp_path / "sourcepack.egg-info"
    root_egg.mkdir()
    nested_egg = tmp_path / "fixtures" / "vendored.egg-info"
    nested_egg.mkdir(parents=True)

    release_smoke.clean_build_outputs(tmp_path)

    assert not (tmp_path / "dist").exists()
    assert not (tmp_path / "build").exists()
    assert not root_egg.exists()
    assert nested_egg.exists()


def test_clean_build_outputs_failure_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "dist").mkdir()
    monkeypatch.setattr(release_smoke.shutil, "rmtree", lambda path: None)

    with pytest.raises(release_smoke.ReleaseSmokeError, match="unable to remove build output"):
        release_smoke.clean_build_outputs(tmp_path)


def test_inspect_wheel_rejects_forbidden_demo_asset_token(tmp_path: Path) -> None:
    wheel = tmp_path / "sourcepack-1.2.3-py3-none-any.whl"
    _write_wheel(wheel, forbidden=True)

    with pytest.raises(release_smoke.ReleaseSmokeError, match="forbidden token pattern"):
        release_smoke.inspect_wheel_contents(wheel)


def test_inspect_sdist_rejects_forbidden_demo_asset_token(tmp_path: Path) -> None:
    sdist = tmp_path / "sourcepack-1.2.3.tar.gz"
    _write_sdist(sdist, forbidden=True)

    with pytest.raises(release_smoke.ReleaseSmokeError, match="forbidden token pattern"):
        release_smoke.inspect_sdist_contents(sdist)


def test_forbidden_tokens_outside_packaged_release_demo_prefixes_are_ignored(tmp_path: Path) -> None:
    wheel = tmp_path / "sourcepack-1.2.3-py3-none-any.whl"
    sdist = tmp_path / "sourcepack-1.2.3.tar.gz"
    _write_wheel(wheel, outside_forbidden=True)
    _write_sdist(sdist, outside_forbidden=True)

    release_smoke.inspect_wheel_contents(wheel)
    release_smoke.inspect_sdist_contents(sdist)


def test_inspect_sdist_requires_demo_tests_file(tmp_path: Path) -> None:
    sdist = tmp_path / "sourcepack-1.2.3.tar.gz"
    _write_sdist(sdist, missing_tests=True)

    with pytest.raises(release_smoke.ReleaseSmokeError, match="no concrete file"):
        release_smoke.inspect_sdist_contents(sdist)


def test_tools_release_smoke_import_does_not_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_run_path(path_name: str, *, run_name: str | None = None):
        calls.append((path_name, run_name))
        return {}

    monkeypatch.setattr(runpy, "run_path", fake_run_path)
    sys.modules.pop("tools.release_smoke", None)
    importlib.import_module("tools.release_smoke")

    assert calls == []


def test_tools_release_smoke_main_executes_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    import tools.release_smoke as wrapper

    calls: list[tuple[str, str | None]] = []

    def fake_run_path(path_name: str, *, run_name: str | None = None):
        calls.append((path_name, run_name))
        return {}

    monkeypatch.setattr(wrapper.runpy, "run_path", fake_run_path)

    assert wrapper.main() == 0
    assert calls == [(str(wrapper.SCRIPT), "__main__")]
