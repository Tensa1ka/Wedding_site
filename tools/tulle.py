"""Фон из фатина: мягкие полупрозрачные драпировки в тёплой шампани.
Плитка бесшовная по обеим осям – фон тянется на любую ширину и высоту.
Запуск: python3 tools/tulle.py assets/img/tulle.webp [ширина высота seed]"""
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

out = sys.argv[1]
W = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
H = int(sys.argv[3]) if len(sys.argv) > 3 else 2400
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 3
rng = np.random.default_rng(seed)
X = np.arange(W)[None, :].astype(float)
Y = np.arange(H)[:, None].astype(float) / H
TAU = 2 * np.pi


def drape(n, wmin, wmax, sway):
    h = np.zeros((H, W))
    for c in rng.uniform(0, W, n):
        w = rng.uniform(wmin, wmax)
        a = rng.uniform(.5, 1.0)
        # колыхание по вертикали – целые периоды, чтобы плитка стыковалась
        k1, k2 = 1, rng.integers(1, 3)
        drift = sway * (np.sin(TAU * (k1 * Y + rng.uniform(0, 1))) + .35 * np.sin(TAU * (k2 * Y + rng.uniform(0, 1))))
        for shift in (-W, 0, W):
            d = (X - c - drift - shift) / w
            h += a * np.exp(-d * d)
    return gaussian_filter(h, 1.6, mode='wrap')


def shade(h, k):
    dx = np.gradient(np.pad(h, ((0, 0), (1, 1)), mode='wrap'), axis=1)[:, 1:-1] * k
    nz = 1 / np.sqrt(1 + dx * dx)
    return np.clip(.55 - .5 * dx * nz, 0, 1), 1 - nz


h1 = drape(int(30 * W / H + 14), 22, 80, 16)
h2 = drape(int(16 * W / H + 8), 70, 190, 24)
d1, s1 = shade(h1, 70)
d2, s2 = shade(h2, 50)

v = .8 + .17 * (d1 - .5) + .14 * (d2 - .5) + .15 * s1 ** .85 + .08 * s2
v -= .06 * gaussian_filter(rng.normal(0, 1, (H, W)), 60, mode='wrap')   # неровность освещения
v = np.clip(v, 0, 1.1)

tint = gaussian_filter(rng.normal(0, 1, (H, W)), 140, mode='wrap')
tint = (tint - tint.min()) / (np.ptp(tint) + 1e-6)
shadow = np.array([214, 196, 182]) / 255
blush = np.array([228, 200, 194]) / 255
light = np.array([253, 250, 246]) / 255
base = shadow + (blush - shadow) * (tint[..., None] * .55)
t = np.clip((v - .55) / .5, 0, 1)[..., None]
col = base + (light - base) * t ** .85
col += rng.normal(0, .006, (H, W, 1))
img = Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8))
img.save(out, quality=76, method=6)
print(out, img.size)
