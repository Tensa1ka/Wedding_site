// Обратный отсчёт до 21 июля 2027, 15:00 по Москве
(function () {
  var target = new Date("2027-07-21T15:00:00+03:00").getTime();
  var root = document.getElementById("countdown");
  if (!root) return;
  var el = {};
  ["days", "hours", "minutes", "seconds"].forEach(function (u) {
    el[u] = root.querySelector('[data-unit="' + u + '"]');
  });

  function tick() {
    var diff = Math.max(0, target - Date.now());
    var s = Math.floor(diff / 1000);
    el.days.textContent = Math.floor(s / 86400);
    el.hours.textContent = Math.floor((s % 86400) / 3600);
    el.minutes.textContent = Math.floor((s % 3600) / 60);
    el.seconds.textContent = s % 60;
    if (diff === 0) clearInterval(timer);
  }
  tick();
  var timer = setInterval(tick, 1000);
})();

// Плавное появление блоков при прокрутке
(function () {
  var items = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) {
    items.forEach(function (n) { n.classList.add("is-visible"); });
    return;
  }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        e.target.classList.add("is-visible");
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.15 });
  items.forEach(function (n) { io.observe(n); });
})();

// Подсказка, пока ссылка на Google Форму не вставлена
(function () {
  var frame = document.getElementById("google-form");
  if (!frame || frame.getAttribute("src").indexOf("ВСТАВЬТЕ_ID_ФОРМЫ") === -1) return;
  var note = document.createElement("p");
  note.className = "form-placeholder";
  note.textContent = "Здесь появится анкета: вставьте ссылку на Google Форму в index.html (см. README).";
  frame.replaceWith(note);
})();
