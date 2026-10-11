"""Бархатный занавес: бесшовная по горизонтали текстура (пыльная роза).
Запуск: python3 tools/velvet.py assets/img/velvet.webp"""
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

W, H = 1800, 1800                     # плитка повторяется по горизонтали
rng = np.random.default_rng(11)
X = np.arange(W)[None, :].astype(float)
Y = np.arange(H)[:, None].astype(float) / H

# складки – мягкие «цилиндры» разной ширины, слегка гуляющие по высоте
h = np.zeros((H, W))
n = 38
centers = np.sort(rng.uniform(0, W, n))
for c in centers:
    w = rng.uniform(18, 64)
    a = rng.uniform(.6, 1.0) * (w / 50) ** .8
    drift = rng.uniform(-90, 90) * np.abs(Y - .1) ** 1.3 + 12 * np.sin(2 * np.pi * (Y * rng.uniform(.5, 1.4) + rng.uniform(0, 1)))
    cx = c + drift
    for shift in (-W, 0, W):         # бесшовность
        d = (X - cx - shift) / w
        h += a * np.exp(-d * d)
h = gaussian_filter(h, 1.2, mode='wrap')

dx = np.gradient(h, axis=1) * 60
dxx = np.gradient(dx, axis=1) * 60
nz = 1 / np.sqrt(1 + dx * dx)

diffuse = np.clip(.5 - .5 * dx * nz, 0, 1)                 # свет слева
sheen = (1 - nz) ** 1.1                                    # ворс блестит на скатах
cav = np.clip(dxx / (np.percentile(np.abs(dxx), 98) + 1e-6), 0, 1)
v = .1 + .36 * diffuse + .78 * sheen
v *= 1 - .8 * cav                                         # глубокие впадины
v *= .78 + .3 * (1 - Y) ** .7                              # свет сверху
v *= 1 - .45 * np.exp(-Y / .025)                           # тень под карнизом

grain = rng.normal(0, 1, (H, W)).astype(np.float32)
grain = gaussian_filter(grain, .6, mode='wrap')
v = v * (1 + .07 * grain)

dark = np.array([58, 26, 31]) / 255
mid = np.array([190, 133, 128]) / 255                      # пыльная роза
hi = np.array([250, 222, 212]) / 255
t = np.clip(v, 0, 1)[..., None]
col = np.where(t < .5, dark + (mid - dark) * (t / .5) ** .9, mid + (hi - mid) * ((t - .5) / .5) ** 1.2)
img = Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8))
out = sys.argv[1] if len(sys.argv) > 1 else 'velvet.webp'
img.save(out, quality=76, method=6)
print(out, img.size)
