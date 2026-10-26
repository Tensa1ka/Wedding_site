"""Готовит присланные картинки (tools/src) для сайта (assets/img).
Фон листов – нарисованная «шахматка» вместо прозрачности: клетки, связанные с краем кадра, становятся прозрачными.
Рамки «Приглашение», «Адрес», «Программа», «Дресс-код» – без текста (текст – на сайте), золотые орнаменты
с рамок и образцов – отдельными картинками. Обложка: присланное фото и его широкая версия 1920 × 1080 (и 2880 × 1620),
продолженная вправо и влево тем же фоном. Новые рамки – как прислали: убран только фон вокруг, «Адрес» приведён к кадру образца.
Запуск: python3 tools/cut.py [имя ...]  (нужны numpy, scipy, Pillow)"""
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


def cut_checker(rgb, holes=0, lum_min=228, chroma_max=4.5):
    """Альфа-маска: прозрачна шахматка, связанная с краем; holes > 0 – ещё и закрытые
    просветы шахматки площадью от holes пикселей (кружево)."""
    lum = rgb.mean(2)
    chroma = rgb.max(2) - rgb.min(2)
    cand = (chroma <= chroma_max) & (lum >= lum_min)
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


def heart_wreath():
    """Сердце из цветов для «Спасибо» после анкеты: светлый ровный фон и середина – прозрачные."""
    rgb = load('heart-wreath.webp')
    bg = np.median(np.concatenate([rgb[:20].reshape(-1, 3), rgb[-20:].reshape(-1, 3)]), 0)
    flat = (np.abs(rgb - bg).max(2) < 9)
    lab, n = ndi.label(flat)
    sizes = ndi.sum(flat, lab, range(1, n + 1))
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    keep = np.isin(lab, edge[edge > 0]) | np.isin(lab, 1 + np.where(sizes > 3000)[0])   # фон и середина сердца
    alpha = 1 - ndi.binary_opening(keep, iterations=1).astype(float)
    alpha[:4], alpha[-4:], alpha[:, :4], alpha[:, -4:] = 0, 0, 0, 0     # артефакты морфологии у края кадра
    alpha = ndi.gaussian_filter(alpha, .8)
    return save('heart-wreath', rgb, alpha)


# ---------- третий набор: конверт во весь экран, фоны, рамки с текстом-образцом ----------

ENV_FLAP = [(0, 0), (857, 0), (857, 134), (415, 775), (0, 155)]   # верхний клапан в кадре конверта


def poly_mask(shape, pts):
    from PIL import ImageDraw
    im = Image.new('L', (shape[1], shape[0]), 0)
    ImageDraw.Draw(im).polygon(pts, fill=255)
    return np.asarray(im) > 127


def envelope_full():
    """Конверт: корпус (под клапаном – внутренняя сторона) и верхний клапан отдельно,
    оба в одном кадре – на сайте клапан поворачивается на петле у верхнего края."""
    a = load_rgba('envelope2.png')[86:1614, 45:902]
    rgb, alpha = a[..., :3], a[..., 3] / 255
    H, W = alpha.shape
    flap = poly_mask((H, W), ENV_FLAP)
    px = rgb[(alpha > .99) & ~flap][::7]
    paper = np.median(px[px.mean(1) > np.percentile(px.mean(1), 70)], 0)   # сама бумага, без узора
    # внутренняя сторона: бумага чуть темнее, к верхнему краю – мягкая тень кармана
    yy = np.mgrid[:H, :W][0]
    inside = paper * np.array([.97, .96, .95]) * (1 - .1 * np.clip(1 - yy / (H * .5), 0, 1))[..., None]
    rng = np.random.default_rng(9)
    inside = inside + ndi.gaussian_filter(rng.normal(0, 2, (H, W)), .9)[..., None]
    cover = ndi.binary_dilation(flap, iterations=7)          # с запасом: тень клапана тоже уходит
    soft = ndi.gaussian_filter(cover.astype(float), 1.2)[..., None]
    body = rgb * (1 - soft) + inside * soft
    save('env-body', body, alpha, quality=86)
    fa = ndi.gaussian_filter(flap.astype(float), .8) * alpha
    save_full('env-flap', rgb, fa)
    s = load_rgba('seal2.png')[102:1141, 134:1124]
    rgb_s, a_s = shrink(s[..., :3], s[..., 3] / 255, 560)
    save('env-seal', rgb_s, a_s)
    print('paper', paper.round())


