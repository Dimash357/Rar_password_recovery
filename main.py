import os
import sys
import subprocess
from pathlib import Path

import rarfile

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
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

    script_unrar = Path(__file__).resolve().parent / "UnRAR.exe"

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
    ):
        super().__init__()

        self.archive_path = archive_path
        self.wordlist_path = wordlist_path
        self.unrar_path = unrar_path
        self.verification_mode = verification_mode
        self.skip_duplicates = skip_duplicates

        self.stop_requested = False

        self.tested = 0
        self.skipped = 0

    def stop(self):
        self.stop_requested = True

    def log(self, text):
        self.log_signal.emit(text)

    # --------------------------------------------------------
    # UNRAR TEST
    # --------------------------------------------------------

    def unrar_test_password(self, password):

        if self.stop_requested:
            return False, False

        try:
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

            code = process.wait()

            return code == 0, True

        except Exception as e:

            self.log(
                f"UnRAR ошибка: {e}"
            )

            return False, True

    # --------------------------------------------------------
    # QUICK
    # --------------------------------------------------------

    def rarfile_quick_test(self, password):

        try:

            with rarfile.RarFile(
                self.archive_path
            ) as archive:

                archive.setpassword(
                    password
                )

                infos = archive.infolist()

                if not infos:

                    return (
                        False,
                        False,
                        "RAR не вернул список файлов",
                    )

                files = [
                    info
                    for info in infos
                    if not info.is_dir()
                ]

                if not files:

                    return (
                        False,
                        False,
                        "В архиве нет файлов",
                    )

                files.sort(
                    key=lambda x:
                    getattr(
                        x,
                        "file_size",
                        0,
                    ) or 0
                )

                test_info = files[0]

                self.log(
                    f"Тест: {test_info.filename}"
                )

                with archive.open(
                    test_info
                ) as file:

                    file.read(4096)

                return True, True, ""

        except rarfile.BadRarFile:

            return (
                False,
                False,
                "Повреждённый или неподдерживаемый RAR",
            )

        except rarfile.PasswordRequired:

            return (
                False,
                False,
                "Требуется пароль",
            )

        except rarfile.RarWrongPassword:

            return (
                False,
                False,
                "Неверный пароль",
            )

        except rarfile.NoCrypto:

            return (
                False,
                False,
                "Криптография RAR не поддерживается",
            )

        except Exception as e:

            return (
                False,
                False,
                str(e),
            )

    # --------------------------------------------------------
    # FULL
    # --------------------------------------------------------

    def rarfile_full_test(self, password):

        try:

            with rarfile.RarFile(
                self.archive_path
            ) as archive:

                archive.setpassword(
                    password
                )

                infos = archive.infolist()

                files = [
                    info
                    for info in infos
                    if not info.is_dir()
                ]

                if not files:

                    return (
                        False,
                        "В архиве нет файлов",
                    )

                for index, info in enumerate(
                    files,
                    start=1,
                ):

                    if self.stop_requested:

                        return (
                            False,
                            "STOP",
                        )

                    self.log(
                        f"Проверка {index}/{len(files)}: "
                        f"{info.filename}"
                    )

                    with archive.open(
                        info
                    ) as file:

                        while True:

                            if self.stop_requested:

                                return (
                                    False,
                                    "STOP",
                                )

                            chunk = file.read(
                                1024 * 1024
                            )

                            if not chunk:
                                break

                return True, ""

        except rarfile.RarWrongPassword:

            return False, "Неверный пароль"

        except rarfile.PasswordRequired:

            return False, "Требуется пароль"

        except rarfile.BadRarFile:

            return False, "Повреждённый RAR"

        except rarfile.NoCrypto:

            return False, "Криптография не поддерживается"

        except Exception as e:

            return False, str(e)

    # --------------------------------------------------------
    # COUNT
    # --------------------------------------------------------

    def count_wordlist(self):

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
    # DECODE
    # --------------------------------------------------------

    @staticmethod
    def decode_password(raw):

        for encoding in (
            "utf-8-sig",
            "utf-8",
            "cp1251",
            "cp866",
            "latin-1",
        ):

            try:
                return raw.decode(
                    encoding
                ).rstrip("\r\n")

            except UnicodeDecodeError:
                continue

        return raw.decode(
            "utf-8",
            errors="replace",
        ).rstrip("\r\n")

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

    def run(self):

        try:

            archive = Path(
                self.archive_path
            )

            wordlist = Path(
                self.wordlist_path
            )

            unrar = Path(
                self.unrar_path
            )

            # ------------------------------------------------
            # VALIDATION
            # ------------------------------------------------

            if not archive.is_file():

                self.error_signal.emit(
                    "Архив не найден."
                )

                return

            if archive.stat().st_size == 0:

                self.error_signal.emit(
                    "Архив пуст."
                )

                return

            if not wordlist.is_file():

                self.error_signal.emit(
                    "Wordlist не найден."
                )

                return

            if not unrar.is_file():

                self.error_signal.emit(
                    "UnRAR.exe не найден."
                )

                return

            rarfile.UNRAR_TOOL = str(
                unrar
            )

            # ------------------------------------------------
            # PASSWORD CHECK
            # ------------------------------------------------

            self.log(
                "Проверка защиты архива паролем..."
            )

            try:

                with rarfile.RarFile(
                        str(archive)
                ) as test_archive:

                    if not test_archive.needs_password():
                        self.error_signal.emit(
                            "RAR архив не защищён паролем."
                        )

                        return

                self.log(
                    "✓ Архив защищён паролем."
                )

            except Exception as e:

                self.error_signal.emit(
                    f"Не удалось определить защиту архива: {e}"
                )

                return

        # ------------------------------------------------
            # INFO
            # ------------------------------------------------

            self.log(
                "Проверка архива..."
            )

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

                    self.log(
                        "✓ Архив успешно распознан."
                    )

                else:

                    self.log(
                        "⚠ UnRAR не смог получить список."
                    )

                    self.log(
                        "Проверка паролей продолжается."
                    )

            except subprocess.TimeoutExpired:

                self.log(
                    "⚠ Проверка списка заняла слишком много времени."
                )

            # ------------------------------------------------
            # WORDLIST
            # ------------------------------------------------

            total = self.count_wordlist()

            if total == 0:

                self.error_signal.emit(
                    "Wordlist пуст."
                )

                return

            self.log(
                f"Wordlist: {total:,} строк"
            )

            seen = set()

            # ------------------------------------------------
            # PASSWORD LOOP
            # ------------------------------------------------

            with open(
                wordlist,
                "rb",
                buffering=1024 * 1024,
            ) as file:

                for raw in file:

                    if self.stop_requested:

                        self.finished_signal.emit(
                            "Проверка остановлена."
                        )

                        return

                    password = (
                        self.decode_password(raw)
                    )

                    if password == "":

                        self.skipped += 1
                        continue

                    if self.skip_duplicates:

                        if password in seen:

                            self.skipped += 1
                            continue

                        seen.add(password)

                    self.tested += 1

                    current = (
                        self.tested
                        + self.skipped
                    )

                    progress = int(
                        current / total * 100
                    )

                    self.progress_signal.emit(
                        min(100, progress)
                    )

                    self.stats_signal.emit(
                        f"{self.tested:,} проверено  •  "
                        f"{self.skipped:,} пропущено  •  "
                        f"{total:,} строк"
                    )

                    # ------------------------------------------------
                    # QUICK
                    # ------------------------------------------------

                    if self.verification_mode == "quick":

                        ok, usable, error = (
                            self.rarfile_quick_test(
                                password
                            )
                        )

                        if ok:

                            self.found_signal.emit(
                                password
                            )

                            self.finished_signal.emit(
                                "Пароль найден."
                            )

                            return

                        if not usable:

                            unrar_ok, _ = (
                                self.unrar_test_password(
                                    password
                                )
                            )

                            if unrar_ok:

                                self.found_signal.emit(
                                    password
                                )

                                self.finished_signal.emit(
                                    "Пароль найден."
                                )

                                return

                    # ------------------------------------------------
                    # FULL
                    # ------------------------------------------------

                    else:

                        ok, error = (
                            self.rarfile_full_test(
                                password
                            )
                        )

                        if ok:

                            self.found_signal.emit(
                                password
                            )

                            self.finished_signal.emit(
                                "Пароль найден."
                            )

                            return

                        if error == "STOP":

                            self.finished_signal.emit(
                                "Проверка остановлена."
                            )

                            return

            self.progress_signal.emit(
                100
            )

            self.finished_signal.emit(
                "Пароль в wordlist не найден."
            )

        except Exception as e:

            self.error_signal.emit(
                f"{type(e).__name__}: {e}"
            )


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.checker = None

        self.setWindowTitle(
            "RAR Password Recovery"
        )

        self.setMinimumSize(
            1080,
            960,
        )

        self.build_ui()
        self.apply_style()
        self.detect_unrar()

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def build_ui(self):

        root = QWidget()

        self.setCentralWidget(
            root
        )

        main = QVBoxLayout(root)

        main.setContentsMargins(
            28,
            24,
            28,
            24,
        )

        main.setSpacing(
            18
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header = QHBoxLayout()

        title_box = QVBoxLayout()

        title = QLabel(
            "RAR Password Recovery"
        )

        title.setObjectName(
            "title"
        )

        subtitle = QLabel(
            "Проверка паролей по словарю"
        )

        subtitle.setObjectName(
            "subtitle"
        )

        title_box.addWidget(
            title
        )

        title_box.addWidget(
            subtitle
        )

        header.addLayout(
            title_box
        )

        header.addStretch()

        main.addLayout(
            header
        )

        # ----------------------------------------------------
        # FILE CARD
        # ----------------------------------------------------

        file_card = QFrame()

        file_card.setObjectName(
            "card"
        )

        file_layout = QVBoxLayout(
            file_card
        )

        file_layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        file_layout.setSpacing(
            12
        )

        card_title = QLabel(
            "Файлы"
        )

        card_title.setObjectName(
            "cardTitle"
        )

        file_layout.addWidget(
            card_title
        )

        self.archive_edit = (
            self.create_file_row(
                file_layout,
                "Архив",
                "Выберите RAR архив...",
                self.select_archive,
            )
        )

        self.wordlist_edit = (
            self.create_file_row(
                file_layout,
                "Wordlist",
                "Выберите файл со списком паролей...",
                self.select_wordlist,
            )
        )

        self.unrar_edit = (
            self.create_file_row(
                file_layout,
                "UnRAR",
                "Путь к UnRAR.exe...",
                self.select_unrar,
            )
        )

        main.addWidget(
            file_card
        )

        # ----------------------------------------------------
        # SETTINGS CARD
        # ----------------------------------------------------

        settings = QFrame()

        settings.setObjectName(
            "card"
        )

        settings_layout = QHBoxLayout(
            settings
        )

        settings_layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        # Verification
        verification_box = QVBoxLayout()

        verification_label = QLabel(
            "Режим проверки"
        )

        verification_label.setObjectName(
            "fieldLabel"
        )

        self.verification_combo = (
            QComboBox()
        )

        self.verification_combo.addItem(
            "Быстрая проверка",
            "quick",
        )

        self.verification_combo.addItem(
            "Полная проверка",
            "full",
        )

        verification_box.addWidget(
            verification_label
        )

        verification_box.addWidget(
            self.verification_combo
        )

        # Duplicate
        duplicate_box = QVBoxLayout()

        duplicate_label = QLabel(
            "Опции"
        )

        duplicate_label.setObjectName(
            "fieldLabel"
        )

        self.duplicate_button = (
            QPushButton(
                "●  Пропускать дубликаты"
            )
        )

        self.duplicate_button.setCheckable(
            True
        )

        self.duplicate_button.setChecked(
            True
        )

        self.duplicate_button.clicked.connect(
            self.toggle_duplicates
        )

        duplicate_box.addWidget(
            duplicate_label
        )

        duplicate_box.addWidget(
            self.duplicate_button
        )

        settings_layout.addLayout(
            verification_box
        )

        settings_layout.addSpacing(
            20
        )

        settings_layout.addLayout(
            duplicate_box
        )

        settings_layout.addStretch()

        main.addWidget(
            settings
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        status_card = QFrame()

        status_card.setObjectName(
            "statusCard"
        )

        status_layout = QVBoxLayout(
            status_card
        )

        status_layout.setContentsMargins(
            20,
            16,
            20,
            16,
        )

        status_header = QHBoxLayout()

        self.status_dot = QLabel(
            "●"
        )

        self.status_dot.setObjectName(
            "statusDot"
        )

        self.status_label = QLabel(
            "Готов к проверке"
        )

        self.status_label.setObjectName(
            "statusLabel"
        )

        status_header.addWidget(
            self.status_dot
        )

        status_header.addWidget(
            self.status_label
        )

        status_header.addStretch()

        self.percent_label = QLabel(
            "0%"
        )

        self.percent_label.setObjectName(
            "percent"
        )

        status_header.addWidget(
            self.percent_label
        )

        status_layout.addLayout(
            status_header
        )

        self.progress = QProgressBar()

        self.progress.setValue(
            0
        )

        self.progress.setTextVisible(
            False
        )

        status_layout.addWidget(
            self.progress
        )

        self.stats_label = QLabel(
            "0 проверено  •  "
            "0 пропущено  •  "
            "0 строк"
        )

        self.stats_label.setObjectName(
            "stats"
        )

        status_layout.addWidget(
            self.stats_label
        )

        main.addWidget(
            status_card
        )

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        buttons = QHBoxLayout()

        self.start_button = QPushButton(
            "▶   Начать проверку"
        )

        self.start_button.setObjectName(
            "startButton"
        )

        self.stop_button = QPushButton(
            "■   Остановить"
        )

        self.stop_button.setObjectName(
            "stopButton"
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

        buttons.addWidget(
            self.start_button
        )

        buttons.addWidget(
            self.stop_button
        )

        main.addLayout(
            buttons
        )

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        log_title = QHBoxLayout()

        log_label = QLabel(
            "Журнал"
        )

        log_label.setObjectName(
            "cardTitle"
        )

        log_title.addWidget(
            log_label
        )

        log_title.addStretch()

        main.addLayout(
            log_title
        )

        self.log = QTextEdit()

        self.log.setReadOnly(
            True
        )

        self.log.setObjectName(
            "log"
        )

        main.addWidget(
            self.log,
            1,
        )

        # ----------------------------------------------------
        # FOOTER
        # ----------------------------------------------------

        footer = QLabel(
            "RAR Password Recovery • "
            "UnRAR backend"
        )

        footer.setObjectName(
            "footer"
        )

        footer.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        main.addWidget(
            footer
        )

    # --------------------------------------------------------
    # FILE ROW
    # --------------------------------------------------------

    def create_file_row(
            self,
            parent_layout,
            label_text,
            placeholder,
            callback,
    ):
        label = QLabel(label_text)

        label.setObjectName(
            "fieldLabel"
        )

        row = QHBoxLayout()
        row.setSpacing(10)

        edit = QLineEdit()

        edit.setPlaceholderText(
            placeholder
        )

        # Поле не будет схлопываться
        edit.setMinimumWidth(420)

        # Длинный путь можно посмотреть целиком
        edit.setToolTip("")

        button = QPushButton(
            "Обзор"
        )

        # Кнопка всегда остаётся нормального размера
        button.setMinimumWidth(90)
        button.setMaximumWidth(110)

        button.clicked.connect(
            callback
        )

        row.addWidget(
            edit,
            1
        )

        row.addWidget(
            button,
            0
        )

        parent_layout.addWidget(
            label
        )

        parent_layout.addLayout(
            row
        )

        return edit

    # --------------------------------------------------------
    # STYLE
    # --------------------------------------------------------

    def apply_style(self):

        self.setStyleSheet(
            """
            QMainWindow {
                background: #0f1117;
            }

            QWidget {
                color: #e7e9ee;
                font-family: "Segoe UI";
                font-size: 14px;
            }

            QLabel#title {
                font-size: 28px;
                font-weight: 700;
                color: #ffffff;
            }

            QLabel#subtitle {
                color: #8d95a5;
                font-size: 14px;
                margin-top: 2px;
            }

            QFrame#card {
                background: #171a22;
                border: 1px solid #252b36;
                border-radius: 14px;
            }

            QFrame#statusCard {
                background: #141923;
                border: 1px solid #263044;
                border-radius: 14px;
            }

            QLabel#cardTitle {
                color: #ffffff;
                font-size: 16px;
                font-weight: 650;
            }

            QLabel#fieldLabel {
                color: #929aaa;
                font-size: 12px;
                font-weight: 600;
            }

            QLineEdit {
                background: #10131a;
                border: 1px solid #2a303c;
                border-radius: 9px;
                padding: 10px 12px;
                color: #eef0f4;
                selection-background-color: #4c79d8;
            }

            QLineEdit:focus {
                border: 1px solid #4c79d8;
            }

            QComboBox {
                background: #10131a;
                border: 1px solid #2a303c;
                border-radius: 9px;
                padding: 9px 12px;
                min-width: 190px;
            }

            QComboBox:hover {
                border: 1px solid #3a4352;
            }

            QComboBox QAbstractItemView {
                background: #171a22;
                border: 1px solid #303746;
                selection-background-color: #344b78;
                color: #ffffff;
            }

            QPushButton {
                background: #202632;
                border: 1px solid #303746;
                border-radius: 9px;
                padding: 10px 16px;
                color: #e8ebf0;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #28303d;
                border-color: #414b5c;
            }

            QPushButton:pressed {
                background: #171c25;
            }

            QPushButton:disabled {
                background: #171a20;
                color: #555d6b;
                border-color: #222731;
            }

            QPushButton#startButton {
                background: #315fc4;
                border: none;
                border-radius: 10px;
                padding: 13px;
                font-size: 15px;
                font-weight: 700;
                color: white;
            }

            QPushButton#startButton:hover {
                background: #3b6bd8;
            }

            QPushButton#startButton:pressed {
                background: #294fa5;
            }

            QPushButton#startButton:disabled {
                background: #242a35;
                color: #616978;
            }

            QPushButton#stopButton {
                background: #242831;
                border: 1px solid #3a404c;
                border-radius: 10px;
                padding: 13px;
                font-size: 15px;
                font-weight: 700;
            }

            QPushButton#stopButton:hover {
                background: #302c31;
                border-color: #55464d;
            }

            QPushButton#stopButton:disabled {
                background: #181b21;
                color: #555d6b;
            }

            QPushButton:checked {
                background: #253a62;
                border-color: #3e62a1;
            }

            QLabel#statusDot {
                color: #5c83d8;
                font-size: 17px;
            }

            QLabel#statusLabel {
                color: #dfe4ec;
                font-size: 14px;
                font-weight: 650;
            }

            QLabel#percent {
                color: #ffffff;
                font-size: 20px;
                font-weight: 700;
            }

            QLabel#stats {
                color: #7f8898;
                font-size: 12px;
            }

            QProgressBar {
                background: #0d1016;
                border: none;
                border-radius: 5px;
                height: 10px;
                margin-top: 8px;
                margin-bottom: 4px;
            }

            QProgressBar::chunk {
                background: #4d78d3;
                border-radius: 5px;
            }

            QTextEdit#log {
                background: #0b0e13;
                border: 1px solid #252b36;
                border-radius: 12px;
                padding: 12px;
                color: #aeb6c5;
                font-family: "Cascadia Mono", "Consolas", monospace;
                font-size: 12px;
            }

            QLabel#footer {
                color: #555d6b;
                font-size: 11px;
            }
            
            QMessageBox {
                background: #171a22;
            }
            
            QMessageBox QLabel {
                color: #ffffff;
                background: transparent;
            }
            """
        )

    # --------------------------------------------------------
    # UNRAR
    # --------------------------------------------------------

    def detect_unrar(self):

        path = find_unrar()

        if path:

            unrar = find_unrar()

            if unrar:
                self.unrar_edit.setText(str(unrar))

            self.write_log(
                f"✓ UnRAR найден: {path}"
            )

        else:

            self.write_log(
                "⚠ UnRAR.exe не найден автоматически."
            )

    # --------------------------------------------------------
    # SELECT ARCHIVE
    # --------------------------------------------------------

    def select_archive(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите RAR архив",
            "",
            "RAR архивы (*.rar *.part*.rar *.r00 *.r01);;"
            "Все файлы (*)",
        )

        if path:

            self.archive_edit.setText(
                path
            )

    # --------------------------------------------------------
    # SELECT WORDLIST
    # --------------------------------------------------------

    def select_wordlist(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите wordlist",
            "",
            "Wordlist (*.txt *.lst *.dic);;"
            "Все файлы (*)",
        )

        if path:

            self.wordlist_edit.setText(
                path
            )

    # --------------------------------------------------------
    # SELECT UNRAR
    # --------------------------------------------------------

    def select_unrar(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите UnRAR.exe",
            "",
            "UnRAR.exe (UnRAR.exe);;Все файлы (*)",
        )

        if path:

            self.unrar_edit.setText(
                path
            )

    # --------------------------------------------------------
    # DUPLICATES
    # --------------------------------------------------------

    def toggle_duplicates(self):

        if self.duplicate_button.isChecked():

            self.duplicate_button.setText(
                "●  Пропускать дубликаты"
            )

        else:

            self.duplicate_button.setText(
                "○  Не пропускать дубликаты"
            )

    # --------------------------------------------------------
    # LOG
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    def start_check(self):

        archive = (
            self.archive_edit.text().strip()
        )

        wordlist = (
            self.wordlist_edit.text().strip()
        )

        unrar = (
            self.unrar_edit.text().strip()
        )

        if not archive:

            QMessageBox.warning(
                self,
                "Не выбран архив",
                "Выберите RAR архив.",
            )

            return

        if not Path(archive).is_file():

            QMessageBox.warning(
                self,
                "Ошибка",
                "Указанный архив не существует.",
            )

            return

        if not wordlist:

            QMessageBox.warning(
                self,
                "Не выбран wordlist",
                "Выберите файл со списком паролей.",
            )

            return

        if not Path(wordlist).is_file():

            QMessageBox.warning(
                self,
                "Ошибка",
                "Wordlist не существует.",
            )

            return

        if not unrar:

            QMessageBox.warning(
                self,
                "UnRAR",
                "Не найден UnRAR.exe.",
            )

            return

        if not Path(unrar).is_file():

            QMessageBox.warning(
                self,
                "UnRAR",
                "Указанный UnRAR.exe не существует.",
            )

            return

        # ----------------------------------------------------
        # UI RESET
        # ----------------------------------------------------

        self.progress.setValue(
            0
        )

        self.percent_label.setText(
            "0%"
        )

        self.status_label.setText(
            "Подготовка..."
        )

        self.stats_label.setText(
            "0 проверено  •  "
            "0 пропущено  •  "
            "подготовка"
        )

        self.write_log("")
        self.write_log(
            "════════════════════════════════════"
        )
        self.write_log(
            "  Запуск RAR Password Recovery 2.2"
        )
        self.write_log(
            "════════════════════════════════════"
        )

        mode = (
            self.verification_combo.currentData()
        )

        skip_duplicates = (
            self.duplicate_button.isChecked()
        )

        self.checker = PasswordChecker(
            archive_path=archive,
            wordlist_path=wordlist,
            unrar_path=unrar,
            verification_mode=mode,
            skip_duplicates=skip_duplicates,
        )

        self.checker.progress_signal.connect(
            self.update_progress
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
            self.worker_finished
        )

        self.set_running_ui(
            True
        )

        self.checker.start()

    # --------------------------------------------------------
    # PROGRESS
    # --------------------------------------------------------

    def update_progress(self, value):

        self.progress.setValue(
            value
        )

        self.percent_label.setText(
            f"{value}%"
        )

        if value > 0:

            self.status_label.setText(
                "Идёт проверка..."
            )

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    def stop_check(self):

        if (
            self.checker
            and self.checker.isRunning()
        ):

            self.status_label.setText(
                "Остановка..."
            )

            self.write_log(
                "⚠ Запрошена остановка."
            )

            self.stop_button.setEnabled(
                False
            )

            self.checker.stop()

    # --------------------------------------------------------
    # FOUND
    # --------------------------------------------------------

    def password_found(self, password):

        self.status_label.setText(
            "Пароль найден!"
        )

        self.status_dot.setText(
            "●"
        )

        self.write_log("")
        self.write_log(
            "════════════════════════════════════"
        )
        self.write_log(
            "  ✓ ПАРОЛЬ НАЙДЕН"
        )
        self.write_log(
            f"  Пароль: {password}"
        )
        self.write_log(
            "════════════════════════════════════"
        )

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Пароль найден")
        dialog.setText("Пароль успешно найден!")
        dialog.setInformativeText(f"\nПароль:\n{password}")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.setStyleSheet(
            """ 
            QMessageBox { 
                background: #171a22; color: #ffffff; min-width: 480px; 
            }
            
            QMessageBox QLabel { 
                color: #ffffff; font-size: 14px; 
            }
            
            QMessageBox QLabel#qt_msgbox_label { 
                color: #ffffff; font-size: 18px; font-weight: 700; 
            }
            
            QMessageBox QLabel#qt_msgbox_informativelabel { 
                background: #10131a; border: 1px solid #343c4c; border-radius: 10px; padding: 14px; color: #ffffff; font-size: 16px; font-weight: 600; 
            }
            
            QPushButton {
                background: #315fc4; border: none; border-radius: 9px; padding: 10px 24px; color: #ffffff; font-weight: 700; min-width: 90px;
            } 
            
            QPushButton:hover { 
                background: #3b6bd8; 
            }
            
            QPushButton:pressed {
            background: #294fa5; 
            } """)

        dialog.exec()

    # --------------------------------------------------------
    # FINISHED
    # --------------------------------------------------------

    def check_finished(self, message):

        self.write_log(
            f"→ {message}"
        )

        if "найден" in message.lower():

            self.status_label.setText(
                "Готово — пароль найден"
            )

        elif "останов" in message.lower():

            self.status_label.setText(
                "Проверка остановлена"
            )

        else:

            self.status_label.setText(
                "Проверка завершена"
            )

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    def check_error(self, message):

        self.status_label.setText(
            "Ошибка"
        )

        self.write_log(
            f"✕ Ошибка: {message}"
        )

        QMessageBox.critical(
            self,
            "Ошибка",
            message,
        )

    # --------------------------------------------------------
    # THREAD FINISHED
    # --------------------------------------------------------

    def worker_finished(self):

        self.set_running_ui(
            False
        )

        self.write_log(
            "Поток проверки завершён."
        )

        if self.checker:

            self.checker.deleteLater()

        self.checker = None

    # --------------------------------------------------------
    # RUNNING UI
    # --------------------------------------------------------

    def set_running_ui(self, running):

        self.start_button.setEnabled(
            not running
        )

        self.stop_button.setEnabled(
            running
        )

        self.archive_edit.setEnabled(
            not running
        )

        self.wordlist_edit.setEnabled(
            not running
        )

        self.unrar_edit.setEnabled(
            not running
        )

        self.verification_combo.setEnabled(
            not running
        )

        self.duplicate_button.setEnabled(
            not running
        )

    # --------------------------------------------------------
    # CLOSE
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
                    "Остановить её и закрыть программу?"
                ),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:

                event.ignore()
                return

            self.checker.stop()

            if not self.checker.wait(5000):

                QMessageBox.warning(
                    self,
                    "Остановка",
                    (
                        "Проверка ещё не завершилась.\n\n"
                        "Закрытие отменено."
                    ),
                )

                event.ignore()
                return
        answer.setStyleSheet(
            """ 
            QMessageBox { 
                background: #171a22; color: #ffffff; min-width: 480px; 
            }

            QMessageBox QLabel { 
                color: #ffffff; font-size: 14px; 
            }

            QMessageBox QLabel#qt_msgbox_label { 
                color: #ffffff; font-size: 18px; font-weight: 700; 
            }

            QMessageBox QLabel#qt_msgbox_informativelabel { 
                background: #10131a; border: 1px solid #343c4c; border-radius: 10px; padding: 14px; color: #ffffff; font-size: 16px; font-weight: 600; 
            }

            QPushButton {
                background: #315fc4; border: none; border-radius: 9px; padding: 10px 24px; color: #ffffff; font-weight: 700; min-width: 90px;
            } 

            QPushButton:hover { 
                background: #3b6bd8; 
            }

            QPushButton:pressed {
                background: #294fa5; 
            } 
            
            QMessageBox {
                background: #171a22;
            }

            QMessageBox QLabel {
                color: #ffffff;
                background: transparent;
            } """)

        event.accept()


# ============================================================
# MAIN
# ============================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "RAR Password Recovery"
    )

    app.setApplicationVersion(
        "2.2"
    )

    font = QFont(
        "Segoe UI",
        10,
    )

    app.setFont(
        font
    )

    window = MainWindow()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()