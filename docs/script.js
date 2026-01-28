let currentYear = null;
let currentPage = 0;  // Now represents 7-day chunk index (0 = most recent 7 days)
let allData = null;
let searchQuery = "";
let searchMode = false;
let searchResults = [];
let selectedSource = "";
let selectedCategory = "";
const DAYS_PER_CHUNK = 7;  // Show 7 days per "page"

async function loadData() {
    try {
        const res = await fetch("site_data.json");
        allData = await res.json();
    } catch (error) {
        document.getElementById("content").innerHTML = 
            "<div class='bg-red-50 border-l-4 border-red-500 p-4 rounded-r-lg text-red-700'>Error loading data. Please try again later.</div>";
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
    
    // Load and display data
    const years = Object.keys(allData.years || {});
    const yearTabs = document.getElementById("year-tabs");
    yearTabs.innerHTML = "";

    if (years.length === 0) {
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
        btn.textContent = year;
        btn.className = "year-tab px-5 py-2.5 bg-slate-100 hover:bg-slate-200 border-2 border-transparent rounded-lg font-medium transition-all text-slate-700";
        btn.setAttribute("data-year", year);
        btn.onclick = () => {
            searchMode = false;
            searchQuery = "";
            document.getElementById("search-input").value = "";
            currentYear = year;
            currentPage = 0;
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
        if (currentYear) {
            displayUnifiedView(currentYear, 0);
        }
    });
    
    categoryFilter.addEventListener("change", () => {
        selectedCategory = categoryFilter.value;
        currentPage = 0;
        if (currentYear) {
            displayUnifiedView(currentYear, 0);
        }
    });
    
    const clearBtn = document.getElementById("clear-filters");
    if (clearBtn) {
        clearBtn.onclick = () => {
            sourceFilter.value = "";
            categoryFilter.value = "";
            selectedSource = "";
            selectedCategory = "";
            currentPage = 0;
            if (currentYear) {
                displayUnifiedView(currentYear, 0);
            }
        };
    }
}

function getDateRangeForChunk(chunkIndex) {
    /**
     * Calculate the date range for a 7-day chunk.
     * chunkIndex 0 = most recent 7 days
     * chunkIndex 1 = previous 7 days (days 8-14)
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

function displayUnifiedView(year, chunkIndex) {
    const yearData = allData.years[year];
    if (!yearData) return;

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
    const dateRange = getDateRangeForChunk(chunkIndex);
    
    // Get all items from RSS feeds for this year
    // This includes Congress.gov API items which are added to grouped structure by summarize.py
    const grouped = yearData.grouped || {};
    let allItems = [];
    Object.keys(grouped).forEach(date => {
        const dateData = grouped[date];
        Object.keys(dateData).forEach(source => {
            const items = dateData[source];
            allItems = allItems.concat(items.map(item => ({
                ...item,
                date: date,
                source: source
            })));
        });
    });
    
    // Filter items to only those in the current 7-day chunk
    allItems = allItems.filter(item => {
        const itemDate = item.date || (item.published ? item.published.split("T")[0] : "");
        return isDateInRange(itemDate, dateRange.start, dateRange.end);
    });
    
    // Sort by date (newest first)
    allItems.sort((a, b) => {
        const dateA = a.published || a.date || "";
        const dateB = b.published || b.date || "";
        return dateB.localeCompare(dateA);
    });

    // Apply filters
    if (selectedSource) {
        allItems = allItems.filter(item => item.source === selectedSource);
    }
    if (selectedCategory) {
        allItems = allItems.filter(item => {
            const source = item.source || "";
            return source.includes(selectedCategory);
        });
    }

    // Group by date and source
    const groupedByDate = {};
    allItems.forEach(item => {
        const date = item.date || (item.published ? item.published.split("T")[0] : "");
        if (!date) return;
        
        if (!groupedByDate[date]) groupedByDate[date] = {};
        if (!groupedByDate[date][item.source]) groupedByDate[date][item.source] = [];
        groupedByDate[date][item.source].push(item);
    });

    // Get all dates in this chunk (sorted newest first)
    const chunkDates = Object.keys(groupedByDate).sort().reverse();
    
    // Also get all dates from full data structure to show empty states
    const allDatesInYear = Object.keys(grouped).sort().reverse();
    // Filter to only dates in current chunk
    const allDatesInChunk = allDatesInYear.filter(date => 
        isDateInRange(date, dateRange.start, dateRange.end)
    );

    // Get daily summaries
    const dailySummaries = allData.daily_summaries || {};
    
    // Get today's date to check if a day has "ended"
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayStr = today.toISOString().split('T')[0];

    // Render dates in this chunk (newest first)
    // Show all dates in the chunk, even if they have no items (for empty state)
    allDatesInChunk.forEach(date => {
        const dateSection = document.createElement("div");
        dateSection.className = "mb-8 p-6 bg-gradient-to-r from-slate-50 to-white rounded-xl border-l-4 border-civic-blue shadow-sm";

        const dateHeader = document.createElement("h2");
        dateHeader.className = "text-xl font-bold text-civic-navy mb-4";
        dateHeader.textContent = formatDate(date);
        dateSection.appendChild(dateHeader);
        
        // Show daily summary if available and the day has ended (not today)
        const daySummary = dailySummaries[date];
        if (daySummary && daySummary.summary && date < todayStr) {
            const summaryDiv = document.createElement("div");
            summaryDiv.className = "bg-gradient-to-r from-blue-50 to-indigo-50 border-l-4 border-civic-blue p-4 mb-5 rounded-r-lg";
            
            const summaryHeader = document.createElement("div");
            summaryHeader.className = "font-semibold text-civic-blue text-xs uppercase tracking-wider mb-2";
            summaryHeader.textContent = "Daily Summary";
            summaryDiv.appendChild(summaryHeader);
            
            const summaryText = document.createElement("div");
            summaryText.className = "text-slate-700 leading-relaxed";
            summaryText.textContent = daySummary.summary;
            summaryDiv.appendChild(summaryText);
            
            // Show counts if available
            if (daySummary.counts && daySummary.counts.total > 0) {
                const countsDiv = document.createElement("div");
                countsDiv.className = "mt-3 text-sm text-slate-500";
                const counts = daySummary.counts;
                let countParts = [];
                if (counts.kansas_house > 0 || counts.kansas_senate > 0) {
                    const ks = [];
                    if (counts.kansas_house > 0) ks.push(`${counts.kansas_house} House`);
                    if (counts.kansas_senate > 0) ks.push(`${counts.kansas_senate} Senate`);
                    countParts.push(`Kansas: ${ks.join(", ")}`);
                }
                if (counts.congress_house > 0 || counts.congress_senate > 0) {
                    const cg = [];
                    if (counts.congress_house > 0) cg.push(`${counts.congress_house} House`);
                    if (counts.congress_senate > 0) cg.push(`${counts.congress_senate} Senate`);
                    countParts.push(`Congress: ${cg.join(", ")}`);
                }
                if (countParts.length > 0) {
                    countsDiv.textContent = countParts.join(" | ");
                    summaryDiv.appendChild(countsDiv);
                }
            }
            
            dateSection.appendChild(summaryDiv);
        }

        // Get ALL sources for this date from the full grouped structure
        const rssSources = grouped[date] || {};
        const allSources = Object.keys(rssSources).sort();

        // Render ALL sources for this date (even if empty in this chunk)
        allSources.forEach(source => {
            // Apply source filter
            if (selectedSource && source !== selectedSource) {
                return;
            }
            
            // Apply category filter for Kansas items
            if (selectedCategory && !source.includes(selectedCategory)) {
                return;
            }

            const sourceSection = document.createElement("div");
            sourceSection.className = "mb-5 p-4 bg-white rounded-lg border-l-3 border-emerald-500 shadow-sm border";

            const srcHeader = document.createElement("h3");
            srcHeader.className = "text-lg font-semibold text-emerald-600 mb-3 flex items-center gap-2";
            srcHeader.innerHTML = `
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/>
                </svg>
                ${source}
            `;
            sourceSection.appendChild(srcHeader);

            // Get items for this source in this chunk
            const itemsInChunk = groupedByDate[date] && groupedByDate[date][source] 
                ? groupedByDate[date][source] 
                : [];

            // Show items or empty state
            if (itemsInChunk.length === 0) {
                const emptyMsg = document.createElement("p");
                emptyMsg.className = "text-slate-400 italic text-sm py-2";
                emptyMsg.textContent = "No updates for this date/source";
                sourceSection.appendChild(emptyMsg);
            } else {
                const ul = document.createElement("ul");
                ul.className = "space-y-3";
                itemsInChunk.forEach(item => {
                    const li = document.createElement("li");
                    li.className = "pb-3 border-b border-slate-100 last:border-0 last:pb-0";
                    
                    const a = document.createElement("a");
                    a.href = item.link || item.url || "#";
                    // Use short_title for Kansas bills if available, otherwise use title
                    const displayTitle = item.short_title || item.title || "(no title)";
                    a.textContent = displayTitle;
                    a.target = "_blank";
                    a.rel = "noopener noreferrer";
                    a.className = "text-civic-blue hover:text-civic-blue-dark font-medium hover:underline transition-colors";
                    li.appendChild(a);
                    
                    // Show bill number
                    if (item.bill_number) {
                        const billNumDiv = document.createElement("div");
                        billNumDiv.className = "text-sm text-civic-blue font-semibold mt-1";
                        billNumDiv.textContent = `Bill: ${item.bill_number}`;
                        li.appendChild(billNumDiv);
                    }
                    
                    // Show official title for Congress bills if available and different
                    if (item.official_title && item.official_title !== displayTitle) {
                        const officialDiv = document.createElement("div");
                        officialDiv.className = "text-sm text-slate-600 mt-1 italic";
                        officialDiv.textContent = `Official: ${item.official_title}`;
                        li.appendChild(officialDiv);
                    }
                    
                    // Show summary if it exists and is different from display title
                    if (item.summary && item.summary.trim() && item.summary !== displayTitle) {
                        const summaryDiv = document.createElement("div");
                        summaryDiv.className = "text-sm text-slate-500 mt-2 leading-relaxed";
                        summaryDiv.textContent = item.summary;
                        li.appendChild(summaryDiv);
                    }
                    
                    ul.appendChild(li);
                });
                sourceSection.appendChild(ul);
            }

            dateSection.appendChild(sourceSection);
        });

        container.appendChild(dateSection);
    });

    // Show message if no items in this chunk
    if (chunkDates.length === 0 && allDatesInChunk.length === 0) {
        container.innerHTML = `<p class='text-slate-500 italic text-center py-8'>No items found for ${formatDate(dateRange.start)} - ${formatDate(dateRange.end)}.</p>`;
    }

    // Calculate total number of chunks available
    // Find the oldest date in the year
    const oldestDate = allDatesInYear.length > 0 ? allDatesInYear[allDatesInYear.length - 1] : null;
    let totalChunks = 1;
    if (oldestDate) {
        const oldest = new Date(oldestDate + "T00:00:00");
        const now = new Date();
        now.setHours(0, 0, 0, 0);
        const daysDiff = Math.ceil((now - oldest) / (1000 * 60 * 60 * 24));
        totalChunks = Math.max(1, Math.ceil(daysDiff / DAYS_PER_CHUNK));
    }

    renderPagination(year, chunkIndex, totalChunks, dateRange);
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

    searchMode = true;
    searchQuery = query.toLowerCase().trim();
    searchResults = [];

    // Search through all items in all years
    const years = Object.keys(allData.years || {});
    
    years.forEach(year => {
        const yearData = allData.years[year];
        const grouped = yearData.grouped || {};
        
        Object.keys(grouped).forEach(date => {
            const dateData = grouped[date];
            Object.keys(dateData).forEach(source => {
                const items = dateData[source];
                items.forEach(item => {
                    const title = (item.title || "").toLowerCase();
                    const shortTitle = (item.short_title || "").toLowerCase();
                    const summary = (item.summary || "").toLowerCase();
                    const searchText = title + " " + shortTitle + " " + summary;
                    
                    if (searchText.includes(searchQuery)) {
                        searchResults.push({
                            ...item,
                            date: date,
                            source: source
                        });
                    }
                });
            });
        });
    });

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
    
    legislationItems.forEach(bill => {
        const title = (bill.title || "").toLowerCase();
        const shortTitle = (bill.short_title || "").toLowerCase();
        const officialTitle = (bill.official_title || "").toLowerCase();
        const summary = (bill.summary || "").toLowerCase();
        const sponsor = (bill.sponsor_name || "").toLowerCase();
        const searchText = title + " " + shortTitle + " " + officialTitle + " " + summary + " " + sponsor;
        
        if (searchText.includes(searchQuery)) {
            searchResults.push({
                ...bill,
                date: bill.latest_action_date ? bill.latest_action_date.split("T")[0] : bill.published ? bill.published.split("T")[0] : "",
                source: bill.source || "Congress.gov API",
                bill_number: `${bill.bill_type || ""} ${bill.bill_number || ""}`.trim()
            });
        }
    });

    // Sort search results by date (newest first)
    searchResults.sort((a, b) => {
        const dateA = a.published || a.date || "";
        const dateB = b.published || b.date || "";
        return dateB.localeCompare(dateA);
    });

    displaySearchResults();
}

function displaySearchResults() {
    const container = document.getElementById("content");
    container.innerHTML = "";

    // Clear active year tabs
    document.querySelectorAll(".year-tab").forEach(btn => {
        btn.classList.remove("bg-civic-blue", "text-white", "border-civic-blue");
        btn.classList.add("bg-slate-100", "text-slate-700", "border-transparent");
    });

    // Hide pagination
    document.getElementById("pagination").innerHTML = "";

    if (searchResults.length === 0) {
        container.innerHTML = `<p class='text-slate-500 italic text-center py-8'>No results found for "${searchQuery}".</p>`;
        return;
    }

    const resultsHeader = document.createElement("div");
    resultsHeader.className = "mb-6 p-5 bg-blue-50 rounded-xl border-l-4 border-civic-blue";
    resultsHeader.innerHTML = `
        <h2 class="text-xl font-bold text-civic-blue mb-1">Search Results (${searchResults.length} found)</h2>
        <p class="text-slate-600">Searching for: "<strong>${searchQuery}</strong>"</p>
    `;
    container.appendChild(resultsHeader);

    // Group results by date
    const groupedByDate = {};
    searchResults.forEach(item => {
        const date = item.date || "Unknown";
        if (!groupedByDate[date]) {
            groupedByDate[date] = {};
        }
        const source = item.source || "Unknown";
        if (!groupedByDate[date][source]) {
            groupedByDate[date][source] = [];
        }
        groupedByDate[date][source].push(item);
    });

    // Display results grouped by date and source
    const dates = Object.keys(groupedByDate).sort().reverse();
    
    dates.forEach(date => {
        const dateSection = document.createElement("div");
        dateSection.className = "mb-8 p-6 bg-gradient-to-r from-slate-50 to-white rounded-xl border-l-4 border-civic-blue shadow-sm";

        const dateHeader = document.createElement("h2");
        dateHeader.className = "text-xl font-bold text-civic-navy mb-4";
        dateHeader.textContent = formatDate(date);
        dateSection.appendChild(dateHeader);

        const sources = groupedByDate[date];
        Object.keys(sources).sort().forEach(source => {
            const sourceSection = document.createElement("div");
            sourceSection.className = "mb-5 p-4 bg-white rounded-lg border-l-3 border-emerald-500 shadow-sm border";

            const srcHeader = document.createElement("h3");
            srcHeader.className = "text-lg font-semibold text-emerald-600 mb-3";
            srcHeader.textContent = source;
            sourceSection.appendChild(srcHeader);

            const ul = document.createElement("ul");
            ul.className = "space-y-3";
            sources[source].forEach(item => {
                const li = document.createElement("li");
                li.className = "pb-3 border-b border-slate-100 last:border-0 last:pb-0";
                
                const a = document.createElement("a");
                a.href = item.link || item.url || "#";
                // Use short_title for Kansas bills if available, otherwise use title
                const displayTitle = item.short_title || item.title || "(no title)";
                a.target = "_blank";
                a.rel = "noopener noreferrer";
                a.className = "text-civic-blue hover:text-civic-blue-dark font-medium hover:underline transition-colors";
                
                // Highlight search terms in title
                if (displayTitle) {
                    const regex = new RegExp(`(${searchQuery})`, "gi");
                    a.innerHTML = displayTitle.replace(regex, "<mark>$1</mark>");
                } else {
                    a.textContent = "(no title)";
                }
                
                li.appendChild(a);
                
                // Show bill number
                if (item.bill_number) {
                    const billNumDiv = document.createElement("div");
                    billNumDiv.className = "text-sm text-civic-blue font-semibold mt-1";
                    billNumDiv.textContent = `Bill: ${item.bill_number}`;
                    li.appendChild(billNumDiv);
                }
                
                // Show official title for Congress bills if available and different
                if (item.official_title && item.official_title !== displayTitle) {
                    const officialDiv = document.createElement("div");
                    officialDiv.className = "text-sm text-slate-600 mt-1 italic";
                    // Highlight search terms in official title
                    if (searchQuery) {
                        const regex = new RegExp(`(${searchQuery})`, "gi");
                        officialDiv.innerHTML = `Official: ${item.official_title.replace(regex, "<mark>$1</mark>")}`;
                    } else {
                        officialDiv.textContent = `Official: ${item.official_title}`;
                    }
                    li.appendChild(officialDiv);
                }
                
                // Show summary if it exists and is different from display title
                if (item.summary && item.summary.trim() && item.summary !== displayTitle) {
                    const summaryDiv = document.createElement("div");
                    summaryDiv.className = "text-sm text-slate-500 mt-2 leading-relaxed";
                    
                    // Also highlight search terms in summary
                    if (item.summary && searchQuery) {
                        const summary = item.summary;
                        const regex = new RegExp(`(${searchQuery})`, "gi");
                        summaryDiv.innerHTML = summary.replace(regex, "<mark>$1</mark>");
                    } else {
                        summaryDiv.textContent = item.summary;
                    }
                    
                    li.appendChild(summaryDiv);
                }
                
                ul.appendChild(li);
            });
            sourceSection.appendChild(ul);
            dateSection.appendChild(sourceSection);
        });

        container.appendChild(dateSection);
    });
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

function renderPagination(year, current, total, dateRange) {
    const container = document.getElementById("pagination");
    container.innerHTML = "";

    if (total <= 1) return;

    // Format date range for display
    const startFormatted = formatDate(dateRange.start);
    const endFormatted = formatDate(dateRange.end);
    
    const paginationInfo = document.createElement("div");
    paginationInfo.className = "text-center text-slate-600 mb-4 text-sm";
    paginationInfo.textContent = `Showing ${startFormatted} - ${endFormatted} (${current + 1} of ${total} periods)`;
    container.appendChild(paginationInfo);

    const btnContainer = document.createElement("div");
    btnContainer.className = "flex justify-center flex-wrap gap-2";

    // Previous 7 days button
    if (current > 0) {
        const prevBtn = document.createElement("button");
        prevBtn.innerHTML = `
            <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
            </svg>
            Previous 7 Days
        `;
        prevBtn.className = "px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded-lg text-sm font-medium transition-colors";
        prevBtn.onclick = () => {
            currentPage = current - 1;
            displayUnifiedView(year, current - 1);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        };
        btnContainer.appendChild(prevBtn);
    }

    // Next 7 days button
    if (current < total - 1) {
        const nextBtn = document.createElement("button");
        nextBtn.innerHTML = `
            Next 7 Days
            <svg class="w-4 h-4 inline ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
        `;
        nextBtn.className = "px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded-lg text-sm font-medium transition-colors";
        nextBtn.onclick = () => {
            currentPage = current + 1;
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

    if (searchButton) {
        searchButton.addEventListener("click", handleSearch);
    }

    if (clearButton) {
        clearButton.addEventListener("click", () => {
            searchInput.value = "";
            performSearch("");
        });
    }
}

async function loadWeeklyOverview() {
    const container = document.getElementById("weekly-overview-content");
    const section = document.getElementById("weekly-overview-section");
    if (!container || !section) return;
    
    // Set up toggle functionality
    const header = document.getElementById("weekly-overview-header");
    if (header) {
        // Ensure it starts collapsed
        section.classList.add("collapsed");
        section.classList.remove("expanded");
        
        // Add click handler to header
        header.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (section.classList.contains("collapsed")) {
                section.classList.remove("collapsed");
                section.classList.add("expanded");
            } else {
                section.classList.remove("expanded");
                section.classList.add("collapsed");
            }
        };
        
        // Also make the entire header clickable
        header.style.cursor = "pointer";
    }
    
    try {
        const res = await fetch("weekly/latest.json");
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
        
        // Summary text
        html += `<div class="leading-relaxed text-slate-700">`;
        const script = data.script || "";
        // Convert line breaks to HTML
        const scriptHtml = script.split("\n").map(line => {
            if (line.trim() === "") {
                return "<br>";
            }
            return `<p class="my-2">${line}</p>`;
        }).join("");
        html += scriptHtml;
        html += `</div>`;
        
        // Item counts
        const counts = data.item_counts || {};
        if (counts.congress > 0 || counts.kansas > 0) {
            html += `<div class="mt-5 pt-4 border-t border-slate-200 text-sm text-slate-500">`;
            html += `This week: ${counts.congress} Congress items, ${counts.kansas} Kansas items`;
            html += `</div>`;
        }
        
        // Update container content
        container.innerHTML = html;
    } catch (error) {
        // If weekly overview doesn't exist, hide the section
        if (section) {
            section.style.display = "none";
        }
    }
}

window.onload = () => {
    loadData();
    setupSearch();
};
