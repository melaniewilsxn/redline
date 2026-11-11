try {
  const storedTheme = window.localStorage.getItem("redline-theme");
  if (storedTheme === "light" || storedTheme === "dark") {
    document.documentElement.dataset.theme = storedTheme;
  }
} catch {
  /* A blocked store leaves the light theme in place. */
}
