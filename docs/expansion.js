/**
 * CivicWatch expansion layer — multi-state dashboards, unified search, legislators
 */
const CivicWatchExpansion = (() => {
    let siteData = null;

    function a11yAnnounce(message) {
        if (window.CivicWatchA11y && typeof CivicWatchA11y.announce === "function" && message) {
            CivicWatchA11y.announce(message);
        }
    }

    async function loadSiteData() {
        if (siteData) return siteData;
        const res = await fetch('site_data.json');
        siteData = await res.json();
        return siteData;
    }

    function getFilters() {
        return {
            state: document.getElementById('state-filter')?.value || '',
            level: document.getElementById('level-filter')?.value || '',
            query: (document.getElementById('unified-search')?.value || '').trim(),
        };
    }

    function renderBillCard(bill) {
        const stateLabel = bill.state || (bill.level === 'federal' ? 'Federal' : '');
        const action = bill.latest_action ? `<p class="text-sm text-slate-500 mt-1">${bill.latest_action}</p>` : '';
        const url = CivicWatchBillUtils.resolveBillUrl(bill);
        const link = url
            ? `<a href="${url}" class="text-civic-blue hover:underline text-sm" target="_blank" rel="noopener">View on ${stateLabel || 'official'} site →</a>`
            : '';
        const cardInner = `
            <div class="flex items-start justify-between gap-2">
                <span class="text-xs font-medium px-2 py-0.5 bg-slate-100 rounded">${stateLabel} ${bill.bill_number || ''}</span>
                <span class="text-xs text-slate-400">${bill.source || ''}</span>
            </div>
            <h3 class="font-semibold text-civic-navy mt-2">${bill.title || '(no title)'}</h3>
            ${action}
            ${bill.ai_summary_short ? `<p class="text-sm text-slate-600 mt-2">${bill.ai_summary_short}</p>` : ''}
            <div class="mt-2">${link}</div>`;

        if (url) {
            return `<a href="${url}" target="_blank" rel="noopener" class="block p-4 bg-white border border-slate-200 rounded-lg hover:shadow-md hover:border-civic-blue transition-all">${cardInner}</a>`;
        }
        return `<div class="p-4 bg-white border border-slate-200 rounded-lg">${cardInner}</div>`;
    }

    function renderVoteCard(vote) {
        const stateLabel = vote.state || '';
        const url = vote.url || '';
        const inner = `
            <div class="flex items-start justify-between gap-2">
                <strong>${vote.bill_number || vote.bill_id || 'Vote'}</strong>
                <span class="text-xs text-slate-400">${stateLabel}</span>
            </div>
            <p class="text-sm mt-1">${vote.action || vote.motion_text || ''}</p>
            <p class="text-xs text-slate-500 mt-1">${vote.date || ''}</p>
            ${vote.title ? `<p class="text-sm text-slate-600 mt-1">${vote.title}</p>` : ''}
            ${url ? `<span class="text-civic-blue text-sm mt-2 inline-block">View bill →</span>` : ''}`;
        if (url) {
            return `<a href="${url}" target="_blank" rel="noopener" class="block p-4 mb-3 border border-slate-200 rounded-lg hover:shadow-md hover:border-civic-blue transition-all">${inner}</a>`;
        }
        return `<div class="p-4 mb-3 border border-slate-200 rounded-lg">${inner}</div>`;
    }

    function populateStateFilter(selectId, states) {
        const sel = document.getElementById(selectId);
        if (!sel) return;
        (states || []).forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.code.toUpperCase();
            opt.textContent = s.name;
            sel.appendChild(opt);
        });
        const fedOpt = document.createElement('option');
        fedOpt.value = 'FEDERAL';
        fedOpt.textContent = 'Federal';
        sel.insertBefore(fedOpt, sel.children[1] || null);
    }

    function filterBills(bills, filters) {
        return CivicWatchBillUtils.filterByStateAndLevel(bills, filters, {
            getHaystack: (bill) =>
                `${bill.title || ''} ${bill.summary || ''} ${bill.latest_action || ''} ${(bill.ai_topics || []).join(' ')} ${bill.bill_number || ''}`,
        });
    }

    async function initDashboards() {
        const data = await loadSiteData();
        const dashboards = data.dashboards || {};
        const searchIndex = data.search_index || {};
        const bills = searchIndex.bills || [];

        populateStateFilter('state-filter', data.states);

        const tabs = [
            { id: 'whats_new_today', label: "What's New Today" },
            { id: 'recent_bills', label: 'Recent Bills' },
            { id: 'upcoming_hearings', label: 'Upcoming Hearings' },
            { id: 'recent_votes', label: 'Recent Votes' },
            { id: 'signed_into_law', label: 'Signed Into Law' },
            { id: 'veterans', label: 'Veterans' },
            { id: 'education', label: 'Education' },
            { id: 'property_tax', label: 'Property Tax' },
            { id: 'ai_technology', label: 'AI & Technology' },
            { id: 'public_safety', label: 'Public Safety' },
        ];

        const tabsEl = document.getElementById('dashboard-tabs');
        const contentEl = document.getElementById('dashboard-content');
        const searchResultsEl = document.getElementById('search-results');
        let activeTab = 'whats_new_today';

        function getTabItems(tabId) {
            if (['veterans', 'education', 'property_tax', 'ai_technology', 'public_safety'].includes(tabId)) {
                return (dashboards.topics || {})[tabId] || [];
            }
            return dashboards[tabId] || [];
        }

        function renderTab(tabId) {
            activeTab = tabId;
            const filters = getFilters();

            tabsEl.querySelectorAll('button').forEach(btn => {
                const isActive = btn.dataset.tab === tabId;
                btn.className = isActive
                    ? 'px-4 py-2 bg-civic-blue text-white rounded-lg text-sm font-medium'
                    : 'px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-medium';
                btn.setAttribute('role', 'tab');
                btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });

            let items = getTabItems(tabId);

            if (tabId === 'upcoming_hearings') {
                items = CivicWatchBillUtils.filterByStateAndLevel(items, filters, {
                    getHaystack: (event) => `${event.title || ''} ${event.scheduled_date || ''}`,
                });
                contentEl.setAttribute('aria-busy', 'false');
                contentEl.innerHTML = items.length
                    ? items.map(e => `<div class="p-4 mb-3 border border-slate-200 rounded-lg">
                        <strong>${e.title}</strong>
                        <p class="text-sm text-slate-500">${e.scheduled_date || ''} · ${e.state || 'Federal'}</p>
                        ${e.url ? `<a href="${e.url}" class="text-civic-blue text-sm" target="_blank" rel="noopener">Details →</a>` : ''}
                    </div>`).join('')
                    : `<p class="text-slate-500 italic">${filters.state ? 'No upcoming hearings for the selected filters.' : 'No upcoming hearings.'}</p>`;
                a11yAnnounce(`${items.length} upcoming hearing${items.length === 1 ? '' : 's'}.`);
                return;
            }

            if (tabId === 'recent_votes') {
                items = CivicWatchBillUtils.filterByStateAndLevel(items, filters, {
                    getHaystack: (vote) =>
                        `${vote.bill_number || ''} ${vote.action || ''} ${vote.motion_text || ''} ${vote.title || ''}`,
                });
                contentEl.setAttribute('aria-busy', 'false');
                contentEl.innerHTML = items.length
                    ? items.map(renderVoteCard).join('')
                    : `<p class="text-slate-500 italic">${filters.state ? 'No recent votes for the selected state.' : 'No recent votes.'}</p>`;
                a11yAnnounce(`${items.length} recent vote${items.length === 1 ? '' : 's'}.`);
                return;
            }

            items = filterBills(items, filters);
            contentEl.setAttribute('aria-busy', 'false');
            contentEl.innerHTML = items.length
                ? `<div class="grid gap-4 md:grid-cols-2">${items.map(renderBillCard).join('')}</div>`
                : `<p class="text-slate-500 italic">${filters.state || filters.level || filters.query ? 'No items match the selected filters.' : 'No items for this dashboard yet.'}</p>`;
            a11yAnnounce(`${items.length} dashboard item${items.length === 1 ? '' : 's'}.`);
        }

        function renderSearchResults() {
            const filters = getFilters();
            const results = filterBills(bills, filters);
            if (!searchResultsEl) return;
            if (filters.query) {
                a11yAnnounce(`${results.length} search result${results.length === 1 ? '' : 's'}.`);
            }
            searchResultsEl.innerHTML = filters.query
                ? (results.length
                    ? `<p class="text-sm text-slate-500 mb-3">${results.length} result(s)</p>
                       <div class="grid gap-3 md:grid-cols-2">${results.slice(0, 40).map(renderBillCard).join('')}</div>`
                    : '<p class="text-slate-500 italic" role="status">No results found.</p>')
                : '';
        }

        function applyFilters() {
            renderTab(activeTab);
            renderSearchResults();
        }

        tabs.forEach(tab => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = tab.label;
            btn.dataset.tab = tab.id;
            btn.setAttribute('role', 'tab');
            btn.setAttribute('aria-selected', tab.id === activeTab ? 'true' : 'false');
            btn.className = 'px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-medium';
            btn.onclick = () => renderTab(tab.id);
            tabsEl.appendChild(btn);
        });

        renderTab(activeTab);

        document.getElementById('state-filter')?.addEventListener('change', applyFilters);
        document.getElementById('level-filter')?.addEventListener('change', applyFilters);
        document.getElementById('unified-search')?.addEventListener('input', applyFilters);
        document.getElementById('search-btn')?.addEventListener('click', applyFilters);
    }

    async function initLegislators() {
        const data = await loadSiteData();
        const legislators = (data.search_index || {}).legislators || [];
        const statsData = data.legislator_stats || {};
        populateStateFilter('leg-state-filter', data.states);
        populateStateFilter('leg-stats-state-filter', data.states);

        const listEl = document.getElementById('legislators-list');
        const statsEl = document.getElementById('legislators-stats');
        const searchEl = document.getElementById('leg-search');
        const stateEl = document.getElementById('leg-state-filter');
        const statsStateEl = document.getElementById('leg-stats-state-filter');
        const directoryPanel = document.getElementById('leg-directory-panel');
        const statsPanel = document.getElementById('leg-stats-panel');
        const tabDirectory = document.getElementById('leg-tab-directory');
        const tabStats = document.getElementById('leg-tab-stats');
        let activeView = 'directory';

        function getSelectedState() {
            return activeView === 'stats'
                ? (statsStateEl?.value || '')
                : (stateEl?.value || '');
        }

        function syncStateFilters(value) {
            if (stateEl && stateEl.value !== value) stateEl.value = value;
            if (statsStateEl && statsStateEl.value !== value) statsStateEl.value = value;
        }

        function formatChamber(chamber) {
            const lower = (chamber || '').toLowerCase();
            if (lower === 'lower' || lower === 'house') return 'House';
            if (lower === 'upper' || lower === 'senate') return 'Senate';
            return chamber || '';
        }

        function renderLegislatorCard(l) {
            const chamberLabel = formatChamber(l.chamber);
            const district = l.district ? `District ${l.district}` : '';
            const meta = [l.party, l.state, chamberLabel, district].filter(Boolean).join(' · ');
            const inner = `
                <h3 class="font-semibold text-civic-navy">${l.name}</h3>
                <p class="text-sm text-slate-500">${meta}</p>
                ${l.url ? '<span class="text-civic-blue text-sm mt-2 inline-block">Official profile →</span>' : ''}`;
            if (l.url) {
                return `<a href="${l.url}" target="_blank" rel="noopener noreferrer" class="block p-4 border border-slate-200 rounded-lg hover:shadow-md hover:border-civic-blue transition-all">${inner}</a>`;
            }
            return `<div class="p-4 border border-slate-200 rounded-lg">${inner}</div>`;
        }

        function renderStatBars(title, counts) {
            const entries = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]);
            if (!entries.length) {
                return `<div class="mb-6"><h3 class="font-semibold text-civic-navy mb-2">${title}</h3><p class="text-sm text-slate-500 italic">No data available.</p></div>`;
            }
            const total = entries.reduce((sum, [, count]) => sum + count, 0);
            const rows = entries.map(([label, count]) => {
                const pct = total ? Math.round((count / total) * 100) : 0;
                return `<div class="mb-3">
                    <div class="flex justify-between text-sm mb-1"><span>${label}</span><span class="text-slate-500">${count} (${pct}%)</span></div>
                    <div class="h-2 rounded-full bg-slate-100 overflow-hidden"><div class="h-full bg-civic-blue rounded-full" style="width:${pct}%"></div></div>
                </div>`;
            }).join('');
            return `<div class="mb-6"><h3 class="font-semibold text-civic-navy mb-3">${title}</h3>${rows}</div>`;
        }

        function renderStats() {
            if (!statsEl) return;
            const state = getSelectedState();
            const byState = statsData.by_state || {};
            const notes = statsData.data_notes || {};

            if (state === 'FEDERAL') {
                statsEl.innerHTML = `<p class="text-slate-500 italic text-center py-8">${notes.federal || 'Congress members are not yet in the normalized legislator dataset.'}</p>`;
                statsEl.setAttribute('aria-busy', 'false');
                return;
            }

            const stateKey = state || '';
            const statesToShow = stateKey ? [stateKey] : Object.keys(byState).sort();

            if (stateKey && !byState[stateKey]) {
                statsEl.innerHTML = '<p class="text-slate-500 italic text-center py-8">No legislator stats available for the selected state.</p>';
                statsEl.setAttribute('aria-busy', 'false');
                return;
            }

            if (!statesToShow.length) {
                statsEl.innerHTML = '<p class="text-slate-500 italic text-center py-8">No legislator stats available yet.</p>';
                return;
            }

            statsEl.innerHTML = statesToShow.map(st => {
                const bucket = byState[st] || {};
                const ageBuckets = bucket.age_buckets || {};
                const ageSummary = bucket.average_age != null
                    ? `<p class="text-sm text-slate-600 mb-4">Average age: <strong>${bucket.average_age}</strong> (where birth date is known)</p>`
                    : '<p class="text-sm text-slate-500 mb-4">Average age unavailable — most legislators lack birth dates in source data.</p>';
                return `<section class="mb-10 p-5 rounded-xl border" style="border-color: var(--cw-border); background: var(--cw-surface-muted);">
                    <h2 class="text-xl font-bold text-civic-navy mb-1">${st}</h2>
                    <p class="text-sm text-slate-500 mb-4">${bucket.total || 0} legislators</p>
                    ${renderStatBars('Party', bucket.party)}
                    ${renderStatBars('Gender', bucket.gender)}
                    ${renderStatBars('Chamber', bucket.chamber)}
                    ${ageSummary}
                    ${renderStatBars('Age ranges', {
                        'Under 40': ageBuckets.under_40 || 0,
                        '40–59': ageBuckets['40_59'] || 0,
                        '60+': ageBuckets['60_plus'] || 0,
                        'Unknown': ageBuckets.unknown || 0,
                    })}
                    <p class="text-sm text-slate-500 italic">${notes.race || 'Race and ethnicity data is not available from the current source.'}</p>
                </section>`;
            }).join('');
            statsEl.setAttribute('aria-busy', 'false');
            a11yAnnounce('Legislator stats updated.');
        }

        function setActiveView(view) {
            activeView = view;
            const isDirectory = view === 'directory';
            directoryPanel.classList.toggle('hidden', !isDirectory);
            statsPanel.classList.toggle('hidden', isDirectory);
            tabDirectory.className = isDirectory
                ? 'px-4 py-2 bg-civic-blue text-white rounded-lg text-sm font-medium'
                : 'px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-medium';
            tabStats.className = !isDirectory
                ? 'px-4 py-2 bg-civic-blue text-white rounded-lg text-sm font-medium'
                : 'px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-medium';
            tabDirectory.setAttribute('aria-selected', isDirectory ? 'true' : 'false');
            tabStats.setAttribute('aria-selected', !isDirectory ? 'true' : 'false');
            if (!isDirectory) renderStats();
        }

        function renderDirectory() {
            const q = (searchEl.value || '').toLowerCase();
            const state = getSelectedState();

            if (state === 'FEDERAL') {
                listEl.innerHTML = `<p class="text-slate-500 italic col-span-2 text-center py-8">${statsData.data_notes?.federal || 'Congress members are not yet in the normalized legislator dataset.'}</p>`;
                listEl.setAttribute('aria-busy', 'false');
                if (activeView === 'stats') renderStats();
                return;
            }

            const filtered = legislators.filter(l => {
                if (state && (l.state || '').toUpperCase() !== state) return false;
                if (q && !(l.name || '').toLowerCase().includes(q)) return false;
                return true;
            });

            listEl.innerHTML = filtered.length
                ? filtered.map(renderLegislatorCard).join('')
                : '<p class="text-slate-500 italic col-span-2 text-center py-8">No legislators match the selected filters.</p>';
            listEl.setAttribute('aria-busy', 'false');
            a11yAnnounce(`${filtered.length} legislator${filtered.length === 1 ? '' : 's'} shown.`);
            if (activeView === 'stats') renderStats();
        }

        searchEl.oninput = renderDirectory;
        stateEl?.addEventListener('change', () => {
            syncStateFilters(stateEl.value);
            renderDirectory();
        });
        statsStateEl?.addEventListener('change', () => {
            syncStateFilters(statsStateEl.value);
            renderDirectory();
        });
        tabDirectory?.addEventListener('click', () => setActiveView('directory'));
        tabStats?.addEventListener('click', () => setActiveView('stats'));
        renderDirectory();
    }

    return { initDashboards, initLegislators, loadSiteData };
})();
