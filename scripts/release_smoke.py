from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
PACKAGE_NAME = "sourcepack"
MISSING_ASSETS_ERROR = "ERROR: examples/demo_repo and examples/fake_ai_answer.md are required"
DEMO_ENV_MARKER = "SOURCEPACK_DEMO_PLACEHOLDER=example_value_not_a_secret"
FORBIDDEN_TOKEN_PATTERNS = (
    "sk-proj-",
    "THIS_SHOULD_NOT_BE_INCLUDED",
    "OPENAI_API_KEY",
    "ghp_",
    "github_pat_",
    "xoxb-",
    "AKIA",
    "ASIA",
    "ya29.",
)
WHEEL_REQUIRED_FILES = (
    "sourcepack/assets/audit_template.md",
    "sourcepack/assets/packet_instructions.md",
    "sourcepack/examples/fake_ai_answer.md",
    "sourcepack/examples/fake_ai_patch.diff",
    "sourcepack/examples/demo_repo/.env",
)
SDIST_REQUIRED_FILES = tuple(f"src/{path}" for path in WHEEL_REQUIRED_FILES)
WHEEL_DEMO_SCAN_PREFIXES = (
    "sourcepack/assets/",
    "sourcepack/examples/",
)
SDIST_DEMO_SCAN_PREFIXES = tuple(f"src/{prefix}" for prefix in WHEEL_DEMO_SCAN_PREFIXES)


class ReleaseSmokeError(RuntimeError):
    pass


def run(cmd: list[str], cwd: Path = ROOT, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd), flush=True)
    cp = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(cp.stdout, end="")
    if check and cp.returncode != 0:
        raise ReleaseSmokeError(f"command failed with exit {cp.returncode}: {' '.join(cmd)}")
    return cp


def clean_build_outputs(root: Path = ROOT) -> None:
    for path in (root / "dist", root / "build"):
        if path.exists():
            shutil.rmtree(path)
        if path.exists():
            raise ReleaseSmokeError(f"unable to remove build output: {path}")
    egg_info_paths = [*root.glob("*.egg-info"), root / "src" / "sourcepack.egg-info"]
    for path in egg_info_paths:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        if path.exists():
            raise ReleaseSmokeError(f"unable to remove egg-info artifact: {path}")


def collect_dist_artifacts(dist: Path = DIST) -> list[Path]:
    artifacts = sorted(path for path in dist.iterdir() if path.is_file()) if dist.exists() else []
    if not artifacts:
        raise ReleaseSmokeError(f"no built artifacts found in {dist}; cannot run twine check")
    return artifacts


def build_clean_artifacts() -> None:
    clean_build_outputs(ROOT)
    run([sys.executable, "-m", "build"], ROOT)
    artifacts = collect_dist_artifacts(DIST)
    run([sys.executable, "-m", "twine", "check", *(str(path) for path in artifacts)], ROOT)


def _check_package_metadata(metadata, artifact: Path, label: str) -> tuple[str, str]:
    name = metadata.get("Name")
    version = metadata.get("Version")
    if name != PACKAGE_NAME:
        raise ReleaseSmokeError(f"{label} metadata package name mismatch in {artifact}: expected {PACKAGE_NAME!r}, found {name!r}")
    if not version:
        raise ReleaseSmokeError(f"missing Version in {label} metadata for {artifact}")
    return name, version


