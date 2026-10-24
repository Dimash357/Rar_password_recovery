import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("RAR Password Recovery")
    app.setApplicationVersion("2.2")
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
