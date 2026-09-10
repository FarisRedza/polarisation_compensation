import dataclasses
import typing
import time

import numpy as np
import motor
import qtoolkit


@dataclasses.dataclass(frozen=True)
class BB84DetectionResult:
    data: qtoolkit.timetags.TimetagData
    qber: float
    qx: float
    singles: dict[int, int]
    coincidences: dict[tuple[int, int], int]
    

@dataclasses.dataclass
class CompensationMeasurement:
    qber: float
    qx: float

    @property
    def target_met(self) -> bool:
        raise NotImplementedError


class PolCompController:
    def __init__(
        self,
        *,
        target_qber: float = 0.05,
        target_qx: float = 0.05,
    ) -> None:

        self.target_qber = target_qber
        self.target_qx = target_qx

        self.active = False

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    