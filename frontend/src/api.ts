// Typed client for the ProjectBuddy JSON API (/api/v1).
// Runs same-origin behind Flask-Login, so read endpoints authenticate with
// the session cookie — no token juggling in the browser.

export interface Owner {
  id: number;
  first_name: string;
  last_name: string;
  department: string | null;
  avatar_url: string | null;
}

export interface Project {
  id: number;
  title: string;
  description: string;
  course: string | null;
  status: string;
  team_size: number;
  member_count: number;
  spots_left: number;
  deadline: string | null;
  created_at: string;
  owner: Owner;
  tags: string[];
  required_skills: string[];
}

export interface Page<T> {
  items: T[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
}

export interface Recommendation {
  project: Project;
  fit_percent: number;
}

export interface RecommendationsResponse {
  items: Recommendation[];
  variant: string | null;
}

export interface ProjectQuery {
  q?: string;
  tag?: string;
  status?: string;
  page?: number;
  per_page?: number;
}

/** Serialize query params, skipping empty/undefined values. */
export function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function getJson<T>(url: string): Promise<T> {
  const resp = await fetch(url, { credentials: "same-origin" });
  if (!resp.ok) {
    throw new Error(`API ${resp.status}: ${url}`);
  }
  return resp.json() as Promise<T>;
}

export function fetchProjects(query: ProjectQuery): Promise<Page<Project>> {
  return getJson(`/api/v1/projects${buildQuery({ ...query })}`);
}

export function fetchRecommendations(): Promise<RecommendationsResponse> {
  return getJson("/api/v1/recommendations");
}
