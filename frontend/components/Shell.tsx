"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearAuth, getStoredAuth } from "@/lib/api";
import { useEffect, useState } from "react";

const links = [
  { href: "/dashboard", label: "Workflows" },
  { href: "/runs", label: "Runs" },
  { href: "/approvals", label: "Approvals" },
  { href: "/dead-letters", label: "Dead letters" },
  { href: "/audit", label: "Audit" },
  { href: "/settings", label: "Settings" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getStoredAuth()) {
      router.replace("/");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) {
    return (
      <div className="shell">
        <p className="muted">Loading console…</p>
      </div>
    );
  }

  const section =
    links.find((l) => pathname.startsWith(l.href))?.label?.toUpperCase() || "CONSOLE";

  return (
    <>
      <div className="chapter-band">
        <div className="inner">
          <strong>Relay</strong>
          <span>{section}</span>
        </div>
      </div>
      <div className="shell fade-in">
        <header className="topbar">
          <div className="brand">
            <strong>Relay</strong>
            <span>Durable workflow control plane</span>
          </div>
          <nav className="nav">
            {links.map((l) => (
              <Link key={l.href} href={l.href} className={pathname.startsWith(l.href) ? "active" : ""}>
                {l.label}
              </Link>
            ))}
            <button
              className="btn"
              onClick={() => {
                clearAuth();
                router.replace("/");
              }}
            >
              Sign out
            </button>
          </nav>
        </header>
        {children}
      </div>
    </>
  );
}

export function statusClass(status: string): string {
  if (["completed", "approved", "ok"].includes(status)) return "ok";
  if (["waiting_approval", "leased", "running", "ready", "pending"].includes(status)) return "wait";
  if (["failed", "dead_lettered", "rejected", "cancelled"].includes(status)) return "danger";
  return "warn";
}
