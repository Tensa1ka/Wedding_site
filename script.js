/* =========================================================
   Свадебный сайт · логика и движение
   ========================================================= */
(function () {
  "use strict";

  var root = document.documentElement;
  var body = document.body;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canAnimate = !!Element.prototype.animate;

  if ("scrollRestoration" in history) history.scrollRestoration = "manual";

  /* рукописные заголовки: содержимое – во внутренний слой, который раскрывается маской */
  document.querySelectorAll("[data-write]").forEach(function (el) {
    var ink = document.createElement("span");
    ink.className = "ink";
    while (el.firstChild) ink.appendChild(el.firstChild);
    el.appendChild(ink);
  });

  /* ---------- Музыка (если положить assets/music.mp3) ---------- */
  var audio = document.getElementById("bg-music");
  var musicBtn = document.getElementById("music");
  function setPlaying(on) {
    musicBtn.classList.toggle("is-playing", on);
    musicBtn.setAttribute("aria-pressed", on ? "true" : "false");
  }
  function playMusic() {
    if (!audio) return;
    audio.volume = 0.4;
    var p = audio.play();
    if (p && p.then) {
      p.then(function () { musicBtn.hidden = false; setPlaying(true); })
       .catch(function () { /* файла нет или браузер запретил – без музыки */ });
    }
  }
  if (audio && musicBtn) {
    audio.addEventListener("pause", function () { setPlaying(false); });
    audio.addEventListener("play", function () { setPlaying(true); });
    musicBtn.addEventListener("click", function () { if (audio.paused) playMusic(); else audio.pause(); });
  }

  /* =========================================================
     Лицо открытки: открытие конверта (около 5,5 секунды)
     0–0,32 с  печать вдавливается и отпускает – она целая;
     0,25–1,5  камера отъезжает: конверт меньше и ниже, чтобы открытый клапан с печатью и письмо уместились в экран;
     0,55–1,75 клапан вместе с печатью откидывается на петле, за ребром уходит за письмо;
     1,7–2,0   пауза 0,3 с: клапан лёг, конверт открыт, в нём письмо;
     1,88–2,98 письмо выезжает из кармана перед клапаном (первые доли секунды – едва заметно);
     3,13–4,13 конверт уходит вниз, письмо выходит в центр экрана и приближается;
     4,58–5,48 письмо растворяется – под ним обложка, на которой поднимается сердце и пишутся имена.
     ========================================================= */
  var intro = document.getElementById("intro");
  var openBtn = document.getElementById("intro-open");
  var opened = false;

  function reveal() {
    root.classList.remove("is-locked");
    body.classList.add("is-opened");
    setTimeout(function () { body.classList.add("is-settled"); }, 3600);
  }

  function openInvitation() {
    if (opened) return;
    opened = true;
    playMusic();
    intro.classList.add("is-open");

    if (reduceMotion || !canAnimate) {
      intro.style.transition = "opacity .7s ease";
      intro.style.opacity = "0";
      reveal();
      setTimeout(function () { intro.remove(); }, 800);
      return;
    }

    var q = function (s) { return intro.querySelector(s); };
    var card = q(".env__card"), letter = q(".env__letter"), note = q(".env__note");
    var out = "cubic-bezier(.22,1,.36,1)", inOut = "cubic-bezier(.65,0,.35,1)";
    var run = function (sel, frames, opts) {
      var el = typeof sel === "string" ? q(sel) : sel;
      opts.fill = "forwards";
      return el.animate(frames, opts);
    };

    // камера: открытый клапан с печатью поднимается над конвертом на 53 % его высоты – вся сцена должна уместиться в экран
    var vw = window.innerWidth, vh = window.innerHeight;
    var r = card.getBoundingClientRect();
    var k = Math.min(1, .9 * vh / (1.533 * r.height), .92 * vw / r.width);
    var dy = vh / 2 + .2665 * r.height * k - (r.top + r.height / 2);
    run(card, [{ transform: "none" }, { transform: "translateY(" + dy.toFixed(1) + "px) scale(" + k.toFixed(4) + ")" }],
      { duration: 1250, delay: 250, easing: inOut });

    // печать отзывается на нажатие и остаётся целой – дальше она едет вместе с клапаном
    run(".seal__img", [{ transform: "scale(1)" }, { transform: "scale(.94)", offset: .45 }, { transform: "scale(1)" }],
      { duration: 320, easing: out });

    // клапан: чуть отклеивается, затем откидывается назад; дальше ребра (90°) – за письмом
    var flap = { duration: 1200, delay: 550, easing: "cubic-bezier(.45,0,.2,1)" };
    run(".env__flap", [
      { transform: "rotateX(0deg)" },
      { transform: "rotateX(9deg)", offset: .15 },
      { transform: "rotateX(180deg)" }
    ], flap);
    run(".env__shade", [{ opacity: 0 }, { opacity: .25, offset: .15 }, { opacity: 1, offset: .55 }, { opacity: 1 }], flap);
    run(".env__back-shade", [{ opacity: 1 }, { opacity: 1, offset: .55 }, { opacity: .2 }], flap);
    run(".env__cast", [{ opacity: 1 }, { opacity: 0 }], { duration: 900, delay: 650, easing: "ease-out" });
    setTimeout(function () { intro.classList.add("is-lifting"); }, 550);
    setTimeout(function () { intro.classList.add("is-flipped"); }, 550 + 1200 * .5);

    // конверт 0,3 с стоит открытым (клапан лёг около 1,7 с, письмо заметно трогается около 2,0 с), затем письмо выезжает
    run(note, [{ transform: "translateY(0)" }, { transform: "translateY(-74%)" }],
      { duration: 1100, delay: 1880, easing: "cubic-bezier(.3,0,.15,1)" });

    // конверт уходит вниз, письмо – в центр экрана, крупнее
    setTimeout(function () {
      var nr = note.getBoundingClientRect(), lr = letter.getBoundingClientRect();
      var cx = nr.left + nr.width / 2, cy = nr.top + nr.height / 2;
      var z = Math.min(2, .7 * vh / nr.height, .88 * vw / nr.width);
      letter.style.transformOrigin = ((cx - lr.left) / k).toFixed(1) + "px " + ((cy - lr.top) / k).toFixed(1) + "px";
      letter.style.clipPath = "none";
      run(letter, [{ transform: "none" }, {
        transform: "translate(" + ((vw / 2 - cx) / k).toFixed(1) + "px, " + ((vh / 2 - cy) / k).toFixed(1) + "px) scale(" + z.toFixed(3) + ")"
      }], { duration: 1000, easing: inOut });
      var sink = { duration: 850, easing: "cubic-bezier(.55,0,.8,.45)" };
      [".env__body", ".env__inside", ".env__pocket"].forEach(function (sel) {
        run(sel, [{ translate: "0 0", opacity: 1 }, { translate: "0 80%", opacity: 0 }], sink);
      });
      run(".env__flap", [{ translate: "0 0" }, { translate: "0 80%" }], sink);   // прозрачность – у изнанки и печати: 3D клапана не сплющивается
      run(".env__flap-back", [{ opacity: 1 }, { opacity: 0 }], sink);
      run(".seal-back", [{ opacity: 1 }, { opacity: 0 }], sink);

      // письмо чуть приближается и растворяется в обложку
      run(note, [{ scale: 1 }, { scale: 1.06 }], { duration: 1600, delay: 1100, easing: "ease-out" });
      run(intro, [{ opacity: 1 }, { opacity: 0 }], { duration: 900, delay: 1450, easing: "ease-in-out" });
      setTimeout(reveal, 1350);
      setTimeout(function () { intro.remove(); }, 2450);
    }, 3130);
  }

  if (intro && openBtn) {
    window.scrollTo(0, 0);
    root.classList.add("is-locked");
    var shown = false;
    var show = function () {
      if (shown) return;
      shown = true;
      requestAnimationFrame(function () { intro.classList.add("is-ready"); });
    };
    var sealImg = openBtn.querySelector("img");
    if (sealImg && !sealImg.complete) {
      sealImg.addEventListener("load", show);
      sealImg.addEventListener("error", show);
      setTimeout(show, 2500);
    } else {
      show();
    }
    openBtn.addEventListener("click", openInvitation);
    intro.addEventListener("click", openInvitation);      // нажатие в любом месте экрана
  } else {
    reveal();
  }

  /* ---------- Появления при прокрутке ---------- */
  document.querySelectorAll(".col").forEach(function (col) {
    col.querySelectorAll("[data-reveal]").forEach(function (el, i) { el.style.setProperty("--i", i % 4); });
  });
  document.querySelectorAll(".prog li").forEach(function (el, i) { el.style.setProperty("--i", i); });
  document.querySelectorAll(".cal > *").forEach(function (el, i) { el.style.setProperty("--i", i); });

  function settleLater(el) {
    if (el.hasAttribute("data-bloom")) setTimeout(function () { el.classList.add("is-settled"); }, 2800);
  }
  var watched = document.querySelectorAll("[data-reveal], [data-inview], [data-write], [data-bloom]");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("is-in");
          settleLater(e.target);
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.01 });
    watched.forEach(function (el) { io.observe(el); });
  } else {
    watched.forEach(function (el) { el.classList.add("is-in"); settleLater(el); });
  }

  /* ---------- Параллакс декора (только transform, раз в кадр) ---------- */
  var layers = [].slice.call(document.querySelectorAll("[data-parallax]")).map(function (el) {
    return { el: el, k: parseFloat(el.getAttribute("data-parallax")) || 0, on: false };
  });
  if (layers.length && !reduceMotion && "IntersectionObserver" in window) {
    var vh = window.innerHeight;
    var pio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        layers.forEach(function (l) { if (l.el === e.target) l.on = e.isIntersecting; });
      });
      tick();
    });
    layers.forEach(function (l) { pio.observe(l.el); });
    var queued = false;
    var tick = function () {
      queued = false;
      for (var i = 0; i < layers.length; i++) {
        var l = layers[i];
        if (!l.on) continue;
        var r = l.el.getBoundingClientRect();
        var off = (r.top + r.height / 2 - vh / 2) * l.k;
        off = Math.max(-90, Math.min(90, off));
        l.el.style.transform = "translate3d(0," + off.toFixed(1) + "px,0)";
      }
    };
    window.addEventListener("scroll", function () {
      if (!queued) { queued = true; requestAnimationFrame(tick); }
    }, { passive: true });
    window.addEventListener("resize", function () { vh = window.innerHeight; tick(); });
  }

  /* ---------- Фон-штора: едет вместе с прокруткой, без повторов ---------- */
  var backdrop = document.querySelector(".backdrop img");
  if (backdrop && !reduceMotion) {
    var bdQueued = false;
    var moveBackdrop = function () {
      bdQueued = false;
      var range = document.documentElement.scrollHeight - window.innerHeight;
      var travel = backdrop.offsetHeight - window.innerHeight;
      var p = range > 0 ? Math.min(1, Math.max(0, window.scrollY / range)) : 0;
      backdrop.style.transform = "translate3d(0," + (-p * travel).toFixed(1) + "px,0)";
    };
    var queueBackdrop = function () {
      if (!bdQueued) { bdQueued = true; requestAnimationFrame(moveBackdrop); }
    };
    window.addEventListener("scroll", queueBackdrop, { passive: true });
    window.addEventListener("resize", queueBackdrop);
    window.addEventListener("load", queueBackdrop);
    moveBackdrop();
  }

  /* ---------- Контур отсчёта – по форме «таблетки» ---------- */
  var cd = document.getElementById("countdown");
  var rect = cd && cd.querySelector(".countdown__line rect");
  function sizeOutline() {
    var w = cd.offsetWidth, h = cd.offsetHeight;
    rect.setAttribute("x", .7); rect.setAttribute("y", .7);
    rect.setAttribute("width", Math.max(0, w - 1.4)); rect.setAttribute("height", Math.max(0, h - 1.4));
    rect.setAttribute("rx", (h - 1.4) / 2);
  }
  if (rect) {
    sizeOutline();
    if ("ResizeObserver" in window) new ResizeObserver(sizeOutline).observe(cd);
    else window.addEventListener("resize", sizeOutline);
  }

  /* ---------- Анкета → Google Форма ----------
     После отправки в окне – «Спасибо!» (или просьба попробовать ещё раз) */
  var form = document.getElementById("rsvp-form");
  var ask = document.getElementById("rsvp-ask");
  var done = document.getElementById("rsvp-done");
  var fail = document.getElementById("rsvp-fail");
  var ANSWER = "entry.87327526", NAME = "entry.225506798";

  function openAsk(step) {
    done.hidden = step !== done;
    fail.hidden = step !== fail;
    ask.setAttribute("aria-labelledby", step === done ? "rsvp-done-title" : "rsvp-fail-title");
    if (typeof ask.showModal === "function") ask.showModal(); else ask.setAttribute("open", "");
    step.focus({ preventScroll: true });
  }
  function closeAsk() { if (typeof ask.close === "function") ask.close(); else ask.removeAttribute("open"); }

  if (form && ask) {
    var radios = form.querySelectorAll('input[name="' + ANSWER + '"]');
    var nameInput = form.querySelector('[name="' + NAME + '"]');
    var sendBtn = form.querySelector(".rsvp__send");
    radios.forEach(function (r) { r.addEventListener("change", function () { radios[0].setCustomValidity(""); }); });
    nameInput.addEventListener("input", function () { nameInput.setCustomValidity(""); });
    ask.querySelectorAll("[data-close]").forEach(function (b) { b.addEventListener("click", closeAsk); });
    // нажатие на затемнение вокруг окна закрывает его
    ask.addEventListener("click", function (ev) {
      if (ev.target !== ask) return;
      var r = ask.getBoundingClientRect();
      if (ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom) closeAsk();
    });

    form.addEventListener("submit", function (ev) {
      if (!window.fetch) return;   // старый браузер: обычная отправка формы в новой вкладке
      ev.preventDefault();
      var name = nameInput.value.trim();
      if (!name) {
        nameInput.setCustomValidity("Пожалуйста, напишите имя и фамилию.");
        nameInput.reportValidity();
        return;
      }
      var answer = form.querySelector('input[name="' + ANSWER + '"]:checked');
      if (!answer) {
        radios[0].setCustomValidity("Пожалуйста, выберите вариант ответа.");
        radios[0].reportValidity();
        return;
      }

      sendBtn.classList.add("is-busy");
      var data = new URLSearchParams();
      data.append(NAME, name);
      data.append(ANSWER, answer.value);

      // Google Формы не отвечают на CORS-запросы, поэтому ответ «непрозрачный»:
      // успешная отправка = запрос дошёл без сетевой ошибки
      fetch(form.action, { method: "POST", mode: "no-cors", body: data })
        .then(function () {
          form.classList.add("is-sent");
          nameInput.readOnly = true;
          radios.forEach(function (r) { r.disabled = true; });
          sendBtn.disabled = true;
          openAsk(done);
        })
        .catch(function () { openAsk(fail); })
        .then(function () { sendBtn.classList.remove("is-busy"); });
    });
  }

  /* ---------- Обратный отсчёт ---------- */
  var target = new Date("2027-07-21T14:00:00+03:00").getTime();
  var WORDS = {
    days: ["день", "дня", "дней"],
    hours: ["час", "часа", "часов"],
    minutes: ["минута", "минуты", "минут"],
    seconds: ["секунда", "секунды", "секунд"]
  };
  function plural(n, f) {
    var n100 = n % 100, n10 = n % 10;
    if (n100 > 10 && n100 < 20) return f[2];
    if (n10 === 1) return f[0];
    if (n10 > 1 && n10 < 5) return f[1];
    return f[2];
  }
  function pad(n) { return n < 10 ? "0" + n : String(n); }

  if (cd) {
    var timer, started = false;
    var tickCd = function () {
      var diff = Math.max(0, target - Date.now());
      var s = Math.floor(diff / 1000);
      var v = { days: Math.floor(s / 86400), hours: Math.floor((s % 86400) / 3600), minutes: Math.floor((s % 3600) / 60), seconds: s % 60 };
      Object.keys(v).forEach(function (u) {
        var num = cd.querySelector('[data-unit="' + u + '"]');
        var text = u === "days" ? String(v[u]) : pad(v[u]);
        if (num.textContent !== text) {
          num.textContent = text;
          if (started && !reduceMotion && canAnimate) {
            num.animate(
              [{ transform: "translateY(-22%)", opacity: 0, filter: "blur(3px)" }, { transform: "none", opacity: 1, filter: "blur(0)" }],
              { duration: 420, easing: "cubic-bezier(.23,1,.32,1)" }
            );
          }
        }
        cd.querySelector('[data-label="' + u + '"]').textContent = plural(v[u], WORDS[u]);
      });
      started = true;
      if (diff === 0) clearInterval(timer);
    };
    tickCd();
    timer = setInterval(tickCd, 1000);
  }
})();
