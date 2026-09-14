# Relay architecture

## Control plane vs workers

```
Client / Console / Webhook
        │
        ▼
   FastAPI (auth, definitions, runs, approvals)
        │
        ├── Postgres (source of truth: runs, steps, leases, audit, DLQ)
        └── Redis list (ready-step notifications)
                │
                ▼
        Worker(s) claim step with FOR UPDATE SKIP LOCKED
                │
                ├── execute connector
                ├── heartbeat lease
                ├── retry / dead-letter
                └── enqueue next step
```

## Durability guarantees (v1)

| Concern | Mechanism |
|---------|-----------|
| Crash mid-step | Lease expiry → reclaim → re-queue |
| Duplicate side effects | `idempotency_key` = `{run_id}:{step_key}:{attempt}` |
| Transient errors | Exponential backoff, `next_retry_at`, max attempts |
| Permanent failure | `dead_letters` + manual replay API |
| Human gate | Step/`run` → `waiting_approval`; resume only on decide |
| Accountability | Append-only `audit_events` |

## Step types (v1)

- `csv.ingest` — rows / csv_text / `use_fixture`
- `data.validate` — required fields + email normalize
- `human.approve` — creates `approval_tasks`
- `csv.export` — writes `/data/exports/run-{id}.csv`
- `slack.notify` — real webhook or stub
- `http.webhook` — POST outbound
- `email.stub` — log only

## Tenancy

JWT users carry `org_id`; `X-Org-Id` required. API keys are org-scoped (`X-API-Key`). All queries filter by `org_id`.

## What we deliberately did not build

- Temporal Cloud dependency
- Full visual DAG editor
- Multi-region consensus
- LLM-required paths
- Lead-gen vendors as core product

## Deploy notes

Compose is the reference topology. For staging: one Postgres, one Redis, ≥1 API, ≥1 worker, Next standalone. Put TLS terminator (Caddy/Nginx/Render) in front. Rotate `SECRET_KEY` and admin password before any external client.
