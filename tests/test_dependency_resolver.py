from sourcepack.dependencies import resolve_js_import, resolve_python_import, unsupported_ecosystems


def test_python_stdlib_local_undeclared_declared(tmp_path):
    assert resolve_python_import(tmp_path, "json").verdict == "PASS"
    (tmp_path/"localmod.py").write_text("x=1")
    assert resolve_python_import(tmp_path, "localmod").verdict == "PASS"
    assert resolve_python_import(tmp_path, "fastapi").reason_code == "unsupported_dependency"
    (tmp_path/"pyproject.toml").write_text("[project]\ndependencies=['fastapi>=0.100']\n")
    assert resolve_python_import(tmp_path, "fastapi").verdict == "PASS"


def test_python_same_patch_and_optional_scope(tmp_path):
    assert resolve_python_import(tmp_path, "fastapi", added_dependencies={"fastapi"}).reason_code == "declared_dependency"
    (tmp_path/"pyproject.toml").write_text("[project.optional-dependencies]\nweb=['fastapi']\n")
    assert resolve_python_import(tmp_path, "fastapi").reason_code == "dependency_scope_review"


def test_js_relative_undeclared_declared_dev_and_scoped(tmp_path):
    assert resolve_js_import(tmp_path, "./lib.js").verdict == "PASS"
    (tmp_path/"package.json").write_text("{}")
    assert resolve_js_import(tmp_path, "react").reason_code == "unsupported_dependency"
    (tmp_path/"package.json").write_text('{"dependencies":{"@scope/pkg":"1","react":"1"}}')
    assert resolve_js_import(tmp_path, "@scope/pkg/sub").verdict == "PASS"
    assert resolve_js_import(tmp_path, "react").verdict == "PASS"
    (tmp_path/"package.json").write_text('{"devDependencies":{"react":"1"}}')
    assert resolve_js_import(tmp_path, "react").reason_code == "dependency_scope_review"


def test_ts_alias_inconclusive_and_unsupported_ecosystem(tmp_path):
    (tmp_path/"tsconfig.json").write_text('{"compilerOptions":{"paths":{"@/*":["src/*"]}}}')
    assert resolve_js_import(tmp_path, "@/lib").reason_code == "js_alias_uncertain"
    (tmp_path/"Cargo.toml").write_text("[package]\nname='x'\n")
    assert unsupported_ecosystems(tmp_path)[0].reason_code == "unsupported_ecosystem"
