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
            "<p class='error'>Error loading data. Please try again later.</p>";
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
    
    // Load weekly overview
    loadWeeklyOverview();
    
    // Load and display data
    const years = Object.keys(allData.years || {});
    const yearTabs = document.getElementById("year-tabs");
    yearTabs.innerHTML = "";

    if (years.length === 0) {
        document.getElementById("content").innerHTML = 
            "<p class='empty-state'>No data available. Run the backfill script to populate history.</p>";
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
        btn.className = "year-tab";
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
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    // Get date range for this chunk
    const dateRange = getDateRangeForChunk(chunkIndex);
    
    // Get all items from RSS feeds for this year
    const grouped = yearData.grouped || {};
    let allRssItems = [];
    Object.keys(grouped).forEach(date => {
        const dateData = grouped[date];
        Object.keys(dateData).forEach(source => {
            const items = dateData[source];
            items.forEach(item => ({
                ...item,
                date: date,
                source: source
            }));
            allRssItems = allRssItems.concat(items.map(item => ({
                ...item,
                date: date,
                source: source
            })));
        });
    });
    
    // Get all legislation items for this year
    const legislation = allData.legislation || {};
    let legislationItems = [];
    
    if (legislation.pages) {
        const allLegPages = legislation.pages.flat();
        legislationItems = allLegPages.map(bill => ({
            date: bill.latest_action_date ? bill.latest_action_date.split("T")[0] : (bill.published ? bill.published.split("T")[0] : ""),
            source: bill.source || "Congress.gov API",
            title: `${bill.bill_type || ""} ${bill.bill_number || ""}: ${bill.title || ""}`.trim(),
            link: bill.url || "",
            published: bill.published || bill.latest_action_date || "",
            summary: bill.summary || "",
            bill_number: bill.bill_number,
            bill_type: bill.bill_type,
            sponsor_name: bill.sponsor_name,
            latest_action: bill.latest_action
        })).filter(item => {
            if (!item.date) return false;
            try {
                const itemYear = new Date(item.date + "T00:00:00").getFullYear();
                return itemYear.toString() === year;
            } catch {
                return false;
            }
        });
    } else if (Array.isArray(legislation)) {
        legislationItems = legislation.map(bill => ({
            date: bill.latest_action_date ? bill.latest_action_date.split("T")[0] : (bill.published ? bill.published.split("T")[0] : ""),
            source: bill.source || "Congress.gov API",
            title: `${bill.bill_type || ""} ${bill.bill_number || ""}: ${bill.title || ""}`.trim(),
            link: bill.url || "",
            published: bill.published || bill.latest_action_date || "",
            summary: bill.summary || ""
        })).filter(item => {
            if (!item.date) return false;
            try {
                const itemYear = new Date(item.date + "T00:00:00").getFullYear();
                return itemYear.toString() === year;
            } catch {
                return false;
            }
        });
    }
    
    // Combine all items
    let allItems = [...allRssItems, ...legislationItems];
    
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

    // Render dates in this chunk (newest first)
    // Show all dates in the chunk, even if they have no items (for empty state)
    allDatesInChunk.forEach(date => {
        const dateSection = document.createElement("div");
        dateSection.className = "date-section";

        const dateHeader = document.createElement("h2");
        dateHeader.textContent = formatDate(date);
        dateSection.appendChild(dateHeader);

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
            sourceSection.className = "source-section";

            const srcHeader = document.createElement("h3");
            srcHeader.textContent = source;
            sourceSection.appendChild(srcHeader);

            // Get items for this source in this chunk
            const itemsInChunk = groupedByDate[date] && groupedByDate[date][source] 
                ? groupedByDate[date][source] 
                : [];

            // Show items or empty state
            if (itemsInChunk.length === 0) {
                const emptyMsg = document.createElement("p");
                emptyMsg.className = "empty-state";
                emptyMsg.textContent = "No updates for this date/source";
                sourceSection.appendChild(emptyMsg);
            } else {
                const ul = document.createElement("ul");
                itemsInChunk.forEach(item => {
                    const li = document.createElement("li");
                    const a = document.createElement("a");
                    a.href = item.link || item.url || "#";
                    // Use short_title for Kansas bills if available, otherwise use title
                    const displayTitle = item.short_title || item.title || "(no title)";
                    a.textContent = displayTitle;
                    a.target = "_blank";
                    a.rel = "noopener noreferrer";
                    li.appendChild(a);
                    
                    // Show bill number for Kansas bills
                    if (item.bill_number) {
                        const billNumDiv = document.createElement("div");
                        billNumDiv.className = "bill-number";
                        billNumDiv.style.cssText = "font-size: 0.85em; color: #1a73e8; margin-top: 4px; font-weight: 600;";
                        billNumDiv.textContent = `Bill: ${item.bill_number}`;
                        li.appendChild(billNumDiv);
                    }
                    
                    // Show summary if it exists and is different from display title
                    if (item.summary && item.summary.trim() && item.summary !== displayTitle) {
                        const summaryDiv = document.createElement("div");
                        summaryDiv.className = "item-summary";
                        summaryDiv.style.cssText = "font-size: 0.9em; color: #666; margin-top: 4px; margin-left: 0; line-height: 1.4;";
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
        container.innerHTML = `<p class='empty-state'>No items found for ${formatDate(dateRange.start)} - ${formatDate(dateRange.end)}.</p>`;
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
        const summary = (bill.summary || "").toLowerCase();
        const sponsor = (bill.sponsor_name || "").toLowerCase();
        const searchText = title + " " + summary + " " + sponsor;
        
        if (searchText.includes(searchQuery)) {
            searchResults.push({
                ...bill,
                date: bill.latest_action_date ? bill.latest_action_date.split("T")[0] : bill.published ? bill.published.split("T")[0] : "",
                source: bill.source || "Congress.gov API"
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
        btn.classList.remove("active");
    });

    // Hide pagination
    document.getElementById("pagination").innerHTML = "";

    if (searchResults.length === 0) {
        container.innerHTML = `<p class='empty-state'>No results found for "${searchQuery}".</p>`;
        return;
    }

    const resultsHeader = document.createElement("div");
    resultsHeader.className = "search-results-header";
    resultsHeader.innerHTML = `<h2>Search Results (${searchResults.length} found)</h2><p>Searching for: "<strong>${searchQuery}</strong>"</p>`;
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
        dateSection.className = "date-section";

        const dateHeader = document.createElement("h2");
        dateHeader.textContent = formatDate(date);
        dateSection.appendChild(dateHeader);

        const sources = groupedByDate[date];
        Object.keys(sources).sort().forEach(source => {
            const sourceSection = document.createElement("div");
            sourceSection.className = "source-section";

            const srcHeader = document.createElement("h3");
            srcHeader.textContent = source;
            sourceSection.appendChild(srcHeader);

            const ul = document.createElement("ul");
            sources[source].forEach(item => {
                const li = document.createElement("li");
                const a = document.createElement("a");
                a.href = item.link || item.url || "#";
                // Use short_title for Kansas bills if available, otherwise use title
                const displayTitle = item.short_title || item.title || "(no title)";
                a.target = "_blank";
                a.rel = "noopener noreferrer";
                
                // Highlight search terms in title
                if (displayTitle) {
                    const regex = new RegExp(`(${searchQuery})`, "gi");
                    a.innerHTML = displayTitle.replace(regex, "<mark>$1</mark>");
                } else {
                    a.textContent = "(no title)";
                }
                
                li.appendChild(a);
                
                // Show bill number for Kansas bills
                if (item.bill_number) {
                    const billNumDiv = document.createElement("div");
                    billNumDiv.className = "bill-number";
                    billNumDiv.style.cssText = "font-size: 0.85em; color: #1a73e8; margin-top: 4px; font-weight: 600;";
                    billNumDiv.textContent = `Bill: ${item.bill_number}`;
                    li.appendChild(billNumDiv);
                }
                
                // Show summary if it exists and is different from display title
                if (item.summary && item.summary.trim() && item.summary !== displayTitle) {
                    const summaryDiv = document.createElement("div");
                    summaryDiv.className = "item-summary";
                    summaryDiv.style.cssText = "font-size: 0.9em; color: #666; margin-top: 4px; margin-left: 0; line-height: 1.4;";
                    
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
    paginationInfo.className = "pagination-info";
    paginationInfo.textContent = `Showing ${startFormatted} - ${endFormatted} (${current + 1} of ${total} periods)`;
    container.appendChild(paginationInfo);

    const btnContainer = document.createElement("div");
    btnContainer.className = "pagination-buttons";

    // Previous 7 days button
    if (current > 0) {
        const prevBtn = document.createElement("button");
        prevBtn.textContent = "← Previous 7 Days";
        prevBtn.className = "pagination-btn";
        prevBtn.onclick = () => {
            currentPage = current - 1;
            displayUnifiedView(year, current - 1);
        };
        btnContainer.appendChild(prevBtn);
    }

    // Next 7 days button
    if (current < total - 1) {
        const nextBtn = document.createElement("button");
        nextBtn.textContent = "Next 7 Days →";
        nextBtn.className = "pagination-btn";
        nextBtn.onclick = () => {
            currentPage = current + 1;
            displayUnifiedView(year, current + 1);
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
            
            console.log("Weekly overview header clicked");
            console.log("Current classes:", section.classList.toString());
            
            if (section.classList.contains("collapsed")) {
                section.classList.remove("collapsed");
                section.classList.add("expanded");
                console.log("Expanded");
            } else {
                section.classList.remove("expanded");
                section.classList.add("collapsed");
                console.log("Collapsed");
            }
        };
        
        // Also make the entire header clickable
        header.style.cursor = "pointer";
    } else {
        console.error("Weekly overview header not found");
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
        
        let html = `<div style="margin-bottom: 15px; color: #666; font-size: 0.9em;">Week of ${weekRange}</div>`;
        
        // Audio player if available
        if (data.audio_available && data.audio_file) {
            html += `
                <div style="margin-bottom: 20px;">
                    <audio controls style="width: 100%; max-width: 500px;">
                        <source src="${data.audio_file}" type="audio/mpeg">
                        Your browser does not support the audio element.
                    </audio>
                </div>
            `;
        }
        
        // Summary text
        html += `<div style="line-height: 1.8; color: #333;">`;
        const script = data.script || "";
        // Convert line breaks to HTML
        const scriptHtml = script.split("\n").map(line => {
            if (line.trim() === "") {
                return "<br>";
            }
            return `<p style="margin: 8px 0;">${line}</p>`;
        }).join("");
        html += scriptHtml;
        html += `</div>`;
        
        // Item counts
        const counts = data.item_counts || {};
        if (counts.congress > 0 || counts.kansas > 0 || counts.va > 0) {
            html += `<div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #ddd; font-size: 0.9em; color: #666;">`;
            html += `This week: ${counts.congress} Congress items, ${counts.kansas} Kansas items, ${counts.va} VA items`;
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
