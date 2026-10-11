"""PNG из tools/out → WebP в assets/img (с прозрачностью).
У букетов срезаются пустые поля, кроме стороны, которой букет прижат к краю экрана.
Запуск: python3 tools/export.py [имя ...]"""
import os
import sys
from PIL import Image

src = os.path.join(os.path.dirname(__file__), 'out')
dst = os.path.join(os.path.dirname(__file__), '..', 'assets', 'img')
os.makedirs(dst, exist_ok=True)

# какие края не обрезать: l – левый, b – нижний
KEEP = {'corner': 'lb', 'garland': 'l', 'finale': 'b', 'callas': 'b', 'cluster': ''}

names = sys.argv[1:] or [f[:-4] for f in os.listdir(src) if f.endswith('.png') and not f.startswith('_')]
for n in names:
    im = Image.open(os.path.join(src, n + '.png')).convert('RGBA')
    if n in KEEP:
        l, t, r, b = im.getchannel('A').getbbox()
        k = KEEP[n]
        im = im.crop((0 if 'l' in k else max(0, l - 4), max(0, t - 4), min(im.size[0], r + 4), im.size[1] if 'b' in k else min(im.size[1], b + 4)))
    out = os.path.join(dst, n + '.webp')
    im.save(out, 'WEBP', quality=84, method=6, alpha_quality=90)
    print(f'{n}.webp {im.size[0]}x{im.size[1]} {os.path.getsize(out) // 1024} KB')
