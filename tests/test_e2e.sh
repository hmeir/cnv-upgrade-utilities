#!/bin/bash
#
# E2E tests for CNV-81685: graceful error handling of missing/invalid builds.
# Requires: VERSION_EXPLORER_URL in .env, network access to Version Explorer.
#
# Usage: bash tests/test_e2e.sh
#

set -uo pipefail

PASS=0
FAIL=0
SCRIPT_DIR=$(cd "$(dirname "$0")/.."; pwd)

run_test() {
    local name="$1"
    local expect_exit="$2"   # 0 = success, 1 = clean error
    local expect_match="$3"  # string that must appear in output
    local reject_match="${4:-Traceback}"  # string that must NOT appear
    shift 4
    local cmd=("$@")

    local display_cmd="${cmd[*]}"
    echo "  RUN   ${display_cmd}"

    output=$("${cmd[@]}" 2>&1)
    actual_exit=$?

    local ok=true

    if [[ "$expect_exit" != "$actual_exit" ]]; then
        ok=false
    fi

    if [[ -n "$expect_match" ]] && ! echo "$output" | grep -qF "$expect_match"; then
        ok=false
    fi

    if [[ -n "$reject_match" ]] && echo "$output" | grep -qF "$reject_match"; then
        ok=false
    fi

    if $ok; then
        echo "  PASS  $name"
    else
        echo "  FAIL  $name"
        echo "        expected exit=$expect_exit got=$actual_exit"
        echo "        expected match='$expect_match'"
        echo "        reject  match='$reject_match'"
        echo "        output (first 3 lines):"
        echo "$output" | head -3 | sed 's/^/        /'
    fi

    if $ok; then ((PASS++)); else ((FAIL++)); fi
    echo ""
}

echo "=== E2E tests for error handling (CNV-81685) ==="
echo "    Working dir: ${SCRIPT_DIR}"
echo ""

cd "$SCRIPT_DIR"

# --- upgrade_jobs_info ---

echo "-- upgrade_jobs_info --"

run_test "non-existent target version" \
    1 "Error:" "Traceback" \
    uv run upgrade_jobs_info -s 4.16.0 -t 4.16.99

run_test "non-existent target build (4.16.31)" \
    1 "Error:" "Traceback" \
    uv run upgrade_jobs_info -s 4.16.0 -t 4.16.31

run_test "downgrade rejected" \
    1 "Error:" "Traceback" \
    uv run upgrade_jobs_info -s 4.16.999 -t 4.16.36

run_test "cross-minor rejected without Y-stream flag" \
    1 "Error:" "Traceback" \
    uv run upgrade_jobs_info -s 4.18.0 -t 4.19.5

run_test "valid Z-stream upgrade returns JSON" \
    0 '"upgrade_type"' "Traceback" \
    uv run upgrade_jobs_info -s 4.16.0 -t 4.16.36

echo ""

# --- release_checklist_upgrade_plan ---

echo "-- release_checklist_upgrade_plan --"

run_test "non-existent version (4.16.99)" \
    1 "Error:" "Traceback" \
    uv run release_checklist_upgrade_plan -v 4.16.99

run_test "non-existent minor (4.99.1)" \
    1 "Error:" "Traceback" \
    uv run release_checklist_upgrade_plan -v 4.99.1

run_test "already released version without flag" \
    1 "Error:" "Traceback" \
    uv run release_checklist_upgrade_plan -v 4.16.36

run_test "already released with --skip-target-check returns JSON" \
    0 '"target_version"' "Traceback" \
    uv run release_checklist_upgrade_plan -v 4.16.36 --skip-target-check

run_test "old version 4.12.23 with --skip-target-check" \
    0 '"target_version"' "Traceback" \
    uv run release_checklist_upgrade_plan -v 4.12.23 --skip-target-check

echo ""

# --- Summary ---

TOTAL=$((PASS + FAIL))
echo "=== Results: ${PASS}/${TOTAL} passed ==="

if [[ $FAIL -gt 0 ]]; then
    echo "FAILED"
    exit 1
fi

echo "ALL PASSED"
