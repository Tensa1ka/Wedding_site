"""Вырезает элементы оформления из присланных листов (tools/src) в assets/img.
Фон листов – нарисованная «шахматка» вместо прозрачности: светлые нейтральные клетки,
связанные с краем кадра, становятся прозрачными. Текст-заглушки на сердце и карточке
программы закрашиваются по окружающему фону.
Запуск: python3 tools/cut.py [имя ...]"""
import os
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'src')
DST = os.path.join(HERE, '..', 'assets', 'img')
PREVIEW = os.path.join(HERE, 'out')
os.makedirs(PREVIEW, exist_ok=True)


def load(name):
    return np.asarray(Image.open(os.path.join(SRC, name)).convert('RGB')).astype(float)


def cut_checker(rgb, holes=0):
    """Альфа-маска: прозрачна шахматка, связанная с краем; holes > 0 – ещё и закрытые
    просветы шахматки площадью от holes пикселей (кружево)."""
    lum = rgb.mean(2)
    chroma = rgb.max(2) - rgb.min(2)
    cand = (chroma <= 4.5) & (lum >= 228)
    lab, n = ndi.label(cand)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    keep = np.isin(lab, edge[edge > 0])
    if holes:
        sizes = ndi.sum(cand, lab, range(1, n + 1))
        flat = ndi.standard_deviation(lum, lab, range(1, n + 1))
        ok = np.zeros(n + 1, bool)
        ok[1:] = (sizes >= holes) & (flat < 9)
        keep |= ok[lab]
    keep = ndi.binary_opening(keep, iterations=1)
    alpha = 1 - keep.astype(float)
    alpha = ndi.binary_opening(alpha > .5, iterations=1).astype(float)
    alpha = ndi.gaussian_filter(alpha, .8)
    return np.clip(alpha, 0, 1)


def solidify(alpha, band):
    """Всё, что глубже band пикселей от контура силуэта, – непрозрачно
    (защищает светлое поле от ложных «просветов»)."""
    sil = ndi.binary_fill_holes(ndi.binary_closing(alpha > .5, iterations=6))
    core = ndi.binary_erosion(sil, iterations=band)
    return np.maximum(alpha, ndi.gaussian_filter(core.astype(float), .8))


def erase(alpha, *boxes):
    """Убирает подписи листа: прямоугольники (y0, y1, x0, x1) в координатах кадра."""
    alpha = alpha.copy()
    for y0, y1, x0, x1 in boxes:
        alpha[max(0, y0):y1, max(0, x0):x1] = 0
    return alpha


def inpaint(rgb, mask, iters=600):
    """Гармоническое заполнение области mask по соседям + зерно бумаги."""
    out = rgb.copy()
    known = ~mask
    # стартовое заполнение – средний цвет края
    for c in range(3):
        ch = out[..., c]
        ch[mask] = ch[ndi.binary_dilation(mask, iterations=2) & known].mean()
    k = np.array([[0, .25, 0], [.25, 0, .25], [0, .25, 0]])
    for _ in range(iters):
        for c in range(3):
            sm = ndi.convolve(out[..., c], k, mode='nearest')
            out[..., c] = np.where(mask, sm, rgb[..., c])
    return out


def grain_like(rgb, mask, ref):
    """Добавляет в залитую область зерно с той же амплитудой, что у ref."""
    hp = rgb - ndi.gaussian_filter(rgb, (2, 2, 0))
    amp = hp[ref].std(0)
    rng = np.random.default_rng(7)
    noise = ndi.gaussian_filter(rng.normal(0, 1, rgb.shape[:2]), .8)
    noise /= noise.std()
    lum_noise = noise[..., None] * amp.mean()
    return np.where(mask[..., None], rgb + lum_noise, rgb)


