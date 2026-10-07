import csv
import curses
import datetime
import time
from pathlib import Path

import numpy as np

from qtoolkit.polarisation import (
    QuarterWaveplate,
    HalfWaveplate,
    PHI_PLUS,
    PolarisationChannelMap,
    BB84Measurement,
    BB84MeasurementPair,
)

from polcomp import (
    SimulatedEPS,
    SimulatedPolCompSystem,
    SimulatedTimetagger,
    SimulatedMotor,
    PolCompController,
)

SEARCH_WAVEPLATE_NAMES = (
    'QWP1',
    'HWP',
    'QWP2',
)

# Simulation settings
INTERVAL_S = 0.1
PAIR_RATE_HZ = 40_000
MEASUREMENT_TIME_S = 0.1
COINCIDENCE_WINDOW_PS = 1_000
MANUAL_STEP_DEG = 1.0

LOG_DIRECTORY = Path(
    'logs'
)
LOG_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)
LOG_FILE = (
    LOG_DIRECTORY
    / (
        'polcomp_'
        + datetime.datetime.now().strftime(
            '%Y%m%d_%H%M%S'
        )
        + '.csv'
    )
)
LOG_FIELDS = [
    'time_s',
    'event',

    # User-controlled disturbance
    'dist_qwp1_deg',
    'dist_hwp_deg',
    'dist_qwp2_deg',

    # Active compensation
    'comp_qwp1_deg',
    'comp_hwp_deg',
    'comp_qwp2_deg',

    # QKD measurements
    'qber',
    'qx',
    'worst_error',

    # Controller
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

    # Empirical Jacobian SEARCH
    'jacobian_iteration',
    'jacobian_probe_index',
    'jacobian_condition',
    'jacobian_predicted_score',
    'jacobian_step_qwp1_deg',
    'jacobian_step_hwp_deg',
    'jacobian_step_qwp2_deg',
    'jacobian_fallback_count',

    'best_score',
    'best_position_deg',
    'controller_moving',

    # Singles
    'single_ch0',
    'single_ch1',
    'single_ch2',
    'single_ch3',
    'single_ch4',
    'single_ch5',
    'single_ch6',
    'single_ch7',

    # Coincidences
    'coinc_HH',
    'coinc_HV',
    'coinc_VH',
    'coinc_VV',
    'coinc_DD',
    'coinc_DA',
    'coinc_AD',
    'coinc_AA',
]

source = SimulatedEPS(
    state=PHI_PLUS,
    pair_rate_hz=PAIR_RATE_HZ,
)


disturbance_qwp1 = SimulatedMotor(
    waveplate=QuarterWaveplate(),
)
disturbance_hwp = SimulatedMotor(
    waveplate=HalfWaveplate(),
)
disturbance_qwp2 = SimulatedMotor(
    waveplate=QuarterWaveplate(),
)
disturbance_waveplates = [
    disturbance_qwp1,
    disturbance_hwp,
    disturbance_qwp2,
]

compensation_qwp1 = SimulatedMotor(
    waveplate=QuarterWaveplate(),
)
compensation_hwp = SimulatedMotor(
    waveplate=HalfWaveplate(),
)
compensation_qwp2 = SimulatedMotor(
    waveplate=QuarterWaveplate(),
)
compensation_waveplates = [
    compensation_qwp1,
    compensation_hwp,
    compensation_qwp2,
]

waveplates = [
    *disturbance_waveplates,
    *compensation_waveplates,
]

# BB84 measurements
first_channels = PolarisationChannelMap(
    h=0,
    v=1,
    d=2,
    a=3,
)
second_channels = PolarisationChannelMap(
    h=4,
    v=5,
    d=6,
    a=7,
)
measurements = BB84MeasurementPair(
    first=BB84Measurement(
        channels=first_channels,
    ),
    second=BB84Measurement(
        channels=second_channels,
    ),
)

# Simulated optical/detection system
channel_rates = {
    channel: 25_000
    for channel in range(8)
}

system = SimulatedPolCompSystem(
    source=source,
    waveplates=waveplates,
    measurements=measurements,
    channel_rates=channel_rates,
    coincidence_delay_ps=300,
    coincidence_jitter_ps=50,
    rng=np.random.default_rng(42),
)

# Simulated timetagger
timetagger = SimulatedTimetagger(
    source=system,
    measurements=measurements,
)

# Active polarisation compensation controller
controller = PolCompController(
    qwp1=compensation_qwp1,
    hwp=compensation_hwp,
    qwp2=compensation_qwp2,
    measurements=measurements,
    target_qber=0.05,
    target_qx=0.05,
    lock_measurements=5
)

