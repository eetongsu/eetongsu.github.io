# Tong Su's academic website

Personal academic website for Tong Su, Ph.D. Candidate at Dartmouth College.

Website: https://eetongsu.github.io/

The site uses plain HTML, CSS, and JavaScript. Its existing design and publication archive are preserved. Only Python's standard library is needed to generate the pages.

## Update the website

- `data/profile.json`: education, experience, public project descriptions, honors, and service.
- `data/publications.json`: publication records, recognition, and manuscript links.
- `data/research-notes.json`: research summaries and keywords.
- `generate.py`: page templates, homepage text, site origin, and citation metadata.
- `docs/assets/`: CSS, JavaScript, and the author photograph.
- `docs/papers/`: the published manuscript PDF copies, including citation and copyright sheets.

For a local preview:

```sh
python generate.py
python scripts/check_site.py
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

Then open http://127.0.0.1:8765/.

Pushing changes to `main` automatically regenerates the HTML, checks local links and PDF assets, and publishes `docs/` through GitHub Actions. The repository's Pages source must be set to **GitHub Actions**. The workflow may also be run manually from the Actions tab.

Keep publication slugs stable so existing links continue to work. When replacing a manuscript PDF, update its `bytes` value in `data/publications.json`; keep its citation cover and applicable reuse notice. Manuscript versions and copyright terms are stated in the PDFs and publication pages. Hosting this repository publicly does not change those terms.

Google Scholar metrics and Web of Science distinctions are dated snapshots. Update their dates and values together after verification. Search Console ownership and indexing are managed separately for this website origin.

Private source manuscripts, raw CV files, audit reports, credentials, and the former host's configuration are not part of this repository.
