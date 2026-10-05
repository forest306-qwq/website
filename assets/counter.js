/* 页脚统计：单一数据源；每次打开页面或完成站内切换计一次访问。 */
(function () {
  "use strict";
  if (window.__countReload) return;

  var API = "https://busuanzi.9420.ltd/api";
  var IDENTITY_KEY = "forest306-counter-identity";
  var activeRequest;
  var lastPage;
  var sequence = 0;

  function renderCounts(pv, uv, state, message) {
    var visit = document.querySelector(".site-footer .visit");
    if (!visit) return;
    visit.dataset.state = state;
    visit.title = message || "";
    ["site_pv", "site_uv"].forEach(function (key, index) {
      var value = document.getElementById("busuanzi_value_" + key);
      var container = document.getElementById("busuanzi_container_" + key);
      if (value) value.textContent = index === 0 ? pv : uv;
      if (container) container.style.display = "inline";
    });
  }

  async function countVisit() {
    var page = location.origin + location.pathname;
    if (page === lastPage) return;
    lastPage = page;
    var id = ++sequence;
    if (activeRequest) activeRequest.abort();
    if (location.protocol === "file:" || /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname)) {
      renderCounts("–", "–", "preview", "本地预览不计入访问统计");
      return;
    }

    var controller = new AbortController();
    activeRequest = controller;
    var timeout = setTimeout(function () { controller.abort(); }, 8000);
    var headers = { "x-bsz-referer": page };
    try {
      var identity = localStorage.getItem(IDENTITY_KEY);
      if (identity) headers.Authorization = "Bearer " + identity;
    } catch (_) { /* 禁用存储时，服务仍可根据 IP 和浏览器识别访客。 */ }
    renderCounts("…", "…", "loading", "正在读取访问统计");
    try {
      var response = await fetch(API, {
        method: "POST", headers: headers, cache: "no-store", signal: controller.signal
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      var result = await response.json();
      var data = result.data;
      if (!result.success || !data || ![data.site_pv, data.site_uv].every(function (value) {
        return /^\d+$/.test(String(value)) && Number.isSafeInteger(Number(value));
      })) throw new Error("Invalid counter response");
      var token = response.headers.get("Set-Bsz-Identity");
      if (token) {
        try { localStorage.setItem(IDENTITY_KEY, token); } catch (_) { /* 存储不可用不影响显示。 */ }
      }
      if (id === sequence) renderCounts(data.site_pv, data.site_uv, "ready");
    } catch (_) {
      if (id === sequence) renderCounts("–", "–", "error", "统计服务暂时不可用，请稍后再访问");
    } finally {
      clearTimeout(timeout);
      if (id === sequence) activeRequest = null;
    }
  }

  function num(value) { return '<span class="num">' + value + "</span>"; }

  function renderUptime() {
    var box = document.getElementById("site-uptime");
    var host = box && box.closest("[data-start]");
    if (!host) return;
    var start = new Date(host.getAttribute("data-start")).getTime();
    if (!Number.isFinite(start)) return;
    var minutes = Math.floor(Math.max(0, Date.now() - start) / 60000);
    var hours = Math.floor(minutes / 60);
    var days = Math.floor(hours / 24);
    box.innerHTML = days ? num(days) + " 天 " + num(hours % 24) + " 小时" :
      hours ? num(hours) + " 小时 " + num(minutes % 60) + " 分" : num(minutes) + " 分钟";
  }

  function refresh() {
    renderUptime();
    countVisit();
  }
  window.__countReload = refresh;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", refresh, { once: true });
  else refresh();
  setInterval(renderUptime, 60000);
})();
