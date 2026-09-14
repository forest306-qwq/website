/* ===========================================================
   Forest306 · 页脚统计  —  counter.js
   1) 访问量：用不蒜子（busuanzi）统计，静态站没有后端，
      数字由第三方服务记录
   2) 存活时间：从建站时刻算到现在，纯前端计算，不依赖任何服务
   注意：站内跳转是局部换页（main.js），不产生新的页面加载，
        所以换页后要再跑一次，否则那些浏览不会被记上
   =========================================================== */

(function () {
  "use strict";

  var SRC = "https://busuanzi.ibruce.info/busuanzi/2.3/busuanzi.pure.mini.js";

  /* ---------------- 访问量 ---------------- */

  function loadCounter() {
    var old = document.getElementById("bsz-script");
    if (old && old.parentNode) old.parentNode.removeChild(old);

    var s = document.createElement("script");
    s.id = "bsz-script";
    s.async = true;
    s.src = SRC;
    (document.body || document.documentElement).appendChild(s);
  }

  /* ---------------- 存活时间 ---------------- */

  function num(v) { return '<span class="num">' + v + "</span>"; }

  function renderUptime() {
    var box = document.getElementById("site-uptime");
    if (!box) return;

    // 起点时间写在页脚的 data-start 上，改日期只改 HTML 就行
    var host = box.closest ? box.closest("[data-start]") : null;
    if (!host) return;

    var start = new Date(host.getAttribute("data-start"));
    if (isNaN(start.getTime())) return;

    var ms = Date.now() - start.getTime();
    if (ms < 0) ms = 0;

    var mins  = Math.floor(ms / 60000);
    var hours = Math.floor(mins / 60);
    var days  = Math.floor(hours / 24);

    if (days >= 1) {
      box.innerHTML = num(days) + " 天 " + num(hours % 24) + " 小时";
    } else if (hours >= 1) {
      box.innerHTML = num(hours) + " 小时 " + num(mins % 60) + " 分";
    } else {
      box.innerHTML = num(mins) + " 分钟";
    }
  }

  /* ---------------- 兜底：确保数字真的显示出来 ---------------- */
  /* 不蒜子的脚本在异常分支里会把容器设成 display:none
     （站内换页时重复注入脚本，容易触发这个分支）
     所以只要确认数字已经取到，就把它强制显示回来 */

  function ensureVisible() {
    ["site_pv", "site_uv"].forEach(function (key) {
      var val = document.getElementById("busuanzi_value_" + key);
      var box = document.getElementById("busuanzi_container_" + key);
      if (!val || !box) return;
      if (val.textContent.replace(/\s/g, "") && box.style.display === "none") {
        box.style.display = "inline";
      }
    });
  }

  /* ---------------- 跑起来 ---------------- */

  function refresh() {
    loadCounter();
    renderUptime();
    // 数字是异步回来的，多查几次；稳态后每分钟查一次也无所谓
    [400, 1200, 2500].forEach(function (ms) { setTimeout(ensureVisible, ms); });
  }

  // 换页之后 main.js 会调这个：重新取访问量 + 重算存活时间
  window.__countReload = refresh;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refresh);
  } else {
    refresh();
  }

  // 页面开着不动时，每分钟刷新一次存活时间
  setInterval(renderUptime, 60000);
})();
