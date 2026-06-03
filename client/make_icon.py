"""
Generate the PhantomTalk app icon — a glowing ember orb on a dark rounded
square — as a multi-resolution .ico (plus a .png).  Run once; output is
committed so the build doesn't need numpy/PIL at build time.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024
cx = cy = S / 2.0

# ---------- dark rounded-square background ----------
bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
db = ImageDraw.Draw(bg)
m = int(S * 0.05)
db.rounded_rectangle([m, m, S - m, S - m], radius=int(S * 0.23), fill=(18, 12, 10, 255))

# ---------- ember orb via numpy radial gradient ----------
yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
R = S * 0.30
norm = dist / R
n = np.clip(norm, 0, 1)

stops = [
    (0.00, (255, 255, 255)),
    (0.14, (255, 217, 168)),
    (0.34, (255, 106, 44)),
    (0.66, (214, 31, 18)),
    (1.00, (70, 14, 9)),
]
rgb = np.zeros((S, S, 3), np.float32)
for i in range(len(stops) - 1):
    t0, c0 = stops[i]
    t1, c1 = stops[i + 1]
    mask = (n >= t0) & (n <= t1)
    tt = (n[mask] - t0) / (t1 - t0 + 1e-9)
    for ch in range(3):
        rgb[..., ch][mask] = c0[ch] + (c1[ch] - c0[ch]) * tt

alpha = np.where(norm <= 1.0, 255.0, 0.0).astype(np.float32)
edge = (norm > 0.90) & (norm <= 1.0)
alpha[edge] = (1.0 - (norm[edge] - 0.90) / 0.10) * 255.0
orb_img = Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")

# ---------- bloom halo ----------
halo = orb_img.filter(ImageFilter.GaussianBlur(S * 0.07))
ha = halo.split()[3].point(lambda a: int(a * 0.75))
halo.putalpha(ha)

# ---------- compose ----------
canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
canvas.alpha_composite(bg)
canvas.alpha_composite(halo)
canvas.alpha_composite(orb_img)

# ---------- thin glowing ring ----------
ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
dr = ImageDraw.Draw(ring)
rr = S * 0.40
dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 154, 90, 130), width=int(S * 0.009))
ring = ring.filter(ImageFilter.GaussianBlur(S * 0.004))
canvas.alpha_composite(ring)

# ---------- save ----------
png_path = os.path.join(HERE, "phantomtalk.png")
ico_path = os.path.join(HERE, "phantomtalk.ico")
canvas.resize((512, 512), Image.LANCZOS).save(png_path)
big = canvas.resize((256, 256), Image.LANCZOS)
big.save(ico_path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("saved", ico_path, "and", png_path)
