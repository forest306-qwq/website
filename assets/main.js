/* ===========================================================
   Forest306 · 个人主页  —  main.js
   1) 页面跳转动画（淡出 → 跳转 → 淡入）
   2) 当前页导航高亮
   =========================================================== */

(function () {
  "use strict";

  /* -------- 1. 跳转动画 -------- */

  var LEAVE_MS = 240;

  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("a") : null;
    if (!link) return;

    var href = link.getAttribute("href");
    if (!href) return;
    if (href.charAt(0) === "#") return;                       // 锚点
    if (/^(https?:)?\/\//.test(href)) return;                 // 外链
    if (link.target === "_blank" || link.hasAttribute("download")) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;

    e.preventDefault();
    document.body.dataset.anim = "out";
    window.setTimeout(function () {
      window.location.href = href;
    }, LEAVE_MS);
  });

  // 进入页面（含浏览器前进/后退缓存恢复）都播放淡入
  window.addEventListener("pageshow", function () {
    document.body.dataset.anim = "in";
  });

  /* -------- 2. 当前页高亮（无需手动维护） -------- */

  document.addEventListener("DOMContentLoaded", function () {
    var here = window.location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".nav-link").forEach(function (a) {
      var href = a.getAttribute("href") || "";
      if (href.split("/").pop() === here) a.classList.add("is-active");
    });
  });
})();
