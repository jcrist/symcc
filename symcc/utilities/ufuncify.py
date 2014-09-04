from sympy import C

from symcc.wrappers.ufuncify_wrapper import UfuncifyCodeWrapper
from symcc.generators.ccodegen import CCodeGen
from symcc.types.routines import Routine

__all__ = ["ufuncify"]


def ufuncify(args, expr, tempdir=None, flags=[], verbose=False, helpers=[]):
    """
    Generates a binary ufunc-like lambda function for numpy arrays

    ``args``
        Either a Symbol or a tuple of symbols. Specifies the argument sequence
        for the ufunc-like function.

    ``expr``
        A SymPy expression that defines the element wise operation

    The returned function can only act on one array at a time, as only the
    first argument accept arrays as input.

    .. Note:: a *proper* numpy ufunc is required to support broadcasting, type
       casting and more.  The function returned here, may not qualify for
       numpy's definition of a ufunc.  That why we use the term ufunc-like.

    References
    ==========
    [1] http://docs.scipy.org/doc/numpy/reference/ufuncs.html

    Examples
    ========

    >>> from sympy.utilities.autowrap import ufuncify
    >>> from sympy.abc import x, y
    >>> import numpy as np
    >>> f = ufuncify([x, y], y + x**2)
    >>> f([1, 2, 3], 2)
    [ 3.  6.  11.]
    >>> a = f(np.arange(5), 3)
    >>> isinstance(a, np.ndarray)
    True
    >>> print a
    [ 3. 4. 7. 12. 19.]

    """
    if isinstance(args, C.Symbol):
        args = [args]
    else:
        args = list(args)

    code_wrapper = UfuncifyCodeWrapper(CCodeGen("ufuncify"), tempdir, flags,
            verbose)
    routine = Routine('autofunc', expr, args)
    helps = []
    for name, expr, args in helpers:
        helps.append(Routine(name, expr, args))
    return code_wrapper.wrap_code(routine, helpers=helps)
