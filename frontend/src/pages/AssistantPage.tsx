import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import {
  askQuestion,
  createConversation,
  deleteConversation,
  fetchReady,
  getConversation,
  listConversations,
  listDocuments,
} from "../api/client";
import { ApiError } from "../api/http";
import { suggestedQuestionsForDocuments } from "../assistant/starterQuestions";
import { CitationList } from "../components/CitationList";
import { ConfirmBanner } from "../components/ConfirmBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { RetrievalDetails } from "../components/RetrievalDetails";
import { SkeletonStack } from "../components/SkeletonStack";
import type { ChatMessage, Citation, ConversationSummary, DocumentSummary } from "../types";

type AskFilters = {
  department: string;
  category: string;
  document_id: string;
};

type PendingAsk = {
  content: string;
  filters: AskFilters;
};

export function AssistantPage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [department, setDepartment] = useState("");
  const [category, setCategory] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingThread, setLoadingThread] = useState(false);
  const [phase, setPhase] = useState<"idle" | "retrieving" | "generating">("idle");
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);
  const [pendingRetry, setPendingRetry] = useState<PendingAsk | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [activeEmbeddingProvider, setActiveEmbeddingProvider] = useState<string | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  const activeTitle = useMemo(
    () => conversations.find((item) => item.id === activeId)?.title ?? "Assistant",
    [conversations, activeId],
  );

  const completedDocuments = useMemo(
    () => documents.filter((doc) => doc.processing_status === "completed"),
    [documents],
  );

  const starterQuestions = useMemo(
    () => suggestedQuestionsForDocuments(completedDocuments),
    [completedDocuments],
  );

  const mismatchedDocuments = useMemo(() => {
    if (!activeEmbeddingProvider) return [];
    return completedDocuments.filter(
      (doc) =>
        doc.embedding_provider != null && doc.embedding_provider !== activeEmbeddingProvider,
    );
  }, [completedDocuments, activeEmbeddingProvider]);

  useEffect(() => {
    void bootstrap().catch((err: unknown) => {
      setError(err instanceof ApiError ? err.message : "Failed to load assistant");
      setLoadingList(false);
    });
  }, []);

  useEffect(() => {
    const node = threadRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [messages, phase]);

  async function bootstrap() {
    setLoadingList(true);
    const [conversationResult, documentResult, ready] = await Promise.all([
      listConversations(),
      listDocuments({ page: 1, page_size: 100, status: "completed" }),
      fetchReady().catch(() => null),
    ]);
    setDocuments(documentResult.items);
    setConversations(conversationResult.items);
    setDemoMode(Boolean(ready?.demo_mode));
    setActiveEmbeddingProvider(ready?.embedding_provider ?? null);
    const nextId = conversationResult.items[0]?.id ?? null;
    setActiveId(nextId);
    if (nextId) {
      setLoadingThread(true);
      const detail = await getConversation(nextId);
      setMessages(detail.messages);
      setLoadingThread(false);
    } else {
      setMessages([]);
    }
    setLoadingList(false);
  }

  async function refreshList(selectId?: string | null) {
    const result = await listConversations();
    setConversations(result.items);
    const nextId = selectId === undefined ? activeId : selectId;
    const resolved = nextId ?? result.items[0]?.id ?? null;
    setActiveId(resolved);
    if (resolved) {
      setLoadingThread(true);
      const detail = await getConversation(resolved);
      setMessages(detail.messages);
      setLoadingThread(false);
    } else {
      setMessages([]);
    }
  }

  async function onSelect(id: string) {
    setActiveId(id);
    setError(null);
    setSelectedCitationId(null);
    setConfirmDeleteId(null);
    setLoadingThread(true);
    try {
      const detail = await getConversation(id);
      setMessages(detail.messages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to open conversation");
    } finally {
      setLoadingThread(false);
    }
  }

  async function onNewConversation() {
    setBusy(true);
    setError(null);
    setSelectedCitationId(null);
    setConfirmDeleteId(null);
    try {
      const created = await createConversation();
      await refreshList(created.id);
      setMessages([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create conversation");
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteConversation(id: string) {
    setBusy(true);
    setError(null);
    try {
      await deleteConversation(id);
      setConfirmDeleteId(null);
      if (activeId === id) {
        setActiveId(null);
        setMessages([]);
      }
      await refreshList(activeId === id ? null : activeId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitQuestion(content: string, filters: AskFilters) {
    const trimmed = content.trim();
    if (!trimmed || busy) return;

    setBusy(true);
    setError(null);
    setPendingRetry(null);
    setPhase("retrieving");
    setQuestion("");

    const optimisticId = `local-user-${Date.now()}`;
    const optimistic: ChatMessage = {
      id: optimisticId,
      role: "user",
      content: trimmed,
      retrieval_top_k: null,
      retrieval_min_score: null,
      max_retrieval_score: null,
      grounded: null,
      insufficient_context: null,
      llm_latency_ms: null,
      llm_model: null,
      created_at: new Date().toISOString(),
      citations: [],
    };
    setMessages((prev) => [...prev, optimistic]);

    try {
      let conversationId = activeId;
      if (!conversationId) {
        const created = await createConversation(trimmed.slice(0, 80));
        conversationId = created.id;
        setActiveId(created.id);
      }

      setPhase("generating");
      const result = await askQuestion(conversationId, trimmed, {
        department: filters.department || undefined,
        category: filters.category || undefined,
        document_id: filters.document_id || undefined,
      });
      setMessages((prev) => [
        ...prev.filter((message) => message.id !== optimisticId),
        result.user_message,
        result.assistant_message,
      ]);
      const list = await listConversations();
      setConversations(list.items);
    } catch (err) {
      setMessages((prev) => prev.filter((message) => message.id !== optimisticId));
      setQuestion(trimmed);
      setPendingRetry({ content: trimmed, filters });
      setError(err instanceof ApiError ? err.message : "Failed to get an answer");
    } finally {
      setBusy(false);
      setPhase("idle");
    }
  }

  function currentFilters(): AskFilters {
    return { department, category, document_id: documentId };
  }

  function onAsk(event: FormEvent) {
    event.preventDefault();
    void submitQuestion(question, currentFilters());
  }

  function onStarter(prompt: string) {
    setQuestion(prompt);
    void submitQuestion(prompt, currentFilters());
  }

  function onRetry() {
    if (!pendingRetry) return;
    void submitQuestion(pendingRetry.content, pendingRetry.filters);
  }

  function onCitationSelect(citation: Citation) {
    setSelectedCitationId((current) => (current === citation.id ? null : citation.id));
  }

  return (
    <section className="assistant-layout">
      <aside className="panel conversation-rail" aria-label="Conversation list">
        <div className="panel-heading compact">
          <h2>Conversations</h2>
          <button
            className="btn primary"
            type="button"
            disabled={busy}
            onClick={() => void onNewConversation()}
          >
            New
          </button>
        </div>

          {loadingList ? (
          <SkeletonStack rows={4} label="Loading conversations" />
        ) : (
          <ul className="conversation-list">
            {conversations.map((item) => (
              <li key={item.id} className="conversation-item">
                <button
                  type="button"
                  className={item.id === activeId ? "active" : ""}
                  onClick={() => void onSelect(item.id)}
                  aria-current={item.id === activeId ? "true" : undefined}
                >
                  <span className="conversation-title">{item.title}</span>
                  <span className="conversation-date muted">{formatDate(item.updated_at)}</span>
                </button>
                <button
                  type="button"
                  className="btn ghost conversation-delete"
                  aria-label={`Delete ${item.title}`}
                  disabled={busy}
                  onClick={() => setConfirmDeleteId(item.id)}
                >
                  ×
                </button>
              </li>
            ))}
            {!conversations.length && (
              <li className="muted empty-rail">No conversations yet. Ask a question to start.</li>
            )}
          </ul>
        )}

        {confirmDeleteId && (
          <ConfirmBanner
            title="Delete this conversation?"
            confirmLabel="Delete"
            busy={busy}
            onConfirm={() => void onDeleteConversation(confirmDeleteId)}
            onCancel={() => setConfirmDeleteId(null)}
          >
            Messages and citations for this thread will be removed.
          </ConfirmBanner>
        )}
      </aside>

      <div className="panel chat-panel">
        <div className="panel-heading compact">
          <div>
            <h2>{activeTitle}</h2>
            <p className="muted">
              Grounded answers use retrieved document context. Relevance scores are retrieval
              similarity, not model certainty.
            </p>
          </div>
        </div>

        {demoMode && (
          <div className="demo-provider-banner" role="status">
            Demo provider active — responses are deterministic test output and may not be
            semantically accurate. Set <code>EMBEDDING_PROVIDER=together</code> and{" "}
            <code>LLM_PROVIDER=together</code> with a Together API key for real RAG testing.
          </div>
        )}

        {mismatchedDocuments.length > 0 && (
          <div className="embedding-mismatch-banner" role="alert">
            {mismatchedDocuments.length} document
            {mismatchedDocuments.length === 1 ? "" : "s"} were indexed with a different embedding
            provider and will not be searched until reprocessed (
            {mismatchedDocuments.map((doc) => doc.title).join(", ")}).
          </div>
        )}

        <div className="ask-filters" aria-label="Retrieval filters">
          <label>
            Department
            <input
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="e.g. HR"
              disabled={busy}
            />
          </label>
          <label>
            Category
            <input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. Benefits"
              disabled={busy}
            />
          </label>
          <label>
            Document
            <select
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              disabled={busy}
            >
              <option value="">All completed documents</option>
              {completedDocuments.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.title} ({doc.department})
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="message-thread" ref={threadRef} aria-live="polite">
          {loadingThread && <SkeletonStack rows={3} label="Loading messages" />}

          {!loadingThread && !messages.length && phase === "idle" && (
            <div className="assistant-empty">
              <h3>Ask about internal policies</h3>
              <p className="muted">
                {completedDocuments.length
                  ? "Start a new conversation or continue an existing one. Suggested questions match your indexed documents."
                  : "Upload and finish indexing at least one document to enable suggested questions."}
              </p>
              {starterQuestions.length > 0 && (
                <div className="starter-grid">
                  {starterQuestions.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="starter-chip"
                      disabled={busy}
                      onClick={() => onStarter(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {messages.map((message) => (
            <article key={message.id} className={`bubble ${message.role}`}>
              <header>
                <strong>{message.role === "user" ? "You" : "Assistant"}</strong>
              </header>
              <p className="assistant-answer">{message.content}</p>
              {message.role === "assistant" && (
                <>
                  <AnswerStatusLine message={message} />
                  {message.insufficient_context || message.answer_status === "insufficient_context"
                    ? null
                    : (
                      <CitationList
                        citations={message.citations}
                        selectedId={selectedCitationId}
                        onSelect={onCitationSelect}
                      />
                    )}
                  <RetrievalDetails message={message} />
                </>
              )}
            </article>
          ))}

          {phase !== "idle" && (
            <div className="bubble assistant generating" aria-busy="true">
              <header>
                <strong>Assistant</strong>
                <span className="badge warn">
                  {phase === "retrieving" ? "Retrieving sources…" : "Generating answer…"}
                </span>
              </header>
              <div className="typing-indicator" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}
        </div>

        {error && (
          <ErrorBanner
            message={error}
            onRetry={pendingRetry ? onRetry : undefined}
          />
        )}

        <form className="ask-form" onSubmit={onAsk}>
          <label htmlFor="assistant-question">Question</label>
          <textarea
            id="assistant-question"
            rows={3}
            placeholder="Ask a question grounded in company documents…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            required
            disabled={busy}
          />
          <button className="btn primary" type="submit" disabled={busy || !question.trim()}>
            {busy ? "Working…" : "Ask"}
          </button>
        </form>
      </div>
    </section>
  );
}

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
    }).format(new Date(value));
  } catch {
    return "";
  }
}

function AnswerStatusLine({ message }: { message: ChatMessage }) {
  const status = message.answer_status;
  if (status === "insufficient_context" || message.insufficient_context) {
    return <p className="answer-status warn">Insufficient context in indexed documents</p>;
  }
  if (status === "demo") {
    return <p className="answer-status warn">Demo answer (fake provider)</p>;
  }
  if (status === "grounded" || message.grounded) {
    const count = message.citations?.length ?? 0;
    if (!count) {
      return <p className="answer-status ok">Grounded</p>;
    }
    return (
      <p className="answer-status ok">
        Grounded in {count} source{count === 1 ? "" : "s"}
      </p>
    );
  }
  return null;
}
