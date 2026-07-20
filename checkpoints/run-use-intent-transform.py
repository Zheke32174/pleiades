#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

script_path = Path(__file__).with_name("apply-use-intent-atomicity.py")
source = script_path.read_text(encoding="utf-8")
old = 'authority = authority[:-3] + tests + "\\n    }\\n}\\n"'
new = 'authority = authority.rsplit("\\n}", 1)[0] + tests + "\\n}\\n"'
if source.count(old) != 1:
    raise SystemExit("operation intent transformer tail expression changed unexpectedly")
source = source.replace(old, new, 1)
namespace = {
    "__file__": str(script_path),
    "__name__": "__main__",
}
exec(compile(source, str(script_path), "exec"), namespace)
