/**
 * PolicyWatch shared page shell — site nav, skip link, footer, theme toggle host.
 * Usage: PolicyWatchShell.init({ page: 'hearings' });
 */
(function (global) {
  'use strict';

  var NAV_ITEMS = [
    { id: 'home', label: 'Home', href: 'index.html' },
    { id: 'veterans', label: 'Veteran Legislation', shortLabel: 'Veterans', href: 'veterans.html' },
    { id: 'hearings', label: 'Hearings', href: 'hearings.html' },
    { id: 'live', label: 'Live', href: 'livestreams.html' },
    { id: 'dashboard', label: 'Elections', href: 'dashboard.html' },
    { id: 'legislators', label: 'Legislators', shortLabel: 'Legislators', href: 'legislators.html' },
    { id: 'map', label: 'District Map', shortLabel: 'Map', href: 'district-map.html' },
    { id: 'about', label: 'About', href: 'veterans-impact.html' },
  ];

  var FOOTER_TEXT =
    'PolicyWatch — Tracking legislation for Kansas, Colorado, Arizona, Utah, Maine, Nebraska, Maryland, Pennsylvania, Massachusetts, West Virginia, Tennessee, North Carolina, Missouri, Iowa, and U.S. Congress';

  var STATE_CHIP_OPTIONS = [
    { value: '', label: 'All' },
    { value: 'Federal', label: 'Congress' },
    { value: 'KS', label: 'KS' },
    { value: 'CO', label: 'CO' },
    { value: 'AZ', label: 'AZ' },
    { value: 'UT', label: 'UT' },
    { value: 'ME', label: 'ME' },
    { value: 'NE', label: 'NE' },
    { value: 'MD', label: 'MD' },
    { value: 'PA', label: 'PA' },
    { value: 'MA', label: 'MA' },
    { value: 'WV', label: 'WV' },
    { value: 'TN', label: 'TN' },
    { value: 'NC', label: 'NC' },
    { value: 'MO', label: 'MO' },
    { value: 'IA', label: 'IA' },
  ];

  function injectSkipLink() {
    if (document.querySelector('.cw-skip-link, .skip-link')) return;
    var mainId = document.getElementById('cw-main-content') ? 'cw-main-content' : 'main-content';
    var skip = document.createElement('a');
    skip.href = '#' + mainId;
    skip.className = 'cw-skip-link';
    skip.textContent = 'Skip to main content';
    document.body.insertBefore(skip, document.body.firstChild);
  }

  function buildNavLink(item, currentPage) {
    var a = document.createElement('a');
    a.href = item.href;
    a.className = 'site-nav-link';
    if (item.id === currentPage) {
      a.className += ' site-nav-link--active';
      a.setAttribute('aria-current', 'page');
    }
    var longLabel = document.createElement('span');
    longLabel.className = 'site-nav-link__long';
    longLabel.textContent = item.label;
    a.appendChild(longLabel);
    if (item.shortLabel && item.shortLabel !== item.label) {
      var shortLabel = document.createElement('span');
      shortLabel.className = 'site-nav-link__short';
      shortLabel.textContent = item.shortLabel;
      a.appendChild(shortLabel);
    }
    return a;
  }

  function injectNav(currentPage) {
    var existing = document.getElementById('site-nav');
    if (existing) {
      existing.querySelectorAll('.site-nav-link').forEach(function (link) {
        link.removeAttribute('aria-current');
        link.className = 'site-nav-link';
      });
      NAV_ITEMS.forEach(function (item) {
        var link = existing.querySelector('a[href="' + item.href + '"]');
        if (link && item.id === currentPage) {
          link.className = 'site-nav-link site-nav-link--active';
          link.setAttribute('aria-current', 'page');
        }
      });
      return;
    }

    var nav = document.createElement('nav');
    nav.id = 'site-nav';
    nav.setAttribute('aria-label', 'Main navigation');

    NAV_ITEMS.forEach(function (item) {
      nav.appendChild(buildNavLink(item, currentPage));
    });

    var header =
      document.querySelector('.cw-card-header') ||
      document.querySelector('header.cw-header') ||
      document.querySelector('.card-header.civic-header') ||
      document.querySelector('header.card-header');

    if (header && header.parentNode) {
      header.parentNode.insertBefore(nav, header.nextSibling);
      return;
    }

    var main = document.getElementById('cw-main-content') || document.getElementById('main-content');
    if (main) {
      main.insertBefore(nav, main.firstChild);
    }
  }

  function injectFooter() {
    if (document.getElementById('cw-page-footer')) return;
    var footer = document.createElement('footer');
    footer.id = 'cw-page-footer';
    footer.className = 'text-center text-slate-500 text-sm mt-6 px-4 cw-page-footer';
    footer.textContent = FOOTER_TEXT;

    var existing = document.querySelector('[data-cw-footer-replace]');
    if (existing) {
      existing.replaceWith(footer);
      return;
    }

    var wrapper = document.getElementById('cw-page-wrapper');
    if (wrapper) {
      wrapper.appendChild(footer);
    } else {
      document.body.appendChild(footer);
    }
  }

  function wrapMainContent() {
    var main = document.getElementById('cw-main-content');
    if (!main || main.closest('#cw-page-wrapper')) return;
    var wrapper = document.createElement('div');
    wrapper.id = 'cw-page-wrapper';
    wrapper.className = 'max-w-6xl mx-auto px-4 py-4 cw-page-wrapper';
    main.parentNode.insertBefore(wrapper, main);
    wrapper.appendChild(main);
  }

  function initStateChips(selectId, chipsContainerId) {
    var select = document.getElementById(selectId);
    var container = document.getElementById(chipsContainerId);
    if (!select || !container || container.dataset.initialized) return;

    container.dataset.initialized = 'true';
    container.classList.add('cw-state-chips');
    container.setAttribute('role', 'group');
    container.setAttribute('aria-label', 'Filter by state');

    STATE_CHIP_OPTIONS.forEach(function (opt) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cw-state-chip';
      btn.dataset.state = opt.value;
      btn.textContent = opt.label;
      btn.setAttribute('aria-pressed', opt.value === select.value ? 'true' : 'false');
      btn.addEventListener('click', function () {
        select.value = opt.value;
        container.querySelectorAll('.cw-state-chip').forEach(function (chip) {
          chip.setAttribute('aria-pressed', chip.dataset.state === opt.value ? 'true' : 'false');
        });
        select.dispatchEvent(new Event('change', { bubbles: true }));
      });
      container.appendChild(btn);
    });

    select.addEventListener('change', function () {
      container.querySelectorAll('.cw-state-chip').forEach(function (chip) {
        chip.setAttribute('aria-pressed', chip.dataset.state === select.value ? 'true' : 'false');
      });
    });
  }

  function init(options) {
    options = options || {};
    var page = options.page || document.body.getAttribute('data-cw-page') || 'home';

    injectSkipLink();
    wrapMainContent();
    injectNav(page);
    injectFooter();

    if (global.PolicyWatchTheme && typeof global.PolicyWatchTheme.init === 'function') {
      global.PolicyWatchTheme.init();
    }
    if (global.PolicyWatchA11y && typeof global.PolicyWatchA11y.init === 'function') {
      global.PolicyWatchA11y.init();
    }

    if (options.stateChips) {
      options.stateChips.forEach(function (pair) {
        initStateChips(pair.select, pair.chips);
      });
    }
  }

  global.PolicyWatchShell = {
    init: init,
    initStateChips: initStateChips,
    NAV_ITEMS: NAV_ITEMS,
    FOOTER_TEXT: FOOTER_TEXT,
  };
})(window);

