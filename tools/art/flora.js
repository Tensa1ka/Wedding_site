// Библиотека цветов в палитре праздника. Рисует в SVG-группы.
// Требует ornament.js (el, bez, f).

const PAL = {
  rose:      { hi: '#eebcb5', mid: '#c58e88', lo: '#93585a', vein: '#a86a68' },
  blush:     { hi: '#fbe8e3', mid: '#e3bfb9', lo: '#bf8f8a', vein: '#c9a09a' },
  peach:     { hi: '#fbe0d0', mid: '#e6b39c', lo: '#bf8064', vein: '#c99278' },
  champagne: { hi: '#fbf1e6', mid: '#e0c6af', lo: '#b3937a', vein: '#c4a78f' },
  ivory:     { hi: '#ffffff', mid: '#f4ece2', lo: '#cdbcaa', vein: '#dccfc0' },
  powder:    { hi: '#e3edf4', mid: '#b2c7d6', lo: '#7f97aa' },
  misty:     { hi: '#c4d1d7', mid: '#8299a3', lo: '#56707b' },
  euca:      { hi: '#cfd8c4', mid: '#9fb08f', lo: '#61755a' },
  sage:      { hi: '#b9c4b0', mid: '#8e9c86', lo: '#5d6b58' },
  // зелёно-белая гамма
  lime:      { hi: '#eef4c4', mid: '#b9c86c', lo: '#7a8c36', vein: '#8c9e45' },
  lime2:     { hi: '#f4f8dc', mid: '#d2dd98', lo: '#98a85a', vein: '#a7b66a' },
  white:     { hi: '#ffffff', mid: '#f3f1e8', lo: '#c6c4b2', vein: '#dcdacb' },
  cream:     { hi: '#fffcf3', mid: '#efe8d6', lo: '#c4b897', vein: '#d9cfb6' },
  hydraG:    { hi: '#f1f6dc', mid: '#c9d79c', lo: '#90a65a' },
  hydraW:    { hi: '#ffffff', mid: '#e9eedb', lo: '#b4c096' },
  amaG:      { hi: '#dde7a8', mid: '#aabb64', lo: '#6f8436' },
  leaf:      { hi: '#8fa865', mid: '#56723a', lo: '#2e451c' },
  olive:     { hi: '#b7bf8f', mid: '#8b9662', lo: '#5d6a3c' },
  stem:      '#6f8452'
};

let _uid = 0;
const uid = p => p + (++_uid);

function setupDefs(svg) {
  const defs = el('defs', {}, svg);
  defs.innerHTML = `
    <filter id="fShadow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="5"/><feOffset dx="3" dy="7"/>
      <feComponentTransfer><feFuncA type="linear" slope=".28"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="fShadowSm" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="2"/><feOffset dx="1" dy="2.5"/>
      <feComponentTransfer><feFuncA type="linear" slope=".3"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="fGloss" x="-10%" y="-10%" width="120%" height="120%" color-interpolation-filters="sRGB">
      <feGaussianBlur in="SourceAlpha" stdDeviation="6" result="b"/>
      <feSpecularLighting in="b" surfaceScale="9" specularConstant=".85" specularExponent="16" lighting-color="#fff" result="s">
        <feDistantLight azimuth="235" elevation="50"/>
      </feSpecularLighting>
      <feComposite in="s" in2="SourceAlpha" operator="in"/>
    </filter>
    <filter id="fSoft"><feGaussianBlur stdDeviation="8"/></filter>
    <filter id="fSoft3"><feGaussianBlur stdDeviation="3"/></filter>
    <filter id="fBloom" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency=".6" numOctaves="2" seed="8"/>
      <feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .5 -.12"/>
      <feComposite in2="SourceGraphic" operator="in"/>
    </filter>
    <filter id="fDots" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="1.4" numOctaves="1" seed="2"/>
      <feColorMatrix values="0 0 0 0 .55  0 0 0 0 .4  0 0 0 0 .2  0 0 0 1.6 -.75"/>
      <feComposite in2="SourceGraphic" operator="in"/>
    </filter>`;
  return defs;
}

function grad(defs, type, stops, attrs = {}) {
  const id = uid('g');
  const g = el(type === 'r' ? 'radialGradient' : 'linearGradient', Object.assign({ id }, attrs), defs);
  stops.forEach(([o, c, op]) => el('stop', { offset: o, 'stop-color': c, 'stop-opacity': op ?? 1 }, g));
  return `url(#${id})`;
}

