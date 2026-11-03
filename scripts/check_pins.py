"""AC3: fail if any dependency in a requirements file is not pinned with ==.
Usage: python scripts/check_pins.py [files...]   (default: all requirements*.in / requirements*.txt)"""
import glob
import re
import sys

PINNED = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*"          # package name
    r"(\[[A-Za-z0-9,._-]+\])?"               # optional extras
    r"==[A-Za-z0-9][A-Za-z0-9.!+_-]*"        # exact version only (no *, no ranges)
    r"(\s*;.*)?$"                            # optional environment marker
)


def check(path):
    errors = []
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            line = raw.split(" #")[0].strip().rstrip("\\").strip()
            if not line or line.startswith(("#", "-")):
                continue                      # blanks, comments, options (-r, -c, --extra-index-url)
            if not PINNED.match(line):
                name = re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0]
                spec = line[len(name):].strip() or "(no version)"
                errors.append(f"{path}:{n}: package '{name}' has invalid specifier '{spec}' - use ==x.y.z")
    return errors


def main(argv):
    files = argv or sorted(glob.glob("requirements*.in") + glob.glob("requirements*.txt"))
    if not files:
        print("No requirements files found.")
        return 1
    errors = [e for p in files for e in check(p)]
    print("\n".join(errors) if errors else f"OK - all packages pinned in: {', '.join(files)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))