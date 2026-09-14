const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type TokenBundle = {
  access_token: string;
  refresh_token: string;
  org_id: string;
  org_slug: string;
};

export function getStoredAuth(): TokenBundle | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("relay_auth");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as TokenBundle;
  } catch {
    return null;
  }
}

export function storeAuth(bundle: TokenBundle) {
  localStorage.setItem("relay_auth", JSON.stringify(bundle));
}

export function clearAuth() {
  localStorage.removeItem("relay_auth");
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  auth?: TokenBundle | null
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = auth ?? getStoredAuth();
  if (token?.access_token) {
    headers.set("Authorization", `Bearer ${token.access_token}`);
    headers.set("X-Org-Id", token.org_id);
  }
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export { API_URL };
