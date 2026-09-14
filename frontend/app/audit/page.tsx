"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";
import { AuditEvent } from "@/lib/types";

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setEvents(await api<AuditEvent[]>("/api/audit?limit=100"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <Shell>
      <div className="stack">
        <div>
          <h1>Audit</h1>
          <p className="muted">Append-only trail across runs, leases, retries, and approvals.</p>
        </div>
        {error ? <p className="error">{error}</p> : null}
        <div className="panel">
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Type</th>
                <th>Message</th>
                <th>Run</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr key={ev.id}>
                  <td className="muted">{new Date(ev.created_at).toLocaleString()}</td>
                  <td className="mono">{ev.event_type}</td>
                  <td>{ev.message}</td>
                  <td>
                    {ev.run_id ? (
                      <Link className="mono" href={`/runs/${ev.run_id}`}>
                        {ev.run_id.slice(0, 8)}…
                      </Link>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
              {events.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    No audit events yet.
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
