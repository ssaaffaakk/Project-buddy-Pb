/* ProjectBuddy Web Push opt-in.
 *
 * Exposes window.pbEnablePush() (wired to the sidebar "Enable push" button).
 * On load: if the user already granted permission, silently make sure a live
 * subscription is stored server-side; otherwise reveal the opt-in button.
 */
(function () {
  'use strict';

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function csrf() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  function supported() {
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  }

  async function getConfig() {
    const res = await fetch('/push/public-key');
    if (!res.ok) return { enabled: false, publicKey: '' };
    return res.json();
  }

  async function saveSubscription(sub) {
    await fetch('/push/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(sub),
    });
  }

  async function subscribe(publicKey) {
    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });
    }
    await saveSubscription(sub.toJSON());
    return sub;
  }

  function showEnableButton(show) {
    const btn = document.getElementById('push-enable-btn');
    if (btn) btn.style.display = show ? 'flex' : 'none';
  }

  // Public: called by the "Enable push" button.
  window.pbEnablePush = async function () {
    if (!supported()) {
      alert('Push notifications are not supported on this browser.');
      return;
    }
    const cfg = await getConfig();
    if (!cfg.enabled || !cfg.publicKey) {
      alert('Push notifications are not configured on the server yet.');
      return;
    }
    const perm = await Notification.requestPermission();
    if (perm !== 'granted') return;
    try {
      await subscribe(cfg.publicKey);
      showEnableButton(false);
    } catch (e) {
      console.warn('push subscribe failed:', e);
    }
  };

  // On load: keep an existing grant in sync, or offer the opt-in.
  window.addEventListener('load', async function () {
    if (!supported()) return;
    const cfg = await getConfig();
    if (!cfg.enabled || !cfg.publicKey) return;

    if (Notification.permission === 'granted') {
      try { await subscribe(cfg.publicKey); } catch (e) { /* ignore */ }
      showEnableButton(false);
    } else if (Notification.permission === 'default') {
      showEnableButton(true);   // let the user opt in on their own click
    }
  });
})();
