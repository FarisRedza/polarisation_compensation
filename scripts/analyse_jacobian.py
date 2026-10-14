#!/usr/bin/env python3

"""Analyse Jacobian corrections across compensation benchmark traces."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    'elapsed_s',
    'controller_state',
    'correction_iteration',
    'correction_baseline_score',
    'correction_predicted_score',
    'correction_measured_score',
    'correction_predicted_improvement',
    'correction_actual_improvement',
}

STEP_COLUMNS = (
    'correction_step_qwp1_deg',
    'correction_step_hwp_deg',
    'correction_step_qwp2_deg',
)


def load_corrections(directory: Path) -> pd.DataFrame:
    """Extract one row per completed correction from each trace."""

    frames = []

    paths = sorted(directory.glob('case_*.csv'))

    if not paths:
        raise FileNotFoundError(
            f'No case_*.csv files found in {directory}'
        )

    for path in paths:
        data = pd.read_csv(path)

        missing = REQUIRED_COLUMNS - set(data.columns)

        if missing:
            raise ValueError(
                f'{path.name} is missing columns: '
                f'{sorted(missing)}'
            )

        completed = (
            data['controller_state'].eq('COMPLETE').any()
        )

        corrections = data.dropna(
            subset=['correction_iteration']
        ).copy()

        corrections = corrections.drop_duplicates(
            subset=['correction_iteration'],
            keep='first',
        )

        corrections['case'] = path.stem
        corrections['completed'] = completed

        # Add correction magnitude if the trace includes step data.
        if all(
            column in corrections.columns
            for column in STEP_COLUMNS
        ):
            corrections['step_magnitude_deg'] = np.sqrt(
                sum(
                    corrections[column] ** 2
                    for column in STEP_COLUMNS
                )
            )

        frames.append(corrections)

    if not frames:
        return pd.DataFrame()

    return pd.concat(
        frames,
        ignore_index=True,
    )


def print_statistics(corrections: pd.DataFrame) -> None:
    """Summarise correction accuracy by benchmark outcome."""

    print(f'\nTotal corrections: {len(corrections)}')

    if corrections.empty:
        return

    for completed, group in corrections.groupby('completed'):
        label = 'COMPLETE' if completed else 'TIMEOUT'

        predicted = group['correction_predicted_improvement']
        actual = group['correction_actual_improvement']

        improved = actual > 0

        print(f'\n{label}')
        print('-' * len(label))

        print(f'Corrections: {len(group)}')
        print(f'Actually improved: {improved.mean():.1%}')
        print(f'Median predicted improvement: {predicted.median():.3f}')
        print(f'Median actual improvement: {actual.median():.3f}')

        print(
            'Median prediction error: '
            f'{(predicted - actual).median():.3f}'
        )

        print(
            'Median absolute prediction error: '
            f'{(predicted - actual).abs().median():.3f}'
        )


def plot_prediction_accuracy(
    corrections: pd.DataFrame,
    output: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 7))

    for completed, group in corrections.groupby('completed'):
        label = 'COMPLETE' if completed else 'TIMEOUT'

        ax.scatter(
            group['correction_predicted_improvement'],
            group['correction_actual_improvement'],
            label=label,
            alpha=0.65,
        )

    predicted = corrections['correction_predicted_improvement']
    actual = corrections['correction_actual_improvement']

    lower = min(predicted.min(), actual.min(), 0)
    upper = max(predicted.max(), actual.max(), 0)

    ax.plot(
        [lower, upper],
        [lower, upper],
        linestyle='--',
        label='Perfect prediction',
    )

    ax.axhline(0, linestyle=':', alpha=0.5)

    ax.set(
        title='Jacobian: Predicted vs Actual Improvement',
        xlabel='Predicted improvement',
        ylabel='Actual improvement',
    )

    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()

    fig.savefig(output, dpi=150)
    plt.close(fig)


def plot_step_accuracy(
    corrections: pd.DataFrame,
    output: Path,
) -> None:
    if 'step_magnitude_deg' not in corrections:
        return

    fig, ax = plt.subplots(figsize=(8, 6))

    for completed, group in corrections.groupby('completed'):
        label = 'COMPLETE' if completed else 'TIMEOUT'

        prediction_error = (
            group['correction_predicted_improvement']
            - group['correction_actual_improvement']
        )

        ax.scatter(
            group['step_magnitude_deg'],
            prediction_error,
            label=label,
            alpha=0.65,
        )

    ax.axhline(0, linestyle='--', alpha=0.6)

    ax.set(
        title='Jacobian Prediction Error vs Correction Magnitude',
        xlabel='Correction magnitude (degrees)',
        ylabel='Predicted minus actual improvement',
    )

    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()

    fig.savefig(output, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        'directory',
        type=Path,
        help='Directory containing case_*.csv traces',
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=Path('jacobian_analysis'),
    )

    args = parser.parse_args()

    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    corrections = load_corrections(args.directory)

    corrections.to_csv(
        args.output / 'corrections.csv',
        index=False,
    )

    print_statistics(corrections)

    if not corrections.empty:
        plot_prediction_accuracy(
            corrections,
            args.output / 'prediction_accuracy.png',
        )

        plot_step_accuracy(
            corrections,
            args.output / 'step_accuracy.png',
        )

    print(f'\nResults written to {args.output}')


if __name__ == '__main__':
    main()