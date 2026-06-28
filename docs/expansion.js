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

    function renderBillCard(bill) {
        const stateLabel = bill.state || (bill.level === 'federal' ? 'Federal' : '');
        const action = bill.latest_action ? `<p class="text-sm text-slate-500 mt-1">${bill.latest_action}</p>` : '';
        const url = bill.url ? `<a href="${bill.url}" class="text-civic-blue hover:underline text-sm" target="_blank">View bill →</a>` : '';
        return `
            <div class="p-4 bg-white border border-slate-200 rounded-lg hover:shadow-md transition-shadow">
                <div class="flex items-start justify-between gap-2">
                    <span class="text-xs font-medium px-2 py-0.5 bg-slate-100 rounded">${stateLabel} ${bill.bill_number || ''}</span>
                    <span class="text-xs text-slate-400">${bill.source || ''}</span>
                </div>
                <h3 class="font-semibold text-civic-navy mt-2">${bill.title || '(no title)'}</h3>
                ${action}
                ${bill.ai_summary_short ? `<p class="text-sm text-slate-600 mt-2">${bill.ai_summary_short}</p>` : ''}
                <div class="mt-2">${url}</div>
            </div>`;
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

    function filterBills(bills, query, state, level) {
        const q = (query || '').toLowerCase();
        return bills.filter(b => {
            if (state === 'FEDERAL' && b.level !== 'federal') return false;
            if (state && state !== 'FEDERAL' && (b.state || '').toUpperCase() !== state) return false;
            if (level && b.level !== level) return false;
            if (!q) return true;
            const hay = `${b.title} ${b.summary || ''} ${b.latest_action || ''} ${(b.ai_topics || []).join(' ')}`.toLowerCase();
            return hay.includes(q);
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
        let activeTab = 'whats_new_today';

        function renderTab(tabId) {
            activeTab = tabId;
            tabsEl.querySelectorAll('button').forEach(btn => {
                btn.className = btn.dataset.tab === tabId
                    ? 'px-4 py-2 bg-civic-blue text-white rounded-lg text-sm font-medium'
                    : 'px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-medium';
            });

            let items = [];
            if (['veterans', 'education', 'property_tax', 'ai_technology', 'public_safety'].includes(tabId)) {
                items = (dashboards.topics || {})[tabId] || [];
            } else {
                items = dashboards[tabId] || [];
            }

            if (tabId === 'upcoming_hearings') {
                contentEl.innerHTML = items.length
                    ? items.map(e => `<div class="p-4 mb-3 border border-slate-200 rounded-lg">
                        <strong>${e.title}</strong>
                        <p class="text-sm text-slate-500">${e.scheduled_date || ''} · ${e.state || 'Federal'}</p>
                        ${e.url ? `<a href="${e.url}" class="text-civic-blue text-sm">Details →</a>` : ''}
                    </div>`).join('')
                    : '<p class="text-slate-500 italic">No upcoming hearings.</p>';
                return;
            }

            if (tabId === 'recent_votes') {
                contentEl.innerHTML = items.length
                    ? items.map(v => `<div class="p-4 mb-3 border border-slate-200 rounded-lg">
                        <strong>${v.bill_number || v.bill_id}</strong>
                        <p class="text-sm">${v.action || ''} · ${v.date || ''}</p>
                    </div>`).join('')
                    : '<p class="text-slate-500 italic">No recent votes.</p>';
                return;
            }

            contentEl.innerHTML = items.length
                ? `<div class="grid gap-4 md:grid-cols-2">${items.map(renderBillCard).join('')}</div>`
                : '<p class="text-slate-500 italic">No items for this dashboard yet. Run the Open States pipeline to populate multi-state data.</p>';
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

        document.getElementById('search-btn').onclick = () => {
            const q = document.getElementById('unified-search').value;
            const state = document.getElementById('state-filter').value;
            const level = document.getElementById('level-filter').value;
            const results = filterBills(bills, q, state, level);
            const el = document.getElementById('search-results');
            el.innerHTML = results.length
                ? `<p class="text-sm text-slate-500 mb-3">${results.length} result(s)</p>
                   <div class="grid gap-3 md:grid-cols-2">${results.slice(0, 40).map(renderBillCard).join('')}</div>`
                : '<p class="text-slate-500 italic">No results found.</p>';
        };
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
                : '<p class="text-slate-500 italic col-span-2 text-center py-8">No legislators loaded yet. Open States data populates this page.</p>';
        }

        searchEl.oninput = render;
        stateEl.onchange = render;
        render();
    }

    return { initDashboards, initLegislators, loadSiteData };
})();
