import sys
from string import Template

from symcc.wrappers.codewrapper import CodeWrapper, register_wrapper
from symcc.types.routines import (OutputArgument, InOutArgument)

__all__ = ["UfuncifyCodeWrapper"]


ufunc_top = Template("""\
#include "Python.h"
#include "numpy/ndarraytypes.h"
#include "numpy/ufuncobject.h"
#include "numpy/halffloat.h"

static PyMethodDef ${MODULE}Methods[] = {
        {NULL, NULL, 0, NULL}
};""")

ufunc_body = Template("""\
static void ${FUNCNAME}_ufunc(char *restrict*restrict args,
        npy_intp *restrict dimensions, npy_intp *restrict steps,
        void *restrict data)
{
    npy_intp i;
    npy_intp n = dimensions[0];
    ${DECLARE_ARGS}
    ${DECLARE_STEPS}
    for (i = 0; i < n; i++) {
        *((double *)out1) = ${FUNCNAME}(${CALL_ARGS});
        ${STEP_INCREMENTS}
    }
}
PyUFuncGenericFunction ${FUNCNAME}_funcs[1] = {&${FUNCNAME}_ufunc};
static char ${FUNCNAME}_types[${N_TYPES}] = ${TYPES}
static void *${FUNCNAME}_data[1] = {NULL};""")

ufunc_bottom = Template("""\
#if PY_VERSION_HEX >= 0x03000000
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "${MODULE}",
    NULL,
    -1,
    ${MODULE}Methods,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC PyInit_${MODULE}(void)
{
    PyObject *m, *d;
    ${FUNCTION_CREATION}
    m = PyModule_Create(&moduledef);
    if (!m) {
        return NULL;
    }
    import_array();
    import_umath();
    d = PyModule_GetDict(m);
    ${UFUNC_INIT}
    return m;
}
#else
PyMODINIT_FUNC init${MODULE}(void)
{
    PyObject *m, *d;
    ${FUNCTION_CREATION}
    m = Py_InitModule("${MODULE}", ${MODULE}Methods);
    if (m == NULL) {
        return;
    }
    import_array();
    import_umath();
    d = PyModule_GetDict(m);
    ${UFUNC_INIT}
}
#endif\
""")

ufunc_init_form = Template("""\
ufunc${IND} = PyUFunc_FromFuncAndData(${FUNCNAME}_funcs, ${FUNCNAME}_data, ${FUNCNAME}_types, 1, ${N_IN}, ${N_OUT},
            PyUFunc_None, "${MODULE}", ${DOCSTRING}, 0);
    PyDict_SetItemString(d, "${FUNCNAME}", ufunc${IND});
    Py_DECREF(ufunc${IND});""")

ufunc_setup = Template("""\
def configuration(parent_package='', top_path=None):
    import numpy
    from numpy.distutils.misc_util import Configuration

    config = Configuration('',
                           parent_package,
                           top_path)
    config.add_extension('${MODULE}',
        sources=['${FILENAME}.c'],
        extra_compile_args=['-std=c99'])
    return config

if __name__ == "__main__":
    from numpy.distutils.core import setup
    setup(configuration=configuration)""")