def save_full(name, rgb, alpha, quality=86):
    """Как save, но без обрезки по альфе – слой совпадает с кадром корпуса."""
    im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255, 0, 255)]).astype(np.uint8), 'RGBA')
    path = os.path.join(DST, name + '.webp')
    im.save(path, 'WEBP', quality=quality, method=6, alpha_quality=92)
    print(f'{name}.webp {im.size[0]}x{im.size[1]} {os.path.getsize(path) // 1024} KB')


def backgrounds():
    save('bg-sections', load('bg-sections.png'), quality=84)


def flowers_bottom():
    a = load_rgba('flowers-bottom.png')
    rgb, alpha = shrink(a[..., :3], a[..., 3] / 255, 1600)
    save('flowers-bottom', rgb, alpha)


def env_inside():
    """Подкладка конверта (внутренняя сторона и изнанка клапана): та же бумага, без узора."""
    a = load_rgba('envelope2.png')[86:1614, 45:902]
    rgb, alpha = a[..., :3], a[..., 3] / 255
    H, W = alpha.shape
    flap = poly_mask((H, W), ENV_FLAP)
    px = rgb[(alpha > .99) & ~flap][::7]
    paper = np.median(px[px.mean(1) > np.percentile(px.mean(1), 70)], 0)
    rng = np.random.default_rng(12)
    fibre = ndi.gaussian_filter(rng.normal(0, 1, (H, W)), (6, 1.2))          # продольные волокна бумаги
    fibre = fibre / fibre.std() * 2.2 + ndi.gaussian_filter(rng.normal(0, 1.4, (H, W)), .8)
    lining = paper * np.array([.97, .96, .94]) + fibre[..., None]
    save_full('env-inside', lining, np.ones((H, W)))


# ---------- четвёртый набор: обложка под 1920 × 1080 и новые рамки ----------

def min_cut(A, B, block):
    """Шов сверху вниз по полосе перекрытия там, где A и B похожи сильнее всего.
    Возвращает мягкую маску: 0 – берётся A (слева от шва), 1 – B (справа)."""
    e = ndi.gaussian_filter(((A - B) ** 2).sum(2), 2) + block * 1e9
    h, w = e.shape
    acc, step = e.copy(), np.zeros((h, w), int)
    for y in range(1, h):
        prev = np.stack([np.r_[np.inf, acc[y - 1, :-1]], acc[y - 1], np.r_[acc[y - 1, 1:], np.inf]])
        step[y] = prev.argmin(0) - 1
        acc[y] += prev.min(0)
    path = np.zeros(h, int)
    path[-1] = acc[-1].argmin()
    for y in range(h - 1, 0, -1):
        path[y - 1] = path[y] + step[y, path[y]]
    return ndi.gaussian_filter((np.arange(w)[None] >= path[:, None]).astype(float), 2.5)


