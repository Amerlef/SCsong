from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                   QLineEdit, QSpinBox, QPushButton, QFormLayout,
                                   QCheckBox)
from PySide6.QtCore import Qt


class AddDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加点歌")
        self.setMinimumWidth(350)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.song_input = QLineEdit()
        self.song_input.setPlaceholderText("输入歌名或 BV 号")
        form.addRow("歌名/BV:", self.song_input)

        self.sender_input = QLineEdit()
        self.sender_input.setPlaceholderText("SC 发送者（可选）")
        form.addRow("发送者:", self.sender_input)

        self.battery_input = QSpinBox()
        self.battery_input.setRange(0, 999999)
        self.battery_input.setSuffix(" 电池")
        self.battery_input.setValue(0)
        form.addRow("电池:", self.battery_input)

        layout.addLayout(form)

        self.deploy_check = QCheckBox("添加到部署区（预约播放，不加入待播队列）")
        layout.addWidget(self.deploy_check)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        add_btn = QPushButton("添加")
        add_btn.setDefault(True)
        add_btn.clicked.connect(self.accept)
        btn_layout.addWidget(add_btn)
        layout.addLayout(btn_layout)

        self.song_input.setFocus()

    def get_data(self) -> dict:
        return {
            "song_name": self.song_input.text().strip(),
            "sender_name": self.sender_input.text().strip(),
            "battery": self.battery_input.value(),
            "to_deploy": self.deploy_check.isChecked(),
        }
