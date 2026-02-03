/**
 * CivicWatch Live Streams — static-site live stream config and behavior.
 *
 * No scraping, no backend, no API keys. Update the liveStreams config below to
 * mark streams as live (isLive: true) and set embed URLs. When a stream is live,
 * it appears in the "Live Now" bar and the embed/placeholder updates accordingly.
 *
 * To add a new stream: add an object to liveStreams with id, title, jurisdiction,
 * type, isLive, embedUrl, and targetId. Ensure the page has an element with
 * data-stream-id="<id>" (for embed) and an element with id="<targetId>" (for Live Now link).
 */

(function () {
  'use strict';

  /**
   * Central configuration for all streams.
   * — id: unique key; must match data-stream-id on the page and be used for targetId where applicable.
   * — title: display name (e.g. in Live Now bar).
   * — jurisdiction: "kansas" | "us-house" | "us-senate".
   * — type: "floor" | "committee".
   * — isLive: set to true when this stream is currently live; false otherwise. Manually update when sessions start/end.
   * — embedUrl: full URL for the iframe src (YouTube, KanView, House.gov, Senate.gov). Leave "" if no embed.
   * — targetId: DOM id of the section or accordion panel to scroll to when user clicks this stream in Live Now.
   */
  var liveStreams = [
    // ——— Kansas Legislature ———
    { id: 'kansas-house-floor', title: 'Kansas House Floor', jurisdiction: 'kansas', type: 'floor', isLive: false, embedUrl: 'https://www.youtube.com/embed/live_stream?channel=UC_0NO-Pb96CFABvxDwXAq8A', targetId: 'kansas-house-floor' },
    { id: 'kansas-senate-floor', title: 'Kansas Senate Floor', jurisdiction: 'kansas', type: 'floor', isLive: false, embedUrl: 'https://www.youtube.com/embed/live_stream?channel=UC_0NO-Pb96CFABvxDwXAq8A', targetId: 'kansas-senate-floor' },
    { id: 'ks-house-judiciary', title: 'Kansas House Judiciary', jurisdiction: 'kansas', type: 'committee', isLive: false, embedUrl: '', targetId: 'ks-house-judiciary' },
    { id: 'ks-house-judiciary-civil', title: 'Kansas House Judiciary — Civil Law', jurisdiction: 'kansas', type: 'committee', isLive: false, embedUrl: '', targetId: 'ks-house-judiciary-civil' },
    { id: 'ks-house-judiciary-criminal', title: 'Kansas House Judiciary — Criminal Law', jurisdiction: 'kansas', type: 'committee', isLive: false, embedUrl: '', targetId: 'ks-house-judiciary-criminal' },
    { id: 'ks-house-appropriations', title: 'Kansas House Appropriations', jurisdiction: 'kansas', type: 'committee', isLive: false, embedUrl: '', targetId: 'ks-house-appropriations' },
    { id: 'ks-house-elections', title: 'Kansas House Elections', jurisdiction: 'kansas', type: 'committee', isLive: false, embedUrl: '', targetId: 'ks-house-elections' },
    { id: 'ks-senate-judiciary', title: 'Kansas Senate Judiciary', jurisdiction: 'kansas', type: 'committee', isLive: false, embedUrl: '', targetId: 'ks-senate-judiciary' },
    { id: 'ks-senate-ways-means', title: 'Kansas Senate Ways & Means', jurisdiction: 'kansas', type: 'committee', isLive: false, embedUrl: '', targetId: 'ks-senate-ways-means' },
    { id: 'ks-senate-education', title: 'Kansas Senate Education', jurisdiction: 'kansas', type: 'committee', isLive: false, embedUrl: '', targetId: 'ks-senate-education' },
    // ——— US House ———
    { id: 'us-house-floor', title: 'US House Floor', jurisdiction: 'us-house', type: 'floor', isLive: false, embedUrl: 'https://live.house.gov/', targetId: 'house-floor-section' },
    { id: 'us-house-judiciary', title: 'US House Judiciary Committee', jurisdiction: 'us-house', type: 'committee', isLive: false, embedUrl: '', targetId: 'house-judiciary' },
    { id: 'us-house-oversight', title: 'US House Oversight & Accountability', jurisdiction: 'us-house', type: 'committee', isLive: false, embedUrl: '', targetId: 'house-oversight' },
    { id: 'us-house-armed', title: 'US House Armed Services', jurisdiction: 'us-house', type: 'committee', isLive: false, embedUrl: '', targetId: 'house-armed' },
    { id: 'us-house-energy', title: 'US House Energy & Commerce', jurisdiction: 'us-house', type: 'committee', isLive: false, embedUrl: '', targetId: 'house-energy' },
    { id: 'us-house-waysmeans', title: 'US House Ways & Means', jurisdiction: 'us-house', type: 'committee', isLive: false, embedUrl: '', targetId: 'house-waysmeans' },
    // ——— US Senate ———
    { id: 'us-senate-floor', title: 'US Senate Floor', jurisdiction: 'us-senate', type: 'floor', isLive: false, embedUrl: 'https://www.senate.gov/floor/', targetId: 'senate-floor-section' },
    { id: 'us-senate-judiciary', title: 'US Senate Judiciary', jurisdiction: 'us-senate', type: 'committee', isLive: false, embedUrl: '', targetId: 'senate-judiciary' },
    { id: 'us-senate-commerce', title: 'US Senate Commerce', jurisdiction: 'us-senate', type: 'committee', isLive: false, embedUrl: '', targetId: 'senate-commerce' },
    { id: 'us-senate-armed', title: 'US Senate Armed Services', jurisdiction: 'us-senate', type: 'committee', isLive: false, embedUrl: '', targetId: 'senate-armed' },
    { id: 'us-senate-finance', title: 'US Senate Finance', jurisdiction: 'us-senate', type: 'committee', isLive: false, embedUrl: '', targetId: 'senate-finance' }
  ];

  /**
   * Apply config to page: set data-embed-src, update placeholder to "🔴 Live" or "Not Live".
   * Floor iframes are NOT loaded here — they load when their tab is first shown (see initFloorLazyLoad).
   */
  function applyConfigToPage() {
    var wrappers = document.querySelectorAll('.embed-wrapper[data-stream-id]');
    var byId = {};
    for (var i = 0; i < wrappers.length; i++) {
      var id = wrappers[i].getAttribute('data-stream-id');
      if (id) byId[id] = wrappers[i];
    }
    liveStreams.forEach(function (stream) {
      var wrapper = byId[stream.id];
      if (!wrapper) return;
      wrapper.setAttribute('data-embed-src', stream.embedUrl || '');
      var placeholder = wrapper.querySelector('.embed-placeholder');
      if (placeholder) {
        placeholder.textContent = stream.isLive ? '🔴 Live' : 'Not Live';
      }
    });
  }

  /**
   * Build Live Now bar: only show streams where isLive === true.
   * If none are live, show graceful empty state: "No hearings live at this time."
   */
  function buildLiveNowBar() {
    var container = document.getElementById('live-now-bar');
    if (!container) return;
    var live = liveStreams.filter(function (s) { return s.isLive === true; });
    container.innerHTML = '';
    if (live.length === 0) {
      var empty = document.createElement('p');
      empty.className = 'small text-muted mb-0 mb-md-3';
      empty.setAttribute('role', 'status');
      empty.textContent = 'No hearings live at this time.';
      container.appendChild(empty);
      container.hidden = false;
      return;
    }
    container.hidden = false;
    var alert = document.createElement('div');
    alert.className = 'alert alert-success d-flex flex-wrap align-items-center gap-2 mb-0 mb-md-3 live-now-bar';
    alert.setAttribute('role', 'status');
    var badge = document.createElement('span');
    badge.className = 'badge bg-danger rounded-pill text-white';
    badge.textContent = 'Live Now';
    alert.appendChild(badge);
    live.forEach(function (stream, i) {
      if (i > 0) {
        var sep = document.createElement('span');
        sep.className = 'text-muted';
        sep.textContent = '·';
        alert.appendChild(sep);
      }
      var link = document.createElement('button');
      link.type = 'button';
      link.className = 'btn btn-link btn-sm p-0 text-decoration-none';
      link.textContent = stream.title;
      link.addEventListener('click', function () { goToTarget(stream.targetId); });
      alert.appendChild(link);
    });
    container.appendChild(alert);
  }

  /**
   * Activate main tab (Kansas / US House / US Senate), open subtab if needed, expand accordion if needed, scroll to target.
   */
  function goToTarget(targetId) {
    var el = document.getElementById(targetId);
    if (!el) return;
    var mainPane = el.closest('#pane-kansas, #pane-house, #pane-senate');
    if (mainPane) {
      var tabButton = document.querySelector('[data-bs-target="#' + mainPane.id + '"]');
      if (tabButton && window.bootstrap && bootstrap.Tab) {
        new bootstrap.Tab(tabButton).show();
      }
    }
    var subTabContent = el.closest('#kansasSubTabContent, #houseSubTabContent, #senateSubTabContent');
    if (subTabContent) {
      var panes = subTabContent.querySelectorAll('.tab-pane[id]');
      for (var i = 0; i < panes.length; i++) {
        if (panes[i].contains(el)) {
          var subTabBtn = document.querySelector('[data-bs-target="#' + panes[i].id + '"]');
          if (subTabBtn && window.bootstrap && bootstrap.Tab) {
            new bootstrap.Tab(subTabBtn).show();
          }
          break;
        }
      }
    }
    var collapse = el.closest('.accordion-collapse');
    if (collapse) {
      var accordionButton = document.querySelector('[data-bs-target="#' + collapse.id + '"]');
      if (accordionButton && window.bootstrap && bootstrap.Collapse) {
        var c = bootstrap.Collapse.getOrCreateInstance(collapse);
        if (!collapse.classList.contains('show')) c.show();
      }
    }
    setTimeout(function () { el.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, 150);
  }

  /**
   * Load iframe inside a wrapper (set src from data-embed-src, hide placeholder).
   */
  function loadEmbedInWrapper(wrapper) {
    var src = (wrapper.getAttribute('data-embed-src') || '').trim();
    var iframe = wrapper.querySelector('iframe');
    if (!iframe || !src) return;
    if (iframe.src) return;
    iframe.src = src;
    var placeholder = wrapper.querySelector('.embed-placeholder');
    if (placeholder) placeholder.style.display = 'none';
  }

  /**
   * Lazy-load iframe when accordion panel is expanded. Single delegated listener.
   */
  function initAccordionLazyLoad() {
    document.addEventListener('shown.bs.collapse', function (e) {
      var target = e.target;
      var wrapper = target.querySelector('.embed-wrapper[data-embed-src]');
      if (wrapper) loadEmbedInWrapper(wrapper);
    });
  }

  /**
   * Lazy-load floor iframes only when their tab pane is first shown (saves initial load).
   * Listens to both main-tab and subtab shown so US House/Senate floor load when user switches main tab.
   */
  function initFloorLazyLoad() {
    function loadVisibleFloorInPane(pane) {
      if (!pane) return;
      var wrapper = pane.querySelector('.embed-wrapper[data-embed-src]');
      if (wrapper && !wrapper.closest('.accordion-collapse')) loadEmbedInWrapper(wrapper);
    }
    var subTabContents = document.querySelectorAll('#kansasSubTabContent, #houseSubTabContent, #senateSubTabContent');
    subTabContents.forEach(function (content) {
      var panes = content.querySelectorAll('.tab-pane[id]');
      panes.forEach(function (pane) {
        var wrapper = pane.querySelector('.embed-wrapper[data-embed-src]');
        if (!wrapper || wrapper.closest('.accordion-collapse')) return;
        var tab = document.querySelector('[data-bs-target="#' + pane.id + '"]');
        if (!tab) return;
        tab.addEventListener('shown.bs.tab', function () { loadEmbedInWrapper(wrapper); }, { once: true });
      });
    });
    document.querySelectorAll('#tab-kansas, #tab-house, #tab-senate').forEach(function (mainTab) {
      mainTab.addEventListener('shown.bs.tab', function () {
        var paneId = mainTab.getAttribute('data-bs-target').replace('#', '');
        var mainPane = document.getElementById(paneId);
        if (!mainPane) return;
        var visible = mainPane.querySelector('.tab-pane.show.active');
        loadVisibleFloorInPane(visible);
      });
    });
    var initialMain = document.querySelector('#mainTabContent .tab-pane.show.active');
    if (initialMain) {
      var initialSub = initialMain.querySelector('.tab-pane.show.active');
      loadVisibleFloorInPane(initialSub);
    }
  }

  function init() {
    applyConfigToPage();
    buildLiveNowBar();
    initAccordionLazyLoad();
    initFloorLazyLoad();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
