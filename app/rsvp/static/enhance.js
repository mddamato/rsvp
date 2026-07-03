// Progressive enhancement only. The app works fully without this file.
// Double-submit protection: disables any button marked data-once on
// form submit, which prevents duplicate rows on slow mobile connections.
document.addEventListener('submit', function (e) {
  var btn = e.target.querySelector('button[data-once]');
  if (btn) {
    btn.disabled = true;
    btn.dataset.label = btn.textContent;
    btn.textContent = 'Sending\u2026';
  }
});
