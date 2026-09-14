"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getStoredAuth, storeAuth, TokenBundle } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@relay.local");
  const [password, setPassword] = useState("RelayDemo2026!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getStoredAuth()) router.replace("/dashboard");
  }, [router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const bundle = await api<TokenBundle>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      storeAuth(bundle);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="hero-login">
      <form className="panel login-card stack fade-in" onSubmit={onSubmit}>
        <div>
          <h1>Relay</h1>
          <p className="muted">Sign in to the durable workflow console.</p>
        </div>
        <label className="stack">
          <span className="muted">Email</span>
          <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="stack">
          <span className="muted">Password</span>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button className="btn primary" disabled={loading} type="submit">
          {loading ? "Signing in…" : "Enter console"}
        </button>
      </form>
    </div>
  );
}
