# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Verification
import unittest
import sys
import os

def run_all_tests():
    # Resolve relative to this script
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tests_dir = os.path.join(base_dir, 'tests')
    
    loader = unittest.TestLoader()
    suite = loader.discover(tests_dir, pattern='test_*.py')
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    sys.exit(not result.wasSuccessful())

if __name__ == "__main__":
    run_all_tests()
