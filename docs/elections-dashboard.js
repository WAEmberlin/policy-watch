/**
 * PolicyWatch elections dashboard — upcoming dates and official results links.
 */
const PolicyWatchElections = (() => {
    'use strict';

    const JURISDICTIONS = [
        {
            id: 'federal',
            name: 'U.S. Congress & Federal',
            badgeClass: 'bg-indigo-100 text-indigo-800',
            calendarUrl: 'https://www.eac.gov/voters/election-dates',
            calendarLabel: 'Federal election dates (EAC)',
            resultsUrl: 'https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/',
            resultsLabel: 'FEC election results & voting info',
            dates: [
                { date: '2026-11-03', label: 'General Election — U.S. House, Senate, and state offices nationwide' },
            ],
            note: 'Federal races appear on each state\'s ballot. Use your state links below for registration deadlines and local results.',
        },
        {
            id: 'ks',
            name: 'Kansas',
            badgeClass: 'bg-sky-100 text-sky-800',
            calendarUrl: 'https://kssos.org/elections/important-election-dates.html',
            calendarLabel: 'Important election dates (Kansas SOS)',
            resultsUrl: 'https://www.kssos.org/elections/election-results.html',
            resultsLabel: 'Kansas election results',
            dates: [
                { date: '2026-07-14', label: 'Voter registration deadline (2026 primary)' },
                { date: '2026-07-15', label: 'Advance voting begins (2026 primary)' },
                { date: '2026-08-04', label: 'Primary Election' },
                { date: '2026-10-13', label: 'Voter registration deadline (2026 general)' },
                { date: '2026-10-14', label: 'Advance voting begins (2026 general)' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'co',
            name: 'Colorado',
            badgeClass: 'bg-emerald-100 text-emerald-800',
            calendarUrl: 'https://www.coloradosos.gov/pubs/elections/',
            calendarLabel: 'Elections & voting (Colorado SOS)',
            resultsUrl: 'https://www.coloradosos.gov/pubs/elections/resultsData.html',
            resultsLabel: 'Colorado election results & data',
            dates: [
                { date: '2026-06-30', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'az',
            name: 'Arizona',
            badgeClass: 'bg-orange-100 text-orange-800',
            calendarUrl: 'https://azsos.gov/elections/election-information/2026-election-info',
            calendarLabel: '2026 election info (Arizona SOS)',
            resultsUrl: 'https://results.arizona.vote/',
            resultsLabel: 'Arizona election results',
            dates: [
                { date: '2026-07-21', label: 'Primary Election' },
                { date: '2026-10-05', label: 'Voter registration deadline (2026 general)' },
                { date: '2026-10-07', label: 'Early voting begins (2026 general)' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'ut',
            name: 'Utah',
            badgeClass: 'bg-violet-100 text-violet-800',
            calendarUrl: 'https://vote.utah.gov/',
            calendarLabel: 'Utah voter information',
            resultsUrl: 'https://vote.utah.gov/election-results/',
            resultsLabel: 'Utah election results & data',
            dates: [
                { date: '2026-06-30', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'me',
            name: 'Maine',
            badgeClass: 'bg-rose-100 text-rose-800',
            calendarUrl: 'https://www1.maine.gov/sos/elections-voting/upcoming-elections',
            calendarLabel: 'Upcoming elections (Maine SOS)',
            resultsUrl: 'https://www1.maine.gov/sos/cec/elec/results/index.html',
            resultsLabel: 'Maine election results & data',
            dates: [
                { date: '2026-06-09', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'ne',
            name: 'Nebraska',
            badgeClass: 'bg-amber-100 text-amber-800',
            calendarUrl: 'https://sos.nebraska.gov/elections/upcoming-elections',
            calendarLabel: 'Upcoming elections (Nebraska SOS)',
            resultsUrl: 'https://electionresults.sos.ne.gov/',
            resultsLabel: 'Nebraska election results',
            dates: [
                { date: '2026-05-12', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'md',
            name: 'Maryland',
            badgeClass: 'bg-teal-100 text-teal-800',
            calendarUrl: 'https://elections.maryland.gov/elections/upcoming/index.html',
            calendarLabel: 'Upcoming elections (Maryland SBE)',
            resultsUrl: 'https://elections.maryland.gov/elections/results/index.html',
            resultsLabel: 'Maryland election results',
            dates: [
                { date: '2026-06-23', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'pa',
            name: 'Pennsylvania',
            badgeClass: 'bg-blue-100 text-blue-800',
            calendarUrl: 'https://www.vote.pa.gov/About-Elections/Pages/Upcoming-Elections.aspx',
            calendarLabel: 'Upcoming elections (Pennsylvania DOS)',
            resultsUrl: 'https://www.electionreturns.pa.gov/',
            resultsLabel: 'Pennsylvania election returns',
            dates: [
                { date: '2026-05-19', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'ma',
            name: 'Massachusetts',
            badgeClass: 'bg-indigo-100 text-indigo-800',
            calendarUrl: 'https://www.sec.state.ma.us/divisions/elections/elections-and-voting.htm',
            calendarLabel: 'Elections & voting (Massachusetts Secretary of the Commonwealth)',
            resultsUrl: 'https://electionstats.state.ma.us/',
            resultsLabel: 'Massachusetts election statistics',
            dates: [
                { date: '2026-09-01', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'wv',
            name: 'West Virginia',
            badgeClass: 'bg-sky-100 text-sky-800',
            calendarUrl: 'https://sos.wv.gov/elections/Pages/default.aspx',
            calendarLabel: 'Elections (West Virginia SOS)',
            resultsUrl: 'https://results.enr.clarityelections.com/WV/',
            resultsLabel: 'West Virginia election results',
            dates: [
                { date: '2026-05-12', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'tn',
            name: 'Tennessee',
            badgeClass: 'bg-orange-100 text-orange-800',
            calendarUrl: 'https://sos.tn.gov/elections/calendar',
            calendarLabel: 'Elections calendar (Tennessee SOS)',
            resultsUrl: 'https://sos.tn.gov/elections/results',
            resultsLabel: 'Tennessee election results',
            dates: [
                { date: '2026-07-07', label: 'Voter registration deadline (2026 primary)' },
                { date: '2026-07-17', label: 'Early voting begins (2026 primary)' },
                { date: '2026-08-06', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'nc',
            name: 'North Carolina',
            badgeClass: 'bg-emerald-100 text-emerald-800',
            calendarUrl: 'https://www.ncsbe.gov/voting/upcoming-election',
            calendarLabel: 'Upcoming elections (N.C. State Board of Elections)',
            resultsUrl: 'https://er.ncsbe.gov/',
            resultsLabel: 'North Carolina election results',
            dates: [
                { date: '2026-03-03', label: 'Primary Election' },
                { date: '2026-05-12', label: 'Primary runoff (if needed)' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'mo',
            name: 'Missouri',
            badgeClass: 'bg-violet-100 text-violet-800',
            calendarUrl: 'https://www.sos.mo.gov/elections/calendar',
            calendarLabel: 'Elections calendar (Missouri SOS)',
            resultsUrl: 'https://www.sos.mo.gov/elections/results',
            resultsLabel: 'Missouri election results',
            dates: [
                { date: '2026-08-04', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
        {
            id: 'ia',
            name: 'Iowa',
            badgeClass: 'bg-amber-100 text-amber-800',
            calendarUrl: 'https://sos.iowa.gov/elections/electioninfo/index.html',
            calendarLabel: 'Election information (Iowa SOS)',
            resultsUrl: 'https://electionresults.iowa.gov/',
            resultsLabel: 'Iowa election results',
            dates: [
                { date: '2026-06-02', label: 'Primary Election' },
                { date: '2026-11-03', label: 'General Election' },
            ],
        },
    ];

    function parseLocalDate(dateStr) {
        const [year, month, day] = dateStr.split('-').map(Number);
        return new Date(year, month - 1, day);
    }

    function formatDisplayDate(dateStr) {
        try {
            return parseLocalDate(dateStr).toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'long',
                day: 'numeric',
                year: 'numeric',
            });
        } catch {
            return dateStr;
        }
    }

    function upcomingDates(dates, today) {
        return dates
            .filter((entry) => parseLocalDate(entry.date) >= today)
            .sort((a, b) => parseLocalDate(a.date) - parseLocalDate(b.date));
    }

    function renderDateList(dates) {
        if (!dates.length) {
            return '<p class="text-sm text-slate-500 italic">No upcoming dates on file — see the official calendar for the latest schedule.</p>';
        }
        return `<ul class="space-y-2">${dates.map((entry) => `
            <li class="flex gap-3 text-sm">
                <time datetime="${entry.date}" class="shrink-0 font-medium text-civic-navy w-36 sm:w-40">${formatDisplayDate(entry.date)}</time>
                <span class="text-slate-600">${entry.label}</span>
            </li>`).join('')}</ul>`;
    }

    function renderCard(jurisdiction, today) {
        const dates = upcomingDates(jurisdiction.dates, today);
        return `
            <article class="rounded-xl border p-5 sm:p-6 flex flex-col gap-4" style="background: var(--cw-surface); border-color: var(--cw-border);">
                <div class="flex flex-wrap items-center gap-2">
                    <span class="inline-block px-2.5 py-0.5 rounded text-xs font-semibold ${jurisdiction.badgeClass}">${jurisdiction.name}</span>
                </div>
                <div>
                    <h2 class="text-lg font-bold text-civic-navy mb-3">Important upcoming dates</h2>
                    ${renderDateList(dates)}
                </div>
                ${jurisdiction.note ? `<p class="text-sm text-slate-500 leading-relaxed">${jurisdiction.note}</p>` : ''}
                <div class="flex flex-col sm:flex-row flex-wrap gap-2 pt-2 mt-auto">
                    <a href="${jurisdiction.calendarUrl}" target="_blank" rel="noopener noreferrer"
                       class="inline-flex items-center justify-center gap-1 px-4 py-2.5 text-sm font-medium rounded-lg border-2 border-civic-blue text-civic-blue hover:bg-civic-blue hover:text-white transition-colors">
                        Official election calendar
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                    </a>
                    <a href="${jurisdiction.resultsUrl}" target="_blank" rel="noopener noreferrer"
                       class="inline-flex items-center justify-center gap-1 px-4 py-2.5 text-sm font-medium rounded-lg bg-civic-blue text-white hover:bg-civic-blue-dark transition-colors">
                        Election results
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                    </a>
                </div>
                <p class="text-xs text-slate-400">
                    <a href="${jurisdiction.calendarUrl}" class="hover:underline">${jurisdiction.calendarLabel}</a>
                    ·
                    <a href="${jurisdiction.resultsUrl}" class="hover:underline">${jurisdiction.resultsLabel}</a>
                </p>
            </article>`;
    }

    function init() {
        const container = document.getElementById('elections-dashboard');
        if (!container) return;

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        container.innerHTML = `
            <p class="text-slate-600 leading-relaxed mb-6">
                Key election dates and links to each jurisdiction's official Secretary of State (or federal) election pages.
                Dates are sourced from state election authorities; always confirm deadlines on the official site before you act.
            </p>
            <div class="grid gap-6 lg:grid-cols-2">
                ${JURISDICTIONS.map((j) => renderCard(j, today)).join('')}
            </div>
            <p class="text-xs text-slate-400 mt-8 text-center">
                PolicyWatch tracks legislation — not live vote tallies. For certified results, use the official results links above.
            </p>`;

        if (window.PolicyWatchA11y) {
            PolicyWatchA11y.announce('Election dashboard loaded.');
        }
    }

    return { init, JURISDICTIONS };
})();
