import dataclasses

import pytest

from polcomp.config import (
    PolCompConfig,
    JacobianSearchConfig,
    JogSearchConfig,
    LockConfig,
)


def test_default_configuration():
    config = PolCompConfig()

    assert config.target_qber == 0.05
    assert config.target_qx == 0.05

    assert config.jacobian.probe_deg == 2.0
    assert config.jacobian.measurements == 3
    assert config.jacobian.damping == 0.05
    assert config.jacobian.max_step_deg == 10.0
    assert config.jacobian.max_total_step_deg == 15.0
    assert config.jacobian.min_determinant == 1e-6
    assert config.jacobian.min_predicted_improvement == 0.02

    assert config.jog.reference_measurements == 3
    assert config.jog.jog_measurements == 3
    assert config.jog.worsening_measurements == 3
    assert config.jog.jog_velocity == 5.0
    assert config.jog.candidate_score == 0.90

    assert config.lock.measurements == 5


def test_configuration_is_immutable():
    config = PolCompConfig()

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.target_qber = 0.02

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.jacobian.probe_deg = 5.0


def test_custom_configuration():
    config = PolCompConfig(
        target_qber=0.02,
        jacobian=JacobianSearchConfig(
            probe_deg=1.5,
            measurements=5,
        ),
        jog=JogSearchConfig(
            jog_velocity=3.0,
        ),
        lock=LockConfig(
            measurements=10,
        ),
    )

    assert config.target_qber == 0.02
    assert config.jacobian.probe_deg == 1.5
    assert config.jacobian.measurements == 5
    assert config.jog.jog_velocity == 3.0
    assert config.lock.measurements == 10