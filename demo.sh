#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=src

rm -rf data && mkdir data

passed=0
failed=0

record() {
  if [ "$1" -eq 0 ]; then
    echo "$2: PASS"
    passed=$((passed + 1))
  else
    echo "$2: FAIL"
    failed=$((failed + 1))
  fi
}

CLI=(python3 src/cli.py)

echo "SaidDone demo. Fictional sample data: pharmacy phone confirmations and clinic bookings."
echo "Each spoken claim is joined to a system-of-record artifact: ok, phantom, or honest_fail."
echo

echo "=== A: trust_words / pharmacy ==="
"${CLI[@]}" check \
  --claims fixtures/pharmacy_claims.jsonl \
  --artifacts fixtures/pharmacy_artifacts.json \
  --policy trust_words \
  --fixture pharmacy \
  --out data/pharmacy-trust_words.json
echo

echo "=== B: said_done / pharmacy ==="
"${CLI[@]}" check \
  --claims fixtures/pharmacy_claims.jsonl \
  --artifacts fixtures/pharmacy_artifacts.json \
  --policy said_done \
  --fixture pharmacy \
  --out data/pharmacy-said_done.json
echo

echo "=== C: said_done / clinic_hold ==="
"${CLI[@]}" check \
  --claims fixtures/clinic_hold_claims.jsonl \
  --artifacts fixtures/clinic_hold_artifacts.json \
  --policy said_done \
  --fixture clinic_hold \
  --out data/clinic_hold-said_done.json
echo

echo "=== D: said_done / clinic_fail ==="
"${CLI[@]}" check \
  --claims fixtures/clinic_fail_claims.jsonl \
  --artifacts fixtures/clinic_fail_artifacts.json \
  --policy said_done \
  --fixture clinic_fail \
  --out data/clinic_fail-said_done.json
echo

echo "=== E: said_done / clinic_ok ==="
"${CLI[@]}" check \
  --claims fixtures/clinic_ok_claims.jsonl \
  --artifacts fixtures/clinic_ok_artifacts.json \
  --policy said_done \
  --fixture clinic_ok \
  --out data/clinic_ok-said_done.json
echo

rc=0
python3 - <<'PY' || rc=1
import json
run = json.load(open("data/pharmacy-trust_words.json"))
truth = json.load(open("fixtures/pharmacy.truth.json"))["trust_words"]
ok = run["ok"] == truth["ok"] and run["phantom"] == truth["phantom"] and run["honest_fail"] == truth["honest_fail"]
raise SystemExit(0 if ok else 1)
PY
record $rc "PATH A (trust_words pharmacy: believes success -> ok)"

rc=0
python3 - <<'PY' || rc=1
import json
run = json.load(open("data/pharmacy-said_done.json"))
truth = json.load(open("fixtures/pharmacy.truth.json"))["said_done"]
ok = (
    run["ok"] == truth["ok"]
    and run["phantom"] == truth["phantom"]
    and run["honest_fail"] == truth["honest_fail"]
    and any("artifact_status:missing" in r or "no_artifact" in r for m in run["matches"] for r in m["reasons"])
)
raise SystemExit(0 if ok else 1)
PY
record $rc "PATH B (said_done pharmacy: missing order -> phantom)"

rc=0
python3 - <<'PY' || rc=1
import json
run = json.load(open("data/clinic_hold-said_done.json"))
ok = (
    run["phantom"] == ["clinic-hold-1"]
    and run["ok"] == []
    and run["honest_fail"] == []
    and any("hold_not_confirmed" in r for m in run["matches"] for r in m["reasons"])
)
raise SystemExit(0 if ok else 1)
PY
record $rc "PATH C (said_done clinic_hold: hold_not_confirmed -> phantom)"

rc=0
python3 - <<'PY' || rc=1
import json
run = json.load(open("data/clinic_fail-said_done.json"))
ok = (
    run["honest_fail"] == ["clinic-fail-1"]
    and run["ok"] == []
    and run["phantom"] == []
)
raise SystemExit(0 if ok else 1)
PY
record $rc "PATH D (said_done clinic_fail: honest_fail)"

rc=0
python3 - <<'PY' || rc=1
import json
run = json.load(open("data/clinic_ok-said_done.json"))
ok = (
    run["ok"] == ["clinic-ok-1"]
    and run["phantom"] == []
    and run["honest_fail"] == []
    and any("confirmed_artifact" in r for m in run["matches"] for r in m["reasons"])
)
raise SystemExit(0 if ok else 1)
PY
record $rc "PATH E (said_done clinic_ok: confirmed -> ok)"

echo
echo "SUMMARY: ${passed} passed, ${failed} failed"
if [ "$failed" -ne 0 ]; then
  exit 1
fi
echo "ALL CLAIMS PASSED"
