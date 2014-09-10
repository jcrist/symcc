"""
Types used to represent a full function/module as an Abstract Syntax Tree.

Most types are small, and are merely used as tokens in the AST. A tree diagram
has been included below to illustrate the relationships between the AST types.


AST Type Tree
-------------

*Basic*
     |--->Assign      
     |--->AugAssign  
     |--->NativeOp  
     |           |--------------|
     |                          |--->AddOp
     |                          |--->SubOp
     |                          |--->MulOp
     |                          |--->DivOp
     |                          |--->ModOp
     |           *Singleton*----|
     |                    |
     |--->DataType        |
     |           |--------|--->NativeBool
     |                    |--->NativeInteger
     |                    |--->NativeFloat
     |                    |--->NativeDouble
     |                    |--->NativeVoid
     |
     |--->For
     |--->Result
     |         |--->ReturnResult
     |         |------------------------------|
     |                                        |--->InOutArgument
     |--->Variable                            |--->OutArgument
     |           |--->Argument----------------|
     |                       |
     |                       |--->InArgument
     |
     |--->Module
     |--->FunctionDef
     |--->Import
     |--->Declare
     |--->Return
"""

from __future__ import print_function, division


from sympy.core import Symbol, Tuple
from sympy.core.singleton import Singleton
from sympy.core.basic import Basic
from sympy.core.sympify import _sympify
from sympy.core.compatibility import with_metaclass
from sympy.tensor import Indexed
from sympy.matrices.expressions.matexpr import MatrixSymbol, MatrixElement
from sympy.utilities.iterables import iterable


class Assign(Basic):
    """Represents variable assignment for code generation.

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
    >>> from sympy.printing.codeprinter import Assign
    >>> x, y, z = symbols('x, y, z')
    >>> Assign(x, y)
    x := y
    >>> Assign(x, 0)
    x := 0
    >>> A = MatrixSymbol('A', 1, 3)
    >>> mat = Matrix([x, y, z]).T
    >>> Assign(A, mat)
    A := Matrix([[x, y, z]])
    >>> Assign(A[0, 1], x)
    A[0, 1] := x
    """

    def __new__(cls, lhs, rhs):
        lhs = _sympify(lhs)
        rhs = _sympify(rhs)
        # Tuple of things that can be on the lhs of an assignment
        assignable = (Symbol, MatrixSymbol, MatrixElement, Indexed)
        if not isinstance(lhs, assignable):
            raise TypeError("Cannot assign to lhs of type %s." % type(lhs))
        # Indexed types implement shape, but don't define it until later. This
        # causes issues in assignment validation. For now, matrices are defined
        # as anything with a shape that is not an Indexed
        lhs_is_mat = hasattr(lhs, 'shape') and not isinstance(lhs, Indexed)
        rhs_is_mat = hasattr(rhs, 'shape') and not isinstance(rhs, Indexed)
        # If lhs and rhs have same structure, then this assignment is ok
        if lhs_is_mat:
            if not rhs_is_mat:
                raise ValueError("Cannot assign a scalar to a matrix.")
            elif lhs.shape != rhs.shape:
                raise ValueError("Dimensions of lhs and rhs don't align.")
        elif rhs_is_mat and not lhs_is_mat:
            raise ValueError("Cannot assign a matrix to a scalar.")
        return Basic.__new__(cls, lhs, rhs)

    def _sympystr(self, printer):
        sstr = printer.doprint
        return '{0} := {1}'.format(sstr(self.lhs), sstr(self.rhs))

    @property
    def lhs(self):
        return self._args[0]

    @property
    def rhs(self):
        return self._args[1]


# The following are defined to be sympy approved nodes. If there is something
# smaller that could be used, that would be preferable. We only use them as
# tokens.


class NativeOp(with_metaclass(Singleton, Basic)):
    """Base type for native operands."""
    pass


class AddOp(NativeOp):
    _symbol = '+'


class SubOp(NativeOp):
    _symbol = '-'


class MulOp(NativeOp):
    _symbol = '*'


class DivOp(NativeOp):
    _symbol = '/'


class ModOp(NativeOp):
    _symbol = '%'


op_registry = {'+': AddOp(),
               '-': SubOp(),
               '*': MulOp(),
               '/': DivOp(),
               '%': ModOp()}


def operator(op):
    """Returns the operator singleton for the given operator"""

    if op.lower() not in op_registry:
        raise ValueError("Unrecognized operator " + op)
    return op_registry[op]


