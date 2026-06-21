from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import release_smoke


def _write_wheel(path: Path, *, forbidden: bool = False) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name in release_smoke.WHEEL_REQUIRED_FILES:
            text = "content\n"
            if name.endswith(".env"):
                text = release_smoke.DEMO_ENV_MARKER + "\n"
            if forbidden and name.endswith("fake_ai_answer.md"):
                text += "ghp_bad_placeholder\n"
            zf.writestr(name, text)
        zf.writestr("sourcepack/examples/demo_repo/sourcepack/cli.py", "print('demo')\n")
        zf.writestr("sourcepack/examples/demo_repo/tests/test_verify.py", "def test_ok(): pass\n")
        zf.writestr("sourcepack-1.2.3.dist-info/METADATA", "Name: sourcepack\nVersion: 1.2.3\n")


def _write_sdist(path: Path, *, missing_tests: bool = False) -> None:
    with tarfile.open(path, "w:gz") as tf:
        files = {name: "content\n" for name in release_smoke.SDIST_REQUIRED_FILES}
        files["src/sourcepack/examples/demo_repo/.env"] = release_smoke.DEMO_ENV_MARKER + "\n"
        files["src/sourcepack/examples/demo_repo/sourcepack/cli.py"] = "print('demo')\n"
        if not missing_tests:
            files["src/sourcepack/examples/demo_repo/tests/test_verify.py"] = "def test_ok(): pass\n"
        for inner, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(f"sourcepack-1.2.3/{inner}")
            info.size = len(data)
            import io

            tf.addfile(info, io.BytesIO(data))


def test_verify_expected_artifacts_uses_wheel_metadata_version(tmp_path: Path) -> None:
    wheel = tmp_path / "sourcepack-1.2.3-py3-none-any.whl"
    sdist = tmp_path / "sourcepack-1.2.3.tar.gz"
    _write_wheel(wheel)
    _write_sdist(sdist)

    assert release_smoke.verify_expected_artifacts(tmp_path) == ("1.2.3", wheel, sdist)


def test_verify_expected_artifacts_rejects_name_metadata_mismatch(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "sourcepack-1.2.3-py3-none-any.whl")
    _write_sdist(tmp_path / "sourcepack-9.9.9.tar.gz")

    with pytest.raises(release_smoke.ReleaseSmokeError, match="artifact names do not match"):
        release_smoke.verify_expected_artifacts(tmp_path)


def test_inspect_wheel_rejects_forbidden_demo_asset_token(tmp_path: Path) -> None:
    wheel = tmp_path / "sourcepack-1.2.3-py3-none-any.whl"
    _write_wheel(wheel, forbidden=True)

    with pytest.raises(release_smoke.ReleaseSmokeError, match="forbidden token pattern"):
        release_smoke.inspect_wheel_contents(wheel)


def test_inspect_sdist_requires_demo_tests_file(tmp_path: Path) -> None:
    sdist = tmp_path / "sourcepack-1.2.3.tar.gz"
    _write_sdist(sdist, missing_tests=True)

    with pytest.raises(release_smoke.ReleaseSmokeError, match="no concrete file"):
        release_smoke.inspect_sdist_contents(sdist)
