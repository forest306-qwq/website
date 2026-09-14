/* ===========================================================
   Forest306 · 照片页内放大  —  lightbox.js
   点四宫格里的照片 → 当前页浮层放大，不跳新标签页
   规则：
     · 用事件委托绑在 document 上，所以站内换页之后依然有效
     · 浮层挂在 <body> 下（在 .layout 之外），换页不会被清掉
     · <a href> 保留着，禁用 JS 或中键点击时仍能打开原图
   =========================================================== */

(function () {
  "use strict";

  var TRANS_MS = 300;
  var box = null, imgEl = null;

  function build() {
    box = document.createElement("div");
    box.className = "lightbox";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.innerHTML =
      '<button class="lightbox-close" type="button" aria-label="\u5173\u95ed">\u00d7</button>' +
      '<img alt="">';

    // 点浮层空白处或关闭按钮都关掉；点图片本身不关
    box.addEventListener("click", function (e) {
      if (e.target === imgEl) return;
      close();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" || e.keyCode === 27) close();
    });

    document.body.appendChild(box);
    imgEl = box.querySelector("img");
  }

  function open(src, alt) {
    if (!box) build();

    imgEl.src = src;
    imgEl.alt = alt || "";

    document.body.classList.add("lightbox-open");
    // 下一帧再加 on，过渡动画才会跑起来
    requestAnimationFrame(function () { box.classList.add("on"); });
  }

  function close() {
    if (!box || !box.classList.contains("on")) return;

    box.classList.remove("on");
    document.body.classList.remove("lightbox-open");

    // 动画结束后撤掉 src，免得下次打开先闪一下旧图
    setTimeout(function () {
      if (box && !box.classList.contains("on")) imgEl.removeAttribute("src");
    }, TRANS_MS + 20);
  }

  /* 只接管「照片网格」里的链接 */
  document.addEventListener("click", function (e) {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;   // 让用户还能中键/新窗口打开

    var link = e.target.closest ? e.target.closest(".photo-grid a") : null;
    if (!link) return;

    var im = link.querySelector("img");
    if (!im) return;

    e.preventDefault();
    open(link.getAttribute("href") || im.currentSrc || im.src, im.getAttribute("alt"));
  });
})();
