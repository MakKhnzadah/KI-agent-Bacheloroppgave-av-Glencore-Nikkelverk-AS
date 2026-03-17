from fastapi import FastAPI

from .routers import documents, health, kb, vector_search, workflow
from .workflow_db.db import init_db

app = FastAPI()


@app.on_event("startup")
def _startup() -> None:
	init_db()

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(vector_search.router)
app.include_router(workflow.router)
app.include_router(kb.router)
