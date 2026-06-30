from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ModuleNotFoundError:
        print("Thiếu PySide6. Hãy cài bằng lệnh:")
        print("py -3.12 -m pip install -r requirements.txt")
        return 1

    from app_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("University Campus Guide")
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