/**
 * Centered loading popup with spinner. Used by feed search, first paint, and
 * other data fetches. Safe to call show() repeatedly to update the label.
 */
(function (global) {
  'use strict';

  var overlay = null;
  var labelEl = null;
  var dialogEl = null;

  function overlayMarkup() {
    return (
      '<div class="cw-loading-dialog" role="status" aria-live="polite" aria-busy="true">' +
        '<div class="cw-loading-spinner" aria-hidden="true"></div>' +
        '<p class="cw-loading-label">Loading…</p>' +
      '</div>'
    );
  }

  function ensure() {
    overlay = document.getElementById('cw-loading-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'cw-loading-overlay';
      overlay.className = 'cw-loading-overlay';
      overlay.setAttribute('role', 'presentation');
      overlay.setAttribute('hidden', '');
      overlay.innerHTML = overlayMarkup();
      document.body.appendChild(overlay);
    }
    overlay.classList.remove('is-visible');
    dialogEl = overlay.querySelector('.cw-loading-dialog');
    labelEl = overlay.querySelector('.cw-loading-label');
    return overlay;
  }

  function show(message) {
    ensure();
    if (labelEl) labelEl.textContent = message || 'Loading…';
    if (dialogEl) dialogEl.setAttribute('aria-busy', 'true');
    overlay.classList.add('cw-loading-overlay--open');
    overlay.removeAttribute('hidden');
    document.documentElement.classList.add('cw-is-loading');
  }

  function hide() {
    ensure();
    if (!overlay) {
      document.documentElement.classList.remove('cw-is-loading');
      return;
    }
    overlay.classList.remove('cw-loading-overlay--open');
    overlay.classList.remove('is-visible');
    overlay.setAttribute('hidden', '');
    if (dialogEl) dialogEl.setAttribute('aria-busy', 'false');
    document.documentElement.classList.remove('cw-is-loading');
  }

  global.PolicyWatchLoading = {
    show: show,
    hide: hide,
  };
})(window);
