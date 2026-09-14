"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";
import { Workflow } from "@/lib/types";

export default function DashboardPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");

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
    setBusy(slug);
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
      setMessage(`Run started: ${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Shell>
      <div className="stack">
        <div>
          <h1>Workflows</h1>
          <p className="muted">Versioned definitions. Start a zero-key Ops Intake demo run.</p>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {message ? (
          <p className="muted">
            {message} — open <Link href="/runs">Runs</Link> or <Link href="/approvals">Approvals</Link>.
          </p>
        ) : null}
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
                      disabled={busy === wf.slug}
                      onClick={() => startFixtureRun(wf.slug)}
                    >
                      {busy === wf.slug ? "Starting…" : "Run fixture"}
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
