import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api } from "./api/client";
import type { User } from "./api/types";

interface AuthValue { user: User | null; loading: boolean; login: (email: string, password: string) => Promise<void>; logout: () => void }
const Ctx = createContext<AuthValue>({ user: null, loading: true, login: async () => {}, logout: () => {} });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const t = localStorage.getItem("ds_token");
    if (!t) { setLoading(false); return; }
    api<User>("/auth/me").then(setUser).catch(() => localStorage.removeItem("ds_token")).finally(() => setLoading(false));
    const h = () => setUser(null);
    window.addEventListener("ds-logout", h);
    return () => window.removeEventListener("ds-logout", h);
  }, []);
  const login = async (email: string, password: string) => {
    const r = await api<{ access_token: string }>("/auth/login", { method: "POST", json: { email, password } });
    localStorage.setItem("ds_token", r.access_token);
    setUser(await api<User>("/auth/me"));
  };
  const logout = () => { localStorage.removeItem("ds_token"); setUser(null); };
  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="p-10 text-sm text-slate-500">Loading session…</div>;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  return <>{children}</>;
}