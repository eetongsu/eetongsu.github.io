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

Google Scholar citation metrics refresh daily at approximately 07:17 America/New_York through the same GitHub Actions workflow. A manual workflow run also refreshes them. Normal source pushes publish without contacting Scholar. Only the public author-profile page is requested, once per run, using its all-time metrics. No API key or Google login is required. The page displays the last successful sync date; network errors, challenges, incomplete tables, or mismatched authors stop that run and preserve the previous public website, metrics, and date. GitHub schedules may be delayed, and scheduled workflows may be disabled after 60 days without repository activity. Successful daily snapshots are committed to the repository. If a run fails, its Actions log identifies the failure category; after resolving an ongoing access problem, the workflow can be run manually again.

Web of Science distinctions remain dated, separately verified snapshots and are not changed by the Scholar updater. Search Console ownership and indexing are managed separately for this website origin.

Private source manuscripts, raw CV files, audit reports, credentials, and the former host's configuration are not part of this repository.
