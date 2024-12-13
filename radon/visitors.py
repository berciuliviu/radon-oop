"""This module contains the ComplexityVisitor class which is where all the
analysis concerning Cyclomatic Complexity is done. There is also the class
HalsteadVisitor, that counts Halstead metrics."""

import ast
import collections
import operator
import pprint

# Helper functions to use in combination with map()
GET_COMPLEXITY = operator.attrgetter("complexity")
GET_REAL_COMPLEXITY = operator.attrgetter("real_complexity")
NAMES_GETTER = operator.attrgetter("name", "asname")
GET_ENDLINE = operator.attrgetter("endline")

BaseFunc = collections.namedtuple(
    "Function",
    [
        "name",
        "lineno",
        "col_offset",
        "endline",
        "is_method",
        "classname",
        "closures",
        "complexity",
    ],
)
BaseClass = collections.namedtuple(
    "Class",
    [
        "name",
        "lineno",
        "col_offset",
        "endline",
        "methods",
        "inner_classes",
        "real_complexity",
    ],
)


def code2ast(source):
    """Convert a string object into an AST object.

    This function is retained for backwards compatibility, but it no longer
    attempts any conversions. It's equivalent to a call to ``ast.parse``.
    """
    return ast.parse(source)


class Function(BaseFunc):
    """Object representing a function block."""

    @property
    def letter(self):
        """The letter representing the function. It is `M` if the function is
        actually a method, `F` otherwise.
        """
        return "M" if self.is_method else "F"

    @property
    def fullname(self):
        """The full name of the function. If it is a method, then the full name
        is:
                {class name}.{method name}
        Otherwise it is just the function name.
        """
        if self.classname is None:
            return self.name
        return "{0}.{1}".format(self.classname, self.name)

    def __str__(self):
        """String representation of a function block."""
        return "{0} {1}:{2}->{3} {4} - {5}".format(
            self.letter,
            self.lineno,
            self.col_offset,
            self.endline,
            self.fullname,
            self.complexity,
        )


class Class(BaseClass):
    """Object representing a class block."""

    letter = "C"

    @property
    def fullname(self):
        """The full name of the class. It is just its name. This attribute
        exists for consistency (see :data:`Function.fullname`).
        """
        return self.name

    @property
    def complexity(self):
        """The average complexity of the class. It corresponds to the average
        complexity of its methods plus one.
        """
        if not self.methods:
            return self.real_complexity
        methods = len(self.methods)
        return int(self.real_complexity / float(methods)) + (methods > 1)

    def __str__(self):
        """String representation of a class block."""
        return "{0} {1}:{2}->{3} {4} - {5}".format(
            self.letter,
            self.lineno,
            self.col_offset,
            self.endline,
            self.name,
            self.complexity,
        )


class CodeVisitor(ast.NodeVisitor):
    """Base class for every NodeVisitors in `radon.visitors`. It implements a
    couple utility class methods and a static method.
    """

    @staticmethod
    def get_name(obj):
        """Shorthand for ``obj.__class__.__name__``."""
        return obj.__class__.__name__

    @classmethod
    def from_code(cls, code, **kwargs):
        """Instantiate the class from source code (string object). The
        `**kwargs` are directly passed to the `ast.NodeVisitor` constructor.
        """
        return cls.from_ast(code2ast(code), **kwargs)

    @classmethod
    def from_ast(cls, ast_node, **kwargs):
        """Instantiate the class from an AST node. The `**kwargs` are
        directly passed to the `ast.NodeVisitor` constructor.
        """
        visitor = cls(**kwargs)
        visitor.visit(ast_node)
        return visitor


