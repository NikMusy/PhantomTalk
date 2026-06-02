"""PhantomTalk PyQt6 UI — ember theme, channels + direct messages + 1-on-1 calls + screen share."""
from __future__ import annotations

import base64
import time
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QKeyEvent, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSizePolicy, QSlider, QSplitter,
    QStatusBar, QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from audio import AudioEngine, list_devices
from net import NetClient, http_json
from screen import ScreenCaster
from theme import COLORS, SANS_FAMILY, SERIF_FAMILY, sans, serif


# ============================================================================
# LOGIN
# ============================================================================

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PhantomTalk — вход")
        self.setMinimumSize(560, 620)

        v = QVBoxLayout(self); v.setSpacing(14); v.setContentsMargins(36, 28, 36, 28)

        title = QLabel("PhantomTalk"); title.setFont(serif(36)); title.setStyleSheet(f"color: {COLORS['amber']};")
        sub = QLabel("ГОЛОС · КОТОРЫЙ · СЛЫШНО")
        f = sans(9, QFont.Weight.DemiBold); sub.setFont(f); sub.setStyleSheet(f"color: {COLORS['dim']}; letter-spacing: 3px;")
        v.addWidget(title); v.addWidget(sub); v.addSpacing(10)

        form = QFormLayout()
        self.server_url = QLineEdit("http://127.0.0.1:9050")
        self.nick = QLineEdit("Phantom")
        for w in (self.server_url, self.nick): w.setMinimumHeight(36)
        form.addRow("Адрес сервера:", self.server_url)
        form.addRow("Никнейм:", self.nick)
        v.addLayout(form)

        v.addWidget(QLabel("Доступные комнаты"))
        self.servers_list = QListWidget(); self.servers_list.setMinimumHeight(220)
        v.addWidget(self.servers_list, 1)

        btns = QHBoxLayout()
        self.refresh_btn = QPushButton("Обновить"); self.refresh_btn.setProperty("ghost", True)
        self.create_btn = QPushButton("Создать сервер…"); self.create_btn.setProperty("ghost", True)
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
            self.servers_list.addItem(f"[ошибка] {e}"); return
        if not data:
            self.servers_list.addItem("(нет публичных серверов)"); return
        for s in data:
            it = QListWidgetItem(f"#{s['id']}  ·  {s['name']}    ({s['online']}/{s['max_users']})    — {s['description']}")
            it.setData(Qt.ItemDataRole.UserRole, s["id"]); self.servers_list.addItem(it)

    def create_server(self):
        name, ok = QInputDialog.getText(self, "Новый сервер", "Название сервера:")
        if not ok or not name.strip(): return
        desc, _ = QInputDialog.getText(self, "Новый сервер", "Описание (необязательно):")
        try:
            data = http_json("POST", f"{self.server_url.text().rstrip('/')}/api/servers",
                             {"name": name.strip(), "description": desc.strip(), "public": True, "max_users": 64})
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e)); return
        QMessageBox.information(self, "Сервер создан",
                                f"ID: {data['id']}\nAdmin token (сохраните для управления):\n{data['admin_token']}")
        self.refresh()

    def _accept(self):
        it = self.servers_list.currentItem()
        if it is not None:
            sid = it.data(Qt.ItemDataRole.UserRole)
            if isinstance(sid, int): self.selected_server_id = sid
        if self.selected_server_id is None:
            QMessageBox.warning(self, "Выбор", "Выберите сервер из списка."); return
        self.accept()


# ============================================================================
# SCREEN VIEWER
# ============================================================================

