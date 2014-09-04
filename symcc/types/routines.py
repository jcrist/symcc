from __future__ import print_function, division


from sympy.core import Symbol, S, Expr, Tuple, Equality, C
from sympy.core.sympify import _sympify
from sympy.core.compatibility import is_sequence
from sympy.tensor import Idx, Indexed, IndexedBase
from sympy.matrices import MatrixSymbol, ImmutableMatrix, MatrixBase

__all__ = [
    # description of routines
    "Assignment", "AssignmentError", "Routine", "DataType",
    "default_datatypes", "get_default_datatype", "Argument", "InputArgument",
    "Result"]


class AssignmentError(Exception):
    """
    Raised if an assignment variable for a loop is missing.
    """
    pass


class Assignment(C.Relational):
    """
    Represents variable assignment for code generation.

    Parameters
    ----------
    lhs : Expr
        Sympy object representing the lhs of the expression. These should be
        singular objects, such as one would use in writing code. Notable types
        include Symbol, MatrixSymbol, MatrixElement, and Indexed. Types that
        subclass these types are also supported.

    rhs : Expr
        Sympy object representing the rhs of the expression. This can be any
        type, provided its shape corresponds to that of the lhs. For example,
        a Matrix type can be assigned to MatrixSymbol, but not to Symbol, as
        the dimensions will not align.

    Examples
    --------

    >>> from sympy import symbols, MatrixSymbol, Matrix
    >>> from sympy.printing.codeprinter import Assignment
    >>> x, y, z = symbols('x, y, z')
    >>> Assignment(x, y)
    x := y
    >>> Assignment(x, 0)
    x := 0
    >>> A = MatrixSymbol('A', 1, 3)
    >>> mat = Matrix([x, y, z]).T
    >>> Assignment(A, mat)
    A := Matrix([[x, y, z]])
    >>> Assignment(A[0, 1], x)
    A[0, 1] := x
    """

    rel_op = ':='
    __slots__ = []

    def __new__(cls, lhs, rhs=0, **assumptions):
        lhs = _sympify(lhs)
        rhs = _sympify(rhs)
        # Tuple of things that can be on the lhs of an assignment
        assignable = (C.Symbol, C.MatrixSymbol, C.MatrixElement, C.Indexed)
        if not isinstance(lhs, assignable):
            raise TypeError("Cannot assign to lhs of type %s." % type(lhs))
        # Indexed types implement shape, but don't define it until later. This
        # causes issues in assignment validation. For now, matrices are defined
        # as anything with a shape that is not an Indexed
        lhs_is_mat = hasattr(lhs, 'shape') and not isinstance(lhs, C.Indexed)
        rhs_is_mat = hasattr(rhs, 'shape') and not isinstance(rhs, C.Indexed)
        # If lhs and rhs have same structure, then this assignment is ok
        if lhs_is_mat:
            if not rhs_is_mat:
                raise ValueError("Cannot assign a scalar to a matrix.")
            elif lhs.shape != rhs.shape:
                raise ValueError("Dimensions of lhs and rhs don't align.")
        elif rhs_is_mat and not lhs_is_mat:
            raise ValueError("Cannot assign a matrix to a scalar.")
        return C.Relational.__new__(cls, lhs, rhs, **assumptions)


