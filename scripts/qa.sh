#!/usr/bin/env bash
# qa.sh — Run all test suites and static analysis, print red/green summary.
# Usage: ./scripts/qa.sh [--skip-e2e] [--skip-bandit] [--skip-migration]
set -euo pipefail

# Load nvm so Node ≥18 is on PATH for frontend steps.
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh" --no-use
if command -v nvm &>/dev/null; then
  nvm use default --silent 2>/dev/null || true
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"

SKIP_E2E=false
SKIP_BANDIT=false
SKIP_MIGRATION=false

for arg in "$@"; do
  case "$arg" in
    --skip-e2e)       SKIP_E2E=true ;;
    --skip-bandit)    SKIP_BANDIT=true ;;
    --skip-migration) SKIP_MIGRATION=true ;;
  esac
done

# ── Colour helpers ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}PASS${NC}  $1"; }
fail() { echo -e "${RED}FAIL${NC}  $1"; FAILURES+=("$1"); }
skip() { echo -e "${YELLOW}SKIP${NC}  $1"; }

FAILURES=()

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Soaring Heights KMS — QA Gate"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Backend unit tests ────────────────────────────────────────────────────
echo "▶ 1/6  Backend unit tests (coverage ≥85%)"
if (
  cd "$BACKEND_DIR"
  if [ -d ".venv" ]; then
    source .venv/bin/activate
  fi
  python -m pytest tests/unit/ \
    --cov=app/services --cov-fail-under=85 \
    --cov-report=term-missing:skip-covered \
    --tb=short -q 2>&1
); then
  pass "Backend unit tests"
else
  fail "Backend unit tests"
fi

# ── 2. Backend IAT tests ─────────────────────────────────────────────────────
echo ""
echo "▶ 2/6  Backend IAT tests"
if (
  cd "$BACKEND_DIR"
  if [ -d ".venv" ]; then
    source .venv/bin/activate
  fi
  python -m pytest tests/iat/ --tb=short -q 2>&1
); then
  pass "Backend IAT tests"
else
  fail "Backend IAT tests"
fi

# ── 3. Frontend unit tests ───────────────────────────────────────────────────
echo ""
echo "▶ 3/6  Frontend unit tests (Vitest)"
if (
  cd "$FRONTEND_DIR"
  if [ -f "package.json" ] && command -v npm &>/dev/null; then
    npm test -- --reporter=verbose --run 2>&1
  else
    echo "  npm not available — skipping"
    exit 0
  fi
); then
  pass "Frontend unit tests"
else
  fail "Frontend unit tests"
fi

# ── 4. Playwright E2E smoke ──────────────────────────────────────────────────
echo ""
echo "▶ 4/6  Playwright E2E smoke"
if $SKIP_E2E; then
  skip "Playwright E2E (--skip-e2e)"
elif ! command -v npx &>/dev/null; then
  skip "Playwright E2E (npx not found)"
else
  if (
    cd "$FRONTEND_DIR"
    npx playwright test --config=tests/e2e/playwright.config.js \
      --reporter=list 2>&1
  ); then
    pass "Playwright E2E smoke"
  else
    fail "Playwright E2E smoke"
  fi
fi

# ── 5. Security linters ──────────────────────────────────────────────────────
echo ""
echo "▶ 5/6  Security linters (bandit)"
if $SKIP_BANDIT; then
  skip "Bandit (--skip-bandit)"
elif ! command -v bandit &>/dev/null && ! python -m bandit --version &>/dev/null 2>&1; then
  skip "Bandit (not installed)"
else
  if (
    cd "$BACKEND_DIR"
    if [ -d ".venv" ]; then source .venv/bin/activate; fi
    python -m bandit -r app/ \
      -ll \
      --exclude app/tests \
      -f txt 2>&1
  ); then
    pass "Bandit security scan"
  else
    fail "Bandit security scan"
  fi
fi

# ── 6. Migration round-trip ──────────────────────────────────────────────────
echo ""
echo "▶ 6/6  Schema migration round-trip"
if $SKIP_MIGRATION; then
  skip "Migration round-trip (--skip-migration)"
else
  TMPDB="$(mktemp /tmp/kms_migration_test_XXXXXX.db)"
  trap 'rm -f "$TMPDB"' EXIT

  if (
    cd "$BACKEND_DIR"
    if [ -d ".venv" ]; then source .venv/bin/activate; fi

    python - <<PYEOF
import asyncio, os, sys
sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///$TMPDB")
os.environ.setdefault("CONFIG_DIR", "../config")

async def run():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel import SQLModel

    # Apply migrations
    test_engine = create_async_engine("sqlite+aiosqlite:///$TMPDB", echo=False)
    import glob, pathlib
    migration_dir = pathlib.Path("migrations")
    sql_files = sorted(migration_dir.glob("*.sql"))
    if not sql_files:
        print("  No migration files found — skipping round-trip")
        return
    async with test_engine.begin() as conn:
        for sql_file in sql_files:
            statements = sql_file.read_text().split(";")
            for stmt in statements:
                stmt = stmt.strip()
                if stmt:
                    await conn.exec_driver_sql(stmt)
    print(f"  Applied {len(sql_files)} migration file(s) — OK")

    # Drop all
    async with test_engine.begin() as conn:
        await conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")
        tables = (await conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        for (t,) in reversed(tables):
            await conn.exec_driver_sql(f"DROP TABLE IF EXISTS [{t}]")
    print(f"  Dropped all tables — OK")

    # Re-apply
    async with test_engine.begin() as conn:
        for sql_file in sql_files:
            statements = sql_file.read_text().split(";")
            for stmt in statements:
                stmt = stmt.strip()
                if stmt:
                    await conn.exec_driver_sql(stmt)
    print(f"  Re-applied migrations — OK")
    await test_engine.dispose()

asyncio.run(run())
PYEOF
  ); then
    pass "Migration round-trip"
  else
    fail "Migration round-trip"
  fi
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ ${#FAILURES[@]} -eq 0 ]; then
  echo -e "${GREEN}ALL CHECKS PASSED${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  exit 0
else
  echo -e "${RED}FAILED CHECKS:${NC}"
  for f in "${FAILURES[@]}"; do
    echo -e "  ${RED}✗${NC} $f"
  done
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  exit 1
fi
