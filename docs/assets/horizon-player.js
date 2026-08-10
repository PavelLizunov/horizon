/* Unified narration player.
 *
 * The page always ships a working <audio controls>. JavaScript replaces it
 * only after both custom views have mounted successfully. Inline and sticky
 * controls operate the same audio element, so playback never restarts when the
 * reader scrolls.
 */
(function () {
  "use strict";

  var SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2, 2.5];
  var SPEED_KEY = "hz-narration-speed-of-encoded";
  var RESUME_PREFIX = "hz-narration-position:";
  var activeController = null;

  function clock(seconds) {
    if (!isFinite(seconds) || seconds < 0) return "--:--";
    var whole = Math.floor(seconds);
    var hours = Math.floor(whole / 3600);
    var minutes = Math.floor((whole % 3600) / 60);
    var rest = whole % 60;
    var short = minutes + ":" + (rest < 10 ? "0" : "") + rest;
    return hours ? hours + ":" + (minutes < 10 ? "0" : "") + short : short;
  }

  function rateText(value) {
    return value.toFixed(2).replace(/\.?0+$/, "") + "×";
  }

  function readNumber(key) {
    try {
      return parseFloat(window.localStorage.getItem(key));
    } catch (error) {
      return NaN;
    }
  }

  function remember(key, value) {
    try {
      window.localStorage.setItem(key, String(value));
    } catch (error) {
      /* Private browsing may block storage; playback still works. */
    }
  }

  function forget(key) {
    try {
      window.localStorage.removeItem(key);
    } catch (error) {
      /* Nothing to clear when storage is unavailable. */
    }
  }

  function storedSpeed() {
    var saved = readNumber(SPEED_KEY);
    return SPEEDS.indexOf(saved) === -1 ? 1 : saved;
  }

  function button(className, label, text) {
    var control = document.createElement("button");
    control.type = "button";
    control.className = className;
    control.setAttribute("aria-label", label);
    if (text) control.textContent = text;
    return control;
  }

  function PlayerController(audio) {
    this.audio = audio;
    this.inline = null;
    this.sticky = null;
    this.observer = null;
    this.bindings = [];
    this.views = [];
    this.playButtons = [];
    this.playGlyphs = [];
    this.seeks = [];
    this.elapsed = [];
    this.remaining = [];
    this.rates = [];
    this.statuses = [];
    this.started = false;
    this.inlineAbove = false;
    this.restored = false;
    this.positionDirty = false;
    this.resumeFloor = 0;
    this.lastSavedAt = 0;
    this.resumeKey = RESUME_PREFIX + window.location.pathname;
  }

  PlayerController.prototype.listen = function (target, name, handler) {
    target.addEventListener(name, handler);
    this.bindings.push([target, name, handler]);
  };

  PlayerController.prototype.makeSeek = function () {
    var self = this;
    var seek = document.createElement("input");
    seek.type = "range";
    seek.className = "hz-player__seek";
    seek.min = "0";
    seek.max = "0";
    seek.step = "0.1";
    seek.value = "0";
    seek.disabled = true;
    seek.setAttribute("aria-label", "Положение воспроизведения");
    this.listen(seek, "input", function () {
      if (isFinite(self.audio.duration)) {
        self.positionDirty = true;
        self.resumeFloor = 0;
        self.audio.currentTime = parseFloat(seek.value);
        self.sync();
      }
    });
    this.seeks.push(seek);
    return seek;
  };

  PlayerController.prototype.makeRate = function () {
    var self = this;
    var select = document.createElement("select");
    select.className = "hz-player__speed";
    select.setAttribute("aria-label", "Скорость воспроизведения");
    for (var i = 0; i < SPEEDS.length; i++) {
      var option = document.createElement("option");
      option.value = String(SPEEDS[i]);
      option.textContent = rateText(SPEEDS[i]);
      select.appendChild(option);
    }
    this.listen(select, "change", function () {
      self.audio.playbackRate = parseFloat(select.value);
      remember(SPEED_KEY, self.audio.playbackRate);
    });
    this.rates.push(select);
    return select;
  };

  PlayerController.prototype.makePlay = function () {
    var self = this;
    var play = button("hz-player__play", "Слушать");
    var glyph = document.createElement("span");
    glyph.className = "hz-i hz-i--play";
    glyph.setAttribute("aria-hidden", "true");
    play.appendChild(glyph);
    this.listen(play, "click", function () {
      self.togglePlay();
    });
    this.playButtons.push(play);
    this.playGlyphs.push(glyph);
    return play;
  };

  PlayerController.prototype.makeTransport = function () {
    var self = this;
    var transport = document.createElement("div");
    transport.className = "hz-player__transport";
    var back = button("hz-player__skip", "Назад на 10 секунд", "−10");
    var forward = button("hz-player__skip", "Вперёд на 15 секунд", "+15");
    this.listen(back, "click", function () { self.seekBy(-10); });
    this.listen(forward, "click", function () { self.seekBy(15); });
    transport.appendChild(back);
    transport.appendChild(this.makePlay());
    transport.appendChild(forward);
    return transport;
  };

  PlayerController.prototype.makeVolume = function () {
    var self = this;
    var group = document.createElement("div");
    group.className = "hz-player__volume";
    var mute = button("hz-player__mute", "Приглушить");
    var glyph = document.createElement("span");
    glyph.className = "hz-i hz-i--volume";
    glyph.setAttribute("aria-hidden", "true");
    mute.appendChild(glyph);

    var slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = "1";
    slider.step = "0.05";
    slider.value = String(this.audio.volume);
    slider.setAttribute("aria-label", "Громкость");

    this.listen(mute, "click", function () {
      self.audio.muted = !self.audio.muted;
      if (!self.audio.muted && self.audio.volume === 0) self.audio.volume = 1;
    });
    this.listen(slider, "input", function () {
      self.audio.volume = parseFloat(slider.value);
      self.audio.muted = self.audio.volume === 0;
    });
    this.listen(this.audio, "volumechange", function () {
      var shown = self.audio.muted ? 0 : self.audio.volume;
      slider.value = String(shown);
      slider.style.setProperty("--hz-level", shown);
      glyph.className = "hz-i hz-i--" + (shown ? "volume" : "muted");
      mute.setAttribute("aria-label", shown ? "Приглушить" : "Включить звук");
    });
    slider.style.setProperty("--hz-level", this.audio.volume);
    group.appendChild(mute);
    group.appendChild(slider);
    return group;
  };

  PlayerController.prototype.makeView = function (sticky) {
    var root = document.createElement("div");
    root.className = "hz-player" + (sticky ? " hz-player--sticky" : " hz-player--inline");
    root.setAttribute("role", "region");
    root.setAttribute("aria-label", sticky ? "Плеер озвучки" : "Озвучка статьи");
    if (sticky) {
      root.hidden = true;
      root.setAttribute("aria-hidden", "true");
    }

    var timeline = document.createElement("div");
    timeline.className = "hz-player__timeline";
    var elapsed = document.createElement("span");
    elapsed.className = "hz-player__time hz-player__time--elapsed";
    elapsed.textContent = "0:00";
    var remaining = document.createElement("span");
    remaining.className = "hz-player__time hz-player__time--remaining";
    remaining.textContent = "−--:--";
    timeline.appendChild(this.makeSeek());
    timeline.appendChild(elapsed);
    timeline.appendChild(remaining);
    this.elapsed.push(elapsed);
    this.remaining.push(remaining);

    var controls = document.createElement("div");
    controls.className = "hz-player__controls";
    controls.appendChild(this.makeTransport());
    var secondary = document.createElement("div");
    secondary.className = "hz-player__secondary";
    if (!sticky) secondary.appendChild(this.makeVolume());
    secondary.appendChild(this.makeRate());
    controls.appendChild(secondary);

    var status = document.createElement("span");
    status.className = "hz-player__status";
    status.setAttribute("aria-live", "polite");
    this.statuses.push(status);

    root.appendChild(timeline);
    root.appendChild(controls);
    root.appendChild(status);
    this.views.push(root);
    return root;
  };

  PlayerController.prototype.mount = function () {
    var self = this;
    try {
      this.inline = this.makeView(false);
      this.sticky = this.makeView(true);
      this.audio.parentNode.insertBefore(this.inline, this.audio);
      document.body.appendChild(this.sticky);

      this.listen(this.audio, "play", function () {
        self.started = true;
        self.positionDirty = true;
        self.setStatus("");
        self.sync();
        self.updateSticky();
        self.updateMediaSession();
      });
      this.listen(this.audio, "pause", function () {
        self.savePosition(true);
        self.sync();
        self.updateMediaSession();
      });
      this.listen(this.audio, "timeupdate", function () {
        self.sync();
        self.savePosition(false);
        self.updateMediaPosition();
      });
      this.listen(this.audio, "durationchange", function () { self.sync(); });
      this.listen(this.audio, "loadedmetadata", function () {
        self.restorePosition();
        self.audio.playbackRate = storedSpeed();
        self.sync();
      });
      this.listen(this.audio, "ratechange", function () { self.sync(); });
      this.listen(this.audio, "waiting", function () { self.setStatus("Звук загружается…"); });
      this.listen(this.audio, "playing", function () { self.setStatus(""); });
      this.listen(this.audio, "canplay", function () { self.setStatus(""); });
      this.listen(this.audio, "error", function () {
        self.setStatus("Не удалось загрузить аудио. Попробуйте обновить страницу.");
      });
      this.listen(this.audio, "ended", function () {
        self.started = false;
        forget(self.resumeKey);
        self.sync();
        self.updateSticky();
      });
      this.listen(window, "pagehide", function () { self.savePosition(true); });
      this.listen(document, "keydown", function (event) { self.onKeydown(event); });

      this.watchInline();
      this.setupMediaSession();
      this.audio.playbackRate = storedSpeed();
      this.sync();

      // Keep this last: if any setup above throws, destroy() leaves the native
      // browser controls intact instead of stranding the reader.
      this.audio.removeAttribute("controls");
      this.audio.dataset.hzEnhanced = "1";
    } catch (error) {
      this.destroy();
      throw error;
    }
  };

  PlayerController.prototype.watchInline = function () {
    var self = this;
    function measure(entry) {
      var box = entry ? entry.boundingClientRect : self.inline.getBoundingClientRect();
      self.inlineAbove = box.bottom <= 0;
      self.updateSticky();
    }
    if ("IntersectionObserver" in window) {
      this.observer = new IntersectionObserver(function (entries) { measure(entries[0]); });
      this.observer.observe(this.inline);
    } else {
      this.listen(window, "scroll", function () { measure(); });
      measure();
    }
  };

  PlayerController.prototype.togglePlay = function () {
    var self = this;
    if (!this.audio.paused) {
      this.audio.pause();
      return;
    }
    var request = this.audio.play();
    if (request && request.catch) {
      request.catch(function () {
        self.setStatus("Не удалось начать воспроизведение.");
      });
    }
  };

  PlayerController.prototype.seekBy = function (seconds) {
    if (!isFinite(this.audio.duration)) return;
    this.positionDirty = true;
    this.resumeFloor = 0;
    this.audio.currentTime = Math.max(0, Math.min(this.audio.duration, this.audio.currentTime + seconds));
    this.sync();
  };

  PlayerController.prototype.changeRate = function (direction) {
    var nearest = 0;
    for (var i = 1; i < SPEEDS.length; i++) {
      if (Math.abs(SPEEDS[i] - this.audio.playbackRate) < Math.abs(SPEEDS[nearest] - this.audio.playbackRate)) {
        nearest = i;
      }
    }
    nearest = Math.max(0, Math.min(SPEEDS.length - 1, nearest + direction));
    this.audio.playbackRate = SPEEDS[nearest];
    remember(SPEED_KEY, this.audio.playbackRate);
  };

  PlayerController.prototype.sync = function () {
    var duration = this.audio.duration;
    var ready = isFinite(duration) && duration > 0;
    var progress = ready ? this.audio.currentTime / duration : 0;
    for (var i = 0; i < this.seeks.length; i++) {
      this.seeks[i].disabled = !ready;
      this.seeks[i].max = ready ? String(duration) : "0";
      this.seeks[i].value = ready ? String(this.audio.currentTime) : "0";
      this.seeks[i].style.setProperty("--hz-level", progress);
    }
    for (var j = 0; j < this.elapsed.length; j++) {
      this.elapsed[j].textContent = clock(this.audio.currentTime);
      this.remaining[j].textContent = "−" + clock(ready ? duration - this.audio.currentTime : NaN);
    }
    for (var k = 0; k < this.rates.length; k++) {
      this.rates[k].value = String(this.audio.playbackRate);
    }
    for (var n = 0; n < this.playButtons.length; n++) {
      var playing = !this.audio.paused && !this.audio.ended;
      this.playGlyphs[n].className = "hz-i hz-i--" + (playing ? "pause" : "play");
      this.playButtons[n].setAttribute("aria-label", playing ? "Пауза" : "Слушать");
    }
  };

  PlayerController.prototype.setStatus = function (message) {
    for (var i = 0; i < this.statuses.length; i++) this.statuses[i].textContent = message;
  };

  PlayerController.prototype.updateSticky = function () {
    if (!this.sticky) return;
    var visible = this.started && this.inlineAbove && !this.audio.ended;
    this.sticky.hidden = !visible;
    this.sticky.setAttribute("aria-hidden", visible ? "false" : "true");
    document.documentElement.classList.toggle("hz-player-is-sticky", visible);
  };

  PlayerController.prototype.restorePosition = function () {
    if (this.restored || !isFinite(this.audio.duration)) return;
    this.restored = true;
    var saved = readNumber(this.resumeKey);
    if (saved > 5 && saved < this.audio.duration - 10) {
      this.resumeFloor = saved;
      this.lastSavedAt = Date.now();
      this.audio.currentTime = Math.max(0, saved - 4);
    }
  };

  PlayerController.prototype.savePosition = function (force) {
    if (!this.positionDirty) return;
    if (!isFinite(this.audio.duration) || !this.audio.currentTime) return;
    var now = Date.now();
    if (!force && now - this.lastSavedAt < 5000) return;
    this.lastSavedAt = now;
    if (this.audio.ended || this.audio.duration - this.audio.currentTime < 10) {
      forget(this.resumeKey);
    } else if (this.audio.currentTime >= 5) {
      remember(this.resumeKey, Math.floor(Math.max(this.audio.currentTime, this.resumeFloor)));
    }
  };

  PlayerController.prototype.onKeydown = function (event) {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
    var target = event.target;
    if (target && target.closest && target.closest("input, select, textarea, button, a, [contenteditable='true']")) return;
    if (!this.started && !this.inline.contains(document.activeElement)) return;
    var key = event.key.toLowerCase();
    if (key === " " || key === "k") this.togglePlay();
    else if (key === "j") this.seekBy(-10);
    else if (key === "l") this.seekBy(15);
    else if (key === "arrowleft") this.seekBy(-5);
    else if (key === "arrowright") this.seekBy(5);
    else if (key === "m") this.audio.muted = !this.audio.muted;
    else if (key === ",") this.changeRate(-1);
    else if (key === ".") this.changeRate(1);
    else return;
    event.preventDefault();
  };

  PlayerController.prototype.setupMediaSession = function () {
    if (!("mediaSession" in navigator)) return;
    var self = this;
    try {
      if ("MediaMetadata" in window) {
        var heading = document.querySelector("h1");
        var logo = document.querySelector(".md-header__button.md-logo img");
        var metadata = {
          title: heading ? heading.textContent.trim() : document.title,
          artist: "Digest Ninitux",
        };
        if (logo && logo.src) metadata.artwork = [{ src: logo.src }];
        navigator.mediaSession.metadata = new MediaMetadata(metadata);
      }
      var actions = {
        play: function () { self.togglePlay(); },
        pause: function () { self.audio.pause(); },
        seekbackward: function (details) { self.seekBy(-(details.seekOffset || 10)); },
        seekforward: function (details) { self.seekBy(details.seekOffset || 15); },
        seekto: function (details) {
          if (isFinite(self.audio.duration)) {
            self.positionDirty = true;
            self.resumeFloor = 0;
            self.audio.currentTime = Math.max(0, Math.min(self.audio.duration, details.seekTime));
          }
        },
      };
      Object.keys(actions).forEach(function (name) {
        try { navigator.mediaSession.setActionHandler(name, actions[name]); } catch (error) { /* unsupported action */ }
      });
    } catch (error) {
      /* Lock-screen integration is optional; the player is not. */
    }
  };

  PlayerController.prototype.updateMediaSession = function () {
    if ("mediaSession" in navigator) {
      navigator.mediaSession.playbackState = this.audio.paused ? "paused" : "playing";
    }
  };

  PlayerController.prototype.updateMediaPosition = function () {
    if (!("mediaSession" in navigator) || !navigator.mediaSession.setPositionState) return;
    if (!isFinite(this.audio.duration) || !this.audio.duration) return;
    try {
      navigator.mediaSession.setPositionState({
        duration: this.audio.duration,
        playbackRate: this.audio.playbackRate,
        position: Math.min(this.audio.currentTime, this.audio.duration),
      });
    } catch (error) {
      /* Some browsers expose the API but reject it for remote audio. */
    }
  };

  PlayerController.prototype.destroy = function () {
    this.savePosition(true);
    if (this.observer) this.observer.disconnect();
    for (var i = 0; i < this.bindings.length; i++) {
      this.bindings[i][0].removeEventListener(this.bindings[i][1], this.bindings[i][2]);
    }
    this.bindings = [];
    if (this.inline && this.inline.parentNode) this.inline.parentNode.removeChild(this.inline);
    if (this.sticky && this.sticky.parentNode) this.sticky.parentNode.removeChild(this.sticky);
    document.documentElement.classList.remove("hz-player-is-sticky");
    this.audio.pause();
    this.audio.controls = true;
    delete this.audio.dataset.hzEnhanced;
    if ("mediaSession" in navigator) {
      ["play", "pause", "seekbackward", "seekforward", "seekto"].forEach(function (name) {
        try { navigator.mediaSession.setActionHandler(name, null); } catch (error) { /* unsupported action */ }
      });
    }
  };

  function enhance() {
    var audio = document.querySelector("audio.hz-narration");
    if (activeController && activeController.audio === audio) return;
    if (activeController) {
      activeController.destroy();
      activeController = null;
    }
    if (!audio) return;
    var controller = new PlayerController(audio);
    try {
      controller.mount();
      activeController = controller;
    } catch (error) {
      // The original <audio controls> is deliberately the error boundary.
      window.console.warn("Narration player enhancement failed", error);
    }
  }

  // Material's instant navigation swaps the article without re-running this
  // file. document$ emits both on first load and after every such swap.
  if (typeof document$ !== "undefined" && document$ && document$.subscribe) {
    document$.subscribe(enhance);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhance);
  } else {
    enhance();
  }
})();
