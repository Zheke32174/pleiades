# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Verification
import ast
import sys
import os

def validate_dir(path):
    print(f"Validating AST for {path}...")
    errors = 0
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith(".py"):
                file_path = os.path.join(root, f)
                try:
                    with open(file_path, "r") as source:
                        ast.parse(source.read()) 
                except Exception as e:
                    print(f"  FAILED: {file_path} - {e}")
                    errors += 1
    return errors

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    sys.exit(validate_dir(path))
