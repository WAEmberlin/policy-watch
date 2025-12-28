let currentYear = null;
let currentPage = 0;
let allData = null;
let searchQuery = "";
let searchMode = false;
let searchResults = [];
let currentView = "feeds"; // "feeds" or "legislation"
let filteredLegislation = [];
let legislationPage = 0; // Current page for legislation pagination

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

    const yearTabs = document.getElementById("year-tabs");
    const content = document.getElementById("content");

    yearTabs.innerHTML = "";
    content.innerHTML = "";

    const years = Object.keys(allData.years || {});

    if (years.length === 0) {
        content.innerHTML = "<p class='empty-state'>No data available. Run the backfill script to populate history.</p>";
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
            showYear(year, 0);
        };
        yearTabs.appendChild(btn);

        // Show first year by default
        if (index === 0 && !searchMode && currentView === "feeds") {
            currentYear = year;
            btn.click();
        }
    });
    
    // Setup view switching
    setupViewSwitching();
    
    // Setup legislation filters
    setupLegislationFilters();
    
    // Show initial view
    if (currentView === "legislation") {
        showLegislationView();
    }
}

function performSearch(query) {
    if (!query || query.trim().length === 0) {
        searchMode = false;
        searchQuery = "";
        if (currentYear) {
            showYear(currentYear, 0);
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
                a.href = item.link;
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

function showYear(year, pageIndex) {
    if (searchMode) return; // Don't show year view if in search mode
    
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

    // Get paginated items
    const pages = yearData.pages || [];
    const page = pages[pageIndex] || [];

    if (page.length === 0) {
        container.innerHTML = "<p class='empty-state'>No items on this page.</p>";
        renderPagination(year, pageIndex, pages.length);
        return;
    }

    // Group page items by date and source
    const grouped = {};
    page.forEach(item => {
        if (!grouped[item.date]) grouped[item.date] = {};
        if (!grouped[item.date][item.source]) grouped[item.date][item.source] = [];
        grouped[item.date][item.source].push(item);
    });

    // Get dates that appear on the current page (newest first)
    const pageDates = Object.keys(grouped).sort().reverse();
    
    // Only render dates that have items on the current page
    pageDates.forEach(date => {
        const dateSection = document.createElement("div");
        dateSection.className = "date-section";

        const dateHeader = document.createElement("h2");
        dateHeader.textContent = formatDate(date);
        dateSection.appendChild(dateHeader);

        // Get all sources for this date from the full grouped structure
        const dateSources = yearData.grouped[date] || {};
        const allSources = Object.keys(dateSources).sort();

        // Render all sources for this date (even if empty on current page)
        allSources.forEach(source => {
            const sourceSection = document.createElement("div");
            sourceSection.className = "source-section";

            const srcHeader = document.createElement("h3");
            srcHeader.textContent = source;
            sourceSection.appendChild(srcHeader);

            // Get items for this source on the current page
            const items = grouped[date] && grouped[date][source] 
                ? grouped[date][source] 
                : [];

            if (items.length === 0) {
                // Show empty state for this source
                const emptyMsg = document.createElement("p");
                emptyMsg.className = "empty-state";
                emptyMsg.textContent = "No updates for this date/source";
                sourceSection.appendChild(emptyMsg);
            } else {
                const ul = document.createElement("ul");
                items.forEach(item => {
                    const li = document.createElement("li");
                    const a = document.createElement("a");
                    a.href = item.link;
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
        prevBtn.onclick = () => showYear(year, current - 1);
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
        btn.onclick = () => showYear(year, i);
        btnContainer.appendChild(btn);
    }

    // Next button
    if (current < total - 1) {
        const nextBtn = document.createElement("button");
        nextBtn.textContent = "Next →";
        nextBtn.className = "pagination-btn";
        nextBtn.onclick = () => showYear(year, current + 1);
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

// Legislation view functions
function setupViewSwitching() {
    const feedsBtn = document.getElementById("view-feeds");
    const legislationBtn = document.getElementById("view-legislation");
    
    if (feedsBtn) {
        feedsBtn.onclick = () => {
            currentView = "feeds";
            updateViewTabs();
            document.getElementById("year-tabs").style.display = "flex";
            document.getElementById("legislation-filters").style.display = "none";
            document.getElementById("search-container").style.display = "block";
            if (currentYear) {
                showYear(currentYear, 0);
            }
        };
    }
    
    if (legislationBtn) {
        legislationBtn.onclick = () => {
            currentView = "legislation";
            legislationPage = 0; // Reset to first page
            updateViewTabs();
            document.getElementById("year-tabs").style.display = "none";
            document.getElementById("legislation-filters").style.display = "block";
            document.getElementById("search-container").style.display = "none";
            showLegislationView(0);
        };
    }
}

function updateViewTabs() {
    document.querySelectorAll(".view-tab").forEach(btn => {
        btn.classList.remove("active");
    });
    if (currentView === "feeds") {
        document.getElementById("view-feeds")?.classList.add("active");
    } else {
        document.getElementById("view-legislation")?.classList.add("active");
    }
}

function setupLegislationFilters() {
    const searchInput = document.getElementById("legislation-search");
    const typeFilter = document.getElementById("bill-type-filter");
    const clearBtn = document.getElementById("clear-legislation-filters");
    
    if (searchInput) {
        searchInput.addEventListener("input", () => {
            legislationPage = 0; // Reset to first page when filtering
            applyLegislationFilters();
        });
        searchInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                legislationPage = 0;
                applyLegislationFilters();
            }
        });
    }
    
    if (typeFilter) {
        typeFilter.addEventListener("change", () => {
            legislationPage = 0; // Reset to first page when filtering
            applyLegislationFilters();
        });
    }
    
    if (clearBtn) {
        clearBtn.onclick = () => {
            if (searchInput) searchInput.value = "";
            if (typeFilter) typeFilter.value = "";
            legislationPage = 0;
            applyLegislationFilters();
        };
    }
}

function showLegislationView(pageIndex = 0) {
    legislationPage = pageIndex;
    
    // Get legislation data (could be array for old format or object with pages for new format)
    const legislationData = allData?.legislation || {};
    
    let allLegislation = [];
    let totalPages = 0;
    
    // Handle both old format (array) and new format (object with pages)
    if (Array.isArray(legislationData)) {
        allLegislation = legislationData;
        // Calculate pages for old format
        const ITEMS_PER_PAGE = 50;
        totalPages = Math.ceil(allLegislation.length / ITEMS_PER_PAGE);
        const startIdx = pageIndex * ITEMS_PER_PAGE;
        allLegislation = allLegislation.slice(startIdx, startIdx + ITEMS_PER_PAGE);
    } else if (legislationData.pages) {
        // New paginated format
        allLegislation = legislationData.pages[pageIndex] || [];
        totalPages = legislationData.pages.length;
    }
    
    if (allLegislation.length === 0 && pageIndex === 0) {
        document.getElementById("content").innerHTML = 
            "<p class='empty-state'>No legislation data available. Run the Congress API fetch script to populate.</p>";
        document.getElementById("pagination").innerHTML = "";
        return;
    }
    
    // Apply filters to current page
    filteredLegislation = allLegislation;
    displayLegislation();
    
    // Render pagination
    renderLegislationPagination(pageIndex, totalPages);
}

function displayLegislation() {
    const container = document.getElementById("content");
    container.innerHTML = "";
    
    if (filteredLegislation.length === 0) {
        container.innerHTML = "<p class='empty-state'>No bills match the current filters.</p>";
        document.getElementById("pagination").innerHTML = "";
        return;
    }
    
    // Group bills by date (using latest_action_date or published)
    const groupedByDate = {};
    
    filteredLegislation.forEach(bill => {
        // Get date from latest_action_date or published
        const dateStr = bill.latest_action_date || bill.published || "";
        if (!dateStr) return;
        
        // Extract date part (YYYY-MM-DD)
        let dateKey = "";
        try {
            const dateObj = new Date(dateStr);
            if (!isNaN(dateObj.getTime())) {
                dateKey = dateObj.toISOString().split("T")[0]; // YYYY-MM-DD format
            } else {
                // Try parsing as string
                dateKey = dateStr.split("T")[0];
            }
        } catch {
            dateKey = dateStr.split("T")[0];
        }
        
        if (!dateKey) return;
        
        if (!groupedByDate[dateKey]) {
            groupedByDate[dateKey] = [];
        }
        groupedByDate[dateKey].push(bill);
    });
    
    // Sort dates (newest first)
    const dates = Object.keys(groupedByDate).sort().reverse();
    
    if (dates.length === 0) {
        container.innerHTML = "<p class='empty-state'>No bills with valid dates found.</p>";
        document.getElementById("pagination").innerHTML = "";
        return;
    }
    
    // Render each date section
    dates.forEach(date => {
        const dateSection = document.createElement("div");
        dateSection.className = "date-section";
        
        const dateHeader = document.createElement("h2");
        dateHeader.textContent = formatDate(date);
        dateSection.appendChild(dateHeader);
        
        // Sort bills within this date by latest action date (newest first)
        const billsForDate = groupedByDate[date].sort((a, b) => {
            const dateA = a.latest_action_date || a.published || "";
            const dateB = b.latest_action_date || b.published || "";
            return dateB.localeCompare(dateA);
        });
        
        // Create a source section for "Congress.gov API" (to match RSS feed structure)
        const sourceSection = document.createElement("div");
        sourceSection.className = "source-section";
        
        const srcHeader = document.createElement("h3");
        srcHeader.textContent = "Congress.gov API";
        sourceSection.appendChild(srcHeader);
        
        const ul = document.createElement("ul");
        
        billsForDate.forEach(bill => {
            const li = document.createElement("li");
            
            // Create bill info with link
            const billInfo = document.createElement("div");
            billInfo.style.marginBottom = "8px";
            
            // Bill number and type
            const billNumber = document.createElement("strong");
            billNumber.style.color = "#1a73e8";
            billNumber.textContent = `${bill.bill_type || ""} ${bill.bill_number || ""}`.trim();
            if (billNumber.textContent) {
                billInfo.appendChild(billNumber);
                billInfo.appendChild(document.createTextNode(": "));
            }
            
            // Title as link
            const titleLink = document.createElement("a");
            titleLink.href = bill.url || "#";
            titleLink.textContent = bill.title || "(No title)";
            titleLink.target = "_blank";
            titleLink.rel = "noopener noreferrer";
            titleLink.style.color = "#1a73e8";
            titleLink.style.textDecoration = "none";
            titleLink.style.fontWeight = "500";
            titleLink.onmouseover = function() { this.style.textDecoration = "underline"; };
            titleLink.onmouseout = function() { this.style.textDecoration = "none"; };
            billInfo.appendChild(titleLink);
            
            // Sponsor info (if available)
            if (bill.sponsor_name) {
                const sponsor = document.createElement("div");
                sponsor.style.fontSize = "0.9em";
                sponsor.style.color = "#666";
                sponsor.style.marginTop = "4px";
                sponsor.textContent = `Sponsor: ${bill.sponsor_name}`;
                billInfo.appendChild(sponsor);
            }
            
            // Latest action (if available)
            if (bill.latest_action) {
                const action = document.createElement("div");
                action.style.fontSize = "0.85em";
                action.style.color = "#888";
                action.style.marginTop = "2px";
                action.style.fontStyle = "italic";
                action.textContent = bill.latest_action;
                billInfo.appendChild(action);
            }
            
            li.appendChild(billInfo);
            ul.appendChild(li);
        });
        
        sourceSection.appendChild(ul);
        dateSection.appendChild(sourceSection);
        container.appendChild(dateSection);
    });
    
    // Pagination will be rendered by renderLegislationPagination
}

function renderLegislationPagination(current, total) {
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
        prevBtn.onclick = () => {
            legislationPage = current - 1;
            applyLegislationFilters();
        };
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
        btn.onclick = () => {
            legislationPage = i;
            applyLegislationFilters();
        };
        btnContainer.appendChild(btn);
    }
    
    // Next button
    if (current < total - 1) {
        const nextBtn = document.createElement("button");
        nextBtn.textContent = "Next →";
        nextBtn.className = "pagination-btn";
        nextBtn.onclick = () => {
            legislationPage = current + 1;
            applyLegislationFilters();
        };
        btnContainer.appendChild(nextBtn);
    }
    
    container.appendChild(btnContainer);
}

function applyLegislationFilters() {
    // Get all legislation (from all pages if paginated)
    const legislationData = allData?.legislation || {};
    let allLegislation = [];
    let totalPages = 0;
    
    if (Array.isArray(legislationData)) {
        allLegislation = legislationData;
        totalPages = Math.ceil(allLegislation.length / 50);
    } else if (legislationData.pages) {
        // Get current page
        allLegislation = legislationData.pages[legislationPage] || [];
        totalPages = legislationData.pages.length;
    }
    
    const searchInput = document.getElementById("legislation-search");
    const typeFilter = document.getElementById("bill-type-filter");
    
    const searchQuery = (searchInput?.value || "").toLowerCase().trim();
    const billType = typeFilter?.value || "";
    
    // Apply filters to current page
    filteredLegislation = allLegislation.filter(bill => {
        // Search filter
        if (searchQuery) {
            const title = (bill.title || "").toLowerCase();
            const summary = (bill.summary || "").toLowerCase();
            const sponsor = (bill.sponsor_name || "").toLowerCase();
            const searchText = title + " " + summary + " " + sponsor;
            if (!searchText.includes(searchQuery)) {
                return false;
            }
        }
        
        // Bill type filter
        if (billType && bill.bill_type !== billType) {
            return false;
        }
        
        return true;
    });
    
    displayLegislation();
    renderLegislationPagination(legislationPage, totalPages);
}

window.onload = () => {
    loadData();
    setupSearch();
};
