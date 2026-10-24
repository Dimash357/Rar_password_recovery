from core.password_checker import PasswordChecker
from core.unrar_utils import find_unrar
from ui.styles import APP_STYLE

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.checker = None
        self.setWindowTitle("RAR Password Recovery")
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

        self.setCentralWidget(root)

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

        title = QLabel("RAR Password Recovery")
        title.setObjectName("title")

        subtitle = QLabel("Проверка паролей по словарю")
        subtitle.setObjectName("subtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header.addLayout(title_box)
        header.addStretch()

        main.addLayout(header)

        # ----------------------------------------------------
        # FILE CARD
        # ----------------------------------------------------

        file_card = QFrame()
        file_card.setObjectName("card")

        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        file_layout.setSpacing(
            12
        )

        card_title = QLabel("Файлы")
        card_title.setObjectName("cardTitle")

        file_layout.addWidget(card_title)

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

        main.addWidget(file_card)

        # ----------------------------------------------------
        # SETTINGS CARD
        # ----------------------------------------------------

        settings = QFrame()
        settings.setObjectName("card")

        settings_layout = QHBoxLayout(settings)
        settings_layout.setContentsMargins(
            20,
            18,
            20,
            18,
        )

        # Verification
        verification_box = QVBoxLayout()

        verification_label = QLabel("Режим проверки")
        verification_label.setObjectName("fieldLabel")

        self.verification_combo = (QComboBox())

        self.verification_combo.addItem(
            "Быстрая проверка",
            "quick",
        )

        self.verification_combo.addItem(
            "Полная проверка",
            "full",
        )

        verification_box.addWidget(verification_label)
        verification_box.addWidget(self.verification_combo)

        # Duplicate
        duplicate_box = QVBoxLayout()

        duplicate_label = QLabel("Опции")
        duplicate_label.setObjectName("fieldLabel")

        self.duplicate_button = (QPushButton("●  Пропускать дубликаты"))
        self.duplicate_button.setCheckable(True)
        self.duplicate_button.setChecked(True)
        self.duplicate_button.clicked.connect(self.toggle_duplicates)

        duplicate_box.addWidget(duplicate_label)
        duplicate_box.addWidget(self.duplicate_button)

        settings_layout.addLayout(verification_box)
        settings_layout.addSpacing(20)
        settings_layout.addLayout(duplicate_box)
        settings_layout.addStretch()

        main.addWidget(settings)

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        status_card = QFrame()
        status_card.setObjectName("statusCard")

        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(
            20,
            16,
            20,
            16,
        )

        status_header = QHBoxLayout()

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_label = QLabel("Готов к проверке")
        self.status_label.setObjectName("statusLabel")

        status_header.addWidget(self.status_dot)
        status_header.addWidget(self.status_label)
        status_header.addStretch()

        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("percent")

        status_header.addWidget(self.percent_label)

        status_layout.addLayout(status_header)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)

        status_layout.addWidget(self.progress)

        self.stats_label = QLabel(
            "0 проверено  •  "
            "0 пропущено  •  "
            "0 строк"
        )

        self.stats_label.setObjectName("stats")

        status_layout.addWidget(self.stats_label)

        main.addWidget(status_card)

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        buttons = QHBoxLayout()

        self.start_button = QPushButton("▶   Начать проверку")
        self.start_button.setObjectName("startButton")

        self.pause_button = QPushButton("⏸  Пауза")
        self.pause_button.setObjectName("pauseButton")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.toggle_pause)

        self.stop_button = QPushButton("■   Остановить")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setEnabled(False)

        self.start_button.clicked.connect(self.start_check)
        self.stop_button.clicked.connect(self.stop_check)

        buttons.addWidget(self.start_button)
        buttons.addWidget(self.pause_button)
        buttons.addWidget(self.stop_button)

        main.addLayout(buttons)

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        log_title = QHBoxLayout()

        log_label = QLabel("Журнал")
        log_label.setObjectName("cardTitle")

        log_title.addWidget(log_label)
        log_title.addStretch()

        main.addLayout(log_title)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("log")

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

        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main.addWidget(footer)

    # --------------------------------------------------------
    # FILE ROW
    # --------------------------------------------------------

    def create_file_row(self, parent_layout, label_text, placeholder, callback):
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")

        row = QHBoxLayout()
        row.setSpacing(10)

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setMinimumWidth(420)
        edit.setToolTip("")

        button = QPushButton("Обзор")
        button.setMinimumWidth(90)
        button.setMaximumWidth(110)
        button.clicked.connect(callback)

        row.addWidget(
            edit,
            1
        )

        row.addWidget(
            button,
            0
        )

        parent_layout.addWidget(label)
        parent_layout.addLayout(row)

        return edit

    # --------------------------------------------------------
    # STYLE
    # --------------------------------------------------------

    def apply_style(self):
        self.setStyleSheet(APP_STYLE)

    # --------------------------------------------------------
    # UNRAR
    # --------------------------------------------------------

    def detect_unrar(self):
        path = find_unrar()

        if path:
            unrar = find_unrar()

            if unrar:
                self.unrar_edit.setText(str(unrar))

            self.write_log(f"✓ UnRAR найден: {path}")

        else:

            self.write_log("⚠ UnRAR.exe не найден автоматически.")

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
            self.archive_edit.setText(path)

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
            self.wordlist_edit.setText(path)

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
            self.unrar_edit.setText(path)

    # --------------------------------------------------------
    # DUPLICATES
    # --------------------------------------------------------

    def toggle_duplicates(self):
        if self.duplicate_button.isChecked():
            self.duplicate_button.setText("●  Пропускать дубликаты")

        else:
            self.duplicate_button.setText("○  Не пропускать дубликаты")

    # --------------------------------------------------------
    # LOG
    # --------------------------------------------------------

    def write_log(self, text):
        self.log.append(text)

        scrollbar = (self.log.verticalScrollBar())
        scrollbar.setValue(scrollbar.maximum())

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    def start_check(self):
        archive = (self.archive_edit.text().strip())

        wordlist = (self.wordlist_edit.text().strip())

        unrar = (self.unrar_edit.text().strip())

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

        self.progress.setValue(0)
        self.percent_label.setText("0%")
        self.status_label.setText("Подготовка...")

        self.stats_label.setText(
            "0 проверено  •  "
            "0 пропущено  •  "
            "подготовка"
        )

        self.write_log("")
        self.write_log("════════════════════════════════════")
        self.write_log("  Запуск RAR Password Recovery 2.2")
        self.write_log("════════════════════════════════════")

        mode = (self.verification_combo.currentData())

        skip_duplicates = (self.duplicate_button.isChecked())

        self.checker = PasswordChecker(
            archive_path=archive,
            wordlist_path=wordlist,
            unrar_path=unrar,
            verification_mode=mode,
            skip_duplicates=skip_duplicates,
        )

        self.checker.progress_signal.connect(self.update_progress)
        self.checker.log_signal.connect(self.write_log)
        self.checker.stats_signal.connect(self.stats_label.setText)
        self.checker.found_signal.connect(self.password_found)
        self.checker.finished_signal.connect(self.check_finished)
        self.checker.error_signal.connect(self.check_error)
        self.checker.finished.connect(self.worker_finished)
        self.set_running_ui(True)

        self.checker.start()

    # --------------------------------------------------------
    # PROGRESS
    # --------------------------------------------------------

    def update_progress(self, value):
        self.progress.setValue(value)
        self.percent_label.setText(f"{value}%")

        if value > 0:
            self.status_label.setText(
                "Идёт проверка..."
            )

    # --------------------------------------------------------
    # PAUSE
    # --------------------------------------------------------

    def toggle_pause(self):
        if not self.checker or not self.checker.isRunning():
            return

        if self.pause_button.text().startswith("⏸"):
            self.checker.pause()
            self.pause_button.setText("▶  Продолжить")
            self.status_label.setText("Проверка приостановлена")
            self.write_log("⏸ Проверка приостановлена.")

        else:
            self.checker.resume()
            self.pause_button.setText("⏸  Пауза")
            self.status_label.setText("Возобновление проверки...")
            self.write_log("▶ Проверка возобновлена.")

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    def stop_check(self):
        if self.checker and self.checker.isRunning():
            self.status_label.setText("Остановка...")
            self.write_log("⚠ Запрошена остановка.")
            self.stop_button.setEnabled(False)
            self.checker.stop()

    # --------------------------------------------------------
    # FOUND
    # --------------------------------------------------------

    def password_found(self, password):
        self.status_label.setText("Пароль найден!")
        self.status_dot.setText("●")
        self.write_log("")
        self.write_log("════════════════════════════════════")
        self.write_log("  ✓ ПАРОЛЬ НАЙДЕН")
        self.write_log(f"  Пароль: {password}")
        self.write_log("════════════════════════════════════")

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
        self.write_log(f"→ {message}")

        if "найден" in message.lower():
            self.status_label.setText("Готово — пароль найден")

        elif "останов" in message.lower():
            self.status_label.setText("Проверка остановлена")

        else:
            self.status_label.setText("Проверка завершена")

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    def check_error(self, message):
        self.status_label.setText("Ошибка")

        self.write_log(f"✕ Ошибка: {message}")

        QMessageBox.critical(
            self,
            "Ошибка",
            message,
        )

    # --------------------------------------------------------
    # THREAD FINISHED
    # --------------------------------------------------------

    def worker_finished(self):
        self.set_running_ui(False)

        self.write_log("Поток проверки завершён.")

        if self.checker:
            self.checker.deleteLater()

        self.checker = None

    # --------------------------------------------------------
    # RUNNING UI
    # --------------------------------------------------------

    def set_running_ui(self, running):
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.archive_edit.setEnabled(not running)
        self.wordlist_edit.setEnabled(not running)
        self.unrar_edit.setEnabled(not running)
        self.verification_combo.setEnabled(not running)
        self.duplicate_button.setEnabled(not running)
        self.pause_button.setEnabled(running)

        if not running:
            self.pause_button.setText("⏸  Пауза")

    # --------------------------------------------------------
    # CLOSE
    # --------------------------------------------------------

    def closeEvent(self, event):
        if self.checker and self.checker.isRunning():
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
