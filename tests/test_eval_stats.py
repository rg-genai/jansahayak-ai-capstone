"""Small-sample statistics used by the eval reports (pure functions, no VM)."""

from __future__ import annotations

import pytest

from eval.eval_stats import (
    cohen_kappa,
    mcnemar_exact,
    paired_bootstrap_diff,
    paired_outcome_test,
    wilson_interval,
)


def test_wilson_interval_matches_reference_values_and_stays_in_bounds():
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-4) and high == pytest.approx(0.7634, abs=1e-4)
    assert wilson_interval(0, 10)[0] == 0.0 and wilson_interval(10, 10)[1] == 1.0
    assert wilson_interval(0, 0) == (0.0, 0.0)
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


def test_mcnemar_exact_uses_only_discordant_pairs():
    assert mcnemar_exact(0, 6) == pytest.approx(2 / 64)  # all 6 changes go one way
    assert mcnemar_exact(3, 3) == 1.0
    assert mcnemar_exact(0, 0) == 1.0


def test_paired_outcome_test_counts_who_won_each_item():
    result = paired_outcome_test([True, True, False, True], [True, False, False, False])
    assert (result["only_a"], result["only_b"], result["n"]) == (2, 0, 4)
    assert result["significant"] is False, "two discordant pairs can never be significant"
    with pytest.raises(ValueError):
        paired_outcome_test([True], [True, False])


def test_paired_bootstrap_is_reproducible_and_detects_a_constant_shift():
    a, b = [3.0, 4.0, 5.0, 6.0] * 5, [2.0, 3.0, 4.0, 5.0] * 5
    first, second = paired_bootstrap_diff(a, b), paired_bootstrap_diff(a, b)
    assert first == second, "fixed seed: the same inputs give the same interval"
    assert first["mean_diff"] == 1.0 and first["ci_low"] == 1.0 and first["significant"] is True
    assert paired_bootstrap_diff([], [])["n"] == 0


def test_cohen_kappa_perfect_chance_and_undefined():
    labels = ["retrieval_miss", "hallucination", "reasoning_error", "retrieval_miss"]
    assert cohen_kappa(labels, labels) == pytest.approx(1.0)
    assert cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == pytest.approx(0.0)
    assert cohen_kappa(["a", "a"], ["a", "a"]) is None
    assert cohen_kappa([], []) is None