class AugAssign(Basic):
    """Represents augmented variable assignment for code generation.

    Parameters
    ----------
    lhs : Expr
        Sympy object representing the lhs of the expression. These should be
        singular objects, such as one would use in writing code. Notable types
        include Symbol, MatrixSymbol, MatrixElement, and Indexed. Types that
        subclass these types are also supported.

    op : NativeOp
        Operator (+, -, /, *, %).

    rhs : Expr
        Sympy object representing the rhs of the expression. This can be any
        type, provided its shape corresponds to that of the lhs. For example,
        a Matrix type can be assigned to MatrixSymbol, but not to Symbol, as
        the dimensions will not align.

    Examples
    --------

    >>> from sympy import symbols
    >>> from symcc.types.ast import AugAssign
    >>> x, y = symbols('x, y')
    >>> AugAssign(x, AddOp, y)
    x += y
    """

    def __new__(cls, lhs, op, rhs):
        lhs = _sympify(lhs)
        rhs = _sympify(rhs)
        # Tuple of things that can be on the lhs of an assignment
        assignable = (Symbol, MatrixSymbol, MatrixElement, Indexed)
        if not isinstance(lhs, assignable):
            raise TypeError("Cannot assign to lhs of type %s." % type(lhs))
        # Indexed types implement shape, but don't define it until later. This
        # causes issues in assignment validation. For now, matrices are defined
        # as anything with a shape that is not an Indexed
        lhs_is_mat = hasattr(lhs, 'shape') and not isinstance(lhs, Indexed)
        rhs_is_mat = hasattr(rhs, 'shape') and not isinstance(rhs, Indexed)
        # If lhs and rhs have same structure, then this assignment is ok
        if lhs_is_mat:
            if not rhs_is_mat:
                raise ValueError("Cannot assign a scalar to a matrix.")
            elif lhs.shape != rhs.shape:
                raise ValueError("Dimensions of lhs and rhs don't align.")
        elif rhs_is_mat and not lhs_is_mat:
            raise ValueError("Cannot assign a matrix to a scalar.")
        if isinstance(op, str):
            op = operator(op)
        elif op not in op_registry.values():
            raise TypeError("Unrecognized Operator")
        return Basic.__new__(cls, lhs, op, rhs)

    def _sympystr(self, printer):
        sstr = printer.doprint
        return '{0} {1}= {2}'.format(sstr(self.lhs), self.op._symbol,
                sstr(self.rhs))

    @property
    def lhs(self):
        return self._args[0]

    @property
    def op(self):
        return self._args[1]

    @property
    def rhs(self):
        return self._args[2]


class For(Basic):
    """Represents a 'for-loop' in the code.

    Expressions are of the form:
        "for target in iter:
            body..."

    Parameters
    ----------
    target : symbol
    iter : iterable
    body : sympy expr
    """
    
    def __new__(cls, target, iter, body):
        target = _sympify(target)
        if not iterable(iter):
            raise TypeError("iter must be an iterable")
        iter = _sympify(iter)
        if not iterable(body):
            raise TypeError("body must be an iterable")
        body = Tuple(*(_sympify(i) for i in body))
        return Basic.__new__(cls, target, iter, body)

    @property
    def target(self):
        return self._args[0]

    @property
    def iterable(self):
        return self._args[1]

    @property
    def body(self):
        return self._args[2]


# The following are defined to be sympy approved nodes. If there is something
# smaller that could be used, that would be preferable. We only use them as
# tokens.

class DataType(with_metaclass(Singleton, Basic)):
    """Base class representing native datatypes"""
    pass


class NativeBool(DataType):
    pass


class NativeInteger(DataType):
    pass


class NativeFloat(DataType):
    pass


class NativeDouble(DataType):
    pass


class NativeVoid(DataType):
    pass


dtype_registry = {'bool': NativeBool(),
                  'int': NativeInteger(),
                  'float': NativeFloat(),
                  'double': NativeDouble(),
                  'void': NativeVoid()}


def datatype(dtype):
    """Returns the datatype singleton for the given dtype"""

    if dtype.lower() not in dtype_registry:
        raise ValueError("Unrecognized datatype " + dtype)
    return dtype_registry[dtype]


class Variable(Basic):
    """Represents a typed variable.
    
    Parameters
    ----------
    name : Symbol, MatrixSymbol
        The sympy object the variable represents.
    dtype : str, DataType
        The type of the variable. Can be either a DataType, or a str (bool,
        int, float, double).
    """

    def __new__(cls, name, dtype):
        if not isinstance(name, (Symbol, MatrixSymbol)):
            raise TypeError("Only Symbols and MatrixSymbols can be Variables.")
        if isinstance(dtype, str):
            dtype = datatype(dtype)
        elif not isinstance(dtype, DataType):
            raise TypeError("datatype must be an instance of DataType.")
        return Basic.__new__(cls, name, dtype)

    @property
    def name(self):
        return self._args[0]

    @property
    def dtype(self):
        return self._args[1]


