document.documentElement.classList.add("js-ready");

const THEME_KEY = "hn-hot-theme";
const themeMedia = matchMedia("(prefers-color-scheme: dark)");

function applyTheme(choice) {
  const dark = choice === "dark" || (choice === "system" && themeMedia.matches);
  document.documentElement.dataset.themeChoice = choice;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

document.querySelectorAll("[data-theme-choice]").forEach((button) => {
  button.addEventListener("click", () => {
    localStorage.setItem(THEME_KEY, button.dataset.themeChoice);
    applyTheme(button.dataset.themeChoice);
  });
});

themeMedia.addEventListener("change", () => {
  const choice = localStorage.getItem(THEME_KEY) || "system";
  if (choice === "system") applyTheme(choice);
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

const STAR_KEY = "hn-hot-starred";

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

document.querySelectorAll("[data-star-id]").forEach((button) => {
  button.addEventListener("click", () => {
    const saved = new Set(readStars());
    if (saved.has(button.dataset.starId)) saved.delete(button.dataset.starId);
    else saved.add(button.dataset.starId);
    writeStars([...saved]);
    syncStarButtons();
  });
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
  selected.forEach((item) => {
    const article = document.createElement("article");
    article.className = "selected-row starred-row";
    const link = document.createElement("a");
    link.href = item.detail_path;
    const title = document.createElement("strong");
    title.textContent = item.title;
    const summary = document.createElement("p");
    summary.textContent = item.ai_summary || "";
    link.append(title, summary);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "bookmark-button is-starred";
    button.dataset.starId = item.item_id;
    button.setAttribute("aria-label", `取消收藏 ${item.title}`);
    button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.75A1.75 1.75 0 0 1 7.75 2h8.5A1.75 1.75 0 0 1 18 3.75v17l-6-3.75-6 3.75z"/></svg>';
    button.addEventListener("click", () => {
      writeStars(readStars().filter((id) => id !== item.item_id));
      renderStarredPage();
    });
    article.append(link, button);
    target.append(article);
  });
  const empty = document.querySelector("[data-starred-empty]");
  if (empty) empty.hidden = selected.length > 0;
}

syncStarButtons();
renderStarredPage();
