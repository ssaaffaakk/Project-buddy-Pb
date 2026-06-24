(function () {
  'use strict';

  // ── XSS-safe escaper ─────────────────────────────────────────────────────────
  window._esc = function (s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
  };

  // ── Viewport helpers ──────────────────────────────────────────────────────────
  function setTouchClass() {
    var coarse = window.matchMedia('(hover: none), (pointer: coarse)').matches;
    document.documentElement.classList.toggle('is-touch', coarse);
  }

  function setViewportUnits() {
    document.documentElement.style.setProperty('--vh', window.innerHeight * 0.01 + 'px');
  }

  // ── Sidebar ───────────────────────────────────────────────────────────────────
  window.pbSidebar = function (open) {
    var sidebar = document.querySelector('.sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    if (!sidebar || !overlay) return;
    sidebar.classList.toggle('open', open);
    overlay.classList.toggle('open', open);
    document.body.classList.toggle('sidebar-open', open);
  };

  // ── CSRF helper + fetch patch ─────────────────────────────────────────────────
  window._getCsrf = function () {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  };

  (function () {
    var _orig = window.fetch;
    window.fetch = function (url, opts) {
      opts = opts || {};
      if (opts.method && opts.method.toUpperCase() === 'POST') {
        opts.headers = Object.assign({ 'X-CSRFToken': window._getCsrf() }, opts.headers || {});
      }
      return _orig.call(this, url, opts);
    };
  })();

  // ── Toast ─────────────────────────────────────────────────────────────────────
  var _ICONS  = { success: '✦', error: '!', warning: '⚠' };
  var _TITLES = { success: 'Done', error: 'Error', warning: 'Warning', info: 'Note' };

  window.showToast = function (msg, type, dur) {
    type = type || 'info'; dur = dur || 4200;
    var c = document.getElementById('toast-container');
    if (!c) return;
    var t = document.createElement('div');
    t.className = 'toast ' + type;
    t.innerHTML =
      '<div class="toast-icon">' + (_ICONS[type] || '') + '</div>' +
      '<div class="toast-body">' +
        '<div class="toast-title">' + (_TITLES[type] || type) + '</div>' +
        '<div class="toast-msg">' + window._esc(String(msg)) + '</div>' +
      '</div>' +
      '<button class="toast-close" onclick="window.dismissToast(this.parentElement)">\xd7</button>' +
      '<div class="toast-progress"></div>';
    c.appendChild(t);
    setTimeout(function () { window.dismissToast(t); }, dur);
  };

  window.dismissToast = function (t) {
    if (!t || t._d) return; t._d = true;
    t.style.animation = 'toastOut 0.28s ease forwards';
    setTimeout(function () { if (t.parentElement) t.parentElement.removeChild(t); }, 280);
  };

  // ── Notifications ─────────────────────────────────────────────────────────────
  window.toggleNotifs = function () {
    var p = document.getElementById('notif-panel');
    if (!p) return;
    var isOpen = p.style.display !== '' && p.style.display !== 'none';
    p.style.display = isOpen ? 'none' : 'block';
    if (!isOpen) window.fetchNotifs();
  };

  window.fetchNotifs = async function () {
    try {
      var r = await fetch('/notifications/unread');
      if (!r.ok) return;
      var d = await r.json();
      var badge = document.getElementById('notif-badge');
      var list  = document.getElementById('notif-list');
      if (badge) {
        if (d.count > 0) { badge.textContent = d.count; badge.style.display = 'inline'; }
        else { badge.style.display = 'none'; }
      }
      if (!list) return;
      if (!d.notifications || d.notifications.length === 0) {
        list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);font-size:0.8rem;">No new notifications</div>';
        return;
      }
      list.innerHTML = d.notifications.map(function (n) {
        return '<a href="' + window._esc(n.link || '#') + '" onclick="window.readNotif(' + n.id + ')" ' +
          'style="display:block;padding:12px 14px;border-bottom:1px solid var(--border);text-decoration:none;color:var(--text);transition:background 0.15s;" ' +
          'onmouseover="this.style.background=\'rgba(255,255,255,0.04)\'" onmouseout="this.style.background=\'none\'">' +
          '<div style="font-size:0.82rem;line-height:1.4;">' + window._esc(n.message) + '</div>' +
          '<div style="font-size:0.7rem;color:var(--muted);margin-top:4px;font-family:\'DM Mono\',monospace;">' + window._esc(n.time_ago) + '</div>' +
          '</a>';
      }).join('');
    } catch (e) {}
  };

  window.readNotif = async function (id) {
    try { await fetch('/notifications/' + id + '/read', { method: 'POST' }); } catch (e) {}
    window.fetchNotifs();
  };

  window.markAllRead = async function () {
    try { await fetch('/notifications/read-all', { method: 'POST' }); } catch (e) {}
    window.fetchNotifs();
  };

  // ── Startup ───────────────────────────────────────────────────────────────────
  setTouchClass();
  setViewportUnits();
  window.addEventListener('resize', setTouchClass, { passive: true });
  window.addEventListener('resize', setViewportUnits, { passive: true });
  window.addEventListener('orientationchange', setViewportUnits, { passive: true });

  document.addEventListener('DOMContentLoaded', function () {
    // Theme toggle button label
    var themeBtn = document.getElementById('themeToggle');
    if (themeBtn) {
      themeBtn.textContent = document.documentElement.classList.contains('light-mode') ? 'Dark' : 'Light';
    }

    // Cursor glow
    var glow = document.getElementById('cursor-glow');
    if (glow) {
      if (document.documentElement.classList.contains('is-touch')) {
        glow.style.display = 'none';
      } else {
        document.addEventListener('mousemove', function (e) {
          glow.style.left = e.clientX + 'px';
          glow.style.top  = e.clientY + 'px';
        });
      }
    }

    // Flask flash messages
    var flashEl = document.getElementById('flask-messages');
    if (flashEl) {
      try {
        JSON.parse(flashEl.getAttribute('data-messages')).forEach(function (m) {
          window.showToast(m[1], m[0] === 'error' ? 'error' : m[0] === 'warning' ? 'warning' : 'success');
        });
      } catch (e) {}
    }

    // Notification polling + outside-click close
    if (document.getElementById('notif-btn')) {
      window.fetchNotifs();
      setInterval(window.fetchNotifs, 30000);
      document.addEventListener('click', function (e) {
        var panel = document.getElementById('notif-panel');
        var btn   = document.getElementById('notif-btn');
        if (panel && btn && !panel.contains(e.target) && !btn.contains(e.target)) {
          panel.style.display = 'none';
        }
      });
    }

    // Keyboard: Escape closes sidebar
    if (!window.__pbKeysBound) {
      window.__pbKeysBound = true;
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') window.pbSidebar(false);
      });
    }

    // Mobile: close sidebar when nav item is tapped
    document.querySelectorAll('.sidebar .nav-item').forEach(function (l) {
      l.addEventListener('click', function () { window.pbSidebar(false); });
    });

    // Sliding nav pill
    var sb = document.querySelector('.sidebar');
    if (sb && !sb.querySelector('.nav-pill')) {
      var pill   = document.createElement('div');
      pill.className = 'nav-pill';
      sb.appendChild(pill);
      var items  = [].slice.call(sb.querySelectorAll('.nav-item'));
      var active = sb.querySelector('.nav-item.active');
      function movePill(el) {
        pill.style.height    = el.offsetHeight + 'px';
        pill.style.transform = 'translateY(' + el.offsetTop + 'px)';
        pill.style.opacity   = '1';
      }
      items.forEach(function (it) {
        it.addEventListener('mouseenter', function () { movePill(it); });
      });
      sb.addEventListener('mouseleave', function () {
        if (active) movePill(active); else pill.style.opacity = '0';
      });
      if (active) movePill(active);
    }
  });

})();
