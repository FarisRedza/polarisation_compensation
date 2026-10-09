import typing

import motor


class MotorExecutor:
    """Execute motor operations without managing compensation state."""

    def __init__(
        self,
        motors: typing.Sequence[motor.Motor],
    ) -> None:
        self.motors = tuple(motors)

    @property
    def is_moving(self) -> bool:
        return any(
            waveplate.is_moving
            for waveplate in self.motors
        )

    def stop_moving(self) -> None:
        for waveplate in self.motors:
            if waveplate.is_moving:
                waveplate.stop()

    def jog(
        self,
        index: int,
        *,
        direction: motor.MotorDirection,
        max_velocity: float,
    ) -> None:
        self.motors[index].jog(
            direction=direction,
            max_velocity=max_velocity,
        )

    def stop_and_move_to(
        self,
        index: int,
        position: float,
    ) -> None:
        waveplate = self.motors[index]
        waveplate.stop()
        waveplate.move_to(position)

    def move_to(
        self,
        index: int,
        position: float,
    ) -> None:
        self.motors[index].move_to(position)

    def apply_step(
        self,
        step: typing.Sequence[float],
    ) -> None:
        for waveplate, delta in zip(
            self.motors,
            step,
        ):
            waveplate.move_to(
                waveplate.position + delta
            )

    def position(self, index: int) -> float:
        """Return the current position of one motor."""
        return self.motors[index].position

    def positions(self) -> tuple[float, ...]:
        """Return the current positions of all motors."""
        return tuple(
            waveplate.position
            for waveplate in self.motors
        )