def save(name, rgb, alpha=None, quality=86):
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    if alpha is None:
        im = Image.fromarray(rgb, 'RGB')
    else:
        a = np.clip(alpha * 255, 0, 255).astype(np.uint8)
        im = Image.fromarray(np.dstack([rgb, a]), 'RGBA')
        bbox = Image.fromarray(a).point(lambda v: 255 if v > 8 else 0).getbbox()
        im = im.crop((max(0, bbox[0] - 2), max(0, bbox[1] - 2), min(im.width, bbox[2] + 2), min(im.height, bbox[3] + 2)))
        # превью на тёмном фоне – видно ореолы
        pv = Image.new('RGBA', im.size, (35, 39, 11, 255))
        pv.alpha_composite(im)
        pv.convert('RGB').save(os.path.join(PREVIEW, '_cut_' + name + '.png'))
    path = os.path.join(DST, name + '.webp')
    im.save(path, 'WEBP', quality=quality, method=6, alpha_quality=92)
    print(f'{name}.webp {im.size[0]}x{im.size[1]} {os.path.getsize(path) // 1024} KB')
    return im


def text_mask(rgb, region, thr=10):
    """Тёмно-оливковые буквы на светлом фоне внутри region."""
    lum = rgb.mean(2)
    bg = ndi.median_filter(lum, size=25)
    olive = (rgb[..., 1] - rgb[..., 2]) > 6      # буквы зеленоватые, тени кружева – нет
    m = ((bg - lum) > thr) & olive & region
    m = ndi.binary_dilation(m, iterations=5)
    return m & region


# ---------- элементы ----------



def flowers_top():
    rgb = load('sheet-decor.webp')[628:1003, 52:552]
    # подпись «3. Цветы сверху»: лист y 983–1010, x 195–395
    return save('flowers-top', rgb, erase(cut_checker(rgb), (355, 380, 140, 345)))


def flowers_arch():
    rgb = load('sheet-decor.webp')[725:970, 570:990]
    return save('flowers-arch', rgb, cut_checker(rgb))


def oval():
    rgb = load('sheet-decor.webp')[1024:1458, 328:692]
    a = solidify(cut_checker(rgb, holes=40), 26)
    # хвост подписи над рамкой: лист y 1024–1040
    return save('oval', rgb, erase(a, (0, 17, 0, 364)))


def frame():
    """Рама программы без бумаги: левая половина (резкая) отражается вправо, поле внутри
    заливается тем же тауповым тоном. Бумажная карточка и цветы – отдельными слоями на сайте."""
    rgb = load('sheet-program.webp')[4:712, 540:996]
    a = solidify(cut_checker(rgb, holes=40), 24)
    a = erase(a, (684, 708, 0, 130))
    H, W = a.shape
    # ось симметрии – середина силуэта
    cols = np.where((a > .5).sum(0) > H * .3)[0]
    c = (cols.min() + cols.max()) / 2
    xs = np.arange(W)
    src = np.clip(np.round(2 * c - xs).astype(int), 0, W - 1)
    right = xs > c
    rgb = rgb.copy()
    rgb[:, right] = rgb[:, src[right]]
    a = a.copy()
    a[:, right] = a[:, src[right]]
    # поле под бумагой (x 50..2c-50, y 137..586 в кадре): квадратичная подгонка по видимым кускам поля
    yy, xx = np.mgrid[:H, :W]
    fx0, fx1 = 52, int(round(2 * c - 52))                       # внутренний край багета – x 50
    card = (xx >= fx0) & (xx <= fx1) & (yy >= 136) & (yy <= 588)
    # тон поля – как у видимых полос над и под бывшей бумагой: светлее вверху, темнее к низу
    top_c, bot_c = np.array([216., 204., 190.]), np.array([196., 182., 160.])
    k = np.clip((yy - 136) / (588 - 136), 0, 1)[..., None] ** 2
    fill = top_c * (1 - k) + bot_c * k
    # лёгкая тень у краёв поля, как под багетом
    d = ndi.distance_transform_edt(card)
    fill *= (1 - .1 * np.exp(-d / 7))[..., None]
    rng = np.random.default_rng(11)
    mottle = ndi.gaussian_filter(rng.normal(0, 1, (H, W)), 5)
    mottle = ndi.gaussian_filter(rng.normal(0, 1, (H, W)), 3)
    mottle *= 2.5 / mottle.std()                                  # пятнистость, как у видимого поля
    fill += (mottle + ndi.gaussian_filter(rng.normal(0, 2.4, (H, W)), 1))[..., None]
    soft = ndi.gaussian_filter(card.astype(float), 2.5)[..., None] * card[..., None]
    soft = np.maximum(soft, ndi.binary_erosion(card, iterations=4)[..., None])
    rgb = rgb * (1 - soft) + fill * soft
    # чистый внешний контур: без светлой бахромы от шахматки
    a = np.minimum(a, ndi.gaussian_filter(ndi.binary_erosion(a > .5, iterations=2).astype(float), .8))
    print('frame field x', fx0, fx1, 'of', W, 'axis', c)
    return save('frame', rgb, a)






