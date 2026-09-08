import time
from typing import cast

import numpy as np

from qtoolkit.polarisation import (
    PHI_PLUS,
    BB84Measurement,
    BB84MeasurementPair,
    HalfWavePlate,
    QuarterWavePlate,
    PolarisationChannelMap,
    apply_local_jones_matrix,
    compose_waveplates,
)
from qtoolkit.timetags import (
    LiveTimetagSimulator,
    coincidence_processes_from_probabilities,
    count_coincidences
)

from qtoolkit.qkd import (
    qber_from_coincidences,
)

# Simulation configuration

SINGLES_RATE_PER_STAGE_HZ = 100_000
PAIR_RATE_HZ = 40_000

INTERVAL_S = 0.25
COMPENSATION_TIME_S = 12.0

COINCIDENCE_DELAY_PS = 300
COINCIDENCE_JITTER_PS = 50
COINCIDENCE_WINDOW_PS = 1_000


# BB84 measurement stages

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

first_bb84 = BB84Measurement(
    channels=first_channels,
)

second_bb84 = BB84Measurement(
    channels=second_channels,
)

measurements = BB84MeasurementPair(
    first=first_bb84,
    second=second_bb84,
)


# Singles rates

# For an ideal maximally entangled state, the reduced state of each
# photon is maximally mixed.
#
# Each detector therefore sees 1/4 of the total singles rate of its
# BB84 measurement stage.

channel_rates = {
    channel: (
        SINGLES_RATE_PER_STAGE_HZ
        / 4
    )
    for channel in range(8)
}


# Define the disturbance

TARGET_QWP1_DEG = 30.0
TARGET_HWP_DEG = -15.0
TARGET_QWP2_DEG = 20.0


# Construct the waveplate transformation which will eventually
# compensate the channel.

