export class ApiError extends Error {
  code: string;
  status: number;
  constructor(message: string, code: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export async function api<T>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { ...((opts.headers as Record<string, string>) || {}) };
  const token = localStorage.getItem("ds_token");
  if (token) headers.Authorization = `Bearer ${token}`;
  let body = opts.body;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }
  const res = await fetch("/api" + path, { ...opts, headers, body });
  if (res.status === 401 && !path.startsWith("/auth/login")) {
    localStorage.removeItem("ds_token");
    window.dispatchEvent(new Event("ds-logout"));
  }
  if (!res.ok) {
    let message = res.statusText || `HTTP ${res.status}`;
    let code = "error";
    try {
      const j = await res.json();
      message = j.error?.message ?? (Array.isArray(j.detail) ? j.detail.map((d: any) => d.msg).join("; ") : j.detail) ?? message;
      code = j.error?.code ?? code;
    } catch { /* non-JSON error body */ }
    throw new ApiError(message, code, res.status);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json() as Promise<T>;
  return (await res.blob()) as unknown as T;
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}