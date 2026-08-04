/**
 * Legislator vote history modal — paginated roll-call records per legislator.
 */
const PolicyWatchLegislatorVotes = (() => {
    'use strict';

    const PAGE_SIZE = 50;
    let voteCounts = {};
    let voteIndex = null;
    let billTitleLookup = null;
    let billUrlLookup = null;
    let countsPromise = null;
    let loadPromise = null;
    let titleLookupPromise = null;
    let modalEl = null;
    let backdropEl = null;
    let currentLegislator = null;
    let currentPage = 0;
    let searchQuery = '';

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function normalizeBillNo(value) {
        return String(value || '').replace(/\s+/g, '').toUpperCase();
    }

    function formatDate(value) {
        if (!value) return '—';
        const d = new Date(value);
        if (Number.isNaN(d.getTime())) return String(value).slice(0, 10);
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function chamberLabel(chamber) {
        const c = String(chamber || '').toLowerCase();
        if (c === 'house' || c === 'lower') return 'House';
        if (c === 'senate' || c === 'upper') return 'Senate';
        if (c.includes('house') || c.includes('representative')) return 'House';
        if (c.includes('senate') || c.includes('senator')) return 'Senate';
        return chamber || '—';
    }

    function optionClass(option) {
        const key = String(option || '').toLowerCase();
        if (key === 'yes') return 'text-emerald-700 font-medium';
        if (key === 'no') return 'text-red-700 font-medium';
        return 'text-slate-600';
    }

    async function ensureCountsLoaded() {
        if (Object.keys(voteCounts).length) return voteCounts;
        if (!countsPromise) {
            countsPromise = policywatchFetch('legislator_vote_counts.json')
                .then((res) => {
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    return res.json();
                })
                .then((data) => {
                    voteCounts = data || {};
                    return voteCounts;
                })
                .catch(() => {
                    voteCounts = {};
                    return voteCounts;
                });
        }
        return countsPromise;
    }

    async function ensureTitleLookupLoaded() {
        if (billTitleLookup && billUrlLookup) return billTitleLookup;
        if (!titleLookupPromise) {
            titleLookupPromise = Promise.all([
                policywatchFetch('bill_title_lookup.json').then((res) => res.ok ? res.json() : {}).catch(() => ({})),
                policywatchFetch('bill_url_lookup.json').then((res) => res.ok ? res.json() : {}).catch(() => ({})),
            ]).then(([titles, urls]) => {
                billTitleLookup = titles || {};
                billUrlLookup = urls || {};
                return billTitleLookup;
            });
        }
        return titleLookupPromise;
    }

    async function ensureLoaded() {
        if (voteIndex) return voteIndex;
        if (!loadPromise) {
            loadPromise = Promise.all([ensureTitleLookupLoaded(), policywatchFetch('legislator_votes.json')
                .then((res) => {
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    return res.json();
                })])
                .then(([, data]) => {
                    voteIndex = data || {};
                    return voteIndex;
                })
                .catch(() => {
                    voteIndex = {};
                    return voteIndex;
                });
        }
        return loadPromise;
    }

    function getBillTitle(vote, state) {
        if (vote?.bill_title) return vote.bill_title;
        if (!billTitleLookup) return '';
        const key = `${String(state || '').toUpperCase()}:${normalizeBillNo(vote?.bill_number)}`;
        return billTitleLookup[key] || '';
    }

    function buildKsBillUrl(billNumber) {
        const normalized = normalizeBillNo(billNumber);
        if (!normalized) return '';
        const resolutionPrefixes = ['HCR', 'SCR', 'HR', 'SR'];
        const isResolution = resolutionPrefixes.some((p) => normalized.startsWith(p));
        if (isResolution) {
            return `https://www.kslegislature.gov/b2025_26/resolutions/${normalized}/`;
        }
        return `https://www.kslegislature.gov/b2025_26/bills/${normalized}`;
    }

    function fixBillUrl(url, state, billNumber) {
        const st = String(state || '').toUpperCase();
        if (st === 'KS') {
            const lower = String(url || '').toLowerCase();
            if (!url || lower.includes('b2023_24') || lower.includes('kslegislature.org') || lower.includes('/measures/')) {
                return buildKsBillUrl(billNumber);
            }
        }
        return url || '';
    }

    function getBillUrl(vote, state) {
        if (vote?.bill_url) return fixBillUrl(vote.bill_url, state, vote?.bill_number);
        const normalized = normalizeBillNo(vote?.bill_number);
        const st = String(state || '').toUpperCase();
        if (billUrlLookup) {
            const key = `${st}:${normalized}`;
            const fromLookup = billUrlLookup[key] || '';
            if (fromLookup) return fixBillUrl(fromLookup, st, vote?.bill_number);
        }
        if (st === 'KS' && normalized) return buildKsBillUrl(vote?.bill_number);
        return '';
    }

    function getVotesForLegislator() {
        if (!currentLegislator?.id || !voteIndex) return [];
        return voteIndex[currentLegislator.id] || [];
    }

    function filterVotes(votes) {
        const q = searchQuery.trim().toLowerCase();
        if (!q) return votes;
        const state = currentLegislator?.state || '';
        return votes.filter((vote) => {
            const title = getBillTitle(vote, state).toLowerCase();
            const haystack = [
                vote.bill_number,
                title,
                vote.motion,
                vote.option,
                vote.chamber,
            ].join(' ').toLowerCase();
            return haystack.includes(q);
        });
    }

    function ensureModal() {
        if (modalEl) return;
        backdropEl = document.createElement('div');
        backdropEl.id = 'cw-leg-vote-modal-backdrop';
        backdropEl.className = 'fixed inset-0 bg-black/50 z-[1000] hidden';
        backdropEl.addEventListener('click', close);

        modalEl = document.createElement('div');
        modalEl.id = 'cw-leg-vote-modal';
        modalEl.className = 'fixed inset-x-4 top-[6vh] md:inset-x-auto md:left-1/2 md:-translate-x-1/2 md:w-full md:max-w-5xl max-h-[88vh] overflow-hidden bg-white rounded-xl shadow-2xl z-[1001] hidden flex flex-col border border-slate-200';
        modalEl.setAttribute('role', 'dialog');
        modalEl.setAttribute('aria-modal', 'true');
        modalEl.innerHTML = `
            <div class="flex items-start justify-between gap-3 p-4 border-b border-slate-200 shrink-0">
                <div>
                    <h2 id="cw-leg-vote-modal-title" class="text-lg font-bold text-civic-navy"></h2>
                    <p id="cw-leg-vote-modal-subtitle" class="text-sm text-slate-500 mt-1"></p>
                </div>
                <button type="button" id="cw-leg-vote-modal-close" class="text-slate-500 hover:text-slate-800 text-2xl leading-none" aria-label="Close">&times;</button>
            </div>
            <div class="px-4 py-3 border-b border-slate-100 shrink-0">
                <label for="cw-leg-vote-search" class="sr-only">Search votes</label>
                <input
                    type="search"
                    id="cw-leg-vote-search"
                    placeholder="Search by bill number, title, motion, or vote..."
                    class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-civic-blue"
                />
            </div>
            <div id="cw-leg-vote-modal-body" class="p-4 overflow-y-auto flex-1"></div>
            <div id="cw-leg-vote-modal-footer" class="p-4 border-t border-slate-200 shrink-0 flex items-center justify-between gap-3"></div>`;

        document.body.appendChild(backdropEl);
        document.body.appendChild(modalEl);
        modalEl.querySelector('#cw-leg-vote-modal-close').addEventListener('click', close);
        modalEl.querySelector('#cw-leg-vote-search').addEventListener('input', (e) => {
            searchQuery = e.target.value || '';
            currentPage = 0;
            renderModalContent();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') close();
        });
    }

    function close() {
        if (!modalEl) return;
        modalEl.classList.add('hidden');
        backdropEl.classList.add('hidden');
        document.body.style.overflow = '';
        currentLegislator = null;
        currentPage = 0;
        searchQuery = '';
        const searchEl = modalEl.querySelector('#cw-leg-vote-search');
        if (searchEl) searchEl.value = '';
    }

    function showLoading(message) {
        modalEl.querySelector('#cw-leg-vote-modal-body').innerHTML =
            `<p class="text-sm text-slate-500 italic py-8 text-center">${message}</p>`;
        modalEl.querySelector('#cw-leg-vote-modal-footer').innerHTML = '';
    }

    function renderTable(votes) {
        if (!votes.length) {
            const message = searchQuery.trim()
                ? 'No votes match your search.'
                : 'No vote records found for this legislator.';
            return `<p class="text-sm text-slate-500 italic">${message}</p>`;
        }
        const state = currentLegislator?.state || '';
        const rows = votes.map((vote) => {
            const title = getBillTitle(vote, state);
            const billUrl = getBillUrl(vote, state);
            const billNo = escapeHtml(vote.bill_number || '—');
            const billCell = billUrl
                ? `<a href="${escapeHtml(billUrl)}" target="_blank" rel="noopener noreferrer" class="text-civic-blue hover:underline">${billNo}</a>`
                : billNo;
            return `
            <tr class="border-b border-slate-100 hover:bg-slate-50">
                <td class="py-2 pr-3 text-sm font-medium whitespace-nowrap align-top">${billCell}</td>
                <td class="py-2 pr-3 text-sm text-slate-700 align-top">${title ? escapeHtml(title) : '<span class="text-slate-400 italic">—</span>'}</td>
                <td class="py-2 pr-3 text-sm text-slate-600 whitespace-nowrap align-top">${formatDate(vote.date)}</td>
                <td class="py-2 pr-3 text-sm text-slate-700 align-top">${escapeHtml(vote.motion || '—')}</td>
                <td class="py-2 pr-3 text-sm ${optionClass(vote.option)} whitespace-nowrap align-top">${escapeHtml(vote.option || '—')}</td>
                <td class="py-2 text-sm text-slate-600 whitespace-nowrap align-top">${chamberLabel(vote.chamber)}</td>
            </tr>`;
        }).join('');
        return `
            <div class="overflow-x-auto">
                <table class="w-full text-left">
                    <thead>
                        <tr class="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                            <th class="py-2 pr-3 font-semibold">Bill</th>
                            <th class="py-2 pr-3 font-semibold">Title</th>
                            <th class="py-2 pr-3 font-semibold">Date</th>
                            <th class="py-2 pr-3 font-semibold">Motion / Result</th>
                            <th class="py-2 pr-3 font-semibold">Vote</th>
                            <th class="py-2 font-semibold">Chamber</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
    }

    function renderPagination(totalVotes, totalUnfiltered) {
        const totalPages = Math.max(1, Math.ceil(totalVotes / PAGE_SIZE));
        const page = Math.min(currentPage, totalPages - 1);
        const start = totalVotes ? page * PAGE_SIZE + 1 : 0;
        const end = Math.min((page + 1) * PAGE_SIZE, totalVotes);
        const prevDisabled = page <= 0;
        const nextDisabled = page >= totalPages - 1;
        const filteredNote = searchQuery.trim() && totalUnfiltered !== totalVotes
            ? ` (${totalVotes} of ${totalUnfiltered} match search)`
            : '';

        return `
            <p class="text-sm text-slate-500">Showing ${start}–${end} of ${totalVotes}${filteredNote}</p>
            <div class="flex gap-2">
                <button type="button" id="cw-leg-vote-prev" class="px-3 py-1.5 text-sm rounded-lg border border-slate-200 ${prevDisabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-slate-50'}" ${prevDisabled ? 'disabled' : ''}>Previous</button>
                <span class="px-2 py-1.5 text-sm text-slate-600">Page ${page + 1} of ${totalPages}</span>
                <button type="button" id="cw-leg-vote-next" class="px-3 py-1.5 text-sm rounded-lg border border-slate-200 ${nextDisabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-slate-50'}" ${nextDisabled ? 'disabled' : ''}>Next</button>
            </div>`;
    }

    function updateSubtitle(totalVotes) {
        if (!currentLegislator) return;
        const chamberLabelText = chamberLabel(currentLegislator.chamber);
        const meta = [currentLegislator.party, currentLegislator.state, chamberLabelText, currentLegislator.district ? `District ${currentLegislator.district}` : '']
            .filter(Boolean)
            .join(' · ');
        const allVotes = getVotesForLegislator();
        const filtered = filterVotes(allVotes);
        const countLabel = searchQuery.trim() && filtered.length !== allVotes.length
            ? `${filtered.length} of ${allVotes.length} votes`
            : `${allVotes.length} vote${allVotes.length === 1 ? '' : 's'}`;
        modalEl.querySelector('#cw-leg-vote-modal-subtitle').textContent = `${meta} — ${countLabel}`;
    }

    function renderModalContent() {
        if (!currentLegislator) return;
        const allVotes = getVotesForLegislator();
        const filteredVotes = filterVotes(allVotes);
        const totalPages = Math.max(1, Math.ceil(filteredVotes.length / PAGE_SIZE));
        if (currentPage >= totalPages) currentPage = totalPages - 1;
        if (currentPage < 0) currentPage = 0;
        const pageVotes = filteredVotes.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

        updateSubtitle(filteredVotes.length);
        modalEl.querySelector('#cw-leg-vote-modal-body').innerHTML = renderTable(pageVotes);
        const footer = modalEl.querySelector('#cw-leg-vote-modal-footer');
        footer.innerHTML = filteredVotes.length || searchQuery.trim()
            ? renderPagination(filteredVotes.length, allVotes.length)
            : '';

        const prevBtn = footer.querySelector('#cw-leg-vote-prev');
        const nextBtn = footer.querySelector('#cw-leg-vote-next');
        prevBtn?.addEventListener('click', () => {
            if (currentPage > 0) {
                currentPage -= 1;
                renderModalContent();
            }
        });
        nextBtn?.addEventListener('click', () => {
            if (currentPage < totalPages - 1) {
                currentPage += 1;
                renderModalContent();
            }
        });
    }

    async function open(legislator) {
        if (!legislator?.id || !hasVotes(legislator)) return;

        ensureModal();
        currentLegislator = legislator;
        currentPage = 0;
        searchQuery = '';
        const searchEl = modalEl.querySelector('#cw-leg-vote-search');
        if (searchEl) searchEl.value = '';

        const chamberLabelText = chamberLabel(legislator.chamber);
        const meta = [legislator.party, legislator.state, chamberLabelText, legislator.district ? `District ${legislator.district}` : '']
            .filter(Boolean)
            .join(' · ');
        const voteCount = getVoteCount(legislator);

        modalEl.querySelector('#cw-leg-vote-modal-title').textContent = legislator.name || 'Legislator';
        modalEl.querySelector('#cw-leg-vote-modal-subtitle').textContent = `${meta} — ${voteCount} vote${voteCount === 1 ? '' : 's'}`;
        showLoading('Loading vote history…');

        modalEl.classList.remove('hidden');
        backdropEl.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        modalEl.querySelector('#cw-leg-vote-modal-close').focus();

        await ensureLoaded();
        if (!currentLegislator || currentLegislator.id !== legislator.id) return;
        if (!hasVotes(legislator)) {
            showLoading('No vote records found for this legislator.');
            return;
        }
        renderModalContent();
    }

    function hasVotes(legislator) {
        if (!legislator?.id) return false;
        return getVoteCount(legislator) > 0;
    }

    function getVoteCount(legislator) {
        if (!legislator?.id) return 0;
        return voteCounts[legislator.id] || 0;
    }

    async function init() {
        await ensureCountsLoaded();
    }

    return { init, open, close, hasVotes, getVoteCount, ensureLoaded, ensureCountsLoaded };
})();
