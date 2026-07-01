/**
 * Kansas roll-call vote modal — show who voted yea/nay on a bill.
 */
const CivicWatchBillVotes = (() => {
    'use strict';

    let voteIndex = {};
    let modalEl = null;
    let backdropEl = null;

    function normalizeBillNo(value) {
        return String(value || '').replace(/\s+/g, '').toUpperCase();
    }

    function formatDate(value) {
        if (!value) return '';
        const d = new Date(value);
        if (Number.isNaN(d.getTime())) return String(value).slice(0, 10);
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function formatTally(tally) {
        if (!tally || typeof tally !== 'object') return '';
        const parts = [];
        if (tally.yea != null) parts.push(`Yea ${tally.yea}`);
        if (tally.nay != null) parts.push(`Nay ${tally.nay}`);
        if (tally.present != null && tally.present) parts.push(`Present ${tally.present}`);
        if (tally.absent != null && tally.absent) parts.push(`Absent ${tally.absent}`);
        return parts.join(' · ');
    }

    function chamberLabel(chamber) {
        const c = String(chamber || '').toLowerCase();
        if (c === 'house') return 'House';
        if (c === 'senate') return 'Senate';
        return chamber || '';
    }

    function renderMemberList(label, members, colorClass) {
        if (!members || !members.length) return '';
        const items = members.map((m) => {
            const name = m.name || 'Unknown';
            if (m.url) {
                return `<li><a href="${m.url}" target="_blank" rel="noopener noreferrer" class="text-civic-blue hover:underline">${name}</a></li>`;
            }
            return `<li>${name}</li>`;
        }).join('');
        return `
            <div class="mb-4">
                <h4 class="text-sm font-semibold ${colorClass} mb-2">${label} (${members.length})</h4>
                <ul class="text-sm text-slate-700 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 max-h-48 overflow-y-auto">${items}</ul>
            </div>`;
    }

    function renderVoteDetail(vote) {
        const members = vote.members || {};
        const hasMembers = ['yea', 'nay', 'present', 'absent', 'not_voting'].some(
            (k) => Array.isArray(members[k]) && members[k].length
        );
        const header = `
            <div class="mb-3 pb-3 border-b border-slate-200">
                <div class="text-xs uppercase tracking-wide text-slate-500">${chamberLabel(vote.chamber)} · RCS ${vote.rcs_num || ''}</div>
                <div class="font-medium text-civic-navy mt-1">${vote.result || 'Roll call vote'}</div>
                <div class="text-sm text-slate-500 mt-1">${formatDate(vote.date)}</div>
                <div class="text-sm text-slate-600 mt-1">${formatTally(vote.tally)}</div>
            </div>`;
        if (!hasMembers) {
            return header + '<p class="text-sm text-slate-500 italic">Member-level breakdown not available for this vote yet.</p>';
        }
        return header + [
            renderMemberList('Yea', members.yea, 'text-emerald-700'),
            renderMemberList('Nay', members.nay, 'text-red-700'),
            renderMemberList('Present', members.present, 'text-amber-700'),
            renderMemberList('Absent', members.absent, 'text-slate-600'),
            renderMemberList('Not voting', members.not_voting, 'text-slate-600'),
        ].join('');
    }

    function ensureModal() {
        if (modalEl) return;
        backdropEl = document.createElement('div');
        backdropEl.id = 'cw-vote-modal-backdrop';
        backdropEl.className = 'fixed inset-0 bg-black/50 z-[1000] hidden';
        backdropEl.addEventListener('click', close);

        modalEl = document.createElement('div');
        modalEl.id = 'cw-vote-modal';
        modalEl.className = 'fixed inset-x-4 top-[8vh] md:inset-x-auto md:left-1/2 md:-translate-x-1/2 md:w-full md:max-w-2xl max-h-[84vh] overflow-hidden bg-white rounded-xl shadow-2xl z-[1001] hidden flex flex-col border border-slate-200';
        modalEl.setAttribute('role', 'dialog');
        modalEl.setAttribute('aria-modal', 'true');
        modalEl.innerHTML = `
            <div class="flex items-start justify-between gap-3 p-4 border-b border-slate-200">
                <div>
                    <h2 id="cw-vote-modal-title" class="text-lg font-bold text-civic-navy"></h2>
                    <p id="cw-vote-modal-subtitle" class="text-sm text-slate-500 mt-1"></p>
                </div>
                <button type="button" id="cw-vote-modal-close" class="text-slate-500 hover:text-slate-800 text-2xl leading-none" aria-label="Close">&times;</button>
            </div>
            <div id="cw-vote-modal-body" class="p-4 overflow-y-auto"></div>`;

        document.body.appendChild(backdropEl);
        document.body.appendChild(modalEl);
        modalEl.querySelector('#cw-vote-modal-close').addEventListener('click', close);
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') close();
        });
    }

    function close() {
        if (!modalEl) return;
        modalEl.classList.add('hidden');
        backdropEl.classList.add('hidden');
        document.body.style.overflow = '';
    }

    function open(bill) {
        ensureModal();
        const billNo = normalizeBillNo(bill.bill_number || bill.billNumber);
        const votes = voteIndex[billNo] || [];
        if (!votes.length) return;

        const title = bill.short_title || bill.title || billNo;
        modalEl.querySelector('#cw-vote-modal-title').textContent = `${billNo} — Roll call votes`;
        modalEl.querySelector('#cw-vote-modal-subtitle').textContent = title;

        const body = modalEl.querySelector('#cw-vote-modal-body');
        body.innerHTML = votes.map((vote, i) => `
            <section class="mb-6 ${i ? 'pt-4 border-t border-slate-100' : ''}">
                ${renderVoteDetail(vote)}
            </section>`).join('');

        modalEl.classList.remove('hidden');
        backdropEl.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        modalEl.querySelector('#cw-vote-modal-close').focus();
    }

    function init(siteData) {
        voteIndex = {};
        const records = siteData?.kansas_vote_records || {};
        Object.keys(records).forEach((billNo) => {
            voteIndex[normalizeBillNo(billNo)] = records[billNo];
        });
    }

    function hasVotes(bill) {
        const billNo = normalizeBillNo(bill.bill_number || bill.billNumber);
        return !!(voteIndex[billNo] && voteIndex[billNo].length);
    }

    function getVoteCount(bill) {
        const billNo = normalizeBillNo(bill.bill_number || bill.billNumber);
        return (voteIndex[billNo] || []).length;
    }

    function attachVoteButton(card, bill) {
        if (!hasVotes(bill)) return;
        const billNo = normalizeBillNo(bill.bill_number || bill.billNumber);
        const count = voteIndex[billNo].length;
        const row = document.createElement('div');
        row.className = 'mt-3 flex flex-wrap gap-2';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'px-3 py-1.5 text-sm font-medium rounded-lg bg-civic-blue text-white hover:bg-civic-blue-dark transition-colors';
        btn.textContent = `Roll call votes (${count})`;
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            open(bill);
        });
        row.appendChild(btn);
        card.appendChild(row);
    }

    return { init, open, hasVotes, getVoteCount, attachVoteButton, normalizeBillNo };
})();
