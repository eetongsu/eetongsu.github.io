/* Optional first-party consent controls for this site's GA4 stream. */
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

    const key = 'tong-su.analytics-consent.v1';
    const disabled = 'ga-disable-' + id;
    let tagStarted = false;
    let choice;
    try { choice = localStorage.getItem(key); } catch { /* Storage may be disabled. */ }

    function enable() {
      if (tagStarted) return;
      tagStarted = true;
      window[disabled] = false;
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () { window.dataLayer.push(arguments); };
      const noAds = {
        ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'
      };
      window.gtag('consent', 'default', { ...noAds, analytics_storage: 'denied' });
      window.gtag('consent', 'update', { ...noAds, analytics_storage: 'granted' });
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

    function disable() {
      window[disabled] = true;
      for (const cookie of document.cookie.split(';')) {
        const name = cookie.trim().split('=')[0];
        if (name.startsWith('tsresearch')) {
          document.cookie = name + '=; Max-Age=0; Path=/; Domain=' + location.hostname + '; Secure';
        }
      }
      // Drop the loaded tag and its event listeners immediately after withdrawal.
      if (tagStarted) location.reload();
    }

    const panel = document.createElement('aside');
    panel.className = 'analytics-choice';
    panel.setAttribute('aria-labelledby', 'analytics-heading');
    panel.id = 'analytics-choice';
    panel.hidden = true;
    panel.innerHTML = '<div class="wrap analytics-inner"><div>' +
      '<h2 id="analytics-heading" tabindex="-1">Optional visitor analytics</h2>' +
      '<p>Allow Google Analytics cookies to measure page visits, PDF link clicks and ' +
      'outbound links. The public map groups visitors by country or region over 90 days ' +
      'and shows areas with at least five active users. You can change your choice in the footer. ' +
      '<a href="https://policies.google.com/technologies/partner-sites">How Google uses this data</a>.</p>' +
      '<p class="analytics-status" hidden></p></div><div class="analytics-actions">' +
      '<button type="button" data-consent="allow">Allow analytics</button>' +
      '<button type="button" data-consent="decline">Decline analytics</button></div></div>';
    const status = panel.querySelector('.analytics-status');
    settings.setAttribute('aria-controls', panel.id);
    function display(moveFocus) {
      const undecided = choice !== 'allow' && choice !== 'decline';
      const open = undecided || moveFocus;
      panel.hidden = !open;
      settings.setAttribute('aria-expanded', String(open));
      status.hidden = undecided;
      status.textContent = choice === 'allow' ? 'Analytics is on.' : 'Analytics is off.';
      if (moveFocus) {
        settings.closest('footer').before(panel);
        panel.querySelector('h2').focus();
      }
    }

    document.querySelector('main').before(panel);
    settings.hidden = false;
    settings.addEventListener('click', () => display(true));
    panel.querySelectorAll('[data-consent]').forEach(button => {
      button.addEventListener('click', () => {
        const atFooter = panel.nextElementSibling === settings.closest('footer');
        choice = button.dataset.consent;
        try { localStorage.setItem(key, choice); } catch { /* Keep choice for this page. */ }
        display(false);
        if (choice === 'allow') enable(); else disable();
        if (atFooter) settings.focus();
      });
    });
    window.addEventListener('storage', event => {
      if (event.key !== key && event.key !== null) return;
      choice = event.newValue;
      display(false);
      if (choice === 'allow') enable(); else disable();
    });
    display(false);
    if (choice === 'allow') enable();
  }

  // A missing configuration or a failed first-party request leaves collection off.
  configure().catch(() => {});
})();
