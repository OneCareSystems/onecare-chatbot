import subprocess
import sys


def run(tmp_path, content):
    f = tmp_path / "requirements.in"
    f.write_text(content)
    return subprocess.run(
        [sys.executable, "scripts/check_pins.py", str(f)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_pinned_passes(tmp_path):
    assert run(tmp_path, "Django==5.0.6\n--extra-index-url https://x\n").returncode == 0


def test_range_fails_and_names_package(tmp_path):
    r = run(tmp_path, "Django==5.0.6\nrequests>=2\n")
    assert r.returncode == 1 and "requests" in r.stdout and ">=2" in r.stdout


def test_bare_name_and_wildcard_fail(tmp_path):
    r = run(tmp_path, "numpy\nfoo==1.*\n")
    assert r.returncode == 1 and "numpy" in r.stdout and "foo" in r.stdout