"""
Ensure libopus is loadable before `import opuslib`.

opuslib calls ctypes.util.find_library('opus') at import time; on Windows
that almost never finds anything in PATH.  We ship our own copy in
PhantomTalk/libs/opus.dll, preload it, and patch find_library so opuslib
picks it up.
"""
import ctypes
import ctypes.util
import os
import sys

def _candidates():
    here = os.path.dirname(os.path.abspath(__file__))
    proj = os.path.dirname(here)
    # Frozen (PyInstaller) bundle keeps data files next to the exe / in _MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    yield os.path.join(here, "opus.dll")
    yield os.path.join(proj, "libs", "opus.dll")
    if meipass:
        yield os.path.join(meipass, "opus.dll")
        yield os.path.join(meipass, "libs", "opus.dll")
    yield "opus.dll"
    yield "libopus-0.dll"


def load():
    last_err = None
    for p in _candidates():
        if p and (os.path.isfile(p) or not os.path.dirname(p)):
            try:
                ctypes.CDLL(p)
                _orig = ctypes.util.find_library
                def _patched(name, _o=_orig, _p=p):
                    if name == "opus":
                        return _p
                    return _o(name)
                ctypes.util.find_library = _patched
                return p
            except OSError as e:
                last_err = e
                continue
    raise RuntimeError(f"libopus not found (tried bundled paths): {last_err}")


load()
