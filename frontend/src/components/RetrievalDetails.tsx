import { useId, useState } from "react";

import type { ChatMessage, Citation } from "../types";

type Props = {
  message: ChatMessage;
};

export function RetrievalDetails({ message }: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  if (message.role !== "assistant") {
    return null;
  }

  const citations = message.citations ?? [];
  const retrieval = message.retrieval;
  const hasMeta =
    message.max_retrieval_score != null ||
    message.retrieval_min_score != null ||
    message.retrieval_top_k != null ||
    retrieval != null ||
    citations.length > 0;

  if (!hasMeta) {
    return null;
  }

  return (
    <div className="retrieval-details">
      <button
        type="button"
        className="retrieval-details-toggle"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? "Hide" : "Show"} retrieval details
      </button>
      {open && (
        <div id={panelId} className="retrieval-details-panel">
          <dl className="retrieval-meta">
            <div>
              <dt>Top-k</dt>
              <dd>{message.retrieval_top_k ?? "—"}</dd>
            </div>
            <div>
              <dt>Min relevance threshold</dt>
              <dd>
                {formatScore(
                  retrieval?.min_relevance_threshold ?? message.retrieval_min_score,
                )}
              </dd>
            </div>
            <div>
              <dt>Maximum relevance</dt>
              <dd>
                {formatScore(retrieval?.max_relevance ?? message.max_retrieval_score)}
              </dd>
            </div>
            <div>
              <dt>Chunks retrieved</dt>
              <dd>{retrieval?.chunks_retrieved ?? citations.length}</dd>
            </div>
            <div>
              <dt>Supporting chunks</dt>
              <dd>{retrieval?.supporting_chunks ?? citations.length}</dd>
            </div>
            <div>
              <dt>Retrieval latency</dt>
              <dd>{formatMs(retrieval?.retrieval_latency_ms ?? message.vector_search_latency_ms)}</dd>
            </div>
            <div>
              <dt>LLM latency</dt>
              <dd>{formatMs(retrieval?.llm_latency_ms ?? message.llm_latency_ms)}</dd>
            </div>
            <div>
              <dt>Answer status</dt>
              <dd>{message.answer_status ?? (message.grounded ? "grounded" : "—")}</dd>
            </div>
          </dl>
          {citations.length > 0 ? (
            <ul className="retrieval-chunk-list">
              {citations.map((citation) => (
                <li key={citation.id}>
                  <ChunkRow citation={citation} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No chunks met the retrieval quality thresholds.</p>
          )}
        </div>
      )}
    </div>
  );
}

function ChunkRow({ citation }: { citation: Citation }) {
  return (
    <div className="retrieval-chunk">
      <strong>
        [{citation.rank}] {citation.document_title}
      </strong>
      <span className="muted">
        {citation.page_number != null ? ` · page ${citation.page_number}` : ""}
        {citation.chunk_index != null ? ` · chunk ${citation.chunk_index}` : ""}
        {citation.chunk_id ? ` · chunk_id ${citation.chunk_id}` : ""}
        {` · relevance ${citation.relevance_score.toFixed(3)}`}
      </span>
      <p>{citation.snippet}</p>
    </div>
  );
}

function formatScore(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toFixed(3);
}

function formatMs(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value} ms`;
}
