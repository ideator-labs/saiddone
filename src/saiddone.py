from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

ClaimKind = Literal["book_appointment", "order_delivery", "other"]
ArtifactKind = Literal["appointment", "order", "hold"]
ArtifactStatus = Literal["confirmed", "hold", "missing", "failed"]
Verdict = Literal["ok", "phantom", "honest_fail"]
AssertOutcome = Literal["success", "failure"]


@dataclass(frozen=True)
class SaidClaim:
    claim_id: str
    said_at: str
    channel: str
    said_text: str
    claim_kind: ClaimKind
    asserted_outcome: AssertOutcome
    asserted_ref: str | None
    asserted_when: str | None


@dataclass(frozen=True)
class Artifact:
    kind: ArtifactKind
    ref: str
    status: ArtifactStatus
    when: str | None
    source: str


@dataclass(frozen=True)
class Match:
    claim_id: str
    verdict: Verdict
    reasons: list[str]
    artifact_ref: str | None
    proposed_outcome: AssertOutcome


@dataclass
class Run:
    policy: str
    fixture: str
    matches: list[Match] = field(default_factory=list)

    @property
    def ok(self) -> list[str]:
        return [m.claim_id for m in self.matches if m.verdict == "ok"]

    @property
    def phantom(self) -> list[str]:
        return [m.claim_id for m in self.matches if m.verdict == "phantom"]

    @property
    def honest_fail(self) -> list[str]:
        return [m.claim_id for m in self.matches if m.verdict == "honest_fail"]

    def to_dict(self) -> dict:
        return {
            "policy": self.policy,
            "fixture": self.fixture,
            "matches": [asdict(m) for m in self.matches],
            "ok": self.ok,
            "phantom": self.phantom,
            "honest_fail": self.honest_fail,
        }


def load_claims(path: Path) -> list[SaidClaim]:
    claims = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        claims.append(
            SaidClaim(
                claim_id=row["claim_id"],
                said_at=row["said_at"],
                channel=row["channel"],
                said_text=row["said_text"],
                claim_kind=row["claim_kind"],
                asserted_outcome=row["asserted_outcome"],
                asserted_ref=row.get("asserted_ref"),
                asserted_when=row.get("asserted_when"),
            )
        )
    if not claims:
        raise ValueError(f"no claims in {path}")
    return claims


def load_artifacts(path: Path) -> dict[str, Artifact]:
    raw = json.loads(path.read_text())
    out: dict[str, Artifact] = {}
    for row in raw:
        art = Artifact(
            kind=row["kind"],
            ref=row["ref"],
            status=row["status"],
            when=row.get("when"),
            source=row["source"],
        )
        out[art.ref] = art
    return out


def trust_words(claims: list[SaidClaim], artifacts: dict[str, Artifact], fixture: str) -> Run:
    run = Run(policy="trust_words", fixture=fixture)
    for c in claims:
        if c.asserted_outcome == "success":
            run.matches.append(
                Match(c.claim_id, "ok", ["trust_words:believed_success"], c.asserted_ref, c.asserted_outcome)
            )
        else:
            run.matches.append(
                Match(c.claim_id, "honest_fail", ["trust_words:believed_failure"], c.asserted_ref, c.asserted_outcome)
            )
    return run


def _find_artifact(claim: SaidClaim, artifacts: dict[str, Artifact]) -> Artifact | None:
    if claim.asserted_ref and claim.asserted_ref in artifacts:
        return artifacts[claim.asserted_ref]
    return None


def said_done(claims: list[SaidClaim], artifacts: dict[str, Artifact], fixture: str) -> Run:
    """Join each claim to an artifact by asserted_ref. hold/missing/failed are not confirmed."""
    run = Run(policy="said_done", fixture=fixture)
    for c in claims:
        art = _find_artifact(c, artifacts)
        if c.asserted_outcome == "success":
            if art is not None and art.status == "confirmed":
                when_ok = c.asserted_when is None or art.when == c.asserted_when
                if when_ok:
                    run.matches.append(
                        Match(c.claim_id, "ok", ["confirmed_artifact"], art.ref, c.asserted_outcome)
                    )
                else:
                    run.matches.append(
                        Match(
                            c.claim_id,
                            "phantom",
                            [f"when_mismatch:said={c.asserted_when} art={art.when}"],
                            art.ref,
                            c.asserted_outcome,
                        )
                    )
            elif art is not None and art.status == "hold":
                run.matches.append(
                    Match(c.claim_id, "phantom", ["hold_not_confirmed"], art.ref, c.asserted_outcome)
                )
            elif art is not None and art.status in ("missing", "failed"):
                run.matches.append(
                    Match(c.claim_id, "phantom", [f"artifact_status:{art.status}"], art.ref, c.asserted_outcome)
                )
            else:
                run.matches.append(
                    Match(c.claim_id, "phantom", ["no_artifact"], c.asserted_ref, c.asserted_outcome)
                )
        else:
            # agent asserted failure
            if art is None or art.status in ("failed", "missing", "hold"):
                run.matches.append(
                    Match(
                        c.claim_id,
                        "honest_fail",
                        ["agent_reported_failure_and_record_incomplete"],
                        None if art is None else art.ref,
                        c.asserted_outcome,
                    )
                )
            elif art.status == "confirmed":
                # said failure but record is confirmed: still surface as phantom of the claim? treat as ok mismatch
                run.matches.append(
                    Match(c.claim_id, "phantom", ["said_failure_but_confirmed"], art.ref, c.asserted_outcome)
                )
            else:
                run.matches.append(
                    Match(c.claim_id, "honest_fail", ["agent_reported_failure"], art.ref, c.asserted_outcome)
                )
    return run


def render_text(run: Run) -> str:
    lines = [f"policy={run.policy} fixture={run.fixture}"]
    for m in run.matches:
        lines.append(f"  {m.claim_id}: {m.verdict} reasons={','.join(m.reasons)} ref={m.artifact_ref}")
    lines.append(f"ok={len(run.ok)} phantom={len(run.phantom)} honest_fail={len(run.honest_fail)}")
    return "\n".join(lines)


def write_run(path: Path, run: Run) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run.to_dict(), indent=2) + "\n")
