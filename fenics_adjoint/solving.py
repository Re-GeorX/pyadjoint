import backend
import ufl
from .tape import Tape, Block, Function, get_working_tape, DirichletBC

def solve(*args, **kwargs):
    annotate_tape = kwargs.pop("annotate_tape", True)
    output = backend.solve(*args, **kwargs)

    if annotate_tape:
        tape = get_working_tape()
        block = SolveBlock(*args, **kwargs)
        tape.add_block(block)

    return output


class SolveBlock(Block):
    def __init__(self, *args, **kwargs):
        super(SolveBlock, self).__init__()
        if isinstance(args[0], ufl.equation.Equation):
            # Variational problem.
            self.eq = args[0]
            self.func = args[1]

            # Store boundary conditions, if any are given.
            if len(args) > 2:
                if isinstance(args[2], list):
                    self.bcs = args[2]
                else:
                    self.bcs = [args[2]]
            else:
                self.bcs = []

            if isinstance(self.eq.lhs, ufl.Form) and isinstance(self.eq.rhs, ufl.Form):
                self.linear = True
                # Add dependence on coefficients on the right hand side.
                for c in self.eq.rhs.coefficients():
                    self.add_dependency(c)

                # Add solution function to dependencies.
                #self.add_dependency(self.func)
            else:
                self.linear = False

            for bc in self.bcs:
                self.add_dependency(bc)

            for c in self.eq.lhs.coefficients():
                    self.add_dependency(c)
        else:
            # Linear algebra problem.
            raise NotImplementedError

    def evaluate_adj(self):
        adj_var = Function(self.func.function_space())

        # Obtain (dFdu)^T.
        if self.linear:
            dFdu = self.eq.lhs
        else:
            dFdu = backend.derivative(self.eq.lhs, self.func, backend.TrialFunction(self.func.function_space()))

        dFdu = backend.assemble(dFdu)

        # Get dJdu from previous calculations.
        dJdu = self.func.get_adj_output()

        # Homogenize and apply boundary conditions on adj_dFdu and dJdu.
        bcs = []
        for bc in self.bcs:
            if isinstance(bc, backend.DirichletBC):
                bc = backend.DirichletBC(bc)
                bc.homogenize()
            bcs.append(bc)
            bc.apply(dFdu)

        dFdu_mat = backend.as_backend_type(dFdu).mat()
        dFdu_mat.transpose(dFdu_mat)

        # Solve the adjoint equations.
        backend.solve(dFdu, adj_var.vector(), dJdu)

        # TODO: Clean up and restructure the code, if possible.
        for c in self.get_dependencies():
            if c != self.func:
                if isinstance(c, backend.Function):
                    if self.linear:
                        dFdm = backend.derivative(self.eq.rhs, c, backend.TrialFunction(c.function_space()))
                        #dFdm = backend.adjoint(dFdm_rhs)

                        if c in self.eq.lhs.coefficients():
                            dFdm_lhs = backend.action(self.eq.lhs, self.func)
                            dFdm_lhs = -backend.derivative(dFdm_lhs, c, backend.TrialFunction(c.function_space()))
                            #dFdm_lhs = backend.adjoint(dFdm_lhs)
                            dFdm += dFdm_lhs

                    else:
                        dFdm = -backend.derivative(self.eq.lhs, c, backend.TrialFunction(c.function_space()))
                        #dFdm = backend.adjoint(dFdm)

                    dFdm = backend.assemble(dFdm)

                    dFdm_mat = backend.as_backend_type(dFdm).mat()

                    import numpy as np
                    #dFdm_mat.setValue(1, 1, 1)
                    #dFdm.zero(np.array([0, self.func.function_space().dim()-1], dtype=np.intc))

                    #print dFdm.array()
                    #import sys; sys.exit()
                    bc_rows = []
                    for bc in bcs:
                        for key in bc.get_boundary_values():
                            bc_rows.append(key)

                    dFdm.zero(np.array(bc_rows, dtype=np.intc))

                    dFdm_mat.transpose(dFdm_mat)

                    c.add_adj_output(dFdm*adj_var.vector())
                elif isinstance(c, backend.Constant):
                    if self.linear:
                        dFdm = backend.derivative(self.eq.rhs, c, backend.Constant(1))

                        if c in self.eq.lhs.coefficients():
                            dFdm_lhs = backend.action(self.eq.lhs, self.func)
                            dFdm_lhs = -backend.derivative(dFdm_lhs, c, backend.Constant(1))
                            dFdm += dFdm_lhs

                    else:
                        dFdm = -backend.derivative(self.eq.lhs, c, backend.Constant(1))

                    dFdm = backend.assemble(dFdm)
                    [bc.apply(dFdm) for bc in bcs]

                    c.add_adj_output(dFdm.inner(adj_var.vector()))
                elif isinstance(c, backend.DirichletBC):
                    tmp_bc = DirichletBC(c)
                    if self.linear:
                        if True:
                            adj_output = []
                            adj_var_array = adj_var.vector().array()
                            for key in c.get_boundary_values():
                                adj_output.append(adj_var_array[key])

                            import numpy as np
                            adj_output = np.array(adj_output)

                            c.add_adj_output(adj_output)
                        else:
                            dFdm = backend.derivative(self.eq.rhs, backend.Constant(1), backend.Constant(1)) # Hacky way of getting 0 vector
                            dFdm = backend.assemble(dFdm)

                            tmp_bc.set_value(backend.Constant(1))
                            tmp_bc.apply(dFdm)

                            c.add_adj_output(dFdm.inner(adj_var.vector()))
                    else:
                        pass



