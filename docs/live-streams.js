/**
 * CivicWatch Live Streams — loads config + live status, drives embeds and Live Now bar.
 */
(function () {
  'use strict';

  var liveStreams = [];
  var stateFloorStream = {};

  function mergeStreamConfig(staticStream, liveInfo) {
    var merged = {
      id: staticStream.id,
      title: staticStream.title,
      jurisdiction: staticStream.jurisdiction,
      state: staticStream.state,
      type: staticStream.type,
      targetId: staticStream.targetId,
      tabPane: staticStream.tabPane,
      youtubeUrl: staticStream.youtubeUrl || staticStream.externalUrl || '',
      embedUrl: staticStream.embedUrl || '',
      isLive: false,
    };
    if (liveInfo && liveInfo.isLive && liveInfo.embedUrl) {
      merged.isLive = true;
      merged.embedUrl = liveInfo.embedUrl;
      merged.liveTitle = liveInfo.title || '';
      merged.videoId = liveInfo.videoId || '';
    }
    return merged;
  }

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
        placeholder.textContent = stream.isLive
          ? '🔴 Live now — click Play here'
          : 'Click Play here to watch on CivicWatch';
      }
    });
    document.querySelectorAll('.play-here-btn[data-stream-id]').forEach(function (btn) {
      var id = btn.getAttribute('data-stream-id');
      var stream = liveStreams.filter(function (s) { return s.id === id; })[0];
      var hasEmbed = stream && stream.embedUrl;
      btn.disabled = !hasEmbed;
      btn.title = hasEmbed
        ? 'Load the stream in the player below without leaving CivicWatch'
        : 'No embed configured for this stream yet';
      if (stream && stream.isLive) {
        btn.classList.add('btn-danger');
        btn.classList.remove('btn-primary');
        btn.textContent = '▶ Play live';
      }
    });
  }

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
      link.addEventListener('click', function () {
        goToTarget(stream.targetId);
        setTimeout(function () {
          var wrapper = document.querySelector('.embed-wrapper[data-stream-id="' + stream.id + '"]');
          if (wrapper) loadEmbedInWrapper(wrapper, { autoplay: true, force: true });
        }, 300);
      });
      alert.appendChild(link);
    });
    container.appendChild(alert);
  }

  function goToTarget(targetId) {
    var el = document.getElementById(targetId);
    if (!el) return;
    var mainPane = el.closest('[id^="pane-"]');
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

  function loadEmbedInWrapper(wrapper, options) {
    options = options || {};
    var src = (wrapper.getAttribute('data-embed-src') || '').trim();
    var iframe = wrapper.querySelector('iframe');
    if (!iframe || !src) return false;
    var currentSrc = iframe.getAttribute('src') || '';
    if (currentSrc && !options.force) return false;
    if (options.autoplay && src.indexOf('youtube.com') !== -1 && src.indexOf('autoplay=') === -1) {
      src += (src.indexOf('?') === -1 ? '?' : '&') + 'autoplay=1&playsinline=1';
    }
    iframe.src = src;
    var placeholder = wrapper.querySelector('.embed-placeholder');
    if (placeholder) placeholder.style.display = 'none';
    return true;
  }

  function initPlayHereButtons() {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('.play-here-btn');
      if (!btn || btn.disabled) return;
      var streamId = btn.getAttribute('data-stream-id');
      if (!streamId) return;
      var wrapper = document.querySelector('.embed-wrapper[data-stream-id="' + streamId + '"]');
      if (!wrapper) return;
      if (loadEmbedInWrapper(wrapper, { autoplay: true, force: true })) {
        wrapper.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    });
  }

  function initAccordionLazyLoad() {
    document.addEventListener('shown.bs.collapse', function (e) {
      var target = e.target;
      var wrapper = target.querySelector('.embed-wrapper[data-embed-src]');
      if (wrapper) loadEmbedInWrapper(wrapper);
    });
  }

  function loadConfigs() {
    var configPromise = fetch('live-streams-config.json').then(function (r) {
      if (!r.ok) throw new Error('live-streams-config.json missing');
      return r.json();
    });
    var statusPromise = fetch('live_status.json').then(function (r) {
      return r.ok ? r.json() : { streams: {} };
    }).catch(function () { return { streams: {} }; });

    return Promise.all([configPromise, statusPromise]).then(function (results) {
      var config = results[0];
      var status = results[1];
      stateFloorStream = config.state_floor_stream || {};
      var liveMap = status.streams || {};
      liveStreams = (config.streams || []).map(function (s) {
        return mergeStreamConfig(s, liveMap[s.id]);
      });
    });
  }

  function init() {
    loadConfigs().then(function () {
      applyConfigToPage();
      buildLiveNowBar();
      initAccordionLazyLoad();
      initPlayHereButtons();
    }).catch(function (err) {
      console.error('Live streams config failed to load:', err);
      var container = document.getElementById('live-now-bar');
      if (container) {
        container.innerHTML = '<p class="small text-muted mb-0">Live stream config unavailable.</p>';
      }
    });
  }

  window.CivicWatchLiveStreams = {
    goToTarget: goToTarget,
    loadEmbedInWrapper: loadEmbedInWrapper,
    getStateFloorStreamId: function (state) {
      return stateFloorStream[state] || stateFloorStream.Federal || '';
    },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