class ComplexityVisitor(CodeVisitor):
    """A visitor that keeps track of the cyclomatic complexity of
    the elements.

    :param to_method: If True, every function is treated as a method. In this
        case the *classname* parameter is used as class name.
    :param classname: Name of parent class.
    :param off: If True, the starting value for the complexity is set to 1,
        otherwise to 0.
    """

    def __init__(self, to_method=False, classname=None, off=True, no_assert=False):
        self.off = off
        self.complexity = 1 if off else 0
        self.functions = []
        self.classes = []
        self.to_method = to_method
        self.classname = classname
        self.no_assert = no_assert
        self._max_line = float("-inf")

    @property
    def functions_complexity(self):
        """The total complexity from all functions (i.e. the total number of
        decision points + 1).

        This is *not* the sum of all the complexity from the functions. Rather,
        it's the complexity of the code *inside* all the functions.
        """
        return sum(map(GET_COMPLEXITY, self.functions)) - len(self.functions)

    @property
    def classes_complexity(self):
        """The total complexity from all classes (i.e. the total number of
        decision points + 1).
        """
        return sum(map(GET_REAL_COMPLEXITY, self.classes)) - len(self.classes)

    @property
    def total_complexity(self):
        """The total complexity. Computed adding up the visitor complexity, the
        functions complexity, and the classes complexity.
        """
        return (
            self.complexity
            + self.functions_complexity
            + self.classes_complexity
            + (not self.off)
        )

    @property
    def blocks(self):
        """All the blocks visited. These include: all the functions, the
        classes and their methods. The returned list is not sorted.
        """
        blocks = []
        blocks.extend(self.functions)
        for cls in self.classes:
            blocks.append(cls)
            blocks.extend(cls.methods)
        return blocks

    @property
    def max_line(self):
        """The maximum line number among the analyzed lines."""
        return self._max_line

    @max_line.setter
    def max_line(self, value):
        """The maximum line number among the analyzed lines."""
        if value > self._max_line:
            self._max_line = value

    def generic_visit(self, node):
        """Main entry point for the visitor."""
        # Get the name of the class
        name = self.get_name(node)
        # Check for a lineno attribute
        if hasattr(node, "lineno"):
            self.max_line = node.lineno
        # The Try/Except block is counted as the number of handlers
        # plus the `else` block.
        # In Python 3.3 the TryExcept and TryFinally nodes have been merged
        # into a single node: Try
        if name in ("Try", "TryExcept"):
            self.complexity += len(node.handlers) + bool(node.orelse)
        elif name == "BoolOp":
            self.complexity += len(node.values) - 1
        # Ifs, with and assert statements count all as 1.
        # Note: Lambda functions are not counted anymore, see #68
        elif name in ("If", "IfExp"):
            self.complexity += 1
        elif name == "Match":
            # check if _ (else) used
            contain_underscore = any(
                (
                    case
                    for case in node.cases
                    if getattr(case.pattern, "pattern", False) is None
                )
            )
            # Max used for case when match contain only _ (else)
            self.complexity += max(0, len(node.cases) - contain_underscore)
        # The For and While blocks count as 1 plus the `else` block.
        elif name in ("For", "While", "AsyncFor"):
            self.complexity += bool(node.orelse) + 1
        # List, set, dict comprehensions and generator exps count as 1 plus
        # the `if` statement.
        elif name == "comprehension":
            self.complexity += len(node.ifs) + 1

        super(ComplexityVisitor, self).generic_visit(node)

    def visit_Assert(self, node):
        """When visiting `assert` statements, the complexity is increased only
        if the `no_assert` attribute is `False`.
        """
        self.complexity += not self.no_assert

    def visit_AsyncFunctionDef(self, node):
        """Async function definition is the same thing as the synchronous
        one.
        """
        self.visit_FunctionDef(node)

    def visit_FunctionDef(self, node):
        """When visiting functions a new visitor is created to recursively
        analyze the function's body.
        """
        # The complexity of a function is computed taking into account
        # the following factors: number of decorators, the complexity
        # the function's body and the number of closures (which count
        # double).
        closures = []
        body_complexity = 1
        for child in node.body:
            visitor = ComplexityVisitor(off=False, no_assert=self.no_assert)
            visitor.visit(child)
            closures.extend(visitor.functions)
            # Add general complexity but not closures' complexity, see #68
            body_complexity += visitor.complexity

        func = Function(
            node.name,
            node.lineno,
            node.col_offset,
            max(node.lineno, visitor.max_line),
            self.to_method,
            self.classname,
            closures,
            body_complexity,
        )
        self.functions.append(func)

    def visit_ClassDef(self, node):
        """When visiting classes a new visitor is created to recursively
        analyze the class' body and methods.
        """
        # The complexity of a class is computed taking into account
        # the following factors: number of decorators and the complexity
        # of the class' body (which is the sum of all the complexities).
        methods = []
        # According to Cyclomatic Complexity definition it has to start off
        # from 1.
        body_complexity = 1
        classname = node.name
        visitors_max_lines = [node.lineno]
        inner_classes = []
        for child in node.body:
            visitor = ComplexityVisitor(
                True, classname, off=False, no_assert=self.no_assert
            )
            visitor.visit(child)
            methods.extend(visitor.functions)
            body_complexity += (
                visitor.complexity
                + visitor.functions_complexity
                + len(visitor.functions)
            )
            visitors_max_lines.append(visitor.max_line)
            inner_classes.extend(visitor.classes)

        cls = Class(
            classname,
            node.lineno,
            node.col_offset,
            max(visitors_max_lines + list(map(GET_ENDLINE, methods))),
            methods,
            inner_classes,
            body_complexity,
        )
        self.classes.append(cls)


