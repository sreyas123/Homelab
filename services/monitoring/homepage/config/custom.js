// Start with the Background group collapsed (tap its heading to open)
(function () {
  var done = false;
  function run() {
    if (done) return;
    var groups = document.querySelectorAll('.services-group');
    groups.forEach(function (g) {
      var t = g.querySelector('h2, button, [class*=group-name]');
      if (t && /^\s*Background\s*$/.test(t.textContent) && g.querySelector('.services-list')) {
        (t.closest('button') || t).click();
        done = true;
      }
    });
  }
  new MutationObserver(run).observe(document.documentElement, { childList: true, subtree: true });
  setTimeout(run, 1500);
})();