def hero_wide(ph, bg, W, H):
    """Фон обложки для широких экранов: присланная сцена без сердца, продолженная вправо и влево.
    Фон без сердца (bg-hero.png – тот же кадр) повторён слева и справа; стыки идут по линии
    наименьшей разницы, поэтому шторы и цветы продолжаются без шва. Сердце – отдельный слой (hero_heart)."""
    Hs = round(H * 1250 / 1080)               # сцена чуть выше экрана: сердце крупнее, край пола уходит вниз
    Ws = round(Hs * ph.width / ph.height)
    p = np.asarray(ph.resize((Ws, Hs), Image.LANCZOS)).astype(float)
    b = np.asarray(bg.resize((Ws, Hs), Image.LANCZOS)).astype(float)
    heart = ndi.binary_fill_holes(ndi.binary_closing(np.abs(p - b).max(2) > 30, iterations=5))
    lab, n = ndi.label(heart)
    heart = lab == 1 + ndi.sum(heart, lab, range(1, n + 1)).argmax()
    keep = ndi.binary_dilation(heart, iterations=12)          # шов не проходит по сердцу
    x0, ov = (W - Ws) // 2, round(W * 20 / 2880)                # узкое перекрытие: у сердца – пышные букеты из двух колонн
    out = np.zeros((Hs, W, 3))
    out[:, x0:x0 + Ws] = b
    xs = np.arange(x0)                                        # левая копия: её правый край заходит на центр на ov
    c = xs - (x0 - Ws + ov)
    out[:, xs] = b[:, np.where(c < 0, -c - 1, c)]
    m = min_cut(b[:, Ws - ov:], b[:, :ov], keep[:, :ov])[..., None]
    out[:, x0:x0 + ov] = b[:, Ws - ov:] * (1 - m) + b[:, :ov] * m
    t0 = x0 + Ws - ov                                         # правая копия
    xs = np.arange(x0 + Ws, W)
    c = xs - t0
    out[:, xs] = b[:, np.where(c >= Ws, 2 * Ws - c - 1, c)]
    m = min_cut(b[:, Ws - ov:], b[:, :ov], keep[:, Ws - ov:])[..., None]
    out[:, t0:x0 + Ws] = b[:, Ws - ov:] * (1 - m) + b[:, :ov] * m
    y0 = round(H * 20 / 1080)
    print('  фото в широкой сцене: left %.3f%% top %.3f%% width %.3f%% height %.3f%%'
          % (100 * x0 / W, -100 * y0 / H, 100 * Ws / W, 100 * Hs / H))
    return Image.fromarray(np.clip(out[y0:y0 + H], 0, 255).astype(np.uint8))


def heart_mask(p, b):
    """Сердце на фото: всё, чем фото отличается от того же кадра без сердца (самый большой кусок, без дыр)."""
    heart = ndi.binary_fill_holes(ndi.binary_closing(np.abs(p - b).max(2) > 30, iterations=5))
    lab, n = ndi.label(heart)
    return lab == 1 + ndi.sum(heart, lab, range(1, n + 1)).argmax()


def hero():
    """Обложка слоями: фон без сердца (узкий кадр – hero-bg.jpg, широкие 1920 × 1080 и 2880 × 1620),
    сердце из присланного фото без надписей и надписи отдельно – на сайте сердце проявляется, имена пишутся.
    Поверх фона слои дают ровно присланное фото. Тёмная кайма скриншота в 1 px срезана."""
    ph = Image.open(os.path.join(SRC, 'hero.jpg')).convert('RGB')
    box = (1, 0, ph.width - 1, ph.height - 1)
    bg = Image.open(os.path.join(SRC, 'bg-hero.png')).convert('RGB').resize(ph.size, Image.LANCZOS).crop(box)
    ph = ph.crop(box)
    p, b = np.asarray(ph).astype(float), np.asarray(bg).astype(float)
    heart = heart_mask(p, b)
    hm = ndi.gaussian_filter(ndi.binary_dilation(heart, iterations=6).astype(float), 3)
    narrow = Image.fromarray(np.clip(p * (1 - hm[..., None]) + b * hm[..., None], 0, 255).astype(np.uint8))
    big = hero_wide(ph, bg, 2880, 1620)              # собирается один раз; 1920 × 1080 – уменьшенная копия
    for name, im in (('hero-bg', narrow), ('hero-wide-2880', big), ('hero-wide', big.resize((1920, 1080), Image.LANCZOS))):
        path = os.path.join(DST, name + '.jpg')
        im.save(path, quality=84, optimize=True, progressive=True)
        print(f'{name}.jpg {im.width}x{im.height} {os.path.getsize(path) // 1024} KB')
    hero_heart(p, heart, hm)


