import json
import re
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Body, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Template

from backend import live_shop
from backend.ai_fix import propose_fix
from backend.proof_engine import DATA_DIR, ORIGINAL, PATCHED, ROOT, baseline, verify

STATE_FILE = DATA_DIR / "state.json"
KEYS = ("fix", "tested", "proof", "time")


@asynccontextmanager
async def lifespan(_app):
    live_shop.start(ORIGINAL, "vulnerable")  # the live shop starts with the bug in it
    yield
    live_shop.stop()


app = FastAPI(title="PatchTrace", lifespan=lifespan)
state: dict = {}

FINDING = {
    "title": "Broken Access Control (IDOR) on GET /orders/<id>",
    "severity": "High",
    "file": "demo_app/app.py",
    "plain_english": (
        "The server checks that you are logged in, but not that the order is yours. "
        "Any customer can read any other customer's order by changing the number in the URL."
    ),
    "why_it_matters": "Leaks private purchase data and can violate privacy laws.",
}


def _persist() -> None:
    """Save the important state to disk so a server restart or a second copy cannot lose it."""
    STATE_FILE.write_text(json.dumps({k: state[k] for k in KEYS if k in state}), encoding="utf-8")


def _sync() -> None:
    """Load the latest saved state from disk."""
    for k in KEYS:
        state.pop(k, None)
    try:
        state.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass


def make_bad_patch() -> str:
    """A deliberately wrong 'fix': it stops the leak by refusing EVERYONE, so normal use breaks."""
    code = ORIGINAL.read_text(encoding="utf-8")
    return re.sub(
        r"return jsonify\(dict\(order\)\)[^\n]*",
        'return jsonify(error="forbidden"), 403  # BAD PATCH: refuses everyone, even the owner',
        code,
        count=1,
    )


@app.post("/api/scan")
def scan():
    result = baseline(refresh=True)
    if not result["tests"]:
        return {"error": "The tests could not run. pytest said:\n\n" + result["output"][-900:]}
    failed = [t for t in result["tests"] if t["group"] == "security" and t["status"] == "failed"]
    state["finding"] = FINDING if failed else None
    return {
        "finding": state["finding"],
        "code": ORIGINAL.read_text(encoding="utf-8"),
        "tests": result["tests"],
        "output": result["output"],
    }


@app.post("/api/propose-fix")
def fix():
    _sync()
    state["fix"] = propose_fix(ORIGINAL.read_text(encoding="utf-8"))
    _persist()
    return state["fix"]


@app.post("/api/verify")
def run_proof(payload: dict | None = Body(default=None)):
    """Test one patch. {"patch": "bad"} tests the demo bad patch; no body tests the AI fix."""
    payload = payload or {}
    _sync()
    if payload.get("patch") == "bad":
        tested = {"code": make_bad_patch(), "source": "demo: deliberately bad patch (refuses everyone)"}
    elif payload.get("code"):
        tested = {"code": payload["code"], "source": "custom patch"}
    elif "fix" in state:
        tested = state["fix"]
    else:
        return {"error": "Generate the AI fix first (step 2)."}

    state.pop("proof", None)  # until this run finishes, nothing counts as verified
    _persist()
    result = verify(tested["code"])
    if "error" in result:
        return result
    state["tested"] = tested
    state["proof"] = result
    state["time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _persist()
    return result


REPORT = Template("""<html><head><title>PatchTrace Verification Report</title></head>
<body style="font-family:sans-serif;max-width:800px;margin:2rem auto;line-height:1.5">
<h1>PatchTrace Verification Report</h1><p>{{ time }}</p>
<h2>Verdict: {{ p.verdict }}</h2>
<h3>Finding</h3><p><b>{{ f.title }}</b> ({{ f.severity }})<br>{{ f.plain_english }}</p>
<h3>Patch source</h3><p>{{ tested.source }}</p>
<h3>Evidence</h3>
<p>Vulnerability reproduced before fix: {{ p.reproduced_before }}<br>
Security test passes after fix: {{ p.security_fixed }}<br>
Regression tests pass after fix: {{ p.regression_ok }}</p>
<h3>Test results after fix ({{ passed }} of {{ total }} passed)</h3>
<ul>{% for t in p.after.tests %}<li>{{ t.name }}: {{ t.status }}</li>{% endfor %}</ul>
<h3>Patch</h3><pre style="background:#f4f4f4;padding:1rem;overflow:auto">{{ p.diff }}</pre>
<h3>Not verified / limitations</h3>
<ul>
<li>Only one vulnerability class (access control) on one controlled demo app.</li>
<li>Passing tests show this specific attack is blocked, not that the app is secure.</li>
<li>Patch code is executed locally; production use would need a sandbox.</li>
</ul></body></html>""", autoescape=True)


@app.get("/api/report", response_class=HTMLResponse)
def report(download: bool = False):
    _sync()
    if "proof" not in state:
        return HTMLResponse("<p>Run the proof engine first.</p>")
    tests = state["proof"]["after"]["tests"]
    html = REPORT.render(
        p=state["proof"], f=FINDING, tested=state["tested"], time=state["time"],
        passed=sum(t["status"] == "passed" for t in tests), total=len(tests),
    )
    headers = {"Content-Disposition": "attachment; filename=patchtrace-report.html"} if download else {}
    return HTMLResponse(html, headers=headers)


@app.get("/api/shop/status")
def shop_status():
    return live_shop.status()


@app.post("/api/shop/attack")
def shop_attack():
    return {"status": live_shop.status(), "attempts": live_shop.attack()}


@app.post("/api/shop/deploy-patch")
def shop_deploy():
    _sync()
    proof, tested = state.get("proof"), state.get("tested")
    if not proof or not tested or proof["verdict"] != "VERIFIED":
        return {"error": "Deploy blocked: only a VERIFIED patch can go live. "
                         "If you just saw VERIFIED, click “4 · Test the GOOD patch” once more and then Deploy."}
    same = lambda a, b: a.replace("\r\n", "\n").strip() == b.replace("\r\n", "\n").strip()
    if not PATCHED.exists() or not same(PATCHED.read_text(encoding="utf-8"), tested["code"]):
        return {"error": "Deploy blocked: the patch file changed after it was verified. Run the proof again."}
    live_shop.start(PATCHED, "patched")
    return {"status": live_shop.status(), "attempts": live_shop.attack()}


@app.post("/api/shop/reset")
def shop_reset():
    live_shop.start(ORIGINAL, "vulnerable")
    return {"status": live_shop.status(), "attempts": live_shop.attack()}


# Keep this LAST so it does not hide the /api routes.
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True))
