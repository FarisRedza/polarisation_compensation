import motor.motor as thorlabs_motor

def pol_comp(
        motor_list: list[thorlabs_motor.Motor],
        motor_qwp_serial_no: str | int,
        motor_hwp_serial_no: str | int,
        target_azimuth: float,
        target_ellipticity: float,
        azimuth_velocities: list[tuple[float, float]],
        ellipticity_velocities: list[tuple[float, float]],
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
            thresholds_velocities: list[tuple[float, float]]
    ) -> None:
        if motor_index == -1:
            return

        motor = motor_list[motor_index]
        motor.position
        delta = current_value - target_value
        direction = '+' if delta > 0 else '-'

        if motor.direction.value != direction:
            motor.stop()
            motor.direction = thorlabs_motor.MotorDirection(direction)

        abs_delta = abs(delta)
        for threshold, velocity in sorted(thresholds_velocities, reverse=True):
            if abs_delta > threshold:
                # if motor.max_velocity != velocity:
                #     motor._motor.setup_jog(
                #         mode='continuous',
                #         max_velocity=velocity
                #     )
                #     motor.max_velocity = velocity
                # motor._motor.jog(
                #     direction=direction,
                #     kind='builtin'
                # )
                # break
                motor.jog(
                    direction=thorlabs_motor.MotorDirection(direction),
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

# def pol_comp(
#         motor_list: list[thorlabs_motor.Motor],
#         motor_qwp_serial_no: str,
#         motor_hwp_serial_no: str,
#         target_azimuth: float,
#         target_ellipticity: float,
#         azimuth_velocities: list[tuple[float, int]],
#         ellipticity_velocities: list[tuple[float, int]],
#         current_azimuth: float,
#         current_ellipticity: float
# ):
#     motor_qwp_index = next((i for i, m in enumerate(motor_list) if m.serial_no == motor_qwp_serial_no), -1)
#     motor_hwp_index = next((i for i, m in enumerate(motor_list) if m.serial_no == motor_hwp_serial_no), -1)

#     def adjust_motor(
#             motor_list: list[thorlabs_motor.Motor],
#             motor_index: int,
#             current_angle: float,
#             target_angle: float,
#             angle_velocities: list[tuple[float, float]]
#     ) -> None:
#         if motor_index == -1:
#             return

#         motor = motor_list[motor_index]
#         motor.position = motor._motor.get_position()
#         delta_angle = current_angle - target_angle

#         if delta_angle > 0:
#             direction = thorlabs_motor.MotorDirection.FORWARD
#         elif delta_angle < 0:
#             direction = thorlabs_motor.MotorDirection.BACKWARD
#         else:
#             direction = thorlabs_motor.MotorDirection.IDLE

#         if motor.direction != direction:
#             motor.stop()

#         for angle, velocity in sorted(angle_velocities, reverse=True):
#             if abs(delta_angle) > angle:
#                 # print(f'Moving motor {motor.device_info.serial_number} {direction.name}')
#                 motor.jog(
#                     direction=direction,
#                     max_velocity=velocity
#                 )
#                 break
#         else:
#             motor.stop()

#     adjust_motor(
#         motor_list=motor_list,
#         motor_index=motor_qwp_index,
#         current_angle=current_azimuth,
#         target_angle=target_azimuth,
#         angle_velocities=azimuth_velocities
#     )

#     adjust_motor(
#         motor_list=motor_list,
#         motor_index=motor_hwp_index,
#         current_angle=current_ellipticity,
#         target_angle=target_ellipticity,
#         angle_velocities=ellipticity_velocities
#     )

# if __name__ == '__main__':
#     event = threading.Event()

#     target_angle = 0

#     polarimeter = scpi_polarimeter.Polarimeter(
#         id='1313:8031',
#         serial_number='M00910360'
#     )
#     motors = [
#         thorlabs_motor.Motor(serial_number='55353314'),
#         thorlabs_motor.Motor(serial_number='55356974')
#     ]

#     azimuth_velocity = [
#         (5.0, 25.0),
#         (2.5, 15.0),
#         (1.0, 5.0),
#         (0.075, 0.5)
#     ]
#     ellipticity_velocity = [
#         (5.0, 25.0),
#         (2.5, 15.0),
#         (1.0, 5.0),
#         (0.075, 0.5)
#     ]
#     data = [scpi_polarimeter.Data()]

#     def pol_data(
#             polarimeter: scpi_polarimeter.Polarimeter,
#             data: list[scpi_polarimeter.Data]
#     ) -> None:
#         while True:
#             data[0] = polarimeter.measure().to_data()
#             if event.is_set():
#                 break
#             time.sleep(0.1)
#         polarimeter.disconnect()

#     pol_thread = threading.Thread(
#         target=pol_data,
#         args=(polarimeter,data)
#     )

#     def pol_motor():
#         while True:
#             pol_comp(
#                 motor_list=motors,
#                 motor_qwp_serial_no='55353314',
#                 motor_hwp_serial_no='55356974',
#                 target_azimuth=target_angle,
#                 target_ellipticity=target_angle,
#                 azimuth_velocities=azimuth_velocity,
#                 ellipticity_velocities=ellipticity_velocity,
#                 current_azimuth=data[0].azimuth,
#                 current_ellipticity=data[0].ellipticity
#             )
#             if event.is_set():
#                 for motor in motors:
#                     motor.stop()
#                 break
#             time.sleep(0.1)

#     motor_thread = threading.Thread(
#         target=pol_motor
#     )

#     pol_thread.start()
#     motor_thread.start()
#     try:
#         while True:
#             print(data[0].azimuth)
#             print(data[0].ellipticity)
#             time.sleep(1)
#     except KeyboardInterrupt:
#         event.set()
#         pol_thread.join()
#         motor_thread.join()