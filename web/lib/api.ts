export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

// ---------- types ----------
export type Modality = "pdf" | "slide" | "video";
export type QType = "mcq" | "short" | "numerical";
export type Locator = { page?: number; slide?: number; t_start?: number; t_end?: number };

export type Citation = {
  unit_id: string;
  source_id: string;
  source_title: string;
  modality: Modality;
  locator: Locator;
  label: string;
  excerpt: string;
  asset_url: string | null;
  youtube_id: string | null;
};

export type Concept = { id: string; name: string; summary: string; prereqs: string[] };
export type Subtopic = { id: string; name: string; concepts: Concept[] };
export type Topic = { id: string; name: string; subtopics: Subtopic[] };
export type Edge = { concept_id: string; prereq_id: string };
export type ConceptsResponse = { topics: Topic[]; edges: Edge[] };

export type MasteryConcept = {
  concept_id: string;
  name: string;
  topic_id: string;
  topic_name: string;
  p_known: number;
  n_obs: number;
  due: boolean;
};
export type Mastery = { concepts: MasteryConcept[]; topics: { topic_id: string; name: string; mean: number }[] };
export type Recommendation = { concept_id: string; name: string; p_known: number; reason: string; units: Citation[] };

export type Question = {
  question_id: string;
  qtype: QType;
  stem: string;
  options: { key: string; text: string }[] | null;
  concept_id: string;
  concept_name: string;
  difficulty: number;
};
export type Feedback = {
  correct: boolean;
  score: number;
  correct_answer: string;
  explanation: string;
  misconception: string | null;
  citations: Citation[];
  p_before: number;
  p_after: number;
  mastery_delta: number;
};

export type ChatResponse = {
  declined: boolean;
  message: string | null;
  sentences: { text: string; cites: string[] }[];
  citations: Citation[];
  outside: string[];
  top_sim: number;
  retrieved: string[];
  check_question: Question | null;
};
export type ChatRequest = { student_id?: string; question: string; allow_outside: boolean; lang: "en" | "hi" };

export type AssessKind = "diagnostic" | "quiz" | "mock_exam";
export type Mix = Partial<Record<QType, number>>;
export type AssessmentRequest = { student_id: string; kind: AssessKind; scope: string[]; n: number; mix?: Mix };
export type Assessment = { assessment_id: string; kind: AssessKind; questions: Question[]; shortfall: number };

export type Report = {
  answered: number;
  total: number;
  correct: number;
  score_by_topic: { topic_id: string; name: string; correct: number; total: number; score: number }[];
  mastery_changes: { concept_id: string; name: string; before: number; after: number; delta: number }[];
  weak_topics: { topic_id: string; name: string; mastery: number }[];
  misconceptions: { label: string; count: number }[];
  next_units: (Citation & { concept_id: string })[];
};

export type SourceStatus = "pending" | "ingesting" | "ready" | "failed";
export type Source = {
  id: string;
  title: string;
  modality: Modality;
  license: string | null;
  status: SourceStatus;
  error: string | null;
  created_at: string;
  units: number;
};

// ---------- transport ----------
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_URL + path, init);
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_URL}`);
  }
  if (!res.ok) {
    let detail = res.statusText || `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (body?.detail) detail = JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body: keep status text */
    }
    throw new ApiError(res.status, detail);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError && e.status === 429) return "Too many requests, wait a moment";
  return e instanceof Error ? e.message : "Something went wrong";
}

const send = (method: string, body: unknown, headers: Record<string, string> = {}): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json", ...headers },
  body: JSON.stringify(body),
});

// ---------- endpoints ----------
export const api = {
  concepts: () => request<ConceptsResponse>("/concepts"),
  createStudent: (name?: string) => request<{ student_id: string }>("/students", send("POST", { name })),
  intake: (id: string, body: { goal?: string; exam_date?: string; familiarity: Record<string, 0 | 1 | 2> }) =>
    request<{ priors_set: number }>(`/students/${id}/intake`, send("POST", body)),
  mastery: (id: string) => request<Mastery>(`/students/${id}/mastery`),
  recommendations: (id: string) => request<Recommendation[]>(`/students/${id}/recommendations`),
  chat: (body: ChatRequest) => request<ChatResponse>("/chat", send("POST", body)),
  chatCheck: (body: { student_id: string; question_id: string; response: string }) =>
    request<Feedback>("/chat/check", send("POST", body)),
  createAssessment: (body: AssessmentRequest) => request<Assessment>("/assessments", send("POST", body)),
  answer: (id: string, body: { question_id: string; response: string }) =>
    request<Feedback>(`/assessments/${id}/answer`, send("POST", body)),
  report: (id: string) => request<Report>(`/assessments/${id}/report`),
  sources: () => request<Source[]>("/sources"),
  uploadSource: (form: FormData, token: string) =>
    request<{ source_id: string; status: string }>("/sources", {
      method: "POST",
      headers: { "X-Admin-Token": token },
      body: form,
    }),
  addUrlSource: (body: { url: string; title: string; license?: string }, token: string) =>
    request<{ source_id: string; status: string }>("/sources/url", send("POST", body, { "X-Admin-Token": token })),
};
