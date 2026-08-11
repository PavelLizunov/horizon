from pathlib import Path

from src.verification.evaluation import run_adversarial_evaluation


def test_recorded_adversarial_corpus_passes_without_false_support() -> None:
    fixture = Path(__file__).parent / "fixtures" / "verification_adversarial.json"

    summary = run_adversarial_evaluation(fixture)

    assert summary.total_cases == 10
    assert summary.passed_cases == 10
    assert summary.false_supported == 0
    assert summary.failures == ()
