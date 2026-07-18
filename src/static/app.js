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

document.addEventListener("click", (event) => {
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

document.querySelectorAll("[data-search-input]").forEach((input) => {
  input.addEventListener("input", () => {
    const query = input.value.trim().toLocaleLowerCase("zh-CN");
    const main = input.closest("main");
    const cards = [...main.querySelectorAll("[data-search-card]")];
    cards.forEach((card) => {
      card.hidden = query !== "" && !card.dataset.searchText.toLocaleLowerCase("zh-CN").includes(query);
    });
    main.querySelectorAll(".date-group, .logical-section").forEach((group) => {
      group.hidden = !group.querySelector("[data-search-card]:not([hidden])");
    });
    const empty = main.querySelector("[data-search-empty]");
    if (empty) empty.hidden = cards.some((card) => !card.hidden);
  });
});

function makeStarredCard(item) {
  const article = document.createElement("article");
  article.className = "story-card";
  const scope = document.createElement("span");
  scope.className = `scope-badge scope-${item.scope}`;
  scope.textContent = {national: "N", hainan: "H", mixed: "M"}[item.scope] || "–";
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

syncStarButtons();
renderStarred();
