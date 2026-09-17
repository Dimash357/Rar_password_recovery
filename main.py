import os
import sys
import subprocess
from pathlib import Path

import rarfile

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QComboBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# ============================================================
# UNRAR
# ============================================================

def find_unrar():
    """Ищет UnRAR.exe в стандартных местах и PATH."""

    candidates = []

    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    program_w6432 = os.environ.get("ProgramW6432")

    if program_files:
        candidates.append(
            Path(program_files) / "WinRAR" / "UnRAR.exe"
        )

    if program_files_x86:
        candidates.append(
            Path(program_files_x86) / "WinRAR" / "UnRAR.exe"
        )

    if program_w6432:
        candidates.append(
            Path(program_w6432) / "WinRAR" / "UnRAR.exe"
        )

    # PATH
    path_unrar = shutil_which("UnRAR.exe")
    if path_unrar:
        candidates.append(Path(path_unrar))

    path_unrar_lower = shutil_which("unrar")
    if path_unrar_lower:
        candidates.append(Path(path_unrar_lower))

    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            pass

    return None


def shutil_which(name):
    """Небольшой аналог shutil.which без отдельного импорта."""
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


# ============================================================
# WORKER
# ============================================================

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
        parent=None,
    ):
        super().__init__(parent)

        self.archive_path = archive_path
        self.wordlist_path = wordlist_path
        self.unrar_path = unrar_path
        self.verification_mode = verification_mode
        self.skip_duplicates = skip_duplicates

        self.stop_requested = False

        self.tested = 0
        self.skipped = 0

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    def stop(self):
        self.stop_requested = True

    # --------------------------------------------------------
    # LOG
    # --------------------------------------------------------

    def log(self, text):
        self.log_signal.emit(text)

    # --------------------------------------------------------
    # UNRAR TEST
    # --------------------------------------------------------

    def unrar_test_password(self, password):
        """
        Резервная проверка пароля через UnRAR.

        t = test archive
        -pPASSWORD = передать пароль
        -y = yes to all
        """

        if self.stop_requested:
            return False, False

        try:
            # Защищаем пароль от проблем с аргументами subprocess:
            # передаём аргументы списком, shell=False.
            command = [
                self.unrar_path,
                "t",
                "-y",
                f"-p{password}",
                self.archive_path,
            ]

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="cp866",
                errors="replace",
                shell=False,
            )

            output_lines = []

            while True:
                if self.stop_requested:
                    try:
                        process.terminate()
                    except Exception:
                        pass

                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        try:
                            process.kill()
                        except Exception:
                            pass

                    return False, False

                line = process.stdout.readline()

                if not line:
                    if process.poll() is not None:
                        break

                    continue

                line = line.strip()

                if line:
                    output_lines.append(line)

            return_code = process.wait()

            output = "\n".join(output_lines)

            # UnRAR возвращает 0 при успешной проверке.
            if return_code == 0:
                return True, True

            # Если это просто неправильный пароль,
            # продолжаем проверку.
            return False, True

        except Exception as e:
            self.log(f"UnRAR ошибка: {e}")
            return False, True

    # --------------------------------------------------------
    # RARFILE QUICK TEST
    # --------------------------------------------------------

    def rarfile_quick_test(self, password):
        """
        Быстрая проверка через rarfile.

        Важный момент версии 2.1:
        password устанавливается ДО infolist().

        Это позволяет работать с архивами,
        где зашифрованы заголовки.
        """

        try:
            with rarfile.RarFile(self.archive_path) as archive:
                archive.setpassword(password)

                try:
                    infos = archive.infolist()
                except Exception as e:
                    return False, False, str(e)

                if not infos:
                    return False, False, "RAR не вернул список файлов"

                files = [
                    info
                    for info in infos
                    if not info.is_dir()
                ]

                if not files:
                    return False, False, "В архиве только каталоги"

                files.sort(
                    key=lambda x: (
                        getattr(x, "file_size", 0) or 0
                    )
                )

                test_info = files[0]

                self.log(
                    f"Тестовый файл: {test_info.filename}"
                )

                with archive.open(test_info) as file:
                    data = file.read(4096)

                return True, True, ""

        except rarfile.BadRarFile:
            return False, False, "Повреждённый или неподдерживаемый RAR"

        except rarfile.PasswordRequired:
            return False, False, "Требуется пароль"

        except rarfile.RarWrongPassword:
            return False, False, "Неверный пароль"

        except rarfile.NoCrypto:
            return False, False, "Криптография RAR не поддерживается rarfile"

        except Exception as e:
            return False, False, str(e)

    # --------------------------------------------------------
    # RARFILE FULL TEST
    # --------------------------------------------------------

    def rarfile_full_test(self, password):
        """
        Полная проверка содержимого архива.
        Медленнее, но надёжнее quick режима.
        """

        try:
            with rarfile.RarFile(self.archive_path) as archive:

                archive.setpassword(password)

                infos = archive.infolist()

                files = [
                    info
                    for info in infos
                    if not info.is_dir()
                ]

                if not files:
                    return False, "В архиве нет обычных файлов"

                for index, info in enumerate(files, start=1):

                    if self.stop_requested:
                        return False, "STOP"

                    self.log(
                        f"Полная проверка: "
                        f"{index}/{len(files)} — {info.filename}"
                    )

                    with archive.open(info) as file:

                        while True:

                            if self.stop_requested:
                                return False, "STOP"

                            chunk = file.read(1024 * 1024)

                            if not chunk:
                                break

                return True, ""

        except rarfile.RarWrongPassword:
            return False, "Неверный пароль"

        except rarfile.PasswordRequired:
            return False, "Требуется пароль"

        except rarfile.BadRarFile:
            return False, "Повреждённый или неподдерживаемый RAR"

        except rarfile.NoCrypto:
            return False, "Криптография не поддерживается"

        except Exception as e:
            return False, str(e)

    # --------------------------------------------------------
    # COUNT WORDLIST
    # --------------------------------------------------------

    def count_wordlist(self):
        """
        Считает количество строк для progress bar.

        Используем бинарный режим — это быстрее
        и меньше зависит от кодировки.
        """

        count = 0

        with open(
            self.wordlist_path,
            "rb",
            buffering=1024 * 1024,
        ) as file:

            for _ in file:
                count += 1

        return count

    # --------------------------------------------------------
    # READ PASSWORD
    # --------------------------------------------------------

    @staticmethod
    def decode_password(raw_line):
        """
        Пытается прочитать строку wordlist.
        """

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

        return raw_line.decode(
            "utf-8",
            errors="replace",
        ).rstrip("\r\n")

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

    def run(self):

        try:
            # ------------------------------------------------
            # VALIDATION
            # ------------------------------------------------

            if self.stop_requested:
                self.finished_signal.emit(
                    "Проверка остановлена."
                )
                return

            archive = Path(self.archive_path)
            wordlist = Path(self.wordlist_path)
            unrar = Path(self.unrar_path)

            if not archive.exists():
                self.error_signal.emit(
                    "Архив не найден:\n\n"
                    f"{archive}"
                )
                return

            if not archive.is_file():
                self.error_signal.emit(
                    "Выбранный путь не является файлом."
                )
                return

            if archive.stat().st_size == 0:
                self.error_signal.emit(
                    "Файл архива пустой."
                )
                return

            if not wordlist.exists():
                self.error_signal.emit(
                    "Wordlist не найден:\n\n"
                    f"{wordlist}"
                )
                return

            if not wordlist.is_file():
                self.error_signal.emit(
                    "Выбранный wordlist не является файлом."
                )
                return

            if not unrar.exists():
                self.error_signal.emit(
                    "UnRAR.exe не найден:\n\n"
                    f"{unrar}"
                )
                return

            # ------------------------------------------------
            # RARFILE CONFIG
            # ------------------------------------------------

            rarfile.UNRAR_TOOL = str(unrar)

            self.log(
                f"Архив: {archive}"
            )

            self.log(
                f"Wordlist: {wordlist}"
            )

            self.log(
                f"UnRAR: {unrar}"
            )

            # ------------------------------------------------
            # BASIC ARCHIVE CHECK
            # ------------------------------------------------

            self.log("Проверка архива через UnRAR...")

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

                if result.returncode != 0:

                    self.log(
                        "UnRAR сообщил, что архив не удалось открыть."
                    )

                    self.log(result.stdout[-3000:])

                    # Не завершаем работу автоматически.
                    # Некоторые варианты RAR могут вести себя
                    # нестандартно при listing.
                    self.log(
                        "Продолжаем проверку паролей..."
                    )

                else:

                    self.log(
                        "Архив успешно распознан UnRAR."
                    )

            except subprocess.TimeoutExpired:
                self.log(
                    "Проверка списка заняла больше 30 секунд."
                )

            # ------------------------------------------------
            # WORDLIST COUNT
            # ------------------------------------------------

            self.log("Подсчёт строк wordlist...")

            total = self.count_wordlist()

            if total == 0:
                self.error_signal.emit(
                    "Wordlist пуст."
                )
                return

            self.log(
                f"Строк в wordlist: {total:,}"
            )

            # ------------------------------------------------
            # CHECK PASSWORDS
            # ------------------------------------------------

            seen = set()

            with open(
                wordlist,
                "rb",
                buffering=1024 * 1024,
            ) as file:

                for raw_line in file:

                    if self.stop_requested:
                        self.finished_signal.emit(
                            "Проверка остановлена пользователем."
                        )
                        return

                    password = self.decode_password(raw_line)

                    # Убираем только CR/LF.
                    # Пробелы внутри/по краям НЕ удаляем,
                    # потому что пробел может быть частью пароля.
                    if password == "":
                        self.skipped += 1
                        continue

                    # ------------------------------------------------
                    # DUPLICATES
                    # ------------------------------------------------

                    if self.skip_duplicates:

                        if password in seen:
                            self.skipped += 1
                            continue

                        seen.add(password)

                    # ------------------------------------------------
                    # STATS
                    # ------------------------------------------------

                    self.tested += 1

                    progress = int(
                        ((self.tested + self.skipped) / total) * 100
                    )

                    progress = max(
                        0,
                        min(100, progress)
                    )

                    self.progress_signal.emit(progress)

                    self.stats_signal.emit(
                        f"Проверено: {self.tested:,}    "
                        f"Пропущено: {self.skipped:,}    "
                        f"Всего строк: {total:,}"
                    )

                    self.log(
                        f"[{self.tested:,}] Проверка пароля"
                    )

                    # ------------------------------------------------
                    # QUICK MODE
                    # ------------------------------------------------

                    if self.verification_mode == "quick":

                        ok, usable, error = (
                            self.rarfile_quick_test(password)
                        )

                        if ok:
                            self.log(
                                "Пароль успешно подтверждён."
                            )

                            self.found_signal.emit(
                                password
                            )

                            self.finished_signal.emit(
                                "Пароль найден."
                            )

                            return

                        # rarfile иногда не может проверить конкретный
                        # архив. В таком случае используем UnRAR.
                        if not usable:

                            self.log(
                                f"rarfile: {error}"
                            )

                            unrar_ok, unrar_ran = (
                                self.unrar_test_password(
                                    password
                                )
                            )

                            if unrar_ok:

                                self.log(
                                    "Пароль подтверждён UnRAR."
                                )

                                self.found_signal.emit(
                                    password
                                )

                                self.finished_signal.emit(
                                    "Пароль найден."
                                )

                                return

                    # ------------------------------------------------
                    # FULL MODE
                    # ------------------------------------------------

                    else:

                        ok, error = (
                            self.rarfile_full_test(
                                password
                            )
                        )

                        if ok:

                            self.log(
                                "Полная проверка успешно завершена."
                            )

                            self.found_signal.emit(
                                password
                            )

                            self.finished_signal.emit(
                                "Пароль найден."
                            )

                            return

                        if error == "STOP":

                            self.finished_signal.emit(
                                "Проверка остановлена пользователем."
                            )

                            return

            # ------------------------------------------------
            # NOTHING FOUND
            # ------------------------------------------------

            self.progress_signal.emit(100)

            self.finished_signal.emit(
                "Проверка завершена. "
                "Подходящий пароль не найден."
            )

        except PermissionError as e:

            self.error_signal.emit(
                "Нет доступа к файлу:\n\n"
                f"{e}"
            )

        except UnicodeError as e:

            self.error_signal.emit(
                "Ошибка кодировки wordlist:\n\n"
                f"{e}"
            )

        except Exception as e:

            self.error_signal.emit(
                "Неожиданная ошибка:\n\n"
                f"{type(e).__name__}: {e}"
            )


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "RAR Password Recovery 2.1"
        )

        self.resize(900, 650)

        self.checker = None
        self.allow_close = False

        self.build_ui()

        self.detect_unrar()

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def build_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        # ----------------------------------------------------
        # ARCHIVE
        # ----------------------------------------------------

        archive_label = QLabel("RAR архив:")

        self.archive_edit = QLineEdit()

        archive_button = QPushButton("Выбрать...")
        archive_button.clicked.connect(
            self.select_archive
        )

        archive_row = QHBoxLayout()

        archive_row.addWidget(
            self.archive_edit
        )

        archive_row.addWidget(
            archive_button
        )

        layout.addWidget(archive_label)
        layout.addLayout(archive_row)

        # ----------------------------------------------------
        # WORDLIST
        # ----------------------------------------------------

        wordlist_label = QLabel("Wordlist:")

        self.wordlist_edit = QLineEdit()

        wordlist_button = QPushButton("Выбрать...")
        wordlist_button.clicked.connect(
            self.select_wordlist
        )

        wordlist_row = QHBoxLayout()

        wordlist_row.addWidget(
            self.wordlist_edit
        )

        wordlist_row.addWidget(
            wordlist_button
        )

        layout.addWidget(wordlist_label)
        layout.addLayout(wordlist_row)

        # ----------------------------------------------------
        # UNRAR
        # ----------------------------------------------------

        unrar_label = QLabel("UnRAR.exe:")

        self.unrar_edit = QLineEdit()

        unrar_button = QPushButton("Выбрать...")
        unrar_button.clicked.connect(
            self.select_unrar
        )

        unrar_row = QHBoxLayout()

        unrar_row.addWidget(
            self.unrar_edit
        )

        unrar_row.addWidget(
            unrar_button
        )

        layout.addWidget(unrar_label)
        layout.addLayout(unrar_row)

        # ----------------------------------------------------
        # VERIFICATION
        # ----------------------------------------------------

        verification_label = QLabel(
            "Режим проверки:"
        )

        self.verification_combo = QComboBox()

        self.verification_combo.addItem(
            "Быстрая проверка",
            "quick",
        )

        self.verification_combo.addItem(
            "Полная проверка",
            "full",
        )

        layout.addWidget(
            verification_label
        )

        layout.addWidget(
            self.verification_combo
        )

        # ----------------------------------------------------
        # DUPLICATES
        # ----------------------------------------------------

        self.skip_duplicates_button = QPushButton(
            "Пропускать дубликаты: ВКЛ"
        )

        self.skip_duplicates_button.setCheckable(
            True
        )

        self.skip_duplicates_button.setChecked(
            True
        )

        self.skip_duplicates_button.clicked.connect(
            self.toggle_duplicates
        )

        layout.addWidget(
            self.skip_duplicates_button
        )

        # ----------------------------------------------------
        # PROGRESS
        # ----------------------------------------------------

        self.progress = QProgressBar()

        self.progress.setRange(
            0,
            100,
        )

        self.progress.setValue(0)

        layout.addWidget(
            self.progress
        )

        # ----------------------------------------------------
        # STATS
        # ----------------------------------------------------

        self.stats_label = QLabel(
            "Проверено: 0    "
            "Пропущено: 0    "
            "Всего строк: 0"
        )

        layout.addWidget(
            self.stats_label
        )

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        buttons_row = QHBoxLayout()

        self.start_button = QPushButton(
            "Начать проверку"
        )

        self.stop_button = QPushButton(
            "Остановить"
        )

        self.stop_button.setEnabled(
            False
        )

        self.start_button.clicked.connect(
            self.start_check
        )

        self.stop_button.clicked.connect(
            self.stop_check
        )

        buttons_row.addWidget(
            self.start_button
        )

        buttons_row.addWidget(
            self.stop_button
        )

        layout.addLayout(
            buttons_row
        )

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        log_label = QLabel("Журнал:")

        layout.addWidget(
            log_label
        )

        self.log = QTextEdit()

        self.log.setReadOnly(
            True
        )

        layout.addWidget(
            self.log
        )

    # --------------------------------------------------------
    # UNRAR DETECTION
    # --------------------------------------------------------

    def detect_unrar(self):

        path = find_unrar()

        if path:

            self.unrar_edit.setText(
                path
            )

            self.write_log(
                f"Найден UnRAR.exe: {path}"
            )

        else:

            self.write_log(
                "UnRAR.exe автоматически не найден."
            )

    # --------------------------------------------------------
    # SELECT ARCHIVE
    # --------------------------------------------------------

    def select_archive(self):

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите RAR архив",
            "",
            (
                "RAR архивы "
                "(*.rar *.part*.rar *.r00 *.r01);;"
                "Все файлы (*)"
            ),
        )

        if file_path:

            self.archive_edit.setText(
                file_path
            )

    # --------------------------------------------------------
    # SELECT WORDLIST
    # --------------------------------------------------------

    def select_wordlist(self):

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите wordlist",
            "",
            "Текстовые файлы (*.txt *.lst *.dic);;"
            "Все файлы (*)",
        )

        if file_path:

            self.wordlist_edit.setText(
                file_path
            )

    # --------------------------------------------------------
    # SELECT UNRAR
    # --------------------------------------------------------

    def select_unrar(self):

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите UnRAR.exe",
            "",
            "UnRAR.exe (UnRAR.exe);;Все файлы (*)",
        )

        if file_path:

            self.unrar_edit.setText(
                file_path
            )

    def toggle_duplicates(self):

        if self.skip_duplicates_button.isChecked():

            self.skip_duplicates_button.setText(
                "Пропускать дубликаты: ВКЛ"
            )

        else:

            self.skip_duplicates_button.setText(
                "Пропускать дубликаты: ВЫКЛ"
            )

    def write_log(self, text):

        self.log.append(
            text
        )

        scrollbar = (
            self.log.verticalScrollBar()
        )

        scrollbar.setValue(
            scrollbar.maximum()
        )

    def start_check(self):

        archive = self.archive_edit.text().strip()
        wordlist = self.wordlist_edit.text().strip()
        unrar = self.unrar_edit.text().strip()

        if not archive:

            QMessageBox.warning(
                self,
                "Ошибка",
                "Выберите RAR архив.",
            )

            return

        if not Path(archive).is_file():

            QMessageBox.warning(
                self,
                "Ошибка",
                "Указанный RAR архив не существует.",
            )

            return

        if Path(archive).stat().st_size == 0:

            QMessageBox.warning(
                self,
                "Ошибка",
                "Выбранный архив пуст.",
            )

            return

        if not wordlist:

            QMessageBox.warning(
                self,
                "Ошибка",
                "Выберите wordlist.",
            )

            return

        if not Path(wordlist).is_file():

            QMessageBox.warning(
                self,
                "Ошибка",
                "Указанный wordlist не существует.",
            )

            return

        if not unrar:

            QMessageBox.warning(
                self,
                "Ошибка",
                "Не указан UnRAR.exe.",
            )

            return

        if not Path(unrar).is_file():

            QMessageBox.warning(
                self,
                "Ошибка",
                "UnRAR.exe не найден.",
            )

            return

        # ----------------------------------------------------
        # RESET
        # ----------------------------------------------------

        self.progress.setValue(0)

        self.stats_label.setText(
            "Проверено: 0    "
            "Пропущено: 0    "
            "Всего строк: 0"
        )

        self.write_log("")
        self.write_log(
            "========================================"
        )
        self.write_log(
            "Запуск RAR Password Recovery 2.1"
        )
        self.write_log(
            "========================================"
        )

        mode = (
            self.verification_combo.currentData()
        )

        skip_duplicates = (
            self.skip_duplicates_button.isChecked()
        )

        # ----------------------------------------------------
        # WORKER
        # ----------------------------------------------------

        self.checker = PasswordChecker(
            archive_path=archive,
            wordlist_path=wordlist,
            unrar_path=unrar,
            verification_mode=mode,
            skip_duplicates=skip_duplicates,
        )

        self.checker.progress_signal.connect(
            self.progress.setValue
        )

        self.checker.log_signal.connect(
            self.write_log
        )

        self.checker.stats_signal.connect(
            self.stats_label.setText
        )

        self.checker.found_signal.connect(
            self.password_found
        )

        self.checker.finished_signal.connect(
            self.check_finished
        )

        self.checker.error_signal.connect(
            self.check_error
        )

        self.checker.finished.connect(
            self.worker_thread_finished
        )

        # ----------------------------------------------------
        # BUTTON STATE
        # ----------------------------------------------------

        self.start_button.setEnabled(
            False
        )

        self.stop_button.setEnabled(
            True
        )

        self.archive_edit.setEnabled(
            False
        )

        self.wordlist_edit.setEnabled(
            False
        )

        self.unrar_edit.setEnabled(
            False
        )

        self.verification_combo.setEnabled(
            False
        )

        self.skip_duplicates_button.setEnabled(
            False
        )

        self.checker.start()

    def stop_check(self):

        if not self.checker:
            return

        if not self.checker.isRunning():
            return

        self.write_log(
            "Запрошена остановка..."
        )

        self.stop_button.setEnabled(
            False
        )

        self.checker.stop()

    def password_found(self, password):

        self.write_log(
            ""
        )

        self.write_log(
            "========================================"
        )

        self.write_log(
            "ПАРОЛЬ НАЙДЕН"
        )

        self.write_log(
            f"Пароль: {password}"
        )

        self.write_log(
            "========================================"
        )

        QMessageBox.information(
            self,
            "Пароль найден",
            f"Пароль:\n\n{password}",
        )

    # --------------------------------------------------------
    # FINISHED
    # --------------------------------------------------------

    def check_finished(self, message):

        self.write_log(
            message
        )

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    def check_error(self, message):

        self.write_log(
            "ОШИБКА:"
        )

        self.write_log(
            message
        )

        QMessageBox.critical(
            self,
            "Ошибка",
            message,
        )

    # --------------------------------------------------------
    # THREAD FINISHED
    # --------------------------------------------------------

    def worker_thread_finished(self):

        self.write_log(
            "Поток проверки завершён."
        )

        self.restore_controls()

        if self.checker:

            self.checker.deleteLater()

        self.checker = None

    # --------------------------------------------------------
    # RESTORE UI
    # --------------------------------------------------------

    def restore_controls(self):

        self.start_button.setEnabled(
            True
        )

        self.stop_button.setEnabled(
            False
        )

        self.archive_edit.setEnabled(
            True
        )

        self.wordlist_edit.setEnabled(
            True
        )

        self.unrar_edit.setEnabled(
            True
        )

        self.verification_combo.setEnabled(
            True
        )

        self.skip_duplicates_button.setEnabled(
            True
        )

    # --------------------------------------------------------
    # CLOSE EVENT
    # --------------------------------------------------------

    def closeEvent(self, event):

        if (
            self.checker
            and self.checker.isRunning()
        ):

            answer = QMessageBox.question(
                self,
                "Проверка выполняется",
                (
                    "Проверка паролей ещё выполняется.\n\n"
                    "Остановить проверку и закрыть программу?"
                ),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:

                event.ignore()
                return

            self.write_log(
                "Остановка перед закрытием программы..."
            )

            self.checker.stop()

            # Ждём завершения потока.
            # Worker самостоятельно завершит внешний UnRAR,
            # если он в этот момент выполняется.
            if not self.checker.wait(5000):

                QMessageBox.warning(
                    self,
                    "Остановка",
                    (
                        "Поток проверки не успел завершиться "
                        "за 5 секунд.\n\n"
                        "Закрытие отменено, чтобы не оставить "
                        "рабочий поток в некорректном состоянии."
                    ),
                )

                event.ignore()
                return

        event.accept()


# ============================================================
# MAIN
# ============================================================

def main():

    app = QApplication(
        sys.argv
    )

    window = MainWindow()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()