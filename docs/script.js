async function loadData() {
    const res = await fetch("site_data.json");
    const data = await res.json();
  
    document.getElementById("last-updated").textContent =
      "Last updated: " +
      new Date(data.last_updated).toLocaleString("en-US", {
        timeZone: "America/Chicago"
      });
  
    const yearTabs = document.getElementById("year-tabs");
    const content = document.getElementById("content");
  
    yearTabs.innerHTML = "";
    content.innerHTML = "";
  
    const years = Object.keys(data.years);
  
    if (years.length === 0) {
      content.innerHTML = "<p>No data available.</p>";
      return;
    }
  
    years.forEach((year, index) => {
      const btn = document.createElement("button");
      btn.textContent = year;
      btn.className = "year-tab";
      btn.onclick = () => showYear(year, 0, data);
      yearTabs.appendChild(btn);
  
      if (index === 0) btn.click();
    });
  }
  
  function showYear(year, pageIndex, data) {
    const yearData = data.years[year];
    const container = document.getElementById("content");
  
    container.innerHTML = "";
  
    const pages = yearData.pages;
    const page = pages[pageIndex] || [];
  
    const grouped = {};
  
    page.forEach(item => {
      if (!grouped[item.date]) grouped[item.date] = {};
      if (!grouped[item.date][item.source]) grouped[item.date][item.source] = [];
      grouped[item.date][item.source].push(item);
    });
  
    Object.keys(grouped)
      .sort()
      .reverse()
      .forEach(date => {
        const dateHeader = document.createElement("h2");
        dateHeader.textContent = date;
        container.appendChild(dateHeader);
  
        const sources = grouped[date];
  
        Object.keys(sources).forEach(source => {
          const srcHeader = document.createElement("h3");
          srcHeader.textContent = source;
          container.appendChild(srcHeader);
  
          const ul = document.createElement("ul");
  
          sources[source].forEach(item => {
            const li = document.createElement("li");
            const a = document.createElement("a");
            a.href = item.link;
            a.textContent = item.title;
            a.target = "_blank";
            li.appendChild(a);
            ul.appendChild(li);
          });
  
          container.appendChild(ul);
        });
      });
  
    renderPagination(year, pageIndex, pages.length, data);
  }
  
  function renderPagination(year, current, total, data) {
    const container = document.getElementById("pagination");
    container.innerHTML = "";
  
    if (total <= 1) return;
  
    for (let i = 0; i < total; i++) {
      const btn = document.createElement("button");
      btn.textContent = i + 1;
      btn.className = i === current ? "active-page" : "";
      btn.onclick = () => showYear(year, i, data);
      container.appendChild(btn);
    }
  }
  
  window.onload = loadData;
  