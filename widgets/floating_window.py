from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                   QLineEdit, QPushButton, QListWidget, QListWidgetItem,
                                   QSlider, QMenu, QSizeGrip, QFrame, QAbstractItemView,
                                   QGraphicsOpacityEffect)
from PySide6.QtCore import (Qt, Signal, QTimer, QPoint, QMimeData,
                              QPropertyAnimation, QEasingCurve)
from PySide6.QtGui import QFont, QShortcut, QKeySequence, QCursor, QDrag

import models.song_model as db
from utils.clipboard import copy_to_clipboard
from utils.bv_handler import is_bv_number, open_bv_video, extract_bv_number
from utils.config import load_config, save_config


class _DragListWidget(QListWidget):
    """QListWidget that emits a signal when an item is dropped from another list."""

    item_dropped_from_other = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)

    def dropEvent(self, event):
        source = event.source()
        if source is not None and source is not self:
            item = source.currentItem()
            if item:
                song_id = item.data(Qt.UserRole)
                self.item_dropped_from_other.emit(song_id)
                event.accept()
                return
        super().dropEvent(event)


class FloatingWindow(QWidget):
    data_changed = Signal()
    song_added = Signal()

    def __init__(self):
        super().__init__()
        self._config = load_config()

        w = self._config.get("float_width", 320)
        h = self._config.get("float_height", 550)
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
        self._settings_visible = False

        self.setup_ui()
        self.refresh_all()

    # ---- Style ----
    def _bg_rgba(self) -> str:
        return f"rgba({self._bg_r},{self._bg_g},{self._bg_b},{self._bg_alpha})"

    def _apply_style(self):
        bg1 = self._bg_rgba()
        r2, g2, b2 = min(self._bg_r + 20, 255), min(self._bg_g + 20, 255), min(self._bg_b + 20, 255)
        bg2 = f"rgba({r2},{g2},{b2},{self._bg_alpha})"
        border = f"rgba({min(self._bg_r+40,255)},{min(self._bg_g+40,255)},{min(self._bg_b+40,255)},180)"

        self.setStyleSheet(f"""
            QWidget#floating_root {{
                background: qlineargradient(x1:0,y1:0, x2:0,y2:1, stop:0 {bg1}, stop:1 {bg2});
                border-radius: 12px; border: 1px solid {border};
            }}
            QListWidget {{
                background: transparent; border: none; outline: none;
                color: #e8e8f0; font-size: 13px;
            }}
            QListWidget::item {{
                background: rgba(255,255,255,0.05);
                border-bottom: 1px solid rgba(255,255,255,0.06);
                padding: 6px 8px; border-radius: 4px;
            }}
            QListWidget::item:hover {{ background: rgba(255,255,255,0.12); }}
            QListWidget::item:selected {{ background: rgba(180,160,255,0.25); }}
            QPushButton {{
                background: rgba(255,255,255,0.08); color: #d0d0e0;
                border: 1px solid rgba(255,255,255,0.12); border-radius: 6px;
                padding: 6px 10px; font-size: 12px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.16); color: #fff; }}
            QPushButton#settings_btn {{
                background: transparent; border: none; font-size: 15px; padding: 2px 6px;
            }}
            QPushButton#settings_btn:hover {{ background: rgba(255,255,255,0.1); }}
            QPushButton#complete_btn {{
                background: rgba(100,200,120,0.20); border-color: rgba(100,200,120,0.35); color: #a0e0b0;
            }}
            QPushButton#complete_btn:hover {{ background: rgba(100,200,120,0.35); }}
            QPushButton#undo_btn {{
                background: rgba(200,160,60,0.20); border-color: rgba(200,160,60,0.35); color: #e0c080;
            }}
            QPushButton#undo_btn:hover {{ background: rgba(200,160,60,0.35); }}
            QPushButton#add_btn {{
                background: rgba(120,140,220,0.20); border-color: rgba(120,140,220,0.35); color: #a0b0f0;
            }}
            QPushButton#add_btn:hover {{ background: rgba(120,140,220,0.35); }}
            QLineEdit {{
                background: rgba(255,255,255,0.07); color: #e8e8f0;
                border: 1px solid rgba(255,255,255,0.12); border-radius: 6px;
                padding: 6px 10px; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: rgba(140,140,220,0.6); }}
            QSlider::groove:horizontal {{
                height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 12px; height: 12px; margin: -4px 0;
                background: #8888cc; border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{ background: #aaaadd; }}
            QFrame#settings_panel {{
                background: rgba(0,0,0,0.25); border-radius: 8px; padding: 4px;
            }}
            QLabel#title_label {{ color: #ccccee; font-size: 13px; font-weight: bold; }}
            QLabel#sub_label {{ color: #8888aa; font-size: 11px; }}
            QLabel#setting_label {{ color: #aaaacc; font-size: 10px; min-width: 16px; }}
            QLabel#section_label {{
                color: #9999bb; font-size: 11px; font-weight: bold; padding: 4px 0 2px 4px;
            }}
        """)

    def setup_ui(self):
        self._container = QWidget(self)
        self._container.setObjectName("floating_root")
        self._container.setGeometry(2, 2, self.width() - 4, self.height() - 4)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # --- Header ---
        header = QHBoxLayout()
        title = QLabel("点歌队列")
        title.setObjectName("title_label")
        header.addWidget(title)
        self._count_label = QLabel("")
        self._count_label.setObjectName("sub_label")
        header.addWidget(self._count_label)
        header.addStretch()

        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("settings_btn")
        settings_btn.setToolTip("显示设置")
        settings_btn.clicked.connect(self._toggle_settings)
        header.addWidget(settings_btn)
        layout.addLayout(header)

        # --- Settings panel ---
        self._settings_panel = QFrame()
        self._settings_panel.setObjectName("settings_panel")
        self._settings_panel.setVisible(False)
        s_layout = QVBoxLayout(self._settings_panel)
        s_layout.setContentsMargins(8, 4, 8, 4)
        s_layout.setSpacing(3)

        def _make_row(label_text, min_v, max_v, init_v, callback):
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setObjectName("setting_label")
            lbl.setFixedWidth(14)
            row.addWidget(lbl)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_v, max_v)
            slider.setValue(init_v)
            slider.valueChanged.connect(callback)
            row.addWidget(slider, stretch=1)
            val = QLabel(str(init_v))
            val.setObjectName("setting_label")
            val.setFixedWidth(24)
            row.addWidget(val)
            return row, slider, val

        row, self._h_slider, self._h_label = _make_row("高", 390, 800, self.height(), self._on_height_change)
        s_layout.addLayout(row)
        row, self._w_slider, self._w_label = _make_row("宽", 200, 600, self.width(), self._on_width_change)
        s_layout.addLayout(row)
        row, self._a_slider, self._a_label = _make_row("透", 60, 255, self._bg_alpha, self._on_alpha_change)
        s_layout.addLayout(row)

        for ch, key in [("R", "bg_r"), ("G", "bg_g"), ("B", "bg_b")]:
            init = self._config.get(key, 42)
            row, slider, vlabel = _make_row(ch, 0, 205, init, lambda v, c=key: self._on_rgb_change(c, v))
            setattr(self, f"_{key}_label", vlabel)
            s_layout.addLayout(row)

        layout.addWidget(self._settings_panel)

        # --- Pending queue ---
        pend_label = QLabel("待播队列（可拖拽排序，拖入下方可部署）")
        pend_label.setObjectName("section_label")
        layout.addWidget(pend_label)

        self.list_widget = _DragListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        self.list_widget.item_dropped_from_other.connect(self._on_dropped_to_pending)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_pending_menu)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.model().rowsMoved.connect(self._on_rows_reordered)
        layout.addWidget(self.list_widget, stretch=3)

        # --- Deploy section ---
        depl_label = QLabel("部署（预约播放，拖入上方可加入队列）")
        depl_label.setObjectName("section_label")
        layout.addWidget(depl_label)

        self.depl_list = _DragListWidget()
        self.depl_list.item_dropped_from_other.connect(self._on_dropped_to_deploy)
        self.depl_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.depl_list.customContextMenuRequested.connect(self._on_deploy_menu)
        self.depl_list.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.depl_list, stretch=1)

        # --- Input ---
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

        # --- Toast label (Android-style bottom toast) ---
        self._toast = QLabel(self._container)
        self._toast.setAlignment(Qt.AlignCenter)
        self._toast.setStyleSheet(
            "background: rgba(40,40,40,220); color: #fff; padding: 10px 22px;"
            "border-radius: 10px; font-size: 13px;"
        )
        self._toast.setFont(QFont("Microsoft YaHei", 10))
        self._toast.hide()
        self._toast_opacity = QGraphicsOpacityEffect(self._toast)
        self._toast_opacity.setOpacity(0.0)
        self._toast.setGraphicsEffect(self._toast_opacity)

        # Size grip
        grip = QSizeGrip(self)
        grip.setFixedSize(14, 14)
        grip.setStyleSheet("background: transparent;")
        grip.move(self.width() - 16, self.height() - 16)

        QShortcut(QKeySequence("Ctrl+N"), self, self.on_add_clicked)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self.on_complete_first)

        self._apply_style()

    # ---- Toast ----
    def _show_toast(self, msg: str):
        """Show an Android-style toast at the bottom of the floating window."""
        self._toast.setText(msg)
        self._toast.adjustSize()

        # Position: centered at bottom of container
        cw = self._container.width()
        ch = self._container.height()
        tx = (cw - self._toast.width()) // 2
        ty = ch - self._toast.height() - 20
        self._toast.move(tx, ty)
        self._toast.show()
        self._toast.raise_()

        # Fade in
        self._toast_opacity.setOpacity(0.0)
        anim_in = QPropertyAnimation(self._toast_opacity, b"opacity", self)
        anim_in.setDuration(200)
        anim_in.setStartValue(0.0)
        anim_in.setEndValue(1.0)
        anim_in.setEasingCurve(QEasingCurve.OutCubic)
        anim_in.start()

        # Fade out after 1.5s
        def _fade_out():
            anim_out = QPropertyAnimation(self._toast_opacity, b"opacity", self)
            anim_out.setDuration(300)
            anim_out.setStartValue(1.0)
            anim_out.setEndValue(0.0)
            anim_out.setEasingCurve(QEasingCurve.InCubic)
            anim_out.finished.connect(self._toast.hide)
            anim_out.start()

        QTimer.singleShot(1500, _fade_out)

    # ---- Settings ----
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

    def _on_rgb_change(self, key: str, v: int):
        setattr(self, f"_{key}", v)
        self._config[key] = v
        label = getattr(self, f"_{key}_label", None)
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
        for child in self.children():
            if isinstance(child, QSizeGrip):
                child.move(self.width() - 16, self.height() - 16)
        super().resizeEvent(event)

    # ---- Cross-list drag-drop ----
    def _on_dropped_to_pending(self, song_id: int):
        self._undo_stack.append(
            dict(next((s for s in db.get_deploy_songs() if s["id"] == song_id), {}))
        )
        db.move_to_pending_end(song_id)
        self.refresh_all()
        self.data_changed.emit()

    def _on_dropped_to_deploy(self, song_id: int):
        self._undo_stack.append(
            dict(next((s for s in db.get_pending_songs() if s["id"] == song_id), {}))
        )
        db.mark_deploy(song_id)
        self.refresh_all()
        self.data_changed.emit()

    # ---- Internal reorder ----
    def _on_rows_reordered(self):
        ids = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            ids.append(item.data(Qt.UserRole))
        db.reorder_pending(ids)
        self.data_changed.emit()

    # ---- Refresh ----
    def refresh_all(self):
        self._refresh_list(self.list_widget, db.get_pending_songs())
        self._refresh_list(self.depl_list, db.get_deploy_songs())
        pending = db.get_pending_songs()
        depl = db.get_deploy_songs()
        self._count_label.setText(f"待播 {len(pending)}  ·  部署 {len(depl)}")

    def _refresh_list(self, widget: QListWidget, songs: list[dict]):
        widget.clear()
        for i, s in enumerate(songs):
            text = f"{i + 1}. {s['song_name']}"
            if s.get("sender_name"):
                text += f"  — {s['sender_name']}"
            if s.get("battery"):
                text += f"  [{s['battery']}⚡]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, s["id"])
            item.setToolTip("左键复制  |  右键菜单  |  拖拽移动")
            widget.addItem(item)

    # ---- Item click (copy) ----
    def _get_song_from_item(self, item: QListWidgetItem) -> dict | None:
        song_id = item.data(Qt.UserRole)
        all_songs = db.get_pending_songs() + db.get_deploy_songs()
        return next((s for s in all_songs if s["id"] == song_id), None)

    def on_item_clicked(self, item: QListWidgetItem):
        song = self._get_song_from_item(item)
        if song:
            copy_to_clipboard(song["song_name"])
            self._show_toast(f"已复制: {song['song_name']}")

    # ---- Context menus ----
    def _on_pending_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        song = self._get_song_from_item(item)
        if not song:
            return
        self._show_menu(song, is_deploy=False)

    def _on_deploy_menu(self, pos):
        item = self.depl_list.itemAt(pos)
        if not item:
            return
        song = self._get_song_from_item(item)
        if not song:
            return
        self._show_menu(song, is_deploy=True)

    def _show_menu(self, song: dict, is_deploy: bool):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2a2a3e; border: 1px solid #5a5a7a; border-radius: 6px;
                    padding: 4px; color: #e0e0f0; }
            QMenu::item { padding: 6px 28px 6px 16px; border-radius: 4px; }
            QMenu::item:selected { background: rgba(140,140,220,0.3); }
            QMenu::separator { height: 1px; background: rgba(255,255,255,0.08); margin: 3px 8px; }
        """)

        sid = song["id"]

        a_copy = menu.addAction("📋  复制歌名")
        menu.addSeparator()

        if is_deploy:
            a_move = menu.addAction("🔽  移回待播队尾")
        else:
            a_played = menu.addAction("✅  标记已播")
            a_skip = menu.addAction("⏭  标记跳过")
            a_deploy = menu.addAction("⏸  移到部署区")

        menu.addSeparator()
        a_del = menu.addAction("🗑  删除")
        a_undo = menu.addAction("↩  撤回")

        action = menu.exec(QCursor.pos())
        if not action:
            return

        if action == a_copy:
            copy_to_clipboard(song["song_name"])
            self._show_toast(f"已复制: {song['song_name']}")

        elif not is_deploy and action == a_played:
            self._undo_stack.append(dict(song))
            db.mark_played(sid)
            self.refresh_all()
            self.data_changed.emit()

        elif not is_deploy and action == a_skip:
            self._undo_stack.append(dict(song))
            db.mark_skipped(sid)
            self.refresh_all()
            self.data_changed.emit()

        elif not is_deploy and action == a_deploy:
            self._undo_stack.append(dict(song))
            db.mark_deploy(sid)
            self.refresh_all()
            self.data_changed.emit()

        elif is_deploy and action == a_move:
            self._undo_stack.append(dict(song))
            db.move_to_pending_end(sid)
            self.refresh_all()
            self.data_changed.emit()

        elif action == a_del:
            self._undo_stack.append(dict(song))
            db.delete_song(sid)
            self.refresh_all()
            self.data_changed.emit()

        elif action == a_undo:
            self.on_undo()

    # ---- Input / Add ----
    def on_input_submit(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()

        bv = extract_bv_number(text)
        if bv:
            open_bv_video(bv)

        db.add_song(text)
        self.refresh_all()
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
            add_to_deploy = data.get("to_deploy", False)

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
            if add_to_deploy:
                songs = db.get_pending_songs()
                if songs:
                    db.mark_deploy(songs[-1]["id"])

            self.refresh_all()
            self.data_changed.emit()
            self.song_added.emit()

    def on_complete_first(self):
        pending = db.get_pending_songs()
        if not pending:
            return
        first = pending[0]
        self._undo_stack.append(dict(first))
        db.mark_played(first["id"])
        self.refresh_all()
        self.data_changed.emit()

    def on_undo(self):
        if not self._undo_stack:
            return
        record = self._undo_stack.pop()
        db.restore_last_deleted(record)
        self.refresh_all()
        self.data_changed.emit()
