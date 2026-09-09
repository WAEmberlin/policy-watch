/**
 * Shared bill URL + filter helpers for PolicyWatch pages.
 */
const PolicyWatchBillUtils = (() => {
    const SKIP_DOMAINS = ["openstates.org", "open.pluralpolicy.com", "pluralpolicy.com"];
    const LEGACY_CONGRESS_VOTE_RE = /https?:\/\/www\.congress\.gov\/roll-call-vote\/(\d+)(?:st|nd|rd|th)-congress\/(\d+)(?:st|nd|rd|th)-session\/(house|senate)\/(\d+)\/?/i;

    function isOfficialUrl(url) {
        if (!url) return false;
        const lower = url.toLowerCase();
        return !SKIP_DOMAINS.some((domain) => lower.includes(domain));
    }

    function rewriteCongressVoteUrl(url) {
        if (!url) return url || "";
        const match = String(url).match(LEGACY_CONGRESS_VOTE_RE);
        if (!match) return url;
        return `https://www.congress.gov/votes/${match[3].toLowerCase()}/${match[1]}-${match[2]}/${match[4]}`;
    }

    function resolveBillUrl(bill) {
        if (!bill) return "";
        const candidates = [
            bill.url,
            bill.link,
            ...(bill.document_urls || []),
        ].filter(Boolean);

        for (const url of candidates) {
            const rewritten = rewriteCongressVoteUrl(url);
            if (isOfficialUrl(rewritten)) return rewritten;
        }
        return rewriteCongressVoteUrl(bill.url || bill.link || "");
    }

    function filterByStateAndLevel(items, filters, options = {}) {
        const state = (filters.state || "").toUpperCase();
        const level = filters.level || "";
        const query = (filters.query || "").toLowerCase().trim();
        const getState = options.getState || ((item) => item.state);
        const getLevel = options.getLevel || ((item) => item.level);
        const getHaystack = options.getHaystack || ((item) =>
            `${item.title || ""} ${item.summary || ""} ${item.latest_action || ""} ${item.bill_number || ""} ${item.action || ""}`
        );

        return items.filter((item) => {
            const itemState = (getState(item) || "").toUpperCase();
            const itemLevel = getLevel(item) || "";

            if (state === "FEDERAL") {
                if (itemLevel && itemLevel !== "federal") return false;
                if (!itemLevel && itemState && itemState !== "US") return false;
            } else if (state && itemState !== state) {
                return false;
            }

            if (level && itemLevel && itemLevel !== level) return false;

            if (query && !getHaystack(item).toLowerCase().includes(query)) return false;
            return true;
        });
    }

    return { resolveBillUrl, filterByStateAndLevel, isOfficialUrl, rewriteCongressVoteUrl };
})();
