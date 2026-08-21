/**
 * Resolve PolicyWatch JSON URLs.
 * When POLICYWATCH_DATA_BASE (or legacy CIVICWATCH_DATA_BASE) is set
 * (Cloudflare R2), fetch from there; otherwise use same-origin relative paths.
 *
 * On localhost / 127.0.0.1, prefer same-origin docs/ files so local UI preview
 * works even when the R2 bucket CORS policy does not allow localhost.
 * Set window.POLICYWATCH_FORCE_R2 = true to force the remote base while developing.
 */
(function (global) {
  'use strict';

  function isLocalPreviewHost() {
    var host = (global.location && global.location.hostname) || '';
    return host === 'localhost' || host === '127.0.0.1';
  }

  function policywatchDataUrl(path) {
    var forceRemote = global.POLICYWATCH_FORCE_R2 === true;
    var base = String(
      global.POLICYWATCH_DATA_BASE || global.CIVICWATCH_DATA_BASE || ''
    ).replace(/\/+$/, '');
    if (isLocalPreviewHost() && !forceRemote) {
      base = '';
    }
    var rel = String(path || '').replace(/^\/+/, '');
    if (!rel) return base || '';
    return base ? base + '/' + rel : rel;
  }

  function policywatchFetch(path, options) {
    return fetch(policywatchDataUrl(path), options);
  }

  global.policywatchDataUrl = policywatchDataUrl;
  global.policywatchFetch = policywatchFetch;
  // Temporary aliases for any cached pages still calling the old names.
  global.civicwatchDataUrl = policywatchDataUrl;
  global.civicwatchFetch = policywatchFetch;
})(typeof window !== 'undefined' ? window : this);