class HalsteadVisitor(CodeVisitor):
    """Visitor that keeps track of operators and operands, in order to compute
    Halstead metrics (see :func:`radon.metrics.h_visit`).
    """

    # As of Python 3.8 Num/Str/Bytes/NameConstat
    # are now in a common node Constant.
    types = {
        "Num": "n",
        "Name": "id",
        "Attribute": "attr",
        "Constant": "value",
    }

    def __init__(self, context=None):
        """*context* is a string used to keep track the analysis' context."""
        self.operators_seen = set()
        self.operands_seen = set()
        self.operators = 0
        self.operands = 0
        self.context = context

        # A new visitor is spawned for every scanned function.
        self.function_visitors = []

    @property
    def distinct_operators(self):
        """The number of distinct operators."""
        return len(self.operators_seen)

    @property
    def distinct_operands(self):
        """The number of distinct operands."""
        return len(self.operands_seen)

    def dispatch(meth):
        """This decorator does all the hard work needed for every node.

        The decorated method must return a tuple of 4 elements:

            * the number of operators
            * the number of operands
            * the operators seen (a sequence)
            * the operands seen (a sequence)
        """

        def aux(self, node):
            """Actual function that updates the stats."""
            results = meth(self, node)
            self.operators += results[0]
            self.operands += results[1]
            self.operators_seen.update(results[2])
            for operand in results[3]:
                new_operand = getattr(
                    operand, self.types.get(type(operand), ""), operand
                )
                name = self.get_name(operand)
                new_operand = getattr(operand, self.types.get(name, ""), operand)

                self.operands_seen.add((self.context, new_operand))
            # Now dispatch to children
            super(HalsteadVisitor, self).generic_visit(node)

        return aux

    @dispatch
    def visit_BinOp(self, node):
        """A binary operator."""
        return (1, 2, (self.get_name(node.op),), (node.left, node.right))

    @dispatch
    def visit_UnaryOp(self, node):
        """A unary operator."""
        return (1, 1, (self.get_name(node.op),), (node.operand,))

    @dispatch
    def visit_BoolOp(self, node):
        """A boolean operator."""
        return (1, len(node.values), (self.get_name(node.op),), node.values)

    @dispatch
    def visit_AugAssign(self, node):
        """An augmented assign (contains an operator)."""
        return (1, 2, (self.get_name(node.op),), (node.target, node.value))

    @dispatch
    def visit_Compare(self, node):
        """A comparison."""
        return (
            len(node.ops),
            len(node.comparators) + 1,
            map(self.get_name, node.ops),
            node.comparators + [node.left],
        )

    def visit_FunctionDef(self, node):
        """When visiting functions, another visitor is created to recursively
        analyze the function's body. We also track information on the function
        itself.
        """
        func_visitor = HalsteadVisitor(context=node.name)

        for child in node.body:
            visitor = HalsteadVisitor.from_ast(child, context=node.name)
            self.operators += visitor.operators
            self.operands += visitor.operands
            self.operators_seen.update(visitor.operators_seen)
            self.operands_seen.update(visitor.operands_seen)

            func_visitor.operators += visitor.operators
            func_visitor.operands += visitor.operands
            func_visitor.operators_seen.update(visitor.operators_seen)
            func_visitor.operands_seen.update(visitor.operands_seen)

        # Save the visited function visitor for later reference.
        self.function_visitors.append(func_visitor)

    def visit_AsyncFunctionDef(self, node):
        """Async functions are similar to standard functions, so treat them as
        such.
        """
        self.visit_FunctionDef(node)


import ast


class AllClassesVisitor(ast.NodeVisitor):
    def __init__(self):
        self.classes = []

    def visit_ClassDef(self, node):
        self.classes.append(node.name)
        self.generic_visit(node)


