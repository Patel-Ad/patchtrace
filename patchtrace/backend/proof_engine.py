"""Security Proof Engine: runs REAL tests before and after a patch and reports the evidence."""
import ast
import difflib
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = ROOT / "demo_app" / "app.py"
# The patched file lives OUTSIDE the project folder. If it lived inside, a server started
# with --reload would restart itself every time a patch is written and forget the result.
DATA_DIR = Path(tempfile.gettempdir()) / "patchtrace"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PATCHED = DATA_DIR / "patched_app.py"

_baseline = None  # the scan's real test run on the unchanged, vulnerable app


def _run_once(target_app: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / "result.xml"
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "-q", "--tb=short",
             "-p", "no:cacheprovider", f"--junitxml={xml_path}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            env={**os.environ, "TARGET_APP": str(target_app),
                 "PYTHONPATH": str(ROOT / "tests"), "PYTHONIOENCODING": "utf-8"},
        )
        tests = []
        if xml_path.exists():
            try:
                for case in ET.parse(xml_path).getroot().iter("testcase"):
                    bad = case.find("failure") is not None or case.find("error") is not None
                    tests.append({
                        "name": case.get("name"),
                        "group": "security" if "test_security" in case.get("classname", "") else "regression",
                        "status": "failed" if bad else "passed",
                    })
            except ET.ParseError:
                pass
    return {"tests": tests, "output": (proc.stdout + proc.stderr)[-3000:]}


def run_tests(target_app: Path) -> dict:
    """Run pytest against one app file and return each test's pass/fail result."""
    result = _run_once(target_app)
    if not result["tests"]:  # rare hiccup (a file lock, antivirus, sync tool): try once more
        time.sleep(0.8)
        result = _run_once(target_app)
    return result


def baseline(refresh: bool = False) -> dict:
    """Real test results for the original, vulnerable app (kept from the scan)."""
    global _baseline
    if refresh or not _baseline:
        run = run_tests(ORIGINAL)
        if run["tests"]:
            _baseline = run
        return run
    return _baseline


def verify(patched_code: str) -> dict:
    """Test the original app and the patched app, then decide if the fix is truly verified."""
    try:
        tree = ast.parse(patched_code)  # reject patches that are not valid Python
    except SyntaxError as e:
        return {"error": f"Patch is not valid Python: {e}"}
    if not any(isinstance(n, ast.FunctionDef) and n.name == "create_app" for n in ast.walk(tree)):
        return {"error": "Patch must keep the create_app() function so the tests can load it."}

    PATCHED.write_text(patched_code, encoding="utf-8")

    before = run_tests(ORIGINAL)
    if not before["tests"] and _baseline:
        before = _baseline  # reuse the scan's real run on the same, unchanged original file
    after = run_tests(PATCHED)

    for name, run in (("original", before), ("patched", after)):
        if not run["tests"]:
            return {"error": f"The tests could not run on the {name} app. pytest said:\n\n{run['output'][-900:]}"}

    sec = lambda r: [t for t in r["tests"] if t["group"] == "security"]
    reg = lambda r: [t for t in r["tests"] if t["group"] == "regression"]

    reproduced = any(t["status"] == "failed" for t in sec(before))
    fixed = bool(sec(after)) and all(t["status"] == "passed" for t in sec(after))
    regression_ok = bool(reg(after)) and all(t["status"] == "passed" for t in reg(after))

    diff = "".join(difflib.unified_diff(
        ORIGINAL.read_text(encoding="utf-8").splitlines(True),
        patched_code.splitlines(True),
        "app.py (original)",
        "app.py (patched)",
    ))
    return {
        "before": before,
        "after": after,
        "diff": diff,
        "reproduced_before": reproduced,
        "security_fixed": fixed,
        "regression_ok": regression_ok,
        "verdict": "VERIFIED" if (reproduced and fixed and regression_ok) else "NOT VERIFIED",
    }
