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

  /* ---------- Разбивка текста на буквы (для волн появления) ---------- */
  function splitLetters(el) {
    var text = el.textContent;
    el.setAttribute("aria-label", text);
    el.textContent = "";
    Array.prototype.forEach.call(text, function (ch, i) {
      var s = document.createElement("span");
      s.textContent = ch;
      s.setAttribute("aria-hidden", "true");
      s.style.setProperty("--i", i);
      el.appendChild(s);
    });
  }
  document.querySelectorAll("[data-letters]").forEach(splitLetters);

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
     Лицо открытки: конверт на весь экран (около 5 секунд)
     Печать остаётся на клапане целой; клапан откидывается на петле у верхнего края,
     части конверта не расходятся – затем весь конверт плавно уезжает вниз.
     ========================================================= */
  var intro = document.getElementById("intro");
  var openBtn = document.getElementById("intro-open");
  var envelope = intro && intro.querySelector(".envelope");
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

    var card = intro.querySelector(".env__card");
    var flap = intro.querySelector(".env__flap");

    // 0–0,45 с: печать отзывается на нажатие
    openBtn.animate(
      [{ transform: "scale(1)" }, { transform: "scale(.94)", offset: .35 }, { transform: "scale(1.02)", offset: .7 }, { transform: "scale(1)" }],
      { duration: 450, easing: "cubic-bezier(.23,1,.32,1)" }
    );
    // 0,45–3 с: клапан вместе с печатью откидывается вверх на петле
    flap.animate(
      [{ transform: "rotateX(0deg)" }, { transform: "rotateX(-12deg)", offset: .14 }, { transform: "rotateX(-180deg)" }],
      { duration: 2550, delay: 450, easing: "cubic-bezier(.42,0,.22,1)", fill: "forwards" }
    );
    // тень под клапаном ослабевает, по мере того как он поднимается
    card.animate(
      [{ filter: "brightness(1)" }, { filter: "brightness(1.04)" }],
      { duration: 2400, delay: 600, easing: "ease-in-out", fill: "forwards" }
    );
    // 3–5 с: конверт целиком уезжает вниз, открывая обложку
    envelope.animate(
      [{ transform: "translateY(0)" }, { transform: "translateY(108%)" }],
      { duration: 1900, delay: 3100, easing: "cubic-bezier(.65,0,.35,1)", fill: "forwards" }
    );
    intro.animate(
      [{ backgroundColor: "rgba(239,228,211,1)" }, { backgroundColor: "rgba(239,228,211,0)" }],
      { duration: 1500, delay: 3200, easing: "ease-out", fill: "forwards" }
    );

    setTimeout(reveal, 3350);
    setTimeout(function () { intro.remove(); }, 5100);
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
    envelope.addEventListener("click", openInvitation);   // нажатие в любом месте конверта
  } else {
    reveal();
  }

  /* ---------- Световая пыль на обложке ---------- */
  var dust = document.querySelector(".dust");
  if (dust && !reduceMotion) {
    for (var d = 0; d < 18; d++) {
      var p = document.createElement("i");
      var dur = 10 + Math.random() * 9;
      p.style.left = (6 + Math.random() * 88) + "%";
      p.style.setProperty("--s", (2 + Math.random() * 4).toFixed(1) + "px");
      p.style.setProperty("--d", dur.toFixed(1) + "s");
      p.style.setProperty("--delay", (-Math.random() * dur).toFixed(1) + "s");
      p.style.setProperty("--x", ((Math.random() - .5) * 80).toFixed(0) + "px");
      dust.appendChild(p);
    }
  }

  /* ---------- Появления при прокрутке ---------- */
  document.querySelectorAll(".col").forEach(function (col) {
    col.querySelectorAll("[data-reveal]").forEach(function (el, i) { el.style.setProperty("--i", i % 4); });
  });
  document.querySelectorAll(".cal > span").forEach(function (el, i) { el.style.setProperty("--i", i); });
  document.querySelectorAll(".prog li").forEach(function (el, i) { el.style.setProperty("--i", i); });
  document.querySelectorAll(".swatches li").forEach(function (el, i) { el.style.setProperty("--i", i); });

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

  /* ---------- Анкета → Google Форма ---------- */
  var form = document.getElementById("rsvp-form");
  var done = document.getElementById("rsvp-done");
  var errBox = document.getElementById("rsvp-error");
  function showError(msg) {
    errBox.textContent = msg;
    errBox.hidden = false;
    if (canAnimate && !reduceMotion) {
      errBox.animate([{ transform: "translateX(-6px)" }, { transform: "translateX(5px)" }, { transform: "translateX(-3px)" }, { transform: "none" }],
        { duration: 320, easing: "ease-out" });
    }
  }
  if (form && window.fetch) {
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      errBox.hidden = true;
      var name = form.elements["entry.225506798"];
      var answer = form.querySelector('input[name="entry.87327526"]:checked');
      if (!name.value.trim()) { showError("Пожалуйста, напишите имя и фамилию."); name.focus(); return; }
      if (!answer) { showError("Пожалуйста, выберите вариант ответа."); return; }

      var btn = form.querySelector(".btn");
      btn.classList.add("is-busy");
      var data = new URLSearchParams();
      data.append("entry.225506798", name.value.trim());
      data.append("entry.87327526", answer.value);

      // Google Формы не отвечают на CORS-запросы, поэтому ответ «непрозрачный»:
      // успешная отправка = запрос дошёл без сетевой ошибки
      fetch(form.action, { method: "POST", mode: "no-cors", body: data })
        .then(function () {
          var swap = function () {
            form.hidden = true;
            done.hidden = false;
            done.focus({ preventScroll: true });
            if (canAnimate && !reduceMotion) {
              done.animate([{ opacity: 0, transform: "translateY(12px)", filter: "blur(4px)" }, { opacity: 1, transform: "none", filter: "blur(0)" }],
                { duration: 700, easing: "cubic-bezier(.23,1,.32,1)" });
            }
          };
          if (canAnimate && !reduceMotion) {
            form.animate([{ opacity: 1, filter: "blur(0)" }, { opacity: 0, filter: "blur(4px)" }], { duration: 260, easing: "ease-out", fill: "forwards" }).onfinish = swap;
          } else {
            swap();
          }
        })
        .catch(function () {
          btn.classList.remove("is-busy");
          showError("Не получилось отправить. Проверьте интернет и попробуйте ещё раз.");
        });
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
