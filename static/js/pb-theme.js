(function () {
  'use strict';

  function setTouchClass() {
    var coarse = window.matchMedia('(hover: none), (pointer: coarse)').matches;
    document.documentElement.classList.toggle('is-touch', coarse);
  }

  function setViewportUnits() {
    document.documentElement.style.setProperty('--vh', window.innerHeight * 0.01 + 'px');
  }

  window.pbSidebar = window.pbSidebar || function (open) {
    var sidebar = document.querySelector('.sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    if (!sidebar || !overlay) return;
    sidebar.classList.toggle('open', open);
    overlay.classList.toggle('open', open);
    document.body.classList.toggle('sidebar-open', open);
  };

  setTouchClass();
  setViewportUnits();
  window.addEventListener('resize', setTouchClass, { passive: true });
  window.addEventListener('resize', setViewportUnits, { passive: true });
  window.addEventListener('orientationchange', setViewportUnits, { passive: true });

  document.addEventListener('DOMContentLoaded', function () {
    var glow = document.getElementById('cursor-glow');
    if (glow && document.documentElement.classList.contains('is-touch')) {
      glow.style.display = 'none';
    }

    if (!window.__pbSidebarBound) {
      window.__pbSidebarBound = true;
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') window.pbSidebar(false);
      });
    }
  });
})();
