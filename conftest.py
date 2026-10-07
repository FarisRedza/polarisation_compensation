import pytest


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