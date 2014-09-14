from __future__ import print_function, division

from sympy import __version__ as sympy_version

from symcc.generators.codegen import CodeGen, header_comment, register_generator
from symcc.printers.ccode import ccode, CCodePrinter
from symcc.types.routines import Result, ResultBase, AssignmentError

__all__ = ["CCodeGen"]


class CCodeGen(CodeGen):
    """
    Generator for C code

    The .write() method inherited from CodeGen will output a code file and an
    interface file, <prefix>.c and <prefix>.h respectively.
    """

    code_extension = "c"
    interface_extension = "h"

    def _get_header(self):
        """Writes a common header for the generated files."""
        code_lines = []
        code_lines.append("/" + "*"*78 + '\n')
        tmp = header_comment % {"version": sympy_version,
            "project": self.project}
        for line in tmp.splitlines():
            code_lines.append(" *%s*\n" % line.center(76))
        code_lines.append(" " + "*"*78 + "/\n")
        return code_lines

    def get_prototype(self, routine):
        """Returns a string for the function prototype for the given routine.

           If the routine has multiple result objects, a ValueError is
           raised.

           See: http://en.wikipedia.org/wiki/Function_prototype
        """
        if len(routine.results) > 1:
            raise ValueError("C only supports a single or no return value.")
        elif len(routine.results) == 1:
            ctype = routine.results[0].get_datatype('C')
        else:
            ctype = "void"

        type_args = []
        for arg in routine.arguments:
            name = ccode(arg.name)
            if arg.dimensions or isinstance(arg, ResultBase):
                type_args.append((arg.get_datatype('C'), "*%s" % name))
            else:
                type_args.append((arg.get_datatype('C'), name))
        arguments = ", ".join([ "%s %s" % t for t in type_args])
        return "%s %s(%s)" % (ctype, routine.name, arguments)

    def _preprocessor_statements(self, prefix):
        code_lines = []
        #code_lines.append("#include \"%s.h\"\n" % os.path.basename(prefix))
        code_lines.append("#include <math.h>\n")
        return code_lines

    def _get_routine_opening(self, routine):
        prototype = self.get_prototype(routine)
        return ["static inline %s {\n" % prototype]

    def _declare_arguments(self, routine):
        # arguments are declared in prototype
        return []

    def _declare_locals(self, routine):
        # loop variables are declared in loop statement
        return []

    def _call_printer(self, routine):
        code_lines = []

        # Compose a list of symbols to be dereferenced in the function
        # body. These are the arguments that were passed by a reference
        # pointer, excluding arrays.
        dereference = []
        for arg in routine.arguments:
            if isinstance(arg, ResultBase) and not arg.dimensions:
                dereference.append(arg.name)

        return_val = None
        for result in routine.result_variables:
            if isinstance(result, Result):
                assign_to = routine.name + "_result"
                t = result.get_datatype('c')
                code_lines.append("{0} {1};\n".format(t, str(assign_to)))
                return_val = assign_to
            else:
                assign_to = result.result_var

            try:
                constants, not_c, c_expr = ccode(result.expr, human=False,
                        assign_to=assign_to, dereference=dereference)
            except AssignmentError:
                assign_to = result.result_var
                code_lines.append(
                    "%s %s;\n" % (result.get_datatype('c'), str(assign_to)))
                constants, not_c, c_expr = ccode(result.expr, human=False,
                        assign_to=assign_to, dereference=dereference)

            for name, value in sorted(constants, key=str):
                code_lines.append("double const %s = %s;\n" % (name, value))
            code_lines.append("%s\n" % c_expr)

        if return_val:
            code_lines.append("   return %s;\n" % return_val)
        return code_lines

    def _indent_code(self, codelines):
        p = CCodePrinter()
        return p.indent_code(codelines)

    def _get_routine_ending(self, routine):
        return ["}\n"]

    def dump_c(self, routines, f, prefix, header=True, empty=True):
        self.dump_code(routines, f, prefix, header, empty)
    dump_c.extension = code_extension
    dump_c.__doc__ = CodeGen.dump_code.__doc__

    def dump_h(self, routines, f, prefix, header=True, empty=True):
        """Writes the C header file.

           This file contains all the function declarations.

           :Arguments:

           routines
                A list of Routine instances
           f
                A file-like object to write the file to
           prefix
                The filename prefix, used to construct the include guards.

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
        guard_name = "%s__%s__H" % (self.project.replace(
            " ", "_").upper(), prefix.replace("/", "_").upper())
        # include guards
        if empty:
            print(file=f)
        print("#ifndef %s" % guard_name, file=f)
        print("#define %s" % guard_name, file=f)
        if empty:
            print(file=f)
        # declaration of the function prototypes
        for routine in routines:
            prototype = self.get_prototype(routine)
            print("%s;" % prototype, file=f)
        # end if include guards
        if empty:
            print(file=f)
        print("#endif", file=f)
        if empty:
            print(file=f)
    dump_h.extension = interface_extension

    # This list of dump functions is used by CodeGen.write to know which dump
    # functions it has to call.
    dump_fns = [dump_c, dump_h]

register_generator('C', CCodeGen)
