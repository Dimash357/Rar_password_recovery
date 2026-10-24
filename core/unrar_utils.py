
import os
import sys
from pathlib import Path


def shutil_which(name):
    path_env = os.environ.get("PATH", "")

    for directory in path_env.split(os.pathsep):
        if not directory:
            continue

        candidate = Path(directory) / name

        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            pass

    return None


def find_unrar():
    local_unrar = Path(sys.executable).resolve().parent / "UnRAR.exe"

    if local_unrar.is_file():
        return local_unrar

    script_unrar = Path(__file__).resolve().parent.parent / "UnRAR.exe"

    if script_unrar.is_file():
        return script_unrar

    possible_paths = [
        Path(os.environ.get("ProgramFiles", "")) / "WinRAR" / "UnRAR.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "WinRAR" / "UnRAR.exe",
        Path(os.environ.get("ProgramW6432", "")) / "WinRAR" / "UnRAR.exe",
    ]

    for path in possible_paths:
        if path.is_file():
            return path

    for folder in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(folder) / "UnRAR.exe"

        if path.is_file():
            return path

    return None
