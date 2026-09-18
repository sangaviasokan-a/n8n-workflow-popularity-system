from __future__ import annotations

import os
import sys


def main() -> int:
    print("n8n Workflow Popularity Intelligence System - preflight")
    print("=" * 64)

    required_modules = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "pydantic_settings",
        "sqlalchemy",
        "psycopg",
        "httpx",
        "tenacity",
        "pytrends",
        "pytest",
    ]

    failed = False

    for module in required_modules:
        try:
            __import__(module)
            print(f"[OK] Python dependency: {module}")
        except Exception as exc:
            failed = True
            print(f"[FAIL] Python dependency: {module} ({exc})")

    database_url = os.getenv("DATABASE_URL", "").strip()
    youtube_key = os.getenv("YOUTUBE_API_KEY", "").strip()

    if database_url:
        print("[OK] DATABASE_URL is configured")
    else:
        print("[WARN] DATABASE_URL is not configured")

    if youtube_key:
        print("[OK] YOUTUBE_API_KEY is configured")
    else:
        print("[WARN] YOUTUBE_API_KEY is not configured")

    print()
    if failed:
        print("Preflight failed: install the missing Python dependencies.")
        return 1

    print("Python dependency preflight passed.")
    print("External service connectivity must be tested with the user's own credentials.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
