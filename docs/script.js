let currentYear = null;
let currentPage = 0;  // Time-chunk index (0 = most recent period)
let currentItemPage = 0;  // Item page within a time chunk (veterans filters only)
let allData = null;
let searchQuery = "";
let searchMode = false;
let searchResults = [];
let selectedSource = "";
let selectedCategory = "";
let selectedState = "";
let veteransImpactFilter = null;
const DAYS_PER_CHUNK = 14;  // Show 2 weeks per "page"
const VETERANS_FEED_ITEM_LIMIT = 100;
const SEARCH_MIN_CHARS = 3;
const SEARCH_MAX_RESULTS = 200;

function a11yAnnounce(message) {
    if (window.CivicWatchA11y && typeof CivicWatchA11y.announce === "function" && message) {
        CivicWatchA11y.announce(message);
    }
}

function setContentBusy(isBusy) {
    const content = document.getElementById("content");
    if (content) content.setAttribute("aria-busy", isBusy ? "true" : "false");
}

const STATE_NAMES = { KS: "Kansas", CO: "Colorado", AZ: "Arizona", UT: "Utah", ME: "Maine", NE: "Nebraska", MD: "Maryland", Federal: "U.S. Congress" };

function inferItemState(item) {
    if (typeof CivicWatchHome !== "undefined") return CivicWatchHome.inferItemState(item);
    if (item.level === "federal") return "Federal";
    if (item.state) return item.state;
    const src = (item.source || "").toLowerCase();
    if (src.includes("congress") || src.includes("federal") || src.includes("u.s.")) return "Federal";
    if (src.includes("kansas")) return "KS";
    if (src.includes("colorado")) return "CO";
    if (src.includes("arizona")) return "AZ";
    if (src.includes("utah")) return "UT";
    if (src.includes("maine")) return "ME";
    if (src.includes("nebraska")) return "NE";
    if (src.includes("maryland")) return "MD";
    return "";
}

function itemMatchesStateFilter(item) {
    if (!selectedState) return true;
    return inferItemState(item) === selectedState;
}

function isVoteFeedItem(item) {
    if (typeof CivicWatchHome !== "undefined" && CivicWatchHome.isVoteEvent) {
        return CivicWatchHome.isVoteEvent(item);
    }
    return item.item_type === "vote_event" || Boolean(item.vote_tally);
}

function classifyActionType(text) {
    if (typeof CivicWatchHome !== "undefined" && CivicWatchHome.classifyActionType) {
        return CivicWatchHome.classifyActionType(text);
    }
    const hay = String(text || "").toLowerCase();
    if (!hay.trim()) return null;
    if (/signed|became (a )?law|enacted|chaptered/.test(hay)) return "enacted";
    if (/veto/.test(hay)) return "vetoed";
    if (/died|dead|pocket veto|failed to pass|defeated/.test(hay)) return "died";
    if (/\bfailed\b/.test(hay)) return "failed";
    if (/referr?ed/.test(hay)) return "referred";
    if (/passed|adopted|approved|agreed to|concurred/.test(hay)) return "passed";
    if (/vote|roll.?call|\byea\b|\bnay\b/.test(hay)) return "vote";
    return null;
}

function buildFeedSearchText(item) {
    const parts = [
        item.title,
        item.short_title,
        item.summary,
        item.bill_number,
        item.motion,
        item.vote_tally,
        item.latest_action,
        item.official_title,
        item.sponsor_name,
    ];
    return parts.filter(Boolean).join(" ").toLowerCase();
}

function itemMatchesVeteransFilter(item) {
    if (!veteransImpactFilter) return true;
    if (typeof CivicWatchHome !== "undefined" && CivicWatchHome.itemMatchesVeteransImpactFilter) {
        return CivicWatchHome.itemMatchesVeteransImpactFilter(item, veteransImpactFilter);
    }
    return true;
}

function feedEmptyMessage(dateRange) {
    const rangeLabel = `${formatDate(dateRange.start)} – ${formatDate(dateRange.end)}`;
    if (veteransImpactFilter) {
        const filterLabels = {
            all: "military or veterans-related",
            red: "high-impact veterans-related",
            yellow: "moderate-impact veterans-related",
            green: "ceremonial or general veterans-related",
        };
        const topicLabel = filterLabels[veteransImpactFilter] || "military or veterans-related";
        const stateLabel = selectedState
            ? (STATE_NAMES[selectedState] || selectedState)
            : "any state";
        return `No ${topicLabel} activity for ${stateLabel} during ${rangeLabel}. Try another filter, state, or time period.`;
    }
    if (selectedState) {
        const stateLabel = STATE_NAMES[selectedState] || selectedState;
        return `No legislative activity for ${stateLabel} during ${rangeLabel}.`;
    }
    return `No legislative activity for ${rangeLabel}.`;
}

function refreshView() {
    updateFilterPills();
    if (searchMode && searchQuery) {
        performSearch(searchQuery);
    } else if (currentYear) {
        displayUnifiedView(currentYear, currentPage);
    }
}

function updateFilterPills() {
    if (typeof CivicWatchHome === "undefined") return;
    CivicWatchHome.updateActiveFilterPills({
        state: selectedState,
        source: selectedSource,
        category: selectedCategory,
        search: searchMode ? searchQuery : "",
        veteransImpact: veteransImpactFilter,
    });
}