// стебель: плавная линия, чуть светлее по одному краю
function stem(g, pts, w = 4, color = PAL.stem) {
  const d = 'M' + pts.map(p => f(p[0]) + ' ' + f(p[1])).join('L');
  el('path', { d, fill: 'none', stroke: color, 'stroke-width': w, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, g);
  el('path', { d, fill: 'none', stroke: '#fff', 'stroke-opacity': .22, 'stroke-width': w * .35, 'stroke-linecap': 'round', transform: `translate(${-w * .2} ${-w * .15})` }, g);
}
function stemBez(g, a, b, c, d, w, color) { stem(g, bez(a, b, c, d, 30), w, color); }

// ---------- Антуриум ----------
// x,y – место крепления (выемка), s – масштаб, rot – поворот (град), кончик смотрит вниз при rot=0
function anthurium(defs, g, x, y, s, rot, key, opts = {}) {
  const P = PAL[key];
  const sq = opts.squash ?? .86, skew = opts.skew ?? 0;
  const gg = el('g', { transform: `translate(${x} ${y}) rotate(${rot}) skewX(${skew}) scale(${s} ${s * sq})`, filter: 'url(#fShadow)' }, g);
  const spathe = 'M0 0C-26-22-72-20-80 16C-88 58-44 112 0 168C44 112 88 58 80 16C72-20 26-22 0 0Z';
  const fill = grad(defs, 'r', [[0, P.hi], [.55, P.mid], [1, P.lo]], { cx: '42%', cy: '34%', r: '75%' });
  el('path', { d: spathe, fill }, gg);
  // прожилки: тёмная бороздка + светлый край
  const veins = [];
  for (let k = 1; k <= 4; k++) {
    const sp = k * 15;
    veins.push(`M0 6C${-sp - 6} ${10 + k * 4} ${-sp - 12} ${60 + k * 6} ${-4 - k * 2} ${150 - k * 9}`);
    veins.push(`M0 6C${sp + 6} ${10 + k * 4} ${sp + 12} ${60 + k * 6} ${4 + k * 2} ${150 - k * 9}`);
  }
  veins.push('M0 6L0 160');
  const clipId = uid('c');
  el('clipPath', { id: clipId }, defs).appendChild(el('path', { d: spathe }));
  const vg = el('g', { 'clip-path': `url(#${clipId})` }, gg);
  veins.forEach(d => {
    el('path', { d, fill: 'none', stroke: P.lo, 'stroke-opacity': .45, 'stroke-width': 1.6 }, vg);
    el('path', { d, fill: 'none', stroke: '#fff', 'stroke-opacity': .35, 'stroke-width': 1.2, transform: 'translate(1.6 1.2)' }, vg);
  });
  // блики и глянец
  el('ellipse', { cx: -30, cy: 34, rx: 26, ry: 40, fill: '#fff', opacity: .38, filter: 'url(#fSoft)', transform: 'rotate(18 -30 34)' }, vg);
  el('ellipse', { cx: 36, cy: 70, rx: 18, ry: 34, fill: '#fff', opacity: .2, filter: 'url(#fSoft)', transform: 'rotate(-14 36 70)' }, vg);
  el('path', { d: spathe, fill: '#fff', filter: 'url(#fGloss)', opacity: .55 }, gg);
  // початок
  const ang = opts.spadix ?? -70;
  const len = opts.spadixLen ?? 74;
  const sg = el('g', { transform: `rotate(${ang + 90})` }, gg);
  const sd = `M-6 4C-8-${len * .4} -4-${len * .8} 3-${len}C6-${len - 2} 7-${len * .78} 6-${len * .4}C6-${len * .1} 6 0 6 4Z`;
  const sfill = grad(defs, 'l', [[0, '#f7ecd5'], [.5, '#e8cf9d'], [1, '#c99f5e']], { x1: 0, y1: 0, x2: 1, y2: 0 });
  el('path', { d: sd, fill: sfill }, sg);
  el('path', { d: sd, fill: '#fff', filter: 'url(#fDots)', opacity: .9 }, sg);
  return gg;
}

// лист антуриума (сердцевидный, приглушённый)
function anthLeaf(defs, g, x, y, s, rot, key = 'leaf') {
  const P = PAL[key];
  const gg = el('g', { transform: `translate(${x} ${y}) rotate(${rot}) scale(${s})`, filter: 'url(#fShadow)' }, g);
  const d = 'M0 0C-30-30-96-22-100 30C-104 92-44 160 0 230C44 160 104 92 100 30C96-22 30-30 0 0Z';
  el('path', { d, fill: grad(defs, 'l', [[0, P.hi], [.5, P.mid], [1, P.lo]], { x1: 0, y1: 0, x2: .6, y2: 1 }) }, gg);
  el('path', { d: 'M0 4L0 222', stroke: '#fff', 'stroke-opacity': .35, 'stroke-width': 2, fill: 'none' }, gg);
  for (let k = 1; k <= 5; k++) {
    const yy = k * 34;
    el('path', { d: `M0 ${yy}C-24 ${yy + 4} -54 ${yy + 18} -74 ${yy + 48 - k * 6}M0 ${yy}C24 ${yy + 4} 54 ${yy + 18} 74 ${yy + 48 - k * 6}`, fill: 'none', stroke: '#fff', 'stroke-opacity': .2, 'stroke-width': 1.4 }, gg);
  }
  el('path', { d, fill: '#fff', filter: 'url(#fGloss)', opacity: .12 }, gg);
}

// ---------- Гортензия ----------
let _seed = 17;
const rnd = () => (_seed = (_seed * 16807) % 2147483647) / 2147483647;
function seedRnd(s) { _seed = s; }

function floret(defs, g, x, y, r, rot, cols) {
  const gg = el('g', { transform: `translate(${f(x)} ${f(y)}) rotate(${f(rot)})` }, g);
  const c = cols[Math.floor(rnd() * cols.length)];
  const fill = grad(defs, 'r', [[0, c[1]], [.6, c[0]], [1, c[0]]], { cx: '50%', cy: '90%', r: '90%' });
  for (let k = 0; k < 4; k++) {
    const a = k * 90 + (rnd() - .5) * 16;
    el('path', { d: `M0 ${-r * .08}C${-r * .5} ${-r * .2} ${-r * .62} ${-r * .95} 0 ${-r}C${r * .62} ${-r * .95} ${r * .5} ${-r * .2} 0 ${-r * .08}Z`, fill, transform: `rotate(${f(a)})`, stroke: c[1], 'stroke-opacity': .5, 'stroke-width': .7 }, gg);
  }
  el('circle', { r: r * .13, fill: '#e4e9cf' }, gg);
  el('circle', { r: r * .06, fill: '#9aa86a' }, gg);
}

function hydrangea(defs, g, x, y, R, keys = ['powder', 'misty'], opts = {}) {
  const gg = el('g', { filter: 'url(#fShadow)' }, g);
  // объём шапки
  el('circle', { cx: x, cy: y, r: R * .72, fill: grad(defs, 'r', [[0, PAL[keys[0]].mid], [1, PAL[keys[keys.length - 1]].mid]], { cx: '40%', cy: '35%' }) }, gg);
  const cols = [];
  keys.forEach((k, i) => { const w = i === 0 ? 5 : 1; for (let j = 0; j < w; j++) cols.push([PAL[k].hi, PAL[k].mid]); if (i === 0) cols.push([PAL[k].mid, PAL[k].lo]); });
  if (opts.blushTint) cols.push([PAL.blush.hi, PAL.blush.mid]);
  const pts = [];
  const n = Math.round(R * R / 120);
  for (let i = 0; i < n; i++) {
    const a = rnd() * Math.PI * 2, rr = Math.sqrt(rnd()) * R * .92;
    pts.push([x + Math.cos(a) * rr, y + Math.sin(a) * rr]);
  }
  pts.sort((p, q) => (p[1] - q[1]) * .6 + (p[0] - q[0]) * .4);
  pts.forEach(p => {
    const dist = Math.hypot(p[0] - x, p[1] - y) / R;
    floret(defs, gg, p[0], p[1], R * (.24 - dist * .06) * (.85 + rnd() * .3), rnd() * 90, cols);
  });
  // тень снизу-справа для объёма
  const clip = uid('c');
  el('clipPath', { id: clip }, defs).appendChild(el('circle', { cx: x, cy: y, r: R * 1.05 }));
  el('circle', { cx: x + R * .35, cy: y + R * .4, r: R * .8, fill: PAL[keys[keys.length - 1]].lo, opacity: .2, filter: 'url(#fSoft)', 'clip-path': `url(#${clip})` }, gg);
  el('circle', { cx: x - R * .3, cy: y - R * .35, r: R * .5, fill: '#fff', opacity: .25, filter: 'url(#fSoft)', 'clip-path': `url(#${clip})` }, gg);
}

// ---------- Роза (вид сверху: слои лепестков и закрученная сердцевина) ----------
function rose(defs, g, x, y, R, key, rot = 0) {
  const P = PAL[key];
  const gg = el('g', { transform: `translate(${x} ${y}) rotate(${rot})`, filter: 'url(#fShadow)' }, g);
  el('circle', { r: R * .5, fill: P.lo }, gg);
  const petalFill = grad(defs, 'r', [[0, P.lo], [.55, P.mid], [.9, P.hi], [1, P.hi]], { cx: 0, cy: 0, r: R, gradientUnits: 'userSpaceOnUse', fx: 0, fy: 0 });
  const pol = (r, a) => [r * Math.cos(a), r * Math.sin(a)];
  function petal(r0, r1, a, span, parent, light) {
    const p0 = pol(r0, a - span), p1 = pol(r1 * .92, a - span * .85), p2 = pol(r1 * 1.08, a), p3 = pol(r1 * .92, a + span * .85), p4 = pol(r0, a + span);
    const c1 = pol(r1 * 1.06, a - span * .5), c2 = pol(r1 * 1.06, a + span * .5);
    const d = `M${f(p0[0])} ${f(p0[1])}L${f(p1[0])} ${f(p1[1])}Q${f(c1[0])} ${f(c1[1])} ${f(p2[0])} ${f(p2[1])}Q${f(c2[0])} ${f(c2[1])} ${f(p3[0])} ${f(p3[1])}L${f(p4[0])} ${f(p4[1])}Z`;
    el('path', { d, fill: petalFill, filter: 'url(#fShadowSm)' }, parent);
    // светлый загнутый край
    el('path', { d: `M${f(p1[0])} ${f(p1[1])}Q${f(c1[0])} ${f(c1[1])} ${f(p2[0])} ${f(p2[1])}Q${f(c2[0])} ${f(c2[1])} ${f(p3[0])} ${f(p3[1])}`, fill: 'none', stroke: '#fff', 'stroke-opacity': light, 'stroke-width': R * .035, 'stroke-linecap': 'round' }, parent);
  }
  const layers = [[.42, 1, 6, .62, .55], [.3, .78, 5, .7, .5], [.18, .58, 5, .72, .45], [.1, .4, 4, .8, .4]];
  layers.forEach(([r0, r1, n, sp, li], L) => {
    const off = L * .55 + rnd() * .3;
    for (let i = 0; i < n; i++) petal(R * r0, R * r1, off + i / n * Math.PI * 2, sp * Math.PI / n * 1.6, gg, li);
  });
  // закрученная сердцевина
  for (let k = 0; k < 7; k++) {
    const r = R * (.05 + k * .035), a0 = k * 1.9;
    const pA = pol(r, a0), pB = pol(r * 1.1, a0 + 2.6);
    el('path', { d: `M${f(pA[0])} ${f(pA[1])}A${f(r)} ${f(r)} 0 0 1 ${f(pB[0])} ${f(pB[1])}`, fill: 'none', stroke: P.lo, 'stroke-width': R * .03, 'stroke-linecap': 'round', opacity: .7 }, gg);
    el('path', { d: `M${f(pA[0])} ${f(pA[1])}A${f(r)} ${f(r)} 0 0 1 ${f(pB[0])} ${f(pB[1])}`, fill: 'none', stroke: P.hi, 'stroke-width': R * .015, 'stroke-linecap': 'round', opacity: .8, transform: `translate(${-R * .012} ${-R * .012})` }, gg);
  }
  el('circle', { r: R * 1.02, fill: '#fff', opacity: .12, filter: 'url(#fSoft)', transform: `translate(${-R * .3} ${-R * .3}) scale(.6)` }, gg);
}

// ---------- Эвкалипт (круглые листья с налётом) ----------
function eucalyptus(defs, g, pts, leafR = 16, key = 'euca', every = 3) {
  stem(g, pts, 2.6, '#7e8a6c');
  const P = PAL[key];
  const gg = el('g', { filter: 'url(#fShadowSm)' }, g);
  for (let i = 2; i < pts.length - 1; i += every) {
    const p = pts[i], q = pts[i + 1];
    const a = Math.atan2(q[1] - p[1], q[0] - p[0]);
    const t = i / pts.length;
    const r = leafR * (1.1 - t * .5) * (.85 + rnd() * .3);
    [-1, 1].forEach((side, k) => {
      if ((i / every + k) % 2 && rnd() < .25) return;
      const ox = p[0] + Math.cos(a + side * Math.PI / 2) * r * .95, oy = p[1] + Math.sin(a + side * Math.PI / 2) * r * .95;
      const fill = grad(defs, 'r', [[0, P.hi], [.7, P.mid], [1, P.lo]], { cx: '40%', cy: '35%', r: '70%' });
      el('ellipse', { cx: f(ox), cy: f(oy), rx: f(r), ry: f(r * .9), fill, transform: `rotate(${f(a * 180 / Math.PI)} ${f(ox)} ${f(oy)})` }, gg);
      el('path', { d: `M${f(p[0])} ${f(p[1])}L${f(ox + (ox - p[0]) * .6)} ${f(oy + (oy - p[1]) * .6)}`, stroke: '#fff', 'stroke-opacity': .3, 'stroke-width': 1 }, gg);
    });
  }
}

// ---------- Свисающий амарант (бусины) ----------
function amaranth(defs, g, x, y, len, sway, key = 'rose') {
  const P = PAL[key];
  const gg = el('g', { filter: 'url(#fShadowSm)' }, g);
  const pts = bez([x, y], [x + sway * .2, y + len * .35], [x + sway, y + len * .6], [x + sway * .8, y + len], 60);
  pts.forEach((p, i) => {
    const t = i / pts.length;
    const r = 6.5 * (1 - t * .7);
    for (let k = 0; k < 3; k++) {
      const ox = (rnd() - .5) * r * 1.6, oy = (rnd() - .5) * r;
      const fill = grad(defs, 'r', [[0, P.hi], [1, rnd() < .5 ? P.mid : P.lo]], { cx: '35%', cy: '30%' });
      el('circle', { cx: f(p[0] + ox), cy: f(p[1] + oy), r: f(r * (.6 + rnd() * .5)), fill }, gg);
    }
  });
}

// ---------- Гипсофила ----------
function gyps(defs, g, x, y, R, n = 34) {
  const gg = el('g', {}, g);
  for (let i = 0; i < n; i++) {
    const a = rnd() * Math.PI * 2, rr = Math.sqrt(rnd()) * R;
    const px = x + Math.cos(a) * rr, py = y + Math.sin(a) * rr;
    el('path', { d: `M${f(x)} ${f(y + R * .8)}Q${f((x + px) / 2 + 6)} ${f((y + py) / 2 + 10)} ${f(px)} ${f(py)}`, stroke: '#a7ad9c', 'stroke-width': .8, fill: 'none' }, gg);
    el('circle', { cx: f(px), cy: f(py), r: f(3 + rnd() * 2.6), fill: rnd() < .3 ? PAL.champagne.hi : '#fffaf4', stroke: '#e6d8c8', 'stroke-width': .6 }, gg);
  }
}

// ---------- Калла ----------
// x,y – низ воронки; растёт вверх по углу rot
function calla(defs, g, x, y, s, rot, key = 'ivory') {
  const P = PAL[key];
  const gg = el('g', { transform: `translate(${x} ${y}) rotate(${rot}) scale(${s})`, filter: 'url(#fShadow)' }, g);
  const body = 'M-6 0C-10-50-24-100-40-148C-48-176-14-204 26-222C30-202 46-182 42-156C36-108 14-50 6 0Z';
  el('path', { d: body, fill: grad(defs, 'l', [[0, P.lo], [.45, P.mid], [1, P.hi]], { x1: 1, y1: 1, x2: 0, y2: .2 }) }, gg);
  // горловина
  el('path', { d: 'M-40-148C-30-162 20-170 42-156C30-146-20-138-40-148Z', fill: grad(defs, 'l', [[0, P.lo], [1, P.mid]], { x1: 0, y1: 0, x2: 0, y2: 1 }) }, gg);
  el('path', { d: 'M-2-150C-4-176 2-194 8-200C11-200 12-197 11-193C8-178 6-162 5-150Z', fill: grad(defs, 'l', [[0, '#f0d9a2'], [1, '#c9a25d']], { x1: 0, y1: 0, x2: 1, y2: 0 }) }, gg);
  // передний край горловины, отогнутый
  el('path', { d: 'M-40-148C-20-136 26-142 42-156C30-140-14-130-40-148Z', fill: P.hi }, gg);
  el('path', { d: 'M-40-148C-48-176-14-204 26-222', fill: 'none', stroke: '#fff', 'stroke-opacity': .55, 'stroke-width': 2.4 }, gg);
  el('path', { d: body, fill: '#fff', filter: 'url(#fGloss)', opacity: .4 }, gg);
}
