from fastapi import FastAPI
from .routers import health, documents
app = FastAPI()

app.include_router(health.router)
app.include_router(documents.router)
