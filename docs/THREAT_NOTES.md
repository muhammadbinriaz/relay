# Webhook & public surface notes (Relay)

## Trust boundaries

- Console JWT is required for UI actions. Org context via `X-Org-Id`.
- Automation integrations should use org API keys (`X-API-Key`), not shared admin passwords.
- Export download requires auth; filenames are constrained (no path traversal).

## Webhook trigger

`POST /api/webhooks/{slug}` is authenticated. Do **not** expose an unauthenticated public webhook without:

1. Per-workflow HMAC secret header verification (future enhancement)
2. Rate limiting at the edge (Render/Cloudflare/Nginx)
3. Payload size caps

Until HMAC lands, treat webhook URLs as private (API key only).

## Secrets

- Rotate `SECRET_KEY` and `ADMIN_PASSWORD` before any external client.
- Never commit `.env`.
- Slack / HubSpot tokens stay server-side only.

## Abuse cases to demo deliberately

- Invalid CSV row → validation errors in approval payload (not silent drop without visibility)
- Kill worker mid-lease → reclaim + retry (local: stop worker container, restart)
- Exhaust retries → dead letter + replay from API/console path