async function loadData() {
    setContentBusy(true);
    try {
        const res = await civicwatchFetch("site_data.json");
        allData = await res.json();
        if (typeof CivicWatchBillVotes !== 'undefined') {
            CivicWatchBillVotes.init(allData);
        }
        if (typeof CivicWatchHome !== 'undefined' && CivicWatchHome.setVeteranImpactLookup) {
            CivicWatchHome.setVeteranImpactLookup((allData.veteran_impact || {}).lookup || {});
        }
    } catch (error) {
        setContentBusy(false);
        document.getElementById("content").innerHTML = 
            "<div class='bg-red-50 border-l-4 border-red-500 p-4 rounded-r-lg text-red-700' role='alert'>Error loading data. Please try again later.</div>";
        a11yAnnounce("Error loading data.");
        return;
    }
    
    // Load weekly overview
    loadWeeklyOverview();

    // Update last updated timestamp
    const lastUpdatedEl = document.getElementById("last-updated");
    if (lastUpdatedEl) {
        const updatedDate = new Date(allData.last_updated);
        lastUpdatedEl.textContent = "Last updated: " + 
            updatedDate.toLocaleString("en-US", {
                timeZone: "America/Chicago",
                year: "numeric",
                month: "long",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
                hour12: true
            });
    }

    // Setup filters
    setupFilters();

    if (typeof CivicWatchHome !== "undefined") {
        CivicWatchHome.fetchWeeklyCounts().then((weeklyCounts) => {
            CivicWatchHome.renderStateSnapshots(allData, weeklyCounts);
        });
        CivicWatchHome.setSelectedState(selectedState);
        if (veteransImpactFilter) CivicWatchHome.setVeteransImpactFilter(veteransImpactFilter);
    }
    updateFilterPills();
    
    // Load and display data
    const years = Object.keys(allData.years || {});
    const yearTabs = document.getElementById("year-tabs");
    yearTabs.innerHTML = "";

    if (years.length === 0) {
        setContentBusy(false);
        document.getElementById("content").innerHTML = 
            "<p class='text-slate-500 italic text-center py-8'>No data available. Run the backfill script to populate history.</p>";
        return;
    }

    // Get current year
    const currentYearNum = new Date().getFullYear();
    const currentYearStr = currentYearNum.toString();

    // Sort years: current year first, then descending order (newest first)
    const sortedYears = [...years].sort((a, b) => {
        const aNum = parseInt(a);
        const bNum = parseInt(b);
        
        // Current year always comes first
        if (a === currentYearStr) return -1;
        if (b === currentYearStr) return 1;
        
        // Otherwise, sort descending (newest first)
        return bNum - aNum;
    });

    // Create year tabs
    let defaultYearSet = false;
    sortedYears.forEach((year) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = year;
        btn.className = "year-tab px-5 py-2.5 bg-slate-100 hover:bg-slate-200 border-2 border-transparent rounded-lg font-medium transition-all text-slate-700";
        btn.setAttribute("data-year", year);
        btn.setAttribute("role", "tab");
        btn.setAttribute("aria-selected", "false");
        btn.onclick = () => {
            searchMode = false;
            searchQuery = "";
            document.getElementById("search-input").value = "";
            currentYear = year;
            currentPage = 0;
            currentItemPage = 0;
            displayUnifiedView(year, 0);
        };
        yearTabs.appendChild(btn);

        // Show current year by default (or first year if current year not available)
        if (!defaultYearSet) {
            if (year === currentYearStr || sortedYears.indexOf(year) === 0) {
                currentYear = year;
                btn.click();
                defaultYearSet = true;
            }
        }
    });
}

function setupFilters() {
    // Collect all unique sources and categories from data
    const sources = new Set();
    const categories = new Set();
    
    // Get sources from RSS feeds (years data)
    const years = allData.years || {};
    Object.values(years).forEach(yearData => {
        const grouped = yearData.grouped || {};
        Object.values(grouped).forEach(dateData => {
            Object.keys(dateData).forEach(source => {
                sources.add(source);
                // Extract category from source if it's Kansas
                if (source.includes("Kansas Legislature")) {
                    const parts = source.split(" - ");
                    if (parts.length > 1) {
                        categories.add(parts[1]);
                    }
                }
            });
        });
    });
    
    // Get sources from legislation
    const legislation = allData.legislation || {};
    if (legislation.pages) {
        legislation.pages.forEach(page => {
            page.forEach(bill => {
                sources.add(bill.source || "Congress.gov API");
            });
        });
    } else if (Array.isArray(legislation)) {
        legislation.forEach(bill => {
            sources.add(bill.source || "Congress.gov API");
        });
    }
    
    // Populate state filter from site config
    const stateFilter = document.getElementById("state-filter");
    if (stateFilter) {
        const states = allData.states || [];
        states.forEach(s => {
            const option = document.createElement("option");
            option.value = s.code.toUpperCase();
            option.textContent = s.name;
            stateFilter.appendChild(option);
        });
        stateFilter.addEventListener("change", () => {
            selectedState = stateFilter.value;
            if (typeof CivicWatchHome !== "undefined") CivicWatchHome.setSelectedState(selectedState);
            currentPage = 0;
            currentItemPage = 0;
            refreshView();
            a11yAnnounce("State filter applied.");
        });
    }

    // Populate source filter
    const sourceFilter = document.getElementById("source-filter");
    const categoryFilter = document.getElementById("category-filter");
    
    // Sort sources
    const sortedSources = Array.from(sources).sort();
    sortedSources.forEach(source => {
        const option = document.createElement("option");
        option.value = source;
        option.textContent = source;
        sourceFilter.appendChild(option);
    });
    
    // Populate category filter
    const sortedCategories = Array.from(categories).sort();
    sortedCategories.forEach(cat => {
        const option = document.createElement("option");
        option.value = cat;
        option.textContent = cat;
        categoryFilter.appendChild(option);
    });
    
    // Add event listeners
    sourceFilter.addEventListener("change", () => {
        selectedSource = sourceFilter.value;
        currentPage = 0;
        currentItemPage = 0;
        refreshView();
        a11yAnnounce("Source filter applied.");
    });
    
    categoryFilter.addEventListener("change", () => {
        selectedCategory = categoryFilter.value;
        currentPage = 0;
        currentItemPage = 0;
        refreshView();
        a11yAnnounce("Category filter applied.");
    });
    
    const clearBtn = document.getElementById("clear-filters");
    if (clearBtn) {
        clearBtn.onclick = () => {
            sourceFilter.value = "";
            categoryFilter.value = "";
            selectedSource = "";
            selectedCategory = "";
            currentPage = 0;
            currentItemPage = 0;
            refreshView();
        };
    }
}

