# RAG answer quality

Grounded answers separate **answer text** from **retrieval metadata**. Citations and
latency live in structured API fields and the collapsed Retrieval Details UI.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_TOP_K` | `5` | Max chunks retrieved before quality gates |
| `RAG_MIN_RELEVANCE_SCORE` | `0.50` | Minimum cosine similarity (`1 - distance`) for evidence |
| `RAG_MIN_SUPPORTING_CHUNKS` | `1` | How many chunks must pass score + term overlap |
| `RAG_MIN_TERM_OVERLAP` | `1` | Question terms that must appear in a supporting chunk |
| `RAG_ANSWER_STYLE` | `concise` | `concise` (2–5 sentences) or `detailed` |

Legacy aliases: `RETRIEVAL_TOP_K`, `RETRIEVAL_MIN_SCORE`.

### Calibrating the relevance threshold

Similarity score ranges **differ by embedding model**:

- **Fake embeddings** (keyword-weighted token hash): related policy text often scores
  ~0.4–0.7 raw cosine. Evidence gating adds a small lexical boost (`+0.08` per
  overlapping question term, capped at `+0.24`) so clearly on-topic chunks can pass
  `0.50` while a ~0.458 unrelated top hit with **no** term overlap still refuses.
- **Together / production models**: measure max scores for supported vs unsupported
  questions on your corpus, then set `RAG_MIN_RELEVANCE_SCORE` slightly above typical
  unsupported peaks. Re-tune after changing embedding models.

Always keep lexical term-overlap enabled so an unrelated top hit cannot ground an answer
solely by vector score.

## Embedding provider consistency

Each completed document stores `embedding_provider` / `embedding_model` from ingestion.
Query-time retrieval only searches documents indexed with the **active**
`EMBEDDING_PROVIDER`. Switching providers without reprocessing yields:

- empty retrieval for stale vectors
- `embedding_provider_mismatch` on ask responses
- a UI warning listing documents that need reprocess

## Demo (fake) providers

`LLM_PROVIDER=fake` and `EMBEDDING_PROVIDER=fake` are for local workflow tests.
`/ready` sets `demo_mode=true` and the Assistant shows a development banner.
Fake LLM output is concise and metadata-free, but it is **not** semantic AI.

For manual RAG verification:

```bash
EMBEDDING_PROVIDER=together
LLM_PROVIDER=together
TOGETHER_API_KEY=...
# Re-upload or reprocess documents after switching providers
```
