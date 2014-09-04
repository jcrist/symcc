from sympy.utilities.lambdify import implemented_function

from symcc.wrappers.codewrapper import get_wrapper
from symcc.generators.codegen import get_code_generator
from symcc.types.routines import Routine

__all__ = ["autowrap", "binary_function"]


def autowrap(
    expr, language='F95', backend='f2py', tempdir=None, args=None, flags=[],
        verbose=False, helpers=[]):
    """Generates python callable binaries based on the math expression.

    expr
        The SymPy expression that should be wrapped as a binary routine

    :Optional arguments:

    language
        The programming language to use, currently 'C' or 'F95'
    backend
        The wrapper backend to use, currently f2py or Cython
    tempdir
        Path to directory for temporary files.  If this argument is supplied,
        the generated code and the wrapper input files are left intact in the
        specified path.
    args
        Sequence of the formal parameters of the generated code, if ommited the
        function signature is determined by the code generator.
    flags
        Additional option flags that will be passed to the backend
    verbose
        If True, autowrap will not mute the command line backends.  This can be
        helpful for debugging.
    helpers
        Used to define auxillary expressions needed for the main expr.  If the
        main expression need to do call a specialized function it should be put
        in the ``helpers`` list.  Autowrap will then make sure that the
        compiled main expression can link to the helper routine.  Items should
        be tuples with (<funtion_name>, <sympy_expression>, <arguments>).  It
        is mandatory to supply an argument sequence to helper routines.

    >>> from sympy.abc import x, y, z
    >>> from sympy.utilities.autowrap import autowrap
    >>> expr = ((x - y + z)**(13)).expand()
    >>> binary_func = autowrap(expr)
    >>> binary_func(1, 4, 2)
    -1.0

    """

    code_generator = get_code_generator(language, "autowrap")
    CodeWrapperClass = get_wrapper(backend)
    code_wrapper = CodeWrapperClass(code_generator, tempdir, flags, verbose)
    try:
        routine = Routine('autofunc', expr, args)
    except ValueError as e:
        # TODO: This used to be handled by some silly error passing. Fix
        # with a better design.
        raise e

    helps = []
    for name, expr, args in helpers:
        helps.append(Routine(name, expr, args))

    return code_wrapper.wrap_code(routine, helpers=helps)


def binary_function(symfunc, expr, **kwargs):
    """Returns a sympy function with expr as binary implementation

    This is a convenience function that automates the steps needed to
    autowrap the SymPy expression and attaching it to a Function object
    with implemented_function().

    >>> from sympy.abc import x, y
    >>> from sympy.utilities.autowrap import binary_function
    >>> expr = ((x - y)**(25)).expand()
    >>> f = binary_function('f', expr)
    >>> type(f)
    <class 'sympy.core.function.UndefinedFunction'>
    >>> 2*f(x, y)
    2*f(x, y)
    >>> f(x, y).evalf(2, subs={x: 1, y: 2})
    -1.0
    """
    binary = autowrap(expr, **kwargs)
    return implemented_function(symfunc, binary)
