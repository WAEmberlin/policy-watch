/**
 * PolicyWatch district map — multi-state legislative and congressional districts.
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
    legislature: true,
  };

  var US_HOUSE_CHAMBERS = {
    'u.s. representative': true,
    'us representative': true,
    'u.s. house': true,
    'us house': true,
  };

  var US_SENATE_CHAMBERS = {
    'u.s. senator': true,
    'us senator': true,
    'u.s. senate': true,
    'us senate': true,
  };

  var PARTY_COLORS = {
    Republican: '#dc2626',
    Democratic: '#2563eb',
    Independent: '#64748b',
    Libertarian: '#ca8a04',
  };

  var DEFAULT_DISTRICT_COLOR = '#94a3b8';
  var DEFAULT_DISTRICT_FILL = '#cbd5e1';

  var STATE_CONFIG = {
    KS: {
      name: 'Kansas',
      center: [38.5, -98.5],
      zoom: 7,
      chambers: {
        house: { file: 'ks-sld-lower.geojson', chamber: 'house', label: 'Kansas House', note: '125 districts' },
        senate: { file: 'ks-sld-upper.geojson', chamber: 'senate', label: 'Kansas Senate', note: '40 districts' },
        us_house: { file: 'ks-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '4 districts' },
        us_senate: { file: 'ks-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    CO: {
      name: 'Colorado',
      center: [39.0, -105.5],
      zoom: 7,
      chambers: {
        house: { file: 'co-sld-lower.geojson', chamber: 'house', label: 'Colorado House', note: '65 districts' },
        senate: { file: 'co-sld-upper.geojson', chamber: 'senate', label: 'Colorado Senate', note: '35 districts' },
        us_house: { file: 'co-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '8 districts' },
        us_senate: { file: 'co-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    AZ: {
      name: 'Arizona',
      center: [34.2, -111.6],
      zoom: 7,
      chambers: {
        house: { file: 'az-sld-lower.geojson', chamber: 'house', label: 'Arizona House', note: '30 districts' },
        senate: { file: 'az-sld-upper.geojson', chamber: 'senate', label: 'Arizona Senate', note: '30 districts' },
        us_house: { file: 'az-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '9 districts' },
        us_senate: { file: 'az-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    UT: {
      name: 'Utah',
      center: [39.3, -111.7],
      zoom: 7,
      chambers: {
        house: { file: 'ut-sld-lower.geojson', chamber: 'house', label: 'Utah House', note: '75 districts' },
        senate: { file: 'ut-sld-upper.geojson', chamber: 'senate', label: 'Utah Senate', note: '29 districts' },
        us_house: { file: 'ut-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '4 districts' },
        us_senate: { file: 'ut-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    ME: {
      name: 'Maine',
      center: [45.3, -69.0],
      zoom: 7,
      chambers: {
        house: { file: 'me-sld-lower.geojson', chamber: 'house', label: 'Maine House', note: '151 districts' },
        senate: { file: 'me-sld-upper.geojson', chamber: 'senate', label: 'Maine Senate', note: '35 districts' },
        us_house: { file: 'me-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '2 districts' },
        us_senate: { file: 'me-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    NE: {
      name: 'Nebraska',
      center: [41.5, -99.8],
      zoom: 7,
      chambers: {
        senate: { file: 'ne-sld-upper.geojson', chamber: 'senate', label: 'Nebraska Legislature', note: '49 districts (unicameral)' },
        us_house: { file: 'ne-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '3 districts' },
        us_senate: { file: 'ne-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    MD: {
      name: 'Maryland',
      center: [39.0, -76.7],
      zoom: 8,
      chambers: {
        house: { file: 'md-sld-lower.geojson', chamber: 'house', label: 'Maryland House', note: '71 legislative districts (141 delegates)' },
        senate: { file: 'md-sld-upper.geojson', chamber: 'senate', label: 'Maryland Senate', note: '47 districts' },
        us_house: { file: 'md-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '8 districts' },
        us_senate: { file: 'md-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    PA: {
      name: 'Pennsylvania',
      center: [40.9, -77.6],
      zoom: 7,
      chambers: {
        house: { file: 'pa-sld-lower.geojson', chamber: 'house', label: 'Pennsylvania House', note: '203 districts' },
        senate: { file: 'pa-sld-upper.geojson', chamber: 'senate', label: 'Pennsylvania Senate', note: '50 districts' },
        us_house: { file: 'pa-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '17 districts' },
        us_senate: { file: 'pa-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    MA: {
      name: 'Massachusetts',
      center: [42.2, -71.8],
      zoom: 8,
      chambers: {
        house: { file: 'ma-sld-lower.geojson', chamber: 'house', label: 'Massachusetts House', note: '160 districts' },
        senate: { file: 'ma-sld-upper.geojson', chamber: 'senate', label: 'Massachusetts Senate', note: '40 districts' },
        us_house: { file: 'ma-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '9 districts' },
        us_senate: { file: 'ma-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    WV: {
      name: 'West Virginia',
      center: [38.7, -80.6],
      zoom: 7,
      chambers: {
        house: { file: 'wv-sld-lower.geojson', chamber: 'house', label: 'West Virginia House', note: '100 districts' },
        senate: { file: 'wv-sld-upper.geojson', chamber: 'senate', label: 'West Virginia Senate', note: '17 districts (34 senators)' },
        us_house: { file: 'wv-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '2 districts' },
        us_senate: { file: 'wv-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    TN: {
      name: 'Tennessee',
      center: [35.8, -86.3],
      zoom: 7,
      chambers: {
        house: { file: 'tn-sld-lower.geojson', chamber: 'house', label: 'Tennessee House', note: '99 districts' },
        senate: { file: 'tn-sld-upper.geojson', chamber: 'senate', label: 'Tennessee Senate', note: '33 districts' },
        us_house: { file: 'tn-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '9 districts' },
        us_senate: { file: 'tn-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    NC: {
      name: 'North Carolina',
      center: [35.5, -79.5],
      zoom: 7,
      chambers: {
        house: { file: 'nc-sld-lower.geojson', chamber: 'house', label: 'North Carolina House', note: '120 districts' },
        senate: { file: 'nc-sld-upper.geojson', chamber: 'senate', label: 'North Carolina Senate', note: '50 districts' },
        us_house: { file: 'nc-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '14 districts' },
        us_senate: { file: 'nc-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    MO: {
      name: 'Missouri',
      center: [38.3, -92.5],
      zoom: 7,
      chambers: {
        house: { file: 'mo-sld-lower.geojson', chamber: 'house', label: 'Missouri House', note: '163 districts' },
        senate: { file: 'mo-sld-upper.geojson', chamber: 'senate', label: 'Missouri Senate', note: '34 districts' },
        us_house: { file: 'mo-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '8 districts' },
        us_senate: { file: 'mo-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
    IA: {
      name: 'Iowa',
      center: [42.0, -93.5],
      zoom: 7,
      chambers: {
        house: { file: 'ia-sld-lower.geojson', chamber: 'house', label: 'Iowa House', note: '100 districts' },
        senate: { file: 'ia-sld-upper.geojson', chamber: 'senate', label: 'Iowa Senate', note: '50 districts' },
        us_house: { file: 'ia-cd119.geojson', chamber: 'us_house', label: 'U.S. House', note: '4 districts' },
        us_senate: { file: 'ia-state.geojson', chamber: 'us_senate', label: 'U.S. Senate', note: 'statewide', statewide: true },
      },
    },
  };

  function normalizeChamber(chamber) {
    var raw = String(chamber || '')
      .trim()
      .toLowerCase()
      .replace(/_/g, ' ');
    if (US_HOUSE_CHAMBERS[raw]) return 'us_house';
    if (US_SENATE_CHAMBERS[raw]) return 'us_senate';
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
    var keys = ['BASENAME', 'SLDL', 'SLDU', 'CD119', 'CD', 'DISTRICT', 'SLDLST'];
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

  function listLegislatorsForChamber(legislators, state, chamber) {
    var targetState = String(state || 'KS').toUpperCase();
    var targetChamber = normalizeChamber(chamber || 'house');
    return (legislators || []).filter(function (leg) {
      return (
        String(leg.state || '').toUpperCase() === targetState &&
        normalizeChamber(leg.chamber) === targetChamber
      );
    });
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
    if (normalized === 'us_house') return 'U.S. House';
    if (normalized === 'us_senate') return 'U.S. Senate';
    return chamber || '';
  }

  function buildPopupHtml(district, legislators, statewide) {
    var districtLabel = statewide
      ? 'Statewide'
      : district
        ? 'District ' + district
        : 'Unknown district';
    if (!legislators.length) {
      return (
        '<div class="district-popup">' +
        '<h3 class="district-popup__title">' +
        districtLabel +
        '</h3>' +
        '<p class="district-popup__empty">No matching legislator found in PolicyWatch data.</p>' +
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

  function buildPanelHtml(district, legislators, statewide) {
    return buildPopupHtml(district, legislators, statewide);
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

  function mergeFederalDelegation(legislators, delegation) {
    var merged = (legislators || []).slice();
    var seen = {};
    merged.forEach(function (leg) {
      if (leg.id) seen[leg.id] = true;
    });
    (delegation || []).forEach(function (member) {
      if (member.id && seen[member.id]) return;
      merged.push(member);
      if (member.id) seen[member.id] = true;
    });
    return merged;
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
    var stateSelect = document.getElementById('map-state-select');
    var subtitleEl = document.getElementById('map-subtitle');
    if (!mapEl) return;

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
    var statewideLegislators = [];
    var selectedLayer = null;
    var legislators = [];
    var activeState = 'KS';
    var activeChamberKey = 'house';
    var activeChamberConfig = null;
    var siteDataLoaded = false;

    function setStatus(message, isError) {
      if (!statusEl) return;
      statusEl.textContent = message || '';
      statusEl.className = isError ? 'district-map-status district-map-status--error' : 'district-map-status';
    }

    function getStateConfig(stateCode) {
      return STATE_CONFIG[String(stateCode || 'KS').toUpperCase()] || STATE_CONFIG.KS;
    }

    function updateSubtitle(stateCode, chamberConfig) {
      if (!subtitleEl || !chamberConfig) return;
      var stateCfg = getStateConfig(stateCode);
      subtitleEl.textContent = 'District Map — ' + chamberConfig.label + ' (' + stateCfg.name + ')';
    }

    function updatePhaseNote(stateCode, chamberKey, chamberConfig) {
      var note = document.getElementById('map-phase-note');
      if (!note || !chamberConfig) return;
      var stateCfg = getStateConfig(stateCode);
      note.textContent =
        'Showing ' +
        chamberConfig.label +
        ' (' +
        (chamberConfig.note || '') +
        ') for ' +
        stateCfg.name +
        '. Click a district for representative details.';
    }

    function setChamberToggleState(stateCode, activeChamberKey) {
      var stateCfg = getStateConfig(stateCode);
      var buttons = document.querySelectorAll('[data-chamber-key]');
      buttons.forEach(function (btn) {
        var key = btn.getAttribute('data-chamber-key');
        var available = !!(stateCfg.chambers && stateCfg.chambers[key]);
        var isActive = key === activeChamberKey;
        btn.className = isActive
          ? 'map-chamber-btn map-chamber-btn--active'
          : available
            ? 'map-chamber-btn'
            : 'map-chamber-btn map-chamber-btn--disabled';
        btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        btn.disabled = !available || isActive;
      });
    }

    function legislatorsForFeature(feature) {
      if (activeChamberConfig && activeChamberConfig.statewide) {
        return statewideLegislators.slice();
      }
      return lookupLegislatorsForFeature(feature.properties, districtIndex);
    }

    function highlightLayer(layer) {
      if (selectedLayer && selectedLayer !== layer) {
        geoLayer.resetStyle(selectedLayer);
      }
      selectedLayer = layer;
      layer.setStyle({ weight: 3, color: '#001f3f', fillOpacity: 0.72 });
      if (layer.bringToFront) layer.bringToFront();
    }

    function showDistrict(district, matchedLegislators, layer) {
      highlightLayer(layer);
      var statewide = !!(activeChamberConfig && activeChamberConfig.statewide);
      var html = buildPanelHtml(district, matchedLegislators, statewide);
      if (panelEl) panelEl.innerHTML = html;
      layer
        .bindPopup(buildPopupHtml(district, matchedLegislators, statewide), {
          maxWidth: 320,
          className: 'district-leaflet-popup',
        })
        .openPopup();
      if (window.PolicyWatchA11y && typeof PolicyWatchA11y.announce === 'function') {
        var name = matchedLegislators.length ? matchedLegislators[0].name : 'No legislator matched';
        PolicyWatchA11y.announce((statewide ? 'Statewide' : 'District ' + district) + ': ' + name);
      }
    }

    function onEachFeature(feature, layer) {
      var district = extractDistrictFromFeature(feature.properties);
      var matchedLegislators = legislatorsForFeature(feature);
      layer.on({
        click: function () {
          showDistrict(district, matchedLegislators, layer);
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
      if (!(activeChamberConfig && activeChamberConfig.statewide)) {
        layer.bindTooltip(district ? 'District ' + district : 'District', {
          sticky: true,
          direction: 'top',
          className: 'district-map-tooltip',
        });
      } else {
        layer.bindTooltip(getStateConfig(activeState).name, {
          sticky: true,
          direction: 'top',
          className: 'district-map-tooltip',
        });
      }
    }

    function styleFeature(feature) {
      return styleForLegislators(legislatorsForFeature(feature));
    }

    function clearMapLayer() {
      if (geoLayer) {
        map.removeLayer(geoLayer);
        geoLayer = null;
      }
      selectedLayer = null;
      if (panelEl) {
        panelEl.innerHTML =
          '<p class="district-popup__empty">Click a district on the map to see representative details.</p>';
      }
    }

    function loadChamber(stateCode, chamberKey) {
      var stateCfg = getStateConfig(stateCode);
      var chamberConfig = (stateCfg.chambers || {})[chamberKey];
      if (!chamberConfig) return;

      activeState = String(stateCode || 'KS').toUpperCase();
      activeChamberKey = chamberKey;
      activeChamberConfig = chamberConfig;

      setChamberToggleState(activeState, activeChamberKey);
      updateSubtitle(activeState, chamberConfig);
      updatePhaseNote(activeState, activeChamberKey, chamberConfig);
      map.setView(stateCfg.center, stateCfg.zoom);

      if (!siteDataLoaded) {
        setStatus('Loading map data…');
        return;
      }

      setStatus('Loading ' + chamberConfig.label + ' boundaries…');
      clearMapLayer();

      var geoUrl = 'data/geo/' + chamberConfig.file;
      loadJson(geoUrl)
        .then(function (geojson) {
          if (chamberConfig.statewide) {
            statewideLegislators = listLegislatorsForChamber(legislators, activeState, chamberConfig.chamber);
            districtIndex = {};
          } else {
            statewideLegislators = [];
            districtIndex = buildDistrictLegislatorIndex(legislators, activeState, chamberConfig.chamber);
          }

          geoLayer = L.geoJSON(geojson, {
            style: styleFeature,
            onEachFeature: onEachFeature,
          }).addTo(map);

          map.fitBounds(geoLayer.getBounds(), { padding: [16, 16] });

          var matched = 0;
          geojson.features.forEach(function (feature) {
            if (legislatorsForFeature(feature).length) matched += 1;
          });

          var unitLabel = chamberConfig.statewide ? 'state' : 'districts';
          setStatus(
            matched +
              ' of ' +
              geojson.features.length +
              ' ' +
              unitLabel +
              ' matched to ' +
              chamberConfig.label +
              ' legislators.'
          );
        })
        .catch(function (err) {
          console.error(err);
          setStatus(
            'Could not load map data for ' +
              chamberConfig.label +
              '. Run scripts/fetch_district_geojson.py to generate GeoJSON.',
            true
          );
          if (panelEl) {
            panelEl.innerHTML =
              '<p class="district-popup__empty">Map data failed to load. See console for details.</p>';
          }
        });
    }

    function defaultChamberForState(stateCode) {
      var chambers = (getStateConfig(stateCode).chambers || {});
      var preferred = ['house', 'senate', 'us_house', 'us_senate'];
      for (var i = 0; i < preferred.length; i++) {
        if (chambers[preferred[i]]) return preferred[i];
      }
      var keys = Object.keys(chambers);
      return keys.length ? keys[0] : 'house';
    }

    if (stateSelect) {
      Object.keys(STATE_CONFIG).forEach(function (code) {
        var option = document.createElement('option');
        option.value = code;
        option.textContent = STATE_CONFIG[code].name;
        if (code === 'KS') option.selected = true;
        stateSelect.appendChild(option);
      });
      stateSelect.addEventListener('change', function () {
        loadChamber(stateSelect.value, defaultChamberForState(stateSelect.value));
      });
    }

    document.querySelectorAll('[data-chamber-key]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.disabled) return;
        loadChamber(stateSelect ? stateSelect.value : activeState, btn.getAttribute('data-chamber-key'));
      });
    });

    setStatus('Loading map data…');
    Promise.all([
      loadJson(typeof policywatchDataUrl === 'function' ? policywatchDataUrl('site_data.json') : 'site_data.json'),
      loadJson('data/federal/delegation.json').catch(function () {
        return [];
      }),
    ])
      .then(function (results) {
        var siteData = results[0];
        legislators = mergeFederalDelegation(
          (siteData.search_index || {}).legislators || [],
          results[1]
        );
        siteDataLoaded = true;
        loadChamber(activeState, activeChamberKey);
      })
      .catch(function (err) {
        console.error(err);
        setStatus('Could not load legislator data from site_data.json.', true);
      });

    window.addEventListener('resize', function () {
      map.invalidateSize();
    });
  }

  global.PolicyWatchDistrictMap = {
    normalizeChamber: normalizeChamber,
    normalizeDistrict: normalizeDistrict,
    extractDistrictFromFeature: extractDistrictFromFeature,
    buildDistrictLegislatorIndex: buildDistrictLegislatorIndex,
    listLegislatorsForChamber: listLegislatorsForChamber,
    lookupLegislatorsForFeature: lookupLegislatorsForFeature,
    init: init,
  };
})(typeof window !== 'undefined' ? window : globalThis);