function getFeedItemLimit() {
    return veteransImpactFilter ? VETERANS_FEED_ITEM_LIMIT : null;
}

function paginateFeedItems(items) {
    const limit = getFeedItemLimit();
    if (!limit || items.length <= limit) {
        return { items, totalItems: items.length, totalItemPages: 1, startIndex: 0 };
    }
    const totalItemPages = Math.ceil(items.length / limit);
    const effectiveItemPage = Math.min(currentItemPage, totalItemPages - 1);
    if (effectiveItemPage !== currentItemPage) currentItemPage = effectiveItemPage;
    const startIndex = effectiveItemPage * limit;
    return {
        items: items.slice(startIndex, startIndex + limit),
        totalItems: items.length,
        totalItemPages,
        startIndex,
    };
}

function getDateRangeForChunk(chunkIndex) {
    /**
     * Calculate the date range for a 14-day chunk.
     * chunkIndex 0 = most recent 2 weeks
     * chunkIndex 1 = previous 2 weeks
     * etc.
     */
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    
    // Calculate end date (most recent day in this chunk)
    const endDate = new Date(now);
    endDate.setDate(endDate.getDate() - (chunkIndex * DAYS_PER_CHUNK));
    
    // Calculate start date (oldest day in this chunk)
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - (DAYS_PER_CHUNK - 1));
    
    return {
        start: startDate.toISOString().split('T')[0],
        end: endDate.toISOString().split('T')[0]
    };
}

function isDateInRange(dateStr, startDate, endDate) {
    /**
     * Check if a date string falls within the given range (inclusive).
     */
    if (!dateStr) return false;
    try {
        const date = new Date(dateStr + "T00:00:00");
        const start = new Date(startDate + "T00:00:00");
        const end = new Date(endDate + "T00:00:00");
        return date >= start && date <= end;
    } catch {
        return false;
    }
}

function collectGroupedItems(yearData) {
    const grouped = yearData.grouped || {};
    let allItems = [];
    Object.keys(grouped).forEach(date => {
        const dateData = grouped[date];
        Object.keys(dateData).forEach(source => {
            const items = dateData[source];
            allItems = allItems.concat(items.map(item => ({
                ...item,
                date: date,
                source: source,
                item_type: item.item_type,
                action_type: item.action_type,
                vote_tally: item.vote_tally,
                motion: item.motion,
            })));
        });
    });
    return allItems;
}

function applyFeedFilters(allItems) {
    let filtered = allItems;
    if (selectedSource) {
        filtered = filtered.filter(item => item.source === selectedSource || isVoteFeedItem(item));
    }
    if (selectedCategory) {
        filtered = filtered.filter(item => {
            if (isVoteFeedItem(item)) return true;
            const source = item.source || "";
            return source.includes(selectedCategory);
        });
    }
    if (selectedState) {
        filtered = filtered.filter(item => itemMatchesStateFilter(item));
    }
    if (veteransImpactFilter) {
        filtered = filtered.filter(item => itemMatchesVeteransFilter(item));
    }
    return filtered;
}

function enrichMultiStateBill(bill, date) {
    const impactLookup = (allData?.veteran_impact || {}).lookup || {};
    const latestAction = bill.latest_action || "";
    const enriched = {
        title: `${bill.bill_number}: ${bill.title}`,
        link: (typeof CivicWatchBillUtils !== "undefined" ? CivicWatchBillUtils.resolveBillUrl(bill) : bill.url),
        summary: bill.summary || latestAction || "",
        source: `State (${STATE_NAMES[bill.state] || bill.state})`,
        state: bill.state,
        level: "state",
        published: bill.latest_action_date,
        latest_action: latestAction,
        bill_number: bill.bill_number,
        date: date,
        classification: bill.classification,
        ai_topics: bill.ai_topics,
        item_type: bill.item_type || "bill_update",
        action_type: bill.action_type || classifyActionType(latestAction),
        vote_tally: bill.vote_tally,
        motion: bill.motion,
    };
    if (typeof CivicWatchHome !== "undefined" && CivicWatchHome.resolveVeteranImpact) {
        enriched.veteran_impact = CivicWatchHome.resolveVeteranImpact(enriched);
    } else if (impactLookup) {
        const key = `${String(bill.state || "").toUpperCase()}|${bill.bill_number}`;
        enriched.veteran_impact = impactLookup[key] || null;
    }
    return enriched;
}

function appendMultiStateBillsForRange(allItems, dateRange) {
    const multiStateBills = (allData.search_index || {}).bills || [];

    if (selectedState && selectedState !== "Federal" && selectedState !== "KS") {
        multiStateBills.forEach(bill => {
            if ((bill.state || "").toUpperCase() !== selectedState) return;
            const date = bill.latest_action_date ? bill.latest_action_date.split("T")[0] : "";
            if (!isDateInRange(date, dateRange.start, dateRange.end)) return;
            const enriched = enrichMultiStateBill(bill, date);
            if (!itemMatchesVeteransFilter(enriched)) return;
            allItems.push(enriched);
        });
    } else if (!selectedState) {
        multiStateBills.forEach(bill => {
            if (!bill.state || bill.state === "KS") return;
            if (bill.level === "federal") return;
            const date = bill.latest_action_date ? bill.latest_action_date.split("T")[0] : "";
            if (!isDateInRange(date, dateRange.start, dateRange.end)) return;
            const enriched = enrichMultiStateBill(bill, date);
            if (!itemMatchesVeteransFilter(enriched)) return;
            allItems.push(enriched);
        });
    }

    return allItems;
}

