
import threading
from unittest.mock import MagicMock, patch

import rarfile

from core.password_checker import PasswordChecker


def create_checker(tmp_path):
    """Create a checker without starting its background thread."""
    archive = tmp_path / "test.rar"
    wordlist = tmp_path / "passwords.txt"
    unrar = tmp_path / "UnRAR.exe"

    archive.write_bytes(b"fake archive")
    wordlist.write_bytes(b"password123\nadmin\n")
    unrar.write_bytes(b"fake executable")

    return PasswordChecker(
        archive_path=str(archive),
        wordlist_path=str(wordlist),
        unrar_path=str(unrar),
    )


class TestDecodePassword:
    def test_decodes_utf8_password(self):
        assert PasswordChecker.decode_password(b"hello123\n") == "hello123"

    def test_decodes_utf8_bom(self):
        assert PasswordChecker.decode_password(
            b"\xef\xbb\xbfhello\n"
        ) == "hello"

    def test_decodes_cyrillic_password(self):
        password = "пароль123"
        raw = password.encode("utf-8") + b"\n"

        assert PasswordChecker.decode_password(raw) == password

    def test_removes_windows_line_ending(self):
        assert PasswordChecker.decode_password(b"admin\r\n") == "admin"

    def test_preserves_spaces_in_password(self):
        assert PasswordChecker.decode_password(
            b" my password \n"
        ) == " my password "

    def test_empty_line_returns_empty_string(self):
        assert PasswordChecker.decode_password(b"\n") == ""


class TestCountWordlist:
    def test_counts_lines(self, tmp_path):
        checker = create_checker(tmp_path)

        checker.wordlist_path = str(tmp_path / "words.txt")
        (tmp_path / "words.txt").write_bytes(b"one\ntwo\nthree\n")

        assert checker.count_wordlist() == 3

    def test_counts_last_line_without_newline(self, tmp_path):
        checker = create_checker(tmp_path)

        checker.wordlist_path = str(tmp_path / "words.txt")
        (tmp_path / "words.txt").write_bytes(b"one\ntwo")

        assert checker.count_wordlist() == 2

    def test_empty_wordlist_has_zero_lines(self, tmp_path):
        checker = create_checker(tmp_path)

        checker.wordlist_path = str(tmp_path / "words.txt")
        (tmp_path / "words.txt").write_bytes(b"")

        assert checker.count_wordlist() == 0

    def test_missing_wordlist_raises_error(self, tmp_path):
        checker = create_checker(tmp_path)
        checker.wordlist_path = str(tmp_path / "missing.txt")

        try:
            checker.count_wordlist()
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("Expected FileNotFoundError")


class TestPasswordCheckerControls:
    def test_checker_starts_unpaused(self, tmp_path):
        checker = create_checker(tmp_path)

        assert checker.pause_event.is_set()

    def test_pause_blocks_event(self, tmp_path):
        checker = create_checker(tmp_path)

        checker.pause()

        assert not checker.pause_event.is_set()

    def test_resume_sets_event(self, tmp_path):
        checker = create_checker(tmp_path)

        checker.pause()
        checker.resume()

        assert checker.pause_event.is_set()

    def test_stop_requests_stop_and_unpauses(self, tmp_path):
        checker = create_checker(tmp_path)

        checker.pause()
        checker.stop()

        assert checker.stop_requested is True
        assert checker.pause_event.is_set()

    def test_wait_if_paused_returns_false_after_stop(self, tmp_path):
        checker = create_checker(tmp_path)

        checker.stop()

        assert checker.wait_if_paused() is False


class TestQuickPasswordCheck:
    def test_returns_success_when_file_is_readable(self, tmp_path):
        checker = create_checker(tmp_path)

        fake_info = MagicMock()
        fake_info.filename = "document.txt"
        fake_info.file_size = 100
        fake_info.isdir.return_value = False

        fake_file = MagicMock()
        fake_file.read.return_value = b"test data"

        fake_archive = MagicMock()
        fake_archive.__enter__.return_value = fake_archive
        fake_archive.__exit__.return_value = False
        fake_archive.infolist.return_value = [fake_info]
        fake_archive.open.return_value.__enter__.return_value = fake_file

        with patch(
            "core.password_checker.rarfile.RarFile",
            return_value=fake_archive,
        ):
            ok, usable, error = checker.rarfile_quick_test("correct")

        assert ok is True
        assert usable is True
        assert error == ""

    def test_returns_error_for_bad_archive(self, tmp_path):
        checker = create_checker(tmp_path)

        with patch(
            "core.password_checker.rarfile.RarFile",
            side_effect=rarfile.BadRarFile("invalid archive"),
        ):
            ok, usable, error = checker.rarfile_quick_test("password")

        assert ok is False
        assert usable is False
        assert error == "Corrupted or unsupported RAR archive"

    def test_returns_error_for_wrong_password(self, tmp_path):
        checker = create_checker(tmp_path)

        with patch(
            "core.password_checker.rarfile.RarFile",
            side_effect=rarfile.RarWrongPassword("wrong password"),
        ):
            ok, usable, error = checker.rarfile_quick_test("wrong")

        assert ok is False
        assert usable is False
        assert error == "Incorrect password"

    def test_returns_error_when_archive_has_no_files(self, tmp_path):
        checker = create_checker(tmp_path)

        fake_archive = MagicMock()
        fake_archive.__enter__.return_value = fake_archive
        fake_archive.__exit__.return_value = False
        fake_archive.infolist.return_value = []

        with patch(
            "core.password_checker.rarfile.RarFile",
            return_value=fake_archive,
        ):
            ok, usable, error = checker.rarfile_quick_test("password")

        assert ok is False
        assert usable is False
        assert error == "RAR returned no file list"
