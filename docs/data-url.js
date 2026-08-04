/**
 * Resolve PolicyWatch JSON URLs.
 * When POLICYWATCH_DATA_BASE (or legacy CIVICWATCH_DATA_BASE) is set
 * (Cloudflare R2), fetch from there; otherwise use same-origin relative paths.
 */
(function (global) {
  'use strict';

  function policywatchDataUrl(path) {
    var base = String(
      global.POLICYWATCH_DATA_BASE || global.CIVICWATCH_DATA_BASE || ''
    ).replace(/\/+$/, '');
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