function getFeedItemsForDateRange(yearData, dateRange) {
    let allItems = collectGroupedItems(yearData);
    allItems = allItems.filter(item => {
        const itemDate = item.date || (item.published ? item.published.split("T")[0] : "");
        return isDateInRange(itemDate, dateRange.start, dateRange.end);
    });
    allItems = applyFeedFilters(allItems);
    allItems = appendMultiStateBillsForRange(allItems, dateRange);
    allItems.sort((a, b) => (b.published || b.date || "").localeCompare(a.published || a.date || ""));
    return allItems;
}

function getTotalChunksForYear(allDatesInYear) {
    const oldestDate = allDatesInYear.length > 0 ? allDatesInYear[allDatesInYear.length - 1] : null;
    if (!oldestDate) return 1;
    const oldest = new Date(oldestDate + "T00:00:00");
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    const daysDiff = Math.ceil((now - oldest) / (1000 * 60 * 60 * 24));
    return Math.max(1, Math.ceil(daysDiff / DAYS_PER_CHUNK));
}

function findFirstNonEmptyChunkIndex(year, totalChunks) {
    const yearData = allData.years[year];
    if (!yearData) return 0;
    for (let i = 0; i < totalChunks; i++) {
        const range = getDateRangeForChunk(i);
        if (getFeedItemsForDateRange(yearData, range).length > 0) {
            return i;
        }
    }
    return 0;
}

function recentWeekHasNoActivity(year) {
    const yearData = allData.years[year];
    if (!yearData) return false;
    return getFeedItemsForDateRange(yearData, getDateRangeForChunk(0)).length === 0;
}

function feedFallbackNotice(dateRange) {
    const rangeLabel = `${formatDate(dateRange.start)} – ${formatDate(dateRange.end)}`;
    return `No activity in the last 2 weeks — showing ${rangeLabel}`;
}

function displayUnifiedView(year, chunkIndex) {
    const yearData = allData.years[year];
    if (!yearData) return;

    setContentBusy(true);
    const container = document.getElementById("content");
    container.innerHTML = "";

    // Update active year tab
    document.querySelectorAll(".year-tab").forEach(btn => {
        if (btn.getAttribute("data-year") === year) {
            btn.classList.remove("bg-slate-100", "text-slate-700", "border-transparent");
            btn.classList.add("bg-civic-blue", "text-white", "border-civic-blue");
        } else {
            btn.classList.remove("bg-civic-blue", "text-white", "border-civic-blue");
            btn.classList.add("bg-slate-100", "text-slate-700", "border-transparent");
        }
    });

    // Get date range for this chunk
    const grouped = yearData.grouped || {};
    const allDatesInYear = Object.keys(grouped).sort().reverse();
    const totalChunks = getTotalChunksForYear(allDatesInYear);

    let effectiveChunkIndex = chunkIndex;
    let dateRange = getDateRangeForChunk(effectiveChunkIndex);
    let allItems = getFeedItemsForDateRange(yearData, dateRange);

    // When the current period is empty, fall back to the most recent 2-week window with data
    if (chunkIndex === 0 && allItems.length === 0) {
        const fallbackChunk = findFirstNonEmptyChunkIndex(year, totalChunks);
        if (fallbackChunk > 0) {
            effectiveChunkIndex = fallbackChunk;
            currentPage = fallbackChunk;
            currentItemPage = 0;
            dateRange = getDateRangeForChunk(effectiveChunkIndex);
            allItems = getFeedItemsForDateRange(yearData, dateRange);
        }
    }

    const pagination = paginateFeedItems(allItems);
    const pageItems = pagination.items;

    // Group by date (flat list per day)
    const itemsByDate = {};
    pageItems.forEach(item => {
        const date = item.date || (item.published ? item.published.split("T")[0] : "");
        if (!date) return;
        if (!itemsByDate[date]) itemsByDate[date] = [];
        itemsByDate[date].push(item);
    });

    const chunkDates = Object.keys(itemsByDate).sort().reverse();

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const showFallbackNote = recentWeekHasNoActivity(year) && pageItems.length > 0;
    if (showFallbackNote) {
        const notice = document.createElement("p");
        notice.className = "text-sm text-slate-500 text-center mb-4 italic";
        notice.setAttribute("role", "status");
        notice.textContent = feedFallbackNotice(dateRange);
        container.appendChild(notice);
    }

    if (pagination.totalItemPages > 1) {
        const startNum = pagination.startIndex + 1;
        const endNum = pagination.startIndex + pageItems.length;
        const itemNotice = document.createElement("p");
        itemNotice.className = "text-sm text-slate-500 text-center mb-4";
        itemNotice.setAttribute("role", "status");
        itemNotice.textContent = `Showing ${startNum}–${endNum} of ${pagination.totalItems} results`;
        container.appendChild(itemNotice);
    }

    let renderedDays = 0;
    chunkDates.forEach(date => {
        const dayItems = itemsByDate[date];
        if (!dayItems || dayItems.length === 0) return;

        const daySection = typeof CivicWatchHome !== "undefined"
            ? CivicWatchHome.renderFeedDay(date, dayItems, {
                searchQuery: "",
                veteransImpactFilter,
            })
            : null;

        if (daySection) {
            container.appendChild(daySection);
            renderedDays++;
        }
    });

    if (renderedDays === 0) {
        container.innerHTML = `<p class='text-slate-500 italic text-center py-8'>${feedEmptyMessage(dateRange)}</p>`;
    }

    setContentBusy(false);
    updateFilterPills();

    renderPagination(year, effectiveChunkIndex, totalChunks, dateRange, pagination);
}

function searchResultKey(item) {
    const bill = (item.bill_number || "").trim().toLowerCase();
    const date = (item.date || item.published || "").split("T")[0];
    const title = (item.title || item.short_title || "").trim().toLowerCase().slice(0, 80);
    const motion = (item.motion || "").trim().toLowerCase();
    return `${bill}|${date}|${title}|${motion}`;
}

function addSearchResult(item, seen, results) {
    const key = searchResultKey(item);
    if (seen.has(key)) return false;
    seen.add(key);
    results.push(item);
    return results.length >= SEARCH_MAX_RESULTS;
}

