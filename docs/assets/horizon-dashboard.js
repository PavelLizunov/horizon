/* Progressive dashboard and article history. No service, CDN, or model calls. */
(function () {
  "use strict";
  var KEY = "hz-dashboard-v1",
    BATCH = 24,
    active = null;
  var state = { saved: [], recent: [] },
    storageOK = true;
  var coverKeys = [
    "chip",
    "orbit",
    "server",
    "network",
    "wave",
    "finance",
    "video",
    "community",
  ];
  function safePage(p) {
    return (
      typeof p === "string" &&
      /^digest\/\d{4}-\d{2}-\d{2}-ru\/[a-zA-Z0-9_-]+-\d+\/$/.test(p)
    );
  }
  function valid(x) {
    return (
      x &&
      typeof x.id === "string" &&
      safePage(x.page) &&
      x.id === x.page.split("/")[1] + "-" + x.page.split("/")[2] &&
      typeof x.title === "string" &&
      typeof x.teaser === "string" &&
      Array.isArray(x.tags) &&
      x.tags.every(function (t) {
        return typeof t === "string";
      }) &&
      Number.isInteger(x.cover_seed) &&
      x.cover_seed >= 0 &&
      x.cover_seed < 4 &&
      Number.isInteger(x.reading_minutes) &&
      x.reading_minutes > 0 &&
      typeof x.audio_ready === "boolean" &&
      /^\d{4}-\d{2}-\d{2}$/.test(x.date) &&
      typeof x.profile_id === "string" &&
      typeof x.profile_name === "string" &&
      (x.score === null ||
        (typeof x.score === "number" &&
          isFinite(x.score) &&
          x.score >= 0 &&
          x.score <= 10)) &&
      coverKeys.indexOf(x.cover_key) >= 0
    );
  }
  function snapshot(x) {
    return { id: x.id, page: x.page, title: x.title, date: x.date };
  }
  var stateLoaded = false;
  function loadState(force) {
    if (stateLoaded && !force) return;
    stateLoaded = true;
    try {
      var x = JSON.parse(localStorage.getItem(KEY) || "{}");
      ["saved", "recent"].forEach(function (k) {
        state[k] = Array.isArray(x[k])
          ? x[k]
              .filter(function (s) {
                return (
                  s &&
                  typeof s.id === "string" &&
                  safePage(s.page) &&
                  typeof s.title === "string"
                );
              })
              .slice(0, k === "saved" ? 500 : 100)
          : [];
      });
    } catch (_) {
      state = { saved: [], recent: [] };
      storageOK = false;
    }
  }
  function persist() {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch (_) {
      storageOK = false;
    }
    syncButtons();
  }
  function hasSaved(id) {
    return state.saved.some(function (x) {
      return x.id === id;
    });
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[c];
    });
  }
  function baseURL() {
    var config = document.querySelector("#__config");
    try {
      return new URL(JSON.parse(config.textContent).base + "/", location.href);
    } catch (_) {
      return new URL("./", location.href);
    }
  }
  function syncButtons() {
    document.querySelectorAll("[data-save]").forEach(function (button) {
      var saved = hasSaved(button.dataset.save);
      var home = button.closest(".hd-dashboard");
      button.hidden = !!(home && !home.dataset.catalogReady);
      button.setAttribute("aria-pressed", String(saved));
      var title =
        button.dataset.title || button.getAttribute("aria-label") || "";
      button.textContent = button.classList.contains("hd-save-article")
        ? saved
          ? "✓ В отложенном"
          : "Отложить на потом"
        : saved
          ? "✓"
          : "+";
      if (!button.classList.contains("hd-save-article")) {
        if (!button.dataset.title)
          button.dataset.title = title.replace(
            /^(Отложить: |Убрать из отложенного: )/,
            "",
          );
        button.setAttribute(
          "aria-label",
          (saved ? "Убрать из отложенного: " : "Отложить: ") +
            button.dataset.title,
        );
      }
    });
    document.querySelectorAll("[data-storage-note]").forEach(function (n) {
      n.textContent = storageOK
        ? ""
        : "Сохранение недоступно; изменения только до закрытия страницы.";
    });
    document.querySelectorAll("[data-saved-count]").forEach(function (n) {
      n.textContent = state.saved.length;
    });
  }
  function toggle(x) {
    if (hasSaved(x.id))
      state.saved = state.saved.filter(function (s) {
        return s.id !== x.id;
      });
    else {
      state.saved.unshift(snapshot(x));
      state.saved = state.saved.slice(0, 500);
    }
    persist();
  }
  function initializeArticle() {
    var node = document.querySelector(".hd-article-data");
    if (!node) return;
    var item;
    try {
      item = JSON.parse(node.textContent);
    } catch (_) {
      return;
    }
    if (!valid(item)) return;
    if (!node.dataset.recorded) {
      node.dataset.recorded = "1";
      state.recent = [snapshot(item)]
        .concat(
          state.recent.filter(function (x) {
            return x.id !== item.id;
          }),
        )
        .slice(0, 100);
      persist();
    }
    var button = document.querySelector(".hd-article-tools [data-save]");
    if (button && !button.dataset.bound) {
      button.dataset.bound = "1";
      button.addEventListener("click", function () {
        toggle(item);
      });
    }
    syncButtons();
  }
  function card(x, lead, base, recentView) {
    var score =
      x.score === null
        ? "<small>без оценки</small>"
        : x.score.toFixed(1) + "<small> / 10</small>";
    return (
      '<article class="hd-story ' +
      (lead ? "hd-lead" : "") +
      '" data-id="' +
      esc(x.id) +
      '" data-score="' +
      esc(x.score) +
      '"><div class="hd-cover" data-cover="' +
      x.cover_key +
      '" data-seed="' +
      (Number(x.cover_seed) % 4 || 0) +
      '" aria-hidden="true"><img src="' +
      esc(new URL("assets/dashboard/" + x.cover_key + ".svg", base).href) +
      '" alt="" width="640" height="420"><span>ИЛЛЮСТРАЦИЯ</span></div><div class="hd-story-body"><div class="hd-story-top"><span>' +
      esc(x.profile_name) +
      '</span><span class="hd-score">' +
      score +
      '</span></div><h3><a href="' +
      esc(new URL(x.page, base).href) +
      '">' +
      esc(x.title) +
      "</a></h3><p>" +
      esc(x.teaser) +
      '</p><div class="hd-story-bottom"><span>' +
      esc(x.date) +
      " · ≈" +
      (Number(x.reading_minutes) || 1) +
      " мин" +
      (x.audio_ready ? ' · <span class="hd-audio">Аудио</span>' : "") +
      "</span>" +
      (recentView
        ? '<button class="hd-remove-recent" data-remove="' +
          esc(x.id) +
          '" aria-label="Убрать из истории: ' +
          esc(x.title) +
          '">×</button>'
        : "") +
      '<button class="hd-save" data-save="' +
      esc(x.id) +
      '" aria-label="Отложить: ' +
      esc(x.title) +
      '" aria-pressed="false">+</button></div></div></article>'
    );
  }
  function initializeHome(root) {
    if (root.dataset.bound) return;
    root.dataset.bound = "1";
    var base = baseURL(),
      items = [],
      byID = {},
      focusIDs = [],
      ready = false,
      abort = new AbortController();
    var ui = {
        view: "news",
        topic: "all",
        period: "all",
        sort: "newest",
        q: "",
      },
      limit = BATCH;
    var input = root.querySelector("input"),
      period = root.querySelector("select"),
      feed = root.querySelector(".hd-feed-grid"),
      hero = root.querySelector(".hd-focus"),
      empty = root.querySelector(".hd-empty"),
      more = root.querySelector(".hd-more"),
      status = root.querySelector(".hd-status"),
      error = root.querySelector(".hd-error");
    function fromURL() {
      var p = new URLSearchParams(location.search);
      ui.view =
        ["saved", "recent"].indexOf(p.get("view")) >= 0
          ? p.get("view")
          : "news";
      ui.topic = p.get("topic") || "all";
      ui.period =
        ["7", "30"].indexOf(p.get("period")) >= 0 ? p.get("period") : "all";
      ui.sort = p.get("sort") === "score" ? "score" : "newest";
      ui.q = (p.get("q") || "").slice(0, 200);
      input.value = ui.q;
      period.value = ui.period;
      limit = BATCH;
    }
    function writeURL(push) {
      var u = new URL(location.href);
      ["view", "topic", "period", "sort", "q"].forEach(function (k) {
        var def = {
          view: "news",
          topic: "all",
          period: "all",
          sort: "newest",
          q: "",
        }[k];
        if (ui[k] !== def) u.searchParams.set(k, ui[k]);
        else u.searchParams.delete(k);
      });
      if (u.href === location.href) return;
      if (push) history.pushState(null, "", u);
      else history.replaceState(null, "", u);
    }
    function recentSidebar() {
      var n = root.querySelector("[data-recent-list]");
      var list = state.recent
        .map(function (s) {
          return byID[s.id];
        })
        .filter(Boolean)
        .slice(0, 3);
      n.innerHTML = list.length
        ? list
            .map(function (x) {
              return (
                '<a href="' +
                esc(new URL(x.page, base).href) +
                '">' +
                esc(x.title) +
                " ↗</a>"
              );
            })
            .join("")
        : "<p>Открытые материалы появятся здесь. Не нужно запоминать выпуск или дату.</p>";
    }
    function render() {
      if (!ready) return;
      var focusedButton = document.activeElement;
      var savedFocus =
        focusedButton && root.contains(focusedButton)
          ? focusedButton.dataset.save
          : null;
      var q = ui.q.trim().toLocaleLowerCase("ru-RU"),
        latest = items.reduce(function (m, x) {
          return x.date > m ? x.date : m;
        }, "");
      var latestMS = Date.parse(latest + "T12:00:00Z");
      var list = items.filter(function (x) {
        return (
          (ui.view === "news" ||
            state[ui.view === "saved" ? "saved" : "recent"].some(function (s) {
              return s.id === x.id;
            })) &&
          (ui.topic === "all" || x.profile_id === ui.topic) &&
          (ui.period === "all" ||
            (latestMS - Date.parse(x.date + "T12:00:00Z")) / 86400000 <
              Number(ui.period)) &&
          (!q ||
            [
              x.title,
              x.teaser,
              x.profile_name,
              x.source_label,
              (x.tags || []).join(" "),
            ]
              .join(" ")
              .toLocaleLowerCase("ru-RU")
              .indexOf(q) >= 0)
        );
      });
      list.sort(function (a, b) {
        if (ui.view === "recent")
          return (
            state.recent.findIndex(function (s) {
              return s.id === a.id;
            }) -
            state.recent.findIndex(function (s) {
              return s.id === b.id;
            })
          );
        if (ui.sort === "score")
          return (
            (b.score === null ? -1 : b.score) -
              (a.score === null ? -1 : a.score) ||
            b.date.localeCompare(a.date) ||
            a.id.localeCompare(b.id)
          );
        return (
          b.date.localeCompare(a.date) ||
          (b.score === null ? -1 : b.score) -
            (a.score === null ? -1 : a.score) ||
          a.id.localeCompare(b.id)
        );
      });
      var focused =
        ui.view === "news" &&
        ui.topic === "all" &&
        ui.period === "all" &&
        ui.sort === "newest" &&
        !q;
      hero.hidden = !focused || !focusIDs.length;
      if (focused) {
        root.querySelector(".hd-hero-grid").innerHTML = focusIDs
          .map(function (id, i) {
            return card(byID[id], i === 0, base);
          })
          .join("");
        list = list.filter(function (x) {
          return focusIDs.indexOf(x.id) < 0;
        });
      }
      feed.innerHTML = list
        .slice(0, limit)
        .map(function (x) {
          return card(x, false, base, ui.view === "recent");
        })
        .join("");
      more.hidden = list.length <= limit;
      more.textContent =
        "Показать ещё (" + Math.min(BATCH, list.length - limit) + ")";
      root.querySelector("[data-feed-title]").textContent =
        ui.view === "saved"
          ? "Отложенное"
          : ui.view === "recent"
            ? "Недавно открывали"
            : focused
              ? "Ещё в ленте"
              : "Материалы архива";
      root.querySelector("[data-result-count]").textContent =
        list.length + " материалов";
      var missing =
        ui.view === "news"
          ? []
          : state[ui.view === "saved" ? "saved" : "recent"].filter(
              function (s) {
                return !byID[s.id];
              },
            );
      empty.hidden = list.length > 0 && !missing.length;
      if (!empty.hidden) {
        empty.innerHTML =
          (focused && !items.length
            ? "<h2>Пока нет опубликованных материалов</h2><p>Первый выпуск появится здесь после публикации.</p>"
            : focused && !list.length
              ? "<h2>Все материалы — в фокусе</h2><p>В этом архиве пока " +
                items.length +
                " материалов. Новые появятся после следующей публикации.</p>"
              : list.length
                ? ""
                : "<h2>" +
                  (ui.view === "saved"
                    ? "Здесь будут ваши находки"
                    : ui.view === "recent"
                      ? "Пока нет открытых материалов"
                      : "Ничего не нашлось") +
                  "</h2><p>" +
                  (ui.view === "saved"
                    ? "Нажмите «+» на карточке, чтобы вернуться к статье позже."
                    : ui.view === "recent"
                      ? "Откройте статью из ленты, архива или Telegram."
                      : "Измените тему или период. Поиск по всему тексту доступен отдельно.") +
                  "</p><button data-reset>К подборке</button>") +
          missing
            .map(function (s) {
              return (
                '<div class="hd-missing">' +
                esc(s.title) +
                ' — больше нет в опубликованном каталоге. <button data-remove="' +
                esc(s.id) +
                '">Удалить запись</button></div>'
              );
            })
            .join("");
      }
      root.querySelectorAll("[data-view]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.dataset.view === ui.view));
      });
      root.querySelectorAll("[data-topic]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.dataset.topic === ui.topic));
      });
      root.querySelectorAll("[data-sort]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.dataset.sort === ui.sort));
      });
      root.querySelector("[data-clear-search]").hidden = !ui.q;
      var full = new URL("search/", base);
      if (ui.q) full.searchParams.set("q", ui.q);
      root.querySelector(".hd-full-search").href = full.href;
      var clear = root.querySelector("[data-clear-state]");
      clear.hidden = ui.view === "news";
      clear.textContent =
        ui.view === "saved" ? "Очистить отложенное" : "Очистить историю";
      recentSidebar();
      syncButtons();
      if (savedFocus && !document.contains(focusedButton)) {
        var replacement = Array.from(root.querySelectorAll("[data-save]")).find(
          function (b) {
            return b.dataset.save === savedFocus;
          },
        );
        if (replacement) replacement.focus();
        else root.querySelector('.hd-views [aria-pressed="true"]').focus();
      }
      status.hidden = false;
      status.textContent =
        (focused
          ? "В архиве " + items.length + " материалов."
          : list.length
            ? "Найдено " + list.length + " материалов."
            : "Нет подходящих материалов.") +
        (ui.period !== "all"
          ? " Период от последнего выпуска " + latest + "."
          : "");
    }
    function reset() {
      ui = { view: "news", topic: "all", period: "all", sort: "newest", q: "" };
      input.value = "";
      period.value = "all";
      limit = BATCH;
      writeURL();
      render();
    }
    function load() {
      error.hidden = true;
      status.hidden = false;
      status.textContent = "Загружаем каталог…";
      fetch(new URL(root.dataset.catalog, base).href, {
        signal: abort.signal,
        cache: "no-cache",
      })
        .then(function (r) {
          if (!r.ok) throw Error("catalog");
          return r.json();
        })
        .then(function (data) {
          if (
            data.schema_version !== 1 ||
            !Array.isArray(data.items) ||
            !Array.isArray(data.focus_ids) ||
            !data.items.every(valid)
          )
            throw Error("schema");
          items = data.items;
          byID = {};
          items.forEach(function (x) {
            if (byID[x.id]) throw Error("duplicate");
            byID[x.id] = x;
          });
          focusIDs = data.focus_ids
            .filter(function (id) {
              return byID[id];
            })
            .slice(0, 5);
          var profiles = {};
          items.forEach(function (x) {
            profiles[x.profile_id] = x.profile_name;
          });
          root.querySelector(".hd-topics").innerHTML =
            '<button data-topic="all" aria-pressed="true">Все темы</button>' +
            Object.keys(profiles)
              .sort(function (a, b) {
                return profiles[a].localeCompare(profiles[b]);
              })
              .map(function (id) {
                return (
                  '<button data-topic="' +
                  esc(id) +
                  '" aria-pressed="false">' +
                  esc(profiles[id]) +
                  "</button>"
                );
              })
              .join("");
          ready = true;
          root.dataset.catalogReady = "1";
          root
            .querySelectorAll(".hd-views,.hd-controls,.hd-topics,[data-view]")
            .forEach(function (n) {
              n.hidden = false;
            });
          fromURL();
          render();
        })
        .catch(function (e) {
          if (e.name === "AbortError") return;
          error.hidden = false;
          status.hidden = true;
        });
    }
    root.addEventListener("click", function (event) {
      var b = event.target.closest("button");
      if (!b || !root.contains(b)) return;
      if (b.dataset.save) {
        if (byID[b.dataset.save]) toggle(byID[b.dataset.save]);
        render();
      } else if (b.dataset.view) {
        ui.view = b.dataset.view;
        ui.topic = "all";
        ui.period = "all";
        ui.q = "";
        input.value = "";
        period.value = "all";
        limit = BATCH;
        writeURL(true);
        render();
      } else if (b.dataset.topic) {
        ui.topic = b.dataset.topic;
        limit = BATCH;
        writeURL(true);
        render();
      } else if (b.dataset.sort) {
        ui.sort = b.dataset.sort;
        limit = BATCH;
        writeURL(true);
        render();
      } else if (b.hasAttribute("data-clear-search")) {
        ui.q = "";
        input.value = "";
        writeURL();
        render();
        input.focus();
      } else if (b.hasAttribute("data-reset")) reset();
      else if (b.hasAttribute("data-retry")) load();
      else if (b.classList.contains("hd-more")) {
        limit += BATCH;
        render();
      } else if (b.hasAttribute("data-clear-state")) {
        var key = ui.view === "saved" ? "saved" : "recent";
        if (
          window.confirm(
            key === "saved"
              ? "Удалить все отложенные статьи из этого браузера?"
              : "Очистить историю этого браузера?",
          )
        ) {
          state[key] = [];
          persist();
          render();
        }
      } else if (b.dataset.remove) {
        var removeKey = ui.view === "saved" ? "saved" : "recent";
        state[removeKey] = state[removeKey].filter(function (x) {
          return x.id !== b.dataset.remove;
        });
        persist();
        render();
      }
    });
    input.addEventListener("input", function () {
      ui.q = input.value.slice(0, 200);
      limit = BATCH;
      writeURL();
      render();
    });
    period.addEventListener("change", function () {
      ui.period = period.value;
      limit = BATCH;
      writeURL(true);
      render();
    });
    var onBack = function () {
      fromURL();
      render();
    };
    window.addEventListener("popstate", onBack);
    active = {
      root: root,
      refresh: render,
      destroy: function () {
        abort.abort();
        window.removeEventListener("popstate", onBack);
      },
    };
    load();
  }
  function enhance() {
    if (active && !document.contains(active.root)) {
      active.destroy();
      active = null;
    }
    loadState();
    initializeArticle();
    var root = document.querySelector(".hd-dashboard");
    if (root) initializeHome(root);
    syncButtons();
  }
  window.addEventListener("storage", function (event) {
    if (event.key === KEY) {
      loadState(true);
      syncButtons();
      if (active) active.refresh();
    }
  });
  if (typeof document$ !== "undefined" && document$ && document$.subscribe)
    document$.subscribe(enhance);
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", enhance);
  else enhance();
})();
