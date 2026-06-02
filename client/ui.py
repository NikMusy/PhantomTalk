"""PyQt6 UI for PhantomTalk - TS3-style channel browser, push-to-talk, settings."""
from __future__ import annotations

import sys
import time
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeyEvent, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QSlider, QSplitter,
    QStackedWidget, QStatusBar, QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from audio import AudioEngine, list_devices, FRAME_SAMPLES, SAMPLE_RATE
from net import NetClient, http_json


# --------------------------- styles ----------------------------------------

DARK_QSS = """
* { font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 10pt; }
QMainWindow, QDialog { background:#0f1115; color:#e6e8ee; }
QWidget { background:#0f1115; color:#e6e8ee; }
QTreeWidget, QListWidget, QTextEdit, QLineEdit, QComboBox {
    background:#171a21; color:#e6e8ee; border:1px solid #232733; border-radius:6px;
    padding:4px;
}
QTreeWidget::item:selected, QListWidget::item:selected { background:#2a3145; }
QPushButton {
    background:#2563eb; color:white; border:none; padding:8px 14px; border-radius:6px;
    font-weight:600;
}
QPushButton:hover { background:#1e4fd4; }
QPushButton:disabled { background:#374151; color:#9aa3b2; }
QPushButton.ghost { background:#1f2430; color:#e6e8ee; }
QPushButton.ghost:hover { background:#2a3145; }
QPushButton.danger { background:#dc2626; }
QPushButton.danger:hover { background:#b91c1c; }
QProgressBar { background:#171a21; border:1px solid #232733; border-radius:4px; text-align:center; height:8px; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #22c55e, stop:0.7 #eab308, stop:1 #ef4444); border-radius:4px; }
QSlider::groove:horizontal { border:1px solid #232733; height:6px; background:#171a21; border-radius:3px; }
QSlider::handle:horizontal { background:#2563eb; width:16px; margin:-6px 0; border-radius:8px; }
QHeaderView::section, QTreeView::branch { background:#0f1115; color:#94a3b8; border:none; }
QStatusBar { background:#0b0d12; color:#94a3b8; }
QTabBar::tab { background:#0f1115; padding:8px 12px; color:#94a3b8; }
QTabBar::tab:selected { color:#e6e8ee; border-bottom:2px solid #2563eb; }
QLabel.h1 { font-size:22pt; font-weight:700; }
QLabel.dim { color:#9aa3b2; }
"""


# --------------------------- login dialog ----------------------------------

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PhantomTalk — вход")
        self.setMinimumWidth(420)
        v = QVBoxLayout(self)

        title = QLabel("PhantomTalk")
        title.setProperty("class", "h1")
        title.setStyleSheet("font-size:24pt; font-weight:800; color:#e6e8ee;")
        sub = QLabel("Голосовая связь нового поколения · Opus 510 кбит/с")
        sub.setStyleSheet("color:#9aa3b2;")
        v.addWidget(title); v.addWidget(sub)
        v.addSpacing(12)

        form = QFormLayout()
        self.server_url = QLineEdit("http://127.0.0.1:9050")
        self.nick = QLineEdit("Phantom")
        form.addRow("Адрес сервера:", self.server_url)
        form.addRow("Никнейм:", self.nick)
        v.addLayout(form)

        self.servers_list = QListWidget()
        self.servers_list.setMinimumHeight(160)
        v.addWidget(QLabel("Доступные комнаты:"))
        v.addWidget(self.servers_list, 1)

        btns = QHBoxLayout()
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.setProperty("class", "ghost")
        self.refresh_btn.setStyleSheet("background:#1f2430;")
        self.create_btn = QPushButton("Создать сервер…")
        self.create_btn.setProperty("class", "ghost")
        self.create_btn.setStyleSheet("background:#1f2430;")
        self.connect_btn = QPushButton("Войти")
        btns.addWidget(self.refresh_btn); btns.addWidget(self.create_btn); btns.addStretch(); btns.addWidget(self.connect_btn)
        v.addLayout(btns)

        self.refresh_btn.clicked.connect(self.refresh)
        self.create_btn.clicked.connect(self.create_server)
        self.connect_btn.clicked.connect(self._accept)
        self.servers_list.itemDoubleClicked.connect(lambda *_: self._accept())

        self.selected_server_id: Optional[int] = None
        QTimer.singleShot(150, self.refresh)

    def refresh(self):
        self.servers_list.clear()
        try:
            data = http_json("GET", f"{self.server_url.text().rstrip('/')}/api/servers")
        except Exception as e:
            self.servers_list.addItem(f"[ошибка] {e}")
            return
        if not data:
            self.servers_list.addItem("(нет публичных серверов)")
            return
        for s in data:
            it = QListWidgetItem(f"#{s['id']}  {s['name']}    ({s['online']}/{s['max_users']})  — {s['description']}")
            it.setData(Qt.ItemDataRole.UserRole, s["id"])
            self.servers_list.addItem(it)

    def create_server(self):
        name, ok = QInputDialog.getText(self, "Новый сервер", "Название сервера:")
        if not ok or not name.strip():
            return
        desc, _ = QInputDialog.getText(self, "Новый сервер", "Описание (необязательно):")
        try:
            data = http_json("POST", f"{self.server_url.text().rstrip('/')}/api/servers",
                             {"name": name.strip(), "description": desc.strip(), "public": True, "max_users": 64})
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))
            return
        QMessageBox.information(self, "Сервер создан",
                                f"ID: {data['id']}\nAdmin token (сохраните для управления):\n{data['admin_token']}")
        self.refresh()

    def _accept(self):
        it = self.servers_list.currentItem()
        if it is not None:
            sid = it.data(Qt.ItemDataRole.UserRole)
            if isinstance(sid, int):
                self.selected_server_id = sid
        if self.selected_server_id is None:
            QMessageBox.warning(self, "Выбор", "Выберите сервер из списка.")
            return
        self.accept()