function performSearch(query) {
    if (!query || query.trim().length === 0) {
        searchMode = false;
        searchQuery = "";
        if (currentYear) {
            displayUnifiedView(currentYear, 0);
        }
        return;
    }

    const trimmed = query.trim();
    if (trimmed.length < SEARCH_MIN_CHARS) {
        searchMode = true;
        searchQuery = trimmed.toLowerCase();
        searchResults = [];
        displaySearchPrompt(`Type at least ${SEARCH_MIN_CHARS} characters to search.`);
        updateFilterPills();
        return;
    }

    setContentBusy(true);
    searchMode = true;
    searchQuery = trimmed.toLowerCase();
    searchResults = [];
    const seen = new Set();
    let capped = false;

    const tryAdd = (item) => {
        if (addSearchResult(item, seen, searchResults)) capped = true;
        return capped;
    };

    // Search through all items in all years
    const years = Object.keys(allData.years || {});
    
    outer: for (const year of years) {
        const yearData = allData.years[year];
        const grouped = yearData.grouped || {};
        
        for (const date of Object.keys(grouped)) {
            const dateData = grouped[date];
            for (const source of Object.keys(dateData)) {
                const items = dateData[source];
                for (const item of items) {
                    if (buildFeedSearchText(item).includes(searchQuery)) {
                        if (tryAdd({
                            ...item,
                            date: date,
                            source: source,
                            item_type: item.item_type,
                            action_type: item.action_type,
                            vote_tally: item.vote_tally,
                            motion: item.motion,
                        })) break outer;
                    }
                }
            }
        }
    }

    if (!capped) {
        // Also search legislation
        const legislation = allData.legislation || {};
        let legislationItems = [];
        if (legislation.pages) {
            legislation.pages.forEach(page => {
                legislationItems = legislationItems.concat(page);
            });
        } else if (Array.isArray(legislation)) {
            legislationItems = legislation;
        }
        
        legLoop: for (const bill of legislationItems) {
            const searchText = buildFeedSearchText({
                title: bill.title,
                short_title: bill.short_title,
                summary: bill.summary,
                bill_number: `${bill.bill_type || ""} ${bill.bill_number || ""}`.trim(),
                latest_action: bill.latest_action,
                motion: bill.motion,
                vote_tally: bill.vote_tally,
            });

            if (searchText.includes(searchQuery)) {
                const billNumber = `${bill.bill_type || ""} ${bill.bill_number || ""}`.trim();
                if (tryAdd({
                    ...bill,
                    date: bill.latest_action_date ? bill.latest_action_date.split("T")[0] : bill.published ? bill.published.split("T")[0] : "",
                    source: bill.source || "Congress.gov API",
                    bill_number: billNumber,
                    item_type: bill.item_type || "bill_update",
                    action_type: bill.action_type || classifyActionType(bill.latest_action),
                    vote_tally: bill.vote_tally,
                    motion: bill.motion,
                })) break legLoop;
            }
        }
    }

    if (!capped) {
        // Also search multi-state index
        const indexBills = (allData.search_index || {}).bills || [];
        indexLoop: for (const bill of indexBills) {
            const searchText = buildFeedSearchText({
                title: bill.title,
                summary: bill.summary,
                bill_number: bill.bill_number,
                latest_action: bill.latest_action,
                motion: bill.motion,
                vote_tally: bill.vote_tally,
            });
            if (searchText.includes(searchQuery)) {
                if (tryAdd({
                    title: `${bill.bill_number}: ${bill.title}`,
                    link: (typeof CivicWatchBillUtils !== "undefined" ? CivicWatchBillUtils.resolveBillUrl(bill) : bill.url),
                    summary: bill.summary || bill.latest_action || "",
                    source: bill.level === "federal" ? "Federal (U.S. Congress)" : `State (${STATE_NAMES[bill.state] || bill.state})`,
                    state: bill.state,
                    level: bill.level,
                    published: bill.latest_action_date,
                    date: bill.latest_action_date ? bill.latest_action_date.split("T")[0] : "",
                    bill_number: bill.bill_number,
                    latest_action: bill.latest_action,
                    item_type: bill.item_type || "bill_update",
                    action_type: bill.action_type || classifyActionType(bill.latest_action),
                    vote_tally: bill.vote_tally,
                    motion: bill.motion,
                })) break indexLoop;
            }
        }
    }

    // Apply state filter to search results
    if (selectedState) {
        searchResults = searchResults.filter(item => itemMatchesStateFilter(item));
    }
    if (veteransImpactFilter) {
        searchResults = searchResults.filter(item => itemMatchesVeteransFilter(item));
    }

    // Sort search results by date (newest first)
    searchResults.sort((a, b) => {
        const dateA = a.published || a.date || "";
        const dateB = b.published || b.date || "";
        return dateB.localeCompare(dateA);
    });

    displaySearchResults({ capped });
    updateFilterPills();
}

function displaySearchPrompt(message) {
    const container = document.getElementById("content");
    container.innerHTML = "";
    document.querySelectorAll(".year-tab").forEach(btn => {
        btn.classList.remove("bg-civic-blue", "text-white", "border-civic-blue");
        btn.classList.add("bg-slate-100", "text-slate-700", "border-transparent");
        btn.setAttribute("aria-selected", "false");
    });
    document.getElementById("pagination").innerHTML = "";
    container.innerHTML = `<p class='text-slate-500 italic text-center py-8'>${escapeHtmlText(message)}</p>`;
    setContentBusy(false);
}

