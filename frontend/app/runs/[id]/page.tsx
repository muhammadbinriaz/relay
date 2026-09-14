"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Shell, statusClass } from "@/components/Shell";
import { api, API_URL, getStoredAuth } from "@/lib/api";
import { AuditEvent, Run } from "@/lib/types";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      const [r, a] = await Promise.all([
        api<Run>(`/api/runs/${params.id}`),
        api<AuditEvent[]>(`/api/audit?run_id=${params.id}&limit=50`),
      ]);
      setRun(r);
      setAudit(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [params.id]);

  const exportStep = run?.steps.find((s) => s.step_type === "csv.export" && s.status === "completed");
  const exportName =
    exportStep?.output && typeof exportStep.output.filename === "string"
      ? exportStep.output.filename
      : null;

  return (
    <Shell>
      <div className="stack">
        <div className="row">
          <Link href="/runs" className="muted">
            ← Runs
          </Link>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {!run ? (
          <p className="muted">Loading…</p>
        ) : (
          <div className="grid-2">
            <div className="panel stack">
              <div>
                <h1 className="mono">{run.id.slice(0, 8)}…</h1>
                <p className="muted">Full id: {run.id}</p>
              </div>
              <div className="row">
                <span className={`badge ${statusClass(run.status)}`}>{run.status}</span>
                <span className="badge">{run.trigger_type}</span>
              </div>
              {run.error ? <p className="error">{run.error}</p> : null}
              {exportName ? (
                <a
                  className="btn"
                  href={`${API_URL}/api/exports/${exportName}`}
                  onClick={(e) => {
                    e.preventDefault();
                    const auth = getStoredAuth();
                    fetch(`${API_URL}/api/exports/${exportName}`, {
                      headers: {
                        Authorization: `Bearer ${auth?.access_token}`,
                        "X-Org-Id": auth?.org_id || "",
                      },
                    })
                      .then((r) => r.blob())
                      .then((blob) => {
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = exportName;
                        a.click();
                        URL.revokeObjectURL(url);
                      });
                  }}
                >
                  Download export CSV
                </a>
              ) : null}
              <h2>Timeline</h2>
              <div className="timeline">
                {run.steps.map((step) => (
                  <div className="timeline-item" key={step.id}>
                    <div className={`dot ${statusClass(step.status)}`} />
                    <div>
                      <div className="row">
                        <strong>{step.step_key}</strong>
                        <span className={`badge ${statusClass(step.status)}`}>{step.status}</span>
                        <span className="mono muted">
                          try {step.attempt}/{step.max_attempts}
                        </span>
                      </div>
                      <div className="muted mono">{step.step_type}</div>
                      {step.error ? <div className="error">{step.error}</div> : null}
                      {step.output ? (
                        <pre className="mono muted" style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>
                          {JSON.stringify(step.output, null, 2).slice(0, 800)}
                        </pre>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="panel stack">
              <h2>Audit</h2>
              {audit.map((ev) => (
                <div key={ev.id} style={{ borderBottom: "1px solid var(--line)", paddingBottom: 10 }}>
                  <div className="mono">{ev.event_type}</div>
                  <div>{ev.message}</div>
                  <div className="muted">{new Date(ev.created_at).toLocaleString()}</div>
                </div>
              ))}
              {audit.length === 0 ? <p className="muted">No events yet.</p> : null}
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}
