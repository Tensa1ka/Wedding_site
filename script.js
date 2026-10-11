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
    var wait = Math.max(0, 1200 - (Date.now() - startedAt));
    setTimeout(function () {
      if (preloader) {
        preloader.classList.add("is-hidden");
        setTimeout(function () { preloader.remove(); }, 900);
      }
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
       .catch(function () { /* файла нет или браузер запретил — без музыки */ });
    }
  }
  if (audio && musicBtn) {
    audio.volume = 0.4;
    audio.addEventListener("loadedmetadata", function () { hasAudio = true; showMusicButton(); });
    audio.addEventListener("pause", function () { setPlaying(false); });
    audio.addEventListener("play", function () { setPlaying(true); });
    musicBtn.addEventListener("click", function () { if (audio.paused) playMusic(); else audio.pause(); });
  }

  /* ---------- Открытие конверта ----------
     антуриум приподнимается → клапан раскрывается → карточка выезжает →
     конверт растворяется, и появляется обложка                          */
  var openBtn = document.getElementById("intro-open");

  function openInvitation() {
    if (opened) return;
    opened = true;
    if (audio) playMusic();
    showMusicButton();

    if (reduceMotion) {
      intro.classList.add("is-leaving");
      finish(60);
      return;
    }
    var steps = [
      [0, "is-opening"],
      [780, "is-flapped"],
      [900, "is-card"],
      [2300, "is-leaving"]
    ];
    steps.forEach(function (s) { setTimeout(function () { intro.classList.add(s[1]); }, s[0]); });
    setTimeout(function () {
      root.classList.remove("is-locked");
      body.classList.add("is-opened");
    }, 2350);
    setTimeout(function () { intro.remove(); measure(); }, 3500);
  }
  function finish(delay) {
    root.classList.remove("is-locked");
    body.classList.add("is-opened");
    setTimeout(function () { intro.remove(); measure(); }, delay);
  }

  if (intro && openBtn) {
    root.classList.add("is-locked");
    openBtn.addEventListener("click", openInvitation);
  } else {
    opened = true;
    body.classList.add("is-opened");
  }

  /* ---------- Плавные появления при прокрутке ----------
     data-reveal       — выезд слева с проявлением из расфокуса
     data-reveal="up"  — карточки поднимаются снизу
     data-inview       — блоки со своей хореографией (календарь, программа, палитра)
     data-bloom        — цветы «распускаются»                                   */
  document.querySelectorAll(".sec, .finale").forEach(function (sec) {
    var i = 0;
    sec.querySelectorAll("[data-reveal]").forEach(function (el) { el.style.setProperty("--i", i++); });
  });
  document.querySelectorAll(".cal").forEach(function (cal) {
    cal.querySelectorAll(":scope > span").forEach(function (el, i) { el.style.setProperty("--i", i); });
  });
  document.querySelectorAll(".palette").forEach(function (p) {
    p.querySelectorAll("li").forEach(function (el, i) { el.style.setProperty("--i", i); });
  });

  var watched = document.querySelectorAll("[data-reveal], [data-inview], [data-bloom]");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("is-in");
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.01 });
    watched.forEach(function (el) { io.observe(el); });
  } else {
    watched.forEach(function (el) { el.classList.add("is-in"); });
  }

  /* ---------- Параллакс цветов на обложке ---------- */
  var parallaxItems = [].map.call(document.querySelectorAll("[data-parallax]"), function (el) {
    return { el: el, amount: parseFloat(el.getAttribute("data-parallax")) || 0, top: 0, h: 0 };
  });
  var vh = window.innerHeight;

  function docTop(el) {
    var y = 0;
    while (el) { y += el.offsetTop; el = el.offsetParent; }
    return y;
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function measure() {
    vh = window.innerHeight;
    parallaxItems.forEach(function (it) { it.top = docTop(it.el.parentNode); it.h = it.el.parentNode.offsetHeight; });
    update();
  }
  function update() {
    if (reduceMotion) return;
    var y = window.pageYOffset;
    for (var i = 0; i < parallaxItems.length; i++) {
      var it = parallaxItems[i];
      var q = clamp((y - it.top) / Math.max(1, it.h), 0, 1);
      it.el.style.transform = "translate3d(0," + (it.amount * q).toFixed(1) + "px,0)";
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
})();
