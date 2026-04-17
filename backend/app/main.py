from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import ai_agent, api_activities, api_auth, api_documents, documents, health, workflow, vector_search
from .workflow_db.db import init_db


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
	init_db()
	yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		"http://127.0.0.1:5173",
		"http://localhost:5173",
		"http://127.0.0.1:5174",
		"http://localhost:5174",
	],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


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

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(api_documents.router)
app.include_router(api_activities.router)
app.include_router(api_auth.router)
app.include_router(ai_agent.router)
app.include_router(vector_search.router)
app.include_router(workflow.router)