def hero_heart(p, heart, hm):
    """Сердце: бумага в середине очищена от имён и даты (гладкая заливка + зерно бумаги); имена в две строки
    и дата – отдельными картинками, цвет восстановлен так, что поверх очищенной бумаги получается фото.
    Печатает положение слоёв для style.css: сердце – в % кадра фото 1124 × 1999, надписи – в % сердца."""
    H, W = heart.shape
    lum = p.mean(2)
    ys, xs = np.where(heart)
    seed = (int(ys.mean()), int(xs.mean()))                  # середина сердца – чистая бумага
    m = ndi.uniform_filter(lum, 7)
    sd = np.sqrt(np.clip(ndi.uniform_filter(lum ** 2, 7) - m ** 2, 0, None))
    lab, _ = ndi.label(ndi.binary_opening((sd < 3) & (np.abs(p - p[seed]).max(2) < 14), iterations=2))
    paper = lab == lab[seed]
    field = ndi.binary_fill_holes(ndi.binary_closing(paper, iterations=40))
    field[:ys.min() + 230] = paper[:ys.min() + 230]          # у выемки сверху – только сама бумага
    near = np.stack([ndi.median_filter(p[..., c], size=31) for c in range(3)], -1)
    dark = near.mean(2) - lum > 10
    ink = dark & ndi.binary_erosion(field, iterations=6)
    for _ in range(10):                                      # кончики росчерков у самого края бумаги
        ink |= ndi.binary_dilation(ink) & dark & ndi.binary_erosion(field, iterations=1)
    hole = ndi.binary_dilation(ink, iterations=4)
    clean = np.where(hole[..., None], smooth_fill(p, paper & ~hole, 4), p)
    clean = grain_like(clean, hole, paper & ~hole)
    y0, y1 = np.where(hm.max(1) > .01)[0][[0, -1]]
    x0, x1 = np.where(hm.max(0) > .01)[0][[0, -1]]
    y1, x1 = y1 + 1, x1 + 1
    save_full('hero-heart', clean[y0:y1, x0:x1], hm[y0:y1, x0:x1], quality=88)
    print('  .hero__heart: left %.3f%% top %.3f%% width %.3f%%' % (100 * x0 / W, 100 * y0 / H, 100 * (x1 - x0) / W))
    # строки: «Фёдор &», «Ирина», дата – по середине каждого штриха
    lab, n = ndi.label(ndi.binary_dilation(ink, iterations=2))
    cy = np.array(ndi.center_of_mass(ink, lab, range(1, n + 1)))[:, 0]
    rows = np.where(ink.any(1))[0]
    date_top = rows[np.where(np.diff(rows) > 8)[0][-1] + 1]  # дата – отдельно, ниже пустой полосы
    d = np.linalg.norm(p - clean, axis=2)
    full = np.percentile(d[ndi.binary_erosion(ink, iterations=2)], 90)
    for name, sel in (('hero-name-1', cy < (ys.min() + 410)), ('hero-name-2', (cy >= ys.min() + 410) & (cy < date_top)),
                      ('hero-date', cy >= date_top)):
        part = np.isin(lab, 1 + np.where(sel)[0]) & ink
        area = ndi.binary_dilation(part, iterations=3)
        a = np.clip(d / full, 0, 1) * area
        a[a < .03] = 0
        col = clean + (p - clean) / np.maximum(a, 1e-3)[..., None]
        ly, lx = np.where(a > 0)
        ly0, ly1, lx0, lx1 = ly.min(), ly.max() + 1, lx.min(), lx.max() + 1
        save_full(name, col[ly0:ly1, lx0:lx1], a[ly0:ly1, lx0:lx1], quality=92)
        print('  %s: left %.3f%% top %.3f%% width %.3f%%' % (name, 100 * (lx0 - x0) / (x1 - x0), 100 * (ly0 - y0) / (y1 - y0),
                                                            100 * (lx1 - lx0) / (x1 - x0)))


