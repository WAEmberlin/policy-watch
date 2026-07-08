/**
 * Legislator vote history modal — paginated roll-call records per legislator.
 */
const CivicWatchLegislatorVotes = (() => {
    'use strict';

    const PAGE_SIZE = 50;
    let voteIndex = null;
    let loadPromise = null;
    let modalEl = null;
    let backdropEl = null;
    let currentLegislator = null;
    let currentPage = 0;

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

    async function ensureLoaded() {
        if (voteIndex) return voteIndex;
        if (!loadPromise) {
            loadPromise = fetch('legislator_votes.json')
                .then((res) => {
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    return res.json();
                })
                .then((data) => {
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

    function ensureModal() {
        if (modalEl) return;
        backdropEl = document.createElement('div');
        backdropEl.id = 'cw-leg-vote-modal-backdrop';
        backdropEl.className = 'fixed inset-0 bg-black/50 z-[1000] hidden';
        backdropEl.addEventListener('click', close);

        modalEl = document.createElement('div');
        modalEl.id = 'cw-leg-vote-modal';
        modalEl.className = 'fixed inset-x-4 top-[6vh] md:inset-x-auto md:left-1/2 md:-translate-x-1/2 md:w-full md:max-w-4xl max-h-[88vh] overflow-hidden bg-white rounded-xl shadow-2xl z-[1001] hidden flex flex-col border border-slate-200';
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
            <div id="cw-leg-vote-modal-body" class="p-4 overflow-y-auto flex-1"></div>
            <div id="cw-leg-vote-modal-footer" class="p-4 border-t border-slate-200 shrink-0 flex items-center justify-between gap-3"></div>`;

        document.body.appendChild(backdropEl);
        document.body.appendChild(modalEl);
        modalEl.querySelector('#cw-leg-vote-modal-close').addEventListener('click', close);
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
    }

    function renderTable(votes) {
        if (!votes.length) {
            return '<p class="text-sm text-slate-500 italic">No vote records found for this legislator.</p>';
        }
        const rows = votes.map((vote) => `
            <tr class="border-b border-slate-100 hover:bg-slate-50">
                <td class="py-2 pr-3 text-sm font-medium text-civic-navy whitespace-nowrap">${vote.bill_number || '—'}</td>
                <td class="py-2 pr-3 text-sm text-slate-600 whitespace-nowrap">${formatDate(vote.date)}</td>
                <td class="py-2 pr-3 text-sm text-slate-700">${vote.motion || '—'}</td>
                <td class="py-2 pr-3 text-sm ${optionClass(vote.option)}">${vote.option || '—'}</td>
                <td class="py-2 text-sm text-slate-600 whitespace-nowrap">${chamberLabel(vote.chamber)}</td>
            </tr>`).join('');
        return `
            <div class="overflow-x-auto">
                <table class="w-full text-left">
                    <thead>
                        <tr class="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                            <th class="py-2 pr-3 font-semibold">Bill</th>
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

    function renderPagination(totalVotes) {
        const totalPages = Math.max(1, Math.ceil(totalVotes / PAGE_SIZE));
        const page = Math.min(currentPage, totalPages - 1);
        const start = page * PAGE_SIZE + 1;
        const end = Math.min((page + 1) * PAGE_SIZE, totalVotes);
        const prevDisabled = page <= 0;
        const nextDisabled = page >= totalPages - 1;

        return `
            <p class="text-sm text-slate-500">Showing ${start}–${end} of ${totalVotes}</p>
            <div class="flex gap-2">
                <button type="button" id="cw-leg-vote-prev" class="px-3 py-1.5 text-sm rounded-lg border border-slate-200 ${prevDisabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-slate-50'}" ${prevDisabled ? 'disabled' : ''}>Previous</button>
                <span class="px-2 py-1.5 text-sm text-slate-600">Page ${page + 1} of ${totalPages}</span>
                <button type="button" id="cw-leg-vote-next" class="px-3 py-1.5 text-sm rounded-lg border border-slate-200 ${nextDisabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-slate-50'}" ${nextDisabled ? 'disabled' : ''}>Next</button>
            </div>`;
    }

    function renderModalContent() {
        if (!currentLegislator) return;
        const allVotes = voteIndex[currentLegislator.id] || [];
        const totalPages = Math.max(1, Math.ceil(allVotes.length / PAGE_SIZE));
        if (currentPage >= totalPages) currentPage = totalPages - 1;
        if (currentPage < 0) currentPage = 0;
        const pageVotes = allVotes.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

        modalEl.querySelector('#cw-leg-vote-modal-body').innerHTML = renderTable(pageVotes);
        const footer = modalEl.querySelector('#cw-leg-vote-modal-footer');
        footer.innerHTML = allVotes.length ? renderPagination(allVotes.length) : '';

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
        await ensureLoaded();
        if (!legislator?.id || !hasVotes(legislator)) return;

        ensureModal();
        currentLegislator = legislator;
        currentPage = 0;

        const chamberLabelText = chamberLabel(legislator.chamber);
        const meta = [legislator.party, legislator.state, chamberLabelText, legislator.district ? `District ${legislator.district}` : '']
            .filter(Boolean)
            .join(' · ');
        const voteCount = (voteIndex[legislator.id] || []).length;

        modalEl.querySelector('#cw-leg-vote-modal-title').textContent = legislator.name || 'Legislator';
        modalEl.querySelector('#cw-leg-vote-modal-subtitle').textContent = `${meta} — ${voteCount} vote${voteCount === 1 ? '' : 's'}`;

        renderModalContent();

        modalEl.classList.remove('hidden');
        backdropEl.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        modalEl.querySelector('#cw-leg-vote-modal-close').focus();
    }

    function hasVotes(legislator) {
        if (!legislator?.id || !voteIndex) return false;
        const votes = voteIndex[legislator.id];
        return Array.isArray(votes) && votes.length > 0;
    }

    function getVoteCount(legislator) {
        if (!legislator?.id || !voteIndex) return 0;
        return (voteIndex[legislator.id] || []).length;
    }

    async function init() {
        await ensureLoaded();
    }

    return { init, open, close, hasVotes, getVoteCount, ensureLoaded };
})();
