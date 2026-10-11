/* =========================================================
   Свадебный сайт · логика и анимации
   ========================================================= */
(function () {
  "use strict";

  var root = document.documentElement;
  var body = document.body;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if ("scrollRestoration" in history) history.scrollRestoration = "manual";

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

  /* ---------- Занавес: печать → занавес собирается к краям → обложка ---------- */
  var intro = document.getElementById("intro");
  var openBtn = document.getElementById("intro-open");
  var opened = false;

  function reveal() {
    root.classList.remove("is-locked");
    body.classList.add("is-opened");
  }
  function openInvitation() {
    if (opened) return;
    opened = true;
    playMusic();
    intro.classList.add("is-open");
    // обложка начинает проявляться, пока занавес ещё расходится
    setTimeout(reveal, reduceMotion ? 50 : 700);
    setTimeout(function () { intro.remove(); }, reduceMotion ? 700 : 2400);
  }

  if (intro && openBtn) {
    window.scrollTo(0, 0);
    root.classList.add("is-locked");
    var show = function () { requestAnimationFrame(function () { intro.classList.add("is-ready"); }); };
    var sealImg = openBtn.querySelector("img");
    if (sealImg && !sealImg.complete) {
      sealImg.addEventListener("load", show);
      sealImg.addEventListener("error", show);
      setTimeout(show, 2500);
    } else {
      show();
    }
    openBtn.addEventListener("click", openInvitation);
  } else {
    reveal();
  }

  /* ---------- Плавные появления при прокрутке ---------- */
  document.querySelectorAll(".col").forEach(function (col) {
    col.querySelectorAll("[data-reveal]").forEach(function (el, i) { el.style.setProperty("--i", i % 4); });
  });
  document.querySelectorAll(".cal > span").forEach(function (el, i) { el.style.setProperty("--i", i); });
  document.querySelectorAll(".prog li").forEach(function (el, i) { el.style.setProperty("--i", i); });
  document.querySelectorAll(".swatches li").forEach(function (el, i) { el.style.setProperty("--i", i); });

  var watched = document.querySelectorAll("[data-reveal], [data-inview]");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("is-in");
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.01 });
    watched.forEach(function (el) { io.observe(el); });
  } else {
    watched.forEach(function (el) { el.classList.add("is-in"); });
  }

  /* ---------- Анкета → Google Форма ---------- */
  var form = document.getElementById("rsvp-form");
  var done = document.getElementById("rsvp-done");
  var errBox = document.getElementById("rsvp-error");

  function showError(msg) {
    errBox.textContent = msg;
    errBox.hidden = false;
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
          form.hidden = true;
          done.hidden = false;
          done.focus({ preventScroll: true });
        })
        .catch(function () {
          btn.classList.remove("is-busy");
          showError("Не получилось отправить. Проверьте интернет и попробуйте ещё раз.");
        });
    });
  }

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
          if (started && !reduceMotion && num.animate) {
            num.animate(
              [{ transform: "translateY(-24%)", opacity: 0, filter: "blur(3px)" }, { transform: "none", opacity: 1, filter: "blur(0)" }],
              { duration: 420, easing: "cubic-bezier(.23,1,.32,1)" }
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