def _wheel_metadata(wheel: Path) -> tuple[str, str]:
    with zipfile.ZipFile(wheel) as zf:
        metadata_names = [name for name in zf.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ReleaseSmokeError(f"expected exactly one wheel METADATA file in {wheel}, found {metadata_names}")
        metadata = Parser().parsestr(zf.read(metadata_names[0]).decode("utf-8"))
    return _check_package_metadata(metadata, wheel, "wheel")


def _sdist_metadata(sdist: Path) -> tuple[str, str]:
    with tarfile.open(sdist, "r:gz") as tf:
        metadata_names = [
            member
            for member in tf.getmembers()
            if member.isfile()
            and len(PurePosixPath(member.name).parts) == 2
            and PurePosixPath(member.name).name == "PKG-INFO"
        ]
        if len(metadata_names) != 1:
            raise ReleaseSmokeError(f"expected exactly one top-level sdist PKG-INFO file in {sdist}, found {[m.name for m in metadata_names]}")
        metadata_file = tf.extractfile(metadata_names[0])
        if metadata_file is None:
            raise ReleaseSmokeError(f"unable to read sdist PKG-INFO in {sdist}")
        metadata = Parser().parsestr(metadata_file.read().decode("utf-8"))
    return _check_package_metadata(metadata, sdist, "sdist")


def verify_expected_artifacts(dist: Path = DIST) -> tuple[str, Path, Path]:
    wheels = sorted(dist.glob("sourcepack-*.whl"))
    sdists = sorted(dist.glob("sourcepack-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ReleaseSmokeError(
            f"expected exactly one SourcePack wheel and one sdist in {dist}; found wheels={wheels}, sdists={sdists}"
        )
    _wheel_name, wheel_version = _wheel_metadata(wheels[0])
    _sdist_name, sdist_version = _sdist_metadata(sdists[0])
    if wheel_version != sdist_version:
        raise ReleaseSmokeError(
            f"wheel metadata version {wheel_version!r} does not match sdist metadata version {sdist_version!r}"
        )
    version = wheel_version
    expected_wheel = dist / f"sourcepack-{version}-py3-none-any.whl"
    expected_sdist = dist / f"sourcepack-{version}.tar.gz"
    if wheels[0] != expected_wheel or sdists[0] != expected_sdist:
        raise ReleaseSmokeError(
            "artifact names do not match packaging metadata version "
            f"{version!r}; expected {expected_wheel.name} and {expected_sdist.name}, "
            f"found {wheels[0].name} and {sdists[0].name}"
        )
    return version, wheels[0], sdists[0]


def _is_concrete_member(name: str, prefix: str) -> bool:
    return name.startswith(prefix) and name != prefix and not name.endswith("/")


def _check_forbidden_text(name: str, text: str) -> None:
    for pattern in FORBIDDEN_TOKEN_PATTERNS:
        if pattern in text:
            raise ReleaseSmokeError(f"forbidden token pattern {pattern!r} found in packaged release asset {name}")


def _decode_member(name: str, data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseSmokeError(f"packaged release asset is not UTF-8 text: {name}") from exc


def inspect_wheel_contents(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
        missing = [name for name in WHEEL_REQUIRED_FILES if name not in names]
        if missing:
            raise ReleaseSmokeError(f"wheel is missing required packaged assets: {missing}")
        for prefix in ("sourcepack/examples/demo_repo/sourcepack/", "sourcepack/examples/demo_repo/tests/"):
            if not any(_is_concrete_member(name, prefix) for name in names):
                raise ReleaseSmokeError(f"wheel has no concrete file under {prefix}")
        env_text = _decode_member("sourcepack/examples/demo_repo/.env", zf.read("sourcepack/examples/demo_repo/.env"))
        if DEMO_ENV_MARKER not in env_text:
            raise ReleaseSmokeError("wheel demo .env does not contain the required placeholder marker")
        for name in sorted(names):
            if any(name.startswith(prefix) for prefix in WHEEL_DEMO_SCAN_PREFIXES) and not name.endswith("/"):
                _check_forbidden_text(name, _decode_member(name, zf.read(name)))


def inspect_sdist_contents(sdist: Path) -> None:
    with tarfile.open(sdist, "r:gz") as tf:
        members = [m for m in tf.getmembers() if m.isfile()]
        files_by_inner_path: dict[str, tarfile.TarInfo] = {}
        for member in members:
            parts = PurePosixPath(member.name).parts
            if len(parts) >= 2:
                files_by_inner_path["/".join(parts[1:])] = member
        names = set(files_by_inner_path)
        missing = [name for name in SDIST_REQUIRED_FILES if name not in names]
        if missing:
            raise ReleaseSmokeError(f"sdist is missing required packaged assets: {missing}")
        for prefix in ("src/sourcepack/examples/demo_repo/sourcepack/", "src/sourcepack/examples/demo_repo/tests/"):
            if not any(_is_concrete_member(name, prefix) for name in names):
                raise ReleaseSmokeError(f"sdist has no concrete file under {prefix}")
        env_member = files_by_inner_path["src/sourcepack/examples/demo_repo/.env"]
        env_file = tf.extractfile(env_member)
        if env_file is None:
            raise ReleaseSmokeError("unable to read sdist demo .env")
        env_text = _decode_member("src/sourcepack/examples/demo_repo/.env", env_file.read())
        if DEMO_ENV_MARKER not in env_text:
            raise ReleaseSmokeError("sdist demo .env does not contain the required placeholder marker")
        for name, member in sorted(files_by_inner_path.items()):
            if any(name.startswith(prefix) for prefix in SDIST_DEMO_SCAN_PREFIXES):
                extracted = tf.extractfile(member)
                if extracted is None:
                    raise ReleaseSmokeError(f"unable to read sdist release asset {name}")
                _check_forbidden_text(name, _decode_member(name, extracted.read()))


def _venv_paths(env: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        return env / "Scripts" / "python.exe", env / "Scripts" / "sourcepack.exe"
    return env / "bin" / "python", env / "bin" / "sourcepack"


def smoke_installed_artifact(artifact: Path, version: str, name: str, work: Path) -> None:
    env = work / f"venv_{name}"
    venv.EnvBuilder(with_pip=True).create(env)
    python, sourcepack = _venv_paths(env)
    run([str(python), "-m", "pip", "install", "--no-cache-dir", str(artifact)], work)
    version_cp = run([str(sourcepack), "--version"], work)
    if version_cp.stdout.strip() != version:
        raise ReleaseSmokeError(f"{name} sourcepack --version printed {version_cp.stdout.strip()!r}, expected {version!r}")
    doctor_cp = run([str(sourcepack), "doctor"], work)
    if "Status: READY" not in doctor_cp.stdout:
        raise ReleaseSmokeError(f"{name} sourcepack doctor did not report Status: READY")
    demo_cp = run([str(sourcepack), "demo"], work)
    if MISSING_ASSETS_ERROR in demo_cp.stdout:
        raise ReleaseSmokeError(f"{name} sourcepack demo printed the old missing-assets error")


def main() -> int:
    try:
        build_clean_artifacts()
        version, wheel, sdist = verify_expected_artifacts(DIST)
        inspect_wheel_contents(wheel)
        print(f"wheel contents inspection passed: {wheel.name}")
        inspect_sdist_contents(sdist)
        print(f"sdist contents inspection passed: {sdist.name}")
        with tempfile.TemporaryDirectory(prefix="sourcepack_release_smoke_install_") as td:
            work = Path(td)
            smoke_installed_artifact(wheel, version, "wheel", work)
            print("fresh wheel install smoke passed")
            smoke_installed_artifact(sdist, version, "sdist", work)
            print("fresh sdist install smoke passed")
    except ReleaseSmokeError as exc:
        print(f"release smoke failed: {exc}", file=sys.stderr)
        return 1
    print("release smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
