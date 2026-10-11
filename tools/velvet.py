"""Бархатный занавес: бесшовная по горизонтали текстура (тёмная олива).
Складки чуть наклонены и сходятся книзу; левую половину занавеса сайт отражает – полотна перекрещиваются.
Запуск: python3 tools/velvet.py assets/img/velvet.webp"""
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

W, H = 1600, 2000                     # плитка повторяется по горизонтали
rng = np.random.default_rng(23)
X = np.arange(W)[None, :].astype(float)
Y = np.arange(H)[:, None].astype(float) / H


def tubes(n, tilt, wmin, wmax):
    """Складки-трубки: в каждой точке видна ближайшая (самая высокая) трубка."""
    best = np.full((H, W), -1.0)
    dval = np.ones((H, W))
    for c in rng.uniform(0, W, n):
        w = rng.uniform(wmin, wmax)
        a = rng.uniform(.75, 1.0)
        drift = tilt * rng.uniform(.5, 1.4) * Y ** 1.6 \
            + 8 * np.sin(2 * np.pi * (Y * rng.uniform(.4, 1.1) + rng.uniform(0, 1)))
        for shift in (-W, 0, W):
            d = (X - c - drift - shift) / w
            prof = a * np.sqrt(np.clip(1 - d * d, 0, 1))
            win = prof > best
            best = np.where(win, prof, best)
            dval = np.where(win, np.abs(d), dval)
    return best, dval


h, dval = tubes(120, 320, 11, 26)
dval = np.clip(dval, 0, 1)
nz = np.sqrt(1 - dval ** 2)                                 # нормаль трубки к зрителю
side = np.sign(np.gradient(np.pad(h, ((0, 0), (1, 1)), mode='wrap'), axis=1)[:, 1:-1])

# бархат: середина трубки тёмная, края вспыхивают ворсом, стыки трубок уходят в черноту
sheen = (1 - nz) ** 1.05
lit = np.clip(1 - np.abs(dval * side + .45) / .5, 0, 1)    # мягкий блик на левой стороне трубки
v = .21 + .08 * nz + 1.15 * sheen * (.72 + .28 * (side < 0)) + .16 * lit
v *= np.clip((1 - dval) / .06, 0, 1) ** .8                  # стык двух трубок
v *= .55 + .45 * np.clip(h, 0, 1)                           # дальние трубки темнее
v = gaussian_filter(v, .6, mode='wrap')
v *= .78 + .35 * np.exp(-((Y - .4) / .55) ** 2)
v *= 1 - .5 * np.exp(-Y / .02)

grain = gaussian_filter(rng.normal(0, 1, (H, W)), .7, mode='wrap')
v = np.clip(v * (1 + .09 * grain), 0, 1.2)

# тонирование: почти чёрная олива в тенях, болотная середина, светлый мох на бликах
stops = [(0, (5, 6, 0)), (.2, (22, 24, 4)), (.42, (44, 47, 12)), (.65, (78, 83, 34)), (.85, (118, 123, 66)), (1.2, (170, 174, 116))]
t = v
col = np.zeros((H, W, 3))
for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
    m = (t >= t0) & (t < t1)
    k = ((t - t0) / (t1 - t0))[..., None]
    col = np.where(m[..., None], np.array(c0) + (np.array(c1) - np.array(c0)) * k, col)
col = np.where((t >= stops[-1][0])[..., None], np.array(stops[-1][1]), col)
img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8))
out = sys.argv[1] if len(sys.argv) > 1 else 'velvet.webp'
img.save(out, quality=78, method=6)
print(out, img.size)
