

import dataclasses


@dataclasses.dataclass(frozen=True)
class JacobianLineSearchTrial:
    alpha: float
    score: float


@dataclasses.dataclass(frozen=True)
class JacobianLineSearchResult:
    iteration: int

    baseline_score: float
    full_score: float
    trial_score: float

    trial_alpha: float
    accepted_alpha: float
    extra_travel_deg: float

    trials: tuple[JacobianLineSearchTrial, ...] = ()

    @property
    def trial_improvement(self) -> float:
        return self.full_score - self.trial_score

    @property
    def accepted_score(self) -> float:
        if self.accepted_alpha == 0.0:
            return self.baseline_score

        if self.accepted_alpha == 1.0:
            return self.full_score

        if self.trials:
            for trial in self.trials:
                if trial.alpha == self.accepted_alpha:
                    return trial.score

        if self.accepted_alpha == self.trial_alpha:
            return self.trial_score

        raise ValueError(
            f"No score recorded for accepted alpha "
            f"{self.accepted_alpha}"
        )