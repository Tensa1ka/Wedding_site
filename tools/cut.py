"""Готовит присланные картинки (tools/src) для сайта (assets/img).
Фон листов – нарисованная «шахматка» вместо прозрачности: клетки, связанные с краем кадра, становятся прозрачными.
Рамки «Приглашение», «Адрес», «Программа», «Дресс-код» – без текста (текст – на сайте), золотые орнаменты
с рамок и образцов – отдельными картинками. Обложка: присланное фото и его широкая версия 1920 × 1080 (и 2880 × 1620),
продолженная вправо и влево тем же фоном. Новые рамки – как прислали: убран только фон вокруг, «Адрес» приведён к кадру образца.
Открытие конверта – присланная Lottie-анимация: картинки из неё и сама анимация – в assets/envelope;
клапан и карман открытого конверта – заново с присланного конверта (envelope2.png), как на образцах открытого конверта.
Запуск: python3 tools/cut.py [имя ...]  (нужны numpy, scipy, Pillow)"""
import base64
import io
import json
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


# ---------- третий набор: открытие конверта, фоны, рамки с текстом-образцом ----------

ENV_DST = os.path.join(HERE, '..', 'assets', 'envelope')
ENV_OFF = (45, 86)   # кадр конверта анимации (857 × 1528) в envelope2.png
# края клапанов на envelope2.png – прямые x = a·y + b, найдены по перепаду яркости
ENV_TOP = ((0.6763, -127.50), (-0.6916, 1078.02))    # верхний клапан: левый и правый край
ENV_BOT = ((-0.7981, 1117.51), (0.7779, -154.20))    # нижний клапан; его вершина спрятана под верхним
ENV_ROUND = 11.4                                     # скругление кончиков клапанов


def env_line(a, b):
    """Прямая с envelope2.png – в кадр анимации."""
    return a, a * ENV_OFF[1] + b - ENV_OFF[0]


def wedge_sdf(x, y, l1, l2, sides, r=0.0):
    """Расстояние до угла между двумя прямыми (снаружи > 0, внутри < 0), кончик скруглён радиусом r.
    sides – с какой стороны от каждой прямой угол: +1 справа (x больше), −1 слева."""
    hs, ns = [], []
    for (a, b), sd in zip((l1, l2), sides):
        k = np.hypot(1, a)
        hs.append(sd * (x - a * y - b) / k - r)
        ns.append(np.array([sd / k, -sd * a / k]))
    h1, h2 = hs
    (a1, b1), (a2, b2) = l1, l2
    # угол «внутренних» прямых (сдвинутых внутрь на r)
    c1 = b1 + sides[0] * r * np.hypot(1, a1)
    c2 = b2 + sides[1] * r * np.hypot(1, a2)
    cy = (c2 - c1) / (a1 - a2)
    cx = a1 * cy + c1
    dot = ns[0] @ ns[1]
    big = np.full_like(x, np.inf)
    d1 = np.where((h1 < 0) & (h2 - h1 * dot >= 0), -h1, big)
    d2 = np.where((h2 < 0) & (h1 - h2 * dot >= 0), -h2, big)
    out = np.minimum(np.minimum(d1, d2), np.hypot(x - cx, y - cy))
    inside = (h1 >= 0) & (h2 >= 0)
    return np.where(inside, -np.minimum(h1, h2), out) - r


def env_save(name, rgb, alpha):
    im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255, 0, 255)]).astype(np.uint8), 'RGBA')
    path = os.path.join(ENV_DST, name)
    im.save(path, 'WEBP', quality=90, method=6, alpha_quality=100)
    pv = Image.new('RGBA', im.size, (35, 39, 11, 255))
    pv.alpha_composite(im)
    pv.convert('RGB').save(os.path.join(PREVIEW, '_env_' + name.replace('.webp', '.png')))
    print(f'envelope/{name} {im.size[0]}x{im.size[1]} {os.path.getsize(path) // 1024} KB')
    return im.size


