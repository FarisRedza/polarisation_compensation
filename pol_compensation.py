import polarimeter.polarimeter as polarimeter
import motor.motor as thorlabs_motor

def pol_comp(
        motor_list: list[thorlabs_motor.Motor],
        motor_qwp_serial_no: str,
        motor_hwp_serial_no: str,
        target_azimuth: float,
        target_ellipticity: float,
        azimuth_thresholds_velocities: list[tuple[float, int]],
        ellipticity_thresholds_velocities: list[tuple[float, int]],
        current_azimuth: float,
        current_ellipticity: float
) -> bool:
    
    motor_qwp_index = next((i for i, m in enumerate(motor_list) if m.serial_no == motor_qwp_serial_no), -1)
    motor_hwp_index = next((i for i, m in enumerate(motor_list) if m.serial_no == motor_hwp_serial_no), -1)

    def adjust_motor(
            motor_list: list[thorlabs_motor.Motor],
            motor_index: int,
            current_value: float,
            target_value: float,
            thresholds_velocities: list[tuple[float, int]]
    ) -> None:
        if motor_index == -1:
            return

        motor = motor_list[motor_index]
        motor.position = motor._motor.get_position()
        delta = current_value - target_value
        direction = '+' if delta > 0 else '-'

        if motor.motor_direction.value != direction:
            motor._motor.stop()
            motor.motor_direction = thorlabs_motor.Motor.MotorDirection(direction)

        abs_delta = abs(delta)
        for threshold, velocity in sorted(thresholds_velocities, reverse=True):
            if abs_delta > threshold:
                if motor.max_velocity != velocity:
                    motor._motor.setup_jog(
                        mode='continuous',
                        max_velocity=velocity
                    )
                    motor.max_velocity = velocity
                motor._motor.jog(
                    direction=direction,
                    kind='builtin'
                )
                break
        else:
            motor._motor.stop()

    adjust_motor(
        motor_list=motor_list,
        motor_index=motor_qwp_index,
        current_value=current_azimuth,
        target_value=target_azimuth,
        thresholds_velocities=azimuth_thresholds_velocities
    )

    adjust_motor(
        motor_list=motor_list,
        motor_index=motor_hwp_index,
        current_value=current_ellipticity,
        target_value=target_ellipticity,
        thresholds_velocities=ellipticity_thresholds_velocities
    )

    return True