let currentYear = null;
let currentPage = 0;
let allData = null;
let searchQuery = "";
let searchMode = false;
let searchResults = [];

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
        if (index === 0 && !searchMode) {
            currentYear = year;
            btn.click();
        }
    });
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

window.onload = () => {
    loadData();
    setupSearch();
};