def erase_text(rgb, alpha, seed_box, boxes):
    """Убирает надписи-образцы точечно: цветы и золото рядом остаются целыми.
    boxes – (y0, y1, x0, x1, mode): 'any' – всё, что отличается от бумаги (буквы, стрелки, ромбики),
    'ink' – только тонкие оливковые штрихи (у заголовка рядом листья и завитки)."""
    H, W = alpha.shape
    lum = rgb.mean(2)
    mean = ndi.uniform_filter(lum, 9)
    flat = np.sqrt(np.clip(ndi.uniform_filter(lum ** 2, 9) - mean ** 2, 0, None)) < 3
    y0, y1, x0, x1 = seed_box
    ref = np.median(rgb[y0:y1, x0:x1][flat[y0:y1, x0:x1]], 0)
    clean = flat & (np.linalg.norm(rgb - ref, axis=2) < 14) & (alpha > .9)
    yy, xx = np.mgrid[:H, :W]
    X, Y = xx / W, yy / H
    T = np.stack([np.ones_like(X), X, Y, X * X, Y * Y, X * Y], -1)
    paper = np.zeros_like(rgb)
    for c in range(3):
        coef, *_ = np.linalg.lstsq(T[clean][::3], rgb[..., c][clean][::3], rcond=None)
        paper[..., c] = T @ coef
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    olive = (lum < paper.mean(2) - 14) & (G - R > -14) & (G - B > 6) & (G - R < 18)
    wide = ndi.binary_opening(olive, iterations=6)            # широкие крупные пятна – листья, не буквы
    lab, n = ndi.label(wide)
    big = np.zeros(n + 1, bool)
    big[1:] = ndi.sum(wide, lab, range(1, n + 1)) > 900
    leaves = ndi.binary_dilation(big[lab], iterations=4)
    mask = np.zeros((H, W), bool)
    for by0, by1, bx0, bx1, mode in boxes:
        box = np.zeros((H, W), bool)
        box[by0:by1, bx0:bx1] = True
        mask |= box & ((np.abs(rgb - paper).max(2) > 10) if mode == 'any' else olive & ~leaves)
    mask = ndi.binary_dilation(mask, iterations=3)
    ys, xs = np.where(mask)
    cy0, cy1, cx0, cx1 = ys.min() - 4, ys.max() + 5, xs.min() - 4, xs.max() + 5
    sub = inpaint(rgb[cy0:cy1, cx0:cx1], mask[cy0:cy1, cx0:cx1], iters=900)
    out = rgb.copy()
    out[cy0:cy1, cx0:cx1] = sub
    rng = np.random.default_rng(5)                            # зерно бумаги на заплатках
    grain = ndi.gaussian_filter(rng.normal(0, 1.6, (H, W)), .8)[..., None]
    soft = ndi.gaussian_filter(mask.astype(float), 1)[..., None]
    return out + grain * soft


def frame_program():
    """Рамка «Программа» (присланная картинка с текстом): поле очищается, текст – на сайте.
    Кадр не обрезается: проценты поля в style.css – от исходного кадра 1024 × 1536."""
    a = load_rgba('frame-program.webp')
    rgb, alpha = a[..., :3], np.clip(a[..., 3] / 252, 0, 1)   # альфа присланных webp – не выше 254
    boxes = [(420, 625, 255, 830, 'ink'),                     # «Программа» с росчерком – у лилий
             (630, 1240, 360, 640, 'any'),                    # время, подписи, стрелки с ромбиками
             (1240, 1285, 360, 690, 'any')]                   # «Завершение вечера»
    clean = erase_text(rgb, alpha, (300, 360, 560, 760), boxes)
    save_full('frame-program', clean, alpha)
    ornament('orn-star', rgb, clean, (742, 807, 503, 534))     # стрелка со звёздочкой между пунктами


def ornament(name, rgb, clean, box, clear=None):
    """Золотой орнамент с макета отдельной картинкой: прозрачность – по отличию от очищенной бумаги,
    цвет восстановлен так, что поверх той же бумаги получается исходный пиксель."""
    y0, y1, x0, x1 = box
    o, c = rgb[y0:y1, x0:x1], clean[y0:y1, x0:x1]
    R, G, B = o[..., 0], o[..., 1], o[..., 2]
    gold = ndi.binary_dilation((R - B > 30) & (R > G + 4), iterations=2)     # без оливковых букв рядом
    a = np.clip(np.linalg.norm(o - c, axis=2) / 60, 0, 1) * gold
    a[a < .04] = 0
    if clear:                                                 # участок с чужим штрихом (хвост буквы заголовка)
        a[clear[0] - y0:clear[1] - y0, clear[2] - x0:clear[3] - x0] = 0
    lab, n = ndi.label(a > 0)                                 # только сам орнамент и то, что касается его
    main = lab == 1 + ndi.sum(a > 0, lab, range(1, n + 1)).argmax()
    a *= np.isin(lab, np.unique(lab[ndi.binary_dilation(main, iterations=3)]))
    col = c + (o - c) / np.maximum(a, 1e-3)[..., None]
    save(name, col, a, quality=92)