class UfuncifyCodeWrapper(CodeWrapper):
    """Wrapper for Ufuncify"""

    @property
    def command(self):
        command = [sys.executable, "setup.py", "build_ext", "--inplace"]
        return command

    def _prepare_files(self, routine):

        # C
        #codefilename = self.module_name + '.c'
        codefilename = self.filename + '.c'
        with open(codefilename, 'a') as f:
            self.dump_c([routine], f, self.filename)

        # setup.py
        with open('setup.py', 'w') as f:
            self.dump_setup(f)

    @classmethod
    def _get_wrapped_function(cls, mod, name):
        return getattr(mod, name)

    def dump_setup(self, f):
        setup = ufunc_setup.substitute(MODULE=self.module_name, FILENAME=self.filename)
        f.write(setup)

    def dump_c(self, routines, f, prefix):
        """Write a C file with python wrappers

        This file contains all the definitions of the routines in c code.

        Arguments
        ---------
        routines
            List of Routine instances
        f
            File-like object to write the file to
        prefix
            The filename prefix, used to name the imported module.
        """
        functions = []
        FUNCTION_CREATION = []
        UFUNC_INIT = []
        MODULE = self.module_name
        INCLUDE_FILE = "\"{0}.h\"".format(prefix)
        top = ufunc_top.substitute(INCLUDE_FILE=INCLUDE_FILE, MODULE=MODULE)
        for r_index, routine in enumerate(routines):
            NAME = routine.name

            # Partition the C function arguments into categories
            py_in, py_out = self._partition_args(routine.arguments)
            N_IN = len(py_in)
            N_OUT = 1

            # Declare Args
            form = "char *{0}{1} = args[{2}];"
            arg_decs = [form.format('in', i, i) for i in range(N_IN)]
            arg_decs.append(form.format('out', 1, N_IN))
            DECLARE_ARGS = '\n    '.join(arg_decs)

            # Declare Steps
            form = "npy_intp {0}{1}_step = steps[{2}];"
            step_decs = [form.format('in', i, i) for i in range(N_IN)]
            step_decs.append(form.format('out', 1, N_IN))
            DECLARE_STEPS = '\n    '.join(step_decs)

            # Call Args
            form = "*(double *)in{0}"
            CALL_ARGS = ', '.join([form.format(a) for a in range(N_IN)])

            # Step Increments
            form = "{0}{1} += {0}{1}_step;"
            step_incs = [form.format('in', i) for i in range(N_IN)]
            step_incs.append(form.format('out', 1))
            STEP_INCREMENTS = '\n        '.join(step_incs)

            # Types
            N_TYPES = N_IN + N_OUT
            TYPES = "{" + ', '.join(["NPY_DOUBLE"]*N_TYPES) + "};"

            # Docstring
            DOCSTRING = '"Placeholder Docstring"'

            # Function Creation
            FUNCTION_CREATION.append("PyObject *ufunc{0};".format(r_index))

            # Ufunc initialization
            UFUNC_INIT.append(ufunc_init_form.substitute(MODULE=MODULE,
                FUNCNAME=NAME, DOCSTRING=DOCSTRING, N_IN=N_IN, N_OUT=N_OUT,
                IND=r_index))

            functions.append(ufunc_body.substitute(MODULE=MODULE,
                    FUNCNAME=NAME, DECLARE_ARGS=DECLARE_ARGS, DECLARE_STEPS=DECLARE_STEPS,
                    CALL_ARGS=CALL_ARGS, STEP_INCREMENTS=STEP_INCREMENTS,
                    N_TYPES=N_TYPES, TYPES=TYPES))

        body = '\n\n'.join(functions)
        UFUNC_INIT = '\n    '.join(UFUNC_INIT)
        FUNCTION_CREATION = '\n    '.join(FUNCTION_CREATION)
        bottom = ufunc_bottom.substitute(MODULE=MODULE, UFUNC_INIT=UFUNC_INIT,
                FUNCTION_CREATION=FUNCTION_CREATION)
        text = [top, body, bottom]
        f.write('\n\n'.join(text))

    def _partition_args(self, args):
        """Group function arguments into categories."""
        py_in = []
        py_out = []
        for arg in args:
            if isinstance(arg, OutputArgument):
                if py_out:
                    raise ValueError("Ufuncify doesn't support multiple OutputArguments")
                py_out.append(arg)
            elif isinstance(arg, InOutArgument):
                raise ValueError("Ufuncify doesn't support InOutArguments")
            else:
                py_in.append(arg)
        return py_in, py_out

register_wrapper('ufuncify', UfuncifyCodeWrapper)
