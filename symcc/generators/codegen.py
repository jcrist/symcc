from __future__ import print_function, division

from sympy.core.compatibility import StringIO

__all__ = ["CodeGen"]

header_comment = """Code generated with sympy %(version)s

See http://www.sympy.org/ for more information.

This file is part of '%(project)s'
"""

class CodeGen(object):
    """Abstract class for the code generators."""

    def __init__(self, project="project"):
        """Initialize a code generator.

           Derived classes will offer more options that affect the generated
           code.
        """
        self.project = project

    def write(self, routines, prefix, to_files=False, header=True, empty=True):
        """Writes all the source code files for the given routines.

            The generate source is returned as a list of (filename, contents)
            tuples, or is written to files (see options). Each filename consists
            of the given prefix, appended with an appropriate extension.

            ``routines``
                A list of Routine instances to be written
            ``prefix``
                The prefix for the output files
            ``to_files``
                When True, the output is effectively written to files.
                [DEFAULT=False] Otherwise, a list of (filename, contents)
                tuples is returned.
            ``header``
                When True, a header comment is included on top of each source
                file. [DEFAULT=True]
            ``empty``
                When True, empty lines are included to structure the source
                files. [DEFAULT=True]

        """
        if to_files:
            for dump_fn in self.dump_fns:
                filename = "%s.%s" % (prefix, dump_fn.extension)
                with open(filename, "w") as f:
                    dump_fn(self, routines, f, prefix, header, empty)
        else:
            result = []
            for dump_fn in self.dump_fns:
                filename = "%s.%s" % (prefix, dump_fn.extension)
                contents = StringIO()
                dump_fn(self, routines, contents, prefix, header, empty)
                result.append((filename, contents.getvalue()))
            return result

    def dump_code(self, routines, f, prefix, header=True, empty=True):
        """Write the code file by calling language specific methods in correct order

        The generated file contains all the definitions of the routines in
        low-level code and refers to the header file if appropriate.

        :Arguments:

        routines
            A list of Routine instances
        f
            A file-like object to write the file to
        prefix
            The filename prefix, used to refer to the proper header file. Only
            the basename of the prefix is used.

        :Optional arguments:

        header
            When True, a header comment is included on top of each source file.
            [DEFAULT=True]
        empty
            When True, empty lines are included to structure the source files.
            [DEFAULT=True]
        """

        code_lines = self._preprocessor_statements(prefix)

        for routine in routines:
            if empty:
                code_lines.append("\n")
            code_lines.extend(self._get_routine_opening(routine))
            code_lines.extend(self._declare_arguments(routine))
            code_lines.extend(self._declare_locals(routine))
            if empty:
                code_lines.append("\n")
            code_lines.extend(self._call_printer(routine))
            if empty:
                code_lines.append("\n")
            code_lines.extend(self._get_routine_ending(routine))

        code_lines = self._indent_code(''.join(code_lines))

        if header:
            code_lines = ''.join(self._get_header() + [code_lines])

        if code_lines:
            f.write(code_lines)


GENERATORS = {}

def register_generator(language, generator):
    GENERATORS[language.upper()] = generator

def get_code_generator(language, project):
    generator = GENERATORS.get(language.upper())
    if generator is None:
        raise ValueError("Language '%s' is not supported." % language)
    return generator(project)
