from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .routers import documents, health, kb, vector_search, workflow
from .routers import api_documents, documents, health, vector_search, workflow
from .workflow_db.db import init_db

app = FastAPI()


def _error_response(status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
	return JSONResponse(
		status_code=status_code,
		content={
			"error": {
				"code": code,
				"message": message,
				"details": details or {},
			}
		},
	)


@app.exception_handler(HTTPException)
async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
	if isinstance(exc.detail, dict) and "error" in exc.detail:
		return JSONResponse(status_code=exc.status_code, content=exc.detail)

	code_by_status = {
		400: "BAD_REQUEST",
		401: "UNAUTHORIZED",
		403: "FORBIDDEN",
		404: "NOT_FOUND",
		409: "CONFLICT",
		422: "BAD_REQUEST",
		500: "INTERNAL_ERROR",
	}

	message = str(exc.detail) if exc.detail else "Request failed"
	return _error_response(exc.status_code, code_by_status.get(exc.status_code, "INTERNAL_ERROR"), message)


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
	return _error_response(
		status_code=422,
		code="BAD_REQUEST",
		message="Validation failed",
		details={"issues": exc.errors()},
	)


@app.on_event("startup")
def _startup() -> None:
	init_db()

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(api_documents.router)
app.include_router(vector_search.router)
app.include_router(workflow.router)
app.include_router(kb.router)