class LCOMVisitor(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self.class_lcoms = {}

    def visit_ClassDef(self, node):
        class_name = node.name
        method_fields = {}
        methods = []

        for body_item in node.body:
            if isinstance(body_item, ast.FunctionDef):
                method_name = body_item.name
                # if method_name.startswith("__") and method_name.endswith("__"):
                #     continue  # Optionally skip special methods
                methods.append(method_name)

                method_visitor = MethodFieldVisitor()
                method_visitor.visit(body_item)
                method_fields[method_name] = method_visitor.fields_accessed

        lcom = self.calculate_lcom(method_fields, methods)
        self.class_lcoms[class_name] = lcom

    def calculate_lcom(self, method_fields, methods):
        num_methods = len(methods)
        if num_methods < 2:
            return 0

        P = 0
        Q = 0

        for i in range(num_methods):
            for j in range(i + 1, num_methods):
                fields_i = method_fields[methods[i]]
                fields_j = method_fields[methods[j]]

                if fields_i and fields_j:
                    if fields_i.isdisjoint(fields_j):
                        P += 1
                    else:
                        Q += 1
                else:
                    P += 1

        if P > Q:
            lcom = P - Q
        else:
            lcom = 0

        return lcom


class MethodFieldVisitor(ast.NodeVisitor):
    def __init__(self):
        self.fields_accessed = set()

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            self.fields_accessed.add(node.attr)
        self.generic_visit(node)


def analyze_lcom(source_code):
    tree = ast.parse(source_code)
    visitor = LCOMVisitor()
    visitor.visit(tree)
    return visitor.class_lcoms


import ast
import builtins


class CBOVisitor(ast.NodeVisitor):
    """
    AST Visitor that computes the Coupling Between Object classes (CBO)
    metric for classes in Python code, resolving import names.
    """

    def __init__(self, all_classes):
        super().__init__()
        self.class_couplings = {}  # {class_name: set of coupled class names}
        self.current_class = None  # Name of the class currently being visited
        self.classes = set(all_classes)  # Set of all class names defined in the code
        self.imported_names = {}  # Mapping of imported names to their full paths
        self.standard_lib_classes = self.get_standard_lib_classes()
        self.self_attributes = {}  # {class_name: {attribute_name: class_name}}

    def split_couplings_and_leave_only_class_names(self):
        for class_name, couplings in self.class_couplings.items():
            self.class_couplings[class_name] = set(
                [self.get_class_name(coupling) for coupling in couplings]
            )

    def get_class_name(self, coupling):
        parts = coupling.split(".")

        if len(parts) > 1:
            for part in parts:
                if self.is_class_name(part):
                    return part

        return coupling

    def get_standard_lib_classes(self):
        # Get a set of built-in class names
        classes = {
            name for name in dir(builtins) if isinstance(getattr(builtins, name), type)
        }

        classes.remove("super")
        return classes

    def visit_Module(self, node):
        # Collect all class names defined in the module and process imports
        for body_item in node.body:
            if isinstance(body_item, ast.ClassDef):
                self.classes.add(body_item.name)
            elif isinstance(body_item, (ast.Import, ast.ImportFrom)):
                self.visit(body_item)
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.name  # e.g., 'json'
            asname = alias.asname or alias.name  # e.g., 'json'
            self.imported_names[asname] = name  # {'json': 'json'}

    def visit_ImportFrom(self, node):
        module = node.module  # e.g., 'os.path'
        for alias in node.names:
            name = alias.name  # e.g., 'join'
            asname = alias.asname or alias.name  # e.g., 'join'
            full_name = f"{module}.{name}" if module else name  # 'os.path.join'
            self.imported_names[asname] = full_name  # {'join': 'os.path.join'}

    def visit_ClassDef(self, node):
        self.current_class = node.name
        self.class_couplings[self.current_class] = set()
        self.self_attributes[self.current_class] = {}
        # Handle InheritsFrom coupling
        for base in node.bases:
            base_name = self.get_full_name(base)
            if self.is_class_name(base_name):
                self.add_coupling(base_name)
        self.generic_visit(node)
        self.current_class = None

    def visit_FunctionDef(self, node):
        if self.current_class:
            # # Handle parameters and return type annotations
            for arg in node.args.args:
                if arg.annotation:
                    type_name = self.get_full_name(arg.annotation)
                    if self.is_class_name(type_name):
                        self.add_coupling(type_name)
            if node.returns:
                return_type = self.get_full_name(node.returns)
                if self.is_class_name(return_type):
                    self.add_coupling(return_type)
        self.generic_visit(node)

    def visit_Assign(self, node):
        if self.current_class:
            # Handle assignments to self attributes
            for target in node.targets:
                if isinstance(target, ast.Attribute) and self.is_self(target.value):
                    attr_name = target.attr
                    assigned_class = self.get_assigned_class(node.value)
                    if self.is_class_name(assigned_class):
                        self.self_attributes[self.current_class][
                            attr_name
                        ] = assigned_class
                        self.add_coupling(assigned_class)
            self.generic_visit(node)
        else:
            self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if self.current_class:
            # Handle annotated assignments (variable annotations)
            if isinstance(node.target, ast.Attribute) and self.is_self(
                node.target.value
            ):
                # self attribute annotation
                attr_name = node.target.attr
                assigned_class = self.get_full_name(node.annotation)
                if assigned_class:
                    self.self_attributes[self.current_class][attr_name] = assigned_class
                    if self.is_class_name(assigned_class):
                        self.add_coupling(assigned_class)
            elif isinstance(node.target, ast.Name):
                # Class variable annotation
                var_name = node.target.id
                assigned_class = self.get_full_name(node.annotation)
                if assigned_class and self.is_class_name(assigned_class):
                    self.add_coupling(assigned_class)
            self.generic_visit(node)

    def visit_Call(self, node):
        if self.current_class:
            # Handle calls to class constructors and methods
            func_name = self.get_full_name(node.func)
            if self.is_class_name(func_name):
                self.add_coupling(func_name)
            self.generic_visit(node)
        else:
            self.generic_visit(node)

    def visit_Attribute(self, node):
        if self.current_class:
            # Handle accesses to attributes of self attributes
            if self.is_self_attribute(node.value):
                attr_class = self.get_self_attribute_class(node.value)
                if self.is_class_name(attr_class):
                    self.add_coupling(attr_class)
            self.generic_visit(node)
        else:
            self.generic_visit(node)

    def is_class_name(self, name):
        # Check if the name starts with a capital letter or is a standard lib class
        if name is None:
            return False
        name_parts = name.split(".")

        if (len(name_parts)) > 1:
            is_class = False
            for name_part in name_parts:
                is_class = (
                    name_part
                    and name_part != self.current_class
                    and (
                        name_part in self.standard_lib_classes
                        or name_part in self.classes
                    )
                )

                if is_class:
                    return True

        return (
            name
            and name != self.current_class
            and (name in self.standard_lib_classes or name in self.classes)
        )

    def add_coupling(self, class_name):
        self.class_couplings[self.current_class].add(class_name)

    def is_self(self, node):
        return isinstance(node, ast.Name) and node.id == "self"

    def is_self_attribute(self, node):
        return isinstance(node, ast.Attribute) and self.is_self(node.value)

    def get_self_attribute_class(self, node):
        attr_name = node.attr
        return self.self_attributes[self.current_class].get(attr_name)

    def get_assigned_class(self, node):
        # Determine the class being assigned
        if isinstance(node, ast.Call):
            func_name = self.get_full_name(node.func)
            return func_name
        elif isinstance(node, ast.Name):
            # Variable assigned, could be a class variable
            name = self.get_full_name(node)
            return name
        elif isinstance(node, ast.Attribute):
            return self.get_full_name(node)
        return None

    def get_full_name(self, node):
        # Resolve the full name, including imports
        if isinstance(node, ast.Name):
            name = node.id
            return self.imported_names.get(name, name)
        elif isinstance(node, ast.Subscript):
            # Handle subscripted types (e.g., List[int])
            return self.get_full_name(node.value)
        elif isinstance(node, ast.Attribute):
            value = self.get_full_name(node.value)
            return f"{value}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self.get_full_name(node.func)
        return None


def analyze_cbo(source_code, all_classes):
    """
    Analyze the CBO metric for all classes in the given source code.
    """
    tree = ast.parse(source_code)
    visitor = CBOVisitor(all_classes.classes)
    visitor.visit(tree)
    visitor.split_couplings_and_leave_only_class_names()
    class_cbo = {}
    for class_name, couplings in visitor.class_couplings.items():
        # The CBO value is the number of unique classes the class is coupled to
        cbo_value = len(couplings)
        class_cbo[class_name] = {"cbo": cbo_value, "coupled_classes": list(couplings)}
    return class_cbo  # Returns a dictionary {class_name: {'cbo': value, 'coupled_classes': [...]}}


def format_couplings(couplings):
    """
    Format the couplings dictionary into a string.
    """
    formatted = []
    for coupling in couplings:
        if len(coupling.split(".")) > 2:
            formatted.append(f"  {coupling}")
