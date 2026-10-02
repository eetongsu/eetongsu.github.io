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

## Automatic Google Scholar metrics

The **Sync Google Scholar metrics** workflow runs on GitHub at 07:17 America/New_York each day, or manually from the Actions tab. It uses the [SerpApi Google Scholar Author API](https://serpapi.com/google-scholar-author-api), checks the author and all three all-time metrics, generates and validates the site, commits the verified snapshot, and triggers the existing Pages publisher. No local computer, browser extension, or Codex session is needed. GitHub schedules can be delayed and public-repository schedules can be disabled after 60 days without repository activity.

To enable it, create a SerpApi account and add its key as the **SERPAPI_API_KEY** repository secret under **Settings → Secrets and variables → Actions**. Then run **Sync Google Scholar metrics** once to verify the connection. Until the secret exists, the workflow skips updates and reports that setup is pending. Store the key only as a secret, never in source files or website JavaScript. See [SerpApi pricing](https://serpapi.com/pricing) for current limits; the workflow uses one request per daily run and does not purchase additional credits.

The page displays the last successful sync date. API/network errors, incomplete tables, or mismatched authors stop the update and preserve the published metrics and date. An unsuccessful sync does not block ordinary website publishing. Only `data/profile.json`, `docs/index.html`, and `docs/sitemap.xml` are committed by the sync workflow; the API key is never included in them.

For an optional manual local refresh, run `python scripts/update_scholar_metrics.py`, then generate, validate, and publish the site as above. This reads the public Scholar author profile directly without an API key; direct requests worked locally but failed from a GitHub-hosted runner during verification. Neither reader modifies the Scholar profile or retries/bypasses challenges. The separate Chrome badge extension is not required or changed.

Web of Science distinctions remain dated, separately verified snapshots and are not changed by the Scholar updater. Search Console ownership and indexing are managed separately for this website origin.

Private source manuscripts, raw CV files, audit reports, credentials, and the former host's configuration are not part of this repository.
