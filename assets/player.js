/* ===========================================================
   Forest306 · 右下角背景音乐  —  player.js
   手动播放模式：进站不出声，点右下角胶囊才播 / 才停
   （站内跳转由 main.js 局部换页，播放器不会被重建，所以听着不会断）
   =========================================================== */

(function () {
  "use strict";

  var audio = document.getElementById("bgm");
  var box   = document.getElementById("nowPlaying");
  if (!audio || !box) return;

  var label = box.querySelector(".label");

  /* -------- 播放时飘出来的透明音符 -------- */
  (function buildNotes() {
    var wrap = document.createElement("span");
    wrap.className = "np-notes";
    var glyphs = ["\u266a", "\u266b", "\u2669", "\u266c"];   // ♪ ♫ ♩ ♬

    for (var i = 0; i < 5; i++) {
      var n = document.createElement("i");
      n.textContent = glyphs[i % glyphs.length];
      n.style.setProperty("--x", (Math.random() * 48 - 16).toFixed(1) + "px");   // 左右飘多远
      n.style.setProperty("--r", (Math.random() * 60 - 30).toFixed(0) + "deg"); // 旋转多少
      n.style.setProperty("--d", (i * 0.72 + Math.random() * 0.4).toFixed(2) + "s"); // 错开出场
      n.style.fontSize = (12.5 + Math.random() * 6.5).toFixed(1) + "px";
      wrap.appendChild(n);
    }
    box.appendChild(wrap);   // 状态交给 CSS：只有 playing 时才会动
  })();

  function setState(state, text) {
    box.dataset.state = state;
    if (label && text) label.textContent = text;
  }

  function showMissing() {
    setState("error", "缺音频文件");
    box.title = "把音乐文件放进 /website/assets/ 并命名为 for-river.mp3 就能播了";
  }

  function play() {
    if (audio.error) { showMissing(); return; }

    var p;
    try { p = audio.play(); } catch (e) { setState("ready", "点击播放"); return; }

    if (p && typeof p.then === "function") {
      p.then(function () { setState("playing", "正在听"); })
       .catch(function () { setState("ready", "点击播放"); });
    } else {
      setState("playing", "正在听");
    }
  }

  function pause() {
    audio.pause();
    setState("paused", "点击播放");
  }

  /* 点胶囊：播放 / 暂停 */
  box.addEventListener("click", function (e) {
    if (e.target.closest(".np-ext")) return;   // ↗ 是外链，交给浏览器
    if (audio.paused) play(); else pause();
  });

  /* 音乐自然播完（单曲循环时不会触发）后回到可点状态 */
  audio.addEventListener("ended", function () { setState("paused", "点击播放"); });

  /* 进站只做准备，不出声 */
  if (audio.error) {
    showMissing();
  } else {
    setState("ready", "点击播放");
    // 音频文件是后来才加载失败的（比如路径写错），这时再提示一次
    audio.addEventListener("error", showMissing);
  }
})();