class Argument(Variable):
    """An abstract Argument data structure"""
    pass


class Result(Basic):
    """Base class for all outgoing information from a routine."""
    pass


class ReturnResult(Result):
    """Represents a result provided via a ``Return``"""

    def __new__(cls, dtype):
        if isinstance(dtype, str):
            dtype = datatype(dtype)
        elif not isinstance(dtype, DataType):
            raise TypeError("datatype must be an instance of DataType.")
        return Basic.__new__(cls, dtype)

    @property
    def dtype(self):
        return self._args[0]


class InArgument(Argument):
    """Argument provided as input only."""
    pass


class OutArgument(Argument, Result):
    """OutputArgument are always initialized in the routine."""
    pass


class InOutArgument(Argument, Result):
    """InOutArgument are never initialized in the routine."""
    pass


class Module(Basic):
    """Represents a module-level object.

    Parameters
    ----------
    name : str
        The name of the module.
    body : iterable
        The elements inside the module.
    """

    def __new__(cls, name, body):
        if not isinstance(name, str):
            raise TypeError("Module name must be string")
        name = Symbol(name)
        # body
        if not iterable(body):
            raise TypeError("body must be an iterable")
        body = Tuple(*body)
        return Basic.__new__(cls, name, body)

    @property
    def name(self):
        return self._args[0]

    @property
    def body(self):
        return self._args[0]


class FunctionDef(Basic):
    """Represents a function definition.

    Parameters
    ----------
    name : str
        The name of the function.
    args : iterable
        The arguments to the function, of type Argument.
    body : iterable
        The body of the function.
    results : iterable
        The results of the function, of type Result.
    """

    def __new__(cls, name, args, body, results):
        # name
        if not isinstance(name, str):
            raise TypeError("Function name must be string")
        name = Symbol(name)
        # args
        if not iterable(args):
            raise TypeError("args must be an iterable")
        if not all(isinstance(a, Argument) for a in args):
            raise TypeError("All args must be of type Argument")
        args = Tuple(*args)
        # body
        if not iterable(body):
            raise TypeError("body must be an iterable")
        body = Tuple(*(_sympify(i) for i in body))
        # results
        if not iterable(results):
            raise TypeError("results must be an iterable")
        if not all(isinstance(i, Result) for i in results):
            raise TypeError("All results must be of type Result")
        results = Tuple(*results)
        return Basic.__new__(cls, name, args, body, results)

    @property
    def name(self):
        return self._args[0]

    @property
    def arguments(self):
        return self._args[1]

    @property
    def body(self):
        return self._args[2]

    @property
    def results(self):
        return self._args[3]


class Import(Basic):
    """Represents inclusion of dependencies in the code.

    Parameters
    ----------
    file_path : str
        The filepath of the module (i.e. header in C).
    func_name : str
        The name of the function to be imported.
    """
    def __new__(cls, file_path, func_name):
        file_path = Symbol(file_path)
        func_name = Symbol(func_name)
        return Basic.__new__(cls, file_path, func_name)

    @property
    def file_path(self):
        return self._args[0]

    @property
    def func_name(self):
        return self._args[1]


# TODO: Should Declare have an optional init value for each var?
class Declare(Basic):
    """Represents a variable declaration in the code.

    Parameters
    ----------
    variable(s)
        A single variable or an iterable of Variables. If iterable, all
        Variables must be of the same type.
    dtype : DataType
        The type for the declaration.
    """

    def __new__(cls, dtype, variables):
        if isinstance(variables, Variable):
            variables = [variables]
        for var in variables:
            if not isinstance(var, Variable):
                raise TypeError("var must be of type Variable")
            if var.dtype != dtype:
                raise ValueError("All variables must have the same dtype")
        variables = Tuple(*variables)
        return Basic.__new__(cls, dtype, variables)

    @property
    def dtype(self):
        return self._args[0]

    @property
    def variables(self):
        return self._args[1]


class Return(Basic):
    """Represents a function return in the code.

    Parameters
    ----------
    expr : sympy expr
        The expression to return
    """

    def __new__(cls, expr):
        expr = _sympify(expr)
        return Basic.__new__(cls, expr)

    @property
    def expr(self):
        return self._args[0]
