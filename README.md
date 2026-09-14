# Relay — Durable Workflow Engine

Production-shaped control plane for business automations: durable steps, leases, retries, human approvals, dead letters, and an append-only audit trail.

Not a RAG demo. Not a lead scraper. Zero paid API keys required for the seeded **Ops Intake** happy path.

## Stack

- **API / worker:** FastAPI, SQLAlchemy, Alembic, Redis queue, Postgres
- **Console:** Next.js App Router
- **Runtime:** Docker Compose (`api`, `worker`, `web`, `postgres`, `redis`)

## Quick start

```powershell
copy .env.example .env
docker compose up --build
```

- Console: http://localhost:3001  
- API docs: http://localhost:8000/docs  
- Health: http://localhost:8000/api/health  

Login (seeded):

- Email: `admin@relay.local`  
- Password: `RelayDemo2026!` (or `ADMIN_PASSWORD` from `.env`)

### Demo path (5 minutes)

1. Sign in → **Workflows** → **Run fixture** (or **Upload CSV**)
2. Open **Approvals** → approve the batch
3. Open the run timeline → download export CSV; HubSpot/Slack show stub or live based on Settings
4. Show **Dead letters** (empty is fine) + **Settings** (API key create for webhooks)

See [CLIENT_DEMO.md](CLIENT_DEMO.md) and [SOW_TEMPLATE.md](SOW_TEMPLATE.md).

## Staging host

Use [render.yaml](render.yaml) blueprint (API + worker + web + Redis + Postgres). After deploy:

1. Set `ADMIN_PASSWORD`, `CORS_ORIGINS`, `APP_URL`, `API_URL`, `NEXT_PUBLIC_API_URL`
2. Confirm `GET /api/health`
3. Run through [CLIENT_DEMO.md](CLIENT_DEMO.md)
4. Keep the URL for cousin referral + Upwork proposals

Python for local backend work: **3.11 or 3.12** (3.14 wheels may be missing on Windows).

## Local backend (without full compose)

```powershell
# postgres + redis via compose
docker compose up -d postgres redis
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
$env:DATABASE_URL="postgresql+psycopg://relay:relay@localhost:5433/relay"
$env:REDIS_URL="redis://localhost:6380/0"
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
# other terminal:
python -m app.worker.main
```

Postgres is on host port **5433**, Redis on **6380** (avoids clashes with local installs).

## Why not Celery-only?

Relay persists **run + step state** in Postgres with:

- worker **leases + heartbeat** (crash reclaim)
- **idempotency keys** per attempt
- **retry backoff** then **dead-letter + replay**
- **approval parking** (`waiting_approval`) with resume
- **audit events** for every transition

That is the story you sell on Upwork — not “background job fired.”

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/THREAT_NOTES.md](docs/THREAT_NOTES.md)
- [CLIENT_DEMO.md](CLIENT_DEMO.md)
- [SOW_TEMPLATE.md](SOW_TEMPLATE.md)

## License

Private portfolio / client delivery kit. All rights reserved unless you choose otherwise.
