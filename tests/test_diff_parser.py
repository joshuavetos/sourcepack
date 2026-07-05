from sourcepack.diff_parser import PatchFileChange, normalize_diff_path, parse_unified_diff


def _only_change(diff_text: str) -> PatchFileChange:
    changes = parse_unified_diff(diff_text)
    assert len(changes) == 1
    return changes[0]


def test_normal_modified_file_shape_tracks_path_operation_and_added_lines():
    change = _only_change(
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1,2 @@
 old = 1
+new = 2
"""
    )

    assert change == PatchFileChange(
        path="app.py",
        old_path="app.py",
        new_file=False,
        deleted_file=False,
        added_lines=["new = 2"],
        diff_lines=["@@ -1 +1,2 @@", " old = 1", "+new = 2"],
        unsafe_path=False,
        operation="modify",
    )


def test_new_file_shape_tracks_new_file_flag_normalized_path_and_added_lines():
    change = _only_change(
        """diff --git a/docs/new.md b/docs/new.md
new file mode 100644
--- /dev/null
+++ b/docs/new.md
@@ -0,0 +1,2 @@
+hello
+world
"""
    )

    assert change.path == "docs/new.md"
    assert change.old_path is None
    assert change.new_file is True
    assert change.deleted_file is False
    assert change.operation == "modify"
    assert change.added_lines == ["hello", "world"]
    assert change.unsafe_path is False


def test_deleted_file_shape_tracks_deleted_file_flag_and_normalized_path():
    change = _only_change(
        """diff --git a/docs/old.md b/docs/old.md
deleted file mode 100644
--- a/docs/old.md
+++ /dev/null
@@ -1 +0,0 @@
-goodbye
"""
    )

    assert change.path == "docs/old.md"
    assert change.old_path == "docs/old.md"
    assert change.new_file is False
    assert change.deleted_file is True
    assert change.operation == "modify"
    assert change.added_lines == []
    assert change.unsafe_path is False


def test_rename_shape_tracks_operation_old_path_and_new_path():
    change = _only_change(
        """diff --git a/old.py b/new.py
similarity index 100%
rename from old.py
rename to new.py
"""
    )

    assert change.path == "new.py"
    assert change.old_path == "old.py"
    assert change.operation == "rename"
    assert change.new_file is False
    assert change.deleted_file is False
    assert change.added_lines == []
    assert change.diff_lines == []
    assert change.unsafe_path is False


def test_copy_shape_tracks_operation_old_path_new_path_and_new_file_flag():
    change = _only_change(
        """diff --git a/source.py b/copy.py
similarity index 100%
copy from source.py
copy to copy.py
"""
    )

    assert change.path == "copy.py"
    assert change.old_path == "source.py"
    assert change.operation == "copy"
    assert change.new_file is True
    assert change.deleted_file is False
    assert change.added_lines == []
    assert change.diff_lines == []
    assert change.unsafe_path is False


def test_binary_diff_has_no_low_level_file_change_representation():
    changes = parse_unified_diff(
        """diff --git a/image.png b/image.png
Binary files a/image.png and b/image.png differ
"""
    )

    assert changes == []


def test_malformed_diff_returns_malformed_unsafe_sentinel():
    changes = parse_unified_diff(
        """@@ -1 +1 @@
+orphaned hunk
"""
    )

    assert changes == [
        PatchFileChange(
            path="",
            old_path=None,
            unsafe_path=True,
            operation="malformed",
        )
    ]


def test_unsafe_absolute_path_is_marked_unsafe_and_adds_malformed_sentinel():
    changes = parse_unified_diff(
        """diff --git a//tmp/outside.txt b//tmp/outside.txt
--- a//tmp/outside.txt
+++ b//tmp/outside.txt
@@ -1 +1 @@
-old
+new
"""
    )

    assert changes[0].path == "/tmp/outside.txt"
    assert changes[0].old_path == "/tmp/outside.txt"
    assert changes[0].unsafe_path is True
    assert changes[0].operation == "modify"
    assert changes[-1].operation == "malformed"
    assert changes[-1].unsafe_path is True


def test_unsafe_posix_traversal_path_is_marked_unsafe_and_normalized():
    changes = parse_unified_diff(
        """diff --git a/../outside.txt b/../outside.txt
--- a/../outside.txt
+++ b/../outside.txt
@@ -1 +1 @@
-old
+new
"""
    )

    assert changes[0].path == "outside.txt"
    assert changes[0].old_path == "outside.txt"
    assert changes[0].unsafe_path is True
    assert changes[-1].operation == "malformed"
    assert changes[-1].unsafe_path is True


def test_unsafe_windows_traversal_path_is_marked_unsafe_and_normalized():
    changes = parse_unified_diff(
        """diff --git a/..\\outside.txt b/..\\outside.txt
--- a/..\\outside.txt
+++ b/..\\outside.txt
@@ -1 +1 @@
-old
+new
"""
    )

    assert changes[0].path == "outside.txt"
    assert changes[0].old_path == "outside.txt"
    assert changes[0].unsafe_path is True
    assert changes[-1].operation == "malformed"
    assert changes[-1].unsafe_path is True


def test_tab_suffixed_diff_path_keeps_only_real_path():
    change = _only_change(
        """diff --git a/file.py b/file.py
--- a/file.py	2026-01-01
+++ b/file.py	2026-01-01
@@ -1 +1 @@
-old
+new
"""
    )

    assert change.path == "file.py"
    assert change.old_path == "file.py"
    assert change.added_lines == ["new"]
    assert change.unsafe_path is False


def test_normalize_diff_path_marks_windows_style_traversal_unsafe():
    assert normalize_diff_path(r"..\outside.txt") == ("outside.txt", True)
