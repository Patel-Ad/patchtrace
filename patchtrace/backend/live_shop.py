"""Starts, stops and attacks the LIVE shop website that PatchTrace demos against."""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.getenv("SHOP_PORT", "5001"))
BASE = f"http://127.0.0.1:{PORT}"

TOKENS = {"Alice": "token-alice", "Bob": "token-bob"}

_lock = threading.Lock()
_proc = None


def _version():
    try:
        with urllib.request.urlopen(BASE + "/__version", timeout=1) as r:
            return json.load(r)["version"]
    except Exception:
        return None


def stop() -> None:
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None


def start(app_path: Path, label: str) -> dict:
    """(Re)start the live shop using the given app file. label is 'vulnerable' or 'patched'."""
    global _proc
    with _lock:
        stop()
        _proc = subprocess.Popen(
            [sys.executable, str(ROOT / "demo_app" / "run_shop.py"), str(app_path), str(PORT), label],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(80):  # wait up to ~12 seconds for the shop to answer
            if _version() == label or _proc.poll() is not None:
                break
            time.sleep(0.15)
    return status()


def status() -> dict:
    version = _version()
    return {"running": version is not None, "version": version, "url": BASE + "/"}


def _get(path: str, who: str) -> dict:
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + TOKENS[who]})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            code, body = r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        code, body = e.code, e.read().decode()
    except Exception as e:
        return {"status": 0, "body": f"Could not reach the shop: {e}"}
    return {"status": code, "body": " ".join(body.split())}


def attack() -> list:
    """Send real HTTP requests to the running shop and report what came back."""
    plan = [
        ("Alice", "/orders/1", "Alice opens her own order #1 (normal use)", "control"),
        ("Alice", "/orders/2", "Alice tries to open Bob's order #2", "attack"),
        ("Bob", "/orders/1", "Bob tries to open Alice's order #1", "attack"),
    ]
    results = []
    for who, path, title, kind in plan:
        r = _get(path, who)
        if r["status"] == 0:
            outcome = "error"
        elif kind == "control":
            outcome = "ok" if r["status"] == 200 else "broken"
        else:
            outcome = "leaked" if r["status"] == 200 else "blocked"
        results.append({
            "who": who, "request": f"GET {path}", "title": title, "kind": kind,
            "status": r["status"], "body": r["body"][:300], "result": outcome,
        })
    return results
