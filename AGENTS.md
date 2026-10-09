# AGENTS.md - SaidDone

Cold-start handoff for a coding agent with no prior context.

## What it is and the one claim

Personal and voice agents routinely tell a user that something is done: the prescription is ordered, the appointment is booked, delivery is Friday. The user hears a confirmation. The system of record may show nothing, a hold, or a failed write.

In a reported Colorado specialty-pharmacy incident, an AI phone line confirmed a prescription order that was never placed. Elsewhere, silent API failures let voice agents say "you're booked" when the EHR only held a slot or rejected the write. Trusting the spoken words is not the same as joining them to the artifact.

SaidDone takes a list of `SaidClaim` rows (what the agent asserted, with an optional `asserted_ref`) and a dict of `Artifact` rows (what the record actually has). Two policies:

- `trust_words`: every success claim becomes `ok`; every failure claim becomes `honest_fail`. No join.
- `said_done`: join by `asserted_ref`. Success plus `confirmed` (and matching `when` when both sides set it) is `ok`. Success against `hold`, `missing`, `failed`, or no artifact is `phantom`. Failure against an incomplete or missing record is `honest_fail`. Failure against a `confirmed` record is `phantom` (`said_failure_but_confirmed`).

The claim `bash demo.sh` proves. On a fictional pharmacy phone confirmation for `REF-RX-1001`, `trust_words` marks it `ok` while `said_done` marks it `phantom` because the OMS row is `missing`. A clinic hold (`APT-77`) is `phantom` with reason `hold_not_confirmed`. A reported failure matching a failed write is `honest_fail`. A confirmed appointment matching the claim is `ok`.

All fixture data is fictional sample data. Refs, dates, and transcripts are made up.

## Status: real vs stubbed

Real:

- JSONL claim and JSON artifact loading (`load_claims`, `load_artifacts`).
- Policies `trust_words` and `said_done` with verdicts `ok`, `phantom`, `honest_fail`.
- Text render and JSON run output via `src/cli.py check`.
- Self-checking `demo.sh` with five paths and an independent pharmacy truth file.
- Break-check procedure: temporarily treat `hold` as confirmed; PATH C must fail; restore; pass.

Stubbed or not built:

- No live phone or voice agent. Claims are fixed JSONL.
- No EHR or OMS connector. Artifacts are a static JSON array.
- No fuzzy text matching. Outcome is the structured `asserted_outcome` field, not NLP over `said_text`.
- Join is by exact `asserted_ref` only. No kind/when fallback search.
- No Hivemind OS or Workflow Core integration.

## Data shape (with paths)

Frozen dataclasses live at the top of `src/saiddone.py`, before policy logic.

| Type | Fields | Notes |
|------|--------|-------|
| `SaidClaim` | `claim_id`, `said_at`, `channel`, `said_text`, `claim_kind`, `asserted_outcome`, `asserted_ref`, `asserted_when` | `claim_kind` in `book_appointment` / `order_delivery` / `other`. `asserted_outcome` in `success` / `failure`. |
| `Artifact` | `kind`, `ref`, `status`, `when`, `source` | `status` in `confirmed` / `hold` / `missing` / `failed`. Loaded into `dict[str, Artifact]` keyed by `ref`. |
| `Match` | `claim_id`, `verdict`, `reasons`, `artifact_ref`, `proposed_outcome` | One row per claim. |
| `Run` | `policy`, `fixture`, `matches` | Properties `ok`, `phantom`, `honest_fail` list claim ids by verdict. |

Fixtures under `fixtures/`:

- `pharmacy_claims.jsonl` + `pharmacy_artifacts.json` + `pharmacy.truth.json`
- `clinic_hold_claims.jsonl` + `clinic_hold_artifacts.json`
- `clinic_fail_claims.jsonl` + `clinic_fail_artifacts.json`
- `clinic_ok_claims.jsonl` + `clinic_ok_artifacts.json`

## Repo map

```
saiddone/
  AGENTS.md
  README.md
  LICENSE
  requirements.txt
  demo.sh
  .gitignore
  src/
    saiddone.py   # types, loaders, policies, render, write_run
    cli.py        # argparse check entrypoint
  fixtures/       # fictional sample claims and artifacts
  data/           # gitignored run output from demo.sh
```

## Verified run steps

```bash
cd /path/to/saiddone
bash demo.sh
```

Expect five PASS lines, then `SUMMARY: 5 passed, 0 failed` and `ALL CLAIMS PASSED`, exit 0.

Manual one-shot:

```bash
PYTHONPATH=src python3 src/cli.py check \
  --claims fixtures/pharmacy_claims.jsonl \
  --artifacts fixtures/pharmacy_artifacts.json \
  --policy said_done \
  --fixture pharmacy \
  --out data/pharmacy-said_done.json
```

## Design decisions

1. Structured `asserted_outcome` on the claim, not phrase heuristics over `said_text`. The demo is about join semantics, not speech parsing.
2. Join only by `asserted_ref`. Keeps the phantom case crisp when the OMS has no matching row or a non-confirmed status.
3. `hold` is never `confirmed`. A voice agent that says "you're booked" while the EHR status is `hold` is a phantom.
4. `trust_words` is the control policy. It shows what happens when the product trusts the agent's prose.

## Limits

- Single-file stdlib Python. No tests beyond `demo.sh`.
- No concurrency, auth, or retention model.
- When mismatch only fires when both sides set `asserted_when` / `when` and they differ.
- Failure + `confirmed` is labeled `phantom` (`said_failure_but_confirmed`); there is no separate "surprise success" verdict.

## Break check

Temporarily change `said_done` so `hold` counts as confirmed, then re-run the demo. PATH C must fail. Restore the original logic and re-run; all five paths must pass.

Example mutation (do not leave in place):

In `src/saiddone.py`, change the success branch so that `art.status in ("confirmed", "hold")` is treated like confirmed (map hold into the confirmed path). Demo PATH C expects `hold_not_confirmed` and phantom; after the mutation it will get `ok` and fail.

Restore the file, run `bash demo.sh` again, expect all pass.

## Prioritized next steps

1. Add a when-mismatch fixture (success claim with wrong date on a confirmed artifact) and a demo path.
   Done when: a new fixture + PATH F asserts `when_mismatch` phantom and `demo.sh` stays green.
2. Wire a read-only EHR/OMS adapter that returns the same `Artifact` shape from a sandbox API.
   Done when: one integration fixture replaces `clinic_ok_artifacts.json` and demo still exits 0.
3. Emit a small HTML report (ok / phantom / honest_fail columns) like StandingOrders.
   Done when: `demo.sh` writes `data/report.html` and opens without JS.

## Working rules

- Keep code simple. Name the data shape first.
- Verify against the real artifact (`bash demo.sh`) before declaring done.
- Unslopped prose. No em-dashes in docs.
- All sample data stays fictional. Label it in fixtures/README.md and the demo banner.
- Stdlib only unless a next step explicitly adds a dependency.

## Sources

- https://nope.net/incidents/2026-colorado-specialty-pharmacy-ai-phone-line-confirmed-prescription-order-never-placed-first-person
- https://www.soundflare.ai/blog/silent-api-failure-voice-agent-booking
- https://techcrunch.com/2026/10/08/cal-ais-19-year-old-founder-just-raised-10m-for-his-new-ai-startup/
