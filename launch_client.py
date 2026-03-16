"""Client launcher entrypoint for PyInstaller client build."""

import sys

from main import main


if __name__ == "__main__":
    if "--mode" not in sys.argv:
        sys.argv.extend(["--mode", "client"])
    main()
