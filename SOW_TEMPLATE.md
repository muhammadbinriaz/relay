# Statement of Work — Relay Ops Intake (template)

**Client:** _______________________  
**Provider:** Muhammad Bin Riaz  
**Project:** Durable Ops Intake workflow on Relay  

## Scope (fixed)

1. Deploy Relay (API, worker, Postgres, Redis, console) to agreed hosting.
2. Configure one org + admin user for the client.
3. Deliver **Ops Intake** workflow:
   - CSV upload and/or webhook trigger
   - Validation + normalization (required fields agreed in kickoff)
   - Human approval step in console
   - CSV export of approved/valid rows
   - Slack notify (webhook URL provided by client) **or** email stub if Slack not ready
4. Provide run timeline + audit access for the admin user.
5. 30-minute handoff Loom + short runbook.

## Out of scope (unless change order)

- Lead generation / scraping vendors (Apify, Apollo, etc.)
- Custom LLM steps
- HubSpot/Salesforce OAuth (optional add-on)
- Mobile apps, SSO/SAML, multi-region HA
- Unlimited workflow redesign after acceptance

## Acceptance criteria (binary)

- [ ] Health endpoint reports database + redis ok on staging/production URL
- [ ] Admin can log into console
- [ ] Sample CSV (≥20 rows, including ≥1 invalid row) processes through the pipeline
- [ ] Invalid rows appear in approval payload / validation output
- [ ] Approving continues to export; rejecting cancels or stops per configured graph
- [ ] Valid rows downloadable as CSV
- [ ] At least one failed-step retry OR dead-letter visible in audit during a deliberate fault demo (provider-led)
- [ ] Slack message received **or** stub audit event documented if webhook not provided

## Timeline

- Kickoff + field mapping: 1 business day  
- Build/configure: ___ business days  
- Acceptance demo: 1 session  

## Commercials

- Fixed fee: $_______  
- Hosting / vendor pass-through: billed at cost (documented)  
- Change orders: written estimate before work  

## Warranty

14 days bugfix on delivered scope after acceptance. Enhancements are new SOW.

## Sign-off

Client: _________________ Date: _______  
Provider: _______________ Date: _______  
