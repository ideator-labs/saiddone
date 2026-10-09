from __future__ import annotations

import argparse
from pathlib import Path

from saiddone import load_artifacts, load_claims, render_text, said_done, trust_words, write_run


def main() -> None:
    parser = argparse.ArgumentParser(prog="saiddone")
    sub = parser.add_subparsers(dest="cmd", required=True)

    check = sub.add_parser("check", help="Join claims to artifacts under a policy")
    check.add_argument("--claims", required=True, type=Path)
    check.add_argument("--artifacts", required=True, type=Path)
    check.add_argument("--policy", required=True, choices=("trust_words", "said_done"))
    check.add_argument("--fixture", required=True)
    check.add_argument("--out", required=True, type=Path)

    args = parser.parse_args()
    if args.cmd == "check":
        claims = load_claims(args.claims)
        artifacts = load_artifacts(args.artifacts)
        if args.policy == "trust_words":
            run = trust_words(claims, artifacts, args.fixture)
        else:
            run = said_done(claims, artifacts, args.fixture)
        print(render_text(run))
        write_run(args.out, run)


if __name__ == "__main__":
    main()
