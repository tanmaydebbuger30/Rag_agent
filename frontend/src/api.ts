export type Status = "met" | "partially_met" | "not_met" | "insufficient_evidence";

export interface Citation {
  chunk_id: string;
  filename: string;
  page: number | null;
  heading: string | null;
  quote: string;
}

export interface CriterionResult {
  criterion_id: string;
  text: string;
  satisfied: boolean;
  citations: Citation[];
}

export interface Review {
  decision: "accept" | "override";
  status: Status;
  note: string;
  reviewer: string;
  reviewed_at: string;
}

export interface Guidance {
  chunk_id: string;
  citation: string;
  heading: string;
  excerpt: string;
}

export interface Finding {
  control_id: string;
  control_name: string;
  citation: string;
  requirement_type: "required" | "addressable";
  requirement_text: string;
  safeguard_category: string | null;
  status: Status;
  basis: "implemented" | "documented_alternative" | null;
  rationale: string;
  criteria: CriterionResult[];
  contradictions: Citation[];
  gaps: string[];
  remediation: string[];
  guidance: Guidance[];
  assessor: "rules" | "llm";
  confidence: "low" | "medium" | "high" | null;
  verification: { passed: boolean; checked_citations: number; problems: string[] };
  needs_review: boolean;
  review_reasons: string[];
  review: Review | null;
}

export interface Summary {
  total: number;
  by_status: Partial<Record<Status, number>>;
  needs_review: number;
  assessor: string;
}

export interface Assessment {
  id: string;
  org_name: string;
  created_at: string;
  assessor: string;
  documents: { document_id: string; filename: string; bytes: number; chunks: number }[];
  review_status: "pending_review" | "complete";
  findings: Finding[];
  review_queue: string[];
  summary: Summary;
  trace: { node: string; ms: number; [k: string]: unknown }[];
  evidence_hits: Record<string, { chunk_id: string; score: number; signals: Record<string, { rank: number; score: number }> }[]>;
}

export type AssessmentListItem = Pick<Assessment, "id" | "org_name" | "created_at" | "assessor" | "summary" | "documents" | "review_status">;

export interface EvidenceChunk {
  chunk_id: string;
  document_id: string;
  filename: string;
  heading: string | null;
  page: number | null;
  text: string;
}

export interface KbChunk {
  chunk_id: string;
  source: string;
  authority_level: "regulation" | "official_guidance" | "supporting_guidance";
  heading: string;
  heading_path: string[];
  control_ids: string[];
  in_scope_v1: boolean;
  page_start: number | null;
  page_end: number | null;
  text: string;
  citation?: string;
}

export interface ControlInfo {
  control_id: string;
  parent_id: string | null;
  control_name: string;
  level: string;
  requirement_type: "required" | "addressable";
  requirement_text: string;
  citation: string;
  aliases: string[];
  criteria: { id: string; text: string; sources: string[] }[];
  guidance: { chunk_id: string; citation: string; heading: string; text: string }[];
}

export interface SearchResult {
  query: string;
  expanded_query: string;
  identified_controls: string[];
  matched_aliases: Record<string, string[]>;
  signals_used: string[];
  chunks: { chunk: KbChunk; citation: string; rrf_score: number; signals: Record<string, { rank: number; score: number }> }[];
  controls: { control_id: string; control_name: string; in_scope_v1: boolean; score: number }[];
}

export interface AppConfig {
  default_assessor: "rules" | "llm";
  llm_available: boolean;
  llm_model: string;
  dense_enabled: boolean;
  supported_files: string[];
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  config: () => request<AppConfig>("/api/config"),
  controls: () => request<ControlInfo[]>("/api/controls"),
  kbChunk: (id: string) => request<KbChunk>(`/api/kb/chunks/${encodeURIComponent(id)}`),
  search: (q: string, inScopeOnly: boolean) =>
    request<SearchResult>(`/api/search?q=${encodeURIComponent(q)}&k=6&in_scope_only=${inScopeOnly}`),
  sample: () => request<{ org_name: string; files: { filename: string; text: string }[] }>("/api/sample-evidence"),
  assessments: () => request<AssessmentListItem[]>("/api/assessments"),
  assessment: (id: string) => request<Assessment>(`/api/assessments/${id}`),
  evidence: (id: string) => request<EvidenceChunk[]>(`/api/assessments/${id}/evidence`),
  create: (form: FormData) => request<Assessment>("/api/assessments", { method: "POST", body: form }),
  review: (id: string, controlId: string, body: { decision: "accept" | "override"; status?: Status; note: string; reviewer: string }) =>
    request<Assessment>(`/api/assessments/${id}/findings/${encodeURIComponent(controlId)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  reportUrl: (id: string) => `/api/assessments/${id}/report.md`,
};

export const STATUS_LABEL: Record<Status, string> = {
  met: "Met",
  partially_met: "Partially met",
  not_met: "Not met",
  insufficient_evidence: "Insufficient evidence",
};

export function finalStatus(f: Finding): Status {
  return f.review?.decision === "override" ? f.review.status : f.status;
}
