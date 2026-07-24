export type UserRole = "admin" | "employee";

export type ApiErrorBody = {
  detail: string;
  code?: string;
};

export type User = {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
};

export type ProcessingStatus = "pending" | "processing" | "completed" | "failed";

export type IngestionStage =
  | "uploaded"
  | "extracting"
  | "chunking"
  | "embedding"
  | "indexing"
  | "completed"
  | "failed";

export type DocumentVersion = {
  id: string;
  version_number: number;
  original_filename: string;
  file_type: "pdf" | "docx" | "txt";
  content_type: string;
  file_size_bytes: number;
  checksum_sha256: string;
  uploaded_by_id: string;
  created_at: string;
};

export type IngestionJob = {
  id: string;
  document_version_id: string;
  status: "pending" | "running" | "completed" | "failed";
  attempt_number: number;
  error_message: string | null;
  embedding_latency_ms?: number | null;
  duration_ms?: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type UploaderInfo = {
  id: string;
  email: string;
  full_name: string;
};

export type DocumentSummary = {
  id: string;
  title: string;
  department: string;
  category: string;
  current_version: number;
  processing_status: ProcessingStatus;
  ingestion_stage: IngestionStage;
  processing_error: string | null;
  embedding_provider?: string | null;
  embedding_model?: string | null;
  uploaded_by_id: string;
  file_type: "pdf" | "docx" | "txt" | null;
  file_size_bytes: number | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
};

export type DocumentDetail = DocumentSummary & {
  uploaded_by: UploaderInfo | null;
  page_count: number | null;
  embedding_count: number;
  versions: DocumentVersion[];
  latest_ingestion_job: IngestionJob | null;
};

export type DocumentPreview = {
  document_id: string;
  title: string;
  file_type: "pdf" | "docx" | "txt" | null;
  page_count: number | null;
  chunk_count: number;
  preview_text: string;
  chunks: Array<{
    chunk_index: number;
    page_number: number | null;
    content: string;
    char_count: number;
  }>;
};

export type DocumentListResponse = {
  items: DocumentSummary[];
  total: number;
  page: number;
  page_size: number;
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type Citation = {
  id: string;
  chunk_id: string | null;
  document_id: string | null;
  document_title: string;
  page_number: number | null;
  chunk_index: number | null;
  relevance_score: number;
  rank: number;
  snippet: string;
};

export type RetrievalMeta = {
  max_relevance: number | null;
  chunks_retrieved: number;
  supporting_chunks: number;
  retrieval_latency_ms: number | null;
  embedding_latency_ms: number | null;
  llm_latency_ms: number | null;
  min_relevance_threshold: number | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  retrieval_top_k: number | null;
  retrieval_min_score: number | null;
  max_retrieval_score: number | null;
  grounded: boolean | null;
  insufficient_context: boolean | null;
  answer_status?: "grounded" | "insufficient_context" | "demo" | null;
  suggestion?: string | null;
  embedding_latency_ms?: number | null;
  vector_search_latency_ms?: number | null;
  llm_latency_ms: number | null;
  llm_model: string | null;
  created_at: string;
  citations: Citation[];
  retrieval?: RetrievalMeta | null;
  embedding_provider_mismatch?: boolean;
  mismatched_documents?: string[];
};

export type ConversationDetail = ConversationSummary & {
  messages: ChatMessage[];
};

export type ConversationListResponse = {
  items: ConversationSummary[];
  total: number;
};

export type AskMessageResponse = {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
};

export type HealthResponse = {
  status: "ok";
  service: string;
  version: string;
  environment: string;
};

export type ReadyResponse = {
  status: "ready" | "degraded" | "not_ready";
  environment: string;
  version: string;
  demo_mode?: boolean;
  llm_provider?: string | null;
  embedding_provider?: string | null;
  checks: Array<{
    name: string;
    status: "ok" | "degraded" | "unavailable";
    detail: string | null;
  }>;
};
