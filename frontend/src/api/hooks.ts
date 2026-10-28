import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { AuditEvent, Case, Doc, DocDetail, ExtractionStats, Field, Finding, Health, Job, Risk, Rule, User } from "./types";

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health"), staleTime: 60_000 });
export const useRules = () => useQuery({ queryKey: ["rules"], queryFn: () => api<Rule[]>("/rules"), staleTime: 300_000 });
export const useCases = (q = "", status = "") =>
  useQuery({ queryKey: ["cases", q, status], queryFn: () => api<Case[]>(`/cases?${new URLSearchParams({ ...(q ? { q } : {}), ...(status ? { status } : {}) })}`) });
export const useCase = (id: number) => useQuery({ queryKey: ["case", id], queryFn: () => api<Case>(`/cases/${id}`), enabled: Number.isFinite(id) });
export const useDocuments = (id: number) => useQuery({ queryKey: ["documents", id], queryFn: () => api<Doc[]>(`/cases/${id}/documents`), enabled: Number.isFinite(id) });
export const useDocument = (docId: number | undefined) => useQuery({ queryKey: ["document", docId], queryFn: () => api<DocDetail>(`/documents/${docId}`), enabled: !!docId });
export const useFields = (docId: number | undefined) => useQuery({ queryKey: ["fields", docId], queryFn: () => api<Field[]>(`/documents/${docId}/fields`), enabled: !!docId });
export const useFindings = (id: number, engine?: string) =>
  useQuery({ queryKey: ["findings", id, engine ?? "all"], queryFn: () => api<Finding[]>(`/cases/${id}/findings${engine ? `?engine=${engine}` : ""}`), enabled: Number.isFinite(id) });
export const useRisk = (id: number) => useQuery({ queryKey: ["risk", id], queryFn: () => api<Risk>(`/cases/${id}/risk`), enabled: Number.isFinite(id) });
export const useJobs = (id: number) => useQuery({ queryKey: ["jobs", id], queryFn: () => api<Job[]>(`/cases/${id}/jobs`), enabled: Number.isFinite(id) });
export const useStats = (id: number) => useQuery({ queryKey: ["stats", id], queryFn: () => api<ExtractionStats>(`/cases/${id}/extraction-stats`), enabled: Number.isFinite(id) });
export const useAudit = () => useQuery({ queryKey: ["audit"], queryFn: () => api<AuditEvent[]>("/audit/events?limit=500") });
export const useUsers = (enabled: boolean) => useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/auth/users"), enabled });
export const usePageImage = (docId: number | undefined, page: number) =>
  useQuery({
    queryKey: ["page", docId, page],
    enabled: !!docId,
    staleTime: Infinity,
    queryFn: async () => URL.createObjectURL(await api<Blob>(`/documents/${docId}/pages/${page}`)),
  });
import type { SecurityScan } from "./types";
export const useSecurity = (docId: number | undefined) => useQuery({ queryKey: ["security", docId], queryFn: () => api<SecurityScan>(`/documents/${docId}/security`), enabled: !!docId, staleTime: 60_000 });
export const useAuditEvents = (enabled: boolean) => useQuery({ queryKey: ["audit"], queryFn: () => api<AuditEvent[]>("/audit/events?limit=500"), enabled });
