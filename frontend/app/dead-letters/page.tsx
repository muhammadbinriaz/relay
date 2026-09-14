"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

type DeadLetter = {
  id: string;
  run_id: string;
  step_id: string;
  reason: string;
  payload: Record<string, unknown>;
  created_at: string;
  replayed_at: string | null;
};

export default function DeadLettersPage() {
  const [items, setItems] = useState<DeadLetter[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  async function load() {
    try {
      setItems(await api<DeadLetter[]>("/api/dead-letters"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  async function replay(id: string) {
    setBusy(id);
    setError("");
    setMessage("");
    try {
      await api(`/api/dead-letters/${id}/replay`, { method: "POST" });
      setMessage(`Replayed ${id.slice(0, 8)}…`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Replay failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Shell>
      <div className="stack">
        <div>
          <h1>Dead letters</h1>
          <p className="muted">Steps that exhausted retries. Replay puts them back on the queue.</p>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {message ? <p className="muted">{message}</p> : null}
        <div className="panel">
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Run</th>
                <th>Reason</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td className="muted">{new Date(item.created_at).toLocaleString()}</td>
                  <td>
                    <Link className="mono" href={`/runs/${item.run_id}`}>
                      {item.run_id.slice(0, 8)}…
                    </Link>
                  </td>
                  <td>
                    <div>{item.reason}</div>
                    <div className="mono muted">{String(item.payload?.step_key || "")}</div>
                  </td>
                  <td>
                    {item.replayed_at ? (
                      <span className="badge ok">replayed</span>
                    ) : (
                      <button className="btn primary" disabled={busy === item.id} onClick={() => replay(item.id)}>
                        {busy === item.id ? "Replaying…" : "Replay"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    No dead letters — healthy so far.
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
