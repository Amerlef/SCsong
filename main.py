import sys
import os

from PySide6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QMessageBox,
                                   QStyle)
from PySide6.QtGui import QIcon, QAction, QPalette, QColor
from PySide6.QtCore import Qt

import models.song_model as db
from widgets.main_window import MainWindow
from widgets.floating_window import FloatingWindow
from utils.config import load_config, save_config


def apply_dark_theme(app: QApplication):
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.Base, QColor(42, 42, 42))
    dark_palette.setColor(QPalette.AlternateBase, QColor(50, 50, 50))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(50, 50, 50))
    dark_palette.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.Text, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.Button, QColor(50, 50, 50))
    dark_palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(80, 160, 255))
    dark_palette.setColor(QPalette.Highlight, QColor(80, 160, 255))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)
    app.setStyleSheet("""
        QTableWidget { gridline-color: #555; }
        QHeaderView::section { background-color: #3a3a3a; padding: 4px; border: 1px solid #555; }
        QListWidget { background-color: #2a2a2a; border: 1px solid #555; border-radius: 4px; }
        QListWidget::item { padding: 6px 4px; border-bottom: 1px solid #444; }
        QListWidget::item:hover { background-color: #3a3a3a; }
        QListWidget::item:selected { background-color: #4040a0; }
        QPushButton { padding: 5px 12px; border: 1px solid #666; border-radius: 3px; background: #444; }
        QPushButton:hover { background: #555; }
        QPushButton:pressed { background: #333; }
        QLineEdit { padding: 4px 8px; border: 1px solid #666; border-radius: 3px; background: #3a3a3a; }
        QSpinBox { padding: 4px 8px; border: 1px solid #666; border-radius: 3px; background: #3a3a3a; }
    """)


def main():
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"), exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("SuperChat 点歌记录")
    app.setOrganizationName("SCsong")

    config = load_config()
    if config.get("dark_theme", True):
        apply_dark_theme(app)

    db.init_db()

    # Create windows
    floating = FloatingWindow()
    main_win = MainWindow()

    # Sync signals: when one window changes data, refresh the other
    floating.data_changed.connect(main_win.refresh_table)
    main_win.data_changed.connect(floating.refresh_list)

    floating.song_added.connect(main_win.refresh_table)
    main_win.song_added.connect(floating.refresh_list)

    # System tray
    tray_icon = QSystemTrayIcon()
    # Use a simple built-in icon
    tray_icon.setIcon(app.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    tray_menu = QMenu()
    show_floating_action = QAction("悬浮窗", tray_menu)
    show_floating_action.triggered.connect(lambda: (floating.show(), floating.raise_()))
    tray_menu.addAction(show_floating_action)

    show_main_action = QAction("主窗口", tray_menu)
    show_main_action.triggered.connect(lambda: (main_win.show(), main_win.raise_()))
    tray_menu.addAction(show_main_action)

    tray_menu.addSeparator()

    quit_action = QAction("退出", tray_menu)
    quit_action.triggered.connect(app.quit)
    tray_menu.addAction(quit_action)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # Show windows
    floating.show()
    main_win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
