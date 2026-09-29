export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

export type MemoryDetail = {
  text?: string;
  score: number | null;
  tags: string[];
  document_id?: string | null;
  trust_tier?: string;
};

export type MemoryDocument = {
  document_id: string;
  tags: string[];
  trust_tier: string;
  trust_tiers?: string[];
  created_at: string | null;
  text_length: number | null;
};

export type PoisoningDemoResult = {
  document_id: string;
  stored: boolean;
  trust_tier: string;
  telemetry_indicators: {
    username: string | null;
    user_agent_family: string | null;
    remark_length: number;
    remark_fingerprint: string | null;
  };
  baseline_response: string;
  protected_response: string;
  raw_remark_excluded_from_protected_prompt: boolean;
};

export type AnalyzeResult = {
  incident_id: string;
  title: string;
  description: string;
  response: string;
  memories_used: string[];
  memory_details: MemoryDetail[];
  hindsight_available: boolean;
  severity: Severity;
  category: string;
  similar_incidents: number;
  estimated_minutes: number | null;
  memory_count: number;
  analysis_ms: number;
  concise: boolean;
};

export type Severity = "Critical" | "High" | "Medium" | "Low";

export type Incident = {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  category: string;
  status: "open" | "resolved";
  created_at: string;
  resolved_at?: string;
  outcome?: string;
  memories_recalled?: number;
  similar_incidents?: number;
  resolution_minutes?: number | null;
  analyst_feedback?: string;
  seeded?: boolean;
  memory_revoked?: boolean;
  memory_details?: MemoryDetail[];
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const body = data && typeof data === "object" ? data as { detail?: unknown; message?: unknown } : null;
    const detail = body?.detail ?? body?.message;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => {
            if (!item || typeof item !== "object") return String(item);
            const issue = item as { loc?: unknown[]; msg?: unknown };
            const location = Array.isArray(issue.loc) ? issue.loc.join(".") : "";
            return [location, typeof issue.msg === "string" ? issue.msg : "Invalid value"].filter(Boolean).join(": ");
          }).join("; ")
        : `Request failed (${res.status})`;
    throw new Error(message);
  }
  if (data === null) throw new Error("The server returned an empty or invalid response.");
  return data as T;
}