# ---------- второй набор (цветы, сердце с кружевом, фон-штора, вазы-фото) ----------

def load_rgba(name):
    return np.asarray(Image.open(os.path.join(SRC, name)).convert('RGBA')).astype(float)


def shrink(rgb, alpha, max_w):
    """Уменьшает до max_w по ширине (картинки листов крупнее, чем нужно сайту)."""
    h, w = rgb.shape[:2]
    if w <= max_w:
        return rgb, alpha
    im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255, 0, 255)]).astype(np.uint8), 'RGBA')
    im = im.resize((max_w, round(h * max_w / w)), Image.LANCZOS)
    a = np.asarray(im).astype(float)
    return a[..., :3], a[..., 3] / 255


def heart_lace():
    """Сердце с кружевом: имена и дата на картинке закрашиваются гладким кремовым тоном –
    сайт пишет их сам, с анимацией."""
    a = load_rgba('heart-lace.png')
    rgb, alpha = a[..., :3].copy(), a[..., 3] / 255
    H, W = alpha.shape
    yy, xx = np.mgrid[:H, :W]
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = rgb.mean(2)
    box = (yy > H * .18) & (yy < H * .78) & (xx > W * .18) & (xx < W * .82)
    # буквы оливковые (зелёный не слабее красного); золотой кант и жемчуг – тёплые, их не трогаем
    ink = box & (lum < 228) & (G - R > -10) & (G - B > 8)
    ink = ndi.binary_dilation(ink, iterations=5) & box
    # гладкая поверхность поля: квадратичная подгонка по чистым кремовым пикселям
    cream = box & ~ndi.binary_dilation(ink, iterations=4) & (np.linalg.norm(rgb - np.array([244, 239, 228]), axis=2) < 14)
    X, Y = xx / W, yy / H
    def terms(x, y):
        return np.stack([np.ones_like(x), x, y, x * x, y * y, x * y], -1)
    fill = np.zeros_like(rgb)
    T = terms(X, Y)
    for c in range(3):
        coef, *_ = np.linalg.lstsq(T[cream], rgb[..., c][cream], rcond=None)
        fill[..., c] = T @ coef
    rng = np.random.default_rng(3)
    fill += ndi.gaussian_filter(rng.normal(0, 1.3, (H, W)), .7)[..., None]
    soft = np.clip(ndi.gaussian_filter(ink.astype(float), 2.5) * 1.6, 0, 1)[..., None]
    rgb = rgb * (1 - soft) + fill * soft
    rgb, alpha = shrink(rgb, alpha, 1000)
    return save('heart', rgb, alpha)


# букеты из листов: (лист, рамка x0, y0, x1, y1, имя)
BLOOMS = [
    ('flowers-a.png', (26, 15, 607, 679), 'bloom-corner-l'),
    ('flowers-a.png', (905, 16, 1435, 685), 'bloom-corner-r'),
    ('flowers-a.png', (601, 40, 906, 464), 'bloom-lily-rose'),
    ('flowers-a.png', (858, 421, 1136, 816), 'bloom-lily'),
    ('flowers-a.png', (512, 454, 883, 881), 'bloom-posy'),
    ('flowers-a.png', (109, 505, 544, 833), 'bloom-roses'),
    ('flowers-a.png', (1158, 568, 1370, 862), 'bloom-peony'),
    ('flowers-a.png', (23, 729, 518, 1069), 'bloom-spray'),
    ('flowers-b.png', (13, 650, 674, 1071), 'bloom-wide'),
]


