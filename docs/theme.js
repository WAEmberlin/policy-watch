/**
 * CivicWatch theme system — light, dark, high-contrast.
 * Persists to localStorage (civicwatch-theme). shell.js calls init() after nav injection.
 */
(function (global) {
  'use strict';

  var STORAGE_KEY = 'civicwatch-theme';
  var VALID_THEMES = ['light', 'dark', 'high-contrast'];
  var THEME_LABELS = {
    light: 'Light',
    dark: 'Dark',
    'high-contrast': 'High contrast',
  };
  var toggleMounted = false;

  function normalizeTheme(name) {
    return VALID_THEMES.indexOf(name) !== -1 ? name : null;
  }

  function getSystemTheme() {
    if (global.matchMedia && global.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }

  function getStoredTheme() {
    try {
      return normalizeTheme(localStorage.getItem(STORAGE_KEY));
    } catch (_err) {
      return null;
    }
  }

  function getTheme() {
    return normalizeTheme(document.documentElement.getAttribute('data-theme')) || 'light';
  }

  function applyTheme(name) {
    var theme = normalizeTheme(name) || getSystemTheme();
    document.documentElement.setAttribute('data-theme', theme);
    if (document.body) {
      document.body.classList.add('cw-themed');
    }
    syncToggleUI(theme);
    return theme;
  }

  function persistTheme(name) {
    try {
      localStorage.setItem(STORAGE_KEY, name);
    } catch (_err) {
      /* private mode / quota */
    }
  }

  function setTheme(name) {
    var theme = normalizeTheme(name);
    if (!theme) {
      return getTheme();
    }
    applyTheme(theme);
    persistTheme(theme);
    return theme;
  }

  function getPreferredTheme() {
    return getStoredTheme() || getSystemTheme();
  }

  function syncToggleUI(theme) {
    var group = document.getElementById('civicwatch-theme-toggle');
    if (!group) return;
    var options = group.querySelectorAll('[role="radio"]');
    for (var i = 0; i < options.length; i++) {
      var opt = options[i];
      var selected = opt.getAttribute('data-theme-value') === theme;
      opt.setAttribute('aria-checked', selected ? 'true' : 'false');
      opt.tabIndex = selected ? 0 : -1;
    }
  }

  function onRadioKeydown(event, group, btn, themeName) {
    var radios = Array.prototype.slice.call(group.querySelectorAll('[role="radio"]'));
    var currentIndex = radios.indexOf(btn);
    var nextIndex = currentIndex;

    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      nextIndex = (currentIndex + 1) % radios.length;
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      nextIndex = (currentIndex - 1 + radios.length) % radios.length;
    } else if (event.key === ' ' || event.key === 'Enter') {
      event.preventDefault();
      setTheme(themeName);
      return;
    } else {
      return;
    }

    radios[nextIndex].focus();
    setTheme(radios[nextIndex].getAttribute('data-theme-value'));
  }

  function buildToggle(host) {
    if (!host || document.getElementById('civicwatch-theme-toggle')) return;

    host.innerHTML = '';
    host.classList.add('cw-theme-toggle-host');

    var group = document.createElement('div');
    group.id = 'civicwatch-theme-toggle';
    group.className = 'cw-theme-segmented';
    group.setAttribute('role', 'radiogroup');
    group.setAttribute('aria-label', 'Color theme');

    VALID_THEMES.forEach(function (themeName, index) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cw-theme-segmented__option';
      btn.setAttribute('role', 'radio');
      btn.setAttribute('data-theme-value', themeName);
      btn.setAttribute('aria-checked', 'false');
      btn.textContent = THEME_LABELS[themeName];
      btn.tabIndex = index === 0 ? 0 : -1;

      btn.addEventListener('click', function () {
        setTheme(themeName);
      });

      btn.addEventListener('keydown', function (event) {
        onRadioKeydown(event, group, btn, themeName);
      });

      group.appendChild(btn);
    });

    host.appendChild(group);
    syncToggleUI(getTheme());
    toggleMounted = true;
  }

  function findToggleHost() {
    return (
      document.getElementById('cw-theme-toggle') ||
      document.querySelector('[data-cw-theme-toggle]')
    );
  }

  function mountToggle() {
    if (toggleMounted) {
      syncToggleUI(getTheme());
      return;
    }

    var host = findToggleHost();
    if (host) {
      buildToggle(host);
      return;
    }

    host = document.createElement('div');
    host.setAttribute('data-cw-theme-toggle', '');
    host.className = 'cw-theme-toggle-host cw-theme-toggle-host--fixed';
    document.body.appendChild(host);
    buildToggle(host);
  }

  function init() {
    applyTheme(getPreferredTheme());
    mountToggle();
  }

  function toggleTheme() {
    var current = getTheme();
    var next = current === 'light' ? 'dark' : current === 'dark' ? 'high-contrast' : 'light';
    setTheme(next);
  }

  /* Apply before paint to reduce flash */
  applyTheme(getStoredTheme() || getSystemTheme());

  global.CivicWatchTheme = {
    init: init,
    setTheme: setTheme,
    getTheme: getTheme,
    toggle: toggleTheme,
    apply: applyTheme,
    getPreferred: getPreferredTheme,
    THEMES: VALID_THEMES.slice(),
  };
})(window);
