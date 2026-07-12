document.documentElement.classList.add("js-ready");

const THEME_KEY = "hn-hot-theme";
const STAR_KEY = "hn-hot-starred";
const themeMedia = matchMedia("(prefers-color-scheme: dark)");

function storedTheme() {
  const value = localStorage.getItem(THEME_KEY);
  return value === "light" || value === "dark" ? value : null;
}

function applyTheme(choice) {
  const resolved = choice || (themeMedia.matches ? "dark" : "light");
  document.documentElement.dataset.themeChoice = choice || "system";
  document.documentElement.dataset.theme = resolved;
  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.setAttribute("aria-checked", String(resolved === "light"));
  });
}

applyTheme(storedTheme());

document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
  button.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
  });
});

themeMedia.addEventListener("change", () => {
  if (!storedTheme()) applyTheme(null);
});

document.querySelectorAll("[data-search-input]").forEach((input) => {
  input.addEventListener("input", () => {
    const query = input.value.trim().toLocaleLowerCase("zh-CN");
    const scope = input.closest("[data-search-scope]");
    scope.querySelectorAll("[data-search-title]").forEach((row) => {
      row.hidden = query !== "" && !row.dataset.searchTitle.toLocaleLowerCase("zh-CN").includes(query);
    });
    scope.querySelectorAll("[data-search-group]").forEach((group) => {
      group.hidden = !group.querySelector("[data-search-title]:not([hidden])");
    });
    const empty = scope.querySelector("[data-search-empty]");
    if (empty) empty.hidden = Boolean(scope.querySelector("[data-search-title]:not([hidden])"));
  });
});

document.querySelectorAll(".nav-toggle").forEach((button) => {
  button.addEventListener("click", () => {
    const expanded = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", String(!expanded));
    button.closest(".primary-nav").classList.toggle("nav-open", !expanded);
  });
});

function readStars() {
  try {
    const value = JSON.parse(localStorage.getItem(STAR_KEY) || "[]");
    return Array.isArray(value) ? value.filter((id) => typeof id === "string") : [];
  } catch (_) {
    return [];
  }
}

function writeStars(ids) {
  localStorage.setItem(STAR_KEY, JSON.stringify(ids));
}

function syncStarButtons() {
  const saved = new Set(readStars());
  document.querySelectorAll("[data-star-id]").forEach((button) => {
    const active = saved.has(button.dataset.starId);
    button.classList.toggle("is-starred", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-star-id]");
  if (!button) return;
  const saved = new Set(readStars());
  if (saved.has(button.dataset.starId)) saved.delete(button.dataset.starId);
  else saved.add(button.dataset.starId);
  writeStars([...saved]);
  syncStarButtons();
});

function bookmarkButton(item) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "bookmark-button";
  button.dataset.starId = item.item_id;
  button.setAttribute("aria-label", `收藏 ${item.title}`);
  button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.75A1.75 1.75 0 0 1 7.75 2h8.5A1.75 1.75 0 0 1 18 3.75v17l-6-3.75-6 3.75z"/></svg>';
  return button;
}

function selectedStory(item) {
  const article = document.createElement("article");
  article.className = "selected-story";
  article.dataset.selectedId = item.item_id;
  article.dataset.searchText = [item.title, item.ai_summary, item.recommendation_reason].join(" ");
  const link = document.createElement("a");
  link.className = "story-main";
  link.href = item.detail_path;
  const title = document.createElement("strong");
  title.className = "story-title";
  title.textContent = item.title;
  const summary = document.createElement("p");
  summary.className = "story-summary";
  summary.textContent = item.ai_summary || "";
  const reason = document.createElement("p");
  reason.className = "story-reason";
  const label = document.createElement("span");
  label.textContent = "为什么值得读";
  reason.append(label, item.recommendation_reason || "");
  link.append(title, summary, reason);
  article.append(link, bookmarkButton(item));
  return article;
}

function dateHeading(value, count) {
  const parts = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
  const weekdays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  const heading = document.createElement("h2");
  const dateLabel = document.createElement("strong");
  dateLabel.className = "current-date";
  dateLabel.textContent = `${parts[1]}月${parts[2]}日`;
  const meta = document.createElement("span");
  meta.className = "current-date-meta";
  meta.textContent = `${weekdays[parsed.getUTCDay()]} · ${count} 条`;
  heading.append(dateLabel, meta);
  return heading;
}

function renderSelectedDate(payload, activeCategory = "全部") {
  const items = payload.items.filter((item) => activeCategory === "全部" || item.category === activeCategory);
  const section = document.createElement("section");
  section.className = "date-group";
  section.dataset.feedDate = payload.date;
  section.append(dateHeading(payload.date, items.length));
  const list = document.createElement("div");
  list.className = "story-list";
  items.forEach((item) => list.append(selectedStory(item)));
  section.append(list);
  return section;
}

const selectedFeedState = {
  dates: [],
  paths: new Map(),
  payloads: new Map(),
  loaded: new Set(),
  failed: null,
  loading: false,
};

