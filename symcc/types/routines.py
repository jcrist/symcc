from __future__ import print_function, division

from sympy.core import Symbol, Tuple, Expr, Basic, Integer, Dict
from sympy.utilities.iterables import iterable
from sympy.core.sympify import _sympify
from sympy import simplify
from sympy.core.assumptions import _assume_defined


from symcc.types.ast import (Assign, Argument, DataType, datatype,
        InOutArgument, OutArgument, InArgument, Bool, Int, Float, Double)
from symcc.utilities.util import do_once, iterate


class RoutineResult(Basic):
    """Base class for all outgoing information from a routine."""
    pass


class RoutineReturn(RoutineResult):
    """Represents a result provided via a ``Return``"""

    def __new__(cls, dtype, expr):
        if isinstance(dtype, str):
            dtype = datatype(dtype)
        elif not isinstance(dtype, DataType):
            raise TypeError("datatype must be an instance of DataType.")
        expr = _sympify(expr)
        return Basic.__new__(cls, dtype, expr)

    @property
    def dtype(self):
        return self._args[0]

    @property
    def expr(self):
        return self._args[1]


class RoutineInplace(RoutineResult):
    """Represents a result provided via an inplace manipulation"""

    def __new__(cls, arg, expr):
        if not isinstance(arg, Argument):
            raise TypeError("arg must be of type `Argument`")
        expr = _sympify(expr)
        return Basic.__new__(cls, arg, expr)

    @property
    def dtype(self):
        return self.name.dtype

    @property
    def name(self):
        return self._args[0]

    @property
    def expr(self):
        return self._args[1]


def routine_result(expr):
    """Easy creation of instances of RoutineResult"""
    expr = _sympify(expr)
    if isinstance(expr, Assign):
        lhs = expr.lhs
        return RoutineInplace(OutArgument(lhs, datatype(lhs)), expr.rhs)
    else:
        return RoutineReturn(datatype(expr), expr)


class Routine(Basic):
    """Represents a function definition.

    Parameters
    ----------
    name : str
        The name of the function.
    args : iterable
        The arguments to the function, of type Argument.
    results : iterable
        The results of the function, of type RoutineResult.
    """

    def __new__(cls, name, args, results):
        # name
        if isinstance(name, str):
            name = Symbol(name)
        elif not isinstance(name, Symbol):
            raise TypeError("Function name must be Symbol or string")
        # args
        if not iterable(args):
            raise TypeError("args must be an iterable")
        if not all(isinstance(a, Argument) for a in args):
            raise TypeError("All args must be of type Argument")
        args = Tuple(*args)
        # results
        if not iterable(results):
            raise TypeError("results must be an iterable")
        if not all(isinstance(i, RoutineResult) for i in results):
            raise TypeError("All results must be of type RoutineResult")
        results = Tuple(*results)
        return Basic.__new__(cls, name, args, results)

    @property
    def name(self):
        return self._args[0]

    @property
    def arguments(self):
        return self._args[1]

    @property
    def results(self):
        return self._args[2]

    @property
    def returns(self):
        return tuple(r for r in self.results if isinstance(r, RoutineReturn))

    @property
    def inplace(self):
        return tuple(r for r in self.results if isinstance(r, RoutineInplace))

    def annotate(self):
        """Prints out a description of the routine"""
        pass

    def __call__(self, *args):
        return RoutineCall(self, args)


def routine(name, args, expr):
    """Easy interface for creating instances of Routine"""

    if isinstance(name, str):
        name = Symbol(name)
    elif not isinstance(name, Symbol):
        raise TypeError("name must be str or Symbol")
    expr = _sympify(expr)
    args = _make_arguments(args, expr)
    results = [routine_result(i) for i in iterate(expr)]
    return Routine(name, args, results)


def _make_arguments(args, expr):
    frees = expr.free_symbols
    args_set = set(args)
    missing = frees - args_set
    if not args_set == frees:
        raise ValueError("Missing arguments {0}".format(', '.join(
                str(a) for a in missing)))
    outs = set([i.lhs for i in iterate(expr) if isinstance(i, Assign)])
    getvars = lambda x: x.rhs.free_symbols if isinstance(x, Assign) else x.free_symbols
    ins = set.union(*[getvars(i) for i in iterate(expr)])
    inouts = ins.intersection(outs)
    ins = ins - inouts
    outs = outs - inouts
    arglist = []
    for i in args:
        if i in ins:
            arglist.append(InArgument(i, datatype(i)))
        elif i in outs:
            arglist.append(OutArgument(i, datatype(i)))
        elif i in inouts:
            arglist.append(InOutArgument(i, datatype(i)))
        else:
            raise ValueError("How did you even get here????")
    return arglist


