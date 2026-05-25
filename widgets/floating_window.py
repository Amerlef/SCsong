from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                   QLineEdit, QPushButton, QListWidget, QListWidgetItem,
                                   QSlider, QMenu, QSizeGrip, QFrame)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QRect
from PySide6.QtGui import QFont, QShortcut, QKeySequence, QCursor

import models.song_model as db
from utils.clipboard import copy_to_clipboard
from utils.bv_handler import is_bv_number, open_bv_video, extract_bv_number
from utils.config import load_config, save_config


class Toast(QWidget):
    """Floating toast notification for copy feedback."""

    def __init__(self, parent: QWidget, text: str):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        label = QLabel(text, self)
        label.setStyleSheet(
            "background:#dd4444;color:#fff;padding:6px 14px;"
            "border-radius:6px;font-size:13px;font-weight:bold;"
        )
        label.setFont(QFont("Microsoft YaHei", 10))
        label.adjustSize()
        self.resize(label.size())

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)

    def show_at(self, pos: QPoint):
        self.move(pos)
        self.show()
        self._timer.start(1500)


class FloatingWindow(QWidget):
    data_changed = Signal()
    song_added = Signal()

    def __init__(self):
        super().__init__()
        self._config = load_config()

        w = self._config.get("float_width", 320)
        h = self._config.get("float_height", 500)
        self._bg_r = self._config.get("bg_r", 42)
        self._bg_g = self._config.get("bg_g", 42)
        self._bg_b = self._config.get("bg_b", 62)
        self._bg_alpha = self._config.get("bg_alpha", 230)

        self.resize(w, h)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._undo_stack: list[dict] = []
        self._drag_pos: QPoint | None = None
        self._resize_grip: QSizeGrip | None = None
        self._settings_visible = False

        self.setup_ui()
        self.refresh_list()

    # ---- Stylesheet builder ----
    def _bg_rgba(self, alpha: int | None = None) -> str:
        a = alpha if alpha is not None else self._bg_alpha
        return f"rgba({self._bg_r},{self._bg_g},{self._bg_b},{a})"

    def _apply_style(self):
        """Rebuild stylesheet with current colors."""
        bg1 = self._bg_rgba()
        # slightly lighter variant for gradient
        r2 = min(self._bg_r + 20, 255)
        g2 = min(self._bg_g + 20, 255)
        b2 = min(self._bg_b + 20, 255)
        bg2 = f"rgba({r2},{g2},{b2},{self._bg_alpha})"

        border_c = f"rgba({min(self._bg_r+40,255)},{min(self._bg_g+40,255)},{min(self._bg_b+40,255)},180)"

        self.setStyleSheet(f"""
            QWidget#floating_root {{
                background: qlineargradient(x1:0,y1:0, x2:0,y2:1,
                    stop:0 {bg1}, stop:1 {bg2});
                border-radius: 12px;
                border: 1px solid {border_c};
            }}
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
                color: #e8e8f0;
                font-size: 13px;
            }}
            QListWidget::item {{
                background: rgba(255,255,255,0.05);
                border-bottom: 1px solid rgba(255,255,255,0.06);
                padding: 8px 10px;
                border-radius: 4px;
            }}
            QListWidget::item:hover {{
                background: rgba(255,255,255,0.12);
            }}
            QListWidget::item:selected {{
                background: rgba(180,160,255,0.25);
            }}
            QPushButton {{
                background: rgba(255,255,255,0.08);
                color: #d0d0e0;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.16);
                color: #fff;
            }}
            QPushButton#settings_btn {{
                background: transparent;
                border: none;
                font-size: 15px;
                padding: 2px 6px;
            }}
            QPushButton#settings_btn:hover {{
                background: rgba(255,255,255,0.1);
            }}
            QPushButton#complete_btn {{
                background: rgba(100,200,120,0.20);
                border-color: rgba(100,200,120,0.35);
                color: #a0e0b0;
            }}
            QPushButton#complete_btn:hover {{
                background: rgba(100,200,120,0.35);
            }}
            QPushButton#undo_btn {{
                background: rgba(200,160,60,0.20);
                border-color: rgba(200,160,60,0.35);
                color: #e0c080;
            }}
            QPushButton#undo_btn:hover {{
                background: rgba(200,160,60,0.35);
            }}
            QPushButton#add_btn {{
                background: rgba(120,140,220,0.20);
                border-color: rgba(120,140,220,0.35);
                color: #a0b0f0;
            }}
            QPushButton#add_btn:hover {{
                background: rgba(120,140,220,0.35);
            }}
            QLineEdit {{
                background: rgba(255,255,255,0.07);
                color: #e8e8f0;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: rgba(140,140,220,0.6);
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgba(255,255,255,0.1);
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 12px;
                height: 12px;
                margin: -4px 0;
                background: #8888cc;
                border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #aaaadd;
            }}
            QFrame#settings_panel {{
                background: rgba(0,0,0,0.25);
                border-radius: 8px;
                padding: 4px;
            }}
            QLabel#title_label {{
                color: #ccccee;
                font-size: 13px;
                font-weight: bold;
            }}
            QLabel#sub_label {{
                color: #8888aa;
                font-size: 11px;
            }}
            QLabel#setting_label {{
                color: #aaaacc;
                font-size: 11px;
            }}
        """)

    def setup_ui(self):
        # Main container
        container = QWidget(self)
        container.setObjectName("floating_root")
        container.setGeometry(2, 2, self.width() - 4, self.height() - 4)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        # --- Header ---
        header = QHBoxLayout()
        title = QLabel("点歌队列")
        title.setObjectName("title_label")
        header.addWidget(title)

        count_label = QLabel("")
        count_label.setObjectName("sub_label")
        header.addWidget(count_label)
        self._count_label = count_label

        header.addStretch()

        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("settings_btn")
        settings_btn.setToolTip("显示设置")
        settings_btn.clicked.connect(self._toggle_settings)
        header.addWidget(settings_btn)

        layout.addLayout(header)

        # --- Settings panel (hidden by default) ---
        self._settings_panel = QFrame()
        self._settings_panel.setObjectName("settings_panel")
        self._settings_panel.setVisible(False)
        s_layout = QVBoxLayout(self._settings_panel)
        s_layout.setContentsMargins(8, 6, 8, 6)
        s_layout.setSpacing(6)

        # Row: width / height
        wh_row = QHBoxLayout()
        wh_row.addWidget(QLabel("宽"))
        w_slider = QSlider(Qt.Horizontal)
        w_slider.setRange(200, 600)
        w_slider.setValue(self.width())
        w_slider.valueChanged.connect(self._on_width_change)
        wh_row.addWidget(w_slider)
        self._w_label = QLabel(str(self.width()))
        self._w_label.setObjectName("setting_label")
        self._w_label.setFixedWidth(28)
        wh_row.addWidget(self._w_label)

        wh_row.addWidget(QLabel("高"))
        h_slider = QSlider(Qt.Horizontal)
        h_slider.setRange(200, 800)
        h_slider.setValue(self.height())
        h_slider.valueChanged.connect(self._on_height_change)
        wh_row.addWidget(h_slider)
        self._h_label = QLabel(str(self.height()))
        self._h_label.setObjectName("setting_label")
        self._h_label.setFixedWidth(28)
        wh_row.addWidget(self._h_label)
        s_layout.addLayout(wh_row)

        # Row: transparency (background alpha)
        tp_row = QHBoxLayout()
        tp_row.addWidget(QLabel("透明"))
        a_slider = QSlider(Qt.Horizontal)
        a_slider.setRange(60, 255)
        a_slider.setValue(self._bg_alpha)
        a_slider.valueChanged.connect(self._on_alpha_change)
        tp_row.addWidget(a_slider)
        self._a_label = QLabel(str(self._bg_alpha))
        self._a_label.setObjectName("setting_label")
        self._a_label.setFixedWidth(28)
        tp_row.addWidget(self._a_label)
        s_layout.addLayout(tp_row)

        # Row: R / G / B
        for label, getter, setter_key in [
            ("R", self._bg_r, "bg_r"),
            ("G", self._bg_g, "bg_g"),
            ("B", self._bg_b, "bg_b"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 120)
            slider.setValue(getattr(self, f"_bg_{label.lower()}"))
            slider.valueChanged.connect(
                lambda v, c=label.lower(): self._on_rgb_change(c, v)
            )
            row.addWidget(slider)
            val_label = QLabel(str(getattr(self, f"_bg_{label.lower()}")))
            val_label.setObjectName("setting_label")
            val_label.setFixedWidth(28)
            row.addWidget(val_label)
            setattr(self, f"_{label.lower()}_label", val_label)
            s_layout.addLayout(row)

        layout.addWidget(self._settings_panel)

        # --- Song list ---
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.on_context_menu)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        # --- Input bar ---
        input_layout = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("歌名或 BV 号，回车添加")
        self.input_box.returnPressed.connect(self.on_input_submit)
        input_layout.addWidget(self.input_box)
        layout.addLayout(input_layout)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        complete_btn = QPushButton("完成")
        complete_btn.setObjectName("complete_btn")
        complete_btn.clicked.connect(self.on_complete_first)
        btn_layout.addWidget(complete_btn)

        undo_btn = QPushButton("撤回")
        undo_btn.setObjectName("undo_btn")
        undo_btn.clicked.connect(self.on_undo)
        btn_layout.addWidget(undo_btn)

        add_btn = QPushButton("添加")
        add_btn.setObjectName("add_btn")
        add_btn.clicked.connect(self.on_add_clicked)
        btn_layout.addWidget(add_btn)

        layout.addLayout(btn_layout)

        # Size grip (bottom-right corner)
        grip = QSizeGrip(self)
        grip.setFixedSize(14, 14)
        grip.setStyleSheet("background: transparent;")
        grip.move(self.width() - 16, self.height() - 16)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+N"), self, self.on_add_clicked)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self.on_complete_first)

        self._apply_style()

    # ---- Settings handlers ----
    def _toggle_settings(self):
        self._settings_visible = not self._settings_visible
        self._settings_panel.setVisible(self._settings_visible)

    def _on_width_change(self, v):
        self._w_label.setText(str(v))
        self.resize(v, self.height())
        self._config["float_width"] = v
        save_config(self._config)

    def _on_height_change(self, v):
        self._h_label.setText(str(v))
        self.resize(self.width(), v)
        self._config["float_height"] = v
        save_config(self._config)

    def _on_alpha_change(self, v):
        self._a_label.setText(str(v))
        self._bg_alpha = v
        self._config["bg_alpha"] = v
        save_config(self._config)
        self._apply_style()

    def _on_rgb_change(self, channel: str, v: int):
        setattr(self, f"_bg_{channel}", v)
        self._config[f"bg_{channel}"] = v
        label = getattr(self, f"_{channel}_label", None)
        if label:
            label.setText(str(v))
        save_config(self._config)
        self._apply_style()

    # ---- Drag / Resize ----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        c = self.findChild(QWidget, "floating_root")
        if c:
            c.setGeometry(2, 2, self.width() - 4, self.height() - 4)
        # Reposition size grip
        for child in self.children():
            if isinstance(child, QSizeGrip):
                child.move(self.width() - 16, self.height() - 16)
        super().resizeEvent(event)

    # ---- Data refresh ----
    def refresh_list(self):
        self.list_widget.clear()
        songs = db.get_pending_songs()
        for i, s in enumerate(songs):
            text = f"{i + 1}. {s['song_name']}"
            if s.get("sender_name"):
                text += f"  — {s['sender_name']}"
            if s.get("battery"):
                text += f"  [{s['battery']}⚡]"

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, s["id"])
            item.setToolTip("左键点击复制歌名  |  右键更多操作")
            self.list_widget.addItem(item)

        self._count_label.setText(f"共 {len(songs)} 首")

    # ---- Interactions ----
    def _get_song_from_item(self, item: QListWidgetItem) -> dict | None:
        song_id = item.data(Qt.UserRole)
        songs = db.get_pending_songs()
        return next((s for s in songs if s["id"] == song_id), None)

    def on_item_clicked(self, item: QListWidgetItem):
        song = self._get_song_from_item(item)
        if song:
            copy_to_clipboard(song["song_name"])
            toast = Toast(None, f"已复制: {song['song_name']}")
            toast.show_at(QCursor.pos() + QPoint(10, 10))

    def on_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        song = self._get_song_from_item(item)
        if not song:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #2a2a3e;
                border: 1px solid #5a5a7a;
                border-radius: 6px;
                padding: 4px;
                color: #e0e0f0;
            }
            QMenu::item {
                padding: 6px 28px 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: rgba(140,140,220,0.3);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255,255,255,0.08);
                margin: 3px 8px;
            }
        """)

        copy_action = menu.addAction("📋  复制歌名")

        menu.addSeparator()

        status_menu = QMenu("状态标记", menu)
        status_menu.setStyleSheet(menu.styleSheet())
        play_action = status_menu.addAction("✅  标记已播")
        skip_action = status_menu.addAction("⏭  标记跳过")
        pend_action = status_menu.addAction("🔄  恢复待播")
        menu.addMenu(status_menu)

        menu.addSeparator()
        del_action = menu.addAction("🗑  删除")
        undo_action = menu.addAction("↩  撤回")

        action = menu.exec(self.list_widget.viewport().mapToGlobal(pos))

        if action == copy_action:
            copy_to_clipboard(song["song_name"])
            toast = Toast(None, f"已复制: {song['song_name']}")
            toast.show_at(QCursor.pos() + QPoint(10, 10))
        elif action == play_action:
            self._undo_stack.append(dict(song))
            db.mark_played(song["id"])
            self.refresh_list()
            self.data_changed.emit()
        elif action == skip_action:
            self._undo_stack.append(dict(song))
            db.mark_skipped(song["id"])
            self.refresh_list()
            self.data_changed.emit()
        elif action == pend_action:
            db.restore_last_deleted(song)
            db.delete_song(song["id"])
            self.refresh_list()
            self.data_changed.emit()
        elif action == del_action:
            self._undo_stack.append(dict(song))
            db.delete_song(song["id"])
            self.refresh_list()
            self.data_changed.emit()
        elif action == undo_action:
            self.on_undo()

    # ---- Actions ----
    def on_input_submit(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()

        bv = extract_bv_number(text)
        if bv:
            open_bv_video(bv)

        db.add_song(text)
        self.refresh_list()
        self.data_changed.emit()
        self.song_added.emit()

    def on_add_clicked(self):
        from widgets.add_dialog import AddDialog
        dlg = AddDialog(self)
        if dlg.exec() == AddDialog.Accepted:
            data = dlg.get_data()
            if not data["song_name"]:
                return
            song_name = data["song_name"]
            bv_number = ""

            if is_bv_number(song_name):
                bv_number = song_name
                open_bv_video(bv_number)
                from PySide6.QtWidgets import QInputDialog
                song_name, ok = QInputDialog.getText(self, "歌名", "请输入这个 BV 对应的歌名：")
                if not ok or not song_name.strip():
                    return
                song_name = song_name.strip()
            else:
                bv = extract_bv_number(song_name)
                if bv:
                    bv_number = bv
                    open_bv_video(bv)

            db.add_song(song_name, data["sender_name"], data["battery"], bv_number)
            self.refresh_list()
            self.data_changed.emit()
            self.song_added.emit()

    def on_complete_first(self):
        pending = db.get_pending_songs()
        if not pending:
            return
        first = pending[0]
        self._undo_stack.append(dict(first))
        db.mark_played(first["id"])
        self.refresh_list()
        self.data_changed.emit()

    def on_undo(self):
        if not self._undo_stack:
            return
        record = self._undo_stack.pop()
        db.restore_last_deleted(record)
        self.refresh_list()
        self.data_changed.emit()
