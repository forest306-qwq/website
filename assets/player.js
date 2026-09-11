/* ===========================================================
   Forest306 · 右下角背景音乐  —  player.js
   1) 进站先尝试自动播放，被浏览器拦下就等用户第一次点击/按键
   2) 开着 / 关掉 / 播放进度都记在 sessionStorage，站内跳转不断曲
   =========================================================== */

(function () {
  "use strict";

  var audio = document.getElementById("bgm");
  var box   = document.getElementById("nowPlaying");
  if (!audio || !box) return;

  var label = box.querySelector(".label");

  var KEY_ON   = "forest306.bgm";        // "on" 开着 / "off" 用户主动关掉
  var KEY_TIME = "forest306.bgm.time";   // 播放进度（秒）

  function store(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} }
  function read(k)     { try { return sessionStorage.getItem(k); } catch (e) { return null; } }

  /* -------- 提示文案 -------- */

  function setState(state, text) {
    box.dataset.state = state;
    if (label && text) label.textContent = text;
  }

  function showMissing() {
    setState("error", "缺音频文件");
    box.title = "把音乐文件放进 /website/assets/ 并命名为 for-river.mp3 就能播了";
  }

  /* -------- 进度记忆 -------- */

  function saveTime()   { store(KEY_TIME, String(audio.currentTime || 0)); }
  function readTime()   { var t = parseFloat(read(KEY_TIME)); return isNaN(t) ? 0 : t; }

  function restoreTime() {
    var t = readTime();
    if (t > 1 && Math.abs(t - audio.currentTime) > 1) {
      try { audio.currentTime = t; } catch (e) {}
    }
  }

  if (audio.readyState >= 1) restoreTime();
  else audio.addEventListener("loadedmetadata", restoreTime, { once: true });

  var lastSave = 0;
  audio.addEventListener("timeupdate", function () {
    var now = Date.now();
    if (now - lastSave > 1000) { lastSave = now; saveTime(); }
  });
  window.addEventListener("pagehide", saveTime);

  /* -------- 播放 / 暂停 -------- */

  function onPlaying() { setState("playing", "正在听"); store(KEY_ON, "on"); }

  function play() {
    if (audio.error) { showMissing(); return; }

    var p;
    try { p = audio.play(); } catch (e) { setState("ready", "点击播放"); return; }

    if (p && typeof p.then === "function") {
      p.then(onPlaying).catch(function () {   // 被自动播放策略拦下
        setState("ready", "点击播放");
        armFirstGesture();
      });
    } else {
      onPlaying();
    }
  }

  function pause() {
    audio.pause();
    saveTime();
    setState("paused", "已暂停");
    store(KEY_ON, "off");
  }

  /* -------- 等用户在这页的第一次交互，再补播一次 -------- */

  var armed = false;

  function armFirstGesture() {
    if (armed) return;
    armed = true;

    var types = ["pointerdown", "keydown", "touchstart"];

    function detach() {
      if (!armed) return;
      armed = false;
      types.forEach(function (t) { document.removeEventListener(t, handler, true); });
    }
    function handler(e) {
      if (box.contains(e.target)) return;     // 播放器自己的按钮，交给 click 处理
      detach();
      if (audio.paused && read(KEY_ON) !== "off") play();
    }

    types.forEach(function (t) { document.addEventListener(t, handler, true); });
    audio.addEventListener("playing", detach);
  }

  /* -------- 播放器本体 -------- */

  box.addEventListener("click", function (e) {
    if (e.target.closest(".np-ext")) return;  // ↗ 是外链，交给浏览器
    if (audio.paused) play(); else pause();
  });

  /* -------- 进站 -------- */

  if (audio.error) {
    showMissing();
  } else if (read(KEY_ON) === "off") {
    setState("paused", "点击播放");
  } else {
    play();
  }
})();
