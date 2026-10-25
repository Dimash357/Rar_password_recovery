
import os
import sys
from pathlib import Path
from unittest.mock import patch

from core import unrar_utils


def create_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


class TestShutilWhich:
    def test_finds_executable_in_path(self, tmp_path):
        executable = create_file(tmp_path / "UnRAR.exe")

        with patch.dict(os.environ, {"PATH": str(tmp_path)}):
            result = unrar_utils.shutil_which("UnRAR.exe")

        assert result == str(executable)

    def test_returns_none_when_file_not_found(self, tmp_path):
        with patch.dict(os.environ, {"PATH": str(tmp_path)}):
            result = unrar_utils.shutil_which("missing.exe")

        assert result is None

    def test_skips_empty_path_entries(self, tmp_path):
        executable = create_file(tmp_path / "UnRAR.exe")
        path_value = os.pathsep + str(tmp_path) + os.pathsep

        with patch.dict(os.environ, {"PATH": path_value}):
            result = unrar_utils.shutil_which("UnRAR.exe")

        assert result == str(executable)

    def test_ignores_directories_with_same_name(self, tmp_path):
        (tmp_path / "UnRAR.exe").mkdir()

        with patch.dict(os.environ, {"PATH": str(tmp_path)}):
            result = unrar_utils.shutil_which("UnRAR.exe")

        assert result is None


class TestFindUnrar:
    def test_finds_unrar_next_to_python_executable(self, tmp_path):
        executable = create_file(tmp_path / "python.exe")
        unrar = create_file(tmp_path / "UnRAR.exe")

        with (
            patch.object(sys, "executable", str(executable)),
            patch.object(unrar_utils, "__file__", str(tmp_path / "core" / "unrar_utils.py")),
            patch.dict(os.environ, {"PATH": ""}),
        ):
            # Ensure the script-relative location does not exist.
            result = unrar_utils.find_unrar()

        assert result == unrar

    def test_finds_unrar_next_to_project_script(self, tmp_path):
        project_dir = tmp_path / "project"
        core_dir = project_dir / "core"
        core_dir.mkdir(parents=True)

        unrar = create_file(project_dir / "UnRAR.exe")
        fake_python = tmp_path / "python.exe"

        with (
            patch.object(sys, "executable", str(fake_python)),
            patch.object(
                unrar_utils,
                "__file__",
                str(core_dir / "unrar_utils.py"),
            ),
            patch.dict(os.environ, {"PATH": ""}),
        ):
            result = unrar_utils.find_unrar()

        assert result == unrar

    def test_finds_unrar_in_program_files(self, tmp_path):
        program_files = tmp_path / "ProgramFiles"
        unrar = create_file(program_files / "WinRAR" / "UnRAR.exe")

        with (
            patch.object(
                sys,
                "executable",
                str(tmp_path / "python.exe"),
            ),
            patch.object(
                unrar_utils,
                "__file__",
                str(tmp_path / "project" / "core" / "unrar_utils.py"),
            ),
            patch.dict(
                os.environ,
                {
                    "PATH": "",
                    "ProgramFiles": str(program_files),
                    "ProgramFiles(x86)": "",
                    "ProgramW6432": "",
                },
            ),
        ):
            result = unrar_utils.find_unrar()

        assert result == unrar

    def test_finds_unrar_in_path_as_fallback(self, tmp_path):
        executable_dir = tmp_path / "bin"
        unrar = create_file(executable_dir / "UnRAR.exe")

        with (
            patch.object(
                sys,
                "executable",
                str(tmp_path / "python.exe"),
            ),
            patch.object(
                unrar_utils,
                "__file__",
                str(tmp_path / "project" / "core" / "unrar_utils.py"),
            ),
            patch.dict(
                os.environ,
                {
                    "PATH": str(executable_dir),
                    "ProgramFiles": "",
                    "ProgramFiles(x86)": "",
                    "ProgramW6432": "",
                },
            ),
        ):
            result = unrar_utils.find_unrar()

        assert result == unrar

    def test_returns_none_when_unrar_is_not_found(self, tmp_path):
        with (
            patch(
                "core.unrar_utils.Path.is_file",
                return_value=False,
            ),
            patch.dict(
                os.environ,
                {
                    "PATH": "",
                    "ProgramFiles": "",
                    "ProgramFiles(x86)": "",
                    "ProgramW6432": "",
                },
            ),
        ):
            result = unrar_utils.find_unrar()

        assert result is None
