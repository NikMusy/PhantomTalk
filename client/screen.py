"""
Screen capture and frame distribution.

Capture loop runs in a background thread, encodes the primary monitor to JPEG
at a tunable fps/quality, base64-encodes and emits via callback (sent over WS
to the peer).  We deliberately ship JPEG over WebSocket instead of doing real
H.264 / WebRTC — the goal is "good enough to demo your game/IDE", with zero
extra dependencies and trivial debugging.
"""
from __future__ import annotations

import base64
import io
import threading
import time
from typing import Callable, Optional

import mss
from PIL import Image


class ScreenCaster:
    def __init__(self, send_frame: Callable[[int, int, str], None],
                 fps: int = 12, max_width: int = 1280, quality: int = 70):
        self.send_frame = send_frame
        self.fps = max(1, min(30, fps))
        self.max_width = max_width
        self.quality = max(30, min(95, quality))
        self._th: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        if self._th and self._th.is_alive(): return
        self._stop.clear()
        self._th = threading.Thread(target=self._loop, daemon=True, name="pt-screen")
        self._th.start()

    def stop(self):
        self._stop.set()
        if self._th:
            self._th.join(timeout=1.5)
            self._th = None

    def _loop(self):
        interval = 1.0 / self.fps
        try:
            with mss.mss() as sct:
                mon = sct.monitors[1]  # primary monitor (sct.monitors[0] = all)
                while not self._stop.is_set():
                    t0 = time.monotonic()
                    img = sct.grab(mon)
                    # BGRA -> RGB PIL Image
                    pil = Image.frombytes("RGB", (img.width, img.height), img.rgb)
                    w, h = pil.size
                    if w > self.max_width:
                        new_h = int(h * (self.max_width / w))
                        pil = pil.resize((self.max_width, new_h), Image.LANCZOS)
                        w, h = pil.size
                    buf = io.BytesIO()
                    pil.save(buf, format="JPEG", quality=self.quality, optimize=False)
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    try:
                        self.send_frame(w, h, b64)
                    except Exception:
                        pass
                    dt = time.monotonic() - t0
                    if dt < interval:
                        time.sleep(interval - dt)
        except Exception as e:
            # capture stopped (display change, missing permissions, etc.)
            print(f"[screen] loop ended: {e}")
