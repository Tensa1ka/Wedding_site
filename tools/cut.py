"""Готовит присланные картинки (tools/src) для сайта (assets/img).
Фон листов – нарисованная «шахматка» вместо прозрачности: клетки, связанные с краем кадра, становятся прозрачными.
Текст-образец в поле рамки «Программа» убирается (текст – на сайте), золотые стрелки с макета сохраняются
отдельной картинкой. Обложка: присланное фото и его широкая версия 1920 × 1080 (и 2880 × 1620),
продолженная вправо и влево тем же фоном. Карточки «Дорогие родные и близкие», «Адрес» и «Дресс-код · Фото · Анкета» –
присланные рамки без изменений (убран только фон вокруг, «Адрес» приведён к кадру образца), текст – с присланных образцов.
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
    """Обложка для широких экранов: присланная сцена, продолженная вправо и влево.
    Фон без сердца (bg-hero.png – тот же кадр) повторён слева и справа; стыки идут по линии
    наименьшей разницы, поэтому шторы и цветы продолжаются без шва. Сердце – пиксели фото."""
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
    hm = ndi.gaussian_filter(ndi.binary_dilation(heart, iterations=6).astype(float), 3)[..., None]
    out[:, x0:x0 + Ws] = out[:, x0:x0 + Ws] * (1 - hm) + p * hm
    y0 = round(H * 20 / 1080)
    return Image.fromarray(np.clip(out[y0:y0 + H], 0, 255).astype(np.uint8))


def hero():
    """Обложка: присланное фото (без тёмной каймы скриншота в 1 px) и широкие версии 1920 × 1080 и 2880 × 1620."""
    ph = Image.open(os.path.join(SRC, 'hero.jpg')).convert('RGB')
    box = (1, 0, ph.width - 1, ph.height - 1)
    bg = Image.open(os.path.join(SRC, 'bg-hero.png')).convert('RGB').resize(ph.size, Image.LANCZOS).crop(box)
    ph = ph.crop(box)
    path = os.path.join(DST, 'hero.jpg')
    ph.save(path, quality=86, optimize=True, progressive=True)
    print(f'hero.jpg {ph.width}x{ph.height} {os.path.getsize(path) // 1024} KB')
    big = hero_wide(ph, bg, 2880, 1620)              # собирается один раз; 1920 × 1080 – уменьшенная копия
    for name, im in (('hero-wide-2880', big), ('hero-wide', big.resize((1920, 1080), Image.LANCZOS))):
        path = os.path.join(DST, name + '.jpg')
        im.save(path, quality=84, optimize=True, progressive=True)
        print(f'{name}.jpg {im.width}x{im.height} {os.path.getsize(path) // 1024} KB')


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


# ---------- пятый набор: присланные рамки как есть, текст – с присланных образцов ----------
# frame-1.webp, frame-2.webp – слои SVG «Рамка 1» и «Рамка 2», сведённые без изменений;
# frame-pearl.webp – «Оригинальная жемчужно-золотая рамка» из Figma;
# sample-*.jpg / sample-place.webp – образцы из архива «образец страниц сайта».

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
    paper = np.median(med[region], 0)                          # крупные тёмные пятна (кнопка) – не бумага
    known = region & (np.abs(img - med).max(2) < tol) & (np.abs(med - paper).max(2) < 30)
    return smooth_fill(img, known, 6)


def paper_field(rgb, alpha, seed, tol=16):
    """Поле-бумага рамки: гладкие кремовые пиксели, связанные с точкой seed (y, x); надписи внутри – залиты."""
    lum = rgb.mean(2)
    m = ndi.uniform_filter(lum, 7)
    sd = np.sqrt(np.clip(ndi.uniform_filter(lum ** 2, 7) - m ** 2, 0, None))
    cream = (sd < 4) & (np.abs(rgb - rgb[seed]).max(2) < tol) & (alpha > .97)
    lab, _ = ndi.label(ndi.binary_opening(cream, iterations=2))
    field = lab == lab[seed]
    return field, ndi.binary_fill_holes(ndi.binary_closing(field, iterations=10))


def transfer_text(frame, sample, zone, same_frame, thr=10):
    """Текст образца на присланную рамку: в пределах zone – пиксели образца, приведённые к тону бумаги рамки.
    same_frame – в образце та же рамка: переносится всё, чем он от неё отличается (текст, кнопка, стёртые линии);
    иначе – всё, что отличается от бумаги образца."""
    s_bg = paper_tone(sample, zone)
    f_bg = paper_tone(frame, zone)
    adj = sample * (f_bg / np.maximum(s_bg, 1))
    diff = np.abs(adj - frame).max(2) if same_frame else np.abs(sample - s_bg).max(2)
    ink = (ndi.binary_opening(diff > thr, iterations=1) | (diff > 2.5 * thr)) & zone
    soft = ndi.gaussian_filter((ndi.binary_dilation(ink, iterations=2) & zone).astype(float), 1)[..., None]
    return frame * (1 - soft) + adj * soft


def cut_black(rgb):
    """Фон – чёрный: прозрачный, вместе с закрытыми просветами и тёмной каймой у края;
    край силуэта – доля яркости от ближайшего пикселя изнутри (сглаживание без чёрного ореола)."""
    mx = rgb.max(2)
    dark = mx <= 10
    lab, n = ndi.label(dark)
    keep = np.zeros(n + 1, bool)
    keep[1:] = ndi.sum(dark, lab, range(1, n + 1)) >= 6
    bg = keep[lab]
    for _ in range(3):
        bg |= ndi.binary_dilation(bg) & (mx < 45)
    fg = ndi.binary_opening(~bg, iterations=1)                 # без одиночных крошек
    return edge_alpha(rgb, fg, lambda P, F: P.sum(2) / np.maximum(F.sum(2), 1), .4)


def cut_white(rgb, white=254.):
    """Фон – белый вокруг рамки: прозрачный; край – доля отличия от белого у ближайшего пикселя изнутри."""
    cand = (rgb.mean(2) >= 240) & (rgb.max(2) - rgb.min(2) <= 6)
    lab, n = ndi.label(cand)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    fg = ~np.isin(lab, edge[edge > 0])
    return edge_alpha(rgb, fg, lambda P, F: (white - P).sum(2) / np.maximum((white - F).sum(2), 1), 0)


def edge_alpha(rgb, fg, share, blur):
    core = ndi.binary_erosion(fg, iterations=1)
    _, (iy, ix) = ndi.distance_transform_edt(~core, return_indices=True)
    F = rgb[iy, ix]
    alpha = np.where(core, 1.0, np.where(fg, np.clip(share(rgb, F), 0, 1), 0.0))
    col = np.where(core[..., None], rgb, F)
    return col, ndi.gaussian_filter(alpha, blur) if blur else alpha


def resize_rgba(rgb, alpha, size):
    im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha * 255]).round().astype(np.uint8), 'RGBA')
    a = np.asarray(im.convert('RGBa').resize(size, Image.LANCZOS).convert('RGBA')).astype(float)
    return a[..., :3], a[..., 3] / 255


def card_invite():
    """«Дорогие родные и близкие» с календарём: «Рамка 1» (чёрный фон – прозрачный), текст – с образца."""
    rgb, alpha = cut_black(load('frame-1.webp'))
    _, field = paper_field(rgb, alpha, (900, 512))
    zone = ndi.binary_dilation(field, iterations=14) & (alpha > .95)
    save('card-invite', transfer_text(rgb, load('sample-invite.jpg'), zone, True), alpha, quality=88)


def card_dress():
    """«Дресс-код · Фото · Анкета»: «Рамка 2» и текст, поле, кружки и кнопка – с образца.
    Координаты поля, кружков и кнопки в style.css – в кадре этой картинки (869 × 1775)."""
    a = load_rgba('frame-2.webp')
    rgb, alpha = a[..., :3], np.clip(a[..., 3] / 252, 0, 1)
    _, field = paper_field(rgb, alpha, (1000, 450))
    zone = ndi.binary_dilation(field, iterations=14) & (alpha > .95)   # с запасом: кнопка заходит на орнамент
    save('card-dress', transfer_text(rgb, load('sample-dress.jpg'), zone, True), alpha, quality=88)


def card_place():
    """«Адрес»: оригинальная жемчужная рамка (белый фон – прозрачный), приведённая к кадру образца 1024 × 1536;
    текст с образца – в овале. Ссылка «Открыть на карте» в style.css – в процентах этого кадра."""
    rgb, alpha = resize_rgba(*cut_white(load('frame-pearl.webp')), (1024, 1536))
    s = load_rgba('sample-place.webp')[..., :3]
    yy, xx = np.mgrid[:1536, :1024]
    zone = (((xx - 513) / 330) ** 2 + ((yy - 765) / 460) ** 2 < 1) & (yy > 350) & (yy < 1135)   # текст – без рамки образца
    save('card-place', transfer_text(rgb, s, zone, False), alpha, quality=88)


ALL = {f.__name__: f for f in (heart_wreath, envelope_full, backgrounds, flowers_bottom, env_inside, hero,
                               frame_program, card_invite, card_dress, card_place)}
if __name__ == '__main__':
    for n in sys.argv[1:] or ALL:
        ALL[n.replace('-', '_')]()
