import argparse
from .data.validation import validate_csv


def main():
    parser = argparse.ArgumentParser(description="Marketing data validation")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("path")
    args = parser.parse_args()
    errors = validate_csv(args.path)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("PASS: weekly schema checks passed; model suitability is not assessed.")


if __name__ == "__main__":
    main()

