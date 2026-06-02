"""
Audio engine: capture, Opus encode, decode, mix and play back.

48 kHz / stereo / 20 ms frames / Opus VOIP @ 510 kbps maximum bitrate
(Discord caps voice at 96 kbps, even on Nitro boosted servers it's 384.)
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Dict, Optional

import numpy as np
import sounddevice as sd

import opus_loader  # noqa: F401  (must load first)
import opuslib

SAMPLE_RATE   = 48000
CHANNELS      = 2          # wire format / playback (always stereo)
FRAME_MS      = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000        # 960 samples per channel
FRAME_BYTES   = FRAME_SAMPLES * CHANNELS * 2          # int16 stereo


def _probe_input_channels(device) -> int:
    """Return 2 if mic supports stereo, else 1. Almost all real mics are mono."""
    try:
        info = sd.query_devices(device, "input")
        return 2 if info.get("max_input_channels", 1) >= 2 else 1
    except Exception:
        return 1


class OpusCodec:
    def __init__(self, bitrate: int = 510000):
        self.enc = opuslib.Encoder(SAMPLE_RATE, CHANNELS, opuslib.APPLICATION_VOIP)
        self.enc.bitrate = bitrate
        try:
            self.enc.complexity = 10
            self.enc.signal     = opuslib.SIGNAL_VOICE
        except Exception:
            pass
        self.dec = opuslib.Decoder(SAMPLE_RATE, CHANNELS)

    def encode_pcm(self, pcm_i16: bytes) -> bytes:
        # Opus wants exactly FRAME_SAMPLES per channel.
        return self.enc.encode(pcm_i16, FRAME_SAMPLES)

    def decode_to_pcm(self, payload: bytes) -> np.ndarray:
        out = self.dec.decode(payload, FRAME_SAMPLES, decode_fec=False)
        return np.frombuffer(out, dtype=np.int16).reshape(-1, CHANNELS)


class PeerBuffer:
    """Tiny jitter buffer + per-peer decoder."""

    def __init__(self, max_frames: int = 8):
        self.dec = opuslib.Decoder(SAMPLE_RATE, CHANNELS)
        self.q: deque[np.ndarray] = deque(maxlen=max_frames)
        self.last_seq: Optional[int] = None
        self.last_used = time.monotonic()

    def push(self, seq: int, payload: bytes):
        self.last_used = time.monotonic()
        # Handle one lost frame with FEC for the prior gap.
        try:
            if self.last_seq is not None and seq == self.last_seq + 2:
                fec = self.dec.decode(payload, FRAME_SAMPLES, decode_fec=True)
                self.q.append(np.frombuffer(fec, dtype=np.int16).reshape(-1, CHANNELS))
            pcm = self.dec.decode(payload, FRAME_SAMPLES, decode_fec=False)
        except opuslib.OpusError:
            return
        self.q.append(np.frombuffer(pcm, dtype=np.int16).reshape(-1, CHANNELS))
        self.last_seq = seq

    def pop(self) -> Optional[np.ndarray]:
        if not self.q:
            return None
        return self.q.popleft()


class AudioEngine:
    """
    Owns input + output sounddevice streams.

    - Input stream produces 20 ms blocks; we call `send_frame(opus_bytes)`.
    - Output stream pulls 20 ms blocks; we mix decoded frames from peers.
    """

    def __init__(self,
                 send_frame: Callable[[bytes], None],
                 input_device: Optional[int] = None,
                 output_device: Optional[int] = None):
        self.send_frame = send_frame
        self.codec = OpusCodec()
        self.peers: Dict[bytes, PeerBuffer] = {}
        self.lock = threading.Lock()
        self._talking = False
        self._mic_gain = 1.0
        self._out_gain = 1.0
        self._noise_gate_dbfs = -55.0          # below this, mic is silenced
        self.input_device = input_device
        self.output_device = output_device
        self._in_stream: Optional[sd.InputStream] = None
        self._out_stream: Optional[sd.OutputStream] = None
        self._last_in_rms: float = 0.0
        self._last_out_rms: float = 0.0

    # ---- mic / output gains -------------------------------------------------
    def set_talking(self, on: bool):
        self._talking = bool(on)

    def set_mic_gain(self, g: float):
        self._mic_gain = max(0.0, min(4.0, float(g)))

    def set_out_gain(self, g: float):
        self._out_gain = max(0.0, min(4.0, float(g)))

    @property
    def input_level(self) -> float:
        return self._last_in_rms

    @property
    def output_level(self) -> float:
        return self._last_out_rms

    # ---- streams ------------------------------------------------------------
    def start(self):
        self._in_channels = _probe_input_channels(self.input_device)
        last_err = None
        for ch in (self._in_channels, 1, 2):
            try:
                self._in_stream = sd.InputStream(
                    samplerate=SAMPLE_RATE, channels=ch, dtype="int16",
                    blocksize=FRAME_SAMPLES, device=self.input_device,
                    callback=self._on_input, latency="low",
                )
                self._in_stream.start()
                self._in_channels = ch
                break
            except Exception as e:
                last_err = e
                self._in_stream = None
        if self._in_stream is None:
            raise RuntimeError(f"cannot open input device: {last_err}")
        self._out_stream = sd.OutputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16",
            blocksize=FRAME_SAMPLES, device=self.output_device,
            callback=self._on_output, latency="low",
        )
        self._out_stream.start()

    def stop(self):
        for s in (self._in_stream, self._out_stream):
            if s is not None:
                try:
                    s.stop(); s.close()
                except Exception:
                    pass
        self._in_stream = self._out_stream = None

    # ---- callbacks ----------------------------------------------------------
    def _on_input(self, indata, frames, timeinfo, status):
        # indata is shape (frames, in_channels) int16
        if not self._talking:
            self._last_in_rms = 0.0
            return
        arr = indata.astype(np.float32)
        if self._mic_gain != 1.0:
            arr = np.clip(arr * self._mic_gain, -32768, 32767)
        # noise gate
        rms = float(np.sqrt(np.mean(arr.astype(np.float64) ** 2)) + 1e-6)
        dbfs = 20.0 * np.log10(rms / 32768.0 + 1e-12)
        self._last_in_rms = min(1.0, rms / 32768.0)
        if dbfs < self._noise_gate_dbfs:
            return
        # Upmix to stereo if we captured mono — Opus encoder is always stereo on the wire.
        if arr.shape[1] == 1:
            arr = np.repeat(arr, 2, axis=1)
        elif arr.shape[1] > 2:
            arr = arr[:, :2]
        pcm = arr.astype(np.int16).tobytes()
        try:
            payload = self.codec.encode_pcm(pcm)
        except opuslib.OpusError:
            return
        try:
            self.send_frame(payload)
        except Exception:
            pass

    def _on_output(self, outdata, frames, timeinfo, status):
        mix = np.zeros((frames, CHANNELS), dtype=np.float32)
        with self.lock:
            stale = []
            for tok, pb in self.peers.items():
                frame = pb.pop()
                if frame is None:
                    if time.monotonic() - pb.last_used > 30.0:
                        stale.append(tok)
                    continue
                if frame.shape[0] != frames:
                    # if size differs (shouldn't), best-effort fit
                    if frame.shape[0] > frames:
                        frame = frame[:frames]
                    else:
                        pad = np.zeros((frames - frame.shape[0], CHANNELS), dtype=np.int16)
                        frame = np.concatenate([frame, pad], axis=0)
                mix += frame.astype(np.float32)
            for t in stale:
                self.peers.pop(t, None)
        if self._out_gain != 1.0:
            mix *= self._out_gain
        np.clip(mix, -32768, 32767, out=mix)
        out_i16 = mix.astype(np.int16)
        outdata[:] = out_i16
        rms = float(np.sqrt(np.mean(mix.astype(np.float64) ** 2)) + 1e-6)
        self._last_out_rms = min(1.0, rms / 32768.0)

    # ---- peer ingress -------------------------------------------------------
    def on_peer_packet(self, src_token: bytes, seq: int, payload: bytes):
        with self.lock:
            pb = self.peers.get(src_token)
            if pb is None:
                pb = PeerBuffer()
                self.peers[src_token] = pb
        pb.push(seq, payload)

    def clear_peers(self):
        with self.lock:
            self.peers.clear()


def list_devices():
    in_devs, out_devs = [], []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] >= 1:
            in_devs.append((i, d["name"]))
        if d["max_output_channels"] >= 1:
            out_devs.append((i, d["name"]))
    return in_devs, out_devs
