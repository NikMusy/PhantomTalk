"""
PhantomTalk — single-window app.

One frameless window with three stacked views:
  Welcome (cinematic) → Connect (server browser) → Main (Discord-style layout).

Main layout (ember tones):
  [server rail] | [channels / DM list] | [chat content] | [members]
with custom title bar, animated view transitions, avatars, 1-on-1 calls,
direct messages and screen share.
"""
from __future__ import annotations

import base64
import time
from typing import Dict, Optional

from PyQt6.QtCore import (
    QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QFont, QIcon, QImage, QKeyEvent, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QFrame,
    QGraphicsOpacityEffect, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSizeGrip, QSizePolicy, QSlider, QStackedWidget,
    QStatusBar, QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from audio import AudioEngine, list_devices
from net import NetClient, http_json
from screen import ScreenCaster
from theme import COLORS, SERIF_FAMILY, sans, serif
from welcome import Welcome
from widgets import (
    IconButton, MemberRow, ServerPill, TitleBar, avatar_pixmap, orb_pixmap,
)


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
        self.label.setStyleSheet(f"background:#000; color:{COLORS['dim']};")
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        v.addWidget(self.label)

    def set_frame(self, w, h, jpeg_b64):
        try:
            img = QImage.fromData(base64.b64decode(jpeg_b64), "JPEG")
            if img.isNull():
                return
            self.label.setPixmap(QPixmap.fromImage(img).scaled(
                self.label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        except Exception:
            pass

    def closeEvent(self, e):
        self.closed.emit(); super().closeEvent(e)


# ============================================================================
# MAIN APP
# ============================================================================

class PhantomApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhantomTalk")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.resize(1320, 840)
        self.setMinimumSize(1040, 680)

        # state (engine/net created on connect)
        self.net: Optional[NetClient] = None
        self.engine: Optional[AudioEngine] = None
        self.screen_caster: Optional[ScreenCaster] = None
        self.screen_viewer: Optional[ScreenViewer] = None
        self.base_url = "http://127.0.0.1:9050"
        self.server_id = 0
        self.nickname = "Phantom"
        self.in_call_with: Optional[str] = None
        self._users_by_token: Dict[str, dict] = {}
        self._channels: Dict[int, str] = {}
        self._dm_threads: Dict[str, list] = {}
        self._dm_open_peer: Optional[str] = None
        self._muted = False
        self._deafened = False
        self._voice_activation = False
        self._ptt_held = False
        self._mode = "server"
        self._main_built = False

        # ---- shell: titlebar + stacked views ----
        central = QWidget(); cv = QVBoxLayout(central)
        cv.setContentsMargins(0, 0, 0, 0); cv.setSpacing(0)
        self.titlebar = TitleBar(self)
        self.stack = QStackedWidget()
        cv.addWidget(self.titlebar)
        cv.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # size grip (bottom-right) for resize
        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(16, 16)

        # views
        import os
        self.connect_view = self._build_connect()
        self.stack.addWidget(self.connect_view)

        auto = os.environ.get("PT_AUTOCONNECT")
        if auto:
            # jump straight in (testing / "remember last server")
            self._refresh_servers()
            QTimer.singleShot(300, lambda: self._auto_connect(int(auto)))
        elif os.environ.get("PT_NO_WELCOME") == "1":
            self.stack.setCurrentWidget(self.connect_view)
            QTimer.singleShot(50, self._refresh_servers)
        else:
            self.welcome = Welcome()
            self.stack.insertWidget(0, self.welcome)
            self.stack.setCurrentWidget(self.welcome)
            self.welcome.finished.connect(self._show_connect)

    def _auto_connect(self, sid: int):
        for i in range(self.server_browser.count()):
            it = self.server_browser.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == sid:
                self.server_browser.setCurrentItem(it); break
        self.stack.setCurrentWidget(self.connect_view)
        self._do_connect()

    # ------------------------------------------------------------------
    # transitions
    # ------------------------------------------------------------------
    def _fade_in(self, widget: QWidget, ms: int = 380):
        eff = QGraphicsOpacityEffect(widget); widget.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", widget)
        a.setDuration(ms); a.setStartValue(0.0); a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.finished.connect(lambda: widget.setGraphicsEffect(None))
        a.start(); self._anim_ref = a

    def _show_connect(self):
        self.stack.setCurrentWidget(self.connect_view)
        self._fade_in(self.connect_view)
        QTimer.singleShot(50, self._refresh_servers)
        QTimer.singleShot(700, self.welcome.deleteLater)

    def resizeEvent(self, e):
        self._grip.move(self.width() - self._grip.width() - 2, self.height() - self._grip.height() - 2)
        super().resizeEvent(e)

    # ==================================================================
    # CONNECT VIEW
    # ==================================================================
    def _build_connect(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page); outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()
        row = QHBoxLayout(); row.addStretch()

        card = QWidget(); card.setObjectName("GlassCard")
        card.setFixedWidth(560)
        cl = QVBoxLayout(card); cl.setContentsMargins(40, 34, 40, 34); cl.setSpacing(12)

        dot = QLabel(); dot.setPixmap(orb_pixmap(40)); dot.setFixedSize(40, 40)
        title = QLabel("PhantomTalk"); title.setFont(serif(30)); title.setStyleSheet(f"color:{COLORS['amber']};")
        sub = QLabel("ГОЛОС · КОТОРЫЙ · СЛЫШНО")
        sub.setStyleSheet(f"color:{COLORS['dim']}; letter-spacing:3px; font-size:9pt; font-weight:600;")
        head = QHBoxLayout(); head.addWidget(dot); head.addSpacing(8)
        tcol = QVBoxLayout(); tcol.setSpacing(0); tcol.addWidget(title); tcol.addWidget(sub)
        head.addLayout(tcol); head.addStretch()
        cl.addLayout(head); cl.addSpacing(8)

        form = QFormLayout(); form.setSpacing(10)
        self.f_url = QLineEdit(self.base_url)
        self.f_nick = QLineEdit(self.nickname)
        for w in (self.f_url, self.f_nick):
            w.setMinimumHeight(38)
        form.addRow("Сервер:", self.f_url)
        form.addRow("Никнейм:", self.f_nick)
        cl.addLayout(form)

        lbl = QLabel("ДОСТУПНЫЕ КОМНАТЫ"); lbl.setObjectName("sectionLabel")
        cl.addWidget(lbl)
        self.server_browser = QListWidget(); self.server_browser.setMinimumHeight(200)
        self.server_browser.itemDoubleClicked.connect(lambda *_: self._do_connect())
        cl.addWidget(self.server_browser, 1)

        btns = QHBoxLayout()
        b_ref = QPushButton("Обновить"); b_ref.setProperty("ghost", True); b_ref.clicked.connect(self._refresh_servers)
        b_new = QPushButton("Создать сервер…"); b_new.setProperty("ghost", True); b_new.clicked.connect(self._create_server)
        b_go = QPushButton("Войти →"); b_go.clicked.connect(self._do_connect)
        btns.addWidget(b_ref); btns.addWidget(b_new); btns.addStretch(); btns.addWidget(b_go)
        cl.addLayout(btns)

        row.addWidget(card); row.addStretch()
        outer.addLayout(row); outer.addStretch()
        return page

    def _refresh_servers(self):
        self.server_browser.clear()
        try:
            data = http_json("GET", f"{self.f_url.text().rstrip('/')}/api/servers")
        except Exception as e:
            self.server_browser.addItem(f"[ошибка] {e}"); return
        if not data:
            self.server_browser.addItem("(нет публичных серверов)"); return
        for s in data:
            it = QListWidgetItem(f"#{s['id']}   {s['name']}      {s['online']}/{s['max_users']}      {s['description']}")
            it.setData(Qt.ItemDataRole.UserRole, s["id"]); self.server_browser.addItem(it)

    def _create_server(self):
        name, ok = QInputDialog.getText(self, "Новый сервер", "Название:")
        if not ok or not name.strip():
            return
        desc, _ = QInputDialog.getText(self, "Новый сервер", "Описание:")
        try:
            data = http_json("POST", f"{self.f_url.text().rstrip('/')}/api/servers",
                             {"name": name.strip(), "description": desc.strip(), "public": True, "max_users": 64})
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e)); return
        QMessageBox.information(self, "Готово",
                               f"Сервер #{data['id']} создан.\nAdmin token:\n{data['admin_token']}")
        self._refresh_servers()

    def _do_connect(self):
        it = self.server_browser.currentItem()
        sid = it.data(Qt.ItemDataRole.UserRole) if it else None
        if not isinstance(sid, int):
            QMessageBox.warning(self, "Выбор", "Выбери комнату из списка."); return
        self.base_url = self.f_url.text().strip()
        self.server_id = sid
        self.nickname = self.f_nick.text().strip() or "Phantom"

        self.net = NetClient(self.base_url)
        self.engine = AudioEngine(send_frame=self.net.send_voice)
        self.screen_caster = ScreenCaster(send_frame=self.net.screen_send_frame)

        if not self._main_built:
            self.main_view = self._build_main()
            self.stack.addWidget(self.main_view)
            self._main_built = True
        self._wire_net()
        self.engine.start()
        self.net.connect(self.server_id, self.nickname)

        self.stack.setCurrentWidget(self.main_view)
        self._fade_in(self.main_view, 460)
        self.meter_timer = QTimer(self); self.meter_timer.timeout.connect(self._tick_meters); self.meter_timer.start(60)

    # ==================================================================
    # MAIN VIEW
    # ==================================================================
    def _build_main(self) -> QWidget:
        page = QWidget()
        h = QHBoxLayout(page); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)

        # ---------- server rail ----------
        rail = QWidget(); rail.setObjectName("ServerRail"); rail.setFixedWidth(76)
        rl = QVBoxLayout(rail); rl.setContentsMargins(12, 14, 12, 14); rl.setSpacing(12)
        rl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.btn_home = ServerPill("✦", "railHome"); self.btn_home.setToolTip("Личные сообщения")
        self.btn_home.clicked.connect(lambda: self._set_mode("dm"))
        sep = QFrame(); sep.setFixedHeight(2); sep.setStyleSheet(f"background:{COLORS['line']}; border-radius:1px;")
        self.btn_server = ServerPill("●", "serverPill"); self.btn_server.setToolTip("Сервер")
        self.btn_server.clicked.connect(lambda: self._set_mode("server"))
        btn_add = ServerPill("＋", "railAdd"); btn_add.setCheckable(False); btn_add.setToolTip("Другой сервер")
        btn_add.clicked.connect(self._switch_server)
        rl.addWidget(self.btn_home); rl.addWidget(sep); rl.addWidget(self.btn_server); rl.addWidget(btn_add)
        rl.addStretch()
        h.addWidget(rail)

        # ---------- channel / dm panel ----------
        panel = QWidget(); panel.setObjectName("ChannelPanel"); panel.setFixedWidth(248)
        pl = QVBoxLayout(panel); pl.setContentsMargins(0, 0, 0, 0); pl.setSpacing(0)

        self.panel_stack = QStackedWidget()

        # channels page
        chans = QWidget(); cvb = QVBoxLayout(chans); cvb.setContentsMargins(12, 0, 12, 8); cvb.setSpacing(6)
        chead = QWidget(); chead.setObjectName("ChannelHeader"); chl = QHBoxLayout(chead); chl.setContentsMargins(4, 12, 4, 12)
        self.server_name = QLabel("Сервер"); self.server_name.setObjectName("serverName")
        chl.addWidget(self.server_name); chl.addStretch()
        cvb.addWidget(chead)
        slabel = QLabel("КАНАЛЫ"); slabel.setObjectName("sectionLabel"); cvb.addWidget(slabel)
        self.tree = QTreeWidget(); self.tree.setObjectName("channelTree"); self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.itemClicked.connect(self._on_tree_click)
        cvb.addWidget(self.tree, 1)
        addch = QPushButton("＋  Создать канал"); addch.setProperty("ghost", True); addch.clicked.connect(self._create_channel)
        cvb.addWidget(addch)
        self.panel_stack.addWidget(chans)

        # dm page
        dms = QWidget(); dvb = QVBoxLayout(dms); dvb.setContentsMargins(12, 0, 12, 8); dvb.setSpacing(6)
        dhead = QWidget(); dhead.setObjectName("ChannelHeader"); dhl = QHBoxLayout(dhead); dhl.setContentsMargins(4, 12, 4, 12)
        dttl = QLabel("Личные сообщения"); dttl.setObjectName("serverName"); dhl.addWidget(dttl); dhl.addStretch()
        dvb.addWidget(dhead)
        dl = QLabel("ОНЛАЙН"); dl.setObjectName("sectionLabel"); dvb.addWidget(dl)
        self.dm_list = QListWidget(); self.dm_list.setObjectName("dmList")
        self.dm_list.itemClicked.connect(self._open_dm_from_list)
        dvb.addWidget(self.dm_list, 1)
        self.panel_stack.addWidget(dms)

        pl.addWidget(self.panel_stack, 1)

        # shared user panel (bottom)
        self.user_panel = self._build_user_panel()
        pl.addWidget(self.user_panel)
        h.addWidget(panel)

        # ---------- content ----------
        content = QWidget(); content.setObjectName("ContentPanel")
        ctl = QVBoxLayout(content); ctl.setContentsMargins(0, 0, 0, 0); ctl.setSpacing(0)
        self.content_stack = QStackedWidget()

        # channel chat page
        cpage = QWidget(); cpv = QVBoxLayout(cpage); cpv.setContentsMargins(0, 0, 0, 0); cpv.setSpacing(0)
        chh = QWidget(); chh.setObjectName("ContentHeader"); chhl = QHBoxLayout(chh); chhl.setContentsMargins(20, 14, 16, 14)
        self.chan_title = QLabel("# выбери канал"); self.chan_title.setObjectName("contentTitle")
        chhl.addWidget(self.chan_title); chhl.addStretch()
        self.lbl_voice = QLabel(""); self.lbl_voice.setStyleSheet(f"color:{COLORS['ember']}; font-weight:600;")
        chhl.addWidget(self.lbl_voice)
        cpv.addWidget(chh)
        self.chat_view = QTextEdit(); self.chat_view.setObjectName("chat"); self.chat_view.setReadOnly(True)
        cpv.addWidget(self.chat_view, 1)
        ci = QWidget(); cil = QHBoxLayout(ci); cil.setContentsMargins(20, 8, 20, 16)
        self.chat_input = QLineEdit(); self.chat_input.setObjectName("chatInput")
        self.chat_input.setPlaceholderText("Написать в канал…"); self.chat_input.returnPressed.connect(self._send_chat)
        cil.addWidget(self.chat_input)
        cpv.addWidget(ci)
        self.content_stack.addWidget(cpage)

        # dm chat page
        dpage = QWidget(); dpv = QVBoxLayout(dpage); dpv.setContentsMargins(0, 0, 0, 0); dpv.setSpacing(0)
        dhh = QWidget(); dhh.setObjectName("ContentHeader"); dhhl = QHBoxLayout(dhh); dhhl.setContentsMargins(20, 12, 16, 12)
        self.dm_title = QLabel("Выбери собеседника"); self.dm_title.setObjectName("contentTitle")
        dhhl.addWidget(self.dm_title); dhhl.addStretch()
        self.btn_call = IconButton("📞", "Позвонить"); self.btn_call.clicked.connect(self._call_selected)
        self.btn_screen = IconButton("🖥", "Демонстрация экрана", checkable=True); self.btn_screen.toggled.connect(self._screen_toggle)
        self.btn_hangup = IconButton("⛔", "Завершить звонок"); self.btn_hangup.clicked.connect(self._hangup); self.btn_hangup.setVisible(False)
        dhhl.addWidget(self.btn_call); dhhl.addWidget(self.btn_screen); dhhl.addWidget(self.btn_hangup)
        dpv.addWidget(dhh)
        self.dm_chat = QTextEdit(); self.dm_chat.setObjectName("dmChat"); self.dm_chat.setReadOnly(True)
        dpv.addWidget(self.dm_chat, 1)
        di = QWidget(); dil = QHBoxLayout(di); dil.setContentsMargins(20, 8, 20, 16)
        self.dm_input = QLineEdit(); self.dm_input.setObjectName("dmInput")
        self.dm_input.setPlaceholderText("Личное сообщение…"); self.dm_input.returnPressed.connect(self._send_dm)
        dil.addWidget(self.dm_input)
        dpv.addWidget(di)
        self.content_stack.addWidget(dpage)

        ctl.addWidget(self.content_stack, 1)
        h.addWidget(content, 1)

        # ---------- member panel ----------
        self.member_panel = QWidget(); self.member_panel.setObjectName("MemberPanel"); self.member_panel.setFixedWidth(232)
        ml = QVBoxLayout(self.member_panel); ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(0)
        mh = QWidget(); mh.setObjectName("MemberHeader"); mhl = QHBoxLayout(mh); mhl.setContentsMargins(16, 14, 16, 14)
        self.member_count = QLabel("УЧАСТНИКИ"); self.member_count.setObjectName("sectionLabel")
        mhl.addWidget(self.member_count); mhl.addStretch()
        ml.addWidget(mh)
        self.member_list = QListWidget(); self.member_list.setObjectName("memberList")
        ml.addWidget(self.member_list, 1)
        h.addWidget(self.member_panel)

        return page

    def _build_user_panel(self) -> QWidget:
        up = QWidget(); up.setObjectName("UserPanel"); up.setFixedHeight(64)
        l = QHBoxLayout(up); l.setContentsMargins(10, 8, 8, 8); l.setSpacing(8)
        self.user_avatar = QLabel(); self.user_avatar.setPixmap(avatar_pixmap(self.nickname, 38)); self.user_avatar.setFixedSize(38, 38)
        col = QVBoxLayout(); col.setSpacing(0)
        self.user_nick = QLabel(self.nickname); self.user_nick.setObjectName("userNick")
        self.user_state = QLabel("● в сети"); self.user_state.setObjectName("userStatus"); self.user_state.setStyleSheet(f"color:#22c55e; font-size:8pt;")
        col.addWidget(self.user_nick); col.addWidget(self.user_state)
        l.addWidget(self.user_avatar); l.addLayout(col, 1)
        self.btn_mute = IconButton("🎙", "Заглушить микрофон", checkable=True); self.btn_mute.toggled.connect(self._on_mute)
        self.btn_deaf = IconButton("🎧", "Не слышать", checkable=True); self.btn_deaf.toggled.connect(self._on_deafen)
        self.btn_settings = IconButton("⚙", "Настройки"); self.btn_settings.clicked.connect(self._open_settings)
        for b in (self.btn_mute, self.btn_deaf, self.btn_settings):
            l.addWidget(b)
        return up

    # ------------------------------------------------------------------
    # mode switching
    # ------------------------------------------------------------------
    def _set_mode(self, mode: str):
        self._mode = mode
        if mode == "dm":
            self.panel_stack.setCurrentIndex(1)
            self.content_stack.setCurrentIndex(1)
            self.member_panel.setVisible(False)
            self.btn_home.setChecked(True); self.btn_server.setChecked(False)
        else:
            self.panel_stack.setCurrentIndex(0)
            self.content_stack.setCurrentIndex(0)
            self.member_panel.setVisible(True)
            self.btn_home.setChecked(False); self.btn_server.setChecked(True)

    def _switch_server(self):
        # go back to connect screen to pick another server
        if self.net:
            try: self.net.disconnect()
            except Exception: pass
        if self.engine:
            try: self.engine.stop()
            except Exception: pass
        self.stack.setCurrentWidget(self.connect_view)
        self._fade_in(self.connect_view); self._refresh_servers()

    # ==================================================================
    # NET WIRING
    # ==================================================================
    def _wire_net(self):
        n = self.net
        n.connected.connect(self._on_connected)
        n.disconnected.connect(lambda r: self.statusBar().showMessage(f"отключено: {r}") if self.statusBar() else None)
        n.presence.connect(self._on_presence)
        n.chat.connect(self._on_chat)
        n.channel_added.connect(self._on_channel_added)
        n.voice_packet.connect(self._on_voice)
        n.dm.connect(self._on_dm)
        n.call_invite.connect(self._on_call_invite)
        n.call_pending.connect(lambda m: None)
        n.call_accepted.connect(self._on_call_accepted)
        n.call_declined.connect(self._on_call_declined)
        n.call_hangup.connect(self._on_call_hangup)
        n.screen_start.connect(self._on_screen_start)
        n.screen_stop.connect(self._on_screen_stop)
        n.screen_frame.connect(self._on_screen_frame)

    def statusBar(self):  # convenience no-op safe
        return super().statusBar()

    # ------------------------------------------------------------------
    def _on_connected(self, w):
        self._set_mode("server")
        try:
            info = http_json("GET", f"{self.base_url.rstrip('/')}/api/servers/{self.server_id}")
        except Exception:
            return
        self.server_name.setText(info["name"])
        self.btn_server.setText((info["name"][:1] or "P").upper())
        self.btn_server.setChecked(True)
        self._channels = {c["id"]: c["name"] for c in info["channels"]}
        self._rebuild_all(info["online"])
        self.user_nick.setText(self.nickname)
        self.user_avatar.setPixmap(avatar_pixmap(self.nickname, 38))
        self.chat_view.setHtml(
            f"<div style='color:{COLORS['dim']}; padding:24px; line-height:1.7'>"
            f"<span style='font-size:15pt; color:{COLORS['amber']}'>Добро пожаловать в {info['name']}.</span><br><br>"
            f"Выбери <b>голосовой канал</b> слева — там тебя услышат в&nbsp;<b>510&nbsp;кбит/с stereo</b>.<br>"
            f"Зажми <b>пробел</b>, чтобы говорить (push-to-talk), или включи голосовую активацию в&nbsp;⚙ настройках.<br>"
            f"Во вкладке <b>✦ Личка</b> — личные сообщения, звонки и демонстрация экрана."
            f"</div>")

    def _on_presence(self, users):
        self._users_by_token = {u["token"]: u for u in users}
        self._rebuild_all(users)

    def _rebuild_all(self, users):
        self._rebuild_tree(users)
        self._rebuild_members(users)
        self._rebuild_dm_list(users)

    def _my_token(self) -> str:
        return self.net.token.hex() if (self.net and self.net.token) else ""

    # ----- channel tree (voice channels w/ nested members) -----
    def _rebuild_tree(self, users):
        self.tree.clear()
        by_chan: Dict[int, list] = {cid: [] for cid in self._channels}
        lobby = []
        for u in users:
            cid = u.get("channel_id") or 0
            if cid and cid > 0:
                by_chan.setdefault(cid, []).append(u)
            else:
                lobby.append(u)
        for cid, name in self._channels.items():
            members = by_chan.get(cid, [])
            it = QTreeWidgetItem([f"  🔊  {name}    ·  {len(members)}"])
            it.setData(0, Qt.ItemDataRole.UserRole, cid)
            if cid == (self.net.channel_id if self.net else None):
                f = it.font(0); f.setBold(True); it.setFont(0, f)
            self.tree.addTopLevelItem(it)
            for u in members:
                ci = QTreeWidgetItem([f"   {u['nick']}"])
                ci.setIcon(0, QIcon(avatar_pixmap(u["nick"], 22)))
                ci.setData(0, Qt.ItemDataRole.UserRole, ("user", u["token"]))
                it.addChild(ci)
            it.setExpanded(True)

    def _on_tree_click(self, item, _col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, int):
            self.net.join_channel(data)
            self.chan_title.setText(f"#  {self._channels.get(data, '')}")
            self.lbl_voice.setText("🔊 в голосовом")
            self.chat_view.clear()

    def _create_channel(self):
        name, ok = QInputDialog.getText(self, "Новый канал", "Название:")
        if not ok or not name.strip():
            return
        tok, ok = QInputDialog.getText(self, "Admin token", "Admin token сервера:", QLineEdit.EchoMode.Password)
        if not ok or not tok.strip():
            return
        try:
            http_json("POST", f"{self.base_url.rstrip('/')}/api/servers/{self.server_id}/channels",
                      {"admin_token": tok.strip(), "name": name.strip()})
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def _on_channel_added(self, m):
        self._channels[m["id"]] = m["name"]
        self._rebuild_tree(list(self._users_by_token.values()))

    def _send_chat(self):
        t = self.chat_input.text().strip()
        if not t or self.net.channel_id is None:
            return
        self.net.send_chat(t); self.chat_input.clear()

    def _on_chat(self, m):
        if m.get("channel_id") != self.net.channel_id:
            return
        ts = time.strftime("%H:%M", time.localtime(m.get("ts", time.time())))
        self.chat_view.append(
            f"<span style='color:{COLORS['dim']}'>[{ts}]</span> "
            f"<b style='color:{COLORS['amber']}'>{m['nick']}</b>  {m['text']}")

    # ----- members -----
    def _rebuild_members(self, users):
        self.member_list.clear()
        self.member_count.setText(f"УЧАСТНИКИ — {len(users)}")
        for u in users:
            it = QListWidgetItem(); it.setSizeHint(QSize(0, 46))
            it.setData(Qt.ItemDataRole.UserRole, u["token"])
            self.member_list.addItem(it)
            self.member_list.setItemWidget(it, MemberRow(u["nick"],
                                                         "не слышит" if u.get("deafened") else "в сети",
                                                         u.get("muted"), u.get("deafened")))

    # ----- dm -----
    def _rebuild_dm_list(self, users):
        self.dm_list.clear()
        for u in users:
            if u["token"] == self._my_token():
                continue
            it = QListWidgetItem(); it.setSizeHint(QSize(0, 46))
            it.setData(Qt.ItemDataRole.UserRole, u["token"])
            self.dm_list.addItem(it)
            self.dm_list.setItemWidget(it, MemberRow(u["nick"], "написать…"))

    def _open_dm_from_list(self, it):
        peer = it.data(Qt.ItemDataRole.UserRole)
        if not peer:
            return
        self._dm_open_peer = peer
        nick = self._users_by_token.get(peer, {}).get("nick", peer[:8])
        self.dm_title.setText(f"@ {nick}")
        self._render_dm(peer)

    def _render_dm(self, peer):
        self.dm_chat.clear()
        for nick, text, ts in self._dm_threads.get(peer, []):
            tt = time.strftime("%H:%M", time.localtime(ts))
            self.dm_chat.append(
                f"<span style='color:{COLORS['dim']}'>[{tt}]</span> "
                f"<b style='color:{COLORS['amber']}'>{nick}</b>  {text}")

    def _send_dm(self):
        if not self._dm_open_peer:
            return
        t = self.dm_input.text().strip()
        if not t:
            return
        self.net.send_dm(self._dm_open_peer, t)
        self._dm_threads.setdefault(self._dm_open_peer, []).append((self.nickname, t, int(time.time())))
        self._render_dm(self._dm_open_peer); self.dm_input.clear()

    def _on_dm(self, m):
        peer = m.get("from"); nick = m.get("nick", peer[:8])
        self._dm_threads.setdefault(peer, []).append((nick, m.get("text", ""), m.get("ts", int(time.time()))))
        if self._dm_open_peer == peer and self._mode == "dm":
            self._render_dm(peer)
        else:
            self.btn_home.setText("✦"); self.statusBar().showMessage(f"ЛС от {nick}")

    # ----- calls -----
    def _call_selected(self):
        peer = self._dm_open_peer
        if not peer:
            it = self.dm_list.currentItem()
            peer = it.data(Qt.ItemDataRole.UserRole) if it else None
        if not peer:
            QMessageBox.information(self, "Звонок", "Открой ЛС с собеседником."); return
        self.net.call_invite_to(peer)
        self.statusBar().showMessage("Гудки…")

    def _on_call_invite(self, m):
        peer = m["from"]; nick = m.get("nick", peer[:8]); room = m["room"]
        if QMessageBox.question(self, "Входящий звонок", f"{nick} звонит. Ответить?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.net.call_accept(peer, room); self._enter_call(peer)
        else:
            self.net.call_decline(peer)

    def _on_call_accepted(self, m):
        self.net.channel_id = -int(m["room"]); self._enter_call(m["from"])

    def _on_call_declined(self, m):
        QMessageBox.information(self, "Звонок", "Собеседник отклонил звонок.")

    def _on_call_hangup(self, m):
        if self.in_call_with == m.get("from"):
            self._leave_call()

    def _enter_call(self, peer):
        self.in_call_with = peer
        nick = self._users_by_token.get(peer, {}).get("nick", peer[:8])
        self._set_mode("dm"); self._dm_open_peer = peer; self.dm_title.setText(f"📞 {nick}")
        self._render_dm(peer)
        self.btn_hangup.setVisible(True)
        self.statusBar().showMessage(f"📞 В звонке с {nick}")

    def _leave_call(self):
        self.in_call_with = None
        self.net.channel_id = None
        self.btn_hangup.setVisible(False)
        if self.btn_screen.isChecked():
            self.btn_screen.setChecked(False)
        if self.screen_viewer:
            self.screen_viewer.close(); self.screen_viewer = None
        self.statusBar().showMessage("Звонок завершён")

    def _hangup(self):
        if self.in_call_with:
            self.net.call_hangup_to(self.in_call_with)
        self._leave_call()

    # ----- screen share -----
    def _screen_toggle(self, on):
        if on:
            if not self.in_call_with:
                QMessageBox.information(self, "Демонстрация", "Сначала начни звонок."); self.btn_screen.setChecked(False); return
            self.net.screen_start_to(self.in_call_with); self.screen_caster.start()
            self.statusBar().showMessage("🖥 Демонстрация запущена")
        else:
            self.screen_caster.stop(); self.net.screen_stop_to()

    def _on_screen_start(self, m):
        if not self.screen_viewer:
            self.screen_viewer = ScreenViewer(m.get("nick", m["from"][:8]))
            self.screen_viewer.closed.connect(lambda: setattr(self, "screen_viewer", None))
            self.screen_viewer.show()

    def _on_screen_stop(self, m):
        if self.screen_viewer:
            self.screen_viewer.close(); self.screen_viewer = None

    def _on_screen_frame(self, m):
        if self.screen_viewer:
            self.screen_viewer.set_frame(int(m.get("w", 0)), int(m.get("h", 0)), m.get("jpeg", ""))

    # ----- voice -----
    def _on_voice(self, src, seq, payload):
        if not self._deafened:
            self.engine.on_peer_packet(src, seq, payload)

    def _on_mute(self, m):
        self._muted = m
        self.net.set_muted(m)
        self.user_state.setText("🔇 микрофон выкл" if m else "● в сети")
        self.user_state.setStyleSheet(f"color:{COLORS['dim'] if m else '#22c55e'}; font-size:8pt;")

    def _on_deafen(self, d):
        self._deafened = d
        self.net.set_deafened(d)
        if d:
            self.engine.clear_peers()

    # ----- settings -----
    def _open_settings(self):
        dlg = QDialog(self); dlg.setWindowTitle("Настройки звука"); dlg.setMinimumWidth(460)
        f = QFormLayout(dlg)
        in_devs, out_devs = list_devices()
        cin = QComboBox(); [cin.addItem(n, i) for i, n in in_devs]
        cout = QComboBox(); [cout.addItem(n, i) for i, n in out_devs]
        gain = QSlider(Qt.Orientation.Horizontal); gain.setRange(0, 400); gain.setValue(100)
        gain.valueChanged.connect(lambda v: self.engine.set_mic_gain(v / 100.0))
        outg = QSlider(Qt.Orientation.Horizontal); outg.setRange(0, 400); outg.setValue(100)
        outg.valueChanged.connect(lambda v: self.engine.set_out_gain(v / 100.0))
        va = QCheckBox("Голосовая активация (вместо PTT — пробел)")
        va.stateChanged.connect(lambda *_: setattr(self, "_voice_activation", va.isChecked()))
        br = QComboBox()
        for kb in (64, 96, 128, 192, 256, 320, 384, 510):
            br.addItem(f"{kb} кбит/с" + ("  ← выше Discord Nitro" if kb >= 384 else ""), kb * 1000)
        br.setCurrentIndex(7)
        br.currentIndexChanged.connect(lambda *_: setattr(self.engine.codec.enc, "bitrate", int(br.currentData())))

        def reopen():
            try:
                self.engine.stop()
                self.engine.input_device = cin.currentData()
                self.engine.output_device = cout.currentData()
                self.engine.start()
            except Exception as e:
                QMessageBox.warning(dlg, "Аудио", str(e))
        cin.currentIndexChanged.connect(reopen); cout.currentIndexChanged.connect(reopen)

        f.addRow("Микрофон:", cin)
        f.addRow("Динамики:", cout)
        f.addRow("Усиление мик:", gain)
        f.addRow("Громкость:", outg)
        f.addRow("", va)
        f.addRow("Битрейт Opus:", br)
        f.addRow(QLabel("PhantomTalk: 48 кГц stereo · 20 мс · до 510 кбит/с\nDiscord: 96 кбит/с (Nitro 384)."))
        ok = QPushButton("Готово"); ok.clicked.connect(dlg.accept); f.addRow(ok)
        dlg.exec()

    # ----- PTT -----
    def _is_tx(self):
        if self._muted:
            return False
        return True if self._voice_activation else self._ptt_held

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Space and not e.isAutoRepeat():
            self._ptt_held = True
            if self.engine: self.engine.set_talking(self._is_tx())
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Space and not e.isAutoRepeat():
            self._ptt_held = False
            if self.engine: self.engine.set_talking(self._is_tx() if self._voice_activation else False)
        super().keyReleaseEvent(e)

    def _tick_meters(self):
        if not self.engine:
            return
        talking = self._is_tx()
        if self._voice_activation:
            self.engine.set_talking(not self._muted)
        elif not self._ptt_held:
            self.engine.set_talking(False)
        # speaking indicator on own avatar
        if talking and self.engine.input_level > 0.06:
            self.user_avatar.setStyleSheet(f"border:2px solid #22c55e; border-radius:21px;")
        else:
            self.user_avatar.setStyleSheet("")

    def closeEvent(self, e):
        for fn in (lambda: self.engine and self.engine.stop(),
                   lambda: self.screen_caster and self.screen_caster.stop(),
                   lambda: self.net and self.net.disconnect()):
            try: fn()
            except Exception: pass
        super().closeEvent(e)
