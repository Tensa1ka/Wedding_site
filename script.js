/* =========================================================
   Свадебный сайт · анимации и логика
   ========================================================= */
(function () {
  "use strict";

  var root = document.documentElement;
  var body = document.body;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  root.classList.add("motion-ready");
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  window.scrollTo(0, 0);

  /* ---------- Прелоадер → конверт ---------- */
  var preloader = document.getElementById("preloader");
  var intro = document.getElementById("intro");
  var startedAt = Date.now();
  var preloaderDone = false;

  function hidePreloader() {
    if (preloaderDone) return;
    preloaderDone = true;
    var wait = Math.max(0, 1400 - (Date.now() - startedAt));
    setTimeout(function () {
      if (preloader) {
        preloader.classList.add("is-hidden");
        setTimeout(function () { preloader.remove(); }, 1000);
      }
      // веточки на створках прорисовываются, печать «опускается» на бумагу
      if (intro) requestAnimationFrame(function () { intro.classList.add("is-ready"); });
    }, wait);
  }
  if (document.readyState === "complete") hidePreloader();
  else window.addEventListener("load", hidePreloader);
  setTimeout(hidePreloader, 4500);

  /* ---------- Музыка ---------- */
  var audio = document.getElementById("bg-music");
  var musicBtn = document.getElementById("music");
  var opened = false;
  var hasAudio = false;

  function setPlaying(on) {
    musicBtn.classList.toggle("is-playing", on);
    musicBtn.setAttribute("aria-pressed", on ? "true" : "false");
  }
  function showMusicButton() { if (hasAudio && opened) musicBtn.hidden = false; }
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
    musicBtn.addEventListener("click", function () { if (audio.paused) playMusic(); else audio.pause(); });
  }

  /* ---------- Открытие конверта: печать целиком приподнимается, створки распахиваются ---------- */
  var openBtn = document.getElementById("intro-open");

  function openInvitation() {
    if (opened) return;
    opened = true;
    if (audio) playMusic();
    showMusicButton();
    if (reduceMotion) {
      intro.classList.add("is-open");
      finishOpening();
      return;
    }
    intro.classList.add("is-lifting");
    setTimeout(function () {
      intro.classList.add("is-open");
      root.classList.remove("is-locked");
      setTimeout(function () { body.classList.add("is-opened"); }, 350);
    }, 420);
    setTimeout(function () { intro.remove(); measure(); }, 2700);
  }
  function finishOpening() {
    root.classList.remove("is-locked");
    body.classList.add("is-opened");
    setTimeout(function () { intro.remove(); measure(); }, 60);
  }

  if (intro && openBtn) {
    root.classList.add("is-locked");
    openBtn.addEventListener("click", openInvitation);
  } else {
    opened = true;
    body.classList.add("is-opened");
  }

  /* ---------- Плавные появления при прокрутке ----------
     data-reveal        — текст: подъём + расфокус → чёткость
     data-reveal="rise" — панели и рамки: мягкий подъём с лёгким увеличением
     data-inview        — блоки со своей хореографией (календарь, программа, палитра, цветы)
     Элементы внутри одного блока появляются каскадом.                                     */
  function indexChildren(selector, childSelector) {
    document.querySelectorAll(selector).forEach(function (box) {
      box.querySelectorAll(childSelector).forEach(function (el, i) { el.style.setProperty("--i", i); });
    });
  }
  // каскад для текстов внутри общего контейнера
  document.querySelectorAll(".sec, .finale, .hero").forEach(function (sec) {
    var i = 0;
    sec.querySelectorAll('[data-reveal]:not([data-reveal="rise"])').forEach(function (el) { el.style.setProperty("--i", i++); });
  });
  indexChildren(".cal", ":scope > span");
  indexChildren(".palette", "li");

  var revealEls = document.querySelectorAll("[data-reveal], [data-inview]");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("is-in");
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.01 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("is-in"); });
  }

  /* ---------- Параллакс: зелень и драпировка ---------- */
  var parallaxItems = [].map.call(document.querySelectorAll("[data-parallax]"), function (el) {
    return { el: el, amount: parseFloat(el.getAttribute("data-parallax")) || 0, top: 0, h: 0 };
  });
  var drapeLayers = document.querySelectorAll(".drape__a, .drape__b");
  var vh = window.innerHeight;

  function docTop(el) {
    while (el && el.offsetTop === undefined) el = el.parentNode;
    var y = 0;
    while (el) { y += el.offsetTop; el = el.offsetParent; }
    return y;
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }

  function measure() {
    vh = window.innerHeight;
    parallaxItems.forEach(function (it) { it.top = docTop(it.el); it.h = it.el.offsetHeight; });
    update();
  }
  function update() {
    if (reduceMotion) return;
    var y = window.pageYOffset;
    for (var i = 0; i < parallaxItems.length; i++) {
      var it = parallaxItems[i];
      var q = clamp((y + vh - it.top) / (vh + it.h), 0, 1);
      it.el.style.transform = "translate3d(0," + (it.amount * q).toFixed(1) + "px,0)";
    }
    // драпировка едва заметно смещается — ощущение глубины
    for (var d = 0; d < drapeLayers.length; d++) {
      drapeLayers[d].style.translate = "0 " + (-(y * (d ? 0.035 : 0.02)) % 60).toFixed(1) + "px";
    }
  }
  var ticking = false;
  window.addEventListener("scroll", function () {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () { ticking = false; update(); });
  }, { passive: true });
  window.addEventListener("resize", function () { requestAnimationFrame(measure); });
  window.addEventListener("load", measure);
  measure();

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
      var v = { days: Math.floor(s / 86400), hours: Math.floor((s % 86400) / 3600), minutes: Math.floor((s % 3600) / 60), seconds: s % 60 };
      Object.keys(v).forEach(function (u) {
        var num = cd.querySelector('[data-unit="' + u + '"]');
        var text = u === "days" ? String(v[u]) : pad(v[u]);
        if (num.textContent !== text) {
          num.textContent = text;
          // цифра мягко «выкатывается» при каждом изменении
          if (!reduceMotion && num.animate && started) {
            num.animate(
              [{ transform: "translateY(-30%)", opacity: 0, filter: "blur(3px)" }, { transform: "none", opacity: 1, filter: "blur(0)" }],
              { duration: 560, easing: "cubic-bezier(.23,1,.32,1)" }
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
    requestAnimationFrame(function () { requestAnimationFrame(function () { popup.classList.add("is-open"); }); });
    var closeBtn = popup.querySelector(".popup__close");
    if (closeBtn) closeBtn.focus({ preventScroll: true });
  }
  function closePopup(popup) {
    popup.classList.remove("is-open");
    root.classList.remove("is-locked");
    setTimeout(function () { popup.hidden = true; }, reduceMotion ? 0 : 240);
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
