/**
 * CivicWatch expansion layer — multi-state dashboards, unified search, legislators
 */
const CivicWatchExpansion = (() => {
    let siteData = null;

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
                btn.className = btn.dataset.tab === tabId
                    ? 'px-4 py-2 bg-civic-blue text-white rounded-lg text-sm font-medium'
                    : 'px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-medium';
            });

            let items = getTabItems(tabId);

            if (tabId === 'upcoming_hearings') {
                items = CivicWatchBillUtils.filterByStateAndLevel(items, filters, {
                    getHaystack: (event) => `${event.title || ''} ${event.scheduled_date || ''}`,
                });
                contentEl.innerHTML = items.length
                    ? items.map(e => `<div class="p-4 mb-3 border border-slate-200 rounded-lg">
                        <strong>${e.title}</strong>
                        <p class="text-sm text-slate-500">${e.scheduled_date || ''} · ${e.state || 'Federal'}</p>
                        ${e.url ? `<a href="${e.url}" class="text-civic-blue text-sm" target="_blank" rel="noopener">Details →</a>` : ''}
                    </div>`).join('')
                    : `<p class="text-slate-500 italic">${filters.state ? 'No upcoming hearings for the selected filters.' : 'No upcoming hearings.'}</p>`;
                return;
            }

            if (tabId === 'recent_votes') {
                items = CivicWatchBillUtils.filterByStateAndLevel(items, filters, {
                    getHaystack: (vote) =>
                        `${vote.bill_number || ''} ${vote.action || ''} ${vote.motion_text || ''} ${vote.title || ''}`,
                });
                contentEl.innerHTML = items.length
                    ? items.map(renderVoteCard).join('')
                    : `<p class="text-slate-500 italic">${filters.state ? 'No recent votes for the selected state.' : 'No recent votes.'}</p>`;
                return;
            }

            items = filterBills(items, filters);
            contentEl.innerHTML = items.length
                ? `<div class="grid gap-4 md:grid-cols-2">${items.map(renderBillCard).join('')}</div>`
                : `<p class="text-slate-500 italic">${filters.state || filters.level || filters.query ? 'No items match the selected filters.' : 'No items for this dashboard yet.'}</p>`;
        }

        function renderSearchResults() {
            const filters = getFilters();
            const results = filterBills(bills, filters);
            if (!searchResultsEl) return;
            searchResultsEl.innerHTML = filters.query
                ? (results.length
                    ? `<p class="text-sm text-slate-500 mb-3">${results.length} result(s)</p>
                       <div class="grid gap-3 md:grid-cols-2">${results.slice(0, 40).map(renderBillCard).join('')}</div>`
                    : '<p class="text-slate-500 italic">No results found.</p>')
                : '';
        }

        function applyFilters() {
            renderTab(activeTab);
            renderSearchResults();
        }

        tabs.forEach(tab => {
            const btn = document.createElement('button');
            btn.textContent = tab.label;
            btn.dataset.tab = tab.id;
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
        populateStateFilter('leg-state-filter', data.states);

        const listEl = document.getElementById('legislators-list');
        const searchEl = document.getElementById('leg-search');
        const stateEl = document.getElementById('leg-state-filter');

        function render() {
            const q = (searchEl.value || '').toLowerCase();
            const state = stateEl.value;
            const filtered = legislators.filter(l => {
                if (state && state !== 'FEDERAL' && (l.state || '').toUpperCase() !== state) return false;
                if (q && !(l.name || '').toLowerCase().includes(q)) return false;
                return true;
            });

            listEl.innerHTML = filtered.length
                ? filtered.map(l => `
                    <div class="p-4 border border-slate-200 rounded-lg">
                        <h3 class="font-semibold text-civic-navy">${l.name}</h3>
                        <p class="text-sm text-slate-500">${l.party || ''} · ${l.state || ''} · ${l.chamber || ''} ${l.district ? 'District ' + l.district : ''}</p>
                        ${l.url ? `<a href="${l.url}" class="text-civic-blue text-sm mt-2 inline-block" target="_blank">Profile →</a>` : ''}
                    </div>`).join('')
                : '<p class="text-slate-500 italic col-span-2 text-center py-8">No legislators match the selected filters.</p>';
        }

        searchEl.oninput = render;
        stateEl.onchange = render;
        render();
    }

    return { initDashboards, initLegislators, loadSiteData };
})();