# Coincidence definitions
coincidence_pairs = {
    'HH': (
        first_channels.h,
        second_channels.h,
    ),
    'HV': (
        first_channels.h,
        second_channels.v,
    ),
    'VH': (
        first_channels.v,
        second_channels.h,
    ),
    'VV': (
        first_channels.v,
        second_channels.v,
    ),
    'DD': (
        first_channels.d,
        second_channels.d,
    ),
    'DA': (
        first_channels.d,
        second_channels.a,
    ),
    'AD': (
        first_channels.a,
        second_channels.d,
    ),
    'AA': (
        first_channels.a,
        second_channels.a,
    ),
}

# Logging
def log_result(
    writer: csv.DictWriter,
    *,
    elapsed_s: float,
    event: str,
    result,
) -> None:
    status = controller.status

    row = {
        'time_s': elapsed_s,
        'event': event,

        # User-controlled disturbance
        'dist_qwp1_deg': disturbance_qwp1.position,
        'dist_hwp_deg': disturbance_hwp.position,
        'dist_qwp2_deg': disturbance_qwp2.position,

        # Active compensation
        'comp_qwp1_deg': compensation_qwp1.position,
        'comp_hwp_deg': compensation_hwp.position,
        'comp_qwp2_deg': compensation_qwp2.position,

        # QKD measurements
        'qber': result.qber,
        'qx': result.qx,

        'worst_error': max(
            result.qber,
            result.qx,
        ),

        # Controller
        'controller_state': status.state.name,
        'search_waveplate': (
            SEARCH_WAVEPLATE_NAMES[
                status.search_waveplate_index
            ]
            if status.state.name == 'SEARCH'
            else ''
        ),
        'search_state': (
            status.search_state.name
            if status.search_state is not None
            else ''
        ),
        'search_measurement_count': (
            status.search_measurement_count
        ),
        'objective': (
            status.score
            if status.score is not None
            else ''
        ),
        'search_jog_velocity_deg_s': (
            controller.search_jog_velocity
        ),
        'search_worsening_count': (
            status.search_worsening_count
        ),
        'search_cycle': (
            status.search_cycle
        ),
        'search_cycle_start_score': (
            status.search_cycle_start_score
            if status.search_cycle_start_score is not None
            else ''
        ),
        'search_cycle_best_score': (
            status.search_cycle_best_score
            if status.search_cycle_best_score is not None
            else ''
        ),
        'search_cycle_improvement': (
            status.search_cycle_improvement
            if status.search_cycle_improvement is not None
            else ''
        ),
        'search_retained_improvement': (
            status.search_retained_improvement
            if status.search_retained_improvement is not None
            else ''
        ),
        'search_stagnant': (
            status.search_stagnant
        ),
        'search_escape_count': (
            status.search_escape_count
        ),
        'jacobian_iteration': status.jacobian_iteration,
        'jacobian_probe_index': status.jacobian_probe_index,
        'jacobian_condition': (
            status.jacobian_condition
            if status.jacobian_condition is not None
            else ''
        ),
        'jacobian_predicted_score': (
            status.jacobian_predicted_score
            if status.jacobian_predicted_score is not None
            else ''
        ),
        'jacobian_step_qwp1_deg': (
            status.jacobian_step_qwp1
            if status.jacobian_step_qwp1 is not None
            else ''
        ),
        'jacobian_step_hwp_deg': (
            status.jacobian_step_hwp
            if status.jacobian_step_hwp is not None
            else ''
        ),
        'jacobian_step_qwp2_deg': (
            status.jacobian_step_qwp2
            if status.jacobian_step_qwp2 is not None
            else ''
        ),
        'jacobian_fallback_count': status.jacobian_fallback_count,
        'best_score': (
            status.best_score
            if status.best_score is not None
            else ''
        ),
        'best_position_deg': (
            status.best_position
            if status.best_position is not None
            else ''
        ),
        'controller_moving': (
            status.is_moving
        ),
    }

    # Singles
    for channel in range(8):
        row[
            f'single_ch{channel}'
        ] = result.singles.get(
            channel,
            0,
        )

    # Coincidences
    for name, pair in coincidence_pairs.items():
        row[
            f'coinc_{name}'
        ] = result.coincidences.get(
            pair,
            0,
        )

    writer.writerow(
        row
    )

