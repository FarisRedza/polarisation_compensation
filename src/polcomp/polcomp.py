import dataclasses
import typing

import numpy as np
import motor
import qtoolkit


class DummyDetector:
    def __init__(self) -> None:
        self._timetag_sim = qtoolkit.LiveTimetagSimulator(
            channel_rates={
                0: 1000,
                1: 1000,
                2: 1000,
                3: 1000,
            }
        )

    def measure(self) -> float:
        return np.random.uniform(low=0, high=1)


@dataclasses.dataclass
class MotorRole:
    motor: motor.Motor
    role: str


class PolComp:
    def __init__(
            self,
            motor_roles: list[MotorRole],
            detector: DummyDetector,
            algorithm: typing.Literal[
                'spgd',
                'jacobian',
                'fast-locating'
            ]
    ) -> None:
        self.motor_roles = motor_roles
        self.detector = detector
        self.algorithm = algorithm

    def start(self) -> None:
        match self.algorithm:
            case 'spgd':
                self._start_spgd()
            case 'jacobian':
                self._start_jacobian()
            case 'fast-locating':
                self._start_fast_locating()
            case _:
                raise ValueError(f'Unknown algorithm: {self.algorithm}')

    def _start_spgd(self) -> None:
        raise NotImplementedError('SPGD algorithm is not implemented yet.')

    def _start_jacobian(self) -> None:
        raise NotImplementedError('Jacobian algorithm is not implemented yet.')

    def _start_fast_locating(self) -> None:
        raise NotImplementedError('Fast locating algorithm is not implemented yet.')

    def _set_motors_to_0(self) -> None:
        for motor_role in self.motor_roles:
            motor_role.motor.move_to(position=0.0)

    def _scramble_motors(
            self,
            rng: typing.Optional[np.random.Generator] = None
    ) -> None:
        if rng is None:
            rng = np.random.default_rng()

        angle = rng.uniform(low=1, high=360)
        direction = rng.uniform(low=0, high=1)
        sign = 1 if direction > 0.5 else -1
        angle *= sign
        
        for motor_role in self.motor_roles:
            motor_role.motor.move_by(angle=angle)


if __name__ == '__main__':
    detector = DummyDetector()
    for data in detector._timetag_sim.stream(0.1):
        print(data)