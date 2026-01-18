// Load theme from storage
document.addEventListener("DOMContentLoaded", function() {
    let theme = localStorage.getItem("theme") || "light";

    document.body.classList.add(theme + "-mode");
});

// Change theme
function setTheme(mode) {
    document.body.classList.remove("light-mode", "dark-mode");
    document.body.classList.add(mode + "-mode");
    localStorage.setItem("theme", mode);
}
function toggleTheme() {
    let current = localStorage.getItem("theme") || "light";
    let newTheme = current === "light" ? "dark" : "light";
    setTheme(newTheme);
}
