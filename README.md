# advent-math

A math advent calendar built for a primary-school math teacher and her students (grades 4–6).
From December 1st to 24th every student opens one window a day, solves a short math problem and
types in the answer. Points reward speed, accuracy and an unbroken daily streak; class and
school rankings keep it competitive. The teacher gets an admin panel with per-class dashboards.

The UI is in Polish, because the students are.

## How it works

- **Students** log in with a 6-digit code (printed on a card with a QR code that logs them in
  directly). No names are stored: each student is a class + register number + a random funny
  nick (e.g. *Kasztan*), which is what rankings show.
- **One window per day.** Only today's window can be opened and answered (Europe/Warsaw time,
  checked server-side). Missed days cannot be caught up.
- **Variants.** Each day has a pool of task variants; students get them in rotation, so
  neighbours usually have different numbers. Answers never leave the server.
- **Answers** are numbers only: digits, a decimal comma and an optional leading minus.

### Scoring

```
day points = round( max(10, 100 − 10 × started minutes over 5:00 − 1 × wrong attempts) × 1.1^N )
```

- The clock starts when the student opens the window.
- Attempts are unlimited; each wrong one costs a point. A correct answer always earns at least
  10 points and keeps the streak alive.
- `N` is the number of consecutive days solved right before today, so day 1 is ×1.0 and a
  perfect day 24 is ×8.95. Missing a day resets the streak — that is intentional.

### Teacher panel (`/admin`)

- Create a class, pick its task set, enter the number of students → codes and nicks are generated.
  The number of students can only grow; a student can be deactivated (data is kept) instead of deleted.
- Regenerate a student's code (progress stays), rename nicks, print code cards.
- Dashboard: per-student, per-day status (opened / solved + points), totals and per-day counts.
- Rankings: school-wide individual, class vs class (average points per student), today's fastest.
- Preview every task set with all variants and answers.

## Task sets

Task sets are JSON files in `app/task_sets/`, versioned with the code. One set can be assigned to
many classes. Every set must define all 24 days; the app refuses to start otherwise.

```json
{
  "name": "Grade 4",
  "days": {
    "1": [
      {"text": "Mikołaj ma 7 worków, w każdym po 48 prezentów. Ile prezentów ma razem?", "answer": "336"},
      {"text": "Mikołaj ma 6 worków, w każdym po 52 prezenty. Ile prezentów ma razem?", "answer": "312"}
    ]
  }
}
```

`grade4-demo.json` and `grade6-demo.json` are placeholders until the real tasks are written.

## Local development

```bash
uv sync
uv run pytest
ADMIN_PASSWORD=dev-password FAKE_NOW=2026-12-01T10:00 uv run uvicorn app.main:create_app --factory --port 8123
```

Open http://localhost:8123 (students) and http://localhost:8123/admin (teacher).
Locally the app uses SQLite (`adwent.db`).

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./adwent.db` | SQLAlchemy URL; Postgres in production |
| `ADMIN_PASSWORD` | – | Teacher panel password (panel is disabled when empty) |
| `SECRET_KEY` | dev value | Signs admin sessions — set a long random value in production |
| `START_DATE` | `2026-12-01` | Day 1 of the calendar |
| `DAYS` | `24` | Number of windows |
| `PUBLIC_URL` | request URL | Address printed on cards and encoded in QR codes |
| `FAKE_NOW` | – | Testing only: pretend the current time is e.g. `2026-12-05T08:00` |

## Deployment (Google Cloud Run + Cloud SQL)

The app is a single container: FastAPI serves both the API and the static pages. Tables are
created automatically on start-up.

1. **Database** — in the existing Cloud SQL Postgres instance create a separate database and user:
   ```bash
   gcloud sql databases create advent_math --instance=INSTANCE
   gcloud sql users create advent --instance=INSTANCE --password=...
   ```
2. **Secrets**
   ```bash
   printf 'postgresql+psycopg://advent:PASSWORD@/advent_math?host=/cloudsql/PROJECT:REGION:INSTANCE' | gcloud secrets create advent-database-url --data-file=-
   printf '...' | gcloud secrets create advent-admin-password --data-file=-
   openssl rand -hex 32 | tr -d '\n' | gcloud secrets create advent-secret-key --data-file=-
   ```
   The Cloud Run service account needs `roles/secretmanager.secretAccessor` and `roles/cloudsql.client`.
3. **Deploy**
   ```bash
   gcloud run deploy advent-math --source . --region europe-central2 --allow-unauthenticated \
     --add-cloudsql-instances PROJECT:REGION:INSTANCE \
     --set-secrets DATABASE_URL=advent-database-url:latest,ADMIN_PASSWORD=advent-admin-password:latest,SECRET_KEY=advent-secret-key:latest \
     --set-env-vars PUBLIC_URL=https://advent-math.web.app \
     --max-instances 2
   ```
   Login rate limiting is kept in memory per instance, hence the low `--max-instances`.

### Friendly address (free)

Cloud Run URLs are long, so the app is exposed through Firebase Hosting, which gives a free
`https://SITE.web.app` address and forwards every request to Cloud Run (`hosting/firebase.json`).

```bash
firebase projects:addfirebase PROJECT            # once, if the GCP project has no Firebase yet
firebase hosting:sites:create advent-math --project PROJECT   # site names are global; pick another if taken
cd hosting && firebase deploy --only hosting --project PROJECT
```

If the site name differs, update `site` in `hosting/firebase.json` and `PUBLIC_URL`.
A custom domain can be attached later in the Firebase console.
