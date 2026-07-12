import { getBrowserClient } from "@/lib/supabase/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface JobResult {
  title: string;
  company: string;
  location: string;
  url: string;
  score: number;
  note: string;
  salary: string | null;
  description: string;
  source: string;
}

export interface SearchResponse {
  jobs: JobResult[];
  total: number;
  query: string;
}

export interface ScoreResponse {
  score: number;
  note: string;
  title: string;
  company: string;
}

export interface TrackerJob {
  title: string;
  company: string;
  url: string;
  score: number;
  status: string;
  date_found: string;
  date_updated: string;
  notes: string;
}

export interface Profile {
  name: string;
  current_role: string;
  core_skills: string[];
  years_experience: number;
  seniority_keywords: string[];
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    const supabase = getBrowserClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
  } catch {}
  return {};
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

export async function searchJobs(params: {
  query: string;
  location?: string;
  threshold?: number;
  max_results?: number;
  require_visa?: boolean;
  exclude_companies?: string[];
}): Promise<SearchResponse> {
  return apiFetch("/api/search", {
    method: "POST",
    body: JSON.stringify({
      query: params.query,
      location: params.location || "Remote",
      threshold: params.threshold || 65,
      max_results: params.max_results || 10,
      require_visa: params.require_visa ?? true,
      exclude_companies: params.exclude_companies || [],
    }),
  });
}

export async function scoreJob(params: {
  title: string;
  description: string;
  company: string;
  location?: string;
}): Promise<ScoreResponse> {
  return apiFetch("/api/score", {
    method: "POST",
    body: JSON.stringify({
      title: params.title,
      description: params.description,
      company: params.company,
      location: params.location || "Remote",
    }),
  });
}

export async function getProfile(): Promise<Profile> {
  return apiFetch("/api/profile");
}

export async function getTracker(status?: string): Promise<{ jobs: TrackerJob[]; total: number }> {
  const qs = status ? `?status=${status}` : "";
  return apiFetch(`/api/tracker${qs}`);
}

export async function addToTracker(params: {
  title: string;
  company: string;
  url?: string;
  score?: number;
  description?: string;
  salary?: string;
  location?: string;
}): Promise<{ status: string; id: string | null }> {
  return apiFetch("/api/tracker/add", {
    method: "POST",
    body: JSON.stringify({
      title: params.title,
      company: params.company,
      url: params.url || "",
      score: params.score || 0,
      description: params.description || "",
      salary: params.salary || "",
      location: params.location || "",
    }),
  });
}

export async function updateTracker(params: {
  title: string;
  company: string;
  status: string;
  notes?: string;
}) {
  return apiFetch("/api/tracker/update", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function updateProfile(params: {
  name: string;
  current_role: string;
  core_skills: string[];
  years_experience: number;
}): Promise<Profile> {
  return apiFetch("/api/profile", {
    method: "PUT",
    body: JSON.stringify(params),
  });
}

export interface DigestPreferences {
  enabled: boolean;
  email: string;
}

export async function getDigestPreferences(): Promise<DigestPreferences> {
  return apiFetch("/api/digest/preferences");
}

export async function updateDigestPreferences(params: {
  enabled: boolean;
  email: string;
}): Promise<DigestPreferences> {
  return apiFetch("/api/digest/preferences", {
    method: "PUT",
    body: JSON.stringify(params),
  });
}
