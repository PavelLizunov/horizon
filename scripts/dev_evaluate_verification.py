"""Run the offline Evidence Ledger adversarial policy corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.verification.evaluation import run_adversarial_evaluation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "fixture",
        nargs="?",
        type=Path,
        default=Path("tests/fixtures/verification_adversarial.json"),
    )
    args = parser.parse_args()
    summary = run_adversarial_evaluation(args.fixture)
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0 if not summary.failures and summary.false_supported == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
