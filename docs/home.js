/**
 * CivicWatch homepage UI — live strip, state snapshots, filters, feed cards.
 */
const CivicWatchHome = (() => {
    'use strict';

    const STATE_CHIPS = [
        { value: '', label: 'All' },
        { value: 'Federal', label: 'Federal' },
        { value: 'KS', label: 'KS' },
        { value: 'CO', label: 'CO' },
        { value: 'AZ', label: 'AZ' },
        { value: 'UT', label: 'UT' },
        { value: 'ME', label: 'ME' },
    ];

    const STATE_NAMES = {
        KS: 'Kansas', CO: 'Colorado', AZ: 'Arizona', UT: 'Utah', ME: 'Maine', Federal: 'U.S. Congress',
    };

    const META_SOURCE_PATTERNS = [/congress\.gov api/i, /openstates/i, /data sync/i, /api feed/i];

    let callbacks = {};

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
        };
        return map[state] || 'bg-slate-100 text-slate-700';
    }

    function countBillsByState(siteData) {
        const counts = { Federal: 0, KS: 0, CO: 0, AZ: 0, UT: 0, ME: 0 };
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
            const res = await fetch('weekly/latest.json');
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
                fetch('live-streams-config.json'),
                fetch('live_status.json').catch(() => null),
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
        };

        const cards = [
            { value: 'Federal', label: 'Federal', sub: 'U.S. Congress' },
            { value: 'KS', label: 'Kansas', sub: 'State Legislature' },
            { value: 'CO', label: 'Colorado', sub: 'State Legislature' },
            { value: 'AZ', label: 'Arizona', sub: 'State Legislature' },
            { value: 'UT', label: 'Utah', sub: 'State Legislature' },
            { value: 'ME', label: 'Maine', sub: 'State Legislature' },
        ];

        row.innerHTML = '';
        cards.forEach((card) => {
            const el = document.createElement('button');
            el.type = 'button';
            el.className = 'state-snapshot-card flex-shrink-0 min-w-[140px] p-4 rounded-xl border border-slate-200 bg-white hover:border-civic-blue hover:shadow-md transition-all text-left';
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
            card.classList.toggle('ring-2', active);
            card.classList.toggle('ring-civic-blue', active);
            card.classList.toggle('border-civic-blue', active);
        });

        const hiddenSelect = document.getElementById('state-filter');
        if (hiddenSelect) hiddenSelect.value = state;
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
        const card = document.createElement('article');
        card.className = 'bill-card p-4 bg-white rounded-lg border border-slate-200 hover:border-civic-blue/40 hover:shadow-sm transition-all';

        const state = inferItemState(item);
        const displayTitle = item.short_title || item.title || '(no title)';
        const url = item.link || item.url || '#';
        const officialUrl = (typeof CivicWatchBillUtils !== 'undefined')
            ? CivicWatchBillUtils.resolveBillUrl(item)
            : url;

        const header = document.createElement('div');
        header.className = 'flex flex-wrap items-start gap-2 mb-2';

        if (state) {
            const badge = document.createElement('span');
            badge.className = `inline-block px-2 py-0.5 rounded text-xs font-semibold ${stateBadgeClass(state)}`;
            badge.textContent = state === 'Federal' ? 'Federal' : state;
            header.appendChild(badge);
        }

        if (item.bill_number) {
            const billNum = document.createElement('span');
            billNum.className = 'text-xs font-semibold text-civic-blue';
            billNum.textContent = item.bill_number;
            header.appendChild(billNum);
        }

        card.appendChild(header);

        const titleLink = document.createElement('a');
        titleLink.href = officialUrl || url;
        titleLink.target = '_blank';
        titleLink.rel = 'noopener noreferrer';
        titleLink.className = 'block text-base font-semibold text-civic-navy hover:text-civic-blue transition-colors';

        if (searchQuery) {
            const regex = new RegExp(`(${escapeRegex(searchQuery)})`, 'gi');
            titleLink.innerHTML = highlightSafe(displayTitle, regex);
        } else {
            titleLink.textContent = displayTitle;
        }
        card.appendChild(titleLink);

        const summaryText = item.summary || item.latest_action || '';
        const showSummary = summaryText.trim() && summaryText !== displayTitle;
        if (showSummary) {
            const summary = document.createElement('p');
            summary.className = 'text-sm text-slate-600 mt-2 line-clamp-2 leading-relaxed';
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
            officialLink.className = 'text-xs text-civic-blue hover:underline inline-flex items-center gap-1';
            officialLink.innerHTML = `
                Official source
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                </svg>`;
            linkRow.appendChild(officialLink);
            card.appendChild(linkRow);
        }

        return card;
    }

    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function highlightSafe(text, regex) {
        return String(text).replace(regex, '<mark>$1</mark>');
    }

    function renderFeedDay(date, items, options) {
        const { dailySummary, searchQuery, todayStr } = options;
        const section = document.createElement('section');
        section.className = 'feed-day mb-8';
        section.setAttribute('aria-label', `Updates for ${date}`);

        const header = document.createElement('h2');
        header.className = 'text-xl font-bold text-civic-navy mb-4 pb-2 border-b border-slate-200';
        header.textContent = formatDate(date);
        section.appendChild(header);

        if (dailySummary?.summary && date < todayStr) {
            section.appendChild(renderDailySummary(dailySummary));
        }

        const legislative = items.filter((i) => !isMetaItem(i));
        const meta = items.filter((i) => isMetaItem(i));

        if (legislative.length === 0 && meta.length === 0) return null;

        const byState = {};
        legislative.forEach((item) => {
            const st = inferItemState(item) || 'Other';
            if (!byState[st]) byState[st] = [];
            byState[st].push(item);
        });

        const stateKeys = Object.keys(byState).sort((a, b) => {
            const order = ['Federal', 'KS', 'CO', 'AZ', 'UT', 'ME', 'Other'];
            return order.indexOf(a) - order.indexOf(b);
        });

        const multiState = stateKeys.length > 1;
        stateKeys.forEach((st) => {
            const stateItems = byState[st];
            if (multiState) {
                const subHeader = document.createElement('h3');
                subHeader.className = 'text-sm font-semibold uppercase tracking-wide text-slate-500 mb-3 mt-4';
                subHeader.textContent = STATE_NAMES[st] || st;
                section.appendChild(subHeader);
            }

            const grid = document.createElement('div');
            grid.className = 'grid gap-3 sm:grid-cols-1';
            stateItems.forEach((item) => {
                grid.appendChild(renderBillCard(item, searchQuery));
            });
            section.appendChild(grid);
        });

        if (meta.length > 0) {
            section.appendChild(renderMetaSection(meta, searchQuery));
        }

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

    function renderDailySummary(daySummary) {
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'border-l-4 border-civic-blue p-4 mb-5 rounded-r-lg';
        summaryDiv.style.background = 'linear-gradient(to right, var(--cw-surface-muted), var(--cw-surface))';

        const summaryHeader = document.createElement('div');
        summaryHeader.className = 'font-semibold text-civic-blue text-xs uppercase tracking-wider mb-2';
        summaryHeader.textContent = 'Daily Summary';
        summaryDiv.appendChild(summaryHeader);

        const summaryText = document.createElement('div');
        summaryText.className = 'text-slate-700 leading-relaxed text-sm';
        summaryText.textContent = daySummary.summary;
        summaryDiv.appendChild(summaryText);

        return summaryDiv;
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
        updateActiveFilterPills,
        renderFeedDay,
        renderBillCard,
        renderStateSnapshots,
        loadLiveNowStrip,
        inferItemState,
        isMetaItem,
        fetchWeeklyCounts,
        formatDate,
        STATE_NAMES,
    };
})();
