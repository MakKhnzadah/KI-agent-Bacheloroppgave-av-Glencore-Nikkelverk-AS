# Backend API Contract v1 (Document Flow)

Status: Draft v1
Scope: Upload + Queue flow only (frontend unchanged)
Source of truth: `frontend/src/types/document.ts`, `frontend/src/services/documentService.ts`, `frontend/src/app/context/documents-context.tsx`

## 1. Contract Rules

- Base path: `/api`
- Content type: `application/json` (except multipart upload endpoint)
- IDs are strings.
- All document responses must match this shape exactly:

```json
{
  "id": "string",
  "title": "string",
  "fileName": "string",
  "category": "Sikkerhet|Vedlikehold|Miljo|Kvalitet|Prosedyre|Annet",
  "status": "pending|approved|rejected",
  "uploadedBy": "string",
  "uploadedAt": "string",
  "originalContent": "string",
  "revisedContent": "string",
  "approvedContent": "string (optional)"
}
```

Note: Frontend uses category value `Milj\u00f8` in TypeScript. Keep backend UTF-8 capable and return `Miljo` only if frontend mapping is added later. Preferred: return `Milj\u00f8`.

## 2. Shared Error Format

All non-2xx responses should use:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

Recommended codes: `BAD_REQUEST`, `NOT_FOUND`, `CONFLICT`, `UNAUTHORIZED`, `INTERNAL_ERROR`.

## 3. Endpoints From Frontend Document Service

### 3.1 List documents

- Method: `GET`
- Path: `/api/documents`
- Query params (optional):
  - `status`: `pending|approved|rejected`
  - `category`: string
- Response `200`:

```json
[
  {
    "id": "1",
    "title": "Sikkerhetsprosedyre Smelteverk 2026",
    "fileName": "sikkerhet_smelteverk_2026.pdf",
    "category": "Sikkerhet",
    "status": "pending",
    "uploadedBy": "Maria Hansen",
    "uploadedAt": "10. feb 2026 - 14:30",
    "originalContent": "...",
    "revisedContent": "..."
  }
]
```

### 3.2 Get by ID

- Method: `GET`
- Path: `/api/documents/{id}`
- Response `200`: `Document`
- Response `404`: shared error format

### 3.3 Upload document (current frontend service call shape)

- Method: `POST`
- Path: `/api/documents`
- Request body `application/json` (as used by current `uploadDocument` service):

```json
{
  "title": "string",
  "fileName": "string",
  "category": "Sikkerhet|Vedlikehold|Miljo|Kvalitet|Prosedyre|Annet",
  "uploadedBy": "string",
  "originalContent": "string",
  "revisedContent": "string"
}
```

- Response `201`: `Document` with `status = "pending"`

Important: If you also support real file upload, add a second endpoint (`/api/documents/upload`) for multipart and map result to the same `Document` response shape.

### 3.4 Approve

- Method: `PATCH`
- Path: `/api/documents/{id}/approve`
- Request body: none
- Response `200`: updated `Document`
- Rules:
  - set `status = "approved"`
  - set `approvedContent = revisedContent` (or selected approved text)

### 3.5 Reject

- Method: `PATCH`
- Path: `/api/documents/{id}/reject`
- Request body: none
- Response `200`: updated `Document`
- Rules:
  - set `status = "rejected"`
  - unset `approvedContent`

### 3.6 Delete

- Method: `DELETE`
- Path: `/api/documents/{id}`
- Response `204`: no body

### 3.7 Stats

- Method: `GET`
- Path: `/api/documents/stats`
- Response `200`:

```json
{
  "total": 7,
  "pending": 3,
  "approved": 3,
  "rejected": 1
}
```

### 3.8 Search

- Method: `GET`
- Path: `/api/documents/search`
- Query params:
  - `q`: string (required)
- Response `200`: `Document[]`

### 3.9 Filter by category (optional alias)

- Method: `GET`
- Path: `/api/documents`
- Query params:
  - `category`: string
- Response `200`: `Document[]`

## 4. Backend-to-Frontend Mapping Checklist

- `id`: string
- `title`: string
- `fileName`: string
- `category`: exact enum text expected by frontend
- `status`: exact enum text expected by frontend
- `uploadedBy`: display name string
- `uploadedAt`: display-ready string (current frontend expects preformatted text)
- `originalContent`: string
- `revisedContent`: string
- `approvedContent`: optional string

## 5. Data Ownership (MVP)

- SQLite (source of truth): metadata + workflow state + audit trail.
- Vector DB: embeddings and chunk metadata for approved/applied knowledge docs only.
- Ollama: revision generation and optional RAG answer generation.

## 6. Out of Scope for v1

- Auth endpoints
- Knowledge bank chat endpoints
- Document detail page backend wiring

These should be defined in v2 after document flow is stable.
