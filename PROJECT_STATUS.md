# CURRENT STATUS: see CURRENT_READINESS.md

The historical notes below are superseded by CURRENT_READINESS.md and SOURCE_REVIEW.md.

# KNOX AI — fixed implementation scope

## Product
RAG knowledge assistant for KKU personnel, initially covering leave and official
travel/reimbursement. Compensation is included only where verified official
documents establish the applicable rules. Answers must include evidence, document,
and page where available. Ask for personnel category when necessary. Do not invent
entitlements or personal salary amounts. Resolver supports this workflow; it is
not a replacement for RAG.

## Workspace and legacy sources
- Active implementation: `backend/` in this workspace.
- Copied from an earlier local backend workspace without secrets or virtual environments.
- Existing resolver remains an external legacy project and is not bundled here.
- Original source folders have not been changed.

## Implemented in this workspace
- PDF extraction preserves physical PDF page numbers across chunks.
- DOCX and TXT keep unknown page numbers as null; DOCX table text is included.
- Upload stores page provenance in chunk records and metadata.
- Existing ask response includes source excerpt and page when the retrieval RPC
  returns them. Existing stored chunks need re-ingestion to acquire provenance.
- Four dependency-free provenance/chunking regression tests pass.
- Python source compilation passes.

## Not yet verified or implemented
- Live Supabase connection, schema, storage and retrieval RPCs.
- RPC return fields must include metadata/page information for citations.
- Current ask endpoint is retrieval-only, not LLM answer generation.
- Official source URL, personnel category and effective-date metadata workflow.
- Reviewed KKU leave/travel corpus and answer reference set.
- User interface, end-to-end tests and resolver integration.
- Legacy backend has no authentication; do not deploy it publicly as-is.

## Next implementation order
1. Inspect actual database schema/RPCs read-only and verify configuration without
   printing credentials. Use local backend-only environment configuration.
2. Add official document metadata and review status; ingest a verified pilot corpus.
3. Implement grounded LLM generation with validated source identifiers,
   insufficient-evidence handling and personnel-category clarification.
4. Build question/answer and document-library screens.
5. Repair and integrate resolver for supported version relationships.
6. Evaluate correct answers, citations, outdated evidence and abstention.

## Local verification
`python -m unittest discover -s backend -p test_provenance.py -v`

The full backend requires the dependencies in `backend/requirements.txt`, backend
Supabase environment variables, an installed embedding model and database objects.
Passing isolated tests does not establish live RAG readiness.


## Update — 2026-10-27: runnable local pilot
- Active app entry point: backend/app.py; start with START_KNOX.ps1.
- Added Thai question/answer and document-library UI.
- Added local SQLite persistence as an optional runtime independent of Supabase.
- Added upload, review gate, date/personnel/category filtering, deletion and source downloads.
- Added optional cached E5 hybrid retrieval, explicit keyword fallback, and Responses API generation with citation-ID validation.
- 13 tests pass; generation service is mocked in tests, not verified live.
- Live localhost app starts; UI clarification flow verified in browser.
- Imported 2 official candidate PDFs / 66 chunks, both pending review.
- Third official PDF is scanned (18 pages); OCR is missing.
- No OpenAI API key/model found; live generated answers remain blocked by configuration.
- No claim of latest-regulation completeness, semantic quality, full resolver integration or production readiness.
- See README.md and SOURCE_REVIEW.md for current instructions; earlier next-step list is superseded by this update.
