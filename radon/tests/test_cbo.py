import unittest
import ast

from radon.visitors import CBOVisitor

# Assuming CBOVisitor is defined as per the previous code snippet


class TestCBOVisitor(unittest.TestCase):
    def test_inherits_from(self):
        code = """
class BaseClass:
    pass

class DerivedClass(BaseClass):
    pass
"""
        tree = ast.parse(code)
        visitor = CBOVisitor()
        visitor.visit(tree)
        cbo = visitor.get_cbo()
        expected_cbo = {"BaseClass": 0, "DerivedClass": 1}
        self.assertEqual(cbo, expected_cbo)

    #     def test_invokes(self):
    #         code = """
    # class ClassA:
    #     def method_a(self):
    #         pass

    # class ClassB:
    #     def method_b(self):
    #         a = ClassA()
    #         a.method_a()
    # """
    #         tree = ast.parse(code)
    #         visitor = CBOVisitor()
    #         visitor.visit(tree)
    #         cbo = visitor.get_cbo()
    #         expected_cbo = {"ClassA": 0, "ClassB": 1}
    #         self.assertEqual(cbo, expected_cbo)

    #     def test_accesses(self):
    #         code = """
    # class ClassA:
    #     def __init__(self):
    #         self.value = 42

    # class ClassB:
    #     def method_b(self):
    #         a = ClassA()
    #         print(a.value)
    # """
    #         tree = ast.parse(code)
    #         visitor = CBOVisitor()
    #         visitor.visit(tree)
    #         cbo = visitor.get_cbo()
    #         expected_cbo = {"ClassA": 0, "ClassB": 1}
    #         self.assertEqual(cbo, expected_cbo)

    #     def test_is_parameter_of(self):
    #         code = """
    # class ClassA:
    #     pass

    # class ClassB:
    #     def method_b(self, param: ClassA):
    #         pass
    # """
    #         tree = ast.parse(code)
    #         visitor = CBOVisitor()
    #         visitor.visit(tree)
    #         cbo = visitor.get_cbo()
    #         expected_cbo = {"ClassA": 0, "ClassB": 1}
    #         self.assertEqual(cbo, expected_cbo)

    #     def test_is_of_type(self):
    #         code = """
    # class ClassA:
    #     pass

    # class ClassB:
    #     def method_b(self):
    #         var: ClassA = ClassA()
    # """
    #         tree = ast.parse(code)
    #         visitor = CBOVisitor()
    #         visitor.visit(tree)
    #         cbo = visitor.get_cbo()
    #         expected_cbo = {"ClassA": 0, "ClassB": 1}
    #         self.assertEqual(cbo, expected_cbo)

    def test_is_defined_in_terms_of(self):
        code = """
class ClassA:
    pass

class ClassB:
    a = ClassA()
"""
        tree = ast.parse(code)
        visitor = CBOVisitor()
        visitor.visit(tree)
        cbo = visitor.get_cbo()
        expected_cbo = {"ClassA": 0, "ClassB": 1}
        self.assertEqual(cbo, expected_cbo)

    def test_is_defined_in_terms_of2(self):
        code = """
class ClassA:
    pass

class ClassB:
    a = ClassA()

class ClassC:
    def __init__(self):
        self.b = ClassB()
"""
        tree = ast.parse(code)
        visitor = CBOVisitor()
        visitor.visit(tree)
        cbo = visitor.get_cbo()
        expected_cbo = {
            "ClassA": 0,
            "ClassB": 1,  # Depends on ClassA
            "ClassC": 1,  # Depends on ClassB
        }
        self.assertEqual(cbo, expected_cbo)


#     def test_combined(self):
#         code = """
# class ClassA:
#     def method_a(self):
#         pass

# class ClassB(ClassA):
#     def __init__(self, param: ClassA):
#         self.attr = param

#     def method_b(self):
#         self.attr.method_a()
#         var: ClassA = ClassA()
#         print(var.value)
# """
#         tree = ast.parse(code)
#         visitor = CBOVisitor()
#         visitor.visit(tree)
#         cbo = visitor.get_cbo()
#         expected_cbo = {"ClassA": 0, "ClassB": 1}
#         self.assertEqual(cbo, expected_cbo)


if __name__ == "__main__":
    unittest.main()
