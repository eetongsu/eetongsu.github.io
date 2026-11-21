(() => {
  const section = document.getElementById('visitor-map');
  if (!section) return;

  const bands = new Map([['1–4', 'first'], ['5–19', 'low'], ['20–49', 'medium'], ['50+', 'high']]);
  const svgNamespace = 'http://www.w3.org/2000/svg';

  function element(name, className, text) {
    const node = document.createElement(name);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function svgElement(name, attrs) {
    const node = document.createElementNS(svgNamespace, name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  }

  async function readAsset(file) {
    const response = await fetch('/assets/' + file, { credentials: 'omit' });
    if (!response.ok) throw new Error('Map asset unavailable');
    return response.json();
  }

  async function renderMap() {
    const snapshot = await readAsset('visitor-countries.json');
    if (!snapshot || !/^\d{4}-\d{2}-\d{2}$/.test(snapshot.end_date)) return;
    const lastDay = new Date(snapshot.end_date + 'T12:00:00Z');
    if (!Number.isFinite(lastDay.valueOf()) || lastDay.toISOString().slice(0, 10) !== snapshot.end_date) return;
    const reported = Object.entries(snapshot.countries || {}).filter(
      ([code, band]) => /^[A-Z]{2}$/.test(code) && bands.has(band)
    );
    const { features } = await readAsset('visitor-geography.json');
    const bandByCode = new Map(reported);

    const names = new Intl.DisplayNames(['en'], { type: 'region' });
    const formatDate = new Intl.DateTimeFormat('en-US', {
      month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC'
    });
    const layout = element('div', 'visitor-layout');
    const figure = element('figure', 'visitor-figure');
    const map = svgElement('svg', {
      viewBox: '0 0 1000 495', role: 'group', 'aria-label': 'World map of active users by country or region'
    });
    const land = svgElement('g', {class: 'visitor-land'});
    const points = svgElement('g', {class: 'visitor-points'});
    const readout = element('figcaption', 'visitor-readout', reported.length
      ? 'Select a highlighted country or region.'
      : 'No country or region has been reported yet.');
    const clearReadout = () => { readout.textContent = 'Select a highlighted country or region.'; };
    let selected = null;

    function select(shape) {
      if (selected) selected.classList.remove('visitor-selected');
      selected = shape;
      if (selected) {
        selected.classList.add('visitor-selected');
        readout.textContent = selected.getAttribute('aria-label');
      } else clearReadout();
    }

    function bindRegion(shape, code, band) {
      const label = names.of(code) + ' · ' + band + ' active users';
      shape.setAttribute('class', 'visitor-region visitor-' + bands.get(band));
      shape.setAttribute('tabindex', '0');
      shape.setAttribute('role', 'button');
      shape.setAttribute('aria-label', label);
      shape.addEventListener('pointerenter', () => select(shape));
      shape.addEventListener('focus', () => select(shape));
      shape.addEventListener('click', () => select(shape));
      shape.addEventListener('keydown', event => {
        if (event.key === 'Escape') select(null);
        if (event.key === ' ' || event.key === 'Enter') {
          event.preventDefault();
          select(shape);
        }
      });
    }

    for (const [code, feature] of Object.entries(features)) {
      const shape = svgElement('path', { d: feature.d, 'fill-rule': 'evenodd', 'aria-hidden': 'true' });
      land.append(shape);
      const band = bandByCode.get(code);
      if (!band) continue;
      if (feature.point) {
        const [cx, cy] = feature.point;
        shape.setAttribute('class', 'visitor-' + bands.get(band));
        const dot = svgElement('circle', {cx, cy, r: 3});
        bindRegion(dot, code, band);
        points.append(dot);
      } else {
        shape.removeAttribute('aria-hidden');
        bindRegion(shape, code, band);
      }
    }
    map.append(land, points);
    figure.append(map, readout);

    const key = element('div', 'visitor-key');
    key.append(element('h3', '', 'Active users'));
    const legend = element('ul', 'visitor-legend');
    for (const [label, level] of bands) {
      const item = element('li');
      const swatch = element('span', 'visitor-swatch visitor-' + level);
      swatch.setAttribute('aria-hidden', 'true');
      item.append(swatch, document.createTextNode(label));
      legend.append(item);
    }
    const details = element('details', 'visitor-details');
    details.append(element('summary', '', 'Country and region list'));
    const list = element('ul', 'visitor-list');
    const labels = reported.map(([code, band]) => [names.of(code), band]);
    labels.sort(([a], [b]) => a.localeCompare(b, 'en'));
    for (const [name, band] of labels) {
      const item = element('li');
      item.append(element('span', '', name), element('span', '', band));
      list.append(item);
    }
    details.append(list);
    key.append(legend);
    if (reported.length) key.append(details);
    layout.append(figure, key);
    let period = 'All-time visits';
    if (snapshot.start_date) {
      const trackingStart = new Date(snapshot.start_date + 'T12:00:00Z');
      period = 'Since ' + formatDate.format(trackingStart) + ' · Updated ' + formatDate.format(lastDay);
    }
    section.append(element('p', 'visitor-period', period), layout);
    section.hidden = false;
  }

  // The homepage remains usable while the first report is pending or unavailable.
  renderMap().catch(() => {});
})();
