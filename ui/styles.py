APP_STYLE = """
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
    
    QPushButton#pauseButton {
        background: #253a62;
        border: 1px solid #3e62a1;
        border-radius: 10px;
        padding: 13px;
        font-size: 15px;
        font-weight: 700;
    }

    QPushButton#pauseButton:hover {
        background: #304b79;
    }
    
    QPushButton#pauseButton:disabled {
        background: #181b21;
        color: #555d6b;
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