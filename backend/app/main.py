"""FastAPI application entry point. Registers all routers and runs startup tasks."""

import logging
import logging.config
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from .database import async_engine
from .routes import (
    auth, owners, dogs, kennels, reservations,
    bills, activities, activity_types, incidents,
    issues, calendar, search, reports, portal, users,
)

# ---------------------------------------------------------------------------
# Logging — structured JSON-style output suitable for container log drivers
# ---------------------------------------------------------------------------
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        }
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        }
    },
    "root": {"level": os.environ.get("LOG_LEVEL", "INFO"), "handlers": ["stdout"]},
})

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter (shared across the app; auth router adds its own limit)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Max request body size — 1 MB is generous for this JSON-only API
# ---------------------------------------------------------------------------
_MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", 1_048_576))  # 1 MB


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
    await _bootstrap_admin()
    if os.environ.get("KMS_INIT_DB", "").lower() in ("1", "true", "yes"):
        logger.info("KMS_INIT_DB set — running provisioning and seeding")
        await _provision_kennels()
        await _seed_activity_types()
    else:
        logger.info("KMS_INIT_DB not set — skipping provisioning/seeding")
    yield
    logger.info("Shutting down")
    await async_engine.dispose()


# ---------------------------------------------------------------------------
# CORS — origins configurable via CORS_ORIGINS env var (comma-separated)
# ---------------------------------------------------------------------------
_default_origins = "http://localhost:9100,http://kennel.soaringheights.local"
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app = FastAPI(
    title="Soaring Heights Kennel Management System",
    version="1.0.0",
    description="Internal kennel management API. All endpoints require Bearer token auth except /api/auth/login and /api/portal/*.",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

for router in [
    auth.router, users.router, owners.router, dogs.router, kennels.router,
    reservations.router, bills.router, activities.router,
    activity_types.router, incidents.router, issues.router,
    calendar.router, search.router, reports.router, portal.router,
]:
    app.include_router(router)


# ---------------------------------------------------------------------------
# Request size limit middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})
    return await call_next(request)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        '{"method":"%s","path":"%s","status":%d,"duration_ms":%.1f}',
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Global exception handler — never expose internal details to clients
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health", tags=["health"])
async def health():
    """Health check endpoint. Returns 503 if DB is unreachable."""
    from sqlalchemy import text
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check DB probe failed")
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "unreachable"})
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


async def _bootstrap_admin() -> None:
    """If staff_users is empty and ADMIN_USERNAME/ADMIN_PASSWORD are set, create the first admin."""
    admin_username = os.environ.get("ADMIN_USERNAME", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not admin_username or not admin_password:
        return

    from sqlmodel import select
    from .models.staff_user import StaffUser
    from .auth import hash_password
    from .database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        existing = await session.exec(select(StaffUser))
        if existing.first():
            logger.info("staff_users not empty — skipping admin bootstrap")
            return
        session.add(StaffUser(
            username=admin_username,
            password_hash=hash_password(admin_password),
            role="admin",
            active=True,
        ))
        await session.commit()
        logger.info("Admin user bootstrapped: %s", admin_username)


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
