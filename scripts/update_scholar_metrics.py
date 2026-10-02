"""Refresh one public Scholar profile; failed reads never replace saved metrics."""
import argparse
from datetime import datetime
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.error import HTTPError
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
    return validate_metrics(result)


def validate_metrics(metrics):
    if any(type(value) is not int or value < 0 for value in metrics.values()):
        raise ValueError('Citation metrics must be nonnegative integers.')
    if metrics['citations'] < max(metrics['h_index'] ** 2, metrics['i10_index'] * 10):
        raise ValueError('The citation metrics are inconsistent.')
    return metrics


def scholar_author_id(profile_url):
    parsed = urlsplit(profile_url)
    author_ids = parse_qs(parsed.query).get('user', [])
    if parsed.scheme != 'https' or parsed.netloc != 'scholar.google.com' or parsed.path != '/citations' or len(author_ids) != 1:
        raise ValueError('Expected a public Google Scholar author-profile URL.')
    return author_ids[0]


def fetch_profile(profile_url):
    author_id = scholar_author_id(profile_url)
    # Keep user= first: this public-profile route is explicitly allowed by Scholar robots.txt.
    url = 'https://scholar.google.com/citations?' + urlencode({'user': author_id, 'hl': 'en'})
    request = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(request, timeout=30) as response:
        final = urlsplit(response.url)
        if final.scheme != 'https' or final.netloc != 'scholar.google.com' or final.path != '/citations' or parse_qs(final.query).get('user') != [author_id]:
            raise ValueError('Scholar redirected away from the requested profile.')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Scholar did not return an HTML profile.')
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError('Scholar returned an unexpectedly large page.')
        return data.decode('utf-8')


def fetch_serpapi(profile_url, api_key):
    if not api_key:
        raise ValueError('SERPAPI_API_KEY is required for cloud updates.')
    params = {'engine': 'google_scholar_author', 'author_id': scholar_author_id(profile_url),
              'hl': 'en', 'api_key': api_key}
    request = Request('https://serpapi.com/search.json?' + urlencode(params),
                      headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urlopen(request, timeout=45) as response:
        if 'application/json' not in response.headers.get('Content-Type', ''):
            raise ValueError('The API did not return JSON.')
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError('The API returned an unexpectedly large response.')
        return json.loads(data)


def parse_serpapi_metrics(payload, expected_name, expected_author_id):
    if payload.get('error') or payload.get('search_metadata', {}).get('status') != 'Success':
        raise ValueError('The API did not complete a successful search.')
    params = payload.get('search_parameters', {})
    if params.get('engine') != 'google_scholar_author' or params.get('author_id') != expected_author_id:
        raise ValueError('The API returned a different author profile.')
    name = ' '.join(payload.get('author', {}).get('name', '').split())
    if name.casefold() != expected_name.casefold():
        raise ValueError('The API returned a different author name.')
    table = payload.get('cited_by', {}).get('table', [])
    result = {}
    for key in ('citations', 'h_index', 'i10_index'):
        rows = [row[key] for row in table if isinstance(row, dict) and key in row]
        if len(rows) != 1 or not isinstance(rows[0], dict) or 'all' not in rows[0]:
            raise ValueError('An all-time metric is missing or ambiguous in the API response.')
        result[key] = rows[0]['all']
    return validate_metrics(result)


def update_profile(path, checked_date=None, source='direct', api_key=None):
    profile = json.loads(path.read_text(encoding='utf-8'))
    if source == 'serpapi':
        metrics = parse_serpapi_metrics(fetch_serpapi(profile['scholar'], api_key),
                                       profile['name'], scholar_author_id(profile['scholar']))
    elif source == 'direct':
        metrics = parse_metrics(fetch_profile(profile['scholar']), profile['name'])
    else:
        raise ValueError('Unknown citation data source.')
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
    cli.add_argument('--source', choices=('direct', 'serpapi'), default='direct')
    args = cli.parse_args()
    try:
        print(json.dumps(update_profile(args.profile, source=args.source,
                                        api_key=os.environ.get('SERPAPI_API_KEY'))))
        return 0
    except Exception as error:
        # Never log the request URL or response body: either may contain an API key.
        reason = 'HTTP ' + str(error.code) if isinstance(error, HTTPError) else type(error).__name__
        print('Scholar sync failed (' + reason + '). Existing metrics and date were preserved.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
