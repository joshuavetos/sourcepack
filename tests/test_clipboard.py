import subprocess
import shutil
from unittest.mock import patch
from sourcepack.cli import copy_to_clipboard

def test_copy_to_clipboard_does_not_execute_shell_commands():
    # We want to ensure that `copy_to_clipboard` safely passes text to the
    # clipboard executables via stdin without invoking a shell.
    # We'll mock `shutil.which` to pretend our dummy executable is the clipboard,
    # and mock `subprocess.run` to verify its arguments.

    with patch("platform.system", return_value="Linux"), \
         patch("shutil.which", return_value="/usr/bin/dummy_clip"), \
         patch("subprocess.run") as mock_run:

        mock_run.return_value.returncode = 0

        # This string looks like shell injection
        malicious_input = "$(whoami); touch /tmp/pwned"

        # The function should swallow the return value and pass the string to the command's stdin
        # and not raise an exception or attempt to execute it in a shell.
        copy_to_clipboard(malicious_input)

        # Verify it was called with shell=False (default or explicit)
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args

        # The command should be a list, which prevents shell execution when shell=False
        assert isinstance(args[0], list)
        assert kwargs.get("shell", False) is False
        assert kwargs.get("input") == malicious_input

        # Check that standard streams are redirected as intended
        assert kwargs.get("stdout") == subprocess.DEVNULL
        assert kwargs.get("stderr") == subprocess.DEVNULL
