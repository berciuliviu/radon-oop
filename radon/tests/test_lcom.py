import unittest
from radon.visitors import analyze_lcom


class TestLCOM(unittest.TestCase):
    def test_lcom_calculation(self):
        source_code = """
class MyClass:
    def __init__(self):
        self.a = 1
        self.b = 2

    def method_one(self):
        return self.a + 1

    def method_two(self):
        return self.b + 2

    def method_three(self):
        return 3
"""
        lcom_results = analyze_lcom(source_code)
        self.assertIn("MyClass", lcom_results)
        self.assertEqual(lcom_results["MyClass"], 2)


if __name__ == "__main__":
    unittest.main()
