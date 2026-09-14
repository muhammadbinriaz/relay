"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";
import { Approval } from "@/lib/types";

export default function ApprovalsPage() {
  const [items, setItems] = useState<Approval[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try {
      setItems(await api<Approval[]>("/api/approvals"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, []);

  async function decide(id: string, decision: "approve" | "reject") {
    setBusy(id);
    setError("");
    try {
      await api(`/api/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision, note: decision === "approve" ? "Looks good" : "Rejected in demo" }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Shell>
      <div className="stack">
        <div>
          <h1>Approvals</h1>
          <p className="muted">Human gates. Runs park here until you approve or reject.</p>
        </div>
        {error ? <p className="error">{error}</p> : null}
        <div className="stack">
          {items.map((item) => (
            <div className="panel stack fade-in" key={item.id}>
              <div className="row">
                <h2 style={{ margin: 0 }}>{item.title}</h2>
                <Link className="mono muted" href={`/runs/${item.run_id}`}>
                  run {item.run_id.slice(0, 8)}…
                </Link>
              </div>
              <pre className="mono muted" style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                {JSON.stringify(item.payload, null, 2)}
              </pre>
              <div className="row">
                <button
                  className="btn primary"
                  disabled={busy === item.id}
                  onClick={() => decide(item.id, "approve")}
                >
                  Approve
                </button>
                <button className="btn danger" disabled={busy === item.id} onClick={() => decide(item.id, "reject")}>
                  Reject
                </button>
              </div>
            </div>
          ))}
          {items.length === 0 ? <div className="panel muted">Inbox empty — start a fixture run from Workflows.</div> : null}
        </div>
      </div>
    </Shell>
  );
}
