/**
 * Resolve CivicWatch JSON URLs.
 * When CIVICWATCH_DATA_BASE is set (Cloudflare R2), fetch from there;
 * otherwise use same-origin relative paths (local / Pages fallback).
 */
(function (global) {
  'use strict';

  function civicwatchDataUrl(path) {
    var base = String(global.CIVICWATCH_DATA_BASE || '').replace(/\/+$/, '');
    var rel = String(path || '').replace(/^\/+/, '');
    if (!rel) return base || '';
    return base ? base + '/' + rel : rel;
  }

  function civicwatchFetch(path, options) {
    return fetch(civicwatchDataUrl(path), options);
  }

  global.civicwatchDataUrl = civicwatchDataUrl;
  global.civicwatchFetch = civicwatchFetch;
})(typeof window !== 'undefined' ? window : this);
