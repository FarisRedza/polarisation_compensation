"""Noise-free optical Jacobian references for simulation only."""
from copy import deepcopy

import numpy as np


def error_probabilities(state):
    """Wrong-outcome probabilities in Z and X for a Phi+ target."""
    amplitudes = np.asarray(state).reshape(2, 2)
    h = np.array([[1., 1.], [1., -1.]]) / np.sqrt(2.)
    x = h @ amplitudes @ h
    return np.array([abs(amplitudes[0, 1])**2 + abs(amplitudes[1, 0])**2,
                     abs(x[0, 1])**2 + abs(x[1, 0])**2])


def error_derivative(state, derivative):
    a = np.asarray(state).reshape(2, 2)
    d = np.asarray(derivative).reshape(2, 2)
    h = np.array([[1., 1.], [1., -1.]]) / np.sqrt(2.)
    def cross(a, d):
        return 2 * np.real(np.conj(a[0, 1])*d[0, 1] + np.conj(a[1, 0])*d[1, 0])
    return np.array([cross(a, d), cross(h @ a @ h, h @ d @ h)])


class OpticalJacobianReference:
    def __init__(self, system, mode):
        if mode not in ('ideal_fd', 'analytical'):
            raise ValueError(mode)
        self.system = system
        self.mode = mode

    def __call__(self, positions, probe_deg, target_qber, target_qx):
        system = self.system
        plates = system.waveplates
        if len(plates) != 6:
            raise ValueError('Expected three disturbance and three compensation plates')
        matrices = [p.matrix.copy() for p in plates[:3]]
        copies = [deepcopy(p.waveplate) for p in plates[3:]]
        def matrix(i, angle):
            copies[i].angle_deg = angle
            return np.asarray(copies[i].matrix).copy()
        matrices += [matrix(i, a) for i, a in enumerate(positions)]
        def state(ms):
            u = np.eye(2, dtype=complex)
            for m in ms:
                u = m @ u
            a = system.source.state.reshape(2, 2)
            return u @ a if system.compensation_subsystem == 0 else a @ u.T
        base = state(matrices)
        columns = []
        for i, angle in enumerate(positions):
            trial = matrices.copy()
            if self.mode == 'ideal_fd':
                trial[i+3] = matrix(i, angle + probe_deg)
                column = (error_probabilities(state(trial)) - error_probabilities(base)) / probe_deg
            else:
                # A fixed-retardance rotating plate contains only constant,
                # sin(2 theta), and cos(2 theta) matrix terms.
                trial[i+3] = (matrix(i, angle+45) - matrix(i, angle-45)) * np.pi/180
                column = error_derivative(base, state(trial))
            columns.append(tuple(column / [target_qber, target_qx]))
        return columns
