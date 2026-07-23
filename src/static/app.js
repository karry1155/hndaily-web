const THEME_KEY = "hnhot-v43-theme";
const STAR_KEY = "hnhot-v43-starred";

function readStars() {
  try { return new Set(JSON.parse(localStorage.getItem(STAR_KEY) || "[]")); }
  catch (_) { return new Set(); }
}

function syncStars() {
  const stars = readStars();
  document.querySelectorAll("[data-star-id]").forEach((button) => {
    const active = stars.has(button.dataset.starId);
    button.classList.toggle("is-starred", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

document.addEventListener("click", (event) => {
  const star = event.target.closest("[data-star-id]");
  if (star) {
    const stars = readStars();
    if (stars.has(star.dataset.starId)) stars.delete(star.dataset.starId);
    else stars.add(star.dataset.starId);
    localStorage.setItem(STAR_KEY, JSON.stringify([...stars]));
    syncStars();
  }
  if (event.target.closest("[data-theme-cycle]")) {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem(THEME_KEY, next);
  }
});

document.querySelectorAll("[data-search-input]").forEach((input) => {
  const main = input.closest("main");
  const results = main.querySelector("[data-archive-search-results]");
  const defaults = main.querySelector("[data-archive-default]");
  const empty = main.querySelector("[data-search-empty]");
  let catalog;
  input.addEventListener("input", async () => {
    const query = input.value.trim().toLocaleLowerCase("zh-CN");
    if (results?.dataset.searchSource) {
      if (defaults) defaults.hidden = Boolean(query);
      results.hidden = !query;
      if (!query) {
        results.replaceChildren();
        if (empty) empty.hidden = true;
        return;
      }
      catalog ||= await fetch(results.dataset.searchSource).then((response) => response.json());
      const matches = catalog.items
        .filter((item) => JSON.stringify(item).toLocaleLowerCase("zh-CN").includes(query))
        .slice(0, 80);
      results.innerHTML = matches.map((item) => `<article class="story-card"><span class="scope-badge scope-${escapeHtml(item.scope)}">${({hainan:"H",domestic:"D",mixed:"M",national:"N",foreign:"F"})[item.scope] || "–"}</span><a class="story-copy" href="${escapeHtml(item.detail_path)}"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.ai_summary || "正文已入库")}</p></a></article>`).join("");
      if (empty) empty.hidden = matches.length > 0;
      return;
    }

    const cards = [...main.querySelectorAll("[data-search-card]")];
    cards.forEach((card) => {
      card.hidden = !card.dataset.searchText.toLocaleLowerCase("zh-CN").includes(query);
    });
    main.querySelectorAll("[data-search-group]").forEach((group) => {
      group.hidden = !group.querySelector("[data-search-card]:not([hidden])");
    });
    if (empty) empty.hidden = cards.some((card) => !card.hidden);
  });
});

document.querySelectorAll("[data-report-browser]").forEach((browser) => {
  const syncReportState = () => {
    const period = browser.dataset.reportPeriod;
    const date = browser.dataset.reportDate;
    const dateTabs = browser.querySelector("[data-report-date-tabs]");
    const showDates = period === "日报";
    if (dateTabs) dateTabs.hidden = !showDates;
    browser.querySelector("[data-report-selection]").textContent = showDates ? `${period} · ${date}` : period;
    browser.querySelector("[data-report-title]").textContent = `${period}能力正在建设`;
  };
  browser.querySelectorAll("[data-report-control]").forEach((control) => {
    control.addEventListener("click", (event) => {
      const button = event.target.closest("[data-report-value]");
      if (!button) return;
      control.querySelectorAll("[data-report-value]").forEach((candidate) => {
        const active = candidate === button;
        candidate.classList.toggle("active", active);
        candidate.setAttribute("aria-pressed", String(active));
      });
      if (control.dataset.reportControl === "period") browser.dataset.reportPeriod = button.dataset.reportValue;
      if (control.dataset.reportControl === "date") browser.dataset.reportDate = button.dataset.reportValue;
      syncReportState();
    });
  });
  syncReportState();
});

const savedTheme = localStorage.getItem(THEME_KEY);
if (savedTheme) document.documentElement.dataset.theme = savedTheme;
syncStars();
