/**
 * MATIKA front-end: theme, schedule filter persistence.
 */
(function () {
  document.documentElement.classList.add("matika-js");

  var STORAGE_THEME = "matika-theme";

  function getTheme() {
    return document.documentElement.dataset.matikaTheme === "dark" ? "dark" : "light";
  }

  function applyTheme(theme) {
    if (theme !== "light" && theme !== "dark") return;
    document.documentElement.dataset.matikaTheme = theme;
    document.documentElement.setAttribute("data-bs-theme", theme);
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(STORAGE_THEME, theme);
    } catch (e) {}
    var btn = document.getElementById("matika-theme-toggle");
    if (btn) {
      btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    }
    try {
      window.dispatchEvent(new CustomEvent("matika-theme-change", { detail: { theme: theme } }));
    } catch (e) {}
  }

  function toggleTheme() {
    applyTheme(getTheme() === "dark" ? "light" : "dark");
  }

  document.addEventListener("DOMContentLoaded", function () {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/static/sw.js").catch(function () {});
    }
    var themeBtn = document.getElementById("matika-theme-toggle");
    if (themeBtn) {
      themeBtn.setAttribute("aria-pressed", getTheme() === "dark" ? "true" : "false");
      themeBtn.addEventListener("click", toggleTheme);
    }

    /* Persist admin schedule filters (GET form on my_schedule). */
    var scheduleForm = document.querySelector("form.matika-schedule-filters");
    if (scheduleForm) {
      var key = "matika-schedule-filters";
      try {
        var raw = sessionStorage.getItem(key);
        if (raw && !window.location.search) {
          var params = new URLSearchParams(raw);
          if (params.toString()) {
            window.location.replace(window.location.pathname + "?" + params.toString());
            return;
          }
        }
      } catch (e) {}
      scheduleForm.addEventListener("change", function () {
        try {
          sessionStorage.setItem(key, new URLSearchParams(new FormData(scheduleForm)).toString());
        } catch (err) {}
      });
      scheduleForm.addEventListener("submit", function () {
        try {
          sessionStorage.setItem(key, new URLSearchParams(new FormData(scheduleForm)).toString());
        } catch (err) {}
      });
    }
  });

  /** Expose chart color helpers for inline templates (analytics). */
  window.matikaChartColors = function () {
    var s = getComputedStyle(document.documentElement);
    return {
      fill1: (s.getPropertyValue("--m-chart-1") || "rgba(227, 6, 19, 0.55)").trim(),
      border1: (s.getPropertyValue("--m-chart-1-border") || "rgba(227, 6, 19, 1)").trim(),
      fill2: (s.getPropertyValue("--m-chart-2") || "rgba(73, 80, 87, 0.45)").trim(),
      border2: (s.getPropertyValue("--m-chart-2-border") || "rgba(73, 80, 87, 1)").trim(),
      grid: getTheme() === "dark" ? "rgba(148,163,184,.12)" : "rgba(15,23,42,.06)",
    };
  };
})();
