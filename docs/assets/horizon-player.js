/* Narration player.
 *
 * Progressive enhancement, deliberately: the page ships a plain <audio
 * controls> element, and this script replaces it only once it has run. With
 * JavaScript off, or if this file fails to load, the reader still gets a
 * working player — just the browser's own.
 *
 * The layout follows the player everyone already knows: the seek bar across
 * the top, then play with volume beside it, and the clock and speed on the
 * right. Volume and speed are plain sliders, always visible — familiar beats
 * clever, and there is nothing to gain from making someone learn a new volume
 * control.
 *
 * Speed starts at 1x, and 1x is already brisk: the files are encoded a quarter
 * faster than the model read them, because a digest is something people want to
 * hear faster than it was read and most will never touch the control. The
 * control is here anyway — Chrome and Safari bury playback rate in a context
 * menu — but it starts where the listener already wanted to be.
 *
 * Skip buttons stay out: furniture on a three-minute file.
 */
(function () {
  "use strict";

  // The files are already encoded a quarter faster than the model read them,
  // so 1x here is the speed a listener asked for. Anything else would compound:
  // the old default of 1.25 on top of a 1.25 file plays at 1.56.
  var SPEED = { min: 0.75, max: 2.5, step: 0.25, fallback: 1 };
  // Key renamed with the meaning. A listener who had chosen 1.25 would
  // otherwise keep it and hear the compounded rate without ever asking for it.
  var SPEED_KEY = "hz-narration-speed-of-encoded";
  var VOLUME_KEY = "hz-narration-volume";

  function clock(seconds) {
    if (!isFinite(seconds)) return "--:--";
    var whole = Math.floor(seconds);
    var minutes = Math.floor(whole / 60);
    var rest = whole % 60;
    return minutes + ":" + (rest < 10 ? "0" : "") + rest;
  }

  function stored(key, fallback, low, high) {
    try {
      var saved = parseFloat(window.localStorage.getItem(key));
      return saved >= low && saved <= high ? saved : fallback;
    } catch (error) {
      // Private mode and blocked storage both throw; the default is fine.
      return fallback;
    }
  }

  function remember(key, value) {
    try {
      window.localStorage.setItem(key, String(value));
    } catch (error) {
      /* nothing to do — the preference just will not survive the page */
    }
  }

  /* A label that is always visible, plus a slider that opens beside it. Used
   * for both volume and speed, because they are the same interaction and
   * writing it twice would let the two drift apart.
   *
   * Opens on focus as well as hover: these are real <input type="range">
   * elements, so arrow keys work without a line of code here, but only if the
   * keyboard can reach them at all. */
  function slidingControl(options) {
    var group = document.createElement("div");
    group.className = "hz-player__group";

    var slider = document.createElement("input");
    slider.type = "range";
    slider.className = "hz-player__slider";
    slider.min = String(options.min);
    slider.max = String(options.max);
    slider.step = String(options.step);
    slider.setAttribute("aria-label", options.label);

    if (options.handle) {
      group.appendChild(options.handle);
      group.appendChild(slider);
    } else {
      group.appendChild(slider);
      group.appendChild(options.readout);
    }

    slider.addEventListener("input", function () {
      options.onChange(parseFloat(slider.value));
    });

    group.sync = function (value) {
      slider.value = String(value);
      var span = options.max - options.min;
      slider.style.setProperty("--hz-level", (value - options.min) / span);
    };
    return group;
  }

  function volumeControl(audio) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "hz-player__flat";
    var icon = document.createElement("span");
    icon.className = "hz-i hz-i--volume";
    icon.setAttribute("aria-hidden", "true");
    button.appendChild(icon);

    var group = slidingControl({
      min: 0,
      max: 1,
      step: 0.05,
      label: "Громкость",
      handle: button,
      onChange: function (value) {
        audio.volume = value;
        audio.muted = value === 0;
        remember(VOLUME_KEY, value);
      },
    });

    function paint() {
      var shown = audio.muted ? 0 : audio.volume;
      group.sync(shown);
      icon.className = "hz-i hz-i--" + (shown ? "volume" : "muted");
      button.setAttribute("aria-label", shown ? "Приглушить" : "Включить звук");
    }

    button.addEventListener("click", function () {
      audio.muted = !audio.muted;
      // Unmuting from a slider dragged to zero would look broken, so give it
      // something to come back to.
      if (!audio.muted && audio.volume === 0) audio.volume = 1;
    });
    audio.addEventListener("volumechange", paint);

    audio.volume = stored(VOLUME_KEY, 1, 0, 1);
    paint();
    return group;
  }

  function rateControl(audio) {
    var readout = document.createElement("span");
    readout.className = "hz-player__rate";

    var group = slidingControl({
      min: SPEED.min,
      max: SPEED.max,
      step: SPEED.step,
      label: "Скорость воспроизведения",
      readout: readout,
      onChange: function (value) {
        audio.playbackRate = value;
        remember(SPEED_KEY, value);
      },
    });

    function paint() {
      group.sync(audio.playbackRate);
      readout.textContent = audio.playbackRate.toFixed(2).replace(/\.?0+$/, "") + "×";
    }

    audio.addEventListener("ratechange", paint);
    // Some browsers reset the rate when the source loads; others do not.
    audio.addEventListener("loadeddata", function () {
      audio.playbackRate = stored(SPEED_KEY, SPEED.fallback, SPEED.min, SPEED.max);
    });

    audio.playbackRate = stored(SPEED_KEY, SPEED.fallback, SPEED.min, SPEED.max);
    paint();
    return group;
  }

  function build(audio) {
    var player = document.createElement("div");
    player.className = "hz-player";

    var button = document.createElement("button");
    button.type = "button";
    button.className = "hz-player__button";
    button.setAttribute("aria-label", "Слушать");
    var glyph = document.createElement("span");
    glyph.className = "hz-i hz-i--play";
    glyph.setAttribute("aria-hidden", "true");
    button.appendChild(glyph);

    // A real <button> rather than a div: it lands in the tab order and answers
    // to space and enter without any of that being written here.
    var bar = document.createElement("button");
    bar.type = "button";
    bar.className = "hz-player__bar";
    bar.setAttribute("aria-label", "Перемотка");

    var time = document.createElement("span");
    time.className = "hz-player__time";
    time.textContent = "0:00";

    // Two rows: the seek bar owns the first one outright, the transport and
    // readouts share the second. In one row the bar was squeezed to 15% of the
    // width — the most important control ending up the smallest.
    var controls = document.createElement("div");
    controls.className = "hz-player__controls";
    controls.appendChild(button);
    controls.appendChild(volumeControl(audio));
    controls.appendChild(time);
    controls.appendChild(rateControl(audio));

    player.appendChild(bar);
    player.appendChild(controls);

    function paint() {
      var done = audio.duration ? audio.currentTime / audio.duration : 0;
      bar.style.setProperty("--hz-played", done.toFixed(4));
      time.textContent = clock(audio.currentTime) + " / " + clock(audio.duration);
    }

    button.addEventListener("click", function () {
      if (audio.paused) {
        audio.play();
      } else {
        audio.pause();
      }
    });

    audio.addEventListener("play", function () {
      glyph.className = "hz-i hz-i--pause";
      button.setAttribute("aria-label", "Пауза");
    });
    audio.addEventListener("pause", function () {
      glyph.className = "hz-i hz-i--play";
      button.setAttribute("aria-label", "Слушать");
    });
    audio.addEventListener("timeupdate", paint);
    audio.addEventListener("loadedmetadata", paint);
    audio.addEventListener("ended", paint);

    bar.addEventListener("click", function (event) {
      if (!audio.duration) return;
      var box = bar.getBoundingClientRect();
      audio.currentTime = audio.duration * ((event.clientX - box.left) / box.width);
      paint();
    });

    audio.removeAttribute("controls");
    audio.parentNode.insertBefore(player, audio);
    paint();
  }

  function enhance() {
    var players = document.querySelectorAll("audio.hz-narration");
    for (var i = 0; i < players.length; i++) {
      if (!players[i].dataset.hzEnhanced) {
        players[i].dataset.hzEnhanced = "1";
        build(players[i]);
      }
    }
  }

  // navigation.instant swaps the page body over XHR and never re-runs this
  // file, so binding to DOMContentLoaded alone enhances the first page visited
  // and nothing after it — the reader gets the browser's default controls until
  // they reload by hand. Material publishes `document$` for exactly this; it
  // emits on the first load and on every instant navigation.
  //
  // An earlier version listened for "DOMContentSwitch", which is not an event
  // Material fires, or anything else does. It looked like the instant-navigation
  // case was handled and it did nothing at all.
  //
  // `typeof` rather than a truthiness check: `document$` is an undeclared
  // global when instant navigation is off, and touching it directly throws.
  if (typeof document$ !== "undefined" && document$ && document$.subscribe) {
    document$.subscribe(enhance);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enhance);
  } else {
    enhance();
  }
})();