function displaySearchResults(options = {}) {
    const { capped = false } = options;
    const container = document.getElementById("content");
    container.innerHTML = "";

    // Clear active year tabs
    document.querySelectorAll(".year-tab").forEach(btn => {
        btn.classList.remove("bg-civic-blue", "text-white", "border-civic-blue");
        btn.classList.add("bg-slate-100", "text-slate-700", "border-transparent");
        btn.setAttribute("aria-selected", "false");
    });

    // Hide pagination
    document.getElementById("pagination").innerHTML = "";

    if (searchResults.length === 0) {
        container.innerHTML = `<p class='text-slate-500 italic text-center py-8'>No results found for "${searchQuery}".</p>`;
        a11yAnnounce(`No search results for ${searchQuery}.`);
        setContentBusy(false);
        return;
    }

    a11yAnnounce(`${searchResults.length} search result${searchResults.length === 1 ? "" : "s"} found.`);

    const resultsHeader = document.createElement("div");
    resultsHeader.className = "mb-6 p-5 bg-blue-50 rounded-xl border-l-4 border-civic-blue";
    resultsHeader.innerHTML = `
        <h2 class="text-xl font-bold text-civic-blue mb-1">Search Results (${searchResults.length} found${capped ? "+" : ""})</h2>
        <p class="text-slate-600">Searching for: "<strong>${escapeHtmlText(searchQuery)}</strong>"</p>
        ${capped ? `<p class="text-sm text-slate-500 mt-2">Showing the first ${SEARCH_MAX_RESULTS} matches. Add more characters to narrow results.</p>` : ""}
    `;
    container.appendChild(resultsHeader);

    // Group results by date (flat list)
    const itemsByDate = {};
    searchResults.forEach(item => {
        const date = item.date || "Unknown";
        if (!itemsByDate[date]) itemsByDate[date] = [];
        itemsByDate[date].push(item);
    });

    const dates = Object.keys(itemsByDate).sort().reverse();
    dates.forEach(date => {
        const daySection = typeof CivicWatchHome !== "undefined"
            ? CivicWatchHome.renderFeedDay(date, itemsByDate[date], {
                searchQuery: searchQuery,
                veteransImpactFilter,
            })
            : null;
        if (daySection) container.appendChild(daySection);
    });

    setContentBusy(false);
    updateFilterPills();
}

function formatDate(dateStr) {
    try {
        const date = new Date(dateStr + "T00:00:00");
        return date.toLocaleDateString("en-US", {
            year: "numeric",
            month: "long",
            day: "numeric",
            timeZone: "America/Chicago"
        });
    } catch {
        return dateStr;
    }
}

function renderPagination(year, current, total, dateRange, itemPagination) {
    const container = document.getElementById("pagination");
    container.innerHTML = "";

    const itemPages = itemPagination?.totalItemPages || 1;
    const showPeriodNav = total > 1;
    const showItemNav = itemPages > 1;
    if (!showPeriodNav && !showItemNav) return;

    // Format date range for display
    const startFormatted = formatDate(dateRange.start);
    const endFormatted = formatDate(dateRange.end);

    if (showPeriodNav) {
        const paginationInfo = document.createElement("div");
        paginationInfo.className = "text-center text-slate-600 mb-4 text-sm";
        paginationInfo.textContent = `Showing ${startFormatted} - ${endFormatted} (${current + 1} of ${total} periods)`;
        container.appendChild(paginationInfo);
    }

    const btnContainer = document.createElement("div");
    btnContainer.className = "flex justify-center flex-wrap gap-2";

    if (showItemNav) {
        if (currentItemPage > 0) {
            const prevItemsBtn = document.createElement("button");
            prevItemsBtn.textContent = "Previous results";
            prevItemsBtn.className = "px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded-lg text-sm font-medium transition-colors";
            prevItemsBtn.setAttribute("aria-label", "Show previous page of results");
            prevItemsBtn.onclick = () => {
                currentItemPage -= 1;
                displayUnifiedView(year, current);
                window.scrollTo({ top: 0, behavior: "smooth" });
            };
            btnContainer.appendChild(prevItemsBtn);
        }

        const itemPageInfo = document.createElement("span");
        itemPageInfo.className = "px-3 py-2 text-sm text-slate-600 self-center";
        itemPageInfo.textContent = `Results page ${currentItemPage + 1} of ${itemPages}`;
        btnContainer.appendChild(itemPageInfo);

        if (currentItemPage < itemPages - 1) {
            const nextItemsBtn = document.createElement("button");
            nextItemsBtn.textContent = "Next results";
            nextItemsBtn.className = "px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded-lg text-sm font-medium transition-colors";
            nextItemsBtn.setAttribute("aria-label", "Show next page of results");
            nextItemsBtn.onclick = () => {
                currentItemPage += 1;
                displayUnifiedView(year, current);
                window.scrollTo({ top: 0, behavior: "smooth" });
            };
            btnContainer.appendChild(nextItemsBtn);
        }
    }

    // Previous 2 weeks button
    if (showPeriodNav && current > 0) {
        const prevBtn = document.createElement("button");
        prevBtn.innerHTML = `
            <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
            </svg>
            Previous 2 Weeks
        `;
        prevBtn.className = "px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded-lg text-sm font-medium transition-colors";
        prevBtn.setAttribute("aria-label", "Show previous 2 weeks");
        prevBtn.onclick = () => {
            currentPage = current - 1;
            currentItemPage = 0;
            displayUnifiedView(year, current - 1);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        };
        btnContainer.appendChild(prevBtn);
    }

    // Next 2 weeks button
    if (showPeriodNav && current < total - 1) {
        const nextBtn = document.createElement("button");
        nextBtn.innerHTML = `
            Next 2 Weeks
            <svg class="w-4 h-4 inline ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
        `;
        nextBtn.className = "px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded-lg text-sm font-medium transition-colors";
        nextBtn.setAttribute("aria-label", "Show next 2 weeks");
        nextBtn.onclick = () => {
            currentPage = current + 1;
            currentItemPage = 0;
            displayUnifiedView(year, current + 1);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        };
        btnContainer.appendChild(nextBtn);
    }

    container.appendChild(btnContainer);
}

