// Общие функции для орнаментов: завитки, листья, бусины.
const NS = 'http://www.w3.org/2000/svg';
const f = n => n.toFixed(1);

function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}

// кубическая Безье → точки
function bez(p0, p1, p2, p3, n = 40) {
  const out = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, u = 1 - t;
    out.push([
      u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
      u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]
    ]);
  }
  return out;
}

// продолжение линии спиралью: от последней точки, по направлению касательной
function curl(pts, r0, turns = 1.1, dir = 1, n = 50) {
  const a = pts[pts.length - 2], b = pts[pts.length - 1];
  let ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
  const cx = b[0] + Math.cos(ang + dir * Math.PI / 2) * r0;
  const cy = b[1] + Math.sin(ang + dir * Math.PI / 2) * r0;
  let th = Math.atan2(b[1] - cy, b[0] - cx);
  const out = pts.slice();
  for (let i = 1; i <= n; i++) {
    const t = i / n;
    const r = r0 * (1 - .78 * t);
    const tt = th + dir * t * turns * Math.PI * 2;
    out.push([cx + Math.cos(tt) * r, cy + Math.sin(tt) * r]);
  }
  return out;
}

// лента переменной ширины вдоль линии (каллиграфический завиток)
function ribbon(pts, w0, w1, wMid) {
  const L = [], R = [];
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const p = pts[i], q = pts[Math.min(n - 1, i + 1)], o = pts[Math.max(0, i - 1)];
    let tx = q[0] - o[0], ty = q[1] - o[1];
    const m = Math.hypot(tx, ty) || 1; tx /= m; ty /= m;
    const t = i / (n - 1);
    const w = wMid !== undefined ? (t < .5 ? w0 + (wMid - w0) * Math.sin(t * Math.PI) : wMid + (w1 - wMid) * (t - .5) * 2) : w0 + (w1 - w0) * t;
    L.push([p[0] - ty * w / 2, p[1] + tx * w / 2]);
    R.push([p[0] + ty * w / 2, p[1] - tx * w / 2]);
  }
  let d = 'M' + L.map(p => f(p[0]) + ' ' + f(p[1])).join('L');
  d += 'L' + R.reverse().map(p => f(p[0]) + ' ' + f(p[1])).join('L') + 'Z';
  return d;
}

// лист аканта/лавра: каплевидная форма
function leaf(x, y, len, wid, ang, bend = .25) {
  const ca = Math.cos(ang), sa = Math.sin(ang);
  const P = (u, v) => [x + u * ca - v * sa, y + u * sa + v * ca];
  const tip = P(len, len * bend * .4);
  const l1 = P(len * .3, -wid), l2 = P(len * .75, -wid * .7 + len * bend * .2);
  const r1 = P(len * .3, wid * .7), r2 = P(len * .75, wid * .55 + len * bend * .3);
  return `M${f(x)} ${f(y)}C${f(l1[0])} ${f(l1[1])} ${f(l2[0])} ${f(l2[1])} ${f(tip[0])} ${f(tip[1])}C${f(r2[0])} ${f(r2[1])} ${f(r1[0])} ${f(r1[1])} ${f(x)} ${f(y)}Z`;
}

// точки вдоль эллипса
function ellipsePts(cx, cy, rx, ry, n, a0 = 0) {
  return Array.from({ length: n }, (_, i) => {
    const t = a0 + i / n * Math.PI * 2;
    return { x: cx + rx * Math.cos(t), y: cy + ry * Math.sin(t), t, ang: Math.atan2(ry * Math.cos(t), -rx * Math.sin(t)) };
  });
}
