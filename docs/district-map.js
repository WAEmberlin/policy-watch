/**
 * CivicWatch district map — Phase 1: Kansas State House (SLD lower).
 * Join logic mirrors src/processing/district_join.py for tests.
 */
(function (global) {
  'use strict';

  var HOUSE_CHAMBERS = {
    representative: true,
    lower: true,
    house: true,
    'state representative': true,
    'state rep': true,
    rep: true,
  };

  var SENATE_CHAMBERS = {
    senator: true,
    upper: true,
    senate: true,
    'state senator': true,
    sen: true,
  };

  var PARTY_COLORS = {
    Republican: '#dc2626',
    Democratic: '#2563eb',
    Independent: '#64748b',
    Libertarian: '#ca8a04',
  };

  var DEFAULT_DISTRICT_COLOR = '#94a3b8';
  var DEFAULT_DISTRICT_FILL = '#cbd5e1';

  function normalizeChamber(chamber) {
    var raw = String(chamber || '')
      .trim()
      .toLowerCase()
      .replace(/_/g, ' ');
    if (HOUSE_CHAMBERS[raw]) return 'house';
    if (SENATE_CHAMBERS[raw]) return 'senate';
    return raw;
  }

  function normalizeDistrict(district) {
    if (district == null) return '';
    var text = String(district).trim();
    if (!text) return '';
    if (/^\d+$/.test(text)) return String(parseInt(text, 10));
    return text;
  }

  function extractDistrictFromFeature(properties) {
    var props = properties || {};
    var keys = ['BASENAME', 'SLDL', 'DISTRICT', 'SLDLST'];
    for (var i = 0; i < keys.length; i++) {
      var value = props[keys[i]];
      if (value != null && value !== '') return normalizeDistrict(value);
    }
    var geoid = String(props.GEOID || '');
    if (geoid.length >= 3 && /^\d{3}$/.test(geoid.slice(-3))) {
      return normalizeDistrict(geoid.slice(-3));
    }
    return '';
  }

  function buildDistrictLegislatorIndex(legislators, state, chamber) {
    var targetState = String(state || 'KS').toUpperCase();
    var targetChamber = normalizeChamber(chamber || 'house');
    var index = {};
    (legislators || []).forEach(function (leg) {
      if (String(leg.state || '').toUpperCase() !== targetState) return;
      if (normalizeChamber(leg.chamber) !== targetChamber) return;
      var district = normalizeDistrict(leg.district);
      if (!district) return;
      if (!index[district]) index[district] = [];
      index[district].push(leg);
    });
    return index;
  }

  function lookupLegislatorsForFeature(properties, index) {
    var district = extractDistrictFromFeature(properties);
    if (!district) return [];
    return (index[district] || []).slice();
  }

  function partyColor(party) {
    return PARTY_COLORS[party] || DEFAULT_DISTRICT_COLOR;
  }

  function partyFill(party) {
    var color = partyColor(party);
    return color + '33';
  }

  function formatChamberLabel(chamber) {
    var normalized = normalizeChamber(chamber);
    if (normalized === 'house') return 'House';
    if (normalized === 'senate') return 'Senate';
    return chamber || '';
  }

  function buildPopupHtml(district, legislators) {
    var districtLabel = district ? 'District ' + district : 'Unknown district';
    if (!legislators.length) {
      return (
        '<div class="district-popup">' +
        '<h3 class="district-popup__title">' +
        districtLabel +
        '</h3>' +
        '<p class="district-popup__empty">No matching legislator found in CivicWatch data.</p>' +
        '</div>'
      );
    }

    var cards = legislators
      .map(function (leg) {
        var meta = [leg.party, formatChamberLabel(leg.chamber)].filter(Boolean).join(' · ');
        var profile =
          leg.url
            ? '<a href="' +
              leg.url +
              '" class="district-popup__link" target="_blank" rel="noopener noreferrer">Official profile →</a>'
            : '';
        var image = leg.image
          ? '<img src="' +
            leg.image +
            '" alt="" class="district-popup__photo" loading="lazy" />'
          : '';
        return (
          '<div class="district-popup__rep">' +
          image +
          '<div class="district-popup__rep-body">' +
          '<strong class="district-popup__name">' +
          (leg.name || 'Unknown') +
          '</strong>' +
          '<p class="district-popup__meta">' +
          meta +
          '</p>' +
          profile +
          '</div></div>'
        );
      })
      .join('');

    return (
      '<div class="district-popup">' +
      '<h3 class="district-popup__title">' +
      districtLabel +
      '</h3>' +
      cards +
      '</div>'
    );
  }

  function buildPanelHtml(district, legislators) {
    return buildPopupHtml(district, legislators);
  }

  function styleForLegislators(legislators) {
    if (!legislators.length) {
      return { color: DEFAULT_DISTRICT_COLOR, fillColor: DEFAULT_DISTRICT_FILL, fillOpacity: 0.45 };
    }
    var party = legislators[0].party;
    return {
      color: partyColor(party),
      fillColor: partyFill(party),
      fillOpacity: 0.55,
      weight: 1.5,
    };
  }

  function loadJson(url) {
    return fetch(url).then(function (res) {
      if (!res.ok) throw new Error('Failed to load ' + url + ' (' + res.status + ')');
      return res.json();
    });
  }

  function setChamberToggleState(activeChamber) {
    var houseBtn = document.getElementById('map-chamber-house');
    var senateBtn = document.getElementById('map-chamber-senate');
    var congressBtn = document.getElementById('map-chamber-congress');
    [houseBtn, senateBtn, congressBtn].forEach(function (btn) {
      if (!btn) return;
      var isActive = btn.dataset.chamber === activeChamber;
      btn.className = isActive
        ? 'map-chamber-btn map-chamber-btn--active'
        : 'map-chamber-btn map-chamber-btn--disabled';
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      btn.disabled = !isActive;
    });
    var note = document.getElementById('map-phase-note');
    if (note) {
      note.textContent =
        activeChamber === 'house'
          ? 'Showing Kansas State House districts (125). Click a district for representative details.'
          : 'Coming soon — additional chambers and states are planned for a later phase.';
    }
  }

  function init() {
    var mapEl = document.getElementById('district-map');
    var panelEl = document.getElementById('district-info-panel');
    var statusEl = document.getElementById('district-map-status');
    if (!mapEl) return;

    setChamberToggleState('house');

    var map = L.map(mapEl, {
      scrollWheelZoom: true,
      tap: true,
    }).setView([38.5, -98.5], 7);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);

    var geoLayer = null;
    var districtIndex = {};
    var selectedLayer = null;

    function setStatus(message, isError) {
      if (!statusEl) return;
      statusEl.textContent = message || '';
      statusEl.className = isError ? 'district-map-status district-map-status--error' : 'district-map-status';
    }

    function highlightLayer(layer) {
      if (selectedLayer && selectedLayer !== layer) {
        geoLayer.resetStyle(selectedLayer);
      }
      selectedLayer = layer;
      layer.setStyle({ weight: 3, color: '#001f3f', fillOpacity: 0.72 });
      if (layer.bringToFront) layer.bringToFront();
    }

    function showDistrict(district, legislators, layer) {
      highlightLayer(layer);
      var html = buildPanelHtml(district, legislators);
      if (panelEl) panelEl.innerHTML = html;
      layer.bindPopup(buildPopupHtml(district, legislators), { maxWidth: 320, className: 'district-leaflet-popup' }).openPopup();
      if (window.CivicWatchA11y && typeof CivicWatchA11y.announce === 'function') {
        var name = legislators.length ? legislators[0].name : 'No legislator matched';
        CivicWatchA11y.announce('District ' + district + ': ' + name);
      }
    }

    function onEachFeature(feature, layer) {
      var district = extractDistrictFromFeature(feature.properties);
      var legislators = lookupLegislatorsForFeature(feature.properties, districtIndex);
      layer.on({
        click: function () {
          showDistrict(district, legislators, layer);
        },
        mouseover: function (e) {
          if (selectedLayer === e.target) return;
          e.target.setStyle({ weight: 2.5, fillOpacity: 0.65 });
        },
        mouseout: function (e) {
          if (selectedLayer === e.target) return;
          geoLayer.resetStyle(e.target);
        },
      });
      layer.bindTooltip(district ? 'District ' + district : 'District', {
        sticky: true,
        direction: 'top',
        className: 'district-map-tooltip',
      });
    }

    function styleFeature(feature) {
      var legislators = lookupLegislatorsForFeature(feature.properties, districtIndex);
      return styleForLegislators(legislators);
    }

    setStatus('Loading map data…');

    Promise.all([loadJson('site_data.json'), loadJson('data/geo/ks-sld-lower.geojson')])
      .then(function (results) {
        var siteData = results[0];
        var geojson = results[1];
        var legislators = ((siteData.search_index || {}).legislators || []).slice();
        districtIndex = buildDistrictLegislatorIndex(legislators, 'KS', 'house');

        geoLayer = L.geoJSON(geojson, {
          style: styleFeature,
          onEachFeature: onEachFeature,
        }).addTo(map);

        map.fitBounds(geoLayer.getBounds(), { padding: [16, 16] });

        var matched = 0;
        geojson.features.forEach(function (feature) {
          if (lookupLegislatorsForFeature(feature.properties, districtIndex).length) matched += 1;
        });

        setStatus(
          matched +
            ' of ' +
            geojson.features.length +
            ' districts matched to Kansas House legislators.'
        );
      })
      .catch(function (err) {
        console.error(err);
        setStatus(
          'Could not load map data. Run scripts/fetch_kansas_district_geojson.py to generate GeoJSON.',
          true
        );
        if (panelEl) {
          panelEl.innerHTML =
            '<p class="district-popup__empty">Map data failed to load. See console for details.</p>';
        }
      });

    window.addEventListener('resize', function () {
      map.invalidateSize();
    });
  }

  global.CivicWatchDistrictMap = {
    normalizeChamber: normalizeChamber,
    normalizeDistrict: normalizeDistrict,
    extractDistrictFromFeature: extractDistrictFromFeature,
    buildDistrictLegislatorIndex: buildDistrictLegislatorIndex,
    lookupLegislatorsForFeature: lookupLegislatorsForFeature,
    init: init,
  };
})(typeof window !== 'undefined' ? window : globalThis);
