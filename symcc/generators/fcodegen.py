from __future__ import print_function, division

from sympy import Function
from sympy import __version__ as sympy_version

from symcc.generators.codegen import CodeGen, header_comment, register_generator
from symcc.printers.fcode import fcode, FCodePrinter
from symcc.types.routines import (InputArgument, InOutArgument,
        OutputArgument, Result, get_default_datatype)

__all__ = ["FCodeGen"]

class FCodeGen(CodeGen):
    """
    Generator for Fortran 95 code

    The .write() method inherited from CodeGen will output a code file and an
    interface file, <prefix>.f90 and <prefix>.h respectively.
    """

    code_extension = "f90"
    interface_extension = "h"

    def __init__(self, project='project'):
        CodeGen.__init__(self, project)

    def _get_symbol(self, s):
        """returns the symbol as fcode print it"""
        return fcode(s).strip()

    def _get_header(self):
        """Writes a common header for the generated files."""
        code_lines = []
        code_lines.append("!" + "*"*78 + '\n')
        tmp = header_comment % {"version": sympy_version,
            "project": self.project}
        for line in tmp.splitlines():
            code_lines.append("!*%s*\n" % line.center(76))
        code_lines.append("!" + "*"*78 + '\n')
        return code_lines

    def _preprocessor_statements(self, prefix):
        return []

    def _get_routine_opening(self, routine):
        """
        Returns the opening statements of the fortran routine
        """
        code_list = []
        if len(routine.results) > 1:
            raise ValueError(
                "Fortran only supports a single or no return value.")
        elif len(routine.results) == 1:
            result = routine.results[0]
            code_list.append(result.get_datatype('fortran'))
            code_list.append("function")
        else:
            code_list.append("subroutine")

        args = ", ".join("%s" % self._get_symbol(arg.name)
                for arg in routine.arguments)

        # name of the routine + arguments
        code_list.append("%s(%s)\n" % (routine.name, args))
        code_list = [ " ".join(code_list) ]

        code_list.append('implicit none\n')
        return code_list

    def _declare_arguments(self, routine):
        # argument type declarations
        code_list = []
        array_list = []
        scalar_list = []
        for arg in routine.arguments:

            if isinstance(arg, InputArgument):
                typeinfo = "%s, intent(in)" % arg.get_datatype('fortran')
            elif isinstance(arg, InOutArgument):
                typeinfo = "%s, intent(inout)" % arg.get_datatype('fortran')
            elif isinstance(arg, OutputArgument):
                typeinfo = "%s, intent(out)" % arg.get_datatype('fortran')
            else:
                raise ValueError("Unkown Argument type: %s" % type(arg))

            fprint = self._get_symbol

            if arg.dimensions:
                # fortran arrays start at 1
                dimstr = ", ".join(["%s:%s" % (
                    fprint(dim[0] + 1), fprint(dim[1] + 1))
                    for dim in arg.dimensions])
                typeinfo += ", dimension(%s)" % dimstr
                array_list.append("%s :: %s\n" % (typeinfo, fprint(arg.name)))
            else:
                scalar_list.append("%s :: %s\n" % (typeinfo, fprint(arg.name)))

        # scalars first, because they can be used in array declarations
        code_list.extend(scalar_list)
        code_list.extend(array_list)

        return code_list

    def _declare_locals(self, routine):
        code_list = []
        for var in sorted(routine.local_vars, key=str):
            typeinfo = get_default_datatype(var)
            code_list.append("%s :: %s\n" % (
                typeinfo.fname, self._get_symbol(var)))
        return code_list

    def _get_routine_ending(self, routine):
        """
        Returns the closing statements of the fortran routine
        """
        if len(routine.results) == 1:
            return ["end function\n"]
        else:
            return ["end subroutine\n"]

    def get_interface(self, routine):
        """Returns a string for the function interface for the given routine and
           a single result object, which can be None.

           If the routine has multiple result objects, a ValueError is
           raised.

           See: http://en.wikipedia.org/wiki/Function_prototype

        """
        prototype = [ "interface\n" ]
        prototype.extend(self._get_routine_opening(routine))
        prototype.extend(self._declare_arguments(routine))
        prototype.extend(self._get_routine_ending(routine))
        prototype.append("end interface\n")

        return "".join(prototype)

    def _call_printer(self, routine):
        declarations = []
        code_lines = []
        for result in routine.result_variables:
            if isinstance(result, Result):
                assign_to = routine.name
            elif isinstance(result, (OutputArgument, InOutArgument)):
                assign_to = result.result_var

            constants, not_fortran, f_expr = fcode(result.expr,
                assign_to=assign_to, source_format='free', human=False)

            for obj, v in sorted(constants, key=str):
                t = get_default_datatype(obj)
                declarations.append(
                    "%s, parameter :: %s = %s\n" % (t.fname, obj, v))
            for obj in sorted(not_fortran, key=str):
                t = get_default_datatype(obj)
                if isinstance(obj, Function):
                    name = obj.func
                else:
                    name = obj
                declarations.append("%s :: %s\n" % (t.fname, name))

            code_lines.append("%s\n" % f_expr)
        return declarations + code_lines

    def _indent_code(self, codelines):
        p = FCodePrinter({'source_format': 'free', 'human': False})
        return p.indent_code(codelines)

    def dump_f95(self, routines, f, prefix, header=True, empty=True):
        # check that symbols are unique with ignorecase
        for r in routines:
            lowercase = set([str(x).lower() for x in r.variables])
            orig_case = set([str(x) for x in r.variables])
            if len(lowercase) < len(orig_case):
                raise ValueError("Fortran ignores case. Got symbols: %s" %
                        (", ".join([str(var) for var in r.variables])))
        self.dump_code(routines, f, prefix, header, empty)
    dump_f95.extension = code_extension
    dump_f95.__doc__ = CodeGen.dump_code.__doc__

    def dump_h(self, routines, f, prefix, header=True, empty=True):
        """Writes the interface to a header file.

           This file contains all the function declarations.

           :Arguments:

           routines
                A list of Routine instances
           f
                A file-like object to write the file to
           prefix
                The filename prefix

           :Optional arguments:

           header
                When True, a header comment is included on top of each source
                file. [DEFAULT=True]
           empty
                When True, empty lines are included to structure the source
                files. [DEFAULT=True]
        """
        if header:
            print(''.join(self._get_header()), file=f)
        if empty:
            print(file=f)
        # declaration of the function prototypes
        for routine in routines:
            prototype = self.get_interface(routine)
            f.write(prototype)
        if empty:
            print(file=f)
    dump_h.extension = interface_extension

    # This list of dump functions is used by CodeGen.write to know which dump
    # functions it has to call.
    dump_fns = [dump_f95, dump_h]

register_generator('F95', FCodeGen)