// Search input handler
function setupSearch() {
    const searchInput = document.getElementById("search-input");
    const searchButton = document.getElementById("search-button");
    const clearButton = document.getElementById("clear-search");

    function handleSearch() {
        const query = searchInput.value.trim();
        performSearch(query);
    }

    searchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            handleSearch();
        }
    });

    let searchDebounce = null;
    searchInput.addEventListener("input", () => {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(handleSearch, 400);
    });

    if (searchButton) {
        searchButton.addEventListener("click", handleSearch);
    }

    if (clearButton) {
        clearButton.addEventListener("click", () => {
            searchInput.value = "";
            selectedState = "";
            selectedSource = "";
            selectedCategory = "";
            veteransImpactFilter = null;
            const sourceFilter = document.getElementById("source-filter");
            const categoryFilter = document.getElementById("category-filter");
            const stateFilter = document.getElementById("state-filter");
            if (sourceFilter) sourceFilter.value = "";
            if (categoryFilter) categoryFilter.value = "";
            if (stateFilter) stateFilter.value = "";
            if (typeof CivicWatchHome !== "undefined") {
                CivicWatchHome.setSelectedState("");
                CivicWatchHome.setVeteransImpactFilter(null);
            }
            searchMode = false;
            searchQuery = "";
            currentPage = 0;
            currentItemPage = 0;
            if (currentYear) displayUnifiedView(currentYear, 0);
            updateFilterPills();
        });
    }
}

function escapeHtmlText(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function extractRecapBillKey(line) {
    const m = String(line).trim().match(/^((?:HR|H\.R\.|H\.?\s*R\.?|S\.|SR|S\.R\.|SB|HB|HF|SF|LD|SP)\s*)(\d+)/i);
    if (!m) return null;
    const type = m[1].replace(/\./g, "").replace(/\s+/g, "").toUpperCase();
    return `${type} ${m[2]}`;
}

function recapLineBillUrl(line, sectionId) {
    const trimmed = String(line).trim();
    const m = trimmed.match(/^(HR|H\.R\.|S\.|SR|S\.R\.|H\.?\s*RES\.?|S\.?\s*RES\.?)\s*(\d+)\s*:/i);
    if (!m || sectionId !== "federal") return null;
    const rawType = m[1].replace(/\./g, "").replace(/\s+/g, "").toUpperCase();
    const num = m[2];
    const congress = "119th-congress";
    if (rawType === "HR" || rawType.startsWith("HRES")) {
        return `https://www.congress.gov/bill/${congress}/house-bill/${num}`;
    }
    if (rawType === "S" || rawType === "SB") {
        return `https://www.congress.gov/bill/${congress}/senate-bill/${num}`;
    }
    if (rawType === "SR" || rawType === "SRES") {
        return `https://www.congress.gov/bill/${congress}/senate-resolution/${num}`;
    }
    return null;
}

function buildVeteransBillKeys(veteransHighlight) {
    const keys = new Set();
    if (!veteransHighlight?.items) return keys;
    veteransHighlight.items.forEach((item) => {
        const key = extractRecapBillKey(item.title || "");
        if (key) keys.add(key);
    });
    return keys;
}

function renderWeeklyRecapLines(recapLines, section) {
    const veteransBillKeys = buildVeteransBillKeys(section.veterans_highlight);
    let skipIndented = false;
    let html = "";

    recapLines.forEach((line) => {
        const trimmed = line.trim();
        if (trimmed === "") return;

        if (line.startsWith("   ")) {
            if (skipIndented) return;
            html += `<p class="my-1 ml-4 text-slate-600">${escapeHtmlText(trimmed)}</p>`;
            return;
        }

        skipIndented = false;
        const billKey = extractRecapBillKey(trimmed);
        if (billKey && veteransBillKeys.has(billKey)) {
            skipIndented = true;
            return;
        }

        if (trimmed.endsWith(":") && !billKey) {
            html += `<p class="my-1 font-medium text-slate-800">${escapeHtmlText(line)}</p>`;
            return;
        }

        const url = recapLineBillUrl(trimmed, section.id);
        if (url) {
            html += `<p class="my-1"><a href="${url}" class="text-civic-blue hover:underline font-medium" target="_blank" rel="noopener">${escapeHtmlText(trimmed)}</a></p>`;
            return;
        }

        html += `<p class="my-1">${escapeHtmlText(line)}</p>`;
    });

    return html;
}

async function loadWeeklyOverview() {
    const container = document.getElementById("weekly-overview-content");
    const section = document.getElementById("weekly-overview-section");
    if (!container || !section) return;
    
    // Set up toggle functionality (collapsed by default; localStorage remembers preference)
    const header = document.getElementById("weekly-overview-header");
    if (header) {
        const saved = localStorage.getItem("civicwatch-weekly-expanded");
        const expanded = saved === "true";
        section.classList.toggle("collapsed", !expanded);
        section.classList.toggle("expanded", expanded);
        header.setAttribute("aria-expanded", expanded ? "true" : "false");
        
        header.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const expanding = section.classList.contains("collapsed");
            if (expanding) {
                section.classList.remove("collapsed");
                section.classList.add("expanded");
                header.setAttribute("aria-expanded", "true");
                localStorage.setItem("civicwatch-weekly-expanded", "true");
                a11yAnnounce("Weekly overview expanded.");
            } else {
                section.classList.remove("expanded");
                section.classList.add("collapsed");
                header.setAttribute("aria-expanded", "false");
                localStorage.setItem("civicwatch-weekly-expanded", "false");
                a11yAnnounce("Weekly overview collapsed.");
            }
        };
    }
    
    try {
        const res = await civicwatchFetch("weekly/latest.json");
        const data = await res.json();
        
        // Format week range
        const weekStart = new Date(data.week_start);
        const weekEnd = new Date(data.week_end);
        const weekRange = weekStart.toLocaleDateString("en-US", {
            month: "long",
            day: "numeric"
        }) + " - " + weekEnd.toLocaleDateString("en-US", {
            month: "long",
            day: "numeric",
            year: "numeric"
        });
        
        let html = `<div class="mb-4 text-slate-500 text-sm">Week of ${weekRange}</div>`;
        
        // Audio player if available
        if (data.audio_available && data.audio_file) {
            html += `
                <div class="mb-5">
                    <audio controls class="w-full max-w-lg">
                        <source src="${data.audio_file}" type="audio/mpeg">
                        Your browser does not support the audio element.
                    </audio>
                </div>
            `;
        }

        if (Array.isArray(data.sections) && data.sections.length > 0) {
            html += `<div class="space-y-6">`;
            data.sections.forEach(section => {
                html += `<div class="border border-slate-200 rounded-lg bg-white p-4">`;
                html += `<div class="flex items-center justify-between gap-3 mb-3">`;
                html += `<h3 class="font-semibold text-civic-navy text-lg">${section.label}</h3>`;
                if (section.item_count > 0) {
                    html += `<span class="text-xs font-medium px-2 py-1 bg-slate-100 text-slate-600 rounded-full">${section.item_count} items</span>`;
                }
                html += `</div>`;

                if (section.veterans_highlight) {
                    const highlight = section.veterans_highlight;
                    html += `<div class="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">`;
                    html += `<div class="flex items-center gap-2 mb-2">`;
                    html += `<span class="inline-block px-2 py-0.5 bg-amber-100 text-amber-900 text-xs font-semibold rounded uppercase tracking-wide">Veterans & Military</span>`;
                    if (highlight.total_matches > 1) {
                        html += `<span class="text-xs text-amber-700">${highlight.total_matches} matches</span>`;
                    }
                    html += `</div>`;
                    html += `<p class="text-sm text-amber-900 mb-2">Notable veterans & military activity this week:</p>`;
                    if (Array.isArray(highlight.items) && highlight.items.length > 0) {
                        html += `<ul class="space-y-1 text-sm">`;
                        highlight.items.forEach(item => {
                            const label = item.title || "Item";
                            if (item.url) {
                                html += `<li><a href="${item.url}" class="text-civic-blue hover:underline font-medium" target="_blank" rel="noopener">${escapeHtmlText(label)}</a></li>`;
                            } else {
                                html += `<li>${escapeHtmlText(label)}</li>`;
                            }
                        });
                        if (highlight.total_matches > highlight.items.length) {
                            html += `<li class="text-xs text-amber-700">Plus ${highlight.total_matches - highlight.items.length} more</li>`;
                        }
                        html += `</ul>`;
                    }
                    html += `</div>`;
                }

                html += `<div class="leading-relaxed text-slate-700 text-sm">`;
                const recapLines = section.recap_lines || [];
                html += renderWeeklyRecapLines(recapLines, section);
                html += `</div>`;
                html += `</div>`;
            });
            html += `</div>`;
        } else {
            // Fallback for older weekly overview format
            html += `<div class="leading-relaxed text-slate-700">`;
            const script = data.script || "";
            const scriptHtml = script.split("\n").map(line => {
                if (line.trim() === "") {
                    return "<br>";
                }
                return `<p class="my-2">${line}</p>`;
            }).join("");
            html += scriptHtml;
            html += `</div>`;
        }
        
        // Item counts
        const counts = data.item_counts || {};
        const countEntries = Object.entries(counts).filter(([, value]) => value > 0);
        if (countEntries.length > 0) {
            html += `<div class="mt-5 pt-4 border-t border-slate-200 text-sm text-slate-500">`;
            html += `This week: ${countEntries.map(([key, value]) => `${value} ${key}`).join(", ")}`;
            html += `</div>`;
        }
        
        // Update container content
        container.innerHTML = html;
        container.setAttribute("aria-busy", "false");
    } catch (error) {
        // If weekly overview doesn't exist, hide the section
        if (section) {
            section.style.display = "none";
        }
    }
}

