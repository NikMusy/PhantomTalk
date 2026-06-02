import imageio
import numpy as np
import os

src = r"C:\Users\Николай\Downloads\video.mp4"
out = r"C:\Users\Николай\PhantomTalk\_frames"
os.makedirs(out, exist_ok=True)

reader = imageio.get_reader(src, "ffmpeg")
meta = reader.get_meta_data()
print("meta:", {k: meta.get(k) for k in ("fps", "duration", "size", "nframes")})

frames = []
for i, fr in enumerate(reader):
    frames.append(fr)
n = len(frames)
print("total frames:", n, "shape:", frames[0].shape if n else None)

idxs = np.linspace(0, n - 1, 9).astype(int)
for j, i in enumerate(idxs):
    imageio.imwrite(os.path.join(out, f"f{j}.jpg"), frames[int(i)])
    print("wrote", f"f{j}.jpg", "from frame", int(i))