# ---------- пятый набор: присланные рамки без текста (текст – на сайте), орнаменты – с образцов ----------
# frame-1.webp – слои SVG «Рамка 1», сведённые без изменений; frame-dress-pearl.webp и frame-place-pearl.webp –
# присланные жемчужные рамки «Дресс-код» и «Адрес» (фон уже прозрачный) – берутся как есть;
# sample-*.jpg / sample-place.webp – образцы из архива «образец страниц сайта» (с них – лилия и линии «Адреса»).
# На сайте «Рамка 1» тянется по высоте под текст: растягивается полоса с ровными планками (строки 1020–1110).

def smooth_fill(rgb, known, sigma):
    """Плавная заливка по известным пикселям (взвешенное гауссово среднее);
    где известных рядом нет – тот же расчёт шире."""
    out = np.zeros_like(rgb)
    todo = np.ones(known.shape, bool)
    for s in (sigma, sigma * 4, sigma * 16):
        w = ndi.gaussian_filter(known.astype(float), s)
        est = np.stack([ndi.gaussian_filter(rgb[..., c] * known, s) for c in range(3)], -1) / np.maximum(w, 1e-9)[..., None]
        ok = todo & (w > .02)
        out[ok] = est[ok]
        todo &= ~ok
    out[todo] = np.median(rgb[known], 0)
    return out


