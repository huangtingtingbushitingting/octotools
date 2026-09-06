import pytest

from octotools.research.experiment import (
    EXPERIMENT_GROUPS,
    get_experiment_group,
)


def test_baseline_is_one_attempt_without_memory_or_cache():
    group = get_experiment_group("b0")
    assert group.max_attempts == 1
    assert not group.enable_plan_cache
    assert not group.sharing_policy.share_observations
    assert not group.sharing_policy.share_failures


def test_plan_gate_ablation_differs_only_in_evidence_path():
    p0 = EXPERIMENT_GROUPS["P0"]
    p1 = EXPERIMENT_GROUPS["P1"]
    assert p0.enable_plan_cache and p1.enable_plan_cache
    assert p0.plan_cache_mode == p1.plan_cache_mode == "assist"
    assert p0.sharing_policy == p1.sharing_policy
    assert not p0.plan_cache_use_evidence
    assert p1.plan_cache_use_evidence


def test_combined_group_enables_both_memory_layers():
    group = EXPERIMENT_GROUPS["C1"]
    assert group.sharing_policy.share_observations
    assert group.sharing_policy.share_failures
    assert group.enable_plan_cache
    assert group.plan_cache_use_evidence


def test_unknown_group_is_rejected():
    with pytest.raises(ValueError, match="Unknown experiment group"):
        get_experiment_group("unknown")