# UI
def draw_ui(
    stdscr,
    *,
    result,
    manual_step_deg: float,
    log_file: Path,
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    status = controller.status
    worst = max(
        result.qber,
        result.qx,
    )
    score = (
        f'{status.score:.3f}'
        if status.score is not None
        else '-'
    )
    best_score = (
        f'{status.best_score:.3f}'
        if status.best_score is not None
        else '-'
    )
    best_position = (
        f'{status.best_position:.2f}°'
        if status.best_position is not None
        else '-'
    )
    search_state = (
        status.search_state.name
        if status.search_state is not None
        else '-'
    )
    search_waveplate = (
        SEARCH_WAVEPLATE_NAMES[
            status.search_waveplate_index
        ]
        if status.state.name == 'SEARCH'
        else '-'
    )
    search_jog_velocity = (
        f'{controller.search_jog_velocity:.2f}°/s'
        if status.state.name == 'SEARCH'
        else '-'
    )
    cycle_start_score = (
        f'{status.search_cycle_start_score:.3f}'
        if status.search_cycle_start_score is not None
        else '-'
    )
    cycle_best_score = (
        f'{status.search_cycle_best_score:.3f}'
        if status.search_cycle_best_score is not None
        else '-'
    )
    cycle_improvement = (
        f'{status.search_cycle_improvement:.2%}'
        if status.search_cycle_improvement is not None
        else '-'
    )
    retained_improvement = (
        f'{status.search_retained_improvement:.2%}'
        if status.search_retained_improvement is not None
        else '-'
    )
    motion = (
        'MOVING'
        if status.is_moving
        else 'STATIONARY'
    )

    lines = [
        'Polarisation Compensation Test',


        'User-controlled disturbance',
        '---------------------------',
        (
            f'QWP1: {disturbance_qwp1.position:8.2f}°    '
            f'HWP: {disturbance_hwp.position:8.2f}°    '
            f'QWP2: {disturbance_qwp2.position:8.2f}°'
        ),


        'Active compensation',
        '-------------------',
        (
            f'QWP1: {compensation_qwp1.position:8.2f}°    '
            f'HWP: {compensation_hwp.position:8.2f}°    '
            f'QWP2: {compensation_qwp2.position:8.2f}°'
        ),


        'Measurement',
        '-----------',
        (
            f'QBER: {result.qber:7.2%}    '
            f'Qx: {result.qx:7.2%}    '
            f'Worst: {worst:7.2%}'
        ),


        'Controller',
        '----------',
        f'State:          {status.state.name}',
        f'Search plate:   {search_waveplate}',
        f'Search state:   {search_state}',
        f'Motor:          {motion}',
        f'Jog velocity:   {search_jog_velocity}',
        f'Worse samples:  {status.search_worsening_count}',
        f'Search cycle:   {status.search_cycle}',
        f'Cycle start:    {cycle_start_score}',
        f'Cycle best:     {cycle_best_score}',
        f'Cycle improve:  {cycle_improvement}',
        f'Retained:       {retained_improvement}',
        f'Jacobian iter:  {status.jacobian_iteration}',
        f'Jacobian probe: {status.jacobian_probe_index + 1}/3',
        (
            'Jacobian cond:  '
            + (
                f'{status.jacobian_condition:.2f}'
                if status.jacobian_condition is not None
                else '-'
            )
        ),
        (
            'Predicted RMS:  '
            + (
                f'{status.jacobian_predicted_score:.3f}'
                if status.jacobian_predicted_score is not None
                else '-'
            )
        ),
        f'Jog fallbacks:  {status.jacobian_fallback_count}',
        f'Objective:      {score}',
        f'Best objective: {best_score}',
        f'Best position:  {best_position}',


        'Manual disturbance controls',
        '---------------------------',
        f'Step size: {manual_step_deg:.2f}°',

        'Q / A    QWP1 + / -',
        'W / S    HWP  + / -',
        'E / D    QWP2 + / -',

        '+ / -    Increase / decrease manual step',

        'R        Restart compensation search',
        'X        Quit',

        f'Log: {log_file}',
    ]

    # Terminal size check
    if height < len(lines):
        message = (
            f'Terminal too small '
            f'({width}x{height}). '
            f'Need at least {len(lines)} rows.'
        )
        try:
            stdscr.addstr(
                0,
                0,
                message[
                    :max(
                        0,
                        width - 1,
                    )
                ],
            )
        except curses.error:
            pass
        stdscr.refresh()
        return

    # Draw
    available_width = max(
        0,
        width - 1,
    )
    for row, line in enumerate(
        lines
    ):
        if available_width == 0:
            continue
        try:
            stdscr.addstr(
                row,
                0,
                line[:available_width],
            )
        except curses.error:
            pass
    stdscr.refresh()

def main(
    stdscr,
) -> None:
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()

    stdscr.nodelay(
        True
    )
    stdscr.keypad(
        True
    )

    manual_step_deg = (
        MANUAL_STEP_DEG
    )

    controller.start()
    start_time = (
        time.monotonic()
    )

    # Events are accumulated between measurements.
    pending_events: list[str] = [
        'START'
    ]

    with LOG_FILE.open(
        'w',
        newline='',
    ) as log_file:
        writer = csv.DictWriter(
            log_file,
            fieldnames=LOG_FIELDS,
        )
        writer.writeheader()
        log_file.flush()

        running = True

        while running:
            loop_start = (
                time.monotonic()
            )

            # Keyboard input
            while True:
                key = stdscr.getch()
                if key == -1:
                    break
                try:
                    char = chr(
                        key
                    ).lower()
                except ValueError:
                    char = ''

                # Disturbance QWP1
                if char == 'q':
                    disturbance_qwp1.move_by(
                        angle=manual_step_deg
                    )
                    pending_events.append(
                        (
                            'DIST_QWP1 '
                            f'+{manual_step_deg:.3f}'
                        )
                    )

                elif char == 'a':
                    disturbance_qwp1.move_by(
                        angle=-manual_step_deg
                    )

                    pending_events.append(
                        (
                            'DIST_QWP1 '
                            f'-{manual_step_deg:.3f}'
                        )
                    )

                # Disturbance HWP
                elif char == 'w':
                    disturbance_hwp.move_by(
                        angle=manual_step_deg
                    )
                    pending_events.append(
                        (
                            'DIST_HWP '
                            f'+{manual_step_deg:.3f}'
                        )
                    )
                elif char == 's':
                    disturbance_hwp.move_by(
                        angle=-manual_step_deg
                    )
                    pending_events.append(
                        (
                            'DIST_HWP '
                            f'-{manual_step_deg:.3f}'
                        )
                    )

                # Disturbance QWP2
                elif char == 'e':
                    disturbance_qwp2.move_by(
                        angle=manual_step_deg
                    )
                    pending_events.append(
                        (
                            'DIST_QWP2 '
                            f'+{manual_step_deg:.3f}'
                        )
                    )
                elif char == 'd':
                    disturbance_qwp2.move_by(
                        angle=-manual_step_deg
                    )

                    pending_events.append(
                        (
                            'DIST_QWP2 '
                            f'-{manual_step_deg:.3f}'
                        )
                    )

                # Manual step size
                elif char == '+':
                    manual_step_deg *= 2
                    pending_events.append(
                        (
                            'MANUAL_STEP '
                            f'{manual_step_deg:.3f}'
                        )
                    )
                elif char == '-':
                    manual_step_deg *= 0.5
                    pending_events.append(
                        (
                            'MANUAL_STEP '
                            f'{manual_step_deg:.3f}'
                        )
                    )

                # Restart controller
                elif char == 'r':
                    controller.start()
                    pending_events.append(
                        'CONTROLLER_RESTART'
                    )

                # Quit
                elif char == 'x':
                    pending_events.append(
                        'QUIT'
                    )
                    running = False
            if not running:
                break

            # Measurement
            result = timetagger.measure(
                duration_s=MEASUREMENT_TIME_S,
                coincidence_window_ps=(
                    COINCIDENCE_WINDOW_PS
                ),
            )

            # Active compensation
            controller.update(
                result=result
            )

            # Logging
            event = '; '.join(
                pending_events
            )
            pending_events.clear()
            log_result(
                writer,
                elapsed_s=(
                    time.monotonic()
                    - start_time
                ),
                event=event,
                result=result,
            )
            # Keep the experimental log even if the program later
            # terminates unexpectedly.
            log_file.flush()

            # Display
            draw_ui(
                stdscr,
                result=result,
                manual_step_deg=(
                    manual_step_deg
                ),
                log_file=LOG_FILE,
            )

            # Maintain update interval
            elapsed = (
                time.monotonic()
                - loop_start
            )
            sleep_time = (
                INTERVAL_S
                - elapsed
            )
            if sleep_time > 0:
                time.sleep(
                    sleep_time
                )

if __name__ == '__main__':
    try:
        curses.wrapper(
            main
        )

    finally:
        for waveplate in waveplates:
            waveplate.disconnect()