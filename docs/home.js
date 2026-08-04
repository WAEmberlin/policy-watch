/**
 * PolicyWatch homepage UI — live strip, state snapshots, filters, feed cards.
 */
const PolicyWatchHome = (() => {
    'use strict';

    const STATE_CHIPS = [
        { value: '', label: 'All' },
        { value: 'Federal', label: 'Federal' },
        { value: 'KS', label: 'KS' },
        { value: 'CO', label: 'CO' },
        { value: 'AZ', label: 'AZ' },
        { value: 'UT', label: 'UT' },
        { value: 'ME', label: 'ME' },
        { value: 'NE', label: 'NE' },
        { value: 'MD', label: 'MD' },
        { value: 'PA', label: 'PA' },
    ];

    const STATE_NAMES = {
        KS: 'Kansas', CO: 'Colorado', AZ: 'Arizona', UT: 'Utah', ME: 'Maine', NE: 'Nebraska', MD: 'Maryland', PA: 'Pennsylvania', Federal: 'U.S. Congress',
    };

    const META_SOURCE_PATTERNS = [/congress\.gov api/i, /openstates/i, /data sync/i, /api feed/i];

    // Align with config/states.yaml topic_dashboards.veterans keywords
    const VETERANS_STRONG_KEYWORDS = [
        'veteran', 'veterans', 'military', 'armed forces', 'armed services',
        'national guard', 'servicemember', 'service member', 'veterans affairs',
    ];

    const VETERANS_DEFENSE_PHRASES = [
        'national defense', 'department of defense', 'defense authorization',
        'defense budget', 'foreign military', 'defense articles', 'defense spending',
        'military sale', 'military forces', 'military personnel', 'military service',
        'military academy', 'military installation',
    ];

    const VETERANS_TOPIC_PATTERN = /veteran|military|armed forces|armed services|national guard/;

    const VETERAN_IMPACT_STYLES = {
        red: 'bg-red-50 border-red-200 hover:border-red-300',
        yellow: 'bg-amber-50 border-amber-200 hover:border-amber-300',
        green: 'bg-green-50 border-green-200 hover:border-green-300',
    };

    const VETERAN_IMPACT_BADGE = {
        red: 'bg-red-100 text-red-900 border-red-200',
        yellow: 'bg-amber-100 text-amber-900 border-amber-200',
        green: 'bg-green-100 text-green-900 border-green-200',
    };

    const ACTION_BADGE_STYLES = {
        passed: 'bg-green-100 text-green-800 border-green-200',
        enacted: 'bg-green-100 text-green-800 border-green-200',
        vetoed: 'bg-orange-100 text-orange-800 border-orange-200',
        died: 'bg-slate-100 text-slate-600 border-slate-200',
        failed: 'bg-slate-100 text-slate-600 border-slate-200',
        vote: 'bg-blue-100 text-blue-800 border-blue-200',
        referred: 'bg-slate-100 text-slate-700 border-slate-300',
    };

    const ACTION_BADGE_LABELS = {
        passed: 'Passed',
        enacted: 'Enacted',
        vetoed: 'Vetoed',
        died: 'Died',
        failed: 'Failed',
        vote: 'Vote',
        referred: 'Referred',
        withdrawn: 'Withdrawn',
    };

    const VETERANS_IMPACT_FILTER_BUTTONS = {
        all: {
            id: 'veterans-filter-btn',
            active: ['border-amber-500', 'bg-amber-500', 'text-white'],
            inactive: ['border-slate-200', 'bg-white', 'text-slate-700'],
        },
        red: {
            id: 'veterans-filter-red-btn',
            active: ['border-red-600', 'bg-red-600', 'text-white'],
            inactive: ['border-red-200', 'bg-red-50', 'text-red-900'],
        },
        yellow: {
            id: 'veterans-filter-yellow-btn',
            active: ['border-amber-500', 'bg-amber-500', 'text-white'],
            inactive: ['border-amber-200', 'bg-amber-50', 'text-amber-900'],
        },
        green: {
            id: 'veterans-filter-green-btn',
            active: ['border-green-600', 'bg-green-600', 'text-white'],
            inactive: ['border-green-200', 'bg-green-50', 'text-green-900'],
        },
    };

    const VETERANS_IMPACT_FILTER_LABELS = {
        all: 'Military / Veterans',
        red: 'Red — High impact',
        yellow: 'Yellow — Moderate impact',
        green: 'Green — Ceremonial / general',
    };

    let callbacks = {};
    let veteranImpactLookup = {};

    function isMetaSource(source) {
        if (!source) return false;
        return META_SOURCE_PATTERNS.some((re) => re.test(source));
    }

    function isMetaItem(item) {
        const src = item.source || '';
        if (!isMetaSource(src)) return false;
        return !item.bill_number && !item.short_title;
    }

    function inferItemState(item) {
        if (item.level === 'federal') return 'Federal';
        if (item.state) return String(item.state).toUpperCase();
        const src = (item.source || '').toLowerCase();
        if (src.includes('congress') || src.includes('federal') || src.includes('u.s.')) return 'Federal';
        if (src.includes('kansas')) return 'KS';
        if (src.includes('colorado')) return 'CO';
        if (src.includes('arizona')) return 'AZ';
        if (src.includes('utah')) return 'UT';
        if (src.includes('maine')) return 'ME';
        if (src.includes('nebraska')) return 'NE';
        if (src.includes('maryland')) return 'MD';
        if (src.includes('pennsylvania')) return 'PA';
        return '';
    }

    function stateBadgeClass(state) {
        const map = {
            Federal: 'bg-indigo-100 text-indigo-800',
            KS: 'bg-sky-100 text-sky-800',
            CO: 'bg-emerald-100 text-emerald-800',
            AZ: 'bg-orange-100 text-orange-800',
            UT: 'bg-violet-100 text-violet-800',
            ME: 'bg-rose-100 text-rose-800',
            NE: 'bg-amber-100 text-amber-800',
            MD: 'bg-teal-100 text-teal-800',
            PA: 'bg-blue-100 text-blue-800',
        };
        return map[state] || 'bg-slate-100 text-slate-700';
    }

    function classifyActionType(text) {
        const hay = String(text || '').toLowerCase();
        if (!hay.trim()) return null;
        if (/signed|became (a )?law|enacted|chaptered/.test(hay)) return 'enacted';
        if (/veto/.test(hay)) return 'vetoed';
        if (/died|dead|pocket veto|failed to pass|defeated/.test(hay)) return 'died';
        if (/\bfailed\b/.test(hay)) return 'failed';
        if (/referr?ed/.test(hay)) return 'referred';
        if (/passed|adopted|approved|agreed to|concurred/.test(hay)) return 'passed';
        if (/vote|roll.?call|\byea\b|\bnay\b/.test(hay)) return 'vote';
        return null;
    }

    function actionBadgeLabel(actionType) {
        return ACTION_BADGE_LABELS[actionType] || actionType;
    }

    function renderActionBadge(actionType) {
        if (!actionType) return null;
        const badge = document.createElement('span');
        badge.className = `inline-block px-2 py-0.5 rounded text-xs font-semibold border ${ACTION_BADGE_STYLES[actionType] || 'bg-slate-100 text-slate-700 border-slate-200'}`;
        badge.textContent = actionBadgeLabel(actionType);
        return badge;
    }

    function isVoteEvent(item) {
        return item.item_type === 'vote_event' || Boolean(item.vote_tally);
    }

    function voteEventTitle(item) {
        const billNo = item.bill_number || '';
        const motion = item.motion || '';
        if (billNo && motion) return `${billNo} — ${motion}`;
        if (billNo) return billNo;
        return item.short_title || item.title || '(no title)';
    }

    function formatActionDate(item) {
        const raw = item.published || item.date || '';
        if (!raw) return '';
        try {
            const d = new Date(raw.includes('T') ? raw : `${raw}T00:00:00`);
            return d.toLocaleDateString('en-US', {
                month: 'short', day: 'numeric', year: 'numeric', timeZone: 'America/Chicago',
            });
        } catch {
            return String(raw).slice(0, 10);
        }
    }

    function countBillsByState(siteData) {
        const counts = { Federal: 0, KS: 0, CO: 0, AZ: 0, UT: 0, ME: 0, NE: 0, MD: 0, PA: 0 };
        (siteData.search_index?.bills || []).forEach((bill) => {
            if (bill.level === 'federal' || !bill.state) {
                counts.Federal++;
            } else {
                const st = String(bill.state).toUpperCase();
                if (counts[st] !== undefined) counts[st]++;
            }
        });
        return counts;
    }

    async function fetchWeeklyCounts() {
        try {
            const res = await policywatchFetch('weekly/latest.json');
            if (!res.ok) return {};
            const data = await res.json();
            return data.item_counts || {};
        } catch {
            return {};
        }
    }

    async function loadLiveNowStrip() {
        const strip = document.getElementById('live-now-strip');
        if (!strip) return;

        try {
            const [configRes, statusRes] = await Promise.all([
                policywatchFetch('live-streams-config.json'),
                policywatchFetch('live_status.json').catch(() => null),
            ]);
            if (!configRes.ok) throw new Error('config missing');
            const config = await configRes.json();
            const status = statusRes?.ok ? await statusRes.json() : { streams: {} };
            const liveMap = status.streams || {};
            const live = (config.streams || []).filter((s) => liveMap[s.id]?.isLive);

            strip.innerHTML = '';
            strip.hidden = false;

            if (live.length === 0) {
                strip.innerHTML = `
                    <p class="text-sm text-slate-500" role="status">
                        No hearings live right now.
                        <a href="livestreams.html" class="text-civic-blue hover:underline ml-1">Watch streams →</a>
                    </p>`;
                return;
            }

            const inner = document.createElement('div');
            inner.className = 'flex flex-wrap items-center gap-2';
            inner.setAttribute('role', 'status');

            const badge = document.createElement('span');
            badge.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold';
            badge.style.cssText = 'background: color-mix(in srgb, var(--cw-live) 12%, var(--cw-surface)); color: var(--cw-live);';
            badge.innerHTML = '<span style="width:0.5rem;height:0.5rem;border-radius:9999px;background:var(--cw-live);display:inline-block" class="animate-pulse" aria-hidden="true"></span> Live Now';
            inner.appendChild(badge);

            live.forEach((stream, i) => {
                if (i > 0) {
                    const sep = document.createElement('span');
                    sep.className = 'text-slate-300';
                    sep.textContent = '·';
                    sep.setAttribute('aria-hidden', 'true');
                    inner.appendChild(sep);
                }
                const link = document.createElement('a');
                link.href = `livestreams.html#${stream.targetId || stream.id}`;
                link.className = 'text-sm font-medium text-civic-blue hover:underline';
                link.textContent = stream.title;
                inner.appendChild(link);
            });

            const allLink = document.createElement('a');
            allLink.href = 'livestreams.html';
            allLink.className = 'text-sm text-slate-500 hover:text-civic-blue ml-auto';
            allLink.textContent = 'All streams →';
            inner.appendChild(allLink);

            strip.appendChild(inner);
        } catch {
            strip.hidden = true;
        }
    }

    function renderStateSnapshots(siteData, weeklyCounts) {
        const row = document.getElementById('state-snapshots');
        if (!row) return;

        const billCounts = countBillsByState(siteData);
        const weekMap = {
            Federal: weeklyCounts.federal || 0,
            KS: weeklyCounts.ks || 0,
            CO: weeklyCounts.co || 0,
            AZ: weeklyCounts.az || 0,
            UT: weeklyCounts.ut || 0,
            ME: weeklyCounts.me || 0,
            NE: weeklyCounts.ne || 0,
            MD: weeklyCounts.md || 0,
            PA: weeklyCounts.pa || 0,
        };

        const cards = [
            { value: 'Federal', label: 'Federal', sub: 'U.S. Congress' },
            { value: 'KS', label: 'Kansas', sub: 'State Legislature' },
            { value: 'CO', label: 'Colorado', sub: 'State Legislature' },
            { value: 'AZ', label: 'Arizona', sub: 'State Legislature' },
            { value: 'UT', label: 'Utah', sub: 'State Legislature' },
            { value: 'ME', label: 'Maine', sub: 'State Legislature' },
            { value: 'NE', label: 'Nebraska', sub: 'Unicameral Legislature' },
            { value: 'MD', label: 'Maryland', sub: 'General Assembly' },
            { value: 'PA', label: 'Pennsylvania', sub: 'General Assembly' },
        ];

        row.innerHTML = '';
        cards.forEach((card) => {
            const el = document.createElement('button');
            el.type = 'button';
            el.className = 'state-snapshot-card w-full p-4 rounded-xl border-2 border-slate-200 bg-white hover:border-civic-blue hover:shadow-md transition-all text-left';
            el.setAttribute('data-state', card.value);
            el.setAttribute('aria-label', `Filter feed to ${card.label}`);

            const weekCount = weekMap[card.value];
            const weekLine = weekCount > 0
                ? `<div class="text-xs mt-1" style="color: var(--cw-success)">+${weekCount} this week</div>`
                : '';

            el.innerHTML = `
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">${card.sub}</div>
                <div class="text-lg font-bold text-civic-navy mt-0.5">${card.label}</div>
                <div class="text-2xl font-bold text-civic-blue mt-1">${billCounts[card.value].toLocaleString()}</div>
                <div class="text-xs text-slate-500">tracked bills</div>
                ${weekLine}
            `;

            el.addEventListener('click', () => {
                setSelectedState(card.value);
                if (callbacks.onStateFilter) callbacks.onStateFilter(card.value);
                document.getElementById('feed-controls')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });

            row.appendChild(el);
        });
    }

    function initStateChips() {
        const container = document.getElementById('state-chips');
        if (!container) return;

        container.innerHTML = '';
        STATE_CHIPS.forEach((chip) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'state-chip px-4 py-2 rounded-full text-sm font-medium border-2 border-slate-200 bg-white text-slate-700 hover:border-civic-blue transition-colors whitespace-nowrap';
            btn.textContent = chip.label;
            btn.setAttribute('data-state', chip.value);
            btn.setAttribute('aria-pressed', 'false');
            btn.addEventListener('click', () => {
                setSelectedState(chip.value);
                if (callbacks.onStateFilter) callbacks.onStateFilter(chip.value);
            });
            container.appendChild(btn);
        });
    }

    function setSelectedState(state) {
        document.querySelectorAll('.state-chip').forEach((btn) => {
            const active = btn.getAttribute('data-state') === state;
            btn.setAttribute('aria-pressed', active ? 'true' : 'false');
            btn.classList.toggle('border-civic-blue', active);
            btn.classList.toggle('bg-civic-blue', active);
            btn.classList.toggle('text-white', active);
            btn.classList.toggle('border-slate-200', !active);
            btn.classList.toggle('bg-white', !active);
            btn.classList.toggle('text-slate-700', !active);
        });

        document.querySelectorAll('.state-snapshot-card').forEach((card) => {
            const active = card.getAttribute('data-state') === state;
            card.classList.toggle('border-civic-blue', active);
            card.classList.toggle('border-slate-200', !active);
        });

        const hiddenSelect = document.getElementById('state-filter');
        if (hiddenSelect) hiddenSelect.value = state;
    }

    function setVeteranImpactLookup(lookup) {
        veteranImpactLookup = lookup && typeof lookup === 'object' ? lookup : {};
    }

    function normalizeCoBillSlug(billNumber) {
        const raw = String(billNumber || '').trim().toUpperCase().replace(/\s+/g, '');
        const match = raw.match(/^([A-Z]+)26-(\d+)$/) || raw.match(/^([A-Z]+)(\d+)$/);
        if (!match) return '';
        return `${match[1]}26-${match[2]}`;
    }

    function buildVeteranImpactKey(state, billNumber) {
        const st = String(state || 'Federal').toUpperCase();
        const num = String(billNumber || '').trim().toUpperCase();
        if (!num) return '';
        if (st === 'CO') {
            const slug = normalizeCoBillSlug(num);
            if (slug) return `CO|${slug}`;
        }
        const generic = num.match(/^([A-Z]+)\s*(\d+[A-Z]?)$/);
        return generic ? `${st}|${generic[1]} ${generic[2]}` : `${st}|${num}`;
    }

    const VETERAN_IMPACT_RED_SIGNALS = [
        'gi bill', 'survivor benefit', 'burial benefit', 'va benefit', 'veterans benefit',
        'compensation', 'pension', 'dependency indemnity', 'title 38',
        'va health', 'veterans health', 'veterans affairs', 'ptsd', 'tbi',
        'mental health', 'suicide prevention', 'post-traumatic',
        'veteran housing', 'homeless veteran', 'housing voucher', 'shelter veteran',
        'disability rating', 'service-connected', 'service connected', 'rating schedule',
        'survivor', 'burial',
        'take care of america',
        'military construction, veterans affairs',
        'military construction and veterans affairs',
        'veterans affairs appropriations',
        'va appropriations',
        'milcon-va',
        'appropriations for the department of veterans affairs',
        'appropriations for veterans affairs',
    ];
    const VETERAN_IMPACT_YELLOW_SIGNALS = [
        'veteran preference', 'hiring preference', 'employment preference',
        'military spouse', 'licensing', 'certification', 'apprenticeship',
        'veterans court', 'veteran court', 'diversion', 'treatment court',
        'veterans justice', 'justice outreach',
    ];
    const VETERAN_IMPACT_GREEN_SIGNALS = [
        'recognition', 'memorial', 'honor', 'honoring', 'ceremonial', 'commemorative',
        'designate', 'memorial highway', 'memorial day', 'purple heart day',
        'resolution honoring', 'honor resolution',
    ];
    const VA_FACILITY_NAMING_PATTERNS = [
        /\b(to\s+)?(designate|name|rename|redesignate)\b.{0,160}\b(community-based outpatient clinic|outpatient clinic|multispecialty clinic|va clinic|veterans affairs clinic|va medical center|veterans affairs medical center|veterans affairs multispecialty clinic)\b/i,
        /\bcommunity-based outpatient clinic\b.{0,120}\bas the\b/i,
        /\bdepartment of veterans affairs\b.{0,160}\bclinic\b.{0,120}\bas the\b/i,
    ];

    function isVaFacilityNaming(text) {
        const hay = String(text || '');
        return VA_FACILITY_NAMING_PATTERNS.some((pattern) => pattern.test(hay));
    }

    function itemHasVeteranTagging(item) {
        const tags = []
            .concat(item.ai_topics || [])
            .concat(item.classification || [])
            .concat(item.topics || []);
        return tags.some((tag) => VETERANS_TOPIC_PATTERN.test(String(tag)));
    }

    function matchedImpactKeywords(hay, keywords, limit) {
        const matched = [];
        const max = limit || 5;
        for (let i = 0; i < keywords.length; i += 1) {
            const kw = keywords[i];
            if (hay.includes(kw) && !matched.includes(kw)) {
                matched.push(kw);
                if (matched.length >= max) break;
            }
        }
        return matched;
    }

    function buildClientImpactReason(level, options) {
        const opts = options || {};
        const label = level === 'red'
            ? 'red (high impact)'
            : level === 'yellow'
                ? 'yellow (moderate impact)'
                : 'green (ceremonial / general)';
        const factors = opts.factors || [];
        const matched = opts.matchedKeywords || [];

        if (opts.source === 'csv') {
            let text = `Impact level set from Colorado veteran tracker (CSV) as ${label}.`;
            if (factors.length) text += ` Matched topics: ${factors.join(', ')}.`;
            return text;
        }
        if (opts.special === 'facility_naming') {
            return 'Classified green because this bill names or renames a VA clinic or outpatient facility.';
        }
        if (opts.special === 'veteran_marker') {
            const markerNote = matched.length ? ` Matched markers: ${matched.join(', ')}.` : '';
            return `Classified ${label} as veteran-related without high or moderate impact keyword signals.${markerNote}`;
        }

        let sentence = `Classified ${label}`;
        if (matched.length) sentence += ` based on matched keywords: ${matched.join(', ')}`;
        sentence += '.';
        if (factors.length) sentence += ` Scoring factors: ${factors.join(', ')}.`;
        return sentence;
    }

    function veteranImpactReason(impact) {
        if (!impact) return '';
        if (impact.reason) return impact.reason;
        if (impact.factors && impact.factors.includes('Facility Naming')) {
            return buildClientImpactReason('green', { special: 'facility_naming', factors: impact.factors });
        }
        if (impact.source === 'csv') {
            return buildClientImpactReason(impact.level, { source: 'csv', factors: impact.factors || [] });
        }
        if (impact.factors && impact.factors.length) {
            return buildClientImpactReason(impact.level, { factors: impact.factors });
        }
        return buildClientImpactReason(impact.level, { special: 'veteran_marker' });
    }

    function classifyVeteranImpactFromText(text) {
        const hay = String(text || '').toLowerCase();
        if (!hay.trim()) return null;

        const markers = VETERANS_STRONG_KEYWORDS.concat(['title 38', 'gi bill', 'servicemember', 'service member']);
        const hasMarker = markers.some((m) => hay.includes(m));
        const hasSignal = VETERAN_IMPACT_RED_SIGNALS.some((kw) => hay.includes(kw))
            || VETERAN_IMPACT_YELLOW_SIGNALS.some((kw) => hay.includes(kw))
            || VETERAN_IMPACT_GREEN_SIGNALS.some((kw) => hay.includes(kw));
        if (!hasMarker && !hasSignal) return null;

        if (isVaFacilityNaming(hay)) {
            const factors = ['Facility Naming'];
            return {
                level: 'green',
                source: 'rules',
                veteran_related: true,
                factors,
                reason: buildClientImpactReason('green', { special: 'facility_naming', factors }),
            };
        }

        const matchedRed = matchedImpactKeywords(hay, VETERAN_IMPACT_RED_SIGNALS);
        const matchedYellow = matchedImpactKeywords(hay, VETERAN_IMPACT_YELLOW_SIGNALS);
        const matchedGreen = matchedImpactKeywords(hay, VETERAN_IMPACT_GREEN_SIGNALS);
        const matchedMarkers = matchedImpactKeywords(hay, markers);

        let level = 'green';
        let matched = matchedMarkers;
        let special = 'veteran_marker';
        if (matchedRed.length) {
            level = 'red';
            matched = matchedRed;
            special = null;
        } else if (matchedYellow.length) {
            level = 'yellow';
            matched = matchedYellow;
            special = null;
        } else if (matchedGreen.length) {
            level = 'green';
            matched = matchedGreen;
            special = null;
        } else if (!hasMarker) {
            return null;
        }

        return {
            level,
            source: 'rules',
            veteran_related: true,
            factors: [],
            reason: buildClientImpactReason(level, { matchedKeywords: matched, special }),
        };
    }

    function defaultGreenImpact() {
        return {
            level: 'green',
            source: 'rules',
            veteran_related: true,
            factors: [],
            reason: buildClientImpactReason('green', { special: 'veteran_marker' }),
        };
    }

    function resolveVeteranImpact(item) {
        if (item.veteran_impact) return item.veteran_impact;
        if (!veteranImpactLookup || Object.keys(veteranImpactLookup).length === 0) {
            if (itemHasVeteranTagging(item)) {
                return classifyVeteranImpactFromText(itemVeteransText(item)) || defaultGreenImpact();
            }
            return classifyVeteranImpactFromText(itemVeteransText(item));
        }

        const state = inferItemState(item);
        let billNumber = item.bill_number || '';
        if (!billNumber) {
            const titleMatch = String(item.title || '').match(/^([A-Za-z]+\s*\d+[A-Za-z]?)\s*:/);
            if (titleMatch) billNumber = titleMatch[1];
        }

        if (billNumber) {
            const keys = [buildVeteranImpactKey(state, billNumber)];
            if (state === 'CO') {
                const slug = normalizeCoBillSlug(billNumber);
                if (slug) keys.push(`CO|${slug}`);
            }
            for (const key of keys) {
                if (key && veteranImpactLookup[key]) return veteranImpactLookup[key];
            }
        }

        if (itemHasVeteranTagging(item)) {
            const tagged = classifyVeteranImpactFromText(itemVeteransText(item));
            if (tagged) return tagged;
            return defaultGreenImpact();
        }

        return classifyVeteranImpactFromText(itemVeteransText(item));
    }

    function veteranImpactCardClasses(level) {
        return VETERAN_IMPACT_STYLES[level] || '';
    }

    function veteranImpactLabel(level) {
        if (level === 'red') return 'High impact';
        if (level === 'yellow') return 'Moderate impact';
        if (level === 'green') return 'Ceremonial / general';
        return '';
    }

    function setVeteransImpactFilter(level) {
        const activeLevel = level || null;
        Object.entries(VETERANS_IMPACT_FILTER_BUTTONS).forEach(([key, config]) => {
            const btn = document.getElementById(config.id);
            if (!btn) return;
            const isActive = activeLevel === key;
            btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            config.active.forEach((cls) => btn.classList.toggle(cls, isActive));
            config.inactive.forEach((cls) => btn.classList.toggle(cls, !isActive));
        });
    }

    function setVeteransFilterActive(active) {
        setVeteransImpactFilter(active ? 'all' : null);
    }

    function initVeteransFilter() {
        Object.entries(VETERANS_IMPACT_FILTER_BUTTONS).forEach(([level, config]) => {
            const btn = document.getElementById(config.id);
            if (!btn) return;
            btn.addEventListener('click', () => {
                const isActive = btn.getAttribute('aria-pressed') === 'true';
                const next = isActive ? null : level;
                setVeteransImpactFilter(next);
                if (callbacks.onVeteransImpactFilter) callbacks.onVeteransImpactFilter(next);
            });
        });
    }

    function initFilterDrawer() {
        const toggle = document.getElementById('filters-toggle');
        const drawer = document.getElementById('filters-drawer');
        if (!toggle || !drawer) return;

        toggle.addEventListener('click', () => {
            const open = drawer.hidden;
            drawer.hidden = !open;
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            if (open) {
                const firstField = drawer.querySelector('select, input, button');
                if (firstField) firstField.focus();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !drawer.hidden) {
                drawer.hidden = true;
                toggle.setAttribute('aria-expanded', 'false');
                toggle.focus();
            }
        });
    }

    function updateActiveFilterPills(filters) {
        const container = document.getElementById('active-filter-pills');
        if (!container) return;

        container.innerHTML = '';
        const pills = [];

        if (filters.state) {
            pills.push({ key: 'state', label: STATE_NAMES[filters.state] || filters.state, value: filters.state });
        }
        if (filters.source) {
            pills.push({ key: 'source', label: filters.source, value: filters.source });
        }
        if (filters.category) {
            pills.push({ key: 'category', label: filters.category, value: filters.category });
        }
        if (filters.search) {
            pills.push({ key: 'search', label: `Search: "${filters.search}"`, value: filters.search });
        }
        if (filters.veteransImpact) {
            pills.push({
                key: 'veterans',
                label: VETERANS_IMPACT_FILTER_LABELS[filters.veteransImpact] || 'Military / Veterans',
                value: filters.veteransImpact,
            });
        }

        if (pills.length === 0) {
            container.hidden = true;
            return;
        }

        container.hidden = false;
        pills.forEach((pill) => {
            const el = document.createElement('span');
            el.className = 'inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-civic-blue/10 text-civic-blue border border-civic-blue/20';
            el.innerHTML = `
                <span>${pill.label}</span>
                <button type="button" class="filter-pill-clear ml-0.5 hover:text-civic-blue-dark" data-filter-key="${pill.key}" aria-label="Remove ${pill.label} filter">×</button>
            `;
            el.querySelector('.filter-pill-clear').addEventListener('click', () => {
                if (callbacks.onClearFilter) callbacks.onClearFilter(pill.key);
            });
            container.appendChild(el);
        });
    }

    function renderBillCard(item, searchQuery) {
        const impact = resolveVeteranImpact(item);
        const voteEvent = isVoteEvent(item);
        const card = document.createElement('article');
        const impactClasses = impact ? veteranImpactCardClasses(impact.level) : '';
        const voteBorder = voteEvent ? 'border-l-4 border-l-blue-400 ' : '';
        card.className = `bill-card p-4 rounded-lg border transition-all ${voteBorder}${impact ? `veteran-impact-card veteran-impact-card--${impact.level} ` : ''}${impactClasses || 'bg-white border-slate-200 hover:border-civic-blue/40 hover:shadow-sm'}`;
        const titleClass = impact
            ? 'veteran-impact-title block text-base font-semibold transition-colors'
            : 'block text-base font-semibold text-civic-navy hover:text-civic-blue transition-colors';
        const metaLinkClass = impact
            ? 'veteran-impact-link'
            : 'text-civic-blue';

        const state = inferItemState(item);
        const displayTitle = voteEvent
            ? voteEventTitle(item)
            : (item.short_title || item.title || '(no title)');
        const url = item.link || item.url || '#';
        const officialUrl = (typeof PolicyWatchBillUtils !== 'undefined')
            ? PolicyWatchBillUtils.resolveBillUrl(item)
            : url;

        const header = document.createElement('div');
        header.className = 'flex flex-wrap items-start gap-2 mb-2';

        if (state) {
            const badge = document.createElement('span');
            badge.className = `inline-block px-2 py-0.5 rounded text-xs font-semibold ${stateBadgeClass(state)}`;
            badge.textContent = state === 'Federal' ? 'Federal' : state;
            header.appendChild(badge);
        }

        const actionType = item.action_type || (voteEvent ? 'vote' : null);
        if (actionType) {
            const actionBadge = renderActionBadge(actionType);
            if (actionBadge) header.appendChild(actionBadge);
        }

        if (item.bill_number && !voteEvent) {
            const billNum = document.createElement('span');
            billNum.className = `text-xs font-semibold ${impact ? metaLinkClass : 'text-civic-blue'}`;
            billNum.textContent = item.bill_number;
            header.appendChild(billNum);
        }

        if (impact) {
            const impactBadge = document.createElement('span');
            impactBadge.className = `veteran-impact-badge inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide border ${VETERAN_IMPACT_BADGE[impact.level] || 'bg-slate-100 text-slate-700 border-slate-200'}`;
            impactBadge.textContent = impact.level;
            impactBadge.title = veteranImpactLabel(impact.level);
            header.appendChild(impactBadge);
        }

        card.appendChild(header);

        if (impact) {
            const reasonText = veteranImpactReason(impact);
            if (reasonText) {
                const reasonWrap = document.createElement('div');
                reasonWrap.className = 'veteran-impact-reason mb-2';

                const reasonToggle = document.createElement('button');
                reasonToggle.type = 'button';
                reasonToggle.className = 'veteran-impact-reason-toggle inline-flex items-center gap-1 text-xs font-medium text-slate-600 hover:text-slate-800';
                reasonToggle.setAttribute('aria-expanded', 'false');
                const reasonId = `veteran-reason-${Math.random().toString(36).slice(2, 9)}`;
                reasonToggle.setAttribute('aria-controls', reasonId);

                const reasonLabel = document.createElement('span');
                reasonLabel.textContent = 'Reasoning';
                const reasonArrow = document.createElement('span');
                reasonArrow.className = 'veteran-impact-reason-arrow';
                reasonArrow.setAttribute('aria-hidden', 'true');
                reasonArrow.textContent = '›';
                reasonToggle.appendChild(reasonLabel);
                reasonToggle.appendChild(reasonArrow);

                const reasonBody = document.createElement('p');
                reasonBody.id = reasonId;
                reasonBody.className = 'veteran-impact-reason-body text-xs text-slate-600 mt-1 leading-relaxed';
                reasonBody.hidden = true;
                reasonBody.textContent = reasonText;

                reasonToggle.addEventListener('click', () => {
                    const open = reasonToggle.getAttribute('aria-expanded') === 'true';
                    const nextOpen = !open;
                    reasonToggle.setAttribute('aria-expanded', nextOpen ? 'true' : 'false');
                    reasonBody.hidden = !nextOpen;
                    reasonArrow.textContent = nextOpen ? '▾' : '›';
                });

                reasonWrap.appendChild(reasonToggle);
                reasonWrap.appendChild(reasonBody);
                card.appendChild(reasonWrap);
            }
        }

        const hasVoteRecords = typeof PolicyWatchBillVotes !== 'undefined'
            && PolicyWatchBillVotes.hasVotes(item);

        if (hasVoteRecords) {
            const titleBtn = document.createElement('button');
            titleBtn.type = 'button';
            titleBtn.className = `text-left w-full ${titleClass}`;
            if (searchQuery) {
                const regex = new RegExp(`(${escapeRegex(searchQuery)})`, 'gi');
                titleBtn.innerHTML = highlightSafe(displayTitle, regex);
            } else {
                titleBtn.textContent = displayTitle;
            }
            titleBtn.addEventListener('click', () => PolicyWatchBillVotes.open(item));
            card.appendChild(titleBtn);
        } else {
            const titleLink = document.createElement('a');
            titleLink.href = officialUrl || url;
            titleLink.target = '_blank';
            titleLink.rel = 'noopener noreferrer';
            titleLink.className = titleClass;
            if (searchQuery) {
                const regex = new RegExp(`(${escapeRegex(searchQuery)})`, 'gi');
                titleLink.innerHTML = highlightSafe(displayTitle, regex);
            } else {
                titleLink.textContent = displayTitle;
            }
            card.appendChild(titleLink);
        }

        if (voteEvent && item.vote_tally) {
            const tallyRow = document.createElement('div');
            tallyRow.className = 'flex items-center gap-2 mt-2 text-sm font-semibold text-blue-900';
            const iconWrap = document.createElement('span');
            iconWrap.className = 'text-blue-600 flex-shrink-0';
            iconWrap.setAttribute('aria-hidden', 'true');
            iconWrap.innerHTML = `
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
                </svg>`;
            tallyRow.appendChild(iconWrap);
            const tallyText = document.createElement('span');
            if (searchQuery) {
                const regex = new RegExp(`(${escapeRegex(searchQuery)})`, 'gi');
                tallyText.innerHTML = highlightSafe(item.vote_tally, regex);
            } else {
                tallyText.textContent = item.vote_tally;
            }
            tallyRow.appendChild(tallyText);
            card.appendChild(tallyRow);
        }

        if (!voteEvent && item.latest_action) {
            const actionRow = document.createElement('p');
            actionRow.className = 'text-sm text-slate-600 mt-2';
            const dateStr = formatActionDate(item);
            const actionText = dateStr
                ? `Action: ${item.latest_action} · ${dateStr}`
                : `Action: ${item.latest_action}`;
            if (searchQuery) {
                const regex = new RegExp(`(${escapeRegex(searchQuery)})`, 'gi');
                actionRow.innerHTML = highlightSafe(actionText, regex);
            } else {
                actionRow.textContent = actionText;
            }
            card.appendChild(actionRow);
        }

        const summaryText = item.summary || '';
        const showSummary = summaryText.trim()
            && summaryText !== displayTitle
            && !(voteEvent && summaryText === item.vote_tally);
        if (showSummary) {
            const summary = document.createElement('p');
            summary.className = impact
                ? 'veteran-impact-summary text-sm mt-2 line-clamp-2 leading-relaxed'
                : 'text-sm text-slate-600 mt-2 line-clamp-2 leading-relaxed';
            if (searchQuery) {
                const regex = new RegExp(`(${escapeRegex(searchQuery)})`, 'gi');
                summary.innerHTML = highlightSafe(summaryText, regex);
            } else {
                summary.textContent = summaryText;
            }
            card.appendChild(summary);
        }

        if (officialUrl && officialUrl !== '#') {
            const linkRow = document.createElement('div');
            linkRow.className = 'mt-2';
            const officialLink = document.createElement('a');
            officialLink.href = officialUrl;
            officialLink.target = '_blank';
            officialLink.rel = 'noopener noreferrer';
            officialLink.className = `text-xs hover:underline inline-flex items-center gap-1 ${impact ? metaLinkClass : 'text-civic-blue'}`;
            officialLink.innerHTML = `
                Official source
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                </svg>`;
            linkRow.appendChild(officialLink);
            card.appendChild(linkRow);
        }

        if (typeof PolicyWatchBillVotes !== 'undefined') {
            PolicyWatchBillVotes.attachVoteButton(card, item);
        }

        return card;
    }

    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function highlightSafe(text, regex) {
        return String(text).replace(regex, '<mark>$1</mark>');
    }

    function matchesVeteransTopic(text) {
        if (!text) return false;
        const haystack = String(text).toLowerCase();
        if (/\bveterans?\s+affairs\b/.test(haystack)) return true;
        if (/\btitle\s+38\b/.test(haystack)) return true;
        if (/\bva\b/.test(haystack) && /veteran|affairs|benefit|health|secretary/.test(haystack)) return true;
        if (VETERANS_STRONG_KEYWORDS.some((kw) => haystack.includes(kw))) return true;
        return VETERANS_DEFENSE_PHRASES.some((ph) => haystack.includes(ph));
    }

    function itemVeteransText(item) {
        const parts = [
            item.title, item.short_title, item.summary, item.latest_action, item.bill_number,
            item.link, item.url,
        ];
        if (Array.isArray(item.classification)) parts.push(item.classification.join(' '));
        if (Array.isArray(item.ai_topics)) parts.push(item.ai_topics.join(' '));
        return parts.filter(Boolean).join(' ');
    }

    function itemMatchesVeteransImpactFilter(item, level) {
        if (!level) return true;
        const impact = resolveVeteranImpact(item);
        if (level === 'red' || level === 'yellow' || level === 'green') {
            return Boolean(impact && impact.level === level);
        }
        return itemMatchesVeteransFilter(item);
    }

    function itemMatchesVeteransFilter(item) {
        if (resolveVeteranImpact(item)) return true;
        if (Array.isArray(item.ai_topics)) {
            const topics = item.ai_topics.map((t) => String(t).toLowerCase());
            if (topics.some((t) => VETERANS_TOPIC_PATTERN.test(t))) return true;
        }
        if (Array.isArray(item.classification)) {
            const cls = item.classification.map((c) => String(c).toLowerCase());
            if (cls.some((c) => VETERANS_TOPIC_PATTERN.test(c))) return true;
        }
        const link = String(item.link || item.url || '').toLowerCase();
        if (link.includes('news.va.gov') || link.includes('va.gov')) return true;
        return matchesVeteransTopic(itemVeteransText(item));
    }

    function renderVeteransCallout(items) {
        const matches = items.filter((item) => matchesVeteransTopic(itemVeteransText(item)));
        if (matches.length === 0) return null;

        const box = document.createElement('div');
        box.className = 'veterans-day-callout mb-4 p-3 rounded-lg border';
        box.style.cssText = 'background: color-mix(in srgb, var(--cw-accent-warn, #f59e0b) 8%, var(--cw-surface)); border-color: color-mix(in srgb, var(--cw-accent-warn, #f59e0b) 35%, var(--cw-border));';

        const labelRow = document.createElement('div');
        labelRow.className = 'flex flex-wrap items-center gap-2 mb-2';
        const badge = document.createElement('span');
        badge.className = 'inline-block px-2 py-0.5 text-xs font-semibold rounded uppercase tracking-wide';
        badge.style.cssText = 'background: color-mix(in srgb, var(--cw-accent-warn, #f59e0b) 18%, var(--cw-surface)); color: var(--cw-text);';
        badge.textContent = 'Veterans & Military';
        labelRow.appendChild(badge);
        if (matches.length > 1) {
            const count = document.createElement('span');
            count.className = 'text-xs text-slate-500';
            count.textContent = `${matches.length} items`;
            labelRow.appendChild(count);
        }
        box.appendChild(labelRow);

        const list = document.createElement('ul');
        list.className = 'space-y-1 text-sm';
        matches.slice(0, 5).forEach((item) => {
            const li = document.createElement('li');
            const url = (typeof PolicyWatchBillUtils !== 'undefined')
                ? PolicyWatchBillUtils.resolveBillUrl(item)
                : (item.link || item.url);
            const displayTitle = item.short_title || item.title || 'Bill';
            const label = (item.bill_number && !displayTitle.startsWith(item.bill_number))
                ? `${item.bill_number}: ${displayTitle}`
                : displayTitle;
            if (url) {
                const a = document.createElement('a');
                a.href = url;
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                a.className = 'text-civic-blue hover:underline font-medium';
                a.textContent = label;
                li.appendChild(a);
            } else {
                li.textContent = label;
            }
            list.appendChild(li);
        });
        if (matches.length > 5) {
            const more = document.createElement('li');
            more.className = 'text-xs text-slate-500';
            more.textContent = `Plus ${matches.length - 5} more`;
            list.appendChild(more);
        }
        box.appendChild(list);
        return box;
    }

    function renderFeedDay(date, items, options) {
        const { searchQuery, veteransImpactFilter } = options;
        const section = document.createElement('section');
        section.className = 'feed-day mb-6';
        section.setAttribute('aria-label', `Updates for ${date}`);

        const card = document.createElement('div');
        card.className = 'feed-day-card rounded-xl border p-5 sm:p-6';
        card.style.cssText = 'background: var(--cw-surface); border-color: var(--cw-border); box-shadow: 0 1px 2px color-mix(in srgb, var(--cw-text) 6%, transparent);';

        const header = document.createElement('h2');
        header.className = 'text-xl font-bold text-civic-navy mb-4 pb-3 border-b';
        header.style.borderColor = 'var(--cw-border)';
        header.textContent = formatDate(date);
        card.appendChild(header);

        const legislative = items.filter((i) => !isMetaItem(i));
        const meta = items.filter((i) => isMetaItem(i));

        if (legislative.length === 0 && meta.length === 0) return null;

        const veteransCallout = veteransImpactFilter ? null : renderVeteransCallout(legislative);
        if (veteransCallout) card.appendChild(veteransCallout);

        const byState = {};
        legislative.forEach((item) => {
            const st = inferItemState(item) || 'Other';
            if (!byState[st]) byState[st] = [];
            byState[st].push(item);
        });

        const stateKeys = Object.keys(byState).sort((a, b) => {
            const order = ['Federal', 'KS', 'CO', 'AZ', 'UT', 'ME', 'NE', 'MD', 'PA', 'Other'];
            return order.indexOf(a) - order.indexOf(b);
        });

        const multiState = stateKeys.length > 1;
        stateKeys.forEach((st) => {
            const stateItems = byState[st];
            if (multiState) {
                const subHeader = document.createElement('h3');
                subHeader.className = 'text-sm font-semibold uppercase tracking-wide text-slate-500 mb-3 mt-4';
                subHeader.textContent = STATE_NAMES[st] || st;
                card.appendChild(subHeader);
            }

            const grid = document.createElement('div');
            grid.className = 'grid gap-3 sm:grid-cols-1';
            stateItems.forEach((item) => {
                grid.appendChild(renderBillCard(item, searchQuery));
            });
            card.appendChild(grid);
        });

        if (meta.length > 0) {
            card.appendChild(renderMetaSection(meta, searchQuery));
        }

        section.appendChild(card);
        return section;
    }

    function renderMetaSection(items, searchQuery) {
        const wrapper = document.createElement('details');
        wrapper.className = 'mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200';
        const summary = document.createElement('summary');
        summary.className = 'cursor-pointer text-sm font-semibold text-slate-600';
        summary.textContent = `Data updates (${items.length})`;
        wrapper.appendChild(summary);

        const list = document.createElement('div');
        list.className = 'mt-3 space-y-2';
        items.forEach((item) => {
            const row = document.createElement('div');
            row.className = 'text-sm text-slate-600';
            const src = document.createElement('span');
            src.className = 'text-xs text-slate-400 mr-2';
            src.textContent = item.source || 'Update';
            row.appendChild(src);
            if (item.link || item.url) {
                const a = document.createElement('a');
                a.href = item.link || item.url;
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                a.className = 'text-civic-blue hover:underline';
                a.textContent = item.title || '(no title)';
                row.appendChild(a);
            } else {
                row.appendChild(document.createTextNode(item.title || '(no title)'));
            }
            list.appendChild(row);
        });
        wrapper.appendChild(list);
        return wrapper;
    }

    function formatDate(dateStr) {
        try {
            const date = new Date(dateStr + 'T00:00:00');
            return date.toLocaleDateString('en-US', {
                year: 'numeric', month: 'long', day: 'numeric', timeZone: 'America/Chicago',
            });
        } catch {
            return dateStr;
        }
    }

    async function init(options) {
        callbacks = options || {};
        initStateChips();
        initVeteransFilter();
        initFilterDrawer();
        loadLiveNowStrip();

        const weeklyCounts = await fetchWeeklyCounts();
        if (options?.siteData) {
            renderStateSnapshots(options.siteData, weeklyCounts);
        }
    }

    return {
        init,
        setSelectedState,
        setVeteransFilterActive,
        setVeteransImpactFilter,
        setVeteranImpactLookup,
        updateActiveFilterPills,
        renderFeedDay,
        renderBillCard,
        renderStateSnapshots,
        loadLiveNowStrip,
        inferItemState,
        isMetaItem,
        isVoteEvent,
        classifyActionType,
        renderActionBadge,
        actionBadgeLabel,
        itemMatchesVeteransFilter,
        itemMatchesVeteransImpactFilter,
        resolveVeteranImpact,
        fetchWeeklyCounts,
        formatDate,
        STATE_NAMES,
    };
})();
