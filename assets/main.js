(function () {
  "use strict";
  var activeRequest = null;
  var sequence = 0;
  var base = new URL(document.querySelector('.brand').href).pathname.replace(/index\.html$/, '');
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  var status = document.getElementById('navigation-status');
  var scrollTimer;

  function highlight() {
    var path = location.pathname;
    document.querySelectorAll('.nav-link').forEach(function (link) {
      var target = new URL(link.href).pathname;
      var section = target.replace(/\.html$/, '');
      var home = /\/index\.html$/.test(target);
      var selected = home ? (path === target || path === base) :
        (path === target || path.indexOf(section + '/') === 0);
      link.classList.toggle('is-active', selected);
      if (selected) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  }

  function saveScroll() {
    history.replaceState(Object.assign({}, history.state, { scrollY: window.scrollY }), '', location.href);
  }

  function targetFor(event) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return null;
    var link = event.target.closest('a');
    if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self') || link.closest('.photo-grid')) return null;
    var href = link.getAttribute('href');
    if (!href || href.charAt(0) === '#') return null;
    var url = new URL(link.href);
    if (url.origin !== location.origin || !/^https?:$/.test(url.protocol) || url.pathname.indexOf(base) !== 0) return null;
    if (!/\.html$/.test(url.pathname) && url.pathname !== base) return null;
    if (url.pathname === location.pathname && url.search === location.search) return null;
    return url;
  }

  function runScripts(root) {
    root.querySelectorAll('script[src]').forEach(function (old) {
      var script = document.createElement('script');
      Array.from(old.attributes).forEach(function (attr) { script.setAttribute(attr.name, attr.value); });
      old.replaceWith(script);
    });
  }

  async function navigate(url, push, restoredScroll) {
    var id = ++sequence;
    clearTimeout(scrollTimer);
    if (push) saveScroll();
    if (activeRequest) activeRequest.abort();
    var controller = new AbortController();
    activeRequest = controller;
    var timeout = setTimeout(function () { controller.abort(); }, 10000);
    document.body.dataset.anim = 'in';
    document.body.classList.add('is-loading');
    var current = document.querySelector('.layout');
    current.setAttribute('aria-busy', 'true');
    if (status) status.textContent = '正在加载页面';
    try {
      var response = await fetch(url.href, { credentials: 'same-origin', signal: controller.signal });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      var doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      var next = doc.querySelector('.layout');
      if (!next) throw new Error('Missing layout');
      if (id !== sequence) return;
      clearTimeout(timeout);
      // Keep the current page readable while fetching; animate only once ready.
      document.body.dataset.anim = 'out';
      if (!reducedMotion.matches) await new Promise(function (resolve) { setTimeout(resolve, 220); });
      if (id !== sequence) return;
      document.dispatchEvent(new Event('site:before-navigate'));
      if (push) {
        history.pushState({ scrollY: 0 }, '', url.href);
      }
      current.replaceWith(next);
      // Swap the home background alongside the page during internal navigation.
      var currentBackdrop = document.querySelector('.home-backdrop');
      var nextBackdrop = doc.querySelector('.home-backdrop');
      if (currentBackdrop) currentBackdrop.remove();
      if (nextBackdrop) next.before(nextBackdrop);
      document.title = doc.title;
      var description = doc.querySelector('meta[name="description"]');
      var currentDescription = document.querySelector('meta[name="description"]');
      if (description && currentDescription) currentDescription.content = description.content;
      highlight();
      document.body.dataset.anim = 'in';
      // Update the URL before giscus reads pathname for its discussion mapping.
      runScripts(next);
      var main = next.querySelector('main');
      if (main) main.focus({ preventScroll: true });
      var anchor = url.hash && document.getElementById(decodeURIComponent(url.hash.slice(1)));
      if (anchor && (push || typeof restoredScroll !== 'number')) anchor.scrollIntoView();
      else window.scrollTo(0, push ? 0 : (restoredScroll || 0));
      if (typeof window.__countReload === 'function') window.__countReload();
      if (status) status.textContent = '已打开：' + doc.title;
    } catch (error) {
      if (id !== sequence) return;
      location.assign(url.href);
    } finally {
      clearTimeout(timeout);
      if (id === sequence) {
        activeRequest = null;
        document.body.classList.remove('is-loading');
        document.querySelector('.layout').removeAttribute('aria-busy');
      }
    }
  }

  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  saveScroll();
  highlight();
  document.addEventListener('click', function (event) {
    var url = targetFor(event);
    if (!url) return;
    event.preventDefault();
    navigate(url, true);
  });
  window.addEventListener('popstate', function (event) {
    clearTimeout(scrollTimer);
    navigate(new URL(location.href), false, event.state && event.state.scrollY);
  });
  window.addEventListener('scroll', function () {
    clearTimeout(scrollTimer);
    if (!activeRequest) scrollTimer = setTimeout(saveScroll, 120);
  }, { passive: true });
  window.addEventListener('pageshow', function () { document.body.dataset.anim = 'in'; });
})();