# --------------------------- main window -----------------------------------

class MainWindow(QMainWindow):
    def __init__(self, base_url: str, server_id: int, nickname: str):
        super().__init__()
        self.setWindowTitle(f"PhantomTalk — {nickname}")
        self.resize(1100, 700)
        self.base_url = base_url
        self.server_id = server_id
        self.nickname = nickname

        self.net = NetClient(base_url)
        self.engine = AudioEngine(send_frame=self.net.send_voice)
        self._ptt_enabled = True
        self._ptt_key = Qt.Key.Key_Space
        self._voice_activation = False
        self._muted = False
        self._deafened = False
        self._channels: Dict[int, str] = {}
        self._users_by_token: Dict[str, dict] = {}

        self._build_ui()
        self._wire_net()

        self.engine.start()
        self.net.connect(server_id, nickname)

        self.meter_timer = QTimer(self)
        self.meter_timer.timeout.connect(self._tick_meters)
        self.meter_timer.start(60)

    # ---------------- UI ----------------
    def _build_ui(self):
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("подключение…")

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: server info + channel tree
        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(8, 8, 8, 8)
        self.server_label = QLabel("(сервер)"); self.server_label.setStyleSheet("font-weight:700; font-size:13pt;")
        lv.addWidget(self.server_label)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._on_tree_dbl)
        lv.addWidget(self.tree, 1)
        new_chan = QPushButton("+  Создать канал")
        new_chan.setStyleSheet("background:#1f2430;")
        new_chan.clicked.connect(self._create_channel)
        lv.addWidget(new_chan)
        splitter.addWidget(left)

        # Right: tabs (chat + settings)
        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(8, 8, 8, 8)

        tabs = QTabWidget()
        # ---- chat tab
        chat_tab = QWidget(); ct = QVBoxLayout(chat_tab)
        self.chat_view = QTextEdit(); self.chat_view.setReadOnly(True)
        self.chat_input = QLineEdit(); self.chat_input.setPlaceholderText("Сообщение в канал… (Enter — отправить)")
        self.chat_input.returnPressed.connect(self._send_chat)
        ct.addWidget(self.chat_view, 1); ct.addWidget(self.chat_input)
        tabs.addTab(chat_tab, "Чат")

        # ---- settings tab
        st_tab = QWidget(); sl = QFormLayout(st_tab)
        in_devs, out_devs = list_devices()
        self.input_dev = QComboBox()
        for idx, name in in_devs:
            self.input_dev.addItem(f"{name}", idx)
        self.output_dev = QComboBox()
        for idx, name in out_devs:
            self.output_dev.addItem(f"{name}", idx)
        self.input_dev.currentIndexChanged.connect(self._reopen_devices)
        self.output_dev.currentIndexChanged.connect(self._reopen_devices)

        self.mic_gain = QSlider(Qt.Orientation.Horizontal); self.mic_gain.setRange(0, 400); self.mic_gain.setValue(100)
        self.mic_gain.valueChanged.connect(lambda v: self.engine.set_mic_gain(v/100.0))
        self.out_gain = QSlider(Qt.Orientation.Horizontal); self.out_gain.setRange(0, 400); self.out_gain.setValue(100)
        self.out_gain.valueChanged.connect(lambda v: self.engine.set_out_gain(v/100.0))

        self.va_check = QCheckBox("Голосовая активация (вместо PTT)")
        self.va_check.stateChanged.connect(lambda *_: setattr(self, "_voice_activation", self.va_check.isChecked()))

        self.bitrate = QComboBox()
        for kb in (64, 96, 128, 192, 256, 320, 384, 510):
            self.bitrate.addItem(f"{kb} кбит/с" + ("  ← выше Discord Nitro" if kb >= 384 else ""), kb*1000)
        self.bitrate.setCurrentIndex(7)
        self.bitrate.currentIndexChanged.connect(self._apply_bitrate)

        sl.addRow("Микрофон:", self.input_dev)
        sl.addRow("Динамики:", self.output_dev)
        sl.addRow("Усиление микрофона:", self.mic_gain)
        sl.addRow("Громкость воспроизведения:", self.out_gain)
        sl.addRow("", self.va_check)
        sl.addRow("Битрейт Opus:", self.bitrate)
        info = QLabel(
            "PhantomTalk использует Opus 48 кГц стерео, 20 мс, до 510 кбит/с.\n"
            "Discord ограничен 96 кбит/с (Nitro: до 384 кбит/с) и моно для голоса."
        )
        info.setStyleSheet("color:#9aa3b2;"); info.setWordWrap(True)
        sl.addRow(info)
        tabs.addTab(st_tab, "Настройки")

        rv.addWidget(tabs, 1)

        # bottom bar: meters + controls
        bottom = QWidget(); bl = QHBoxLayout(bottom); bl.setContentsMargins(0, 4, 0, 0)
        self.in_meter = QProgressBar(); self.in_meter.setRange(0, 100); self.in_meter.setTextVisible(False); self.in_meter.setFixedHeight(10)
        self.out_meter = QProgressBar(); self.out_meter.setRange(0, 100); self.out_meter.setTextVisible(False); self.out_meter.setFixedHeight(10)
        meters = QVBoxLayout()
        m1 = QHBoxLayout(); m1.addWidget(QLabel("MIC ")); m1.addWidget(self.in_meter, 1)
        m2 = QHBoxLayout(); m2.addWidget(QLabel("OUT ")); m2.addWidget(self.out_meter, 1)
        meters.addLayout(m1); meters.addLayout(m2)
        bl.addLayout(meters, 1)

        self.mute_btn = QPushButton("Заглушить мик")
        self.mute_btn.setStyleSheet("background:#1f2430;")
        self.mute_btn.setCheckable(True)
        self.mute_btn.toggled.connect(self._on_mute)
        self.deaf_btn = QPushButton("Не слышать")
        self.deaf_btn.setStyleSheet("background:#1f2430;")
        self.deaf_btn.setCheckable(True)
        self.deaf_btn.toggled.connect(self._on_deafen)
        self.ptt_label = QLabel("PTT: SPACE")
        self.ptt_label.setStyleSheet("color:#9aa3b2;")
        bl.addWidget(self.ptt_label); bl.addWidget(self.mute_btn); bl.addWidget(self.deaf_btn)
        rv.addWidget(bottom)

        splitter.addWidget(right)
        splitter.setSizes([320, 780])
        self.setCentralWidget(splitter)

    # ---------------- network glue -----------
    def _wire_net(self):
        self.net.connected.connect(self._on_connected)
        self.net.disconnected.connect(self._on_disconnected)
        self.net.presence.connect(self._on_presence)
        self.net.chat.connect(self._on_chat)
        self.net.channel_added.connect(self._on_channel_added)
        self.net.error.connect(self._on_net_error)
        self.net.voice_packet.connect(self._on_voice)

    def _on_connected(self, welcome):
        self.statusBar().showMessage("в сети · UDP " + str(welcome.get("udp_port", "?")))
        # fetch initial channel list
        try:
            info = http_json("GET", f"{self.base_url.rstrip('/')}/api/servers/{self.server_id}")
        except Exception as e:
            self._on_net_error(str(e)); return
        self.server_label.setText(info["name"])
        self._channels = {c["id"]: c["name"] for c in info["channels"]}
        self._rebuild_tree(info["online"])

    def _on_disconnected(self, reason):
        self.statusBar().showMessage(f"отключено: {reason}")

    def _on_net_error(self, msg):
        self.statusBar().showMessage(f"ошибка: {msg}")

    def _on_presence(self, users):
        self._users_by_token = {u["token"]: u for u in users}
        self._rebuild_tree(users)

    def _on_chat(self, m):
        if m.get("channel_id") != self.net.channel_id:
            return
        ts = time.strftime("%H:%M", time.localtime(m.get("ts", time.time())))
        self.chat_view.append(f"<span style='color:#9aa3b2'>[{ts}]</span> <b>{m['nick']}:</b> {m['text']}")

    def _on_channel_added(self, m):
        self._channels[m["id"]] = m["name"]
        self._rebuild_tree(list(self._users_by_token.values()))

    def _on_voice(self, src_token: bytes, seq: int, payload: bytes):
        if self._deafened:
            return
        self.engine.on_peer_packet(src_token, seq, payload)

    # ---------------- tree -------------
    def _rebuild_tree(self, users):
        self.tree.clear()
        by_chan: Dict[int, list] = {cid: [] for cid in self._channels.keys()}
        by_chan[0] = []  # lobby (no channel)
        for u in users:
            cid = u["channel_id"] or 0
            by_chan.setdefault(cid, []).append(u)
        # lobby first
        if by_chan.get(0):
            lobby = QTreeWidgetItem([f"Вестибюль ({len(by_chan[0])})"])
            lobby.setData(0, Qt.ItemDataRole.UserRole, None)
            self.tree.addTopLevelItem(lobby)
            for u in by_chan[0]:
                self._add_user_node(lobby, u)
            lobby.setExpanded(True)
        for cid, name in self._channels.items():
            members = by_chan.get(cid, [])
            it = QTreeWidgetItem([f"🔊 {name} ({len(members)})"])
            it.setData(0, Qt.ItemDataRole.UserRole, cid)
            if cid == self.net.channel_id:
                f = it.font(0); f.setBold(True); it.setFont(0, f)
            self.tree.addTopLevelItem(it)
            for u in members:
                self._add_user_node(it, u)
            it.setExpanded(True)

    def _add_user_node(self, parent: QTreeWidgetItem, u: dict):
        badge = ""
        if u.get("muted"): badge += " [mute]"
        if u.get("deafened"): badge += " [deaf]"
        ch = QTreeWidgetItem([f"  👤 {u['nick']}{badge}"])
        ch.setData(0, Qt.ItemDataRole.UserRole, ("user", u["token"]))
        parent.addChild(ch)

    def _on_tree_dbl(self, item: QTreeWidgetItem, _col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, int):
            self.net.join_channel(data)
        elif data is None:
            self.net.leave_channel()

    def _create_channel(self):
        name, ok = QInputDialog.getText(self, "Новый канал", "Название:")
        if not ok or not name.strip():
            return
        tok, ok = QInputDialog.getText(self, "Admin token",
                                       "Введите admin token этого сервера:",
                                       QLineEdit.EchoMode.Password)
        if not ok or not tok.strip():
            return
        try:
            http_json("POST",
                      f"{self.base_url.rstrip('/')}/api/servers/{self.server_id}/channels",
                      {"admin_token": tok.strip(), "name": name.strip()})
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    # ---------------- audio controls ----
    def _on_mute(self, m: bool):
        self._muted = m
        self.engine.set_talking(False if m else self._is_transmitting())
        self.net.set_muted(m)

    def _on_deafen(self, d: bool):
        self._deafened = d
        self.net.set_deafened(d)
        if d:
            self.engine.clear_peers()

    def _is_transmitting(self) -> bool:
        if self._muted:
            return False
        if self._voice_activation:
            return True
        # PTT — depends on key state, see keyPress/Release
        return self._ptt_held

    _ptt_held = False

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == self._ptt_key and not e.isAutoRepeat():
            self._ptt_held = True
            self.engine.set_talking(self._is_transmitting())
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent):
        if e.key() == self._ptt_key and not e.isAutoRepeat():
            self._ptt_held = False
            self.engine.set_talking(self._is_transmitting() if self._voice_activation else False)
        super().keyReleaseEvent(e)

    def _send_chat(self):
        txt = self.chat_input.text().strip()
        if not txt or self.net.channel_id is None:
            return
        self.net.send_chat(txt)
        self.chat_input.clear()

    def _reopen_devices(self):
        try:
            self.engine.stop()
            self.engine.input_device = self.input_dev.currentData()
            self.engine.output_device = self.output_dev.currentData()
            self.engine.start()
        except Exception as e:
            QMessageBox.warning(self, "Аудио", f"{e}")

    def _apply_bitrate(self):
        kb = self.bitrate.currentData()
        try:
            self.engine.codec.enc.bitrate = int(kb)
        except Exception:
            pass

    def _tick_meters(self):
        self.in_meter.setValue(int(self.engine.input_level * 100))
        self.out_meter.setValue(int(self.engine.output_level * 100))
        if self._voice_activation:
            self.engine.set_talking(not self._muted)
        elif not self._ptt_held:
            self.engine.set_talking(False)

    def closeEvent(self, e):
        try:
            self.engine.stop()
        except Exception:
            pass
        try:
            self.net.disconnect()
        except Exception:
            pass
        super().closeEvent(e)
