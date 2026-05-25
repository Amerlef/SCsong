import csv
import os
from datetime import datetime

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QPushButton, QTableWidget, QTableWidgetItem,
                                QHeaderView, QMenu, QMessageBox, QFileDialog,
                                QAbstractItemView)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShortcut, QKeySequence

import models.song_model as db
from utils.clipboard import copy_to_clipboard


class MainWindow(QMainWindow):
    data_changed = Signal()
    song_added = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SuperChat 点歌记录")
        self.resize(900, 600)
        self._undo_stack: list[dict] = []
        self.setup_ui()
        self.refresh_table()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("＋ 添加点歌")
        add_btn.clicked.connect(self.on_add)
        toolbar.addWidget(add_btn)

        complete_btn = QPushButton("✓ 标记已播 (首行)")
        complete_btn.clicked.connect(self.on_complete_first)
        toolbar.addWidget(complete_btn)

        batch_btn = QPushButton("🗑 批量清除已完成")
        batch_btn.clicked.connect(self.on_batch_delete)
        toolbar.addWidget(batch_btn)

        undo_btn = QPushButton("↩ 撤回")
        undo_btn.clicked.connect(self.on_undo)
        toolbar.addWidget(undo_btn)

        export_btn = QPushButton("📤 导出 CSV")
        export_btn.clicked.connect(self.on_export_csv)
        toolbar.addWidget(export_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+N"), self, self.on_add)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self.on_complete_first)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["序号", "歌名", "发送者", "电池", "BV号", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_context_menu)
        self.table.cellClicked.connect(self.on_cell_clicked)
        layout.addWidget(self.table)

        self.status_to_text = {"pending": "⏳ 待播", "played": "✅ 已播", "skipped": "⏭ 跳过"}

    def refresh_table(self):
        songs = db.get_all_songs()
        self.table.setRowCount(len(songs))
        for i, s in enumerate(songs):
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            name_item = QTableWidgetItem(s["song_name"])
            name_item.setToolTip("点击歌名复制到剪贴板")
            self.table.setItem(i, 1, name_item)
            self.table.setItem(i, 2, QTableWidgetItem(s.get("sender_name", "")))
            battery_item = QTableWidgetItem(str(s.get("battery", 0)))
            battery_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 3, battery_item)
            self.table.setItem(i, 4, QTableWidgetItem(s.get("bv_number", "")))
            status_text = self.status_to_text.get(s["status"], s["status"])
            self.table.setItem(i, 5, QTableWidgetItem(status_text))
            # Store song id in first column
            self.table.item(i, 0).setData(Qt.UserRole, s["id"])

    def on_cell_clicked(self, row: int, col: int):
        if col == 1:  # song name column
            name = self.table.item(row, 1).text()
            copy_to_clipboard(name)
            self.statusBar().showMessage(f"已复制: {name}", 2000)

    def on_add(self):
        from widgets.add_dialog import AddDialog
        from utils.bv_handler import is_bv_number, open_bv_video, extract_bv_number

        dlg = AddDialog(self)
        if dlg.exec() == AddDialog.Accepted:
            data = dlg.get_data()
            if not data["song_name"]:
                return
            song_name = data["song_name"]
            bv_number = ""

            # If the entire input is a BV号, ask for song name
            if is_bv_number(song_name):
                bv_number = song_name
                open_bv_video(bv_number)
                song_name = ""
                from PySide6.QtWidgets import QInputDialog
                song_name, ok = QInputDialog.getText(self, "歌名", "请输入这个 BV 对应的歌名：")
                if not ok or not song_name.strip():
                    return
            else:
                # If text contains a BV号, extract and open it
                bv = extract_bv_number(song_name)
                if bv:
                    bv_number = bv
                    open_bv_video(bv)
                song_name = song_name.strip()

            db.add_song(song_name, data["sender_name"], data["battery"], bv_number)
            self.refresh_table()
            self.data_changed.emit()
            self.song_added.emit()
            self.statusBar().showMessage(f"已添加: {song_name}", 2000)

    def on_complete_first(self):
        pending = db.get_pending_songs()
        if not pending:
            self.statusBar().showMessage("没有待播歌曲", 2000)
            return
        first = pending[0]
        self._undo_stack.append(dict(first))
        db.mark_played(first["id"])
        self.refresh_table()
        self.data_changed.emit()
        self.statusBar().showMessage(f"已标记完成: {first['song_name']}", 2000)

    def on_batch_delete(self):
        songs_to_delete = [s for s in db.get_all_songs() if s["status"] in ("played", "skipped")]
        if not songs_to_delete:
            self.statusBar().showMessage("没有已完成/已跳过的记录", 2000)
            return
        reply = QMessageBox.question(
            self, "确认", f"确定要删除 {len(songs_to_delete)} 条已完成的记录吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._undo_stack.extend(dict(s) for s in songs_to_delete)
            db.batch_delete_played()
            self.refresh_table()
            self.data_changed.emit()
            self.statusBar().showMessage(f"已删除 {len(songs_to_delete)} 条记录", 2000)

    def on_undo(self):
        if not self._undo_stack:
            self.statusBar().showMessage("没有可撤回的操作", 2000)
            return
        record = self._undo_stack.pop()
        db.restore_last_deleted(record)
        self.refresh_table()
        self.data_changed.emit()
        self.statusBar().showMessage(f"已撤回: {record.get('song_name', '')}", 2000)

    def on_export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 CSV", f"点歌记录_{datetime.now():%Y%m%d_%H%M%S}.csv",
            "CSV 文件 (*.csv)"
        )
        if not path:
            return
        songs = db.get_all_songs()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["序号", "歌名", "发送者", "电池", "BV号", "状态", "时间"])
            for i, s in enumerate(songs):
                writer.writerow([
                    i + 1, s["song_name"], s.get("sender_name", ""),
                    s.get("battery", 0), s.get("bv_number", ""),
                    self.status_to_text.get(s["status"], s["status"]),
                    s.get("created_at", "")
                ])
        self.statusBar().showMessage(f"已导出: {path}", 3000)

    def on_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        item = self.table.item(row, 0)
        if not item:
            return
        song_id = item.data(Qt.UserRole)
        songs = db.get_all_songs()
        song = next((s for s in songs if s["id"] == song_id), None)
        if not song:
            return

        menu = QMenu(self)
        copy_action = menu.addAction("📋 复制歌名")
        menu.addSeparator()
        play_action = menu.addAction("✅ 标记已播")
        skip_action = menu.addAction("⏭ 标记跳过")
        menu.addSeparator()
        pending_action = menu.addAction("🔄 恢复待播")
        menu.addSeparator()
        del_action = menu.addAction("🗑 删除此行")
        undo_action = menu.addAction("↩ 撤回")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))

        if action == copy_action:
            copy_to_clipboard(song["song_name"])
            self.statusBar().showMessage(f"已复制: {song['song_name']}", 2000)
        elif action == play_action:
            self._undo_stack.append(dict(song))
            db.mark_played(song_id)
            self.refresh_table()
            self.data_changed.emit()
        elif action == skip_action:
            self._undo_stack.append(dict(song))
            db.mark_skipped(song_id)
            self.refresh_table()
            self.data_changed.emit()
        elif action == pending_action:
            db.restore_last_deleted(song)
            db.delete_song(song_id)
            self.refresh_table()
            self.data_changed.emit()
        elif action == del_action:
            self._undo_stack.append(dict(song))
            db.delete_song(song_id)
            self.refresh_table()
            self.data_changed.emit()
        elif action == undo_action:
            self.on_undo()
