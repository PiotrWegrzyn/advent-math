#!/usr/bin/env bash
set -euo pipefail

PROJECT="${PROJECT:-law-hub-512902}"
REGION="${REGION:-europe-west1}"
PUBLIC_URL="${PUBLIC_URL:-}"

env_vars="START_DATE=2026-12-01,SEED_TASK_SETS_DIR="
if [ -n "${UNLOCK_ALL_DAYS:-}" ]; then
  env_vars="$env_vars,UNLOCK_ALL_DAYS=$UNLOCK_ALL_DAYS"
fi
if [ -n "$PUBLIC_URL" ]; then
  env_vars="$env_vars,PUBLIC_URL=$PUBLIC_URL"
fi

gcloud run deploy advent-math \
  --project "$PROJECT" \
  --region "$REGION" \
  --source . \
  --service-account "advent-run@$PROJECT.iam.gserviceaccount.com" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --memory 512Mi \
  --set-secrets DATABASE_URL=advent-database-url:latest,ADMIN_PASSWORD=advent-admin-password:latest,SECRET_KEY=advent-secret-key:latest \
  --set-env-vars "$env_vars"
