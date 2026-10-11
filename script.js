/* =========================================================
   Свадебный сайт · анимации и логика
   ========================================================= */
(function () {
  "use strict";

  var root = document.documentElement;
  var body = document.body;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  root.classList.add("motion-ready");

  // Каждый раз начинаем с обложки
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  window.scrollTo(0, 0);

  function clamp(v, min, max) { return v < min ? min : v > max ? max : v; }
  function easeOut(t) { return 1 - Math.pow(1 - t, 4); }

  /* ---------- Прелоадер ---------- */
  var preloader = document.getElementById("preloader");
  var startedAt = Date.now();
  var preloaderDone = false;

  function hidePreloader() {
    if (preloaderDone || !preloader) return;
    preloaderDone = true;
    var wait = Math.max(0, 1200 - (Date.now() - startedAt));
    setTimeout(function () {
      preloader.classList.add("is-hidden");
      setTimeout(function () { preloader.remove(); }, 900);
    }, wait);
  }
  if (document.readyState === "complete") hidePreloader();
  else window.addEventListener("load", hidePreloader);
  setTimeout(hidePreloader, 4500); // если что-то грузится слишком долго

  /* ---------- Музыка ---------- */
  var audio = document.getElementById("bg-music");
  var musicBtn = document.getElementById("music");
  var opened = false;
  var hasAudio = false;

  function setPlaying(on) {
    musicBtn.classList.toggle("is-playing", on);
    musicBtn.setAttribute("aria-pressed", on ? "true" : "false");
  }
  function showMusicButton() {
    if (hasAudio && opened) musicBtn.hidden = false;
  }
  function playMusic() {
    var p = audio.play();
    if (p && p.then) {
      p.then(function () { hasAudio = true; setPlaying(true); showMusicButton(); })
       .catch(function () { /* файла нет или браузер запретил — просто без музыки */ });
    }
  }

  if (audio && musicBtn) {
    audio.volume = 0.4;
    audio.addEventListener("loadedmetadata", function () { hasAudio = true; showMusicButton(); });
    audio.addEventListener("pause", function () { setPlaying(false); });
    audio.addEventListener("play", function () { setPlaying(true); });
    musicBtn.addEventListener("click", function () {
      if (audio.paused) playMusic(); else audio.pause();
    });
  }

  /* ---------- Заставка-конверт ---------- */
  var intro = document.getElementById("intro");
  var openBtn = document.getElementById("intro-open");

  function openInvitation() {
    if (opened) return;
    opened = true;
    intro.classList.add("is-open");
    root.classList.remove("is-locked");
    body.classList.add("is-opened");
    if (audio) playMusic();
    showMusicButton();
    setTimeout(function () { intro.remove(); measure(); }, reduceMotion ? 50 : 2200);
  }

  if (intro && openBtn) {
    root.classList.add("is-locked");
    openBtn.addEventListener("click", openInvitation);
  } else {
    opened = true;
    body.classList.add("is-opened");
  }

  /* ---------- Движение при прокрутке ----------
     data-scrub="zoom"  — проявление с увеличением (0.9 → 1)
     data-scrub="title" — заголовок «наводится на резкость»: подъём + расфокус → чёткость
     data-scrub="left"  — выезд слева + увеличение
     data-scrub="right" — выезд справа + увеличение
     data-parallax="-90" — медленный сдвиг по вертикали (параллакс)
     data-kenburns      — фото медленно «отъезжает» по мере прокрутки  */
  var SCRUB = {
    zoom:  { x: 0,   y: 18, s: 0.9,  b: 0 },
    title: { x: 0,   y: 26, s: 0.94, b: 8 },
    left:  { x: -70, y: 0,  s: 0.9,  b: 0 },
    right: { x: 70,  y: 0,  s: 0.9,  b: 0 }
  };

  var scrubItems = [].map.call(document.querySelectorAll("[data-scrub]"), function (el) {
    return { el: el, cfg: SCRUB[el.getAttribute("data-scrub")] || SCRUB.zoom, top: 0, last: -1 };
  });
  var parallaxItems = [].map.call(document.querySelectorAll("[data-parallax]"), function (el) {
    return { el: el, amount: parseFloat(el.getAttribute("data-parallax")) || 0, top: 0, h: 0 };
  });
  var zoomItems = [].map.call(document.querySelectorAll("[data-kenburns]"), function (el) {
    return { el: el, box: el.parentNode, top: 0, h: 0 };
  });

  function docTop(el) {
    // у SVG-элементов нет offsetTop — считаем от ближайшего HTML-родителя
    while (el && el.offsetTop === undefined) el = el.parentNode;
    var y = 0;
    while (el) { y += el.offsetTop; el = el.offsetParent; }
    return y;
  }

  var vh = window.innerHeight;
  var maxScroll = 0;

  function measure() {
    vh = window.innerHeight;
    // высота страницы без учёта ещё не «всплывших» блоков (они временно сдвинуты вниз)
    maxScroll = Math.max(0, body.offsetHeight - vh);
    scrubItems.forEach(function (it) { it.top = docTop(it.el); it.last = -1; });
    parallaxItems.forEach(function (it) { it.top = docTop(it.el); it.h = it.el.offsetHeight; });
    zoomItems.forEach(function (it) { it.top = docTop(it.box); it.h = it.box.offsetHeight; });
    update();
  }

  function update() {
    var y = window.pageYOffset;
    var dist = Math.min(320, vh * 0.45);

    for (var i = 0; i < scrubItems.length; i++) {
      var it = scrubItems[i];
      var start = it.top - vh + 40;              // элемент показался снизу экрана
      var end = Math.min(start + dist, maxScroll); // у самого низа страницы — успеть до конца
      var p = reduceMotion || end <= start ? 1 : clamp((y - start) / (end - start), 0, 1);
      p = Math.round(easeOut(p) * 1000) / 1000;
      if (p === it.last) continue;
      it.last = p;
      var c = it.cfg, k = 1 - p;
      it.el.style.opacity = p;
      it.el.style.transform = p === 1 ? "none" :
        "translate3d(" + (c.x * k).toFixed(1) + "px," + (c.y * k).toFixed(1) + "px,0) scale(" + (c.s + (1 - c.s) * p).toFixed(3) + ")";
      if (c.b) it.el.style.filter = p > 0.98 ? "none" : "blur(" + (c.b * k).toFixed(2) + "px)";
    }

    if (!reduceMotion) {
      for (var j = 0; j < parallaxItems.length; j++) {
        var pi = parallaxItems[j];
        var q = clamp((y + vh - pi.top) / (vh + pi.h), 0, 1);
        pi.el.style.transform = "translate3d(0," + (pi.amount * q).toFixed(1) + "px,0)";
      }
      for (var z = 0; z < zoomItems.length; z++) {
        var zi = zoomItems[z];
        var r = clamp((y + vh - zi.top) / (vh + zi.h), 0, 1);
        zi.el.style.transform = "scale(" + (1.12 - 0.12 * r).toFixed(4) + ")";
      }
    }
  }

  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () { ticking = false; update(); });
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", function () { requestAnimationFrame(measure); });
  window.addEventListener("load", measure);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
  if ("ResizeObserver" in window) new ResizeObserver(function () { requestAnimationFrame(measure); }).observe(body);
  measure();

  /* ---------- Появление при попадании в кадр ---------- */
  var inviewEls = document.querySelectorAll("[data-inview], [data-aos]");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("is-inview");
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -120px 0px" });
    inviewEls.forEach(function (el) { io.observe(el); });
  } else {
    inviewEls.forEach(function (el) { el.classList.add("is-inview"); });
  }

  /* ---------- Фото: показываем, если файл добавлен ---------- */
  document.querySelectorAll("img[data-photo]").forEach(function (img) {
    function fail() {
      if (img.getAttribute("data-photo") === "hide") img.closest("figure").style.display = "none";
      else img.remove(); // остаётся красивый узор-заглушка
      measure();
    }
    if (img.complete && img.naturalWidth === 0) fail();
    else img.addEventListener("error", fail);
  });

  /* ---------- Обратный отсчёт ---------- */
  var target = new Date("2027-07-21T15:00:00+03:00").getTime();
  var cd = document.getElementById("countdown");
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
    var tick = function () {
      var diff = Math.max(0, target - Date.now());
      var s = Math.floor(diff / 1000);
      var v = {
        days: Math.floor(s / 86400),
        hours: Math.floor((s % 86400) / 3600),
        minutes: Math.floor((s % 3600) / 60),
        seconds: s % 60
      };
      Object.keys(v).forEach(function (u) {
        var num = cd.querySelector('[data-unit="' + u + '"]');
        var text = u === "days" ? String(v[u]) : pad(v[u]);
        if (num.textContent !== text) {
          num.textContent = text;
          // цифра мягко «выкатывается» сверху при каждом изменении
          if (!reduceMotion && num.animate && started) {
            num.animate(
              [{ transform: "translateY(-35%)", opacity: 0, filter: "blur(3px)" }, { transform: "none", opacity: 1, filter: "blur(0)" }],
              { duration: 520, easing: "cubic-bezier(.23,1,.32,1)" }
            );
          }
        }
        cd.querySelector('[data-label="' + u + '"]').textContent = plural(v[u], WORDS[u]);
      });
      started = true;
      if (diff === 0) clearInterval(timer);
    };
    tick();
    timer = setInterval(tick, 1000);
  }

  /* ---------- Всплывающее окно «Пожелания» ---------- */
  var lastFocus = null;

  function openPopup(popup) {
    lastFocus = document.activeElement;
    popup.hidden = false;
    root.classList.add("is-locked");
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { popup.classList.add("is-open"); });
    });
    var closeBtn = popup.querySelector(".popup__close");
    if (closeBtn) closeBtn.focus({ preventScroll: true });
  }
  function closePopup(popup) {
    popup.classList.remove("is-open");
    root.classList.remove("is-locked");
    setTimeout(function () { popup.hidden = true; }, reduceMotion ? 0 : 350);
    if (lastFocus) lastFocus.focus({ preventScroll: true });
  }

  document.querySelectorAll("[data-open]").forEach(function (btn) {
    var popup = document.getElementById(btn.getAttribute("data-open"));
    if (!popup) return;
    btn.addEventListener("click", function () { openPopup(popup); });
    popup.querySelectorAll("[data-close]").forEach(function (c) {
      c.addEventListener("click", function () { closePopup(popup); });
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    var open = document.querySelector(".popup.is-open");
    if (open) closePopup(open);
  });

  /* ---------- Подсказка, пока Google Форма не подключена ---------- */
  var frame = document.getElementById("google-form");
  if (frame && frame.getAttribute("src").indexOf("ВСТАВЬТЕ_ID_ФОРМЫ") !== -1) {
    var note = document.createElement("p");
    note.className = "form-placeholder";
    note.textContent = "Здесь появится анкета: вставьте ссылку на Google Форму в index.html (см. README).";
    frame.replaceWith(note);
  }
})();
