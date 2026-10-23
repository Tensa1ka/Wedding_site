"""Вырезает элементы оформления из присланных листов (tools/src) в assets/img.
Фон листов – нарисованная «шахматка» вместо прозрачности: светлые нейтральные клетки,
связанные с краем кадра, становятся прозрачными. Текст-образец в полях рамок «Адрес» и «Программа»
закрашивается по окружающему фону. Обложка (assets/img/hero.jpg) и карточки «Дорогие родные и близкие»
и «Дресс-код · Фото · Анкета» (card-*.webp) вставлены как прислали – этот скрипт их не трогает.
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


def clear_field(rgb, alpha, seed_box, flat_tol=3.0, cream_tol=20, erode=7, extra=()):
    """Очищает внутреннее поле рамки от текста-образца: гладкая заливка по чистым пикселям поля."""
    H, W = alpha.shape
    lum = rgb.mean(2)
    mean = ndi.uniform_filter(lum, 9)
    flat = np.sqrt(np.clip(ndi.uniform_filter(lum ** 2, 9) - mean ** 2, 0, None)) < flat_tol
    y0, y1, x0, x1 = seed_box
    ref = np.median(rgb[y0:y1, x0:x1][flat[y0:y1, x0:x1]], 0)
    cream = flat & (np.linalg.norm(rgb - ref, axis=2) < cream_tol) & (alpha > .9)
    lab, _ = ndi.label(ndi.binary_opening(cream, iterations=2))
    seed = np.zeros_like(cream)
    seed[y0:y1, x0:x1] = True
    field = np.isin(lab, np.unique(lab[seed & (lab > 0)]))
    field = ndi.binary_fill_holes(ndi.binary_closing(field, iterations=8))
    inner = ndi.binary_erosion(field, iterations=erode)
    clean = inner & cream
    yy, xx = np.mgrid[:H, :W]
    X, Y = xx / W, yy / H
    T = np.stack([np.ones_like(X), X, Y, X * X, Y * Y, X * Y], -1)
    fill = np.zeros_like(rgb)
    for c in range(3):
        coef, *_ = np.linalg.lstsq(T[clean][::3], rgb[..., c][clean][::3], rcond=None)
        fill[..., c] = T @ coef
    rng = np.random.default_rng(4)
    fill += ndi.gaussian_filter(rng.normal(0, 1.6, (H, W)), .8)[..., None]
    # остатки надписей у края поля (заголовок под цветами, кнопка): оливковые штрихи в пределах поля
    ys, xs = np.where(field)
    box = (yy >= ys.min() - H * .07) & (yy <= ys.max()) & (xx >= xs.min()) & (xx <= xs.max())
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    ink = box & (lum < fill.mean(2) - 22) & (G - R > -14) & (G - B > 6) & (G - R < 18)   # без золота и листьев
    ink = ndi.binary_dilation(ndi.binary_opening(ink, iterations=1), iterations=4)
    for y0e, y1e, x0e, x1e in extra:                          # явные участки (контур нарисованной кнопки)
        ink[y0e:y1e, x0e:x1e] = True
    soft = np.maximum(ndi.gaussian_filter(inner.astype(float), 2), ndi.gaussian_filter(ink.astype(float), 1.5))[..., None]
    out = rgb * (1 - soft) + fill * soft
    ys, xs = np.where(inner)
    print('  field x %.3f-%.3f y %.3f-%.3f' % (xs.min() / W, xs.max() / W, ys.min() / H, ys.max() / H))
    return out


def frames_new():
    for name, box in [('frame-place', (800, 1000, 340, 680)), ('frame-program', (850, 1100, 330, 600))]:
        a = load_rgba(name + '.png')
        rgb, alpha = a[..., :3], a[..., 3] / 255
        print(name, alpha.shape)
        save_full(name, clear_field(rgb, alpha, box), alpha)   # без обрезки: проценты поля – от исходного кадра


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


ALL = {f.__name__: f for f in (heart_wreath, envelope_full, backgrounds, frames_new, flowers_bottom, env_inside)}
if __name__ == '__main__':
    for n in sys.argv[1:] or ALL:
        ALL[n.replace('-', '_')]()