# A dictionary of acceptable type aliases. The key is the type of the
# argument defined in the Routine. The value is a tuple of types that
# are acceptable to pass to the routine for that argument.
_accepted_types = {Int: (Int,),
                   Bool: (Bool,),
                   Double: (Double, Float, Int),
                   Float: (Double, Float, Int)}

def _validate_arg(arg, param):
    arg_type = datatype(arg)
    if not arg_type in _accepted_types[param.dtype]:
        raise ValueError("Type mismatch on argument %s. "
                         "Expected %s, got %s." % (n, param.dtype, arg_type))


class RoutineCall(Basic):
    def __new__(cls, routine, args):
        if not isinstance(routine, Routine):
            raise TypeError("routine must be of type Routine")
        if len(routine.arguments) != len(args):
            raise ValueError("Incorrect number of arguments")
        for n, (a, p) in enumerate(zip(args, routine.arguments)):
            _validate_arg(a, p)
        args = Tuple(*args)
        return Basic.__new__(cls, routine, args)

    @property
    def routine(self):
        return self._args[0]

    @property
    def arguments(self):
        return self._args[1]

    @property
    def returns(self):
        """Returns a tuple of return values"""
        return self._returns()

    @do_once
    def _returns(self):
        ret = self.routine.returns
        if len(ret) == 1:
            return ScalarRoutineCallResult(self, -1)
        else:
            return Tuple(*[ScalarRoutineCallResult(self, n) for n, i in enumerate(ret)])

    @property
    def inplace(self):
        """Returns a dict of implicit return values"""
        return self._inplace()

    @do_once
    def _inplace(self):
        inp = self.routine.inplace
        d = dict((i.name.name, ScalarRoutineCallResult(self, i.name.name)) for i in
                iterate(inp))
        return Dict(d)

    def _sympystr(self, printer):
        sstr = printer.doprint
        args = ', '.join(sstr(a) for a in self.arguments)
        name = sstr(self.routine.name)
        return "{0}({1})".format(name, args)

    def _eval_subs(self, old, new):
        """Don't perform subs inside the routine"""
        args = self.arguments.subs(old, new)
        return self.func(self.routine, args)

    def _eval_simplify(self, **kwargs):
        args = simplify(self.arguments)
        return self.func(self.routine, args)


class ScalarRoutineCallResult(Expr):
    """Represents a scalar result returned from a routine call"""

    def __new__(cls, routine_call, idx):
        if not isinstance(routine_call, RoutineCall):
            raise TypeError("routine_call must be of type RoutineCall")
        idx = _sympify(idx)
        if isinstance(idx, Integer):
            if not -1 <= idx < len(routine_call.routine.returns):
                raise ValueError("idx out of bounds")
        elif isinstance(idx, Symbol):
            names = [a.name.name for a in routine_call.routine.inplace]
            if idx not in names:
                raise KeyError("unknown inplace result %s" % idx)
        # Get the name of the symbol
        if idx == -1:
            expr = routine_call.routine.returns[0].expr
        elif isinstance(idx, Integer):
            expr = routine_call.routine.returns[idx].expr
        else:
            inp = routine_call.routine.inplace
            expr = [i.expr for i in inp if idx == i.name.name][0]
        # Sub in values to expression
        args = [i.name for i in routine_call.routine.arguments]
        values = [i for i in routine_call.arguments]
        expr = expr.subs(dict(zip(args, values)))
        # Create the object
        s = Expr.__new__(cls, routine_call, idx)
        s._expr = expr
        _alias_assumptions(s, expr)
        return s

    def _sympystr(self, printer):
        sstr = printer.doprint
        call = sstr(self.rcall)
        if self.idx == -1:
            return "{0}.returns".format(call)
        elif isinstance(self.idx, Integer):
            return "{0}.returns[{1}]".format(call, sstr(self.idx))
        else:
            return "{0}.inplace[{1}]".format(call, sstr(self.idx))

    def _eval_subs(self, old, new):
        """Don't perform subs on the idx"""
        rcall = self.rcall.subs(old, new)
        return self.func(rcall, self.idx)

    @property
    def rcall(self):
        return self._args[0]

    @property
    def idx(self):
        return self._args[1]

    @property
    def expr(self):
        return self._expr

    @property
    def free_symbols(self):
        return self.rcall.arguments.free_symbols


def _alias_assumptions(alias, obj):
    """Alias all calls to alias.is_* to obj.is_*. Note that this assumes *no*
    default assumptions"""
    for a in _assume_defined:
        alias._prop_handler[a] = _make_func(a)
    alias._assumptions.clear()


def _make_func(name):
    def lookup(self):
        return getattr(self.expr, 'is_' + name)
    return lookup
