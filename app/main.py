from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.collection import router as collection_router
from app.api.health import router as health_router
from app.api.workflows import router as workflow_router
from app.config import settings
from app.database.database import create_tables


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "n8n Workflow Popularity "
        "Intelligence System"
    ),
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    create_tables()


app.include_router(
    health_router
)

app.include_router(
    workflow_router
)

app.include_router(
    collection_router
)


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "status": "running",
        "version": "0.1.0",
    }