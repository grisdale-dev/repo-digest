import sys


def main() -> None:
    from repo_digest.cli import main as cli_main

    sys.exit(cli_main())