class Routine(object):
    """Generic description of an evaluation routine for a set of sympy expressions.

       A CodeGen class can translate instances of this class into C/Fortran/...
       code. The routine specification covers all the features present in these
       languages. The CodeGen part must raise an exception when certain features
       are not present in the target language. For example, multiple return
       values are possible in Python, but not in C or Fortran. Another example:
       Fortran and Python support complex numbers, while C does not.
    """
    def __init__(self, name, expr, argument_sequence=None):
        """Initialize a Routine instance.

        ``name``
            A string with the name of this routine in the generated code
        ``expr``
            The sympy expression that the Routine instance will represent.  If
            given a list or tuple of expressions, the routine will be
            considered to have multiple return values.
        ``argument_sequence``
            Optional list/tuple containing arguments for the routine in a
            preferred order.  If omitted, arguments will be ordered
            alphabetically, but with all input aguments first, and then output
            or in-out arguments.

        A decision about whether to use output arguments or return values,
        is made depending on the mathematical expressions.  For an expression
        of type Equality, the left hand side is made into an OutputArgument
        (or an InOutArgument if appropriate).  Else, the calculated
        expression is the return values of the routine.

        A tuple of exressions can be used to create a routine with both
        return value(s) and output argument(s).

        """
        arg_list = []

        if is_sequence(expr) and not isinstance(expr, MatrixBase):
            if not expr:
                raise ValueError("No expression given")
            expressions = Tuple(*expr)
        else:
            expressions = Tuple(expr)

        # local variables
        local_vars = set([i.label for i in expressions.atoms(Idx)])

        # symbols that should be arguments
        symbols = expressions.free_symbols - local_vars

        # Decide whether to use output argument or return value
        return_val = []
        output_args = []
        for expr in expressions:
            if isinstance(expr, Equality):
                out_arg = expr.lhs
                expr = expr.rhs
                if isinstance(out_arg, Indexed):
                    dims = tuple([ (S.Zero, dim - 1) for dim in out_arg.shape])
                    symbol = out_arg.base.label
                elif isinstance(out_arg, Symbol):
                    dims = []
                    symbol = out_arg
                elif isinstance(out_arg, MatrixSymbol):
                    dims = tuple([ (S.Zero, dim - 1) for dim in out_arg.shape])
                    symbol = out_arg
                else:
                    raise ValueError("Only Indexed, Symbol, or MatrixSymbol "
                                       "can define output arguments.")

                if expr.has(symbol):
                    output_args.append(
                        InOutArgument(symbol, out_arg, expr, dimensions=dims))
                else:
                    output_args.append(OutputArgument(
                        symbol, out_arg, expr, dimensions=dims))

                # avoid duplicate arguments
                symbols.remove(symbol)
            elif isinstance(expr, ImmutableMatrix):
                # Create a "dummy" MatrixSymbol to use as the Output arg
                out_arg = MatrixSymbol('out_%s' % abs(hash(expr)), *expr.shape)
                dims = tuple([(S.Zero, dim - 1) for dim in out_arg.shape])
                output_args.append(OutputArgument(out_arg, out_arg, expr,
                        dimensions=dims))
            else:
                return_val.append(Result(expr))

        # setup input argument list
        array_symbols = {}
        for array in expressions.atoms(Indexed):
            array_symbols[array.base.label] = array
        for array in expressions.atoms(MatrixSymbol):
            array_symbols[array] = array

        for symbol in sorted(symbols, key=str):
            if symbol in array_symbols:
                dims = []
                array = array_symbols[symbol]
                for dim in array.shape:
                    dims.append((S.Zero, dim - 1))
                metadata = {'dimensions': dims}
            else:
                metadata = {}

            arg_list.append(InputArgument(symbol, **metadata))

        output_args.sort(key=lambda x: str(x.name))
        arg_list.extend(output_args)

        if argument_sequence is not None:
            # if the user has supplied IndexedBase instances, we'll accept that
            new_sequence = []
            for arg in argument_sequence:
                if isinstance(arg, IndexedBase):
                    new_sequence.append(arg.label)
                else:
                    new_sequence.append(arg)
            argument_sequence = new_sequence

            missing = [x for x in arg_list if x.name not in argument_sequence]
            if missing:
                raise ValueError("Argument list didn't specify: %s" %
                        ", ".join([str(m.name) for m in missing]), missing)

            # create redundant arguments to produce the requested sequence
            name_arg_dict = dict([(x.name, x) for x in arg_list])
            new_args = []
            for symbol in argument_sequence:
                try:
                    new_args.append(name_arg_dict[symbol])
                except KeyError:
                    new_args.append(InputArgument(symbol))
            arg_list = new_args

        self.name = name
        self.arguments = arg_list
        self.results = return_val
        self.local_vars = local_vars

    @property
    def variables(self):
        """Returns a set containing all variables possibly used in this routine.

        For routines with unnamed return values, the dummies that may or may
        not be used will be included in the set.
        """
        v = set(self.local_vars)
        for arg in self.arguments:
            v.add(arg.name)
        for res in self.results:
            v.add(res.result_var)
        return v

    @property
    def result_variables(self):
        """Returns a list of OutputArgument, InOutArgument and Result.

        If return values are present, they are at the end ot the list.
        """
        args = [arg for arg in self.arguments if isinstance(
            arg, (OutputArgument, InOutArgument))]
        args.extend(self.results)
        return args


class DataType(object):
    """Holds strings for a certain datatype in different programming languages."""
    def __init__(self, cname, fname, pyname):
        self.cname = cname
        self.fname = fname
        self.pyname = pyname


