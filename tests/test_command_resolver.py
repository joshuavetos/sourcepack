from sourcepack.commands import resolve_command


def test_npm_script_missing_and_present(tmp_path):
    (tmp_path/"package.json").write_text('{"scripts":{}}')
    assert resolve_command(tmp_path, "npm run dev").reason_code == "unsupported_command"
    (tmp_path/"package.json").write_text('{"scripts":{"dev":"vite"}}')
    assert resolve_command(tmp_path, "npm run dev").verdict == "PASS"


def test_same_patch_script_addition_warns(tmp_path):
    assert resolve_command(tmp_path, "npm run dev", added_manifests={"package.json":'{"scripts":{"dev":"vite"}}'}).reason_code == "declared_command"


def test_compose_support(tmp_path):
    assert resolve_command(tmp_path, "docker compose up").reason_code == "unsupported_command"
    (tmp_path/"compose.yml").write_text("services: {}")
    assert resolve_command(tmp_path, "docker compose up").verdict == "PASS"


def test_makefile_target(tmp_path):
    (tmp_path/"Makefile").write_text("test:\n\tpytest\n")
    assert resolve_command(tmp_path, "make test").verdict == "PASS"
    assert resolve_command(tmp_path, "make missing").reason_code == "unsupported_command"


def test_justfile_taskfile_detected(tmp_path):
    (tmp_path/"justfile").write_text("test:\n  pytest\n")
    assert resolve_command(tmp_path, "just test").verdict == "PASS"
    (tmp_path/"Taskfile.yml").write_text("tasks:\n  build:\n    cmds: [echo ok]\n")
    assert resolve_command(tmp_path, "task build").verdict == "PASS"


def test_tox_env_present_and_dynamic_inconclusive(tmp_path):
    (tmp_path/"tox.ini").write_text("[tox]\nenvlist = py311\n")
    assert resolve_command(tmp_path, "tox -e py311").verdict == "PASS"
    (tmp_path/"tox.ini").write_text("[tox]\nenvlist = py{310,311}\n")
    assert resolve_command(tmp_path, "tox -e py311").reason_code == "command_check_inconclusive"


def test_unsupported_parser_and_path_safety(tmp_path):
    assert resolve_command(tmp_path, "unknown thing").reason_code == "command_check_inconclusive"
    assert resolve_command(tmp_path, "make ../../x").reason_code in {"command_manifest_missing", "unsupported_command"}
