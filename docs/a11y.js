/**
 * CivicWatch accessibility helpers — skip link and live region announcements.
 */
(function (global) {
  'use strict';

  function getMainTarget() {
    return document.getElementById('cw-main-content') || document.getElementById('main-content');
  }

  function ensureLiveRegion() {
    var region = document.getElementById('a11y-live-region');
    if (region) return region;
    region = document.createElement('div');
    region.id = 'a11y-live-region';
    region.className = 'sr-only';
    region.setAttribute('aria-live', 'polite');
    region.setAttribute('aria-atomic', 'true');
    region.setAttribute('role', 'status');
    document.body.insertBefore(region, document.body.firstChild.nextSibling);
    return region;
  }

  function announce(message) {
    if (!message) return;
    var region = ensureLiveRegion();
    region.textContent = '';
    window.setTimeout(function () {
      region.textContent = message;
    }, 50);
  }

  function initSkipLink() {
    var skip = document.querySelector('.cw-skip-link, .skip-link');
    var main = getMainTarget();
    if (!skip || !main) return;

    skip.addEventListener('click', function (e) {
      e.preventDefault();
      if (!main.hasAttribute('tabindex')) {
        main.setAttribute('tabindex', '-1');
      }
      main.focus({ preventScroll: false });
      main.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  function init() {
    ensureLiveRegion();
    initSkipLink();
  }

  global.CivicWatchA11y = {
    init: init,
    announce: announce,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
