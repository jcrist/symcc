from sympy.core.compatibility import string_types

from symcc.generators.codegen import get_code_generator
from symcc.types.routines import Routine

__all__ = ["codegen"]


def codegen(name_expr, language, prefix, project="project", to_files=False,
        header=True, empty=True, argument_sequence=None):
    """Write source code for the given expressions in the given language.

    :Mandatory Arguments:

    ``name_expr``
        A single (name, expression) tuple or a list of (name, expression)
        tuples. Each tuple corresponds to a routine.  If the expression is an
        equality (an instance of class Equality) the left hand side is
        considered an output argument.
    ``language``
            A string that indicates the source code language. This is case
            insensitive. For the moment, only 'C' and 'F95' is supported.
    ``prefix``
            A prefix for the names of the files that contain the source code.
            Proper (language dependent) suffixes will be appended.

    :Optional Arguments:

    ``project``
        A project name, used for making unique preprocessor instructions.
        [DEFAULT="project"]
    ``to_files``
        When True, the code will be written to one or more files with the given
        prefix, otherwise strings with the names and contents of these files
        are returned. [DEFAULT=False]
    ``header``
        When True, a header is written on top of each source file.
        [DEFAULT=True]
    ``empty``
        When True, empty lines are used to structure the code.  [DEFAULT=True]
    ``argument_sequence``
        sequence of arguments for the routine in a preferred order.  A
        ValueError is raised if required arguments are missing.  Redundant
        arguments are used without warning.

        If omitted, arguments will be ordered alphabetically, but with all
        input aguments first, and then output or in-out arguments.

    >>> from sympy.utilities.codegen import codegen
    >>> from sympy.abc import x, y, z
    >>> [(c_name, c_code), (h_name, c_header)] = codegen(
    ...     ("f", x+y*z), "C", "test", header=False, empty=False)
    >>> print(c_name)
    test.c
    >>> print(c_code)
    #include "test.h"
    #include <math.h>
    double f(double x, double y, double z) {
      double f_result;
      f_result = x + y*z;
      return f_result;
    }
    >>> print(h_name)
    test.h
    >>> print(c_header)
    #ifndef PROJECT__TEST__H
    #define PROJECT__TEST__H
    double f(double x, double y, double z);
    #endif

    """

    # Initialize the code generator.
    code_gen = get_code_generator(language, project)

    # Construct the routines based on the name_expression pairs.
    #  mainly the input arguments require some work
    routines = []
    if isinstance(name_expr[0], string_types):
        # single tuple is given, turn it into a singleton list with a tuple.
        name_expr = [name_expr]

    for name, expr in name_expr:
        routines.append(Routine(name, expr, argument_sequence))

    # Write the code.
    return code_gen.write(routines, prefix, to_files, header, empty)
