import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import pandas as pd

from scripts.plot_logfile import (
    BENCHMARK_COLUMNS,
    plot_benchmark_trace,
)


def test_benchmark_plotting():
    data = pd.DataFrame({
        'elapsed_s': [0.1, 0.2, 0.3],
        'controller_state': ['SEARCH', 'SEARCH', 'COMPLETE'],
        'search_state': ['START', 'JACOBIAN_PROBE_MOVE', ''],
        'qber': [0.20, 0.10, 0.02],
        'qx': [0.15, 0.08, 0.03],
        'search_rms': [3.54, 1.81, 0.51],
        'acceptance_score': [4.0, 2.0, 0.6],
        'jacobian_iteration': [0, 1, 1],
        'jacobian_condition': [None, 2.0, 2.0],
        'jacobian_fallback_count': [0, 0, 0],
        'qwp1_deg': [0.0, 2.0, 4.0],
        'hwp_deg': [0.0, 1.0, 2.0],
        'qwp2_deg': [0.0, 0.0, 1.0],
    })

    assert BENCHMARK_COLUMNS.issubset(data.columns)

    try:
        plot_benchmark_trace(data)
        assert len(plt.get_fignums()) == 4
    finally:
        plt.close('all')