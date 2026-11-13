#!/usr/bin/env bash
# One-time setup: secrets and a dedicated service account for Cloud Run.
# Expects the advent-database-url secret to exist already.
set -euo pipefail

PROJECT="${PROJECT:-law-hub-512902}"
SA_NAME="advent-run"
SA="$SA_NAME@$PROJECT.iam.gserviceaccount.com"

create_secret() {
  local name="$1" value="$2"
  if gcloud secrets describe "$name" --project "$PROJECT" >/dev/null 2>&1; then
    echo "secret $name already exists, leaving it"
  else
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --project "$PROJECT" --replication-policy=automatic
  fi
}

ADMIN_PASSWORD="$(python3 -c 'import secrets, string; print("".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16)))')"
create_secret advent-admin-password "$ADMIN_PASSWORD"
create_secret advent-secret-key "$(openssl rand -hex 32)"

if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT" --display-name "advent-math Cloud Run"
fi

for secret in advent-database-url advent-admin-password advent-secret-key; do
  gcloud secrets add-iam-policy-binding "$secret" --project "$PROJECT" \
    --member "serviceAccount:$SA" --role roles/secretmanager.secretAccessor --condition=None >/dev/null
  echo "granted $SA access to $secret"
done

echo
echo "Teacher panel password:"
gcloud secrets versions access latest --secret advent-admin-password --project "$PROJECT"
echo
