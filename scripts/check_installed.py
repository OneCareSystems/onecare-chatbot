"""AC2: installed versions must equal the lock file. Usage: python scripts/check_installed.py requirements.txt"""
import re
import sys
from importlib.metadata import PackageNotFoundError, version


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


bad = []

with open(sys.argv[1], encoding="utf-8") as f:
    for line in f:
        line = line.split(" #")[0].strip().rstrip("\\").strip()
        if not line or line.startswith(("#", "-")) or "==" not in line:
            continue
        name, ver = re.split(r"==", line.split(";")[0].strip(), maxsplit=1)
        name = name.split("[")[0]
        try:
            got = version(norm(name))
        except PackageNotFoundError:
            got = None
        if got != ver.strip():
            bad.append(f"{name}: lock={ver.strip()} installed={got}")
print("\n".join(bad) if bad else "OK - installed versions match the lock file")
sys.exit(1 if bad else 0)