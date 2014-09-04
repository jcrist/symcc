import sys

from symcc.wrappers.codewrapper import CodeWrapper, register_wrapper

__all__ = ["F2PyCodeWrapper"]


class F2PyCodeWrapper(CodeWrapper):
    """Wrapper that uses f2py"""

    @property
    def command(self):
        filename = self.filename + '.' + self.generator.code_extension
        args = ['-c', '-m', self.module_name, filename]
        command = [sys.executable, "-c", "import numpy.f2py as f2py2e;f2py2e.main()"]+args
        return command

    def _prepare_files(self, routine):
        pass

    @classmethod
    def _get_wrapped_function(cls, mod, name):
        return getattr(mod, name)

register_wrapper('F2Py', F2PyCodeWrapper)
