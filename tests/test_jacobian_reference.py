from types import SimpleNamespace

import numpy as np
from qtoolkit.polarisation import QuarterWaveplate, HalfWaveplate, PHI_PLUS
from polcomp.simulation.jacobian_reference import OpticalJacobianReference, error_probabilities


def test_reference_derivatives():
    plates = [QuarterWaveplate(), HalfWaveplate(), QuarterWaveplate(),
              QuarterWaveplate(), HalfWaveplate(), QuarterWaveplate()]
    for plate, angle in zip(plates, (12., 37., 81., 0., 0., 0.)):
        plate.angle_deg = angle
    system = SimpleNamespace(
        waveplates=[SimpleNamespace(matrix=p.matrix, waveplate=p) for p in plates],
        source=SimpleNamespace(state=np.asarray(PHI_PLUS)),
        compensation_subsystem=0,
    )
    for subsystem in (0, 1):
        system.compensation_subsystem = subsystem
        for positions in ((12., 43., 79.), (0., 0., 0.), (91., 17., 122.)):
            exact = OpticalJacobianReference(system, 'analytical')(positions, 2., .05, .05)
            fd = OpticalJacobianReference(system, 'ideal_fd')(positions, 1e-5, .05, .05)
            np.testing.assert_allclose(exact, fd, atol=1e-6, rtol=1e-5)
    assert all(p.angle_deg == 0 for p in plates[3:])


def test_phi_plus_errors():
    np.testing.assert_allclose(error_probabilities(PHI_PLUS), [0., 0.], atol=1e-15)
