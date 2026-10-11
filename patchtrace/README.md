# PatchTrace

**AI writes the patch. PatchTrace traces the proof.**

PatchTrace helps developers move from security alerts to tested fixes by combining
AI-assisted remediation with real, reproducible security-test evidence.

## What it does
1. Starts a **real, running shop website** (port 5001) with a Broken Access Control bug: User A can read User B's order, and the other way round.
2. Attacks the live shop with real HTTP requests and shows what leaked.
3. Explains the problem in plain English.
4. Asks Claude for a code fix (falls back to a saved fix if the API is unavailable).
5. Runs the security tests and regression tests **before and after** the patch.
6. Gives a VERIFIED or NOT VERIFIED verdict and a downloadable report with the evidence and limitations.
7. Only if VERIFIED, deploys the patch to the live shop and repeats the same attack. Now it is blocked.

The shop has its own page at http://127.0.0.1:5001 and is also embedded in the dashboard. Log in as Alice and open order 2 to see the leak yourself.

## Run it on Windows (easiest)
1. Install Python 3.11 or newer from python.org (tick "Add Python to PATH").
2. Double-click `start.bat`.
3. Open http://127.0.0.1:8000 and click the buttons in order.

## Run it manually (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ANTHROPIC_API_KEY="your-key"     # optional: without it the saved fallback fix is used
python -m uvicorn backend.main:app --port 8000
```
Run only ONE copy at a time (close any old PowerShell window running it with Ctrl+C) and do not add `--reload`.
Run this from inside the `PatchTrace` folder, the one that directly contains `backend`, `tests` and `frontend`.
Use `python -m uvicorn` (not plain `uvicorn`) so Python can find the `backend` folder.

## Demo path (follow the numbered steps at the top of the dashboard)
1. **Run security check** finds the bug.
2. **Generate AI fix** shows the proposed patch along with the choice of Al Model Google Gemini or the Claude.
3. **Test the BAD patch** is a deliberately wrong fix. Expected: NOT VERIFIED, Deploy stays locked.
4. **Test the GOOD patch** is the AI fix. Expected: VERIFIED, Deploy unlocks.
5. **Deploy verified patch to live app** restarts the live shop with the patch, then the same attack is blocked.

The Deploy button appears in the verdict box right under the test results, and also in the Live shop box at the top.

## Folder map
| Folder / file | What it holds |
|---|---|
| `demo_app/` | The deliberately vulnerable shop app (`app.py`), its storefront page (`shop.html`) and the runner that serves it live (`run_shop.py`) |
| `tests/` | Security tests (the attacks) and regression tests (normal behavior) |
| `backend/` | Proof engine, AI fix module, live shop manager, FastAPI server |
| `frontend/` | The single-page dashboard |
| `fallback/` | A known-good fix used when the AI is unavailable |
| `start.bat` | One-click start for Windows |
| `requirements.txt` | The Python packages PatchTrace needs |

## How the verdict works
VERIFIED needs all three to be true:
- the vulnerability was **reproduced** before the fix,
- the security tests **pass** after the fix,
- the regression tests **still pass** after the fix.

A patch that blocks the leak but breaks normal use is marked NOT VERIFIED.

## Limitations (honest list)
- One vulnerability class (access control) on one controlled demo app.
- The finding text is predefined; detection is the failing security test.
- Passing tests show these specific attacks are blocked, not that the app is secure.
- Patch code is executed locally; a production version needs a sandbox (e.g. Docker).
