// Small progressive enhancements. The site works without this file;
// it only adds confirmations and live totals.

// Ask before destructive actions.
//   <form data-confirm="Delete this line?"> ... </form>
//   <button data-confirm="Clear your slip?" formaction="..."> ... </button>
document.addEventListener('submit', function (e) {
  var msg = (e.submitter && e.submitter.dataset.confirm) || e.target.dataset.confirm;
  if (msg && !window.confirm(msg)) {
    e.preventDefault();
  }
});

// Live payout preview:
//   <input data-payout-mult="3.5" data-payout-target="some-id">
// writes (value x multiplier) into the element with that id.
document.addEventListener('input', function (e) {
  var input = e.target;
  if (!input.dataset || !input.dataset.payoutMult) return;
  var out = document.getElementById(input.dataset.payoutTarget);
  if (!out) return;
  var total = parseFloat(input.value) * parseFloat(input.dataset.payoutMult);
  out.textContent = isFinite(total) ? total.toFixed(2) : '0.00';
});

// Dark mode toggle
const themeToggle = document.getElementById("theme-toggle");
const html = document.documentElement;

// Load saved theme preference
let savedTheme = localStorage.getItem("lineup-theme") || "light";

html.setAttribute("data-bs-theme", savedTheme);

function updateThemeButton() {
    if (!themeToggle) return;

    if (html.getAttribute("data-bs-theme") === "dark") {
        themeToggle.textContent = "☀ Light mode";
        themeToggle.setAttribute("aria-label", "Switch to light mode");
    } else {
        themeToggle.textContent = "☾ Dark mode";
        themeToggle.setAttribute("aria-label", "Switch to dark mode");
    }
}

updateThemeButton();

// Toggle theme when clicked
if (themeToggle) {
    themeToggle.addEventListener("click", function () {
        const currentTheme = html.getAttribute("data-bs-theme");

        const newTheme = currentTheme === "dark" ? "light" : "dark";

        html.setAttribute("data-bs-theme", newTheme);

        localStorage.setItem("lineup-theme", newTheme);

        updateThemeButton();
    });
}