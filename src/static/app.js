const THEME_KEY = "hn-hot-theme";
const STAR_KEY = "hn-hot-starred";

function readStars() {
  try {
    const value = JSON.parse(localStorage.getItem(STAR_KEY) || "[]");
    return Array.isArray(value) ? value.filter((id) => typeof id === "string") : [];
  } catch (_) {
    return [];
  }
}

function syncStarButtons() {
  const stars = new Set(readStars());
  document.querySelectorAll("[data-star-id]").forEach((button) => {
    const active = stars.has(button.dataset.starId);
    button.classList.toggle("is-starred", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function clearSubjectFocus() {
  document.querySelectorAll(".subject-mention.is-subject-active").forEach((mention) => {
    mention.classList.remove("is-subject-active");
  });
  document.querySelectorAll("[data-subject-link].is-active").forEach((link) => {
    link.classList.remove("is-active");
    link.removeAttribute("aria-current");
  });
}

function activateSubject(subjectId, {scroll = false} = {}) {
  clearSubjectFocus();
  if (!/^subject-\d+$/.test(subjectId)) return false;
  const mentions = [...document.querySelectorAll(`[data-subject-id="${subjectId}"]`)]
    .filter((element) => element.classList.contains("subject-mention"));
  const link = document.querySelector(`[data-subject-link][data-subject-id="${subjectId}"]`);
  if (!mentions.length || !link) return false;
  mentions.forEach((mention) => mention.classList.add("is-subject-active"));
  link.classList.add("is-active");
  link.setAttribute("aria-current", "location");
  if (scroll) {
    mentions[0].scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "center",
    });
  }
  return true;
}

function subjectIdFromHash() {
  return decodeURIComponent(window.location.hash.slice(1));
}

document.addEventListener("click", (event) => {
  const subjectLink = event.target.closest("[data-subject-link]");
  if (subjectLink) {
    event.preventDefault();
    const subjectId = subjectLink.dataset.subjectId;
    if (subjectLink.classList.contains("is-active")) {
      clearSubjectFocus();
      history.pushState(null, "", `${location.pathname}${location.search}`);
    } else {
      history.pushState(null, "", `#${subjectId}`);
      activateSubject(subjectId, {scroll: true});
    }
  }
  const star = event.target.closest("[data-star-id]");
  if (star) {
    const stars = new Set(readStars());
    if (stars.has(star.dataset.starId)) stars.delete(star.dataset.starId);
    else stars.add(star.dataset.starId);
    localStorage.setItem(STAR_KEY, JSON.stringify([...stars]));
    syncStarButtons();
    renderStarred();
  }
  if (event.target.closest("[data-theme-cycle]")) {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    document.documentElement.dataset.themeChoice = next;
    localStorage.setItem(THEME_KEY, next);
  }
});

const archiveSearchCatalogs = new Map();
const ARCHIVE_SEARCH_LIMIT = 80;

function archiveSearchText(item) {
  const entityNames = [item.subjects, item.locations, item.topics, item.events, item.plans]
    .flatMap((rows) => (Array.isArray(rows) ? rows : []))
    .map((row) => row.name || "");
  return [
    item.title, item.ai_summary, item.published_date, item.page_name,
    item.page_number, ...entityNames,
  ].filter(Boolean).join("\n").toLocaleLowerCase("zh-CN");
}

function archiveDateLabel(value) {
  const [year, month, day] = value.split("-").map(Number);
  return `${year}年${month}月${day}日`;
}

function archiveWeekday(value) {
  const [year, month, day] = value.split("-").map(Number);
  return ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][
    new Date(Date.UTC(year, month - 1, day)).getUTCDay()
  ];
}

function makeArchiveSearchCard(item) {
  const article = document.createElement("article");
  article.className = "story-card";
  article.dataset.searchCard = "";

  const scope = document.createElement("span");
  scope.className = `scope-badge scope-${item.scope}`;
  scope.textContent = {national: "N", hainan: "H", domestic: "D", mixed: "M", foreign: "F"}[item.scope] || "–";
  const scopeLabel = {
    hainan: "H · 海南本地", domestic: "D · 国内关联", mixed: "M · 海南开放",
    national: "N · 全国", foreign: "F · 全球",
  }[item.scope] || "尚未分类";
  scope.title = scopeLabel;
  scope.setAttribute("aria-label", scopeLabel);

  const link = document.createElement("a");
  link.className = "story-copy";
  link.href = item.detail_path;
  const title = document.createElement("h3");
  title.textContent = item.title;
  const summary = document.createElement("p");
  summary.textContent = item.ai_summary || "这篇历史报道尚待重新生成结构化摘要。";
  link.append(title, summary);

  const button = document.createElement("button");
  button.type = "button";
  button.className = "bookmark-button";
  button.dataset.starId = item.item_id;
  button.setAttribute("aria-label", `收藏 ${item.title}`);
  button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h12v17l-6-4-6 4z"/></svg>';
  article.append(scope, link, button);
  return article;
}

function renderArchiveSearchResults(target, items) {
  const byDate = new Map();
  items.forEach((item) => {
    if (!byDate.has(item.published_date)) byDate.set(item.published_date, []);
    byDate.get(item.published_date).push(item);
  });
  const groups = [...byDate.entries()].map(([date, rows]) => {
    const section = document.createElement("section");
    section.className = "date-group";
    const header = document.createElement("header");
    const heading = document.createElement("h2");
    heading.textContent = archiveDateLabel(date);
    const meta = document.createElement("span");
    meta.textContent = `${archiveWeekday(date)} · ${rows.length} 条`;
    header.append(heading, meta);
    const list = document.createElement("div");
    list.className = "story-list";
    list.append(...rows.map(makeArchiveSearchCard));
    section.append(header, list);
    return section;
  });
  target.replaceChildren(...groups);
  syncStarButtons();
}

document.querySelectorAll("[data-search-input]").forEach((input) => {
  let timer = 0;
  let searchGeneration = 0;
  input.addEventListener("input", () => {
    window.clearTimeout(timer);
    const generation = ++searchGeneration;
    timer = window.setTimeout(async () => {
      const query = input.value.trim().toLocaleLowerCase("zh-CN");
      const main = input.closest("main");
      const archiveDefault = main.querySelector("[data-archive-default]");
      const archiveResults = main.querySelector("[data-archive-search-results]");
      const empty = main.querySelector("[data-search-empty]");
      const note = main.querySelector("[data-archive-search-note]");

      if (archiveDefault && archiveResults) {
        archiveDefault.hidden = query !== "";
        archiveResults.hidden = query === "";
      }
      if (query === "") {
        if (archiveResults?.dataset.searchSource) archiveResults.replaceChildren();
        if (empty) empty.hidden = true;
        if (note) note.hidden = true;
        return;
      }

      if (archiveResults?.dataset.searchSource) {
        const source = archiveResults.dataset.searchSource;
        try {
          if (!archiveSearchCatalogs.has(source)) {
            archiveSearchCatalogs.set(source, fetch(source).then((response) => {
              if (!response.ok) throw new Error(`search index ${response.status}`);
              return response.json();
            }));
          }
          const catalog = await archiveSearchCatalogs.get(source);
          if (generation !== searchGeneration) return;
          const matches = (catalog.items || [])
            .filter((item) => archiveSearchText(item).includes(query))
            .sort((a, b) => b.published_date.localeCompare(a.published_date)
              || (a.page_sequence || 0) - (b.page_sequence || 0));
          const visible = matches.slice(0, ARCHIVE_SEARCH_LIMIT);
          renderArchiveSearchResults(archiveResults, visible);
          if (empty) empty.hidden = matches.length > 0;
          if (note) {
            note.hidden = matches.length === 0;
            note.textContent = matches.length > ARCHIVE_SEARCH_LIMIT
              ? `找到 ${matches.length} 条，当前显示前 ${ARCHIVE_SEARCH_LIMIT} 条`
              : `找到 ${matches.length} 条`;
          }
        } catch (_) {
          if (generation !== searchGeneration) return;
          archiveSearchCatalogs.delete(source);
          archiveResults.replaceChildren();
          if (empty) empty.hidden = true;
          if (note) {
            note.hidden = false;
            note.textContent = "搜索索引暂时无法加载";
          }
        }
        return;
      }

      const cards = [...main.querySelectorAll("[data-search-card]")];
      cards.forEach((card) => {
        card.hidden = !card.dataset.searchText.toLocaleLowerCase("zh-CN").includes(query);
      });
      main.querySelectorAll(".date-group, .logical-section").forEach((group) => {
        group.hidden = !group.querySelector("[data-search-card]:not([hidden])");
      });
      if (empty) empty.hidden = cards.some((card) => !card.hidden);
    }, 140);
  });
});

function makeStarredCard(item) {
  const article = document.createElement("article");
  article.className = "story-card";
  const scope = document.createElement("span");
  scope.className = `scope-badge scope-${item.scope}`;
  scope.textContent = {national: "N", hainan: "H", domestic: "D", mixed: "M", foreign: "F"}[item.scope] || "–";
  const scopeLabel = {
    hainan: "H · 海南本地", domestic: "D · 国内关联", mixed: "M · 海南开放",
    national: "N · 全国", foreign: "F · 全球",
  }[item.scope] || "尚未分类";
  scope.title = scopeLabel;
  scope.setAttribute("aria-label", scopeLabel);
  const link = document.createElement("a");
  link.className = "story-copy";
  link.href = item.detail_path;
  const title = document.createElement("h3");
  title.textContent = item.title;
  const summary = document.createElement("p");
  summary.textContent = item.ai_summary || "这篇历史报道尚待重新生成结构化摘要。";
  link.append(title, summary);
  const button = document.createElement("button");
  button.type = "button";
  button.className = "bookmark-button";
  button.dataset.starId = item.item_id;
  button.setAttribute("aria-label", `取消收藏 ${item.title}`);
  button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h12v17l-6-4-6 4z"/></svg>';
  article.append(scope, link, button);
  return article;
}

function renderStarred() {
  const target = document.querySelector("[data-starred-list]");
  const source = document.getElementById("starred-catalog");
  if (!target || !source) return;
  let catalog = [];
  try { catalog = JSON.parse(source.textContent); } catch (_) { catalog = []; }
  const stars = new Set(readStars());
  const selected = catalog.filter((item) => stars.has(item.item_id));
  target.replaceChildren(...selected.map(makeStarredCard));
  const empty = document.querySelector("[data-starred-empty]");
  if (empty) empty.hidden = selected.length > 0;
}

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

syncStarButtons();
renderStarred();

window.addEventListener("hashchange", () => activateSubject(subjectIdFromHash()));
activateSubject(subjectIdFromHash());

const articleContext = document.querySelector(".article-context");
if (articleContext) {
  const narrowViewport = matchMedia("(max-width: 760px)");
  const syncArticleContext = () => {
    articleContext.toggleAttribute("open", !narrowViewport.matches);
  };
  narrowViewport.addEventListener("change", syncArticleContext);
  syncArticleContext();
}

const backToTop = document.querySelector("[data-back-to-top]");
if (backToTop) {
  const syncBackToTop = () => {
    backToTop.hidden = window.scrollY < 360;
  };
  window.addEventListener("scroll", syncBackToTop, { passive: true });
  syncBackToTop();
}