def paper_tone(img, region, k=4, size=9, tol=8):
    """Тон бумаги без надписей: медиана по уменьшенной картинке, затем заливка по чистым пикселям."""
    H, W = region.shape
    small = np.asarray(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((W // k, H // k), Image.BOX))
    med = np.stack([ndi.median_filter(small[..., c].astype(float), size=size) for c in range(3)], -1)
    med = np.asarray(Image.fromarray(med.astype(np.uint8)).resize((W, H), Image.BILINEAR)).astype(float)
    paper = np.median(med[region], 0)
    known = region & (np.abs(img - med).max(2) < tol) & (np.abs(med - paper).max(2) < 30)
    return smooth_fill(img, known, 6)


def cut_black(rgb, band=1, min_hole=6):
    """Фон – чёрный: прозрачный, вместе с закрытыми просветами и тёмной каймой у края;
    край силуэта – доля яркости от ближайшего пикселя изнутри (сглаживание без чёрного ореола).
    band > 1 – ещё и тусклое серое свечение на band пикселей от края (у мелких белых цветов) становится
    полупрозрачным, а не серым; золото, листья и яркие цветы при этом не трогаются."""
    mx = rgb.max(2)
    dark = mx <= 10
    lab, n = ndi.label(dark)
    keep = np.zeros(n + 1, bool)
    keep[1:] = ndi.sum(dark, lab, range(1, n + 1)) >= min_hole    # min_hole 1 – и мелкие просветы кружевной сетки
    bg = keep[lab]
    glow = (mx - rgb.min(2) < 18) & (rgb.mean(2) < 150) if band > 1 else np.ones(mx.shape, bool)
    for _ in range(3):
        bg |= ndi.binary_dilation(bg) & (mx < 45) & glow
    fg = ndi.binary_opening(~bg, iterations=1)                 # без одиночных крошек
    return edge_alpha(rgb, fg, lambda P, F: P.sum(2) / np.maximum(F.sum(2), 1), .4, band, glow)


def edge_alpha(rgb, fg, share, blur, band=1, soft=None):
    core = ndi.binary_erosion(fg, iterations=1)
    if band > 1:                                               # широкий край – только у пикселей soft
        core &= ndi.binary_erosion(fg, iterations=band) | ~soft
    _, (iy, ix) = ndi.distance_transform_edt(~core, return_indices=True)
    F = rgb[iy, ix]
    alpha = np.where(core, 1.0, np.where(fg, np.clip(share(rgb, F), 0, 1), 0.0))
    col = np.where(core[..., None], rgb, F)
    return col, ndi.gaussian_filter(alpha, blur) if blur else alpha


def frame_invite():
    """«Рамка 1» как есть, чёрный фон вокруг – прозрачный. С поля убраны разделитель, линии у года
    и сердце с линиями (календарь на сайте живой): звёздочка и сердце – отдельными картинками."""
    rgb, alpha = cut_black(load('frame-1.webp'))
    boxes = [(935, 980, 395, 645, 'any'),                     # линия со звёздочкой
             (1086, 1106, 312, 738, 'any'),                   # линии у «2027»
             (1292, 1378, 265, 740, 'any')]                   # сердце у «21» с линиями
    clean = erase_text(rgb, alpha, (800, 860, 300, 700), boxes)
    save('frame-invite', clean, alpha, quality=88)
    ornament('orn-sparkle', rgb, clean, (935, 980, 500, 538))
    ornament('orn-heart', rgb, clean, (1292, 1378, 388, 492))


def as_sent(name, src):
    """Присланная рамка как есть: пиксели не меняются, только альфа доведена до 255 (у присланных webp она
    бывает не выше 254) и пустые прозрачные поля вокруг обрезаны по силуэту. Проценты поля в style.css –
    от обрезанного кадра."""
    a = load_rgba(src)
    return save(name, a[..., :3], np.clip(a[..., 3] / 252, 0, 1), quality=95)


def frame_dress():
    """Рамка «Дресс-код» – присланная жемчужная frame-dress-pearl.webp как есть (на сайте не растягивается).
    Лилия для разделителя под дресс-кодом – с образца, бумага образца приведена к тону поля рамки."""
    im = as_sent('frame-dress', 'frame-dress-pearl.webp')
    tone = np.median(np.asarray(im.convert('RGB'))[500:1000, 250:600].reshape(-1, 3), 0)
    y0, y1, x0, x1 = 812, 930, 650, 798
    s = load('sample-dress.jpg')[y0:y1, x0:x1]
    paper = np.median(s.reshape(-1, 3), 0)
    s = s * tone / paper                                       # бумага образца → тон бумаги рамки
    corner = np.zeros(s.shape[:2], bool)
    corner[:858 - y0, :688 - x0] = True                        # слева сверху – конец строки «просим»: стереть
    s[ndi.binary_dilation(corner & (s.mean(2) < 200), iterations=2) & corner] = np.median(s.reshape(-1, 3), 0)
    m = np.abs(s - np.median(s.reshape(-1, 3), 0)).max(2) > 10   # всё, что не бумага
    m = ndi.binary_fill_holes(ndi.binary_closing(m, iterations=3))
    lab, n = ndi.label(m)
    m = lab == 1 + ndi.sum(m, lab, range(1, n + 1)).argmax()   # сама лилия с листьями
    a = ndi.gaussian_filter(ndi.binary_dilation(m, iterations=1).astype(float), 1)
    save('orn-lily', s, a, quality=90)


def frame_place():
    """«Адрес» – присланная жемчужная овальная рамка frame-place-pearl.webp как есть.
    Линии с лилией и подвеска под «Открыть на карте» – с образца."""
    as_sent('frame-place', 'frame-place-pearl.webp')
    s = load_rgba('sample-place.webp')[..., :3]
    yy, xx = np.mgrid[:1536, :1024]
    clean = paper_tone(s, ((xx - 513) / 330) ** 2 + ((yy - 765) / 460) ** 2 < 1)
    ornament('orn-rule', s, clean, (560, 622, 262, 766), clear=(560, 583, 262, 480))   # без хвоста «А»
    ornament('orn-rule-short', s, clean, (766, 827, 386, 643))
    ornament('orn-pendant', s, clean, (1095, 1129, 474, 554))   # подвеска под «Открыть на карте» (линия – на сайте)


ALL = {f.__name__: f for f in (heart_wreath, envelope_full, backgrounds, flowers_bottom, env_inside, hero,
                               frame_program, frame_invite, frame_dress, frame_place)}
if __name__ == '__main__':
    for n in sys.argv[1:] or ALL:
        ALL[n.replace('-', '_')]()
