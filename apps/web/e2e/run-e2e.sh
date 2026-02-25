#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# E2E test runner for Synapse avatar-engine tests.
#
# Handles two concerns:
# 1. Model override: modifies avatar.yaml so the backend starts with
#    gemini-2.0-flash (cheap model). The frontend picks up VITE_E2E_MODEL
#    from playwright.config.ts webServer command to show matching UI.
# 2. Fresh servers: kills any existing backend/frontend so Playwright
#    starts clean instances with the test configuration.
#
# Usage:
#   ./e2e/run-e2e.sh                        # all tests (tier1 + tier2)
#   ./e2e/run-e2e.sh --project tier1        # only offline tests
#   ./e2e/run-e2e.sh --project tier2-live   # only live tests
#   ./e2e/run-e2e.sh --headed               # headed mode
#   ./e2e/run-e2e.sh --grep @live           # only @live tests
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

AVATAR_YAML="$HOME/.synapse/avatar.yaml"
BACKUP="$AVATAR_YAML.e2e-backup"
TEST_MODEL="gemini-2.0-flash"

# ── Cleanup: always restore YAML on exit (success, failure, Ctrl+C) ──
cleanup() {
  if [[ -f "$BACKUP" ]]; then
    cp "$BACKUP" "$AVATAR_YAML"
    rm -f "$BACKUP"
    echo "[e2e] Restored original avatar.yaml"
  fi
}
trap cleanup EXIT

# ── 1. Kill existing servers so Playwright starts fresh ones ─────────
for PORT in 8000 5173; do
  PIDS=$(lsof -ti:"$PORT" 2>/dev/null || true)
  if [[ -n "$PIDS" ]]; then
    echo "[e2e] Killing existing process on port $PORT"
    echo "$PIDS" | xargs kill 2>/dev/null || true
  fi
done
# Wait for ports to be released
for _ in $(seq 1 20); do
  if ! lsof -ti:8000 &>/dev/null && ! lsof -ti:5173 &>/dev/null; then break; fi
  sleep 0.25
done

# ── 2. Switch backend model to flash in avatar.yaml ──────────────────
if [[ -f "$AVATAR_YAML" ]]; then
  cp "$AVATAR_YAML" "$BACKUP"
  sed -i "/^gemini:/,/^[a-z]/ s/model: \"[^\"]*\"/model: \"$TEST_MODEL\"/" "$AVATAR_YAML"
  echo "[e2e] Backend model → $TEST_MODEL"
else
  echo "[e2e] No avatar.yaml found — running with default config"
fi

# ── 3. Determine run mode and execute ────────────────────────────────
ARGS="$*"

if [[ "$ARGS" == *"--project tier2-live"* ]] || [[ "$ARGS" == *"--project=tier2-live"* ]] \
   || [[ "$ARGS" == *"--grep @live"* ]] || [[ "$ARGS" == *"--grep=@live"* ]]; then
  # Live tests: single worker (AI provider handles one conversation at a time)
  echo "[e2e] Running live tests (workers=1)"
  npx playwright test --workers=1 "$@"
elif [[ "$ARGS" == *"--project tier1"* ]] || [[ "$ARGS" == *"--project=tier1"* ]]; then
  echo "[e2e] Running tier1 tests (parallel)"
  npx playwright test "$@"
else
  # Both projects: tier1 parallel, then tier2-live serial
  echo "[e2e] Running tier1 (parallel) + tier2-live (workers=1)"
  npx playwright test --project=tier1 "$@"
  npx playwright test --project=tier2-live --workers=1 "$@"
fi
