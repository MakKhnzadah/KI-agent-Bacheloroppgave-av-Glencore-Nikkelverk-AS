from fastapi import FastAPI

from .routers import documents, health, vector_search

app = FastAPI()

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(vector_search.router)
