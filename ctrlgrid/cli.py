"""Command line entry point.

Placeholder so that the `ctrlgrid` script declared in pyproject.toml resolves.
The real CLI — arguments, overrides, interactive preset picker — arrives with
milestone M1 (§ 11 and § 14 of the specification).
"""

import sys


def main() -> int:
    sys.stderr.write(
        "ctrlgrid is not implemented yet.\n"
        "The design is complete; see pflichtenheft-vorlagengenerator.md "
        "and start at milestone M1.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
