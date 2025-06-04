import sys
import os

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import motor.base_motor as base_motor

def pol_comp(
        motor_list: list[base_motor.Motor],
        motor_qwp_serial_no: str,
        motor_hwp_serial_no: str,
        target_azimuth: float,
        target_ellipticity: float,
        azimuth_velocities: list[tuple[float, float]],
        ellipticity_velocities: list[tuple[float, float]],
        current_azimuth: float,
        current_ellipticity: float
) -> bool:
    motor_qwp_index = next(
        (i for i, m in enumerate(motor_list) if m.device_info.serial_number == motor_qwp_serial_no),
        -1
    )
    motor_hwp_index = next(
        (i for i, m in enumerate(motor_list) if m.device_info.serial_number == motor_hwp_serial_no),
        -1
    )

    def adjust_motor(
        motor_list: list[base_motor.Motor],
        motor_index: int,
        current_value: float,
        target_value: float,
        thresholds_velocities: list[tuple[float, float]]
    ) -> None:
        if motor_index == -1:
            return

        motor = motor_list[motor_index]
        delta = target_value - current_value

        if abs(delta) < 1e-3:  # small error threshold to prevent jitter
            motor.stop()
            return

        taget_direction = '-' if delta > 0 else '+'
        abs_delta = abs(delta)

        for threshold, velocity in sorted(thresholds_velocities, reverse=True):
            if abs_delta > threshold:
                if (motor.direction.value != taget_direction or
                        motor.max_velocity != velocity):
                    motor.stop()
                    motor.direction = base_motor.MotorDirection(taget_direction)
                    motor.jog(
                        direction=motor.direction,
                        acceleration=20.0,
                        max_velocity=velocity
                    )
                break
        else:
            motor.stop()


    adjust_motor(
        motor_list=motor_list,
        motor_index=motor_qwp_index,
        current_value=current_azimuth,
        target_value=target_azimuth,
        thresholds_velocities=azimuth_velocities
    )

    adjust_motor(
        motor_list=motor_list,
        motor_index=motor_hwp_index,
        current_value=current_ellipticity,
        target_value=target_ellipticity,
        thresholds_velocities=ellipticity_velocities
    )

    return True