def env_pocket():
    """Карман открытого конверта из envelope2.png, как на присланных образцах открытого конверта:
    вырез образуют боковые клапаны (их края идут по краям верхнего клапана), между ними – скруглённая
    вершина нижнего клапана (у закрытого конверта она под верхним клапаном – дорисована из его же краёв).
    Тень закрытого клапана снята с кармана в отдельный слой – он гаснет, когда клапан поднимается."""
    a = load_rgba('envelope2.png')[ENV_OFF[1]:ENV_OFF[1] + 1528, ENV_OFF[0]:ENV_OFF[0] + 857]
    rgb, alpha = a[..., :3], a[..., 3] / 255
    H, W = alpha.shape
    y, x = np.mgrid[:H, :W].astype(float)
    tl, tr = (env_line(*l) for l in ENV_TOP)
    bl, br = (env_line(*l) for l in ENV_BOT)
    flap_d = wedge_sdf(x, y, tl, tr, (1, -1), ENV_ROUND)      # верхний клапан (кончик скруглён)
    vee_d = wedge_sdf(x, y, tl, tr, (1, -1))                  # вырез без скругления – края боковых клапанов
    bot_d = wedge_sdf(x, y, bl, br, (1, -1), ENV_ROUND)       # нижний клапан
    side = np.clip(.5 + vee_d + .7, 0, 1)                     # на 0,7 px под клапан – без щели у закрытого
    bottom = np.clip(.5 - bot_d, 0, 1)
    pocket = np.maximum(side, bottom) * alpha
    hidden = (bot_d < .5) & (flap_d < 24)       # вершина нижнего клапана под верхним и в его тени

    # пиксели под самым краем клапана – ближайшими снаружи
    ok = flap_d >= 1.5
    idx = ndi.distance_transform_edt(~ok, return_distances=False, return_indices=True)
    orig = rgb[idx[0], idx[1]]

    # тень клапана: во сколько раз темнее на расстоянии d от края, чем вдали. Свет справа сверху – слева
    # тень вдвое шире; профили левого и правого края (медианы по всей полосе), у кончика – по направлению к краю
    d = np.clip(flap_d, 0, None)
    band = (pocket > .99) & ~hidden & (alpha > .99) & (vee_d > 1) & (d > 0)
    profs, ends = [], []
    for m in (band & (x < 380), band & (x > 470)):
        ref = np.median(orig[m & (d >= 150) & (d < 180)], 0)
        prof = np.ones((181, 3))
        ks = [k for k in range(150) if (m & (d >= k) & (d < k + 1)).sum() >= 20]
        for c in range(3):
            prof[:150, c] = np.interp(np.arange(150), ks, [np.median(orig[m & (d >= k) & (d < k + 1), c]) / ref[c] for k in ks])
        prof = ndi.gaussian_filter1d(np.clip(prof, 0, 1), 1.5, axis=0)
        end = next(k for k in range(10, 150) if prof[k:k + 4].min() > .985)
        prof[end:] = 1
        profs.append(np.clip(np.maximum.accumulate(prof, 0), .2, 1))
        ends.append(end)
    print('тень клапана: слева до', ends[0], 'px, справа до', ends[1], 'px, у края', profs[0][1].round(2), profs[1][1].round(2))
    gy, gx = np.gradient(flap_d)
    ang = np.arctan2(gy, gx)                                   # направление от края клапана наружу
    nl, nr = np.arctan2(tl[0], -1), np.arctan2(-tr[0], 1)      # наружные нормали левого и правого края
    wr = np.clip((np.arctan2(np.sin(ang - nl), np.cos(ang - nl))) / np.arctan2(np.sin(nr - nl), np.cos(nr - nl)), 0, 1)
    s = np.stack([np.interp(d, np.arange(181), profs[0][:, c]) * (1 - wr)
                  + np.interp(d, np.arange(181), profs[1][:, c]) * wr for c in range(3)], -1)
    end = max(ends)
    clean = orig / s

    # вершина нижнего клапана: переносом вдоль его краёв из видимой части (кромка сохраняется);
    # левая половина – вдоль левого края, правая – вдоль правого, по оси – плавный переход
    apex_x = bl[0] * (br[1] - bl[1]) / (bl[0] - br[0]) + bl[1]
    acc, wsum = np.zeros_like(clean), np.zeros(hidden.shape)
    for (la, _), w in ((bl, np.clip((apex_x + 2 - x) / 4, 0, 1)), (br, np.clip((x - apex_x + 2) / 4, 0, 1))):
        dx, dy = la / np.hypot(1, la), 1 / np.hypot(1, la)
        todo = hidden & (w > 0)
        for t in range(60, 400, 4):
            if not todo.any():
                break
            sx, sy = x[todo] + dx * t, y[todo] + dy * t
            ok_src = ndi.map_coordinates(flap_d, [sy, sx], order=1) >= 70   # за тенью клапана
            ii, jj = np.nonzero(todo)
            ii, jj, sx, sy = ii[ok_src], jj[ok_src], sx[ok_src], sy[ok_src]
            for c in range(3):
                acc[ii, jj, c] += w[ii, jj] * ndi.map_coordinates(clean[..., c], [sy, sx], order=1)
            wsum[ii, jj] += w[ii, jj]
            todo[ii, jj] = False
    filled = wsum > 0
    wf = np.clip((24 - flap_d[filled]) / 8, 0, 1)[:, None]     # к видимой части – плавно
    clean[filled] = clean[filled] * (1 - wf) + acc[filled] / wsum[filled][:, None] * wf

    # сгиб по краю боковых клапанов: тонкая складка и лёгкий блик, как на образце
    e = np.where(bottom < .5, vee_d + .7, 99)
    crease = 1 - .09 * np.exp(-((e - .4) / .8) ** 2) + .045 * np.exp(-((e - 2.6) / 1.3) ** 2)
    clean = clean * crease[..., None]

    shadow_w = np.clip((end - d) / 12, 0, 1)
    return rgb, alpha, flap_d, clean, pocket, orig, shadow_w