async function fetchSelectedDate(date) {
  if (selectedFeedState.payloads.has(date)) return selectedFeedState.payloads.get(date);
  const response = await fetch(selectedFeedState.paths.get(date));
  if (!response.ok) throw new Error(`feed ${date} returned ${response.status}`);
  const payload = await response.json();
  if (payload.date !== date || !Array.isArray(payload.items)) throw new Error(`feed ${date} is invalid`);
  selectedFeedState.payloads.set(date, payload);
  return payload;
}

function loaderButton(text, date) {
  const button = document.createElement("button");
  button.type = "button";
  button.dataset.loadMore = date;
  button.textContent = text;
  return button;
}

function nextUnloadedDate() {
  return selectedFeedState.dates.find((date) => !selectedFeedState.loaded.has(date));
}

async function loadSelectedDate(date) {
  if (!date || selectedFeedState.loading || selectedFeedState.loaded.has(date)) return;
  const feed = document.querySelector("[data-selected-feed]");
  const loader = document.querySelector("[data-feed-loader]");
  const activeCategory = document.querySelector("[data-selected-category]")?.dataset.selectedCategory || "全部";
  selectedFeedState.loading = true;
  loader.textContent = "正在加载…";
  try {
    const payload = await fetchSelectedDate(date);
    feed.append(renderSelectedDate(payload, activeCategory));
    selectedFeedState.loaded.add(date);
    selectedFeedState.failed = null;
    loader.replaceChildren();
    const next = nextUnloadedDate();
    if (!next) return;
    if (!("IntersectionObserver" in window)) loader.append(loaderButton("加载更多", next));
  } catch (_) {
    selectedFeedState.failed = date;
    loader.replaceChildren(loaderButton("加载失败，重试", date));
  } finally {
    selectedFeedState.loading = false;
    syncStarButtons();
  }
}

function restoreProgressiveFeed(feed, activeCategory) {
  feed.replaceChildren();
  selectedFeedState.loaded.forEach((date) => {
    const payload = selectedFeedState.payloads.get(date);
    if (payload) feed.append(renderSelectedDate(payload, activeCategory));
  });
}

async function runSelectedSearch(query) {
  const normalized = query.trim().toLocaleLowerCase("zh-CN");
  const feed = document.querySelector("[data-selected-feed]");
  const empty = document.querySelector("[data-search-empty]");
  const activeCategory = document.querySelector("[data-selected-category]")?.dataset.selectedCategory || "全部";
  if (!normalized) {
    restoreProgressiveFeed(feed, activeCategory);
    empty.hidden = true;
    return;
  }
  const payloads = await Promise.all(selectedFeedState.dates.map(fetchSelectedDate));
  feed.replaceChildren();
  payloads.forEach((payload) => {
    const items = payload.items.filter((item) => {
      if (activeCategory !== "全部" && item.category !== activeCategory) return false;
      return [item.title, item.ai_summary, item.recommendation_reason]
        .join(" ").toLocaleLowerCase("zh-CN").includes(normalized);
    });
    if (items.length) feed.append(renderSelectedDate({...payload, items}, activeCategory));
  });
  empty.hidden = Boolean(feed.children.length);
  syncStarButtons();
}

function initSelectedFeed() {
  const source = document.querySelector("[data-selected-feed-manifest]");
  if (!source) return;
  let manifest;
  try { manifest = JSON.parse(source.textContent); } catch (_) { return; }
  selectedFeedState.dates = Array.isArray(manifest.dates) ? manifest.dates : [];
  selectedFeedState.dates.forEach((date, index) => selectedFeedState.paths.set(date, manifest.feeds[index]));
  document.querySelectorAll("[data-feed-date]").forEach((section) => {
    selectedFeedState.loaded.add(section.dataset.feedDate);
  });
  const loader = document.querySelector("[data-feed-loader]");
  const next = nextUnloadedDate();
  if (next && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) loadSelectedDate(nextUnloadedDate());
    }, {rootMargin: "500px 0px"});
    observer.observe(loader);
  } else if (next) {
    loader.append(loaderButton("加载更多", next));
  }
  document.querySelector("[data-selected-search]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    runSelectedSearch(event.currentTarget.querySelector("input").value).catch(() => {
      loader.replaceChildren(loaderButton("加载失败，重试", selectedFeedState.failed || nextUnloadedDate()));
    });
  });
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-load-more]");
  if (button) loadSelectedDate(button.dataset.loadMore);
});

function renderStarredPage() {
  const target = document.querySelector("[data-starred-list]");
  const source = document.getElementById("starred-catalog");
  if (!target || !source) return;
  let catalog = [];
  try { catalog = JSON.parse(source.textContent); } catch (_) { catalog = []; }
  const saved = new Set(readStars());
  const selected = catalog.filter((item) => saved.has(item.item_id));
  target.replaceChildren();
  selected.forEach((item) => target.append(selectedStory(item)));
  const empty = document.querySelector("[data-starred-empty]");
  if (empty) empty.hidden = selected.length > 0;
}

syncStarButtons();
initSelectedFeed();
renderStarredPage();
