"""Refresh one public Scholar profile; failed reads never replace saved metrics."""
import argparse
from datetime import datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = 'TongSuAcademicWebsite/1.0 (+https://eetongsu.github.io/)'


class MetricsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.name_parts = []
        self.name_tag = None
        self.table_depth = 0
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id') == 'gsc_prf_in':
            self.name_tag = tag
        if tag == 'table' and (self.table_depth or attrs.get('id') == 'gsc_rsb_st'):
            self.table_depth += 1
        if self.table_depth and tag == 'tr':
            self.row = []
        if self.table_depth and tag in ('td', 'th'):
            self.cell = []

    def handle_data(self, data):
        if self.name_tag:
            self.name_parts.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == self.name_tag:
            self.name_tag = None
        if self.table_depth:
            if tag in ('td', 'th') and self.cell is not None:
                if self.row is not None:
                    self.row.append(' '.join(''.join(self.cell).split()))
                self.cell = None
            elif tag == 'tr' and self.row is not None:
                self.rows.append(self.row)
                self.row = None
            elif tag == 'table':
                self.table_depth -= 1


def parse_metrics(document, expected_name):
    parser = MetricsParser()
    parser.feed(document)
    name = ' '.join(''.join(parser.name_parts).split())
    if name.casefold() != expected_name.casefold():
        raise ValueError('The returned page does not match the expected author.')
    headers = [row for row in parser.rows if 'All' in row]
    if len(headers) != 1 or headers[0].count('All') != 1:
        raise ValueError('The all-time citation metrics table is missing or ambiguous.')
    column = headers[0].index('All')
    result = {}
    for label, key in [('Citations', 'citations'), ('h-index', 'h_index'), ('i10-index', 'i10_index')]:
        rows = [row for row in parser.rows if row and row[0] == label]
        if len(rows) != 1 or len(rows[0]) <= column:
            raise ValueError('A required citation metric is missing or ambiguous.')
        value = rows[0][column]
        if not re.fullmatch(r'(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)', value):
            raise ValueError('A citation metric is not a complete nonnegative integer.')
        result[key] = int(value.replace(',', ''))
    if result['citations'] < max(result['h_index'] ** 2, result['i10_index'] * 10):
        raise ValueError('The citation metrics are inconsistent.')
    return result


def fetch_profile(profile_url):
    parsed = urlsplit(profile_url)
    author_ids = parse_qs(parsed.query).get('user', [])
    if parsed.scheme != 'https' or parsed.netloc != 'scholar.google.com' or parsed.path != '/citations' or len(author_ids) != 1:
        raise ValueError('Expected a public Google Scholar author-profile URL.')
    # Keep user= first: this public-profile route is explicitly allowed by Scholar robots.txt.
    url = 'https://scholar.google.com/citations?' + urlencode({'user': author_ids[0], 'hl': 'en'})
    request = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(request, timeout=30) as response:
        final = urlsplit(response.url)
        if final.netloc != parsed.netloc or final.path != parsed.path or parse_qs(final.query).get('user') != author_ids:
            raise ValueError('Scholar redirected away from the requested profile.')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Scholar did not return an HTML profile.')
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError('Scholar returned an unexpectedly large page.')
        return data.decode('utf-8')


def update_profile(path, checked_date=None):
    profile = json.loads(path.read_text(encoding='utf-8'))
    metrics = parse_metrics(fetch_profile(profile['scholar']), profile['name'])
    if profile['metrics']['citations'] > 0 and metrics['citations'] == 0:
        raise ValueError('Unexpectedly empty citation metrics; review before replacing saved data.')
    checked_date = checked_date or datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    changed = metrics != profile['metrics'] or checked_date != profile['snapshot_date']
    if changed:
        profile['metrics'] = metrics
        profile['snapshot_date'] = checked_date
        temp = path.with_suffix('.json.tmp')
        temp.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temp.replace(path)
    return {'updated': changed, 'metrics': metrics, 'last_synced': checked_date}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--profile', type=Path, default=ROOT / 'data' / 'profile.json')
    args = cli.parse_args()
    try:
        print(json.dumps(update_profile(args.profile)))
        return 0
    except Exception as error:
        # No retries, CAPTCHA handling, alternate proxies, or changes to the saved data.
        print('Scholar sync failed (' + type(error).__name__ + '). Existing metrics and date were preserved.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
