import pytest
pytest.importorskip("firedrake")

from firedrake import *
from firedrake_adjoint import *
import numpy as np


def test_external_modification():
    mesh = UnitSquareMesh(2, 2)
    fs = FunctionSpace(mesh, 'CG', 1)

    u = Function(fs)
    v1 = Function(fs)
    v2 = Function(fs)

    u.assign(1.)
    v1.project(u)
    with stop_annotating(modifies=u):
        u.dat.data[:] = 2.
    v2.project(u)

    J = assemble(v1*dx + v2*dx)
    Jhat = ReducedFunctional(J, Control(u))

    assert np.allclose(J, Jhat(2))
