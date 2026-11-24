/* GA4 measurement defaults and the visitor's footer preference. */
(() => {
  if (location.origin !== 'https://eetongsu.github.io') return;

  async function configure() {
    const settings = document.querySelector('[data-analytics-settings]');
    if (!settings) return;

    const response = await fetch('/assets/analytics-config.json', {
      credentials: 'omit', redirect: 'error'
    });
    if (!response.ok) return;
    const { measurement_id: id } = await response.json();
    if (typeof id !== 'string' || !/^G-[A-Z0-9]+$/.test(id)) return;

    const key = 'tong-su.analytics-consent.v2';
    const legacyKey = 'tong-su.analytics-consent.v1';
    const disabled = 'ga-disable-' + id;
    const privacySignal = navigator.globalPrivacyControl === true || navigator.doNotTrack === '1';
    let tagStarted = false;

    function savedChoice() {
      try {
        const value = localStorage.getItem(key);
        if (value === 'allow' || value === 'decline') return value;
        return localStorage.getItem(legacyKey) === 'decline' ? 'decline' : null;
      } catch { return 'decline'; }
    }
    let choice = savedChoice();

    function measure() {
      window[disabled] = false;
      if (tagStarted) {
        if (choice === 'allow') window.gtag('consent', 'update', { analytics_storage: 'granted' });
        return;
      }
      tagStarted = true;
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () { window.dataLayer.push(arguments); };
      const noAds = {
        ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'
      };
      window.gtag('consent', 'default', {
        ...noAds, analytics_storage: choice === 'allow' ? 'granted' : 'denied'
      });
      if (choice !== 'allow') {
        window.gtag('consent', 'default', { region: ['US'], analytics_storage: 'granted' });
      }
      window.gtag('js', new Date());
      window.gtag('config', id, {
        allow_google_signals: false, allow_ad_personalization_signals: false,
        cookie_domain: location.hostname, cookie_prefix: 'tsresearch'
      });
      const tag = document.createElement('script');
      tag.async = true;
      tag.src = 'https://www.googletagmanager.com/gtag/js?id=' + id;
      document.head.append(tag);
    }

    function applyChoice() {
      if (!privacySignal && choice !== 'decline') {
        measure();
        return;
      }
      window[disabled] = true;
      try {
        for (const cookie of document.cookie.split(';')) {
          const name = cookie.trim().split('=')[0];
          if (name.startsWith('tsresearch')) {
            document.cookie = name + '=; Max-Age=0; Path=/; Domain=' + location.hostname + '; Secure';
          }
        }
      } catch { /* Cookies may be blocked. */ }
      if (tagStarted && savedChoice() === 'decline') location.reload();
    }

    const panel = document.createElement('aside');
    panel.className = 'analytics-choice';
    panel.setAttribute('aria-labelledby', 'analytics-heading');
    panel.id = 'analytics-choice';
    panel.hidden = true;
    panel.innerHTML = '<div class="wrap analytics-inner"><div>' +
      '<h2 id="analytics-heading" tabindex="-1">Visitor analytics</h2>' +
      '<p>This site uses Google Analytics to measure page views, PDF clicks and outgoing links. ' +
      'Analytics cookies are on by default in the US. Elsewhere, visits are measured without analytics cookies ' +
      'unless you allow them. The site owner can view aggregated visitor locations in Analytics. ' +
      '<a href="https://policies.google.com/technologies/partner-sites">How Google uses this data</a>.</p>' +
      '<p class="analytics-status"></p></div><div class="analytics-actions">' +
      '<button type="button" data-consent="allow">Allow analytics cookies</button>' +
      '<button type="button" data-consent="decline">Turn off analytics</button></div></div>';
    const status = panel.querySelector('.analytics-status');
    settings.setAttribute('aria-controls', panel.id);
    function display(open) {
      panel.hidden = !open;
      settings.setAttribute('aria-expanded', String(open));
      if (privacySignal) status.textContent = 'Analytics is off because your browser requests privacy.';
      else if (choice === 'decline') status.textContent = 'Analytics is off for this browser.';
      else if (choice === 'allow') status.textContent = 'Analytics cookies are enabled for this browser.';
      else status.textContent = 'This browser uses the regional default.';
      if (open) panel.querySelector('h2').focus();
    }

    settings.closest('footer').before(panel);
    settings.hidden = false;
    settings.addEventListener('click', () => display(panel.hidden));
    panel.querySelectorAll('[data-consent]').forEach(button => {
      if (privacySignal && button.dataset.consent === 'allow') button.disabled = true;
      button.addEventListener('click', () => {
        choice = button.dataset.consent;
        try { localStorage.setItem(key, choice); } catch { /* Keep choice for this page. */ }
        display(false);
        settings.focus();
        applyChoice();
      });
    });
    window.addEventListener('storage', event => {
      if (event.key !== key && event.key !== legacyKey && event.key !== null) return;
      const next = savedChoice();
      if (next === choice) return;
      choice = next;
      display(false);
      if (tagStarted && choice === null) location.reload();
      else applyChoice();
    });
    display(false);
    applyChoice();
  }

  // A missing configuration or a failed first-party request leaves collection off.
  configure().catch(() => {});
})();
