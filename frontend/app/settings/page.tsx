"use client";

import { FormEvent, useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

type IntegrationStatus = {
  slack_configured: boolean;
  hubspot_configured: boolean;
  export_dir: string;
  api_url: string;
  app_url: string;
};

type ApiKeyRow = {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  revoked_at: string | null;
};

type CreatedKey = {
  id: string;
  name: string;
  key_prefix: string;
  api_key: string;
  created_at: string;
};

export default function SettingsPage() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [name, setName] = useState("client-webhook");
  const [created, setCreated] = useState<CreatedKey | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [s, k] = await Promise.all([
        api<IntegrationStatus>("/api/auth/integrations"),
        api<ApiKeyRow[]>("/api/auth/api-keys"),
      ]);
      setStatus(s);
      setKeys(k);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setCreated(null);
    try {
      const row = await api<CreatedKey>("/api/auth/api-keys", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setCreated(row);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/api/auth/api-keys/${id}/revoke`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Revoke failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell>
      <div className="stack">
        <div>
          <h1>Settings</h1>
          <p className="muted">Integrations and API keys for client webhooks.</p>
        </div>
        {error ? <p className="error">{error}</p> : null}

        <div className="panel stack">
          <h2 style={{ margin: 0 }}>Integrations</h2>
          <div className="row">
            <span className={`badge ${status?.slack_configured ? "ok" : "warn"}`}>
              Slack {status?.slack_configured ? "configured" : "stub mode"}
            </span>
            <span className={`badge ${status?.hubspot_configured ? "ok" : "warn"}`}>
              HubSpot {status?.hubspot_configured ? "configured" : "stub mode"}
            </span>
          </div>
          <p className="muted" style={{ margin: 0 }}>
            Set <span className="mono">SLACK_WEBHOOK_URL</span> /{" "}
            <span className="mono">HUBSPOT_ACCESS_TOKEN</span> in server env, then restart API/worker.
            Demo path works without either.
          </p>
        </div>

        <div className="panel stack">
          <h2 style={{ margin: 0 }}>API keys</h2>
          <p className="muted" style={{ margin: 0 }}>
            Use header <span className="mono">X-API-Key</span> for{" "}
            <span className="mono">POST /api/webhooks/ops-intake</span>.
          </p>
          <form className="row" onSubmit={onCreate}>
            <input className="input" style={{ maxWidth: 260 }} value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn primary" disabled={busy} type="submit">
              {busy ? "Creating…" : "Create key"}
            </button>
          </form>
          {created ? (
            <div className="panel" style={{ background: "rgba(61,207,142,0.06)" }}>
              <strong>Copy now — shown once</strong>
              <pre className="mono" style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}>
                {created.api_key}
              </pre>
            </div>
          ) : null}
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Prefix</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id}>
                  <td>{k.name}</td>
                  <td className="mono">{k.key_prefix}…</td>
                  <td>
                    <span className={`badge ${k.is_active && !k.revoked_at ? "ok" : "danger"}`}>
                      {k.is_active && !k.revoked_at ? "active" : "revoked"}
                    </span>
                  </td>
                  <td>
                    {k.is_active && !k.revoked_at ? (
                      <button className="btn danger" disabled={busy} onClick={() => revoke(k.id)}>
                        Revoke
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
              {keys.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    No keys yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
