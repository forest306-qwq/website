/* 自建访问统计；数据保存在服务器，两个域名共用 Cookie 和总数。 */
(function () {
  "use strict";
  if (window.__countReload) return;
  var lastPage;
  var sequence = 0;
  var queue = Promise.resolve();

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


  async function sendVisit(event) {
    for (var attempt = 0; attempt < 2; attempt++) {
      var controller = new AbortController();
      var timeout = setTimeout(function () { controller.abort(); }, 8000);
      try {
        var response = await fetch("/api/site-counter", {
          method: "POST",
          credentials: "same-origin",
          cache: "no-store",
          headers: { "Content-Type": "application/json", "X-Counter-Request": "1" },
          body: JSON.stringify({ event: event }),
          signal: controller.signal
        });
        if (!response.ok) throw new Error("Counter HTTP " + response.status);
        var result = await response.json();
        var data = result.data;
        if (!result.success || !data || ![data.site_pv, data.site_uv].every(function (value) {
          return /^\d+$/.test(String(value)) && Number.isSafeInteger(Number(value));
        })) throw new Error("Invalid counter response");
        return data;
      } catch (error) {
        if (attempt === 1) throw error;
      } finally {
        clearTimeout(timeout);
      }
    }
  }

  function countVisit() {
    var page = location.pathname;
    if (page === lastPage) return;
    lastPage = page;
    if (location.protocol === "file:" || /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname)) {
      renderCounts("–", "–", "preview", "本地预览不计入访问统计");
      return;
    }
    if (!/^(www\.)?nwuc\.cn$/.test(location.hostname)) {
      renderCounts("–", "–", "preview", "访问 nwuc.cn 查看站点统计");
      return;
    }
    var id = ++sequence;
    var event = crypto.randomUUID();
    renderCounts("…", "…", "loading", "正在读取访问统计");
    // Serialize navigation events so the first response can establish the shared cookie.
    queue = queue.then(function () { return sendVisit(event); }).then(function (data) {
      if (id === sequence) renderCounts(data.site_pv, data.site_uv, "ready", "本站服务器统计；访客数按浏览器 Cookie 去重");
    }).catch(function () {
      if (id === sequence) renderCounts("–", "–", "error", "统计服务暂不可用，请稍后刷新");
    });
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