default_datatypes = {
    "int": DataType("int", "INTEGER*4", "int"),
    "float": DataType("double", "REAL*8", "float")
}


def get_default_datatype(expr):
    """Derives a decent data type based on the assumptions on the expression."""
    if expr.is_integer:
        return default_datatypes["int"]
    elif isinstance(expr, MatrixBase):
        for element in expr:
            if not element.is_integer:
                return(default_datatypes["float"])
        return default_datatypes["int"]
    else:
        return default_datatypes["float"]


class Variable(object):
    """Represents a typed variable."""

    def __init__(self, name, datatype=None, dimensions=None, precision=None):
        """Initializes a Variable instance

           name  --  must be of class Symbol or MatrixSymbol
           datatype  --  When not given, the data type will be guessed based
                         on the assumptions on the symbol argument.
           dimension  --  If present, the argument is interpreted as an array.
                          Dimensions must be a sequence containing tuples, i.e.
                          (lower, upper) bounds for each index of the array
           precision  --  FIXME
        """
        if not isinstance(name, (Symbol, MatrixSymbol)):
            raise TypeError("The first argument must be a sympy symbol.")
        if datatype is None:
            datatype = get_default_datatype(name)
        elif not isinstance(datatype, DataType):
            raise TypeError("The (optional) `datatype' argument must be an instance of the DataType class.")
        if dimensions and not isinstance(dimensions, (tuple, list)):
            raise TypeError(
                "The dimension argument must be a sequence of tuples")

        self._name = name
        self._datatype = {
            'C': datatype.cname,
            'FORTRAN': datatype.fname,
            'PYTHON': datatype.pyname
        }
        self.dimensions = dimensions
        self.precision = precision

    @property
    def name(self):
        return self._name

    def get_datatype(self, language):
        """Returns the datatype string for the requested langage.

            >>> from sympy import Symbol
            >>> from sympy.utilities.codegen import Variable
            >>> x = Variable(Symbol('x'))
            >>> x.get_datatype('c')
            'double'
            >>> x.get_datatype('fortran')
            'REAL*8'
        """
        try:
            return self._datatype[language.upper()]
        except KeyError:
            raise ValueError("Has datatypes for languages: %s" %
                    ", ".join(self._datatype))


class Argument(Variable):
    """An abstract Argument data structure: a name and a data type.

       This structure is refined in the descendants below.
    """

    def __init__(self, name, datatype=None, dimensions=None, precision=None):
        """ See docstring of Variable.__init__
        """

        Variable.__init__(self, name, datatype, dimensions, precision)


class InputArgument(Argument):
    pass


class ResultBase(object):
    """Base class for all ``outgoing'' information from a routine

       Objects of this class stores a sympy expression, and a sympy object
       representing a result variable that will be used in the generated code
       only if necessary.
   """
    def __init__(self, expr, result_var):
        self.expr = expr
        self.result_var = result_var


class OutputArgument(Argument, ResultBase):
    """OutputArgument are always initialized in the routine
    """
    def __init__(self, name, result_var, expr, datatype=None, dimensions=None, precision=None):
        """ See docstring of Variable.__init__
        """
        Argument.__init__(self, name, datatype, dimensions, precision)
        ResultBase.__init__(self, expr, result_var)


class InOutArgument(Argument, ResultBase):
    """InOutArgument are never initialized in the routine
    """

    def __init__(self, name, result_var, expr, datatype=None, dimensions=None, precision=None):
        """ See docstring of Variable.__init__
        """
        if not datatype:
            datatype = get_default_datatype(expr)
        Argument.__init__(self, name, datatype, dimensions, precision)
        ResultBase.__init__(self, expr, result_var)


class Result(ResultBase):
    """An expression for a scalar return value.

       The name result is used to avoid conflicts with the reserved word
       'return' in the python language. It is also shorter than ReturnValue.

    """

    def __init__(self, expr, datatype=None, precision=None):
        """Initialize a (scalar) return value.

           The second argument is optional. When not given, the data type will
           be guessed based on the assumptions on the expression argument.
        """
        if not isinstance(expr, Expr):
            raise TypeError("The first argument must be a sympy expression.")

        temp_var = Variable(Symbol('result_%s' % abs(hash(expr))),
                datatype=datatype, dimensions=None, precision=precision)
        ResultBase.__init__(self, expr, temp_var.name)
        self._temp_variable = temp_var

    def get_datatype(self, language):
        return self._temp_variable.get_datatype(language)