class ScreenViewer(QWidget):
    closed = pyqtSignal()

    def __init__(self, from_nick: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Демонстрация — {from_nick}")
        self.resize(1024, 600)
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(f"Ждём поток от {from_nick}…")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(f"background: #000; color: {COLORS['dim']};")
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        v.addWidget(self.label)

    def set_frame(self, w: int, h: int, jpeg_b64: str):
        try:
            data = base64.b64decode(jpeg_b64)
            img = QImage.fromData(data, "JPEG")
            if img.isNull(): return
            scaled = QPixmap.fromImage(img).scaled(self.label.size(),
                                                   Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation)
            self.label.setPixmap(scaled)
        except Exception:
            pass

    def closeEvent(self, e):
        self.closed.emit(); super().closeEvent(e)


# ============================================================================
# MAIN
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self, base_url: str, server_id: int, nickname: str):
        super().__init__()
        self.setWindowTitle(f"PhantomTalk — {nickname}")
        self.resize(1280, 800)

        self.base_url = base_url
        self.server_id = server_id
        self.nickname = nickname

        self.net = NetClient(base_url)
        self.engine = AudioEngine(send_frame=self.net.send_voice)
        self.screen_caster = ScreenCaster(send_frame=self.net.screen_send_frame)
        self.screen_viewer: Optional[ScreenViewer] = None
        self.in_call_with: Optional[str] = None    # peer token_hex
        self._users_by_token: Dict[str, dict] = {}
        self._channels: Dict[int, str] = {}
        self._dm_threads: Dict[str, list] = {}     # peer_token -> [(nick,text,ts), ...]
        self._dm_open_peer: Optional[str] = None
        self._muted = False
        self._deafened = False
        self._ptt_key = Qt.Key.Key_Space
        self._ptt_held = False
        self._voice_activation = False

        self._build_ui()
        self._wire_net()

        self.engine.start()
        self.net.connect(server_id, nickname)

        self.meter_timer = QTimer(self); self.meter_timer.timeout.connect(self._tick_meters); self.meter_timer.start(60)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.setStatusBar(QStatusBar()); self.statusBar().showMessage("подключение…")

        # Top serif header
        header = QWidget(); hl = QHBoxLayout(header); hl.setContentsMargins(20, 16, 20, 0)
        h_title = QLabel("PhantomTalk"); h_title.setFont(serif(22))
        h_title.setStyleSheet(f"color: {COLORS['amber']};")
        h_nick = QLabel(f"  ·  {self.nickname}"); h_nick.setStyleSheet(f"color: {COLORS['dim']};")
        hl.addWidget(h_title); hl.addWidget(h_nick); hl.addStretch()

        # Main split: tabs left (Каналы / Личка), chat right
        split = QSplitter(Qt.Orientation.Horizontal)

        # ----- LEFT: navigation tabs -----
        left = QTabWidget(); left.setMinimumWidth(330)

        # Channels tab
        chan_tab = QWidget(); cv = QVBoxLayout(chan_tab); cv.setContentsMargins(8, 10, 8, 10)
        self.server_label = QLabel("(сервер)"); self.server_label.setFont(serif(15))
        cv.addWidget(self.server_label)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._on_tree_dbl)
        cv.addWidget(self.tree, 1)
        new_chan = QPushButton("＋  Создать канал"); new_chan.setProperty("ghost", True)
        new_chan.clicked.connect(self._create_channel); cv.addWidget(new_chan)
        left.addTab(chan_tab, "Каналы")

        # Direct messages tab
        dm_tab = QWidget(); dv = QVBoxLayout(dm_tab); dv.setContentsMargins(8, 10, 8, 10)
        dv.addWidget(QLabel("Онлайн на сервере"))
        self.dm_users = QListWidget()
        self.dm_users.itemDoubleClicked.connect(self._open_dm_from_list)
        dv.addWidget(self.dm_users, 1)
        row = QHBoxLayout()
        self.btn_call = QPushButton("📞 Позвонить")
        self.btn_screen = QPushButton("🖥 Демонстрация"); self.btn_screen.setProperty("ghost", True); self.btn_screen.setCheckable(True)
        self.btn_call.clicked.connect(self._call_selected)
        self.btn_screen.toggled.connect(self._screen_toggle)
        row.addWidget(self.btn_call); row.addWidget(self.btn_screen)
        dv.addLayout(row)
        left.addTab(dm_tab, "Личка")

        # ----- RIGHT: chat + settings -----
        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(8, 10, 8, 10)
        self.tabs_right = QTabWidget()

        # Channel chat
        chat = QWidget(); ct = QVBoxLayout(chat)
        self.chat_view = QTextEdit(); self.chat_view.setReadOnly(True)
        self.chat_input = QLineEdit(); self.chat_input.setPlaceholderText("Сообщение в канал… (Enter — отправить)")
        self.chat_input.returnPressed.connect(self._send_chat)
        ct.addWidget(self.chat_view, 1); ct.addWidget(self.chat_input)
        self.tabs_right.addTab(chat, "Чат канала")

        # DM chat
        dmc = QWidget(); dc = QVBoxLayout(dmc)
        self.dm_label = QLabel("Выбери собеседника во вкладке «Личка» слева")
        self.dm_view = QTextEdit(); self.dm_view.setReadOnly(True)
        self.dm_input = QLineEdit(); self.dm_input.setPlaceholderText("Личное сообщение…")
        self.dm_input.returnPressed.connect(self._send_dm)
        dc.addWidget(self.dm_label); dc.addWidget(self.dm_view, 1); dc.addWidget(self.dm_input)
        self.tabs_right.addTab(dmc, "ЛС")

        # Settings
        st = QWidget(); sl = QFormLayout(st)
        in_devs, out_devs = list_devices()
        self.input_dev = QComboBox(); [self.input_dev.addItem(n, i) for i, n in in_devs]
        self.output_dev = QComboBox(); [self.output_dev.addItem(n, i) for i, n in out_devs]
        self.input_dev.currentIndexChanged.connect(self._reopen_devices)
        self.output_dev.currentIndexChanged.connect(self._reopen_devices)
        self.mic_gain = QSlider(Qt.Orientation.Horizontal); self.mic_gain.setRange(0, 400); self.mic_gain.setValue(100)
        self.mic_gain.valueChanged.connect(lambda v: self.engine.set_mic_gain(v / 100.0))
        self.out_gain = QSlider(Qt.Orientation.Horizontal); self.out_gain.setRange(0, 400); self.out_gain.setValue(100)
        self.out_gain.valueChanged.connect(lambda v: self.engine.set_out_gain(v / 100.0))
        self.va_check = QCheckBox("Голосовая активация (вместо PTT)")
        self.va_check.stateChanged.connect(lambda *_: setattr(self, "_voice_activation", self.va_check.isChecked()))
        self.bitrate = QComboBox()
        for kb in (64, 96, 128, 192, 256, 320, 384, 510):
            tail = "  ← выше Discord Nitro" if kb >= 384 else ""
            self.bitrate.addItem(f"{kb} кбит/с{tail}", kb * 1000)
        self.bitrate.setCurrentIndex(7)
        self.bitrate.currentIndexChanged.connect(self._apply_bitrate)
        sl.addRow("Микрофон:", self.input_dev)
        sl.addRow("Динамики:", self.output_dev)
        sl.addRow("Усиление микрофона:", self.mic_gain)
        sl.addRow("Громкость воспроизведения:", self.out_gain)
        sl.addRow("", self.va_check)
        sl.addRow("Битрейт Opus:", self.bitrate)
        sl.addRow(QLabel("PhantomTalk: 48 кГц stereo, 20 мс, до 510 кбит/с\nDiscord: 96 кбит/с моно (Nitro: 384)."))
        self.tabs_right.addTab(st, "Настройки")

        rv.addWidget(self.tabs_right, 1)

        # Bottom transport bar
        bottom = QWidget(); bl = QHBoxLayout(bottom); bl.setContentsMargins(0, 6, 0, 0)
        self.in_meter = QProgressBar(); self.in_meter.setRange(0, 100); self.in_meter.setFixedHeight(9); self.in_meter.setTextVisible(False)
        self.out_meter = QProgressBar(); self.out_meter.setRange(0, 100); self.out_meter.setFixedHeight(9); self.out_meter.setTextVisible(False)
        meters = QVBoxLayout()
        m1 = QHBoxLayout(); m1.addWidget(QLabel("MIC")); m1.addWidget(self.in_meter, 1); meters.addLayout(m1)
        m2 = QHBoxLayout(); m2.addWidget(QLabel("OUT")); m2.addWidget(self.out_meter, 1); meters.addLayout(m2)
        bl.addLayout(meters, 1)
        self.mute_btn = QPushButton("🎙 Заглушить мик"); self.mute_btn.setProperty("ghost", True); self.mute_btn.setCheckable(True); self.mute_btn.toggled.connect(self._on_mute)
        self.deaf_btn = QPushButton("🔇 Не слышать"); self.deaf_btn.setProperty("ghost", True); self.deaf_btn.setCheckable(True); self.deaf_btn.toggled.connect(self._on_deafen)
        self.hangup_btn = QPushButton("⛔ Завершить звонок"); self.hangup_btn.setProperty("danger", True); self.hangup_btn.clicked.connect(self._hangup); self.hangup_btn.setVisible(False)
        self.ptt_label = QLabel("PTT: SPACE"); self.ptt_label.setStyleSheet(f"color: {COLORS['dim']};")
        bl.addWidget(self.ptt_label); bl.addWidget(self.hangup_btn); bl.addWidget(self.mute_btn); bl.addWidget(self.deaf_btn)
        rv.addWidget(bottom)

        split.addWidget(left); split.addWidget(right); split.setSizes([340, 940])

        root = QWidget(); rl = QVBoxLayout(root); rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(header); rl.addWidget(split, 1)
        self.setCentralWidget(root)

    # ------------------------------------------------------------------
    # network wiring
    # ------------------------------------------------------------------
    def _wire_net(self):
        self.net.connected.connect(self._on_connected)
        self.net.disconnected.connect(lambda r: self.statusBar().showMessage(f"отключено: {r}"))
        self.net.presence.connect(self._on_presence)
        self.net.chat.connect(self._on_chat)
        self.net.channel_added.connect(self._on_channel_added)
        self.net.error.connect(lambda m: self.statusBar().showMessage(f"ошибка: {m}"))
        self.net.voice_packet.connect(self._on_voice)

        self.net.dm.connect(self._on_dm)
        self.net.call_invite.connect(self._on_call_invite)
        self.net.call_pending.connect(self._on_call_pending)
        self.net.call_accepted.connect(self._on_call_accepted)
        self.net.call_declined.connect(self._on_call_declined)
        self.net.call_hangup.connect(self._on_call_hangup)
        self.net.screen_start.connect(self._on_screen_start)
        self.net.screen_stop.connect(self._on_screen_stop)
        self.net.screen_frame.connect(self._on_screen_frame)

    # ------------------------------------------------------------------
    # connection / presence
    # ------------------------------------------------------------------
    def _on_connected(self, w):
        self.statusBar().showMessage(f"в сети · UDP {w.get('udp_port', '?')}")
        try:
            info = http_json("GET", f"{self.base_url.rstrip('/')}/api/servers/{self.server_id}")
        except Exception as e:
            self.statusBar().showMessage(f"ошибка: {e}"); return
        self.server_label.setText(info["name"])
        self._channels = {c["id"]: c["name"] for c in info["channels"]}
        self._rebuild_tree(info["online"]); self._rebuild_dm_users(info["online"])

    def _on_presence(self, users):
        self._users_by_token = {u["token"]: u for u in users}
        self._rebuild_tree(users); self._rebuild_dm_users(users)

    def _on_chat(self, m):
        if m.get("channel_id") != self.net.channel_id: return
        ts = time.strftime("%H:%M", time.localtime(m.get("ts", time.time())))
        self.chat_view.append(f"<span style='color:{COLORS['dim']}'>[{ts}]</span> "
                              f"<b style='color:{COLORS['amber']}'>{m['nick']}:</b> {m['text']}")

    def _on_channel_added(self, m):
        self._channels[m["id"]] = m["name"]
        self._rebuild_tree(list(self._users_by_token.values()))

    def _on_voice(self, src, seq, payload):
        if self._deafened: return
        self.engine.on_peer_packet(src, seq, payload)

    # ------------------------------------------------------------------
    # channel tree
    # ------------------------------------------------------------------
    def _rebuild_tree(self, users):
        self.tree.clear()
        by_chan = {cid: [] for cid in self._channels}
        by_chan[0] = []
        for u in users:
            cid = u["channel_id"] or 0
            if cid > 0 or cid == 0:
                by_chan.setdefault(cid, []).append(u)
        if by_chan.get(0):
            lobby = QTreeWidgetItem([f"Вестибюль ({len(by_chan[0])})"])
            lobby.setData(0, Qt.ItemDataRole.UserRole, None); self.tree.addTopLevelItem(lobby)
            for u in by_chan[0]: self._add_user_node(lobby, u)
            lobby.setExpanded(True)
        for cid, name in self._channels.items():
            members = by_chan.get(cid, [])
            it = QTreeWidgetItem([f"🔊  {name}    ({len(members)})"])
            it.setData(0, Qt.ItemDataRole.UserRole, cid)
            if cid == self.net.channel_id:
                f = it.font(0); f.setBold(True); it.setFont(0, f)
            self.tree.addTopLevelItem(it)
            for u in members: self._add_user_node(it, u)
            it.setExpanded(True)

    def _add_user_node(self, parent, u):
        badge = ""
        if u.get("muted"): badge += "  🔇"
        if u.get("deafened"): badge += "  🚫"
        c = QTreeWidgetItem([f"  👤  {u['nick']}{badge}"])
        c.setData(0, Qt.ItemDataRole.UserRole, ("user", u["token"])); parent.addChild(c)

    def _on_tree_dbl(self, item, _col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, int): self.net.join_channel(data)
        elif data is None: self.net.leave_channel()

    def _create_channel(self):
        name, ok = QInputDialog.getText(self, "Новый канал", "Название:")
        if not ok or not name.strip(): return
        tok, ok = QInputDialog.getText(self, "Admin token", "Введите admin token этого сервера:", QLineEdit.EchoMode.Password)
        if not ok or not tok.strip(): return
        try:
            http_json("POST", f"{self.base_url.rstrip('/')}/api/servers/{self.server_id}/channels",
                      {"admin_token": tok.strip(), "name": name.strip()})
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def _send_chat(self):
        txt = self.chat_input.text().strip()
        if not txt or self.net.channel_id is None: return
        self.net.send_chat(txt); self.chat_input.clear()

    # ------------------------------------------------------------------
    # DM
    # ------------------------------------------------------------------
    def _rebuild_dm_users(self, users):
        self.dm_users.clear()
        for u in users:
            if u["token"] == (self.net.token.hex() if self.net.token else ""): continue
            it = QListWidgetItem(f"👤  {u['nick']}")
            it.setData(Qt.ItemDataRole.UserRole, u["token"]); self.dm_users.addItem(it)

    def _open_dm_from_list(self, it: QListWidgetItem):
        peer = it.data(Qt.ItemDataRole.UserRole)
        if not peer: return
        self._dm_open_peer = peer
        nick = self._users_by_token.get(peer, {}).get("nick", peer[:8])
        self.dm_label.setText(f"ЛС с {nick}")
        self._render_dm_thread(peer)
        self.tabs_right.setCurrentIndex(1)

    def _render_dm_thread(self, peer: str):
        self.dm_view.clear()
        for nick, text, ts in self._dm_threads.get(peer, []):
            tt = time.strftime("%H:%M", time.localtime(ts))
            self.dm_view.append(f"<span style='color:{COLORS['dim']}'>[{tt}]</span> "
                                f"<b style='color:{COLORS['amber']}'>{nick}:</b> {text}")

    def _send_dm(self):
        if not self._dm_open_peer: return
        txt = self.dm_input.text().strip()
        if not txt: return
        self.net.send_dm(self._dm_open_peer, txt)
        ts = int(time.time())
        self._dm_threads.setdefault(self._dm_open_peer, []).append((self.nickname, txt, ts))
        self._render_dm_thread(self._dm_open_peer)
        self.dm_input.clear()

    def _on_dm(self, m):
        peer = m.get("from"); nick = m.get("nick", peer[:8])
        self._dm_threads.setdefault(peer, []).append((nick, m.get("text", ""), m.get("ts", int(time.time()))))
        if self._dm_open_peer == peer:
            self._render_dm_thread(peer)
        else:
            self.statusBar().showMessage(f"ЛС от {nick} — открой вкладку «ЛС»")

    # ------------------------------------------------------------------
    # 1-on-1 calls
    # ------------------------------------------------------------------
    def _call_selected(self):
        it = self.dm_users.currentItem()
        if not it:
            QMessageBox.information(self, "Звонок", "Выбери собеседника во вкладке «Личка»."); return
        peer = it.data(Qt.ItemDataRole.UserRole)
        self.net.call_invite_to(peer)
        self.statusBar().showMessage(f"Звоним {self._users_by_token.get(peer,{}).get('nick',peer[:8])}…")

    def _on_call_pending(self, m): self.statusBar().showMessage(f"Гудки… ждём ответа")

    def _on_call_invite(self, m):
        peer = m["from"]; nick = m.get("nick", peer[:8]); room = m["room"]
        ans = QMessageBox.question(self, "Входящий звонок",
                                   f"{nick} звонит. Ответить?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            self.net.call_accept(peer, room); self._enter_call(peer)
        else:
            self.net.call_decline(peer)

    def _on_call_accepted(self, m):
        peer = m["from"]; room = m["room"]
        self.net.channel_id = -int(room); self._enter_call(peer)

    def _on_call_declined(self, m):
        nick = self._users_by_token.get(m.get("from",""), {}).get("nick", "собеседник")
        QMessageBox.information(self, "Звонок", f"{nick} отклонил звонок.")

    def _on_call_hangup(self, m):
        if self.in_call_with == m.get("from"): self._leave_call()

    def _enter_call(self, peer: str):
        self.in_call_with = peer
        nick = self._users_by_token.get(peer, {}).get("nick", peer[:8])
        self.statusBar().showMessage(f"📞 В звонке с {nick}")
        self.hangup_btn.setVisible(True)

    def _leave_call(self):
        self.in_call_with = None
        self.net.channel_id = None
        self.hangup_btn.setVisible(False)
        if self.btn_screen.isChecked(): self.btn_screen.setChecked(False)
        if self.screen_viewer:
            self.screen_viewer.close(); self.screen_viewer = None
        self.statusBar().showMessage("Звонок завершён")

    def _hangup(self):
        if self.in_call_with:
            self.net.call_hangup_to(self.in_call_with)
        self._leave_call()

    # ------------------------------------------------------------------
    # Screen share
    # ------------------------------------------------------------------
    def _screen_toggle(self, on: bool):
        if on:
            if not self.in_call_with:
                QMessageBox.information(self, "Демонстрация", "Сначала начни звонок."); self.btn_screen.setChecked(False); return
            self.net.screen_start_to(self.in_call_with)
            self.screen_caster.start()
            self.statusBar().showMessage("🖥 Демонстрация запущена")
        else:
            self.screen_caster.stop()
            self.net.screen_stop_to()
            self.statusBar().showMessage("Демонстрация остановлена")

    def _on_screen_start(self, m):
        if not self.screen_viewer:
            nick = m.get("nick", m["from"][:8])
            self.screen_viewer = ScreenViewer(nick)
            self.screen_viewer.closed.connect(lambda: setattr(self, "screen_viewer", None))
            self.screen_viewer.show()

    def _on_screen_stop(self, m):
        if self.screen_viewer: self.screen_viewer.close(); self.screen_viewer = None

    def _on_screen_frame(self, m):
        if self.screen_viewer:
            self.screen_viewer.set_frame(int(m.get("w", 0)), int(m.get("h", 0)), m.get("jpeg", ""))

    # ------------------------------------------------------------------
    # mic / output / PTT
    # ------------------------------------------------------------------
    def _on_mute(self, m): self._muted = m; self.engine.set_talking(False if m else self._is_tx()); self.net.set_muted(m)
    def _on_deafen(self, d): self._deafened = d; self.net.set_deafened(d); self.engine.clear_peers() if d else None
    def _is_tx(self) -> bool:
        if self._muted: return False
        return True if self._voice_activation else self._ptt_held

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == self._ptt_key and not e.isAutoRepeat():
            self._ptt_held = True; self.engine.set_talking(self._is_tx())
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent):
        if e.key() == self._ptt_key and not e.isAutoRepeat():
            self._ptt_held = False
            self.engine.set_talking(self._is_tx() if self._voice_activation else False)
        super().keyReleaseEvent(e)

    def _reopen_devices(self):
        try:
            self.engine.stop()
            self.engine.input_device = self.input_dev.currentData()
            self.engine.output_device = self.output_dev.currentData()
            self.engine.start()
        except Exception as e:
            QMessageBox.warning(self, "Аудио", str(e))

    def _apply_bitrate(self):
        kb = self.bitrate.currentData()
        try: self.engine.codec.enc.bitrate = int(kb)
        except Exception: pass

    def _tick_meters(self):
        self.in_meter.setValue(int(self.engine.input_level * 100))
        self.out_meter.setValue(int(self.engine.output_level * 100))
        if self._voice_activation: self.engine.set_talking(not self._muted)
        elif not self._ptt_held:   self.engine.set_talking(False)

    def closeEvent(self, e):
        try: self.engine.stop()
        except Exception: pass
        try: self.screen_caster.stop()
        except Exception: pass
        try: self.net.disconnect()
        except Exception: pass
        super().closeEvent(e)
