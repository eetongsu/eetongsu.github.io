"""Check generated academic pages and their local links before publishing."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
BASE = 'https://eetongsu.github.io'


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.canonical = None
        self.metadata = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('a', 'link') and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag in ('img', 'script') and attrs.get('src'):
            self.links.append(attrs['src'])
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical = attrs.get('href')
        if tag == 'meta' and attrs.get('name'):
            self.metadata[attrs['name']] = attrs.get('content', '')


pages = list(DOCS.rglob('*.html'))
assert pages, 'No generated HTML pages'
for file in pages:
    doc = file.read_text(encoding='utf-8')
    parser = Page()
    parser.feed(doc)
    if file.name != '404.html':
        expected = BASE + '/' + file.parent.relative_to(DOCS).as_posix().strip('.')
        expected = expected.rstrip('/') + '/'
        assert parser.canonical == expected, f'Incorrect canonical URL: {file}'
        assert 'noindex' not in parser.metadata.get('robots', '').lower()
    assert 'tong-su-research.eetongsu.chatgpt.site' not in doc, f'Old origin in {file}'
    for link in parser.links:
        url = urlsplit(link)
        if url.scheme or url.netloc or not url.path:
            continue
        target = DOCS / unquote(url.path.lstrip('/')) if url.path.startswith('/') else file.parent / unquote(url.path)
        if target.is_dir():
            target = target / 'index.html'
        assert target.is_file(), f'Broken local link: {file} -> {link}'

publications = json.loads((ROOT / 'data/publications.json').read_text(encoding='utf-8'))
for paper in publications:
    if manuscript := paper.get('manuscript'):
        pdf = DOCS / manuscript['url'].lstrip('/')
        assert pdf.read_bytes().startswith(b'%PDF-'), f'Invalid PDF: {pdf}'
        assert pdf.stat().st_size == manuscript['bytes'], f'Incorrect PDF size: {pdf}'

sitemap = ET.parse(DOCS / 'sitemap.xml')
locations = [node.text for node in sitemap.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
assert len(locations) == len(publications) + 4
assert all(url.startswith(BASE + '/') for url in locations)
assert 'Sitemap: ' + BASE + '/sitemap.xml' in (DOCS / 'robots.txt').read_text(encoding='utf-8')
assert (DOCS / '.nojekyll').exists()
print(json.dumps({'html_pages': len(pages), 'publications': len(publications),
                  'pdfs': len(list((DOCS / 'papers').glob('*.pdf'))),
                  'sitemap_urls': len(locations), 'local_links': 'passed'}))
