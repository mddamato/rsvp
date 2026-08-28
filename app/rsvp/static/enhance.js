// Progressive enhancement only. The app works fully without this file.
// Double-submit protection: disables any button marked data-once on
// form submit, which prevents duplicate rows on slow mobile connections.
// Checked via e.submitter first since the dashboard's bulk-action
// buttons live outside the <form> they submit (associated via
// form="bulk-form"), so they aren't found by querySelector on it.
document.addEventListener('submit', function (e) {
  var btn = (e.submitter && e.submitter.hasAttribute('data-once'))
    ? e.submitter
    : e.target.querySelector('button[data-once]');
  if (btn) {
    btn.disabled = true;
    btn.dataset.label = btn.textContent;
    btn.textContent = 'Sending\u2026';
  }
});

// Admin dashboard "select all" checkbox: toggles every per-row
// checkbox. Purely a convenience -- without JS, guests can still be
// checked one at a time and every bulk action still works.
(function () {
  var selectAll = document.getElementById('select-all');
  if (!selectAll) return;
  var boxes = document.querySelectorAll('input[name="invitee_ids"]');
  selectAll.addEventListener('change', function () {
    boxes.forEach(function (b) { b.checked = selectAll.checked; });
  });
})();

// Progressive enhancement for the "Add guest" rows: collapse to
// (filled rows + 1) on load, reveal one more per click. The app
// works fully without this -- every row is rendered and usable by
// default; this only tidies the initial view.
document.querySelectorAll('.guest-rows').forEach(function (container) {
  var rows = container.querySelectorAll('.guest-row');
  var addBtn = container.querySelector('.add-guest');
  if (!rows.length || !addBtn) return;

  var visibleCount = 0;
  rows.forEach(function (row, i) {
    var input = row.querySelector('input[type=text]');
    if (input && input.value.trim()) visibleCount = i + 1;
  });
  visibleCount = Math.min(rows.length, Math.max(visibleCount + 1, 1));
  rows.forEach(function (row, i) { if (i >= visibleCount) row.hidden = true; });

  function refreshButton() {
    addBtn.hidden = !Array.prototype.some.call(rows, function (r) { return r.hidden; });
  }
  addBtn.addEventListener('click', function () {
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].hidden) { rows[i].hidden = false; break; }
    }
    refreshButton();
  });
  refreshButton();
});
