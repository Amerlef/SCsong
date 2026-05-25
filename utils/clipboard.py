from PySide6.QtWidgets import QApplication


def copy_to_clipboard(text: str):
    clipboard = QApplication.clipboard()
    clipboard.setText(text)
