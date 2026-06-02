"""
PhantomTalk server.

Runs three things in one process:
  * HTTP/REST  (FastAPI)  - account-less voice "servers", channels, server browser
  * WebSocket            - signaling: join/leave, presence, text chat
  * UDP socket           - voice relay (Opus packets) between users in same channel

Voice packet format (client -> server):
    [VER:1=0x01][TOKEN:16][SERVER_ID:4][CHANNEL_ID:4][SEQ:4][OPUS_PAYLOAD...]

Voice packet format (server -> client):
    [VER:1=0x01][SRC_TOKEN:16][SEQ:4][OPUS_PAYLOAD...]

The server never decodes audio.  It just forwards Opus frames to every other
session subscribed to the same channel.  That keeps CPU low and quality
literally bit-perfect end-to-end.
"""
import asyncio
import json
import os
import secrets
import socket
import struct
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Tuple

import aiosqlite
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEBSITE_DIR = os.path.join(ROOT, "website")
DB_PATH = os.path.join(HERE, "phantomtalk.db")

HTTP_HOST = os.environ.get("PT_HOST", "0.0.0.0")
HTTP_PORT = int(os.environ.get("PT_PORT", "9050"))
UDP_PORT  = int(os.environ.get("PT_UDP",  "9051"))

VOICE_VER = 0x01


# ----------------------------- in-memory state -------------------------------

@dataclass
class Session:
    token: bytes                       # 16 raw bytes
    nickname: str
    server_id: int
    channel_id: Optional[int] = None
    udp_addr: Optional[Tuple[str, int]] = None
    ws: Optional[WebSocket] = None
    muted: bool = False
    deafened: bool = False
    screen_target: str = ""             # token_hex of peer we're streaming our screen to
    last_seen: float = field(default_factory=time.time)

    @property
    def token_hex(self) -> str:
        return self.token.hex()


SESSIONS: Dict[bytes, Session] = {}
# server_id -> channel_id -> set[token]
CHANNEL_MEMBERS: Dict[int, Dict[int, Set[bytes]]] = {}


