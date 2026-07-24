import { API_BASE_URL, ApiError, apiRequest, clearSession, getStoredToken } from "./http";
import type {
  AskMessageResponse,
  ConversationDetail,
  ConversationListResponse,
  ConversationSummary,
  DocumentDetail,
  DocumentListResponse,
  DocumentPreview,
  HealthResponse,
  IngestionJob,
  ReadyResponse,
  TokenResponse,
  User,
} from "../types";

export { API_BASE_URL };

export function fetchHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("/health");
}

export function fetchReady(): Promise<ReadyResponse> {
  return apiRequest<ReadyResponse>("/ready", { acceptStatuses: [503] });
}

export function registerUser(input: {
  email: string;
  password: string;
  full_name: string;
}): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/api/v1/auth/register", {
    method: "POST",
    json: input,
    token: null,
  });
}

export function loginUser(input: { email: string; password: string }): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    json: input,
    token: null,
  });
}

export function fetchMe(): Promise<User> {
  return apiRequest<User>("/api/v1/auth/me");
}

export function listDocuments(params?: {
  page?: number;
  page_size?: number;
  department?: string;
  category?: string;
  status?: string;
  q?: string;
  sort_by?: string;
  sort_order?: string;
}): Promise<DocumentListResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  if (params?.department) query.set("department", params.department);
  if (params?.category) query.set("category", params.category);
  if (params?.status) query.set("status", params.status);
  if (params?.q) query.set("q", params.q);
  if (params?.sort_by) query.set("sort_by", params.sort_by);
  if (params?.sort_order) query.set("sort_order", params.sort_order);
  const suffix = query.toString() ? `?${query}` : "";
  return apiRequest<DocumentListResponse>(`/api/v1/documents${suffix}`);
}

export function getDocument(documentId: string): Promise<DocumentDetail> {
  return apiRequest<DocumentDetail>(`/api/v1/documents/${documentId}`);
}

export function getDocumentPreview(documentId: string): Promise<DocumentPreview> {
  return apiRequest<DocumentPreview>(`/api/v1/documents/${documentId}/preview`);
}

export async function uploadDocument(input: {
  file: File;
  title: string;
  department: string;
  category: string;
  onProgress?: (percent: number) => void;
}): Promise<DocumentDetail> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("title", input.title);
  form.append("department", input.department);
  form.append("category", input.category);

  if (!input.onProgress) {
    return apiRequest<DocumentDetail>("/api/v1/documents", {
      method: "POST",
      body: form,
    });
  }

  return uploadWithProgress("/api/v1/documents", form, input.onProgress);
}

