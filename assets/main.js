/* ===========================================================
   Forest306 · 个人主页  —  main.js
   1) 站内跳转：不重载整页，只替换 .layout 的内容
      —— 右下角的音乐播放器不会被销毁，点过一次之后换页不断曲
   2) 导航高亮
   失败时（fetch 不可用 / file:// 打开 / 目标不存在）自动退回普通跳转
   =========================================================== */

(function () {
  "use strict";

  var LEAVE_MS = 240;
  var busy = false;

  function wait(ms) {
    return new Promise(function (r) { setTimeout(r, ms); });
  }

  /* -------- 判断要不要接管这次点击 -------- */

  function internalTarget(e) {
    var link = e.target.closest ? e.target.closest("a") : null;
    if (!link) return null;

    var href = link.getAttribute("href");
    if (!href) return null;
    if (href.charAt(0) === "#") return null;                  // 锚点
    if (/^(https?:)?\/\//.test(href)) return null;            // 外链
    if (href.indexOf("mailto:") === 0) return null;
    if (link.target === "_blank" || link.hasAttribute("download")) return null;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return null;
    if (href.indexOf("/website/") !== 0) return null;          // 只管本站路径

    return href;
  }

  /* -------- 当前页导航高亮 -------- */

  function highlight() {
    var here = (window.location.pathname.split("/").pop() || "index.html").toLowerCase();
    document.querySelectorAll(".nav-link").forEach(function (a) {
      var href = a.getAttribute("href") || "";
      a.classList.toggle("is-active", href.split("/").pop().toLowerCase() === here);
    });
  }

  /* -------- 局部换页 -------- */

  function loadLayout(href) {
    return fetch(href, { credentials: "same-origin" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.text();
    }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, "text/html");
      var next = doc.querySelector(".layout");
      if (!next) throw new Error("目标页没有 .layout");
      return { layout: next, title: doc.title };
    });
  }

  function navigate(href, push) {
    if (busy) return;
    busy = true;

    document.body.dataset.anim = "out";

    Promise.all([loadLayout(href), wait(LEAVE_MS)]).then(function (r) {
      var data = r[0];
      var current = document.querySelector(".layout");
      if (!current) throw new Error("当前页没有 .layout");

      current.replaceWith(data.layout);       // 播放器在 .layout 之外，不受影响
      if (data.title) document.title = data.title;

      if (push) history.pushState({ href: href }, "", href);

      highlight();
      window.scrollTo(0, 0);
      document.body.dataset.anim = "in";
      busy = false;
    }).catch(function () {
      // 换页失败 → 老老实实整页跳
      window.location.href = href;
    });
  }

  document.addEventListener("click", function (e) {
    var href = internalTarget(e);
    if (!href) return;
    e.preventDefault();
    navigate(href, true);
  });

  window.addEventListener("popstate", function () {
    navigate(window.location.pathname + window.location.search, false);
  });

  // 进入页面（含前进 / 后退恢复）播放淡入
  window.addEventListener("pageshow", function () {
    document.body.dataset.anim = "in";
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", highlight);
  } else {
    highlight();
  }
})();
