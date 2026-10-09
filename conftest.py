from unittest.mock import Mock

import pytest

import polcomp.polcomp as controller_module


def pytest_addoption(parser) -> None:
    parser.addoption(
        '--realtime',
        action='store_true',
        default=False,
        help=(
            'Run compensation benchmarks using real wall-clock '
            'time instead of the accelerated simulation clock.'
        ),
    )


@pytest.fixture
def simulated_time(
    request: pytest.FixtureRequest,
) -> bool:
    return not request.config.getoption(
        '--realtime'
    )

@pytest.fixture
def controller():
    """Construct a controller without running a simulation."""
    return controller_module.PolCompController(
        qwp1=Mock(),
        hwp=Mock(),
        qwp2=Mock(),
        measurements=Mock(),
    )