"""
Build PhantomTalkSetup.exe — the cinematic installer.

Bundles dist/PhantomTalk.exe (the app), the icon and the fonts inside a single
windowed setup executable, then copies it to website/ for download.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLIENT = os.path.join(ROOT, "client")
DIST = os.path.join(ROOT, "dist")
WEB = os.path.join(ROOT, "website")

APP_EXE = os.path.join(DIST, "PhantomTalk.exe")
ICON = os.path.join(CLIENT, "phantomtalk.ico")
PNG = os.path.join(CLIENT, "phantomtalk.png")
FONTS = os.path.join(CLIENT, "fonts")
ENTRY = os.path.join(HERE, "installer.py")


def main():
    if not os.path.isfile(APP_EXE):
        print(f"[!] build the app first — missing {APP_EXE}")
        sys.exit(2)

    add_data = [
        f"{APP_EXE};.",
        f"{ICON};.",
        f"{PNG};.",
        f"{FONTS};fonts",
    ]
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", "PhantomTalkSetup",
        "--windowed", "--onefile",
        "--icon", ICON,
    ]
    for d in add_data:
        cmd += ["--add-data", d]
    cmd.append(ENTRY)

    print("[+] running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    out = os.path.join(DIST, "PhantomTalkSetup.exe")
    if not os.path.isfile(out):
        print("[!] no setup produced"); sys.exit(3)
    os.makedirs(WEB, exist_ok=True)
    dst = os.path.join(WEB, "PhantomTalkSetup.exe")
    shutil.copy2(out, dst)
    mb = os.path.getsize(out) / 1024 / 1024
    print(f"[OK] built {out}  ({mb:.1f} MB)")
    print(f"[OK] published to {dst}")


if __name__ == "__main__":
    main()
