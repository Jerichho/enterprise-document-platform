import { Link } from "react-router-dom";

import type { Citation } from "../types";

type Props = {
  citations: Citation[];
  onSelect?: (citation: Citation) => void;
  selectedId?: string | null;
};

export function CitationList({ citations, onSelect, selectedId }: Props) {
  if (!citations.length) {
    return null;
  }

  return (
    <div className="citations">
      <p className="citations-label">Sources</p>
      <ul className="citation-cards">
        {citations.map((citation) => {
          const selected = citation.id === selectedId;
          return (
            <li key={citation.id}>
              <button
                type="button"
                className={`citation-card${selected ? " selected" : ""}`}
                onClick={() => onSelect?.(citation)}
                aria-pressed={selected}
              >
                <span className="citation-card-title">
                  [{citation.rank}] {citation.document_title}
                </span>
                <span className="citation-card-meta muted">
                  {citation.page_number != null ? `Page ${citation.page_number}` : "Page n/a"}
                </span>
                <p className="citation-card-excerpt">{citation.snippet}</p>
                <span className="citation-card-score muted">
                  Retrieval relevance: {citation.relevance_score.toFixed(2)}
                </span>
              </button>
              {citation.document_id && (
                <Link className="citation-doc-link" to={`/documents/${citation.document_id}`}>
                  Open document
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