def envelope():
    """Открытие конверта – присланная Lottie-анимация (envelope-opening.json): картинки из неё – отдельными
    файлами .webp в assets/envelope, сама анимация без картинок – assets/envelope/envelope.js
    (подключается обычным <script>, поэтому сайт работает и при открытии index.html с диска).
    Конверт – с присланного конверта (envelope2.png): клапан по его настоящему краю, карман открытого
    конверта – боковые клапаны и вершина нижнего клапана (env_pocket), без полосы и тени по старому вырезу."""
    with open(os.path.join(SRC, 'envelope-opening.json'), encoding='utf-8') as f:
        anim = json.load(f)
    os.makedirs(ENV_DST, exist_ok=True)
    for a in anim['assets']:
        if not a.get('p', '').startswith('data:'):
            continue
        im = Image.open(io.BytesIO(base64.b64decode(a['p'].split(',', 1)[1])))
        name = a['id'] + '.webp'
        path = os.path.join(ENV_DST, name)
        im.save(path, 'WEBP', quality=90, method=6, alpha_quality=100)
        a.update(u='', p=name, e=0)
        print(f'envelope/{name} {im.size[0]}x{im.size[1]} {os.path.getsize(path) // 1024} KB')

    rgb, alpha, flap_d, clean, pocket, orig, shadow_w = env_pocket()
    assets = {a['id']: a for a in anim['assets']}
    layers = {l['ind']: l for l in anim['layers']}

    def put(aid, name, rgb_, alpha_):
        w, h = env_save(name, rgb_, alpha_)
        assets.setdefault(aid, {'id': aid})
        assets[aid].update(w=w, h=h, u='', p=name, e=0)
        if assets[aid] not in anim['assets']:
            anim['assets'].append(assets[aid])

    # клапан – по настоящему краю (в анимации маска шла на 5–7 px внутри края) и его затенение
    fh = np.nonzero((flap_d < 1).any(1))[0].max() + 2
    fa = np.clip(.5 - flap_d[:fh], 0, 1) * alpha[:fh]
    put('img_2', 'img_2.webp', rgb[:fh], fa)
    shade = np.asarray(Image.open(os.path.join(ENV_DST, 'img_1.webp')).convert('RGBA')).astype(float)
    k = np.polyfit(np.arange(80, 720), shade[80:720, 428, 3], 1)     # затенение – градиент сверху вниз
    put('img_1', 'img_1.webp', np.broadcast_to(shade[shade[..., 3] > 5][:, :3].mean(0), (fh, 857, 3)),
        fa * np.clip(np.polyval(k, np.arange(fh)) / 255, 0, 1)[:, None])
    for i in (2, 3):
        layers[i].pop('masksProperties', None)
        layers[i]['hasMask'] = False

    # карман и тень закрытого клапана на нём (исходные пиксели с тенью поверх кармана без неё)
    put('img_12', 'img_12.webp', clean, pocket)
    put('img_13', 'img_13.webp', orig, pocket * shadow_w)
    layers[4].update(refId='img_12', hasMask=False)
    layers[4].pop('masksProperties', None)
    cast = json.loads(json.dumps(layers[4]))
    cast.update(ind=16, nm='Тень клапана на кармане', refId='img_13', ip=0, op=61)
    ease = {'o': {'x': [.45], 'y': [0]}, 'i': {'x': [.55], 'y': [1]}}
    cast['ks']['o'] = {'a': 1, 'k': [dict(t=42, s=[100], **ease), {'t': 60, 's': [0]}]}
    anim['layers'].insert(anim['layers'].index(layers[4]), cast)

    # тень кармана на письме – та же размытая форма кармана, что была в анимации (σ 6 px, 5 px вверх)
    pad = np.pad(pocket, 30)
    sh = ndi.shift(ndi.gaussian_filter(pad, 6), (-5, 0), order=1) * .219
    put('img_4', 'img_4.webp', np.broadcast_to(np.array([40., 30, 8]), sh.shape + (3,)), sh)

    # вырез кармана: письмо видно над краем кармана; подкладка – до края кармана с запасом
    tl, tr = (env_line(*l) for l in ENV_TOP)
    bl, br = (env_line(*l) for l in ENV_BOT)
    cross = lambda l1, l2: ((l2[1] - l1[1]) / (l1[0] - l2[0]) * l1[0] + l1[1], (l2[1] - l1[1]) / (l1[0] - l2[0]))
    jl, jr, apex, vee = cross(tl, bl), cross(tr, br), cross(bl, br), cross(tl, tr)
    yl, yr = -tl[1] / tl[0], (857 - tr[1]) / tr[0]
    r2 = lambda p: [round(p[0], 2), round(p[1], 2)]
    cut = [[0, -3056], [857, -3056], [857, yr], jr, apex, jl, [0, yl]]
    shape = layers[6]['shapes'][0]['it'][0]['ks']['k']
    shape.update(v=[r2(p) for p in cut], i=[[0, 0]] * len(cut), o=[[0, 0]] * len(cut))
    lin = [[0, 0], [857, 0], [857, yr + 6], [vee[0], vee[1] + 9], [0, yl + 6]]
    m = layers[13]['masksProperties'][0]['pt']['k']
    m.update(v=[[p[0], round(p[1] - 14, 2)] for p in lin], i=[[0, 0]] * 5, o=[[0, 0]] * 5)

    # подкладка и тень под клапаном – с 49 кадра, когда клапан начинает подниматься: раньше их видно
    # только серыми квадратами в скруглённых верхних углах закрытого конверта
    for i in (12, 13):
        layers[i]['ip'] = 49

    path = os.path.join(ENV_DST, 'envelope.js')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('/* Открытие конверта (Lottie). Создаётся из tools/src/envelope-opening.json и envelope2.png: python3 tools/cut.py envelope */\n')
        f.write('window.ENVELOPE_ANIMATION = ' + json.dumps(anim, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print(f'envelope/envelope.js {os.path.getsize(path) // 1024} KB')


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
# frame-1.webp – слои SVG «Рамка 1», сведённые без изменений; frame-dress-pearl.webp и frame-place-pearl.jpg –
# присланные жемчужные рамки «Дресс-код» и «Адрес» (на чёрном);
# sample-*.jpg / sample-place.webp – образцы из архива «образец страниц сайта» (с них – лилия и линии «Адреса»).
# На сайте прямоугольные рамки тянутся по высоте под текст: растягивается полоса с ровными планками
# (у «Рамки 1» – строки 1020–1110; у «Дресс-кода» полоса из целого числа жемчужин повторяется, см. frame_dress).

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


# Новые рамки подгоняются под поле для текста прежних, поэтому раскладка текста в style.css не меняется.
# «Дресс-код»: поле прежней рамки в кадре 869 × 1775 и поле присланной frame-dress-pearl.webp (884 × 1779) –
# x слева и справа посередине высоты, y сверху и снизу между цветами.
DRESS_FIELD_OLD = (107, 251, 782, 1654)
DRESS_FIELD_NEW = (97, 176, 784, 1566)
DRESS_GAP = 133          # от низа поля до низа кадра – как у прежней рамки (больше – если цветок внизу ниже)
DRESS_SIDE = 120         # ширина боковых планок для border-image (жемчужная нитка и золотые линии)
# «Адрес»: овал поля текущей рамки (1024 × 1536) и присланной frame-place-pearl.jpg (1024 × 1536)
PLACE_FIELD_OLD = (182, 298, 841, 1234)
PLACE_FIELD_NEW = (174, 289, 849, 1212)


def fit_frame(rgb, alpha, sx, sy, tx, ty, size):
    """Масштаб sx, sy и сдвиг tx, ty в кадр size (премультиплицированно – без тёмной каймы на краях)."""
    im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha * 255]).round().astype(np.uint8), 'RGBA').convert('RGBa')
    im = im.transform(size, Image.AFFINE, (1 / sx, 0, -tx / sx, 0, 1 / sy, -ty / sy), Image.BICUBIC).convert('RGBA')
    a = np.asarray(im).astype(float)
    return a[..., :3], a[..., 3] / 255


