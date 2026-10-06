#!/usr/bin/env python3

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

def load_log(
    filename: Path,
) -> pd.DataFrame:
    data = pd.read_csv(
        filename
    )

    required_columns = {
        'time_s',
        'qber',
        'qx',
        'dist_qwp1_deg',
        'dist_hwp_deg',
        'dist_qwp2_deg',
        'comp_qwp1_deg',
        'comp_hwp_deg',
        'comp_qwp2_deg',
        'controller_state',
        'search_state',
        'search_waveplate',
        'search_measurement_count',
        'objective',
        'search_jog_velocity_deg_s',
        'search_worsening_count',
        'search_cycle',
        'search_cycle_start_score',
        'search_cycle_best_score',
        'search_cycle_improvement',
        'search_retained_improvement',
        'search_stagnant',
        'search_escape_count',
        'controller_moving',
    }

    missing = (
        required_columns
        - set(data.columns)
    )

    if missing:
        raise ValueError(
            'Log is missing required columns: '
            + ', '.join(
                sorted(missing)
            )
        )

    return data

def add_event_lines(
    ax,
    data: pd.DataFrame,
) -> None:
    if 'event' not in data:
        return

    events = data[
        data['event'].notna()
        & (data['event'] != '')
    ]

    for _, row in events.iterrows():
        ax.axvline(
            row['time_s'],
            linestyle=':',
            alpha=0.4,
        )


def add_target_line(
    ax,
    target: float,
) -> None:
    ax.axhline(
        target,
        linestyle='--',
        alpha=0.6,
        label=f'Target ({target:.1%})',
    )

def plot_errors(
    data: pd.DataFrame,
    *,
    target: float,
) -> None:
    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    ax.plot(
        data['time_s'],
        data['qber'] * 100,
        label='QBER',
    )

    ax.plot(
        data['time_s'],
        data['qx'] * 100,
        label='Qx',
    )

    ax.axhline(
        target * 100,
        linestyle='--',
        alpha=0.6,
        label=f'Target ({target:.1%})',
    )

    add_event_lines(
        ax,
        data,
    )

    ax.set_title(
        'Polarisation Error'
    )

    ax.set_xlabel(
        'Time (s)'
    )

    ax.set_ylabel(
        'Error (%)'
    )

    ax.grid(
        alpha=0.3
    )

    ax.legend()

    fig.tight_layout()

def plot_disturbance(
    data: pd.DataFrame,
) -> None:
    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    ax.plot(
        data['time_s'],
        data['dist_qwp1_deg'],
        label='QWP1',
    )

    ax.plot(
        data['time_s'],
        data['dist_hwp_deg'],
        label='HWP',
    )

    ax.plot(
        data['time_s'],
        data['dist_qwp2_deg'],
        label='QWP2',
    )

    add_event_lines(
        ax,
        data,
    )

    ax.set_title(
        'User-Controlled Disturbance'
    )

    ax.set_xlabel(
        'Time (s)'
    )

    ax.set_ylabel(
        'Waveplate angle (deg)'
    )

    ax.grid(
        alpha=0.3
    )

    ax.legend()

    fig.tight_layout()

def plot_compensation(
    data: pd.DataFrame,
) -> None:
    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    ax.plot(
        data['time_s'],
        data['comp_qwp1_deg'],
        label='QWP1',
    )

    ax.plot(
        data['time_s'],
        data['comp_hwp_deg'],
        label='HWP',
    )

    ax.plot(
        data['time_s'],
        data['comp_qwp2_deg'],
        label='QWP2',
    )

    add_event_lines(
        ax,
        data,
    )

    ax.set_title(
        'Active Compensation'
    )

    ax.set_xlabel(
        'Time (s)'
    )

    ax.set_ylabel(
        'Waveplate angle (deg)'
    )

    ax.grid(
        alpha=0.3
    )

    ax.legend()

    fig.tight_layout()

def plot_objective(
    data: pd.DataFrame,
) -> None:
    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    ax.plot(
        data['time_s'],
        data['objective'],
        label='Objective',
    )

    ax.axhline(
        1.0,
        linestyle='--',
        alpha=0.6,
        label='Target',
    )

    add_event_lines(
        ax,
        data,
    )

    ax.set_title(
        'Controller Objective'
    )

    ax.set_xlabel(
        'Time (s)'
    )

    ax.set_ylabel(
        'Objective'
    )

    ax.grid(
        alpha=0.3
    )

    ax.legend()

    fig.tight_layout()

def plot_search_jog(
    data: pd.DataFrame,
) -> None:
    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    search = data[
        data['controller_state'] == 'SEARCH'
    ]

    if search.empty:
        plt.close(fig)
        return

    ax.plot(
        search['time_s'],
        search['search_jog_velocity_deg_s'],
        label='Jog velocity',
    )

    add_event_lines(
        ax,
        data,
    )

    ax.set_title(
        'Search Jog Velocity'
    )

    ax.set_xlabel(
        'Time (s)'
    )

    ax.set_ylabel(
        'Jog velocity (deg/s)'
    )

    ax.grid(
        alpha=0.3
    )

    ax.legend()

    fig.tight_layout()


