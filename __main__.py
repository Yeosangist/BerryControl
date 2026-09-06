#!/usr/bin/env python3

if __package__ in {None, ""}:
    import os
    import sys

    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from strawberry_controller.main import main
else:
    from .main import main

if __name__ == "__main__":
    raise SystemExit(main())
