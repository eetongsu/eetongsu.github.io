#!/usr/bin/env bash
# Run from Google Cloud Shell with a project ID you own.
# Usage: bash scripts/setup_visitor_identity.sh YOUR_PROJECT_ID
set -euo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]]; then
  echo 'Usage: bash scripts/setup_visitor_identity.sh YOUR_PROJECT_ID' >&2
  exit 2
fi

project=$1
pool=ga4-visitor-map
provider=github-pages-reader
sa_id=ga4-visitor-reader
email="$sa_id@$project.iam.gserviceaccount.com"
marker='Dedicated to the eetongsu/eetongsu.github.io visitor map.'
issuer=https://token.actions.githubusercontent.com
workflow='eetongsu/eetongsu.github.io/.github/workflows/visitor-map.yml@refs/heads/main'
condition="assertion.repository_id == '1400871394' && assertion.repository_owner_id == '44361584' && assertion.ref == 'refs/heads/main' && assertion.workflow_ref == '$workflow'"
mapping='google.subject=assertion.sub,attribute.repository_id=assertion.repository_id'

command -v python3 >/dev/null
project_number=$(gcloud projects describe "$project" --format='value(projectNumber)')
[[ $project_number =~ ^[0-9]+$ ]] || { echo 'Could not identify the selected project.' >&2; exit 1; }
parent="projects/$project_number/locations/global/workloadIdentityPools/$pool"
common=(--project="$project" --quiet)
pools=(gcloud iam workload-identity-pools)
accounts=(gcloud iam service-accounts)

gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  analyticsdata.googleapis.com "${common[@]}"

# A successful list with no match means absent; any listing error stops the script.
emails=$("${accounts[@]}" list "${common[@]}" --format='value(email)')
if ! grep -Fxq "$email" <<< "$emails"; then
  "${accounts[@]}" create "$sa_id" --display-name='GA4 visitor map reader' \
    --description="$marker" "${common[@]}"
fi
description=$("${accounts[@]}" describe "$email" "${common[@]}" --format='value(description)')
[[ $description == "$marker" ]] || { echo "Service account $email already has another purpose." >&2; exit 1; }

pool_names=$("${pools[@]}" list --location=global "${common[@]}" --format='value(name)')
if ! grep -Fxq "$parent" <<< "$pool_names"; then
  "${pools[@]}" create "$pool" --location=global --display-name='GA4 visitor map' \
    --description="$marker" "${common[@]}"
fi
pool_info=$("${pools[@]}" describe "$pool" --location=global "${common[@]}" --format=json)
python3 -c '
import json, sys
p = json.load(sys.stdin)
if p.get("description") != sys.argv[1] or p.get("disabled") or p.get("state") != "ACTIVE":
    sys.exit("The pool is inactive or belongs to another application.")
' "$marker" <<< "$pool_info"

provider_flags=(--location=global --workload-identity-pool="$pool" "${common[@]}")
provider_name="$parent/providers/$provider"
provider_names=$("${pools[@]}" providers list "${provider_flags[@]}" --format='value(name)')
if [[ -z $provider_names ]]; then
  "${pools[@]}" providers create-oidc "$provider" "${provider_flags[@]}" \
    --display-name='Visitor map workflow' --issuer-uri="$issuer" \
    --attribute-mapping="$mapping" --attribute-condition="$condition"
elif [[ $provider_names != "$provider_name" ]]; then
  echo 'The dedicated pool already contains another provider. No trust binding added.' >&2
  exit 1
fi

provider_info=$("${pools[@]}" providers describe "$provider" "${provider_flags[@]}" --format=json)
python3 -c '
import json, sys
p = json.load(sys.stdin)
oidc = p.get("oidc", {})
expected = {"google.subject": "assertion.sub", "attribute.repository_id": "assertion.repository_id"}
if (p.get("disabled") or p.get("state") != "ACTIVE" or oidc.get("issuerUri") != sys.argv[1]
        or oidc.get("allowedAudiences") or p.get("attributeCondition") != sys.argv[2]
        or p.get("attributeMapping") != expected):
    sys.exit("The existing provider has different trust settings. No trust binding added.")
' "$issuer" "$condition" <<< "$provider_info"

member="principalSet://iam.googleapis.com/$parent/attribute.repository_id/1400871394"
"${accounts[@]}" add-iam-policy-binding "$email" --member="$member" \
  --role=roles/iam.workloadIdentityUser --condition=None "${common[@]}" --format=none

printf '\nGrant Viewer on the target GA4 property to %s.\n' "$email"
printf 'Set these repository Actions variables:\nGA4_WIF_PROVIDER=%s\nGA4_SERVICE_ACCOUNT=%s\n' "$provider_name" "$email"
echo 'Set GA4_PROPERTY_ID to the numeric ID of that GA4 property, then run Update visitor map.'
