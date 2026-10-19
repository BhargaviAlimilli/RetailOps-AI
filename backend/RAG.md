# Document retrieval

Authenticated users can maintain their own private document corpus. JSON text and
Markdown ingestion uses `POST /api/v1/documents`; file upload uses
`POST /api/v1/documents/upload` with multipart `title` and `file` fields. Only UTF-8
`.txt` and `.md` files up to 100,000 bytes are supported. PDF and binary files are
explicitly rejected. JSON content is bounded to 100,000 characters. No server-side
file path or remote URL is accepted.

Chunks preserve offsets in the stored, normalized source. Gemini embeddings use
the explicitly configured embedding model and 768 dimensions, normalized before
storage in PostgreSQL `vector(768)`. Search combines exact cosine-distance nearest
neighbors with BM25 using reciprocal rank fusion. The optional reranker is a
documented deterministic lexical-overlap adjustment, not a trained cross-encoder.
The corpus is bounded to 50 documents per user and 200 chunks per document; exact
vector search is intentional at this scale. Ownership filters apply to both
retrieval branches and source reads. Citations contain actual stored chunk IDs
and excerpts. Context explicitly labels document text as untrusted evidence.

Ingestion commits a bounded processing lease before calling the provider. A late
old attempt cannot overwrite a newer lease. Failed ingestion remains visible as
an error, and identical ready content is idempotent for the owner/model. Search
and ingestion attempts have durable per-user quotas recorded without prompt text
in the audit log; deleting a document does not reset them. Four embedding calls
may execute concurrently per process. SDK automatic retries are disabled. Multiple
worker deployments should add shared query-concurrency enforcement at the edge.

Run `python scripts/evaluate_rag.py --output fixtures/data/documents/evaluation_mock.json`
for the reproducible offline keyword/vector/hybrid/reranked comparison. Its mock
semantic rankings test plumbing and do not establish model quality. The separate
`evaluation_live.json` records the authorized live smoke: three synthetic policies
were ingested and both short queries retrieved the expected source first, using
five actual embedding HTTP requests. No generation call or faithfulness score is
claimed. The initial SDK-only failure was fixed by removing a Vertex-only config
field and is covered by an actual SDK conversion test with HTTP MockTransport.

Live checks require explicit user approval plus
`python scripts/verify_live_rag.py --allow-model-calls`. The script is restricted to
development `retailops_demo`, uses local credentials without printing them, and
caps request attempts. It must not be added to automatic test or CI commands.