def frame_dress():
    """Рамка «Дресс-код» – присланная жемчужная frame-dress-pearl.webp: чёрный фон – прозрачный; масштаб одинаковый
    по обеим осям – ширина поля как у прежней рамки, верх поля на том же месте, низ кадра – на DRESS_GAP ниже поля.
    Лилия у «оставить для невесты» – с образца.
    Бока рамки – жемчужная нитка: при вытягивании под текст полоса из целого числа жемчужин повторяется
    (border-image round), а не растягивается. Печатает её строки – --cut-* в style.css."""
    rgb, alpha = cut_black(load('frame-dress-pearl.webp'), band=4)
    (ox0, oy0, ox1, _), (nx0, ny0, nx1, ny1) = DRESS_FIELD_OLD, DRESS_FIELD_NEW
    k = (ox1 - ox0) / (nx1 - nx0)
    tx, ty = ox0 - nx0 * k, oy0 - ny0 * k
    low = np.where(alpha.max(1) > .03)[0][-1] * k + ty         # нижний край цветка
    H = int(np.ceil(max(ny1 * k + ty + DRESS_GAP, low + 3)))
    rgb, alpha = fit_frame(rgb, alpha, k, k, tx, ty, (869, H))
    save_full('frame-dress', rgb, alpha, quality=88)
    # полоса для повторения: высота – целое число жемчужин, строки над и под ней совпадают на обоих боках
    flat = rgb * alpha[..., None]
    sides = np.r_[0:DRESS_SIDE, 869 - DRESS_SIDE:869]
    sig = flat[400:1300, 40:110].mean((1, 2))
    sig = sig - sig.mean()
    ac = np.correlate(sig, sig, 'full')[len(sig) - 1:]
    period = 15 + np.argmax(ac[15:120])
    best = None
    for n in (3, 4, 5):
        h = int(round(n * period))
        for r in range(int(ny0 * k + ty) + 450, int(ny1 * k + ty) - 650 - h):
            err = np.abs(flat[r - 2:r + 3, sides] - flat[r + h - 2:r + h + 3, sides]).mean()
            if best is None or err < best[0]:
                best = (err, r, h)
    err, r, h = best
    print(f'  кадр 869 × {H}, шаг жемчуга {period}, полоса строк {r}–{r + h} ({h} = {h / period:.2f} шага, '
          f'шов {err:.1f}): --frame-h {H}; --cut-t {r}; --cut-b {H - r - h}; бока {DRESS_SIDE}')
    y0, y1, x0, x1 = 812, 930, 650, 798
    s = load('sample-dress.jpg')[y0:y1, x0:x1]
    paper = np.median(s.reshape(-1, 3), 0)
    s = s * np.median(rgb[y0:y1, x0:x1].reshape(-1, 3), 0) / paper     # бумага образца → тон бумаги рамки
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
    """«Адрес» – присланная жемчужная овальная рамка frame-place-pearl.jpg (1024 × 1536): чёрный фон – прозрачный,
    овал поля совмещён с полем прежней рамки (по ширине −2,4 %, по высоте +1,4 %); если нижний цветок выходит
    за кадр, рамка чуть приподнимается. Линии с лилией и подвеска под «Открыть на карте» – с образца."""
    rgb, alpha = cut_black(load('frame-place-pearl.jpg'), band=4, min_hole=1)
    (ox0, oy0, ox1, oy1), (nx0, ny0, nx1, ny1) = PLACE_FIELD_OLD, PLACE_FIELD_NEW
    sx, sy = (ox1 - ox0) / (nx1 - nx0), (oy1 - oy0) / (ny1 - ny0)
    tx, ty = ox0 - nx0 * sx, oy0 - ny0 * sy
    rows = np.where(alpha.max(1) > .03)[0]
    ty -= max(0, rows[-1] * sy + ty - (1536 - 3))
    print(f'  поле: x {nx0 * sx + tx:.0f}–{nx1 * sx + tx:.0f}, y {ny0 * sy + ty:.0f}–{ny1 * sy + ty:.0f} (прежнее {PLACE_FIELD_OLD})')
    rgb, alpha = fit_frame(rgb, alpha, sx, sy, tx, ty, (1024, 1536))
    save_full('frame-place', rgb, alpha, quality=88)
    s = load_rgba('sample-place.webp')[..., :3]
    yy, xx = np.mgrid[:1536, :1024]
    clean = paper_tone(s, ((xx - 513) / 330) ** 2 + ((yy - 765) / 460) ** 2 < 1)
    ornament('orn-rule', s, clean, (560, 622, 262, 766), clear=(560, 583, 262, 480))   # без хвоста «А»
    ornament('orn-rule-short', s, clean, (766, 827, 386, 643))
    ornament('orn-pendant', s, clean, (1095, 1129, 474, 554))   # подвеска под «Открыть на карте» (линия – на сайте)


ALL = {f.__name__: f for f in (heart_wreath, envelope, backgrounds, flowers_bottom, hero,
                               frame_program, frame_invite, frame_dress, frame_place)}
if __name__ == '__main__':
    for n in sys.argv[1:] or ALL:
        ALL[n.replace('-', '_')]()
