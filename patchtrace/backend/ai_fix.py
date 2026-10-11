"""Ask Claude to propose a fix. If the API is unavailable, use the saved fallback fix."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROMPT = """You are a secure-code reviewer. The Flask file below has a Broken Access Control
vulnerability: any logged-in user can read another user's order via GET /orders/<id>.
Return the COMPLETE corrected file in a single ```python block. Change as little as possible.
Keep create_app(), every route, and every response format unchanged."""


def propose_fix(source: str) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _fallback("no ANTHROPIC_API_KEY set")
    try:
        import anthropic

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        msg = client.messages.create(
            model=os.getenv("MODEL", "claude-sonnet-5-5"),
            max_tokens=4000,
            messages=[{"role": "user", "content": f"{PROMPT}\n\n```python\n{source}\n```"}],
        )
        text = msg.content[0].text
        match = re.search(r"```python\n(.*?)```", text, re.S)
        return {"code": match.group(1) if match else text, "source": "claude"}
    except Exception as e:  # network down, bad key, etc.
        return _fallback(type(e).__name__)


def _fallback(reason: str) -> dict:
    code = (ROOT / "fallback" / "app_fixed.py").read_text(encoding="utf-8")
    return {"code": code, "source": f"fallback ({reason})"}
