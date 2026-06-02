"""
Network layer: HTTP REST + WebSocket signaling + UDP voice.

The UDP socket and the WebSocket run on a background asyncio loop in a
dedicated thread so the Qt main thread is never blocked.  Inbound events
are delivered to the UI via Qt signals; outbound voice frames are queued
directly into the UDP transport.
"""
from __future__ import annotations

import asyncio
import json
import struct
import threading
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlsplit

import websockets
from PyQt6.QtCore import QObject, pyqtSignal

VOICE_VER = b"\x01"


class VoiceUDP(asyncio.DatagramProtocol):
    def __init__(self, on_packet: Callable[[bytes, Tuple[str, int]], None]):
        self.on_packet = on_packet
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.on_packet(data, addr)


class NetClient(QObject):
    # Qt signals
    connected     = pyqtSignal(dict)            # welcome payload
    disconnected  = pyqtSignal(str)             # reason
    presence      = pyqtSignal(list)            # users list
    chat          = pyqtSignal(dict)            # chat msg
    channel_added = pyqtSignal(dict)
    error         = pyqtSignal(str)
    voice_packet  = pyqtSignal(bytes, int, bytes)  # src_token, seq, payload

    def __init__(self, base_url: str):
        super().__init__()
        # base_url like http://host:9050
        self.base_url = base_url.rstrip("/")
        u = urlsplit(self.base_url)
        self.host = u.hostname or "127.0.0.1"
        self.http_port = u.port or 9050
        ws_scheme = "wss" if u.scheme == "https" else "ws"
        self._ws_root = f"{ws_scheme}://{u.hostname}:{self.http_port}"
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ws = None
        self._udp_transport: Optional[asyncio.DatagramTransport] = None
        self._udp_target: Optional[Tuple[str, int]] = None
        self.token: Optional[bytes] = None
        self.server_id: Optional[int] = None
        self.channel_id: Optional[int] = None

    # ---------- thread / loop -----------------------------------------------
    def start_loop(self):
        if self._thread is not None:
            return
        ready = threading.Event()

        def runner():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=runner, daemon=True, name="pt-net")
        self._thread.start()
        ready.wait(2.0)

    def _submit(self, coro):
        assert self._loop is not None
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    # ---------- connect / disconnect ----------------------------------------
    def connect(self, server_id: int, nickname: str):
        self.start_loop()
        self.server_id = server_id
        self._submit(self._connect(server_id, nickname))

    def disconnect(self):
        if self._loop is None:
            return
        self._submit(self._disconnect()).result(timeout=2.0)

    async def _connect(self, server_id: int, nickname: str):
        try:
            uri = f"{self._ws_root}/ws/{server_id}"
            self._ws = await websockets.connect(uri, max_size=2**20)
            await self._ws.send(json.dumps({"type": "hello", "nick": nickname}))
            welcome = json.loads(await self._ws.recv())
            if welcome.get("type") != "welcome":
                self.error.emit(welcome.get("msg", "bad welcome"))
                await self._ws.close()
                self._ws = None
                return
            self.token = bytes.fromhex(welcome["token"])
            udp_port = int(welcome["udp_port"])
            self._udp_target = (self.host, udp_port)
            # open udp
            loop = asyncio.get_running_loop()
            self._udp_transport, _ = await loop.create_datagram_endpoint(
                lambda: VoiceUDP(self._on_udp), remote_addr=self._udp_target,
            )
            self.connected.emit(welcome)
            # spawn keepalive
            asyncio.create_task(self._keepalive())
            # main recv loop
            async for raw in self._ws:
                try:
                    m = json.loads(raw)
                except Exception:
                    continue
                t = m.get("type")
                if t == "presence":
                    self.presence.emit(m.get("users", []))
                elif t == "chat":
                    self.chat.emit(m)
                elif t == "channel_added":
                    self.channel_added.emit(m)
                elif t == "error":
                    self.error.emit(m.get("msg", ""))
        except Exception as e:
            self.error.emit(f"net: {e}")
        finally:
            await self._disconnect()
            self.disconnected.emit("closed")

    async def _disconnect(self):
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        if self._udp_transport is not None:
            try:
                self._udp_transport.close()
            except Exception:
                pass
            self._udp_transport = None

    async def _keepalive(self):
        while self._ws is not None:
            try:
                await asyncio.sleep(15)
                if self._ws is None:
                    return
                await self._ws.send(json.dumps({"type": "ping", "ts": 0}))
                # Also send a small UDP keepalive so the server learns/keeps our addr.
                self._send_udp_raw(b"")  # zero payload, will be ignored by server but punches NAT
            except Exception:
                return

    # ---------- send WS commands --------------------------------------------
    def _send_ws(self, msg: dict):
        if self._loop is None or self._ws is None:
            return
        data = json.dumps(msg, ensure_ascii=False)
        async def _s():
            try:
                if self._ws is not None:
                    await self._ws.send(data)
            except Exception:
                pass
        self._submit(_s())

    def join_channel(self, channel_id: int):
        self.channel_id = channel_id
        self._send_ws({"type": "join_channel", "channel_id": channel_id})

    def leave_channel(self):
        self.channel_id = None
        self._send_ws({"type": "leave_channel"})

    def set_muted(self, m: bool):
        self._send_ws({"type": "mute", "muted": m})

    def set_deafened(self, d: bool):
        self._send_ws({"type": "deafen", "deafened": d})

    def send_chat(self, text: str):
        self._send_ws({"type": "chat", "text": text})

    # ---------- voice UDP ---------------------------------------------------
    def _send_udp_raw(self, payload: bytes):
        if (self._udp_transport is None or self.token is None
                or self.server_id is None or self.channel_id is None):
            return
        hdr = (VOICE_VER + self.token
               + struct.pack(">I", self.server_id)
               + struct.pack(">I", self.channel_id))
        # seq is appended by caller; raw form here used for keepalive when payload="".
        if not payload:
            # Use seq 0 as keepalive marker; server ignores empty payloads anyway.
            data = hdr + struct.pack(">I", 0)
        else:
            data = payload
        try:
            self._udp_transport.sendto(data)
        except Exception:
            pass

    _seq = 0
    def send_voice(self, opus_payload: bytes):
        if (self._udp_transport is None or self.token is None
                or self.server_id is None or self.channel_id is None):
            return
        self._seq = (self._seq + 1) & 0xFFFFFFFF
        hdr = (VOICE_VER + self.token
               + struct.pack(">I", self.server_id)
               + struct.pack(">I", self.channel_id)
               + struct.pack(">I", self._seq))
        try:
            self._udp_transport.sendto(hdr + opus_payload)
        except Exception:
            pass

    def _on_udp(self, data: bytes, addr):
        # Server -> client: [VER:1][SRC_TOKEN:16][SEQ:4][OPUS...]
        if len(data) < 21 or data[0] != 0x01:
            return
        src = data[1:17]
        seq = struct.unpack_from(">I", data, 17)[0]
        payload = data[21:]
        if not payload:
            return
        self.voice_packet.emit(src, seq, payload)


# ---------------------------- HTTP helpers --------------------------------
import urllib.request
import urllib.error


def http_json(method: str, url: str, body: Optional[dict] = None, timeout: float = 5.0):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read().decode("utf-8"))
        except Exception:
            j = {"detail": str(e)}
        raise RuntimeError(j.get("detail", str(e)))
