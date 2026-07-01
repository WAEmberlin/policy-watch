/**
 * CivicWatch district map — Kansas House, Senate, U.S. House, and U.S. Senate.
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
    'state sen': true,
    sen: true,
  };

  var PARTY_COLORS = {
    Republican: '#dc2626',
    Democratic: '#2563eb',
    Democrat: '#2563eb',
    Independent: '#64748b',
    Libertarian: '#ca8a04',
  };

  var DEFAULT_DISTRICT_COLOR = '#94a3b8';
  var DEFAULT_DISTRICT_FILL = '#cbd5e1';

  var CHAMBERS = {
    house: {
      id: 'house',
      label: 'Kansas House',
      geojson: 'data/geo/ks-sld-lower.geojson',
      layer: 'house',
      mapLabel: 'Kansas House districts',
      note: 'Showing Kansas State House districts (125). Click a district for representative details.',
      matchLabel: 'Kansas House legislators',
    },
    senate: {
      id: 'senate',
      label: 'Kansas Senate',
      geojson: 'data/geo/ks-sld-upper.geojson',
      layer: 'senate',
      mapLabel: 'Kansas Senate districts',
      note: 'Showing Kansas State Senate districts (40). Click a district for senator details.',
      matchLabel: 'Kansas Senate legislators',
    },
    congress: {
      id: 'congress',
      label: 'U.S. House',
      geojson: 'data/geo/ks-cd119.geojson',
      layer: 'congress',
      mapLabel: 'Kansas U.S. House districts',
      note: 'Showing Kansas congressional districts (119th Congress). Click a district for U.S. representative details.',
      matchLabel: 'Kansas U.S. representatives',
      federal: true,
    },
    'us-senate': {
      id: 'us-senate',
      label: 'U.S. Senate',
      geojson: 'data/geo/ks-state.geojson',
      layer: 'statewide',
      mapLabel: 'Kansas statewide',
      note: 'Kansas U.S. Senators represent the entire state. Click the map to view senator details.',
      matchLabel: 'Kansas U.S. senators',
      federal: true,
      statewide: true,
    },
  };

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

  function extractDistrictFromFeature(properties, layer) {
    var props = properties || {};
    var layerKey = String(layer || 'house').toLowerCase();

    if (layerKey === 'congress' || layerKey === 'cd119') {
      var cdKeys = ['BASENAME', 'CD119', 'DISTRICT'];
      for (var c = 0; c < cdKeys.length; c++) {
        var cdVal = props[cdKeys[c]];
        if (cdVal != null && cdVal !== '') return normalizeDistrict(cdVal);
      }
      var cdGeoid = String(props.GEOID || '');
      if (cdGeoid.length >= 2 && /^\d{2}$/.test(cdGeoid.slice(-2))) {
        return normalizeDistrict(cdGeoid.slice(-2));
      }
      return '';
    }

    if (layerKey === 'senate' || layerKey === 'upper' || layerKey === 'sldu') {
      var senKeys = ['BASENAME', 'SLDU', 'DISTRICT'];
      for (var s = 0; s < senKeys.length; s++) {
        var senVal = props[senKeys[s]];
        if (senVal != null && senVal !== '') return normalizeDistrict(senVal);
      }
      var senGeoid = String(props.GEOID || '');
      if (senGeoid.length >= 2 && /^\d{2}$/.test(senGeoid.slice(-2))) {
        return normalizeDistrict(senGeoid.slice(-2));
      }
      return '';
    }

    if (layerKey === 'statewide') {
      return 'statewide';
    }

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

  function buildCongressionalIndex(delegation) {
    var index = {};
    ((delegation && delegation.representatives) || []).forEach(function (rep) {
      var district = normalizeDistrict(rep.district);
      if (!district) return;
      if (!index[district]) index[district] = [];
      index[district].push(rep);
    });
    return index;
  }

  function lookupLegislatorsForFeature(properties, index, layer) {
    var district = extractDistrictFromFeature(properties, layer);
    if (!district) return [];
    if (layer === 'statewide') {
      return (index.statewide || []).slice();
    }
    return (index[district] || []).slice();
  }

  function partyColor(party) {
    return PARTY_COLORS[party] || DEFAULT_DISTRICT_COLOR;
  }

  function partyFill(party) {
    return partyColor(party) + '33';
  }

  function formatChamberLabel(chamber) {
    var normalized = normalizeChamber(chamber);
    if (normalized === 'house') return 'House';
    if (normalized === 'senate') return 'Senate';
    return chamber || '';
  }

  function buildPopupHtml(district, legislators, options) {
    options = options || {};
    var districtLabel = options.statewide
      ? 'Kansas (statewide)'
      : district
        ? 'District ' + district
        : 'Unknown district';
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
        var meta = [leg.party, leg.chamber || formatChamberLabel(leg.chamber)].filter(Boolean).join(' · ');
        var profile = leg.url
          ? '<a href="' +
            leg.url +
            '" class="district-popup__link" target="_blank" rel="noopener noreferrer">Official profile →</a>'
          : '';
        var image = leg.image
          ? '<img src="' + leg.image + '" alt="" class="district-popup__photo" loading="lazy" />'
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

  function init() {
    var mapEl = document.getElementById('district-map');
    var panelEl = document.getElementById('district-info-panel');
    var statusEl = document.getElementById('district-map-status');
    if (!mapEl) return;

    var map = L.map(mapEl, { scrollWheelZoom: true, tap: true }).setView([38.5, -98.5], 7);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);

    var siteData = null;
    var geoCache = {};
    var geoLayer = null;
    var districtIndex = {};
    var selectedLayer = null;
    var activeChamber = 'house';
    var activeConfig = CHAMBERS.house;

    function setStatus(message, isError) {
      if (!statusEl) return;
      statusEl.textContent = message || '';
      statusEl.className = isError ? 'district-map-status district-map-status--error' : 'district-map-status';
    }

    function setChamberToggleState(chamberId) {
      Object.keys(CHAMBERS).forEach(function (key) {
        var btn = document.getElementById('map-chamber-' + key);
        if (!btn) return;
        var isActive = key === chamberId;
        btn.className = isActive ? 'map-chamber-btn map-chamber-btn--active' : 'map-chamber-btn';
        btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
      var note = document.getElementById('map-phase-note');
      if (note && CHAMBERS[chamberId]) note.textContent = CHAMBERS[chamberId].note;
      var header = document.querySelector('[data-cw-page="map"] .cw-text-on-header-muted');
      if (header && CHAMBERS[chamberId]) {
        header.textContent = 'District Map — ' + CHAMBERS[chamberId].label;
      }
      mapEl.setAttribute('aria-label', 'Interactive map of ' + (CHAMBERS[chamberId] || {}).mapLabel);
    }

    function buildIndexForChamber(config) {
      if (config.statewide) {
        return { statewide: (siteData.kansas_federal_delegation || {}).senators || [] };
      }
      if (config.federal) {
        return buildCongressionalIndex(siteData.kansas_federal_delegation || {});
      }
      var legislators = ((siteData.search_index || {}).legislators || []).slice();
      return buildDistrictLegislatorIndex(legislators, 'KS', config.layer);
    }

    function highlightLayer(layer) {
      if (selectedLayer && selectedLayer !== layer && geoLayer) {
        geoLayer.resetStyle(selectedLayer);
      }
      selectedLayer = layer;
      layer.setStyle({ weight: 3, color: '#001f3f', fillOpacity: 0.72 });
      if (layer.bringToFront) layer.bringToFront();
    }

    function showDistrict(district, legislators, layer) {
      highlightLayer(layer);
      var html = buildPopupHtml(district, legislators, { statewide: activeConfig.statewide });
      if (panelEl) panelEl.innerHTML = html;
      layer
        .bindPopup(buildPopupHtml(district, legislators, { statewide: activeConfig.statewide }), {
          maxWidth: 320,
          className: 'district-leaflet-popup',
        })
        .openPopup();
      if (window.CivicWatchA11y && typeof CivicWatchA11y.announce === 'function') {
        var name = legislators.length ? legislators[0].name : 'No legislator matched';
        CivicWatchA11y.announce((activeConfig.statewide ? 'Kansas statewide' : 'District ' + district) + ': ' + name);
      }
    }

    function onEachFeature(feature, layer) {
      var district = extractDistrictFromFeature(feature.properties, activeConfig.layer);
      var legislators = lookupLegislatorsForFeature(feature.properties, districtIndex, activeConfig.layer);
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
          if (geoLayer) geoLayer.resetStyle(e.target);
        },
      });
      var tooltip = activeConfig.statewide
        ? 'Kansas — U.S. Senate'
        : district
          ? 'District ' + district
          : 'District';
      layer.bindTooltip(tooltip, { sticky: true, direction: 'top', className: 'district-map-tooltip' });
    }

    function styleFeature(feature) {
      var legislators = lookupLegislatorsForFeature(feature.properties, districtIndex, activeConfig.layer);
      return styleForLegislators(legislators);
    }

    function renderChamber(chamberId) {
      activeChamber = chamberId;
      activeConfig = CHAMBERS[chamberId];
      if (!activeConfig) return Promise.resolve();
      setChamberToggleState(chamberId);
      setStatus('Loading ' + activeConfig.label + '…');
      selectedLayer = null;
      if (panelEl) {
        panelEl.innerHTML = '<p class="district-popup__empty">Click a district on the map to see details.</p>';
      }

      districtIndex = buildIndexForChamber(activeConfig);

      var geoPromise = geoCache[activeConfig.geojson]
        ? Promise.resolve(geoCache[activeConfig.geojson])
        : loadJson(activeConfig.geojson).then(function (data) {
            geoCache[activeConfig.geojson] = data;
            return data;
          });

      return geoPromise
        .then(function (geojson) {
          if (geoLayer) {
            map.removeLayer(geoLayer);
            geoLayer = null;
          }
          geoLayer = L.geoJSON(geojson, {
            style: styleFeature,
            onEachFeature: onEachFeature,
          }).addTo(map);
          map.fitBounds(geoLayer.getBounds(), { padding: [16, 16] });

          var matched = 0;
          geojson.features.forEach(function (feature) {
            if (lookupLegislatorsForFeature(feature.properties, districtIndex, activeConfig.layer).length) {
              matched += 1;
            }
          });
          setStatus(
            matched +
              ' of ' +
              geojson.features.length +
              ' ' +
              (activeConfig.statewide ? 'regions' : 'districts') +
              ' matched to ' +
              activeConfig.matchLabel +
              '.'
          );
        })
        .catch(function (err) {
          console.error(err);
          setStatus('Could not load map data for ' + activeConfig.label + '.', true);
          if (panelEl) {
            panelEl.innerHTML =
              '<p class="district-popup__empty">Map data failed to load. Run scripts/fetch_kansas_district_geojson.py.</p>';
          }
        });
    }

    Object.keys(CHAMBERS).forEach(function (key) {
      var btn = document.getElementById('map-chamber-' + key);
      if (!btn) return;
      btn.addEventListener('click', function () {
        if (activeChamber === key) return;
        renderChamber(key);
      });
    });

    setStatus('Loading map data…');
    Promise.all([loadJson('site_data.json')])
      .then(function (results) {
        siteData = results[0];
        return renderChamber('house');
      })
      .catch(function (err) {
        console.error(err);
        setStatus('Could not load site data.', true);
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
    buildCongressionalIndex: buildCongressionalIndex,
    lookupLegislatorsForFeature: lookupLegislatorsForFeature,
    init: init,
  };
})(typeof window !== 'undefined' ? window : globalThis);
