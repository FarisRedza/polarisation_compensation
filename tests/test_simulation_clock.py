"""Regression tests for the simulated motor clock contract."""

import time

import pytest
from qtoolkit.polarisation import QuarterWaveplate
from polcomp.simulation import RealTimeClock, SimulationClock, SimulatedMotor


def test_default_motor_clock_is_realtime():
    motor = SimulatedMotor(waveplate=QuarterWaveplate())
    print(type(motor.clock))
    assert isinstance(motor.clock, RealTimeClock)


def test_default_motor_progresses_without_manual_clock_advance():
    motor = SimulatedMotor(waveplate=QuarterWaveplate())
    motor.update_settings(acceleration=1000.0, max_velocity=1000.0)
    motor.move_by(0.25)
    time.sleep(0.05)
    assert not motor.is_moving
    assert motor.position == pytest.approx(0.25)


def test_explicit_simulation_clock_requires_advance():
    clock = SimulationClock()
    motor = SimulatedMotor(waveplate=QuarterWaveplate(), clock=clock)
    motor.move_by(10.0)
    assert motor.is_moving
    assert motor.position == pytest.approx(0.0)
    clock.advance(2.0)
    assert not motor.is_moving
    assert motor.position == pytest.approx(10.0)


def test_shared_clock_moves_multiple_motors():
    clock = SimulationClock()
    first = SimulatedMotor(waveplate=QuarterWaveplate(), clock=clock)
    second = SimulatedMotor(waveplate=QuarterWaveplate(), clock=clock)
    first.move_by(10.0)
    second.move_by(-5.0)
    clock.advance(2.0)
    assert first.position == pytest.approx(10.0)
    assert second.position == pytest.approx(-5.0)
    assert not first.is_moving
    assert not second.is_moving


@pytest.mark.parametrize('clock_type', [SimulationClock, RealTimeClock])
def test_clock_rejects_negative_advance(clock_type):
    with pytest.raises(ValueError):
        clock_type().advance(-0.1)
