import time
import curses

import numpy as np

from qtoolkit.polarisation import (
    QuarterWavePlate,
    HalfWavePlate,
    compose_waveplates,
    apply_local_jones_matrix,
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
)

from polcomp import tui


# ---------------------------------------------------------------------
# Simulation settings
# ---------------------------------------------------------------------
INTERVAL_S = 0.1

PAIR_RATE_HZ = 40_000

MEASUREMENT_TIME_S = 0.1
COINCIDENCE_WINDOW_PS = 1_000

# ---------------------------------------------------------------------
# Fixed polarisation disturbance
# ---------------------------------------------------------------------
TARGET_QWP1_DEG = 30
TARGET_HWP_DEG = -15
TARGET_QWP2_DEG = 20
disturbance = (
    compose_waveplates(
        [
            QuarterWavePlate(
                angle_deg=TARGET_QWP1_DEG,
            ),
            HalfWavePlate(
                angle_deg=TARGET_HWP_DEG,
            ),
            QuarterWavePlate(
                angle_deg=TARGET_QWP2_DEG,
            ),
        ]
    )
).conj().T

disturbed_state = apply_local_jones_matrix(
    state=PHI_PLUS,
    matrix=disturbance,
    subsystem=0,
)

# ---------------------------------------------------------------------
# Entangled photon source
# ---------------------------------------------------------------------
source = SimulatedEPS(
    state=disturbed_state,
    pair_rate_hz=PAIR_RATE_HZ,
)

# ---------------------------------------------------------------------
# Motorised compensation waveplates
# ---------------------------------------------------------------------
qwp1 = SimulatedMotor(
    waveplate=QuarterWavePlate(),
)
hwp = SimulatedMotor(
    waveplate=HalfWavePlate(),
)
qwp2 = SimulatedMotor(
    waveplate=QuarterWavePlate(),
)
waveplates = [
    qwp1,
    hwp,
    qwp2,
]

# ---------------------------------------------------------------------
# BB84 measurements
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# Simulated optical/detection system
# ---------------------------------------------------------------------
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

timetagger = SimulatedTimetagger(
    source=system,
    measurements=measurements,
)

def main(
    stdscr,
) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    step_size_deg = 1.0

    running = True
    while running:
        loop_start = time.monotonic()

        key = stdscr.getch()

        if key != -1:
            try:
                char = chr(
                    key
                ).lower()

            except ValueError:
                char = ''

            match char:
                case 'q':
                    qwp1.move_by(
                        angle=step_size_deg
                    )
                case 'a':
                    qwp1.move_by(
                        angle=-step_size_deg
                    )

                case 'w':
                    hwp.move_by(
                        angle=step_size_deg
                    )
                case 's':
                    hwp.move_by(
                        angle=-step_size_deg
                    )

                case 'e':
                    qwp2.move_by(
                        angle=step_size_deg
                    )
                case 'd':
                    qwp2.move_by(
                        angle=-step_size_deg
                    )

                case '+':
                    step_size_deg *= 2
                case '-':
                    step_size_deg *= 0.5

                case 'x':
                    running = False

        result = timetagger.measure(
            duration_s=MEASUREMENT_TIME_S,
            coincidence_window_ps=COINCIDENCE_WINDOW_PS,
        )

        tui.draw_ui(
            stdscr=stdscr,
            qwp1_position=qwp1.position,
            hwp_position=hwp.position,
            qwp2_position=qwp2.position,
            first_channels=first_channels,
            second_channels=second_channels,
            measurement_time=MEASUREMENT_TIME_S,
            result=result,
        )

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
        curses.wrapper(main)

    finally:
        for waveplate in waveplates:
            waveplate.disconnect()