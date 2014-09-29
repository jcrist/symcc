from sympy import symbols, sin, cos, Dict, sqrt, tan, simplify
from sympy.utilities.pytest import raises
from sympy.core.assumptions import _assume_defined

from symcc.types.ast import Assign, InArgument, OutArgument, datatype
from symcc.types.routines import (RoutineReturn, RoutineInplace, Routine,
        routine, routine_result, ScalarRoutineCallResult)


a, b, c = symbols('a, b, c')
out = symbols('out')
dbl = datatype('double')
a_arg = InArgument(a, dbl)
b_arg = InArgument(b, dbl)
c_arg = InArgument(c, dbl)
out_arg = OutArgument(out, dbl)
expr = sin(a) + cos(b**2)*c
inp_expr = Assign(out, expr)


def test_arg_invariance():
    r = RoutineReturn(dbl, expr)
    assert r.func(*r.args) == r
    rip = RoutineInplace(out_arg, Assign(out, expr))
    assert rip.func(*rip.args) == rip
    rout = Routine('test', [a_arg, b_arg, c_arg, out_arg], [r, rip])
    assert rout.func(*rout.args) == rout
    rcall = rout(a, b, c, out)
    assert rcall.func(*rcall.args) == rcall
    rcallret = rcall.returns
    assert rcallret.func(*rcallret.args) == rcallret
    rcallinp = rcall.inplace[out]
    assert rcallinp.func(*rcallinp.args) == rcallinp


def test_routine_result():
    r = routine_result(expr)
    assert r == RoutineReturn(dbl, expr)
    r = routine_result(Assign(out, expr))
    assert r == RoutineInplace(out_arg, expr)


def test_routine():
    test = routine('test', (a, b, c), expr)
    assert test == Routine('test', (a_arg, b_arg, c_arg), (RoutineReturn(dbl, expr),))
    test = routine('test', (a, b, c, out), inp_expr)
    assert test == Routine('test', (a_arg, b_arg, c_arg, out_arg), (RoutineInplace(out_arg, expr),))
    # Test arg errors
    raises(ValueError, lambda: routine('test', (a, b, c), inp_expr))
    raises(ValueError, lambda: routine('test', (a, b, c, out), expr))


def test_Routine():
    test = routine('test', (a, b, c), expr)
    assert test.name == symbols('test')
    assert test.arguments == (a_arg, b_arg, c_arg)
    assert test.results == (routine_result(expr),)
    assert test.returns == (routine_result(expr),)
    assert test.inplace == ()
    # Multiple results
    test = routine('test', (a, b, c, out), (expr, inp_expr))
    assert test.arguments == (a_arg, b_arg, c_arg, out_arg)
    assert test.results == (routine_result(expr), routine_result(inp_expr))
    assert test.returns == (routine_result(expr),)
    assert test.inplace == (routine_result(inp_expr),)


def test_RoutineCall():
    test = routine('test', (a, b, c), expr)
    rcall = test(1, 2, 3)
    assert rcall.routine == test
    assert rcall.arguments == (1, 2, 3)
    assert rcall.returns == ScalarRoutineCallResult(rcall, -1)
    assert rcall.inplace == Dict()
    # Multiple results
    test = routine('test', (a, b, c, out), (expr, inp_expr))
    rcall = test(1, 2, 3, out)
    assert rcall.routine == test
    assert rcall.arguments == (1, 2, 3, out)
    assert rcall.returns == ScalarRoutineCallResult(rcall, -1)
    assert rcall.inplace == Dict({out: ScalarRoutineCallResult(rcall, out)})


def test_ScalarRoutineCallResult():
    test = routine('test', (a, b, c, out), (expr, inp_expr))
    rcall = test(1, 2, 3, out)
    res_expr = expr.subs({a: 1, b: 2, c: 3})
    ret = rcall.returns
    inp = rcall.inplace[out]
    assert ret.expr == res_expr
    assert inp.expr == res_expr
    assert ret.free_symbols == set([out])
    assert inp.free_symbols == set([out])


def test_ScalarRoutineCallResult_assumptions():
    test = routine('test', (a, b, c), expr)
    rcall = test(1, 2, 3)
    res_expr = expr.subs({a: 1, b: 2, c: 3})
    ret = rcall.returns
    # Use results in some expressions (will error if fails)
    ret*a + sin(b*c)
    sin(ret)
    sqrt(ret)*ret
    def assump_checker(ret, expr, name):
        name = 'is_' + name
        assert getattr(ret, name) == getattr(ret, name)
    # Check the aliasing of assumptions
    for name in _assume_defined:
        assump_checker(ret, res_expr, name)
    # See if the assumption checks broke anything
    ret*a + sin(b*c)
    sin(ret)
    sqrt(ret)*ret


def test_ScalarRoutineCallResult_subs():
    test = routine('test', (a, b, c), expr)
    rcall = test(1, 2, 3)
    ret = rcall.returns
    assert ret.subs(a, 1) == ret
    assert ret.subs(1, a) == test(a, 2, 3).returns


def test_ScalarRoutineCallResult_simplify():
    ret = routine('test', (a, b, c), expr)(1, 2, 3).returns
    test_expr = ret * sin(a)/cos(a)
    assert simplify(test_expr) == ret * tan(a)

