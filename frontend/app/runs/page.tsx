"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Shell, statusClass } from "@/components/Shell";
import { api } from "@/lib/api";
import { Run } from "@/lib/types";

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setRuns(await api<Run[]>("/api/runs"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, []);

  return (
    <Shell>
      <div className="stack">
        <div>
          <h1>Runs</h1>
          <p className="muted">Live run list. Auto-refreshes while you wait on approvals.</p>
        </div>
        {error ? <p className="error">{error}</p> : null}
        <div className="panel">
          <table className="table">
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Trigger</th>
                <th>Current</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>
                    <Link className="mono" href={`/runs/${run.id}`}>
                      {run.id.slice(0, 8)}…
                    </Link>
                  </td>
                  <td>
                    <span className={`badge ${statusClass(run.status)}`}>{run.status}</span>
                  </td>
                  <td className="mono">{run.trigger_type}</td>
                  <td className="mono">{run.current_step_key || "—"}</td>
                  <td className="muted">{new Date(run.created_at).toLocaleString()}</td>
                </tr>
              ))}
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="muted">
                    No runs yet. Start one from Workflows.
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
