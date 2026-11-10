try {
  const storedTheme = window.localStorage.getItem("redline-theme");
  if (storedTheme === "light" || storedTheme === "dark") {
    document.documentElement.dataset.theme = storedTheme;
  }
} catch {
  /* The system theme stays in place when storage is blocked. */
}
