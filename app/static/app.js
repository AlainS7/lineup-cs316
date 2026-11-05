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

// Dark mode toggle. base.html applies the saved/OS theme before paint; this flips and saves it.
(function () {
  var btn = document.getElementById('theme-toggle');
  if (!btn) return;
  var root = document.documentElement;
  function sync() { btn.setAttribute('aria-pressed', root.getAttribute('data-bs-theme') === 'dark' ? 'true' : 'false'); }
  sync();
  btn.addEventListener('click', function () {
    var next = root.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-bs-theme', next);
    try { localStorage.setItem('lu-theme', next); } catch (e) {}
    sync();
  });
})();
