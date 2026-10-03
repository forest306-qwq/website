(function () {
  'use strict';
  var box, image, closeButton, opener;
  var background = [];
  var shown = false;
  function build() {
    box = document.createElement('div');
    box.className = 'lightbox';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', '照片预览');
    box.setAttribute('aria-hidden', 'true');
    box.innerHTML = '<button class="lightbox-close" type="button" aria-label="关闭照片预览">×</button><img alt="">';
    document.body.appendChild(box);
    image = box.querySelector('img');
    closeButton = box.querySelector('button');
    box.addEventListener('click', function (event) { if (event.target !== image) close(); });
  }
  function open(link, thumbnail) {
    if (!box) build();
    opener = link;
    image.src = link.href;
    image.alt = thumbnail.alt;
    shown = true;
    background = Array.from(document.body.children).filter(function (el) { return el !== box && el.tagName !== 'SCRIPT'; });
    background = background.map(function (el) { var wasInert = el.inert; el.inert = true; return { el: el, wasInert: wasInert }; });
    box.setAttribute('aria-hidden', 'false');
    document.body.classList.add('lightbox-open');
    box.classList.add('on');
    closeButton.focus();
  }
  function close() {
    if (!shown) return;
    shown = false;
    box.classList.remove('on');
    box.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('lightbox-open');
    background.forEach(function (item) { item.el.inert = item.wasInert; });
    background = [];
    if (opener && opener.isConnected) opener.focus({ preventScroll: true });
    setTimeout(function () { if (!shown) image.removeAttribute('src'); }, 300);
  }
  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    var link = event.target.closest('.photo-grid a');
    if (!link || !link.querySelector('img')) return;
    event.preventDefault();
    open(link, link.querySelector('img'));
  });
  document.addEventListener('keydown', function (event) {
    if (!shown) return;
    if (event.key === 'Escape') { event.preventDefault(); close(); }
    if (event.key === 'Tab') { event.preventDefault(); closeButton.focus(); }
  });
  document.addEventListener('site:before-navigate', close);
})();
