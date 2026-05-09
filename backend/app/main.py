"""FastAPI application entry point. Registers all routers and runs startup tasks."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import async_engine
from .routes import (
    auth, owners, dogs, kennels, reservations,
    bills, activities, activity_types, incidents,
    issues, calendar, search, reports, portal,
)

logger = logging.getLogger(__name__)


_INSECURE_SECRET = "CHANGE_ME_IN_PRODUCTION"


def _validate_secrets() -> None:
    """Abort startup if any secret is still set to its insecure placeholder."""
    from .auth import SECRET_KEY as _sk
    from .routes.portal import PORTAL_SECRET as _ps
    bad = []
    if not _sk or _INSECURE_SECRET in _sk:
        bad.append("SECRET_KEY")
    if not _ps or _INSECURE_SECRET in _ps:
        bad.append("PORTAL_SECRET_KEY (or SECRET_KEY)")
    if bad:
        raise RuntimeError(
            f"Insecure placeholder detected for: {', '.join(bad)}. "
            "Set a strong random value via environment variables before starting. "
            "Generate one with: openssl rand -hex 32"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_secrets()
    logger.info("Starting Kennel Management System backend")
    await _run_migrations()
    await _provision_kennels()
    await _seed_activity_types()
    yield
    logger.info("Shutting down")
    await async_engine.dispose()


app = FastAPI(
    title="Soaring Heights Kennel Management System",
    version="1.0.0",
    description="Internal kennel management API. All endpoints require Bearer token auth except /api/auth/login and /api/portal/*.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9100", "http://kennel.soaringheights.local"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in [
    auth.router, owners.router, dogs.router, kennels.router,
    reservations.router, bills.router, activities.router,
    activity_types.router, incidents.router, issues.router,
    calendar.router, search.router, reports.router, portal.router,
]:
    app.include_router(router)


@app.get("/api/health", tags=["health"])
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


def _split_sql_statements(sql: str) -> list:
    """Split SQL source into individual statements, stripping line and block comments."""
    import re
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)  # block comments
    sql = re.sub(r'--[^\n]*', '', sql)                     # line comments
    return [s.strip() for s in sql.split(';') if s.strip()]


async def _run_migrations() -> None:
    """Apply pending versioned SQL migration scripts from /backend/migrations/."""
    import glob
    from sqlalchemy import text
    migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
    scripts = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))

    async with async_engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(filename TEXT PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')))"
        ))
        applied = {row[0] for row in await conn.execute(text("SELECT filename FROM schema_migrations"))}

        for script_path in scripts:
            filename = os.path.basename(script_path)
            if filename not in applied:
                logger.info("Applying migration: %s", filename)
                try:
                    with open(script_path, encoding="utf-8") as f:
                        sql = f.read()
                except OSError as exc:
                    raise RuntimeError(f"Cannot read migration file {script_path}: {exc}") from exc
                for stmt in _split_sql_statements(sql):
                    await conn.execute(text(stmt))
                await conn.execute(text("INSERT INTO schema_migrations (filename) VALUES (:f)"), {"f": filename})
                logger.info("Migration applied: %s", filename)


async def _provision_kennels() -> None:
    """Auto-provision kennel records from kennels.json on every startup."""
    from .models.kennel import Kennel
    from .config import get_kennels
    from sqlmodel import select
    from .database import AsyncSessionLocal

    cfg = get_kennels()
    counter = 1
    async with AsyncSessionLocal() as session:
        for kt in cfg["kennel_types"]:
            for _ in range(kt["count"]):
                num = f"K-{counter:02d}"
                counter += 1
                existing = await session.exec(select(Kennel).where(Kennel.kennel_number == num))
                if existing.first():
                    continue
                session.add(Kennel(
                    kennel_number=num,
                    kennel_type=kt["type"],
                    max_size_class=kt["max_size_class"],
                    sqft=float(kt["sqft"]),
                    features=kt.get("features"),
                    active=True,
                    provisioned_from_config=True,
                ))
        await session.commit()
    logger.info("Kennel provisioning complete")


async def _seed_activity_types() -> None:
    """Seed initial activity types if table is empty."""
    from .models.activity_type import ActivityType
    from sqlmodel import select
    from .database import AsyncSessionLocal

    SEED_TYPES = [
        {"name": "Nature Walk",               "qualifies_for_pacfa_exception": True},
        {"name": "Playtime",                  "qualifies_for_pacfa_exception": False},
        {"name": "Medication Administration", "qualifies_for_pacfa_exception": False},
        {"name": "Emergency Grooming",        "qualifies_for_pacfa_exception": False},
        {"name": "Play Yard",                 "qualifies_for_pacfa_exception": True},
    ]

    async with AsyncSessionLocal() as session:
        existing = await session.exec(select(ActivityType))
        if existing.first():
            logger.info("Activity types already seeded, skipping")
            return
        for at in SEED_TYPES:
            session.add(ActivityType(**at))
        await session.commit()
    logger.info("Activity types seeded")
