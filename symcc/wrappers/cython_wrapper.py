import sys

from sympy import C

from symcc.wrappers.codewrapper import CodeWrapper, register_wrapper
from symcc.types.routines import (OutputArgument, InOutArgument, InputArgument, ResultBase)

__all__ = ["CythonCodeWrapper"]


class CythonCodeWrapper(CodeWrapper):
    """Wrapper that uses Cython"""

    setup_template = (
            "from distutils.core import setup\n"
            "from distutils.extension import Extension\n"
            "from Cython.Distutils import build_ext\n"
            "\n"
            "setup(\n"
            "    cmdclass = {{'build_ext': build_ext}},\n"
            "    ext_modules = [Extension({ext_args}, extra_compile_args=['-std=c99'])]\n"
            "        )")

    pyx_imports = (
            "import numpy as np\n"
            "cimport numpy as np\n\n")

    pyx_header = (
            "cdef extern from '{header_file}.h':\n"
            "    {prototype}\n\n")

    pyx_func = (
            "def {name}_c({arg_string}):\n"
            "\n"
            "{declarations}"
            "{body}")

    _need_numpy = False

    @property
    def command(self):
        command = [sys.executable, "setup.py", "build_ext", "--inplace"]
        return command

    def _prepare_files(self, routine):
        pyxfilename = self.module_name + '.pyx'
        codefilename = "%s.%s" % (self.filename, self.generator.code_extension)

        # pyx
        with open(pyxfilename, 'w') as f:
            self.dump_pyx([routine], f, self.filename)

        # setup.py
        ext_args = [repr(self.module_name), repr([pyxfilename, codefilename])]
        with open('setup.py', 'w') as f:
            f.write(self.setup_template.format(ext_args=", ".join(ext_args)))

    @classmethod
    def _get_wrapped_function(cls, mod, name):
        return getattr(mod, name + '_c')

    def dump_pyx(self, routines, f, prefix):
        """Write a Cython file with python wrappers

        This file contains all the definitions of the routines in c code and
        refers to the header file.

        Arguments
        ---------
        routines
            List of Routine instances
        f
            File-like object to write the file to
        prefix
            The filename prefix, used to refer to the proper header file.
            Only the basename of the prefix is used.
        """
        headers = []
        functions = []
        for routine in routines:
            prototype = self.generator.get_prototype(routine)

            # C Function Header Import
            headers.append(self.pyx_header.format(header_file=prefix,
                    prototype=prototype))

            # Partition the C function arguments into categories
            py_rets, py_args, py_loc, py_inf = self._partition_args(routine.arguments)

            # Function prototype
            name = routine.name
            arg_string = ", ".join(self._prototype_arg(arg) for arg in py_args)

            # Local Declarations
            local_decs = []
            for arg, val in py_inf.items():
                proto = self._prototype_arg(arg)
                mat, ind = val
                local_decs.append("    cdef {0} = {1}.shape[{2}]".format(proto, mat, ind))
            local_decs.extend(["    cdef {0}".format(self._declare_arg(a)) for a in py_loc])
            declarations = "\n".join(local_decs)
            if declarations:
                declarations = declarations + "\n"

            # Function Body
            args_c = ", ".join([self._call_arg(a) for a in routine.arguments])
            rets = ", ".join([str(r.name) for r in py_rets])
            if routine.results:
                body = '    return %s(%s)' % (routine.name, args_c)
                if rets:
                    body = body + ', ' + rets
            else:
                body = '    %s(%s)\n' % (routine.name, args_c)
                body = body + '    return ' + rets

            functions.append(self.pyx_func.format(name=name, arg_string=arg_string,
                    declarations=declarations, body=body))

        # Write text to file
        if self._need_numpy:
            # Only import numpy if required
            f.write(self.pyx_imports)
        f.write('\n'.join(headers))
        f.write('\n'.join(functions))

    def _partition_args(self, args):
        """Group function arguments into categories."""
        py_args = []
        py_returns = []
        py_locals = []
        py_inferred = {}
        for arg in args:
            if isinstance(arg, OutputArgument):
                py_returns.append(arg)
                py_locals.append(arg)
            elif isinstance(arg, InOutArgument):
                py_returns.append(arg)
                py_args.append(arg)
            else:
                py_args.append(arg)
        # Find arguments that are array dimensions. These can be inferred
        # locally in the Cython code.
            if isinstance(arg, (InputArgument, InOutArgument)) and arg.dimensions:
                dims = [d[1] + 1 for d in arg.dimensions]
                sym_dims = [(i, d) for (i, d) in enumerate(dims) if isinstance(d, C.Symbol)]
                for (i, d) in sym_dims:
                    py_inferred[d] = (arg.name, i)
        for arg in args:
            if arg.name in py_inferred:
                py_inferred[arg] = py_inferred.pop(arg.name)
        # Filter inferred arguments from py_args
        py_args = [a for a in py_args if a not in py_inferred]
        return py_returns, py_args, py_locals, py_inferred

    def _prototype_arg(self, arg):
        mat_dec = "np.ndarray[{mtype}, ndim={ndim}] {name}"
        np_types = {'double': 'np.double_t',
                    'int': 'np.int_t'}
        t = arg.get_datatype('c')
        if arg.dimensions:
            self._need_numpy = True
            ndim = len(arg.dimensions)
            mtype = np_types[t]
            return mat_dec.format(mtype=mtype, ndim=ndim, name=arg.name)
        else:
            return "%s %s" % (t, str(arg.name))

    def _declare_arg(self, arg):
        proto = self._prototype_arg(arg)
        if arg.dimensions:
            shape = '(' + ','.join(str(i[1] + 1) for i in arg.dimensions) + ')'
            return proto + " = np.empty({shape})".format(shape=shape)
        else:
            return proto + " = 0"

    def _call_arg(self, arg):
        if arg.dimensions:
            t = arg.get_datatype('c')
            return "<{0}*> {1}.data".format(t, arg.name)
        elif isinstance(arg, ResultBase):
            return "&{0}".format(arg.name)
        else:
            return str(arg.name)

register_wrapper('Cython', CythonCodeWrapper)
