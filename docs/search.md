# Поиск по архиву

<div class="hz-search" markdown="0">
  <div class="hz-search__field">
    <span class="hz-i hz-i--search" aria-hidden="true"></span>
    <input id="hz-search-input" type="search" placeholder="Заголовок, источник, тема" autocomplete="off" aria-label="Поиск по архиву">
  </div>
  <p id="hz-search-status" class="hz-search-status" hidden></p>
  <div id="hz-search-empty" hidden></div>
  <ul id="hz-search-results" class="hz-search-results"></ul>
</div>

<script>
(function () {
  "use strict";
  var input = document.getElementById("hz-search-input");
  var status = document.getElementById("hz-search-status");
  var empty = document.getElementById("hz-search-empty");
  var results = document.getElementById("hz-search-results");
  var timer = null;

  // The API marks matches with U+0001/U+0002 rather than with tags. Escape
  // first — this is model output over scraped content and must never reach
  // innerHTML as markup — then turn the surviving sentinels into <mark>.
  // Doing it this way means the highlighting comes from the Elasticsearch
  // analyser, which knows Russian morphology; matching terms here with a
  // regex missed every inflected form.
  function highlight(text) {
    var safe = document.createElement("span");
    safe.textContent = text || "";
    return safe.innerHTML
      .split("\u0001").join("<mark>")
      .split("\u0002").join("</mark>");
  }

  function showStatus(text) {
    status.textContent = text;
    status.hidden = !text;
  }

  // Empty states are not centred and carry no illustration: same alignment as
  // the rest of the text, one sentence of fact and one thing to do.
  function showEmpty(head, body) {
    if (!head) {
      empty.hidden = true;
      empty.innerHTML = "";
      return;
    }
    empty.innerHTML =
      '<div class="hz-empty">' +
      '<span class="hz-i hz-i--none" aria-hidden="true"></span>' +
      '<div class="hz-empty__head"></div>' +
      '<div class="hz-empty__body"></div>' +
      "</div>";
    empty.querySelector(".hz-empty__head").textContent = head;
    empty.querySelector(".hz-empty__body").innerHTML = body;
    empty.hidden = false;
  }

  // Mirrors _score_tier / _score_markup in src/ai/summarizer.py — that is the
  // source of truth for both thresholds and the 4..10 normalisation.
  function scoreElement(score) {
    var value = parseFloat(score);
    var span = document.createElement("span");
    span.className = "hz-score";
    if (isNaN(value)) {
      span.textContent = "?";
      return span;
    }
    span.dataset.tier = value >= 8.0 ? "high" : value >= 6.0 ? "mid" : "low";
    span.style.setProperty(
      "--hz-score",
      Math.min(Math.max((value - 4.0) / 6.0, 0.04), 1.0).toFixed(2)
    );
    span.textContent = value.toFixed(1);
    return span;
  }

  function render(data) {
    results.innerHTML = "";
    var hits = (data && data.hits) || [];
    if (!hits.length) {
      showStatus("");
      showEmpty(
        "Ничего не найдено",
        'Попробуйте другое слово или откройте <a href="/digest/">архив выпусков</a>.'
      );
      return;
    }
    showEmpty("");
    showStatus("Найдено: " + (data.total !== undefined ? data.total : hits.length));
    hits.forEach(function (hit) {
      var li = document.createElement("li");
      var item = document.createElement("div");
      item.className = "hz-item";

      // The title opens our article page; the original source is a secondary
      // link in the meta line.
      var a = document.createElement("a");
      a.className = "hz-item__title";
      a.href = hit.page || hit.url;
      a.innerHTML = highlight(hit.title || "(без названия)");
      item.appendChild(a);

      if (hit.score !== undefined && hit.score !== null) {
        var score = scoreElement(hit.score);
        item.appendChild(score);
        li.dataset.tier = score.dataset.tier || "";
      }

      var meta = document.createElement("div");
      meta.className = "hz-item__meta";
      var bits = [];
      if (hit.date) bits.push(hit.date);
      if (hit.profile) bits.push(hit.profile);
      meta.textContent = bits.join(" · ");
      if (hit.url) {
        var src = document.createElement("a");
        src.href = hit.url;
        src.className = "hz-source";
        src.textContent = (hit.url.split("/")[2] || "оригинал").replace(/^www\./, "");
        meta.appendChild(document.createTextNode(" "));
        meta.appendChild(src);
      }
      item.appendChild(meta);

      var snippet = document.createElement("p");
      snippet.className = "hz-search-snippet";
      snippet.innerHTML = highlight(hit.snippet || "");
      item.appendChild(snippet);

      li.appendChild(item);
      results.appendChild(li);
    });
  }

  function runSearch() {
    var q = input.value.trim();
    results.innerHTML = "";
    if (q.length < 2) {
      showStatus("");
      showEmpty("");
      return;
    }
    showStatus("Ищем…");
    fetch("/api/search?q=" + encodeURIComponent(q))
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) { render(data); })
      .catch(function () {
        showStatus("");
        showEmpty(
          "Поиск недоступен",
          'Индекс сейчас не отвечает. Выпуски открываются напрямую из <a href="/digest/">архива</a>.'
        );
      });
  }

  input.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(runSearch, 350);
  });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      clearTimeout(timer);
      runSearch();
    }
  });

  // ?q= из адреса — чтобы ссылки на поиск работали
  var preset = new URLSearchParams(location.search).get("q");
  if (preset) {
    input.value = preset;
    runSearch();
  }
})();
</script>
