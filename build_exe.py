"""
Build PhantomTalk.exe via PyInstaller.

Bundles client/main.py + libs/opus.dll + sounddevice's portaudio into a single
windowed executable, then copies the result into website/static/ so visitors of
the landing page can download it directly.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT = os.path.join(HERE, "client")
LIBS   = os.path.join(HERE, "libs")
WEB_STATIC = os.path.join(HERE, "website")
DIST   = os.path.join(HERE, "dist")

OPUS_DLL = os.path.join(LIBS, "opus.dll")
ENTRY    = os.path.join(CLIENT, "main.py")
ICON     = None  # set to a .ico path if you add one

def main():
    if not os.path.isfile(OPUS_DLL):
        print(f"[!] missing {OPUS_DLL}")
        sys.exit(2)

    # PyInstaller path-sep for --add-data on Windows is `;`
    add_data = [
        f"{OPUS_DLL};.",
        f"{OPUS_DLL};libs",
    ]
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "PhantomTalk",
        "--windowed",
        "--onefile",
        "--paths", CLIENT,
    ]
    for d in add_data:
        cmd += ["--add-data", d]
    cmd += [
        "--hidden-import", "opuslib.api.ctl",
        "--hidden-import", "opuslib.api.info",
        "--hidden-import", "opuslib.api.encoder",
        "--hidden-import", "opuslib.api.decoder",
    ]
    if ICON and os.path.isfile(ICON):
        cmd += ["--icon", ICON]
    cmd.append(ENTRY)

    print("[+] running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=HERE)

    exe = os.path.join(DIST, "PhantomTalk.exe")
    if not os.path.isfile(exe):
        print("[!] build did not produce", exe)
        sys.exit(3)

    # Publish on landing page
    os.makedirs(WEB_STATIC, exist_ok=True)
    dst = os.path.join(WEB_STATIC, "PhantomTalk.exe")
    shutil.copy2(exe, dst)
    size_mb = os.path.getsize(dst) / 1024 / 1024
    print(f"[OK] built {exe}  ({size_mb:.1f} MB)")
    print(f"[OK] published to {dst}")

if __name__ == "__main__":
    main()
