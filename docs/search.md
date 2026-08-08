# Поиск по архиву

<div class="hz-search" markdown="0">
  <div class="hz-search__field">
    <span class="hz-i hz-i--search" aria-hidden="true"></span>
    <input id="hz-search-input" type="search" placeholder="Ключевые слова, например: llama.cpp квантизация" autocomplete="off">
  </div>
  <div id="hz-search-status" class="hz-search-status" hidden></div>
  <ol id="hz-search-results" class="hz-search-results"></ol>
</div>

<script>
(function () {
  "use strict";
  var input = document.getElementById("hz-search-input");
  var status = document.getElementById("hz-search-status");
  var results = document.getElementById("hz-search-results");
  var timer = null;

  function highlight(text, terms) {
    var safe = document.createElement("span");
    safe.textContent = text;
    var html = safe.innerHTML;
    terms.forEach(function (term) {
      if (!term) return;
      var re = new RegExp("(" + term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
      html = html.replace(re, "<mark>$1</mark>");
    });
    return html;
  }

  function showStatus(text) {
    status.textContent = text;
    status.hidden = !text;
  }

  function render(data, terms) {
    results.innerHTML = "";
    var hits = (data && data.hits) || [];
    if (!hits.length) {
      showStatus("Ничего не найдено.");
      return;
    }
    showStatus("Найдено: " + (data.total !== undefined ? data.total : hits.length));
    hits.forEach(function (hit) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      // The title opens our article page; the original source is a
      // secondary link in the meta line.
      a.href = hit.page || hit.url;
      a.className = "hz-item__title";
      a.innerHTML = highlight(hit.title || "(без названия)", terms);
      var meta = document.createElement("div");
      meta.className = "hz-item__meta";
      var bits = [];
      if (hit.date) bits.push(hit.date);
      if (hit.score !== undefined && hit.score !== null) bits.push("⭐️ " + hit.score + "/10");
      if (hit.profile) bits.push(hit.profile);
      meta.textContent = bits.join(" · ");
      if (hit.url) {
        var src = document.createElement("a");
        src.href = hit.url;
        src.textContent = "оригинал";
        src.className = "hz-search-source";
        meta.appendChild(document.createTextNode(" · "));
        meta.appendChild(src);
      }
      var snippet = document.createElement("div");
      snippet.className = "hz-search-snippet";
      snippet.innerHTML = highlight(hit.snippet || "", terms);
      li.appendChild(a);
      li.appendChild(meta);
      li.appendChild(snippet);
      results.appendChild(li);
    });
  }

  function runSearch() {
    var q = input.value.trim();
    results.innerHTML = "";
    if (q.length < 2) {
      showStatus("");
      return;
    }
    showStatus("Ищем…");
    fetch("/api/search?q=" + encodeURIComponent(q))
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) { render(data, q.split(/\s+/)); })
      .catch(function () {
        showStatus("Поиск недоступен. Попробуйте позже.");
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