def blooms():
    cache = {}
    for sheet, (x0, y0, x1, y1), name in BLOOMS:
        if sheet not in cache:
            a = load_rgba(sheet)
            m = ndi.binary_closing(a[..., 3] > 20, iterations=4)
            cache[sheet] = (a, ndi.label(m)[0])
        a, lab = cache[sheet]
        box = lab[y0:y1, x0:x1]
        ids, cnt = np.unique(box[box > 0], return_counts=True)
        own = box == ids[np.argmax(cnt)]                         # только свой букет, без соседей
        own = ndi.binary_dilation(own, iterations=2)
        rgb = a[y0:y1, x0:x1, :3]
        alpha = a[y0:y1, x0:x1, 3] / 255 * own
        rgb, alpha = shrink(rgb, alpha, 720)
        save(name, rgb, alpha)


def backdrop():
    """Фон страницы – одна штора целиком (на сайте медленно едет при прокрутке)."""
    return save('backdrop', load('backdrop.png'), quality=84)


def urns_photo():
    """Нижняя композиция – фото целиком; края растворяются в фоне средствами CSS."""
    rgb = load('urns-photo.png')
    im = Image.fromarray(rgb.astype(np.uint8)).resize((1600, round(rgb.shape[0] * 1600 / rgb.shape[1])), Image.LANCZOS)
    return save('urns', np.asarray(im).astype(float), quality=84)


def envelope():
    """Конверт для заставки: печать отдельно (уходит целиком, не ломаясь),
    под ней – бумага, чтобы клапаны раскрывались без «дырки»."""
    a = load_rgba('envelope.webp')
    rgb, alpha = a[..., :3], a[..., 3] / 255
    H, W = alpha.shape
    cx, cy, r = 495, 873, 178
    yy, xx = np.mgrid[:H, :W]
    disk = (xx - cx) ** 2 + (yy - cy) ** 2 < r * r
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    gold = disk & ((R - B) > 80) & (R > 120)
    gold = ndi.binary_fill_holes(ndi.binary_closing(gold, iterations=6))
    gold = ndi.binary_opening(gold, iterations=4)                # отрезаем тонкие золотые веточки рядом
    gold &= (xx - cx) ** 2 + (yy - cy) ** 2 < 162 ** 2
    lab, n = ndi.label(gold)
    gold = lab == (np.argmax(ndi.sum(gold, lab, range(1, n + 1))) + 1)
    seal_a = ndi.gaussian_filter(ndi.binary_erosion(gold, iterations=1).astype(float), .9)
    ys, xs = np.where(gold)
    y0, y1, x0, x1 = ys.min() - 4, ys.max() + 5, xs.min() - 4, xs.max() + 5
    save('env-seal', rgb[y0:y1, x0:x1], seal_a[y0:y1, x0:x1])
    # бумага под печатью: гармоническое заполнение с запасом по краю (тень печати)
    hole = ndi.binary_dilation(gold, iterations=14)
    py0, py1, px0, px1 = y0 - 40, y1 + 40, x0 - 40, x1 + 40
    sub = rgb[py0:py1, px0:px1]
    m = hole[py0:py1, px0:px1]
    small = Image.fromarray(np.clip(sub, 0, 255).astype(np.uint8)).resize((sub.shape[1] // 2, sub.shape[0] // 2), Image.LANCZOS)
    ms = np.asarray(Image.fromarray(m.astype(np.uint8) * 255).resize(small.size, Image.BILINEAR)) > 20
    filled = inpaint(np.asarray(small).astype(float), ms, iters=900)
    up = np.asarray(Image.fromarray(np.clip(filled, 0, 255).astype(np.uint8)).resize((sub.shape[1], sub.shape[0]), Image.BICUBIC)).astype(float)
    soft = ndi.gaussian_filter(m.astype(float), 3)[..., None]
    rng = np.random.default_rng(5)
    up += ndi.gaussian_filter(rng.normal(0, 2.2, up.shape[:2]), .8)[..., None]   # фактура бумаги
    sub = sub * (1 - soft) + up * soft
    rgb = rgb.copy()
    rgb[py0:py1, px0:px1] = sub
    return save('envelope', rgb, alpha, quality=86)


ALL = {f.__name__: f for f in (flowers_top, flowers_arch, oval, frame,
                                     heart_lace, blooms, backdrop, urns_photo, envelope)}
if __name__ == '__main__':
    for n in sys.argv[1:] or ALL:
        ALL[n.replace('-', '_')]()