def plot_search_worsening_count(
    data: pd.DataFrame,
) -> None:
    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    search = data[
        data['controller_state'] == 'SEARCH'
    ]

    if search.empty:
        plt.close(fig)
        return

    ax.plot(
        search['time_s'],
        search['search_worsening_count'],
        marker='.',
        linestyle='-',
        label='Worsening samples',
    )

    add_event_lines(
        ax,
        data,
    )

    ax.set_title(
        'Search Worsening Count'
    )

    ax.set_xlabel(
        'Time (s)'
    )

    ax.set_ylabel(
        'Consecutive samples'
    )

    ax.grid(
        alpha=0.3
    )

    ax.legend()

    fig.tight_layout()



def plot_search_cycles(
    data: pd.DataFrame,
) -> None:
    search = data[
        data['controller_state'] == 'SEARCH'
    ].copy()

    completed = search[
        search['search_cycle_improvement'].notna()
    ].copy()

    if completed.empty:
        return

    # Keep one row for each completed cycle. The completion row is the
    # first row carrying that cycle's calculated improvement.
    completed = (
        completed
        .drop_duplicates(
            subset=['search_cycle'],
            keep='first',
        )
        .sort_values('search_cycle')
    )

    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    ax.plot(
        completed['search_cycle'],
        completed['search_cycle_start_score'],
        marker='o',
        label='Cycle start',
    )

    ax.plot(
        completed['search_cycle'],
        completed['search_cycle_best_score'],
        marker='o',
        label='Cycle best',
    )

    ax.set_title(
        'SEARCH Cycle Objective'
    )

    ax.set_xlabel(
        'Completed search cycle'
    )

    ax.set_ylabel(
        'RMS search objective'
    )

    ax.grid(
        alpha=0.3
    )

    ax.legend()

    fig.tight_layout()

    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    ax.plot(
        completed['search_cycle'],
        100 * completed['search_cycle_improvement'],
        marker='o',
    )

    ax.axhline(
        0.0,
        linestyle='--',
        alpha=0.6,
    )

    ax.set_title(
        'SEARCH Cycle Improvement'
    )

    ax.set_xlabel(
        'Completed search cycle'
    )

    ax.set_ylabel(
        'Improvement (%)'
    )

    ax.grid(
        alpha=0.3
    )

    fig.tight_layout()



def plot_search_stagnation(
    data: pd.DataFrame,
) -> None:
    search = data[
        data['controller_state'] == 'SEARCH'
    ].copy()

    retained = search[
        search['search_retained_improvement'].notna()
    ].copy()

    if not retained.empty:
        retained = (
            retained
            .drop_duplicates(
                subset=[
                    'search_cycle',
                    'search_retained_improvement',
                ],
                keep='first',
            )
            .sort_values('time_s')
        )

        fig, ax = plt.subplots(
            figsize=(11, 5)
        )

        ax.plot(
            retained['time_s'],
            100 * retained[
                'search_retained_improvement'
            ],
            marker='o',
            label='Retained improvement',
        )

        ax.axhline(
            5.0,
            linestyle='--',
            alpha=0.6,
            label='Stagnation threshold',
        )

        ax.set_title(
            'SEARCH Retained Progress'
        )

        ax.set_xlabel(
            'Time (s)'
        )

        ax.set_ylabel(
            'Improvement over 3 cycles (%)'
        )

        ax.grid(
            alpha=0.3
        )

        ax.legend()

        fig.tight_layout()

    escapes = search[
        search['search_escape_count'].diff().fillna(0) > 0
    ]

    if not escapes.empty:
        print()
        print('SEARCH escapes')
        print('--------------')

        for _, row in escapes.iterrows():
            print(
                f'{row["time_s"]:8.3f} s  '
                f'escape {int(row["search_escape_count"])}  '
                f'QWP1={row["comp_qwp1_deg"]:.2f}°'
            )


def plot_coincidences(
    data: pd.DataFrame,
) -> None:
    coincidence_columns = [
        'coinc_HH',
        'coinc_HV',
        'coinc_VH',
        'coinc_VV',
        'coinc_DD',
        'coinc_DA',
        'coinc_AD',
        'coinc_AA',
    ]

    available = [
        column
        for column in coincidence_columns
        if column in data
    ]

    if not available:
        return

    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    for column in available:
        ax.plot(
            data['time_s'],
            data[column],
            label=column.removeprefix(
                'coinc_'
            ),
        )

    add_event_lines(
        ax,
        data,
    )

    ax.set_title(
        'Coincidence Counts'
    )

    ax.set_xlabel(
        'Time (s)'
    )

    ax.set_ylabel(
        'Counts per measurement'
    )

    ax.grid(
        alpha=0.3
    )

    ax.legend(
        ncols=4
    )

    fig.tight_layout()

