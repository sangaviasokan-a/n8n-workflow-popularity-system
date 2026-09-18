from __future__ import annotations

import os

# Keep the automated test suite independent from developer secrets
# and local PostgreSQL credentials. These values are set before app
# modules create the SQLAlchemy engine.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_suite.db")
os.environ.setdefault("YOUTUBE_API_KEY", "test-key")

# The API tests use TestClient without a lifespan context, so FastAPI's
# startup hook is not guaranteed to create the SQLite schema before the
# first request. Create the schema when pytest loads this conftest.
from app.database.database import Base, engine
from app.models import Metric, Source, Workflow  # noqa: F401,E402


Base.metadata.create_all(bind=engine)