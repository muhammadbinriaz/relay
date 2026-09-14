# Client demo script — Relay

**Goal:** Cousin referral or Upwork discovery call sees a working durable workflow in under 10 minutes. No Apify. No LLM keys.

## Before the call

- [ ] Staging or local Compose is up (`/api/health` = ok)
- [ ] You can log in with seeded admin
- [ ] Optional: set `SLACK_WEBHOOK_URL` if you want a real ping; otherwise say “stubbed notify, same code path”

## Script (≈6 minutes)

1. **Open console** — “This is Relay, a durable workflow control plane I deploy for ops teams.”
2. **Workflows** — show `Ops Intake Pipeline` steps: ingest → validate → approve → export → notify.
3. **Run fixture** — start run with built-in sample rows (includes one bad email on purpose).
4. **Runs timeline** — watch steps move; call out lease/attempt counters.
5. **Approvals** — show valid/invalid summary; **Approve**.
6. **Export** — download CSV of valid rows only.
7. **Audit** — scroll events: started, completed, approval.decided, run.completed.
8. **Close** — “Acceptance is binary: rows processed, approval recorded, CSV out, failures visible. Not lead quality debates.”

## Lines to say early

- “Human QA stays in the loop by design.”
- “Vendor spend is pass-through when we add paid connectors later.”
- “This same engine hosts other templates (CRM sync, webhook ops) without rebuilding the runtime.”

## Do not demo

- Lead scraping / Apollo / Apify
- “100% accuracy”
- Unfinished HubSpot unless OAuth is configured

## After approve path

Ask for next step: fixed SOW (see `SOW_TEMPLATE.md`) → delivery → 5★ review.