window.onload = () => {
    if (typeof CivicWatchHome !== "undefined") {
        CivicWatchHome.init({
            onStateFilter: (state) => {
                selectedState = state;
                currentPage = 0;
                currentItemPage = 0;
                refreshView();
                a11yAnnounce("State filter applied.");
            },
            onVeteransImpactFilter: (level) => {
                veteransImpactFilter = level;
                currentPage = 0;
                currentItemPage = 0;
                refreshView();
                const announcements = {
                    all: "Military and veterans filter applied.",
                    red: "Red high-impact veterans filter applied.",
                    yellow: "Yellow moderate-impact veterans filter applied.",
                    green: "Green ceremonial veterans filter applied.",
                };
                a11yAnnounce(level ? (announcements[level] || "Veterans filter applied.") : "Military and veterans filter cleared.");
            },
            onClearFilter: (key) => {
                if (key === "state") {
                    selectedState = "";
                    if (typeof CivicWatchHome !== "undefined") CivicWatchHome.setSelectedState("");
                    const stateFilter = document.getElementById("state-filter");
                    if (stateFilter) stateFilter.value = "";
                } else if (key === "veterans") {
                    veteransImpactFilter = null;
                    if (typeof CivicWatchHome !== "undefined") CivicWatchHome.setVeteransImpactFilter(null);
                } else if (key === "source") {
                    selectedSource = "";
                    const sourceFilter = document.getElementById("source-filter");
                    if (sourceFilter) sourceFilter.value = "";
                } else if (key === "category") {
                    selectedCategory = "";
                    const categoryFilter = document.getElementById("category-filter");
                    if (categoryFilter) categoryFilter.value = "";
                } else if (key === "search") {
                    const searchInput = document.getElementById("search-input");
                    if (searchInput) searchInput.value = "";
                    searchMode = false;
                    searchQuery = "";
                }
                currentPage = 0;
                currentItemPage = 0;
                refreshView();
            },
        });
    }

    const feedControls = document.getElementById("feed-controls");
    if (feedControls) {
        window.addEventListener("scroll", () => {
            feedControls.classList.toggle("is-sticky", window.scrollY > 400);
        }, { passive: true });
    }

    loadData();
    setupSearch();
};
