let currentYear = null;
let currentPage = 0;
let allData = null;
let searchQuery = "";
let searchMode = false;
let searchResults = [];
let selectedSource = "";
let selectedCategory = "";

async function loadData() {
    try {
        const res = await fetch("site_data.json");
        allData = await res.json();
    } catch (error) {
        document.getElementById("content").innerHTML = 
            "<p class='error'>Error loading data. Please try again later.</p>";
        return;
    }

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
            "<p class='empty-state'>No data available. Run the backfill script to populate history.</p>";
        return;
    }

    // Create year tabs
    years.forEach((year, index) => {
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

        // Show first year by default
        if (index === 0) {
            currentYear = year;
            btn.click();
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

function displayUnifiedView(year, pageIndex) {
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

    // Get paginated items from RSS feeds
    const pages = yearData.pages || [];
    let page = pages[pageIndex] || [];
    
    // Also include legislation items for this year if available
    const legislation = allData.legislation || {};
    let legislationItems = [];
    
    if (legislation.pages) {
        // Get all legislation pages and filter by year
        const allLegPages = legislation.pages.flat();
        legislationItems = allLegPages.map(bill => ({
            date: bill.latest_action_date ? bill.latest_action_date.split("T")[0] : (bill.published ? bill.published.split("T")[0] : ""),
            source: bill.source || "Congress.gov API",
            title: `${bill.bill_type || ""} ${bill.bill_number || ""}: ${bill.title || ""}`.trim(),
            link: bill.url || "",
            published: bill.published || bill.latest_action_date || "",
            summary: bill.summary || "",
            // Keep bill-specific fields
            bill_number: bill.bill_number,
            bill_type: bill.bill_type,
            sponsor_name: bill.sponsor_name,
            latest_action: bill.latest_action
        })).filter(item => {
            // Filter by year
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
    
    // Combine RSS feed items and legislation items
    let allPageItems = [...page, ...legislationItems];
    
    // Sort combined items by date (newest first)
    allPageItems.sort((a, b) => {
        const dateA = a.published || a.date || "";
        const dateB = b.published || b.date || "";
        return dateB.localeCompare(dateA);
    });

    if (allPageItems.length === 0) {
        container.innerHTML = "<p class='empty-state'>No items on this page.</p>";
        renderPagination(year, pageIndex, pages.length);
        return;
    }

    // Apply filters
    let filteredPage = allPageItems;
    if (selectedSource) {
        filteredPage = filteredPage.filter(item => item.source === selectedSource);
    }
    if (selectedCategory) {
        filteredPage = filteredPage.filter(item => {
            const source = item.source || "";
            return source.includes(selectedCategory);
        });
    }

    // Group by date and source
    const grouped = {};
    filteredPage.forEach(item => {
        const date = item.date || (item.published ? item.published.split("T")[0] : "");
        if (!date) return;
        
        if (!grouped[date]) grouped[date] = {};
        if (!grouped[date][item.source]) grouped[date][item.source] = [];
        grouped[date][item.source].push(item);
    });

    // Get all dates from full grouped structure (for empty state detection)
    const allDates = Object.keys(yearData.grouped || {}).sort().reverse();
    const pageDates = Object.keys(grouped).sort().reverse();

    // Render dates (newest first)
    // Always show all dates that have any items, and show all sources for each date
    allDates.forEach(date => {
        const dateSection = document.createElement("div");
        dateSection.className = "date-section";

        const dateHeader = document.createElement("h2");
        dateHeader.textContent = formatDate(date);
        dateSection.appendChild(dateHeader);

        // Get ALL sources for this date from the full grouped structure
        const rssSources = yearData.grouped[date] || {};
        const allSources = Object.keys(rssSources).sort();

        // Render ALL sources for this date (even if empty on current page)
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

            // Get items for this source from the full grouped structure
            const allItemsForSource = rssSources[source] || [];
            // Filter to only items on current page (if paginated)
            const itemsOnPage = grouped[date] && grouped[date][source] 
                ? grouped[date][source] 
                : [];

            // Show "No updates" if no items exist for this source on this date
            if (allItemsForSource.length === 0) {
                const emptyMsg = document.createElement("p");
                emptyMsg.className = "empty-state";
                emptyMsg.textContent = "No updates for this date/source";
                sourceSection.appendChild(emptyMsg);
            } else if (itemsOnPage.length === 0) {
                // Items exist but not on current page (due to pagination)
                const emptyMsg = document.createElement("p");
                emptyMsg.className = "empty-state";
                emptyMsg.textContent = "No updates for this date/source";
                sourceSection.appendChild(emptyMsg);
            } else {
                // Show items that are on current page
                const ul = document.createElement("ul");
                itemsOnPage.forEach(item => {
                    const li = document.createElement("li");
                    const a = document.createElement("a");
                    a.href = item.link || item.url || "#";
                    a.textContent = item.title || "(no title)";
                    a.target = "_blank";
                    a.rel = "noopener noreferrer";
                    li.appendChild(a);
                    ul.appendChild(li);
                });
                sourceSection.appendChild(ul);
            }

            dateSection.appendChild(sourceSection);
        });

        container.appendChild(dateSection);
    });

    renderPagination(year, pageIndex, pages.length);
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
                    const summary = (item.summary || "").toLowerCase();
                    const searchText = title + " " + summary;
                    
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
                a.textContent = item.title || "(no title)";
                a.target = "_blank";
                a.rel = "noopener noreferrer";
                
                // Highlight search terms in title
                if (item.title) {
                    const title = item.title;
                    const regex = new RegExp(`(${searchQuery})`, "gi");
                    a.innerHTML = title.replace(regex, "<mark>$1</mark>");
                }
                
                li.appendChild(a);
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

function renderPagination(year, current, total) {
    const container = document.getElementById("pagination");
    container.innerHTML = "";

    if (total <= 1) return;

    const paginationInfo = document.createElement("div");
    paginationInfo.className = "pagination-info";
    paginationInfo.textContent = `Page ${current + 1} of ${total}`;
    container.appendChild(paginationInfo);

    const btnContainer = document.createElement("div");
    btnContainer.className = "pagination-buttons";

    // Previous button
    if (current > 0) {
        const prevBtn = document.createElement("button");
        prevBtn.textContent = "← Previous";
        prevBtn.className = "pagination-btn";
        prevBtn.onclick = () => displayUnifiedView(year, current - 1);
        btnContainer.appendChild(prevBtn);
    }

    // Page number buttons
    const maxButtons = 10;
    let startPage = Math.max(0, current - Math.floor(maxButtons / 2));
    let endPage = Math.min(total, startPage + maxButtons);

    if (endPage - startPage < maxButtons) {
        startPage = Math.max(0, endPage - maxButtons);
    }

    for (let i = startPage; i < endPage; i++) {
        const btn = document.createElement("button");
        btn.textContent = i + 1;
        btn.className = i === current ? "pagination-btn active-page" : "pagination-btn";
        btn.onclick = () => displayUnifiedView(year, i);
        btnContainer.appendChild(btn);
    }

    // Next button
    if (current < total - 1) {
        const nextBtn = document.createElement("button");
        nextBtn.textContent = "Next →";
        nextBtn.className = "pagination-btn";
        nextBtn.onclick = () => displayUnifiedView(year, current + 1);
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

window.onload = () => {
    loadData();
    setupSearch();
};
