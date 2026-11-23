(() => {
  const section = document.getElementById('visitor-map');
  if (!section) return;

  const radii = new Map([['1–4', 5], ['5–19', 8], ['20–49', 12], ['50+', 17]]);
  const names = new Intl.DisplayNames(['en'], {type: 'region'});

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function svg(tag, attributes) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    return node;
  }

  function projectedCenter(lat, lon, projection) {
    // Equal Earth, in the same viewBox coordinates as the Natural Earth outlines.
    const theta = Math.asin(Math.sqrt(3) / 2 * Math.sin(lat * Math.PI / 180));
    const t2 = theta ** 2;
    const t6 = t2 ** 3;
    const t8 = t6 * t2;
    const x = lon * Math.PI / 180 * 2 * Math.cos(theta) / (Math.sqrt(3) *
      (1.340264 - 3 * .081106 * t2 + 7 * .000893 * t6 + 9 * .003796 * t8));
    const y = theta * (1.340264 - .081106 * t2 + .000893 * t6 + .003796 * t8);
    return [projection.translate[0] + projection.scale * x, projection.translate[1] - projection.scale * y];
  }

  async function readAsset(file) {
    const response = await fetch('/assets/' + file, {credentials: 'omit'});
    if (!response.ok) throw new Error('Map asset unavailable');
    return response.json();
  }

  function locations(snapshot, geography) {
    const items = [];
    for (const city of Object.values(snapshot.cities || {})) {
      if (!radii.has(city.band) || !/^[A-Z]{2}$/.test(city.country) ||
          !Number.isFinite(city.lat) || !Number.isFinite(city.lon)) continue;
      const name = [city.city, city.region === city.city ? '' : city.region, names.of(city.country)].filter(Boolean).join(', ');
      items.push({name, band: city.band, point: projectedCenter(city.lat, city.lon, geography.projection), kind: 'city'});
    }
    // Previously published snapshots contained only country totals.
    for (const [code, band] of Object.entries(snapshot.country_only ?? snapshot.countries ?? {})) {
      const point = geography.features[code]?.point;
      if (!point || !radii.has(band)) continue;
      items.push({name: names.of(code) + ' (country/region only)', band, point, kind: 'country'});
    }
    return items.sort((a, b) => a.name.localeCompare(b.name, 'en'));
  }

  async function renderMap() {
    const [snapshot, geography] = await Promise.all([
      readAsset('visitor-countries.json'), readAsset('visitor-geography.json?v=2')
    ]);
    const items = locations(snapshot, geography);
    const dates = new Intl.DateTimeFormat('en-US', {month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC'});
    const day = value => dates.format(new Date(value + 'T12:00:00Z'));
    const period = 'Since ' + day(snapshot.start_date) + ' · Updated ' + day(snapshot.end_date);
    const layout = element('div', 'visitor-layout');
    const figure = element('figure', 'visitor-figure');
    const map = svg('svg', {viewBox: '0 0 1000 495', role: 'group', 'aria-label': 'World map of visitor locations'});
    const land = svg('g', {class: 'visitor-land', 'aria-hidden': 'true'});
    for (const feature of Object.values(geography.features)) {
      land.append(svg('path', {d: feature.d, 'fill-rule': 'evenodd'}));
    }
    const dots = svg('g', {});
    const prompt = items.length ? 'Select a dot to see the location and visitor range.' : 'No locations have been reported yet.';
    const readout = element('figcaption', 'visitor-readout', prompt);
    readout.setAttribute('aria-live', 'polite');
    let selected;
    function select(marker) {
      if (selected) selected.classList.remove('visitor-selected');
      selected = marker;
      if (marker) marker.classList.add('visitor-selected');
      readout.textContent = marker?.getAttribute('aria-label') || prompt;
    }

    const markers = new Map();
    // Small dots stay clickable when cities share a metropolitan area.
    for (const item of [...items].sort((a, b) => radii.get(b.band) - radii.get(a.band))) {
      const [x, y] = item.point;
      const radius = radii.get(item.band);
      const label = item.name + ' · ' + item.band + ' active users';
      const marker = svg('g', {class: 'visitor-marker visitor-' + item.kind, transform: 'translate(' + x + ' ' + y + ')',
        role: 'button', tabindex: '0', 'aria-label': label});
      marker.append(svg('circle', {r: Math.max(radius + 3, 9), class: 'visitor-hit'}),
        svg('circle', {r: radius, class: 'visitor-dot'}));
      for (const event of ['pointerenter', 'click', 'focus']) marker.addEventListener(event, () => select(marker));
      marker.addEventListener('keydown', event => {
        if (event.key === 'Escape') select(null);
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          select(marker);
        }
      });
      dots.append(marker);
      markers.set(item, marker);
    }
    map.append(land, dots);
    figure.append(map, readout);

    const key = element('div', 'visitor-key');
    key.append(element('h3', '', 'Active users'));
    const legend = element('ul', 'visitor-legend');
    for (const [band, radius] of radii) {
      const line = element('li');
      const swatch = element('span', 'visitor-swatch');
      swatch.style.setProperty('--size', (radius * 1.5) + 'px');
      swatch.setAttribute('aria-hidden', 'true');
      line.append(swatch, document.createTextNode(band));
      legend.append(line);
    }
    key.append(legend, element('p', 'visitor-note', 'Filled dots mark city centers. Open circles show visits located only by country or region.'));
    if (items.length) {
      const details = element('details', 'visitor-details');
      details.append(element('summary', '', 'Location list (' + items.length + ')'));
      const list = element('ul', 'visitor-list');
      for (const item of items) {
        const li = element('li');
        const button = element('button', 'visitor-location', item.name);
        button.type = 'button';
        button.addEventListener('click', () => select(markers.get(item)));
        li.append(button, element('span', '', item.band));
        list.append(li);
      }
      details.append(list);
      key.append(details);
    }
    const credit = element('p', 'visitor-credit');
    const attribution = element('a', '', 'GeoNames');
    attribution.href = 'https://www.geonames.org/';
    credit.append('City coordinates from ', attribution, '.');
    key.append(credit);
    layout.append(figure, key);
    section.append(element('p', 'visitor-period', period), layout);
  }

  renderMap().catch(() => {
    section.append(element('p', 'visitor-period', 'The visitor map is temporarily unavailable.'));
  });
})();