def plot_singles(
    data: pd.DataFrame,
) -> None:
    columns = [
        f'single_ch{channel}'
        for channel in range(8)
    ]

    available = [
        column
        for column in columns
        if column in data
    ]

    if not available:
        return

    fig, ax = plt.subplots(
        figsize=(11, 5)
    )

    for column in available:
        ax.plot(
            data['time_s'],
            data[column],
            label=column.removeprefix(
                'single_'
            ),
        )

    add_event_lines(
        ax,
        data,
    )

    ax.set_title(
        'Singles Counts'
    )

    ax.set_xlabel(
        'Time (s)'
    )

    ax.set_ylabel(
        'Counts per measurement'
    )

    ax.grid(
        alpha=0.3
    )

    ax.legend(
        ncols=4
    )

    fig.tight_layout()

def plot_search_trajectory(
    data: pd.DataFrame,
) -> None:
    waveplates = {
        'QWP1': 'comp_qwp1_deg',
        'HWP': 'comp_hwp_deg',
        'QWP2': 'comp_qwp2_deg',
    }

    for waveplate, position_column in (
        waveplates.items()
    ):
        search = data[
            (data['controller_state'] == 'SEARCH')
            & (
                data['search_waveplate']
                == waveplate
            )
            & data['objective'].notna()
        ]

        if search.empty:
            continue

        fig, ax = plt.subplots(
            figsize=(8, 5)
        )

        moving = search[
            search['controller_moving'].astype(bool)
        ]

        stationary = search[
            ~search['controller_moving'].astype(bool)
        ]

        if not moving.empty:
            ax.plot(
                moving[position_column],
                moving['objective'],
                marker='.',
                linestyle='-',
                label='Jog measurements',
            )

        if not stationary.empty:
            ax.scatter(
                stationary[position_column],
                stationary['objective'],
                marker='x',
                label='Stationary measurements',
            )

        ax.axhline(
            1.0,
            linestyle='--',
            alpha=0.6,
            label='Target',
        )

        ax.set_title(
            f'{waveplate} Search Trajectory'
        )

        ax.set_xlabel(
            f'Compensation {waveplate} '
            'angle (deg)'
        )

        ax.set_ylabel(
            'Objective'
        )

        ax.grid(
            alpha=0.3
        )

        ax.legend()

        fig.tight_layout()

def print_events(
    data: pd.DataFrame,
) -> None:
    if 'event' not in data:
        return

    events = data[
        data['event'].notna()
        & (data['event'] != '')
    ]

    if events.empty:
        return

    print()
    print('Events')
    print('------')

    for _, row in events.iterrows():
        print(
            f'{row["time_s"]:8.3f} s  '
            f'{row["event"]}'
        )

def print_summary(
    data: pd.DataFrame,
) -> None:
    print()
    print('Run summary')
    print('-----------')

    print(
        f'Duration: '
        f'{data["time_s"].max():.2f} s'
    )

    print(
        f'Measurements: '
        f'{len(data)}'
    )

    print(
        f'Mean QBER: '
        f'{data["qber"].mean():.2%}'
    )

    print(
        f'Mean Qx: '
        f'{data["qx"].mean():.2%}'
    )

    print(
        f'Minimum QBER: '
        f'{data["qber"].min():.2%}'
    )

    print(
        f'Minimum Qx: '
        f'{data["qx"].min():.2%}'
    )

    if data['objective'].notna().any():
        print(
            f'Minimum objective: '
            f'{data["objective"].min():.3f}'
        )

    print()
    print(
        'Final disturbance: '
        f'QWP1={data["dist_qwp1_deg"].iloc[-1]:.2f}°, '
        f'HWP={data["dist_hwp_deg"].iloc[-1]:.2f}°, '
        f'QWP2={data["dist_qwp2_deg"].iloc[-1]:.2f}°'
    )

    print(
        'Final compensation: '
        f'QWP1={data["comp_qwp1_deg"].iloc[-1]:.2f}°, '
        f'HWP={data["comp_hwp_deg"].iloc[-1]:.2f}°, '
        f'QWP2={data["comp_qwp2_deg"].iloc[-1]:.2f}°'
    )

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            'Plot a polarisation compensation '
            'CSV log.'
        )
    )

    parser.add_argument(
        'log',
        type=Path,
        help='CSV log file',
    )

    parser.add_argument(
        '--target',
        type=float,
        default=0.05,
        help=(
            'QBER/Qx target as a fraction '
            '(default: 0.05)'
        ),
    )

    args = parser.parse_args()

    data = load_log(
        args.log
    )

    print(
        f'Loaded: {args.log}'
    )

    print_summary(
        data
    )

    print_events(
        data
    )

    plot_errors(
        data,
        target=args.target,
    )

    # plot_disturbance(
    #     data
    # )

    plot_compensation(
        data
    )

    plot_objective(
        data
    )

    plot_search_jog(
        data
    )

    plot_search_worsening_count(
        data
    )

    plot_search_cycles(
        data
    )

    plot_search_stagnation(
        data
    )

    plot_search_trajectory(
        data
    )

    # plot_coincidences(
    #     data
    # )

    # plot_singles(
    #     data
    # )

    plt.show()


if __name__ == '__main__':
    main()