import subprocess
import threading
from pathlib import Path

import rarfile
from PyQt6.QtCore import QThread, pyqtSignal


class PasswordChecker(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    found_signal = pyqtSignal(str)
    stats_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        archive_path,
        wordlist_path,
        unrar_path,
        verification_mode="quick",
        skip_duplicates=True,
    ):
        super().__init__()

        self.archive_path = archive_path
        self.wordlist_path = wordlist_path
        self.unrar_path = unrar_path
        self.verification_mode = verification_mode
        self.skip_duplicates = skip_duplicates

        self.stop_requested = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.tested = 0
        self.skipped = 0

    def stop(self):
        self.stop_requested = True
        self.pause_event.set()

    def pause(self):
        self.pause_event.clear()

    def resume(self):
        self.pause_event.set()

    def wait_if_paused(self):
        while not self.pause_event.wait(timeout=0.2):
            if self.stop_requested:
                return

        return not self.stop_requested

    def log(self, text):
        self.log_signal.emit(text)

    def unrar_test_password(self, password):
        try:
            process = subprocess.Popen(
                [
                    self.unrar_path,
                    "t",
                    "-y",
                    f"-p{password}",
                    self.archive_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="cp866",
                errors="replace",
                shell=False,
            )

            while process.poll() is None:
                if self.stop_requested:
                    process.terminate()

                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()

                    return False, False

                process.stdout.readline()

            return process.returncode == 0, True

        except Exception as e:
            self.log(f"UnRAR error: {e}")
            return False, True

    def rarfile_quick_test(self, password):
        try:
            with rarfile.RarFile(self.archive_path) as archive:
                archive.setpassword(password)
                infos = archive.infolist()

                if not infos:
                    return False, False, "RAR returned no file list"

                files = [info for info in infos if not info.isdir()]

                if not files:
                    return False, False, "The archive contains no files"

                files.sort(
                    key=lambda info: getattr(info, "file_size", 0) or 0
                )

                test_info = files[0]
                self.log(f"Testing: {test_info.filename}")

                with archive.open(test_info) as file:
                    file.read(4096)

            return True, True, ""

        except rarfile.BadRarFile:
            return False, False, "Corrupted or unsupported RAR archive"
        except rarfile.PasswordRequired:
            return False, False, "Password required"
        except rarfile.RarWrongPassword:
            return False, False, "Incorrect password"
        except rarfile.NoCrypto:
            return False, False, "RAR encryption is not supported"
        except Exception as e:
            return False, False, str(e)

    def rarfile_full_test(self, password):
        try:
            with rarfile.RarFile(self.archive_path) as archive:
                archive.setpassword(password)
                infos = archive.infolist()
                files = [info for info in infos if not info.isdir()]

                if not files:
                    return False, "The archive contains no files"

                for index, info in enumerate(files, start=1):
                    if self.stop_requested:
                        return False, "STOP"

                    self.log(
                        f"Checking {index}/{len(files)}: {info.filename}"
                    )

                    with archive.open(info) as file:
                        while True:
                            if not self.wait_if_paused():
                                return False, "STOP"

                            if self.stop_requested:
                                return False, "STOP"

                            chunk = file.read(1024 * 1024)

                            if not chunk:
                                break

            return True, ""

        except rarfile.RarWrongPassword:
            return False, "Incorrect password"
        except rarfile.PasswordRequired:
            return False, "Password required"
        except rarfile.BadRarFile:
            return False, "Corrupted RAR archive"
        except rarfile.NoCrypto:
            return False, "Encryption is not supported"
        except Exception as e:
            return False, str(e)

    def count_wordlist(self):
        count = 0

        with open(self.wordlist_path, "rb") as file:
            while True:
                chunk = file.read(1024 * 1024)

                if not chunk:
                    break

                count += chunk.count(b"\n")

                if not chunk.endswith(b"\n"):
                    count += 1

        return count

    @staticmethod
    def decode_password(raw_line):
        for encoding in (
            "utf-8-sig",
            "utf-8",
            "cp1251",
            "cp866",
            "latin-1",
        ):
            try:
                return raw_line.decode(encoding).rstrip("\r\n")
            except UnicodeDecodeError:
                continue

        return raw_line.decode("utf-8", errors="replace").rstrip("\r\n")

    def run(self):
        try:
            archive = Path(self.archive_path)
            wordlist = Path(self.wordlist_path)
            unrar = Path(self.unrar_path)

            if not archive.is_file():
                self.error_signal.emit("RAR archive not found.")
                return

            if archive.stat().st_size == 0:
                self.error_signal.emit("RAR archive is empty.")
                return

            if not wordlist.is_file():
                self.error_signal.emit("Wordlist not found.")
                return

            if not unrar.is_file():
                self.error_signal.emit("UnRAR.exe not found.")
                return

            rarfile.UNRAR_TOOL = str(unrar)

            try:
                with rarfile.RarFile(str(archive)) as rar:
                    if not rar.needs_password():
                        self.error_signal.emit(
                            "The RAR archive is not password-protected."
                        )
                        return

                self.log("✓ Archive is password-protected.")

            except Exception as e:
                self.error_signal.emit(
                    f"Could not determine archive protection: {e}"
                )
                return

            try:
                result = subprocess.run(
                    [
                        str(unrar),
                        "l",
                        "-y",
                        str(archive),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="cp866",
                    errors="replace",
                    shell=False,
                    timeout=30,
                )

                if result.returncode == 0:
                    self.log("✓ Archive recognized successfully.")
                else:
                    self.log(
                        "Warning: UnRAR returned exit code "
                        f"{result.returncode}."
                    )

            except subprocess.TimeoutExpired:
                self.log("Warning: UnRAR verification took too long.")

            total = self.count_wordlist()

            if total == 0:
                self.error_signal.emit("Wordlist is empty.")
                return

            self.log(f"Wordlist: {total:,} lines")

            seen = set()

            with open(self.wordlist_path, "rb", buffering=1024 * 1024) as file:
                for raw_line in file:
                    if not self.wait_if_paused():
                        self.finished_signal.emit(
                            "Recovery stopped."
                        )
                        return

                    if self.stop_requested:
                        self.finished_signal.emit("Recovery stopped.")
                        return

                    password = self.decode_password(raw_line)

                    if not password:
                        self.skipped += 1
                        continue

                    if self.skip_duplicates and password in seen:
                        self.skipped += 1
                        continue

                    seen.add(password)
                    self.tested += 1

                    current = self.tested + self.skipped
                    progress = int(current / total * 100)

                    self.progress_signal.emit(min(100, progress))
                    self.stats_signal.emit(
                        f"{self.tested:,} checked  •  "
                        f"{self.skipped:,} skipped  •  "
                        f"{total:,} lines"
                    )

                    if self.verification_mode == "quick":
                        ok, usable, error = self.rarfile_quick_test(password)

                        if ok:
                            self.found_signal.emit(password)
                            self.finished_signal.emit("Password found.")
                            return

                        if not usable:
                            unrar_ok, can_continue = (
                                self.unrar_test_password(password)
                            )

                            if unrar_ok:
                                self.found_signal.emit(password)
                                self.finished_signal.emit("Password found.")
                                return

                    else:
                        ok, error = self.rarfile_full_test(password)

                        if ok:
                            self.found_signal.emit(password)
                            self.finished_signal.emit("Password found.")
                            return

                        if error == "STOP":
                            self.finished_signal.emit("Recovery stopped.")
                            return

            self.progress_signal.emit(100)
            self.finished_signal.emit("Password not found in the wordlist.")

        except Exception as e:
            self.error_signal.emit(f"{type(e).__name__}: {e}")
