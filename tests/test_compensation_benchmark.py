import sys
import pathlib

import pytest

sys.path.append(str(pathlib.Path(__file__).parent.parent.joinpath('tests')))
from benchmark import (
    run_compensation_benchmark,
)

@pytest.mark.parametrize(
    'disturbance',
    [
        (162.0, -124.0, -168.0),
        (-143.0, 384.0, 88.0),
        (24.0, 37.0, -71.0)
    ],
)
def test_known_disturbances(disturbance: tuple[float,float,float]) -> None:
    result = run_compensation_benchmark(
        disturbance=disturbance,
        seed=42,
        timeout_s=120.0,
    )

    print(result.summary())

    assert result.completed, result.failure_details()
