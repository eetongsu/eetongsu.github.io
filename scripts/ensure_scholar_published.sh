#!/usr/bin/env bash
set -euo pipefail

expected=docs/index.html
test -s "$expected"
received=$(mktemp)
trap 'rm -f "$received"' EXIT

homepage_matches() {
  local url="https://eetongsu.github.io/?scholar-check=${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-$1"
  curl --fail --silent --show-error --max-time 12 --output "$received" "$url" &&
    cmp -s "$expected" "$received"
}

if homepage_matches initial; then
  echo 'The public homepage matches the saved snapshot.' >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi

echo 'Requesting a fresh Pages deployment of main.' >> "$GITHUB_STEP_SUMMARY"
gh workflow run pages.yml --ref main --repo "$GITHUB_REPOSITORY"

for attempt in {1..15}; do
  sleep 12
  if homepage_matches "$attempt"; then
    echo 'Verified the updated public homepage after deployment.' >> "$GITHUB_STEP_SUMMARY"
    exit 0
  fi
done

echo '::error::The public homepage could not be verified after requesting deployment. Check the Pages run. The next scheduled check will compare again.'
exit 1