# ----------------------------- database --------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS servers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    admin_token   TEXT NOT NULL,
    public        INTEGER NOT NULL DEFAULT 1,
    max_users     INTEGER NOT NULL DEFAULT 64,
    created_at    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS channels (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id    INTEGER NOT NULL,
    name         TEXT NOT NULL,
    position     INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(server_id) REFERENCES servers(id) ON DELETE CASCADE
);
"""

db_lock = asyncio.Lock()

async def db():
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    return conn


async def init_db():
    async with db_lock:
        conn = await db()
        try:
            await conn.executescript(SCHEMA)
            await conn.commit()
            # Seed a default public server if none exists, so the user has somewhere to land.
            cur = await conn.execute("SELECT COUNT(*) AS c FROM servers")
            row = await cur.fetchone()
            if row["c"] == 0:
                tok = secrets.token_hex(16)
                cur = await conn.execute(
                    "INSERT INTO servers(name,description,admin_token,public,max_users,created_at)"
                    " VALUES(?,?,?,?,?,?)",
                    ("PhantomTalk Public", "Главный публичный сервер PhantomTalk", tok, 1, 128, int(time.time())),
                )
                sid = cur.lastrowid
                for i, name in enumerate(["General", "Music", "Gaming", "AFK"]):
                    await conn.execute(
                        "INSERT INTO channels(server_id,name,position) VALUES(?,?,?)",
                        (sid, name, i),
                    )
                await conn.commit()
                print(f"[db] seeded default server #{sid} admin_token={tok}")
        finally:
            await conn.close()


# ----------------------------- HTTP API --------------------------------------

class CreateServerReq(BaseModel):
    name: str
    description: str = ""
    public: bool = True
    max_users: int = 64


class CreateChannelReq(BaseModel):
    admin_token: str
    name: str


app = FastAPI(title="PhantomTalk")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    await init_db()


@app.get("/api/health")
async def health():
    return {"ok": True, "udp_port": UDP_PORT, "sessions": len(SESSIONS)}


@app.get("/api/servers")
async def list_servers():
    conn = await db()
    try:
        cur = await conn.execute(
            "SELECT id,name,description,public,max_users FROM servers WHERE public=1 ORDER BY id"
        )
        rows = await cur.fetchall()
        out = []
        for r in rows:
            online = sum(
                1 for s in SESSIONS.values() if s.server_id == r["id"]
            )
            out.append({
                "id": r["id"], "name": r["name"], "description": r["description"],
                "max_users": r["max_users"], "online": online,
            })
        return out
    finally:
        await conn.close()


@app.post("/api/servers")
async def create_server(req: CreateServerReq):
    if not (1 <= len(req.name) <= 64):
        raise HTTPException(400, "Bad name length")
    tok = secrets.token_hex(16)
    conn = await db()
    try:
        cur = await conn.execute(
            "INSERT INTO servers(name,description,admin_token,public,max_users,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (req.name, req.description or "", tok, 1 if req.public else 0,
             max(2, min(512, req.max_users)), int(time.time())),
        )
        sid = cur.lastrowid
        for i, n in enumerate(["General", "Lobby"]):
            await conn.execute(
                "INSERT INTO channels(server_id,name,position) VALUES(?,?,?)", (sid, n, i)
            )
        await conn.commit()
    finally:
        await conn.close()
    return {"id": sid, "admin_token": tok}


@app.get("/api/servers/{sid}")
async def get_server(sid: int):
    conn = await db()
    try:
        cur = await conn.execute("SELECT id,name,description,max_users FROM servers WHERE id=?", (sid,))
        s = await cur.fetchone()
        if not s:
            raise HTTPException(404, "not found")
        cur = await conn.execute(
            "SELECT id,name,position FROM channels WHERE server_id=? ORDER BY position,id", (sid,)
        )
        channels = [dict(r) for r in await cur.fetchall()]
        return {
            "id": s["id"], "name": s["name"], "description": s["description"],
            "max_users": s["max_users"],
            "channels": channels,
            "online": [
                {"token": ss.token_hex, "nick": ss.nickname,
                 "channel_id": ss.channel_id, "muted": ss.muted, "deafened": ss.deafened}
                for ss in SESSIONS.values() if ss.server_id == sid
            ],
        }
    finally:
        await conn.close()


@app.post("/api/servers/{sid}/channels")
async def create_channel(sid: int, req: CreateChannelReq):
    conn = await db()
    try:
        cur = await conn.execute("SELECT admin_token FROM servers WHERE id=?", (sid,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "server not found")
        if row["admin_token"] != req.admin_token:
            raise HTTPException(403, "bad admin token")
        cur = await conn.execute(
            "SELECT COALESCE(MAX(position),0)+1 AS p FROM channels WHERE server_id=?", (sid,)
        )
        pos = (await cur.fetchone())["p"]
        cur = await conn.execute(
            "INSERT INTO channels(server_id,name,position) VALUES(?,?,?)",
            (sid, req.name[:48], pos),
        )
        await conn.commit()
        new_id = cur.lastrowid
    finally:
        await conn.close()
    await broadcast_server(sid, {"type": "channel_added", "id": new_id, "name": req.name[:48]})
    return {"id": new_id, "name": req.name[:48]}


# ----------------------------- WebSocket signaling ---------------------------

async def _send_to_token(token_hex: str, msg: dict):
    """Send a JSON message to the session identified by hex token."""
    try:
        token = bytes.fromhex(token_hex)
    except Exception:
        return
    s = SESSIONS.get(token)
    if not s or s.ws is None:
        return
    try:
        await s.ws.send_text(json.dumps(msg, ensure_ascii=False))
    except Exception:
        pass


async def broadcast_server(sid: int, msg: dict):
    data = json.dumps(msg, ensure_ascii=False)
    dead = []
    for s in list(SESSIONS.values()):
        if s.server_id == sid and s.ws is not None:
            try:
                await s.ws.send_text(data)
            except Exception:
                dead.append(s.token)
    for t in dead:
        await drop_session(t)


def presence_payload(sid: int) -> dict:
    return {
        "type": "presence",
        "users": [
            {"token": s.token_hex, "nick": s.nickname,
             "channel_id": s.channel_id, "muted": s.muted, "deafened": s.deafened}
            for s in SESSIONS.values() if s.server_id == sid
        ],
    }


async def move_session(s: Session, channel_id: Optional[int]):
    # remove from old
    old = s.channel_id
    if old is not None:
        chans = CHANNEL_MEMBERS.get(s.server_id, {})
        members = chans.get(old)
        if members is not None:
            members.discard(s.token)
    s.channel_id = channel_id
    if channel_id is not None:
        CHANNEL_MEMBERS.setdefault(s.server_id, {}).setdefault(channel_id, set()).add(s.token)
    await broadcast_server(s.server_id, presence_payload(s.server_id))


async def drop_session(token: bytes):
    s = SESSIONS.pop(token, None)
    if not s:
        return
    chans = CHANNEL_MEMBERS.get(s.server_id, {})
    for members in chans.values():
        members.discard(token)
    try:
        if s.ws is not None:
            await s.ws.close()
    except Exception:
        pass
    await broadcast_server(s.server_id, presence_payload(s.server_id))


@app.websocket("/ws/{sid}")
async def ws_endpoint(ws: WebSocket, sid: int):
    await ws.accept()
    # first message must be a join
    try:
        hello = await asyncio.wait_for(ws.receive_text(), timeout=10)
    except Exception:
        await ws.close()
        return
    try:
        msg = json.loads(hello)
        assert msg.get("type") == "hello"
        nick = str(msg.get("nick", "")).strip()[:24] or f"guest-{secrets.token_hex(2)}"
    except Exception:
        await ws.close()
        return

    conn = await db()
    try:
        cur = await conn.execute("SELECT id FROM servers WHERE id=?", (sid,))
        if not await cur.fetchone():
            await ws.send_text(json.dumps({"type": "error", "msg": "server not found"}))
            await ws.close()
            return
    finally:
        await conn.close()

    token = secrets.token_bytes(16)
    sess = Session(token=token, nickname=nick, server_id=sid, ws=ws)
    SESSIONS[token] = sess

    await ws.send_text(json.dumps({
        "type": "welcome",
        "token": token.hex(),
        "udp_port": UDP_PORT,
    }))
    await broadcast_server(sid, presence_payload(sid))

    try:
        while True:
            raw = await ws.receive_text()
            try:
                m = json.loads(raw)
            except Exception:
                continue
            t = m.get("type")
            if t == "join_channel":
                cid = int(m.get("channel_id"))
                await move_session(sess, cid)
            elif t == "leave_channel":
                await move_session(sess, None)
            elif t == "mute":
                sess.muted = bool(m.get("muted", False))
                await broadcast_server(sid, presence_payload(sid))
            elif t == "deafen":
                sess.deafened = bool(m.get("deafened", False))
                await broadcast_server(sid, presence_payload(sid))
            elif t == "chat":
                if sess.channel_id is None:
                    continue
                await broadcast_server(sid, {
                    "type": "chat",
                    "channel_id": sess.channel_id,
                    "nick": sess.nickname,
                    "text": str(m.get("text", ""))[:1000],
                    "ts": int(time.time()),
                })
            elif t == "udp_hello":
                # client tells us its UDP port via signaling as backup
                pass
            elif t == "ping":
                await ws.send_text(json.dumps({"type": "pong", "ts": m.get("ts")}))

            # ---------------- DIRECT MESSAGES + 1-on-1 CALLS ----------------
            elif t == "dm":
                await _send_to_token(m.get("to", ""), {
                    "type": "dm",
                    "from": sess.token_hex, "nick": sess.nickname,
                    "text": str(m.get("text", ""))[:2000],
                    "ts": int(time.time()),
                })
            elif t == "call_invite":
                # invite a peer to a 1-on-1 voice call (negative channel id, ephemeral)
                target = m.get("to", "")
                room = abs(hash((sess.token_hex, target))) % 10_000_000 + 1_000_000_000
                await _send_to_token(target, {
                    "type": "call_invite",
                    "from": sess.token_hex, "nick": sess.nickname, "room": room,
                })
                await ws.send_text(json.dumps({"type": "call_pending", "to": target, "room": room}))
            elif t == "call_accept":
                room = int(m.get("room", 0))
                target = m.get("to", "")
                await _send_to_token(target, {"type": "call_accepted", "from": sess.token_hex, "room": room})
                await move_session(sess, -room)              # negative cid = direct room
            elif t == "call_decline":
                await _send_to_token(m.get("to", ""), {"type": "call_declined", "from": sess.token_hex})
            elif t == "call_hangup":
                await _send_to_token(m.get("to", ""), {"type": "call_hangup", "from": sess.token_hex})
                await move_session(sess, None)

            # ---------------- SCREEN SHARE (JPEG frames over WS) -------------
            elif t == "screen_start":
                target = m.get("to", "")
                sess.screen_target = target
                await _send_to_token(target, {"type": "screen_start", "from": sess.token_hex, "nick": sess.nickname})
            elif t == "screen_stop":
                tgt = getattr(sess, "screen_target", "")
                if tgt:
                    await _send_to_token(tgt, {"type": "screen_stop", "from": sess.token_hex})
                sess.screen_target = ""
            elif t == "screen_frame":
                tgt = getattr(sess, "screen_target", "")
                if tgt:
                    await _send_to_token(tgt, {
                        "type": "screen_frame",
                        "from": sess.token_hex,
                        "w": int(m.get("w", 0)), "h": int(m.get("h", 0)),
                        "jpeg": m.get("jpeg", ""),   # base64
                    })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[ws] err: {e}")
    finally:
        await drop_session(token)


# ----------------------------- UDP voice relay -------------------------------

class VoiceProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport):
        self.transport = transport
        print(f"[udp] listening on {UDP_PORT}")

    def datagram_received(self, data: bytes, addr):
        # Minimum size: VER(1)+TOKEN(16)+SID(4)+CID(4)+SEQ(4) = 29
        if len(data) < 29:
            return
        if data[0] != VOICE_VER:
            return
        token = data[1:17]
        sess = SESSIONS.get(token)
        if sess is None:
            return
        # learn / refresh udp addr
        sess.udp_addr = addr
        sess.last_seen = time.time()
        try:
            server_id = struct.unpack_from(">I", data, 17)[0]
            channel_id = struct.unpack_from(">I", data, 21)[0]
            seq = struct.unpack_from(">I", data, 25)[0]
        except struct.error:
            return
        if sess.server_id != server_id or sess.channel_id != channel_id:
            return
        if sess.muted:
            return
        payload = data[29:]
        if not payload:
            return
        # forward to all peers in same channel except sender, who are not deafened
        members = CHANNEL_MEMBERS.get(server_id, {}).get(channel_id, set())
        out = b"\x01" + token + struct.pack(">I", seq) + payload
        tr = self.transport
        for tk in members:
            if tk == token:
                continue
            peer = SESSIONS.get(tk)
            if peer is None or peer.udp_addr is None or peer.deafened:
                continue
            try:
                tr.sendto(out, peer.udp_addr)
            except OSError:
                pass


async def run_udp():
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(
        VoiceProtocol, local_addr=(HTTP_HOST, UDP_PORT)
    )


# ----------------------------- static website --------------------------------

if os.path.isdir(WEBSITE_DIR):
    app.mount("/static", StaticFiles(directory=WEBSITE_DIR), name="static")

    @app.get("/")
    async def root():
        return FileResponse(os.path.join(WEBSITE_DIR, "index.html"))

    @app.get("/{path:path}")
    async def site(path: str):
        full = os.path.join(WEBSITE_DIR, path)
        if os.path.isfile(full):
            return FileResponse(full)
        return FileResponse(os.path.join(WEBSITE_DIR, "index.html"))


# ----------------------------- entrypoint ------------------------------------

async def main():
    await init_db()
    await run_udp()
    config = uvicorn.Config(app, host=HTTP_HOST, port=HTTP_PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("bye")
