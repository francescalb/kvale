import argparse
from pathlib import Path

from kvale.gui.app import KvaleApp


def main() -> None:
    parser = argparse.ArgumentParser(prog="kvale")
    parser.add_argument("path", nargs="?", help="Optional path to a pattern JSON file to open")
    args = parser.parse_args()

    initial_path = Path(args.path).expanduser() if args.path else None
    app = KvaleApp(initial_path=initial_path)
    app.run()


if __name__ == "__main__":
    main()
