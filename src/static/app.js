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