function uploadWithProgress(
  path: string,
  form: FormData,
  onProgress: (percent: number) => void,
): Promise<DocumentDetail> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${path}`);
    const token = getStoredToken();
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as DocumentDetail);
        return;
      }
      let message = `Request failed (${xhr.status})`;
      let code: string | undefined;
      try {
        const payload = JSON.parse(xhr.responseText) as { detail?: string; code?: string };
        message = payload.detail || message;
        code = payload.code;
      } catch {
        // ignore
      }
      if (xhr.status === 401) {
        clearSession();
      }
      reject(new ApiError(message, xhr.status, code));
    };
    xhr.onerror = () => reject(new ApiError("Upload failed", 0));
    xhr.send(form);
  });
}

export function deleteDocument(documentId: string): Promise<void> {
  return apiRequest<void>(`/api/v1/documents/${documentId}`, { method: "DELETE" });
}

export function reprocessDocument(documentId: string): Promise<DocumentDetail> {
  return apiRequest<DocumentDetail>(`/api/v1/documents/${documentId}/reprocess`, {
    method: "POST",
  });
}

export function listConversations(): Promise<ConversationListResponse> {
  return apiRequest<ConversationListResponse>("/api/v1/conversations");
}

export function createConversation(title?: string): Promise<ConversationSummary> {
  return apiRequest<ConversationSummary>("/api/v1/conversations", {
    method: "POST",
    json: { title: title ?? null },
  });
}

export function getConversation(conversationId: string): Promise<ConversationDetail> {
  return apiRequest<ConversationDetail>(`/api/v1/conversations/${conversationId}`);
}

export function deleteConversation(conversationId: string): Promise<void> {
  return apiRequest<void>(`/api/v1/conversations/${conversationId}`, { method: "DELETE" });
}

export function askQuestion(
  conversationId: string,
  content: string,
  filters?: { department?: string; category?: string; document_id?: string },
): Promise<AskMessageResponse> {
  return apiRequest<AskMessageResponse>(`/api/v1/conversations/${conversationId}/messages`, {
    method: "POST",
    json: {
      content,
      department: filters?.department || null,
      category: filters?.category || null,
      document_id: filters?.document_id || null,
    },
  });
}

export function adminAccessCheck(): Promise<{ status: string; role: string }> {
  return apiRequest<{ status: string; role: string }>("/api/v1/admin/access-check");
}

export type AdminAnalytics = {
  total_users: number;
  total_documents: number;
  total_indexed_chunks: number;
  total_conversations: number;
  total_questions: number;
  completed_ingestion_jobs: number;
  failed_ingestion_jobs_count: number;
  average_e2e_latency_ms: number | null;
  average_embedding_latency_ms: number | null;
  average_vector_search_latency_ms: number | null;
  average_llm_latency_ms: number | null;
  average_response_latency_ms: number | null;
  documents_by_status: Array<{ status: string; count: number }>;
  documents_by_department: Array<{ name: string; count: number }>;
  documents_by_category: Array<{ category: string; count: number }>;
  questions_over_time: Array<{ date: string; count: number }>;
  most_cited_documents: Array<{
    document_id: string | null;
    document_title: string;
    citation_count: number;
  }>;
  recent_uploads: Array<{
    id: string;
    title: string;
    department: string;
    category: string;
    processing_status: string;
    created_at: string;
  }>;
  failed_ingestion_jobs: Array<{
    id: string;
    document_id: string;
    attempt_number: number;
    error_message: string | null;
    created_at: string;
  }>;
  most_used_categories: Array<{ category: string; count: number }>;
  recent_system_errors: Array<{
    id: string;
    action: string;
    resource_type: string | null;
    resource_id: string | null;
    error_message: string | null;
    created_at: string;
  }>;
  range_start: string | null;
  range_end: string | null;
};

export function fetchAdminAnalytics(params?: {
  start?: string;
  end?: string;
}): Promise<AdminAnalytics> {
  const query = new URLSearchParams();
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  const suffix = query.toString() ? `?${query}` : "";
  return apiRequest<AdminAnalytics>(`/api/v1/admin/analytics${suffix}`);
}

export function fetchAuditLogs(page = 1): Promise<{
  items: Array<{
    id: string;
    action: string;
    success: boolean;
    actor_user_id: string | null;
    resource_type: string | null;
    resource_id: string | null;
    error_message: string | null;
    created_at: string;
  }>;
  total: number;
}> {
  return apiRequest(`/api/v1/admin/audit-logs?page=${page}&page_size=20`);
}

export function fetchIngestionJobs(params?: {
  status?: string;
  limit?: number;
}): Promise<{
  items: Array<{
    id: string;
    document_id: string;
    status: string;
    attempt_number: number;
    error_message: string | null;
    embedding_latency_ms: number | null;
    duration_ms: number | null;
    created_at: string;
    started_at: string | null;
    completed_at: string | null;
  }>;
  total: number;
}> {
  const query = new URLSearchParams();
  query.set("limit", String(params?.limit ?? 20));
  if (params?.status) query.set("status", params.status);
  return apiRequest(`/api/v1/admin/ingestion-jobs?${query}`);
}

export function recoverStaleIngestionJobs(): Promise<{
  recovered: number;
  job_ids: string[];
  stale_after_minutes: number;
}> {
  return apiRequest("/api/v1/admin/ingestion-jobs/recover-stale", { method: "POST" });
}

export function listDocumentIngestionJobs(documentId: string): Promise<{
  items: IngestionJob[];
  total: number;
}> {
  return apiRequest(`/api/v1/documents/${documentId}/ingestion-jobs`);
}