target_compensation = compose_waveplates(
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


# Construct a channel disturbance which is exactly cancelled by the
# target compensation.
#
# Since the waveplate transformation is unitary:
#
#     U^-1 = U^\dagger
#
# so:
#
#     target_compensation @ disturbance = I

disturbance = (
    target_compensation
    .conj()
    .T
)


# Initial compensation state

initial_compensation = compose_waveplates(
    [
        QuarterWavePlate(
            angle_deg=0.0,
        ),
        HalfWavePlate(
            angle_deg=0.0,
        ),
        QuarterWavePlate(
            angle_deg=0.0,
        ),
    ]
)


initial_transformation = (
    initial_compensation
    @ disturbance
)


# Apply the channel and compensator to photon 0 of the Bell pair.

initial_state = apply_local_jones_matrix(
    state=PHI_PLUS,
    matrix=initial_transformation,
    subsystem=0,
)


# Calculate the expected joint detector probabilities.

initial_probabilities = (
    measurements
    .joint_probabilities(
        initial_state
    )
)


# Convert those probabilities into genuine coincidence processes.

initial_coincidence_pairs = (
    coincidence_processes_from_probabilities(
        probabilities=initial_probabilities,
        pair_rate_hz=PAIR_RATE_HZ,
        delay_ps=COINCIDENCE_DELAY_PS,
        jitter_ps=COINCIDENCE_JITTER_PS,
    )
)


# Start simulator

simulator = LiveTimetagSimulator(
    channel_rates=channel_rates,
    coincidence_pairs=initial_coincidence_pairs,
    rng=np.random.default_rng(42),
)


# Coincidences to measure

pairs_to_measure = [
    # Z basis
    (
        first_channels.h,
        second_channels.h,
    ),
    (
        first_channels.h,
        second_channels.v,
    ),
    (
        first_channels.v,
        second_channels.h,
    ),
    (
        first_channels.v,
        second_channels.v,
    ),

    # X basis
    (
        first_channels.d,
        second_channels.d,
    ),
    (
        first_channels.d,
        second_channels.a,
    ),
    (
        first_channels.a,
        second_channels.d,
    ),
    (
        first_channels.a,
        second_channels.a,
    ),
]


number_of_steps = round(
    COMPENSATION_TIME_S
    / INTERVAL_S
)

print(
    '| QWP1     | HWP     | QWP2    | QBER     | Qx       | H       | V       | D       | A       |\n'
    '|----------|---------|---------|----------|----------|---------|---------|---------|---------|'
)



# Slowly move the compensation waveplates to the correct settings

for step in range(
    number_of_steps + 1
):
    loop_start = time.monotonic()

    fraction = (
        step
        / number_of_steps
    )

    # Waveplate positions

    qwp1_angle = (
        fraction
        * TARGET_QWP1_DEG
    )

    hwp_angle = (
        fraction
        * TARGET_HWP_DEG
    )

    qwp2_angle = (
        fraction
        * TARGET_QWP2_DEG
    )


    compensation = compose_waveplates(
        [
            QuarterWavePlate(
                angle_deg=qwp1_angle,
            ),
            HalfWavePlate(
                angle_deg=hwp_angle,
            ),
            QuarterWavePlate(
                angle_deg=qwp2_angle,
            ),
        ]
    )


    # Channel disturbance followed by the compensator.
    total_transformation = (
        compensation
        @ disturbance
    )


    # Transform the Bell state

    state = apply_local_jones_matrix(
        state=PHI_PLUS,
        matrix=total_transformation,
        subsystem=0,
    )


    # Calculate expected detector-pair probabilities

    probabilities = (
        measurements
        .joint_probabilities(
            state
        )
    )


    # Update the live simulator

    simulator.set_coincidence_processes(
        coincidence_processes_from_probabilities(
            probabilities=probabilities,
            pair_rate_hz=PAIR_RATE_HZ,
            delay_ps=COINCIDENCE_DELAY_PS,
            jitter_ps=COINCIDENCE_JITTER_PS,
        )
    )


    data = simulator.read(
        INTERVAL_S
    )

    first_counts = {
        'H': data.count(
            first_channels.h
        ),
        'V': data.count(
            first_channels.v
        ),
        'D': data.count(
            first_channels.d
        ),
        'A': data.count(
            first_channels.a
        ),
    }


    second_counts = {
        'H': data.count(
            second_channels.h
        ),
        'V': data.count(
            second_channels.v
        ),
        'D': data.count(
            second_channels.d
        ),
        'A': data.count(
            second_channels.a
        ),
    }

    coincidences = count_coincidences(
        data=data,
        pairs=cast(
            list[tuple[int, int]],
            pairs_to_measure,
        ),
        coincidence_window=(
            COINCIDENCE_WINDOW_PS
        ),
    )

    hh = coincidences[
        cast(
            tuple[int, int],
            (
                first_channels.h,
                second_channels.h,
            ),
        )
    ]

    hv = coincidences[
        cast(
            tuple[int, int],
            (
                first_channels.h,
                second_channels.v,
            ),
        )
    ]

    vh = coincidences[
        cast(
            tuple[int, int],
            (
                first_channels.v,
                second_channels.h,
            ),
        )
    ]

    vv = coincidences[
        cast(
            tuple[int, int],
            (
                first_channels.v,
                second_channels.v,
            ),
        )
    ]


    qber = qber_from_coincidences(
        c_00=hh,
        c_01=hv,
        c_10=vh,
        c_11=vv,
    )

    dd = coincidences[
        cast(
            tuple[int, int],
            (
                first_channels.d,
                second_channels.d,
            ),
        )
    ]

    da = coincidences[
        cast(
            tuple[int, int],
            (
                first_channels.d,
                second_channels.a,
            ),
        )
    ]

    ad = coincidences[
        cast(
            tuple[int, int],
            (
                first_channels.a,
                second_channels.d,
            ),
        )
    ]

    aa = coincidences[
        cast(
            tuple[int, int],
            (
                first_channels.a,
                second_channels.a,
            ),
        )
    ]


    qx = qber_from_coincidences(
        c_00=dd,
        c_01=da,
        c_10=ad,
        c_11=aa,
    )

    print(
        f'| {qwp1_angle:6.1f}°  '
        f'| {hwp_angle:6.1f}° '
        f'| {qwp2_angle:6.1f}° '
        f'| {qber:7.2%}  '
        f'| {qx:7.2%}  '
        f'| {first_counts["V"]:6d}  '
        f'| {first_counts["H"]:6d}  '
        f'| {first_counts["D"]:6d}  '
        f'| {first_counts["A"]:6d}  |',
        end='\r'
    )

    # Real-time pacing

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
print()