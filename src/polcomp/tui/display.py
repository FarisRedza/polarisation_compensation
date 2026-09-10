import curses

from qtoolkit.polarisation import PolarisationChannelMap

def draw_ui(
    stdscr,
    *,
    qwp1_position: float,
    hwp_position: float,
    qwp2_position: float,
    first_channels: PolarisationChannelMap,
    second_channels: PolarisationChannelMap,
    measurement_time: float,
    result,
) -> None:
    stdscr.erase()
    curses.start_color()
    curses.use_default_colors()

    height, width = stdscr.getmaxyx()


    worst = max(
        result.qber,
        result.qx,
    )

    mean = (
        result.qber
        + result.qx
    ) / 2

    channel_names = {
        0: 'H1',
        1: 'V1',
        2: 'D1',
        3: 'A1',
        4: 'H2',
        5: 'V2',
        6: 'D2',
        7: 'A2',
    }

    coincidence_pairs = [
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


    coincidence_names = {
        coincidence_pairs[0]: 'HH',
        coincidence_pairs[1]: 'HV',
        coincidence_pairs[2]: 'VH',
        coincidence_pairs[3]: 'VV',
        coincidence_pairs[4]: 'DD',
        coincidence_pairs[5]: 'DA',
        coincidence_pairs[6]: 'AD',
        coincidence_pairs[7]: 'AA',
    }

    lines = [
        (
            '| QWP1      | HWP       | QWP2      '
            '| QBER    | Qx      | Worst   | Mean    |'
        ),
        (
            '|-----------|-----------|-----------'
            '|---------|---------|---------|---------|'
        ),
        (
            f'| {qwp1_position:8.2f}° '
            f'| {hwp_position:8.2f}° '
            f'| {qwp2_position:8.2f}° '
            f'| {result.qber:7.2%} '
            f'| {result.qx:7.2%} '
            f'| {worst:7.2%} '
            f'| {mean:7.2%} |'
        ),
        '',
        (
            '| Ch | Pol | Counts | Rate (Hz) '
            '| Pair | Counts | Rate (Hz) |'
        ),
        (
            '|----|-----|--------|-----------'
            '|------|--------|-----------|'
        ),
    ]

    for channel, pair in zip(
        range(8),
        coincidence_pairs,
    ):
        single_count = result.singles.get(
            channel,
            0,
        )

        coincidence_count = (
            result.coincidences.get(
                pair,
                0,
            )
        )


        single_rate = (
            single_count
            / measurement_time
        )

        coincidence_rate = (
            coincidence_count
            / measurement_time
        )

        lines.append(
            (
                f'| {channel:^2} '
                f'| {channel_names[channel]:^3} '
                f'| {single_count:6d} '
                f'| {single_rate:9.0f} '
                f'| {coincidence_names[pair]:^4} '
                f'| {coincidence_count:6d} '
                f'| {coincidence_rate:9.0f} |'
            )
        )
    lines.append('\nX        Quit')

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

    available_width = max(
        0,
        width - 1,
    )

    for row, line in enumerate(lines):
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
