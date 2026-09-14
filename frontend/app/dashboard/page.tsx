"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { api, API_URL, getStoredAuth } from "@/lib/api";
import { Workflow } from "@/lib/types";

export default function DashboardPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadSlug, setUploadSlug] = useState("ops-intake");

  async function load() {
    try {
      setWorkflows(await api<Workflow[]>("/api/workflows"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function startFixtureRun(slug: string) {
    setBusy(`fixture:${slug}`);
    setMessage("");
    setError("");
    try {
      const run = await api<{ id: string }>("/api/runs", {
        method: "POST",
        body: JSON.stringify({
          slug,
          trigger_type: "manual",
          input: { use_fixture: true },
        }),
      });
      setMessage(`Fixture run started: ${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
    } finally {
      setBusy(null);
    }
  }

  async function uploadCsv(slug: string, file: File) {
    setBusy(`csv:${slug}`);
    setMessage("");
    setError("");
    try {
      const auth = getStoredAuth();
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/api/runs/csv?slug=${encodeURIComponent(slug)}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${auth?.access_token}`,
          "X-Org-Id": auth?.org_id || "",
        },
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || res.statusText);
      }
      const run = await res.json();
      setMessage(`CSV run started: ${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "CSV upload failed");
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <Shell>
      <div className="stack">
        <div>
          <h1>Workflows</h1>
          <p className="muted">Start a fixture demo or upload a client CSV for Ops Intake.</p>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {message ? (
          <p className="muted">
            {message} — open <Link href="/runs">Runs</Link> or <Link href="/approvals">Approvals</Link>.
          </p>
        ) : null}

        <div className="panel stack">
          <h2 style={{ margin: 0 }}>Upload CSV</h2>
          <p className="muted" style={{ margin: 0 }}>
            Expected columns: <span className="mono">name, email, company, title</span>
          </p>
          <div className="row">
            <select
              className="input"
              style={{ maxWidth: 220 }}
              value={uploadSlug}
              onChange={(e) => setUploadSlug(e.target.value)}
            >
              {workflows.map((wf) => (
                <option key={wf.id} value={wf.slug}>
                  {wf.slug}
                </option>
              ))}
            </select>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadCsv(uploadSlug, file);
              }}
            />
            <button
              className="btn"
              type="button"
              disabled={!!busy}
              onClick={() => fileRef.current?.click()}
            >
              {busy?.startsWith("csv:") ? "Uploading…" : "Choose file"}
            </button>
          </div>
        </div>

        <div className="panel">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Slug</th>
                <th>Steps</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {workflows.map((wf) => (
                <tr key={wf.id}>
                  <td>
                    <strong>{wf.name}</strong>
                    <div className="muted">{wf.description}</div>
                  </td>
                  <td className="mono">{wf.slug}</td>
                  <td className="mono">{wf.graph?.steps?.length ?? 0}</td>
                  <td>
                    <button
                      className="btn primary"
                      disabled={busy === `fixture:${wf.slug}`}
                      onClick={() => startFixtureRun(wf.slug)}
                    >
                      {busy === `fixture:${wf.slug}` ? "Starting…" : "Run fixture"}
                    </button>
                  </td>
                </tr>
              ))}
              {workflows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    No workflows yet.
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
