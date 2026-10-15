from polcomp.config import (
    JacobianSearchConfig,
    PolCompConfig,
)
from polcomp.jacobian_search import JacobianSearch


def test_fixed_step_status_limit():
    search = JacobianSearch(
        JacobianSearchConfig(adaptive_step=False)
    )

    assert search.max_total_step_deg == 15.0


def test_adaptive_step_initial_limit():
    search = JacobianSearch(
        JacobianSearchConfig(adaptive_step=True)
    )

    assert search.max_total_step_deg == 15.0


def test_adaptive_config_preserves_other_defaults():
    config = PolCompConfig(
        jacobian=JacobianSearchConfig(
            adaptive_step=True,
        )
    )

    defaults = PolCompConfig()

    assert config.jacobian.adaptive_step
    assert config.jacobian.probe_deg == defaults.jacobian.probe_deg
    assert config.jacobian.damping == defaults.jacobian.damping
    assert config.jacobian.max_step_deg == defaults.jacobian.max_step_deg
    assert config.jacobian.max_total_step_deg == 15.0
    assert config.jog == defaults.jog
    assert config.lock == defaults.lock


def test_benchmark_records_adaptive_limit():
    from benchmark import run_compensation_benchmark

    result = run_compensation_benchmark(
        disturbance=(162.0, -124.0, -168.0),
        seed=42,
        timeout_s=10.0,
        simulated_time=True,
        adaptive_step=True,
    )

    assert result.samples

    limits = {
        sample.jacobian_max_total_step_deg
        for sample in result.samples
    }

    assert limits <= {10.0, 12.0, 15.0}
    assert 15.0 in limits