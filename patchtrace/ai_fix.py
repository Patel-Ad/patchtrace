"""Ask an AI model to propose a fix.

Providers: "claude", "gemini", or "saved" (the known-good fix in fallback/).
"auto" picks Claude if its key is set, otherwise Gemini, otherwise the saved fix.
If the chosen AI fails for any reason, the saved fix is used and the reason is shown.
"""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROMPT = """You are a secure-code reviewer. The Flask file below has a Broken Access Control
vulnerability: any logged-in user can read another user's order via GET /orders/<id>.
Return the COMPLETE corrected file in a single ```python block. Change as little as possible.
Keep create_app(), every route, and every response format unchanged."""

KEY_NAMES = {
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def _gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""


def available() -> dict:
    """Which providers have a key set (the dashboard shows this)."""
    return {
        "claude": bool(os.getenv("ANTHROPIC_API_KEY")),
        "gemini": bool(_gemini_key()),
        "saved": True,
    }


def propose_fix(source: str, provider: str = "auto") -> dict:
    have = available()
    if provider == "auto":
        provider = "claude" if have["claude"] else "gemini" if have["gemini"] else "saved"
    if provider == "saved":
        return _fallback("saved fix chosen, or no API key set")
    if provider not in KEY_NAMES:
        return _fallback(f"unknown provider '{provider}'")
    if not have[provider]:
        return _fallback(f"no {KEY_NAMES[provider]} set")
    try:
        ask = _ask_claude if provider == "claude" else _ask_gemini
        text, label = ask(f"{PROMPT}\n\n```python\n{source}\n```")
        return {"code": _extract_code(text), "source": label}
    except Exception as e:  # network down, bad key, wrong model name, etc.
        return _fallback(f"{provider} failed: {_safe(e)}")


def _ask_claude(prompt: str):
    import anthropic

    model = os.getenv("CLAUDE_MODEL") or os.getenv("MODEL") or "claude-sonnet-5-5"
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    msg = client.messages.create(
        model=model,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text, f"claude ({model})"


def _ask_gemini(prompt: str):
    from google import genai
    from google.genai import types

    model = os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
    client = genai.Client(
        api_key=_gemini_key(),
        http_options=types.HttpOptions(timeout=60000),  # 60 seconds, so the button never hangs
    )
    try:
        # Current Gemini API (what Google's quickstart shows).
        reply = client.interactions.create(model=model, input=prompt)
        text = reply.output_text
    except Exception:
        # Older generate_content API, in case the first one is not available.
        reply = client.models.generate_content(model=model, contents=prompt)
        text = reply.text
    if not text:
        raise ValueError("Gemini returned an empty answer")
    return text, f"gemini ({model})"


def _extract_code(text: str) -> str:
    """Take the code out of a ```python ... ``` block (or use the whole reply if there is none)."""
    match = re.search(r"```(?:python|py)?[ \t]*\n(.*?)```", text, re.S)
    return (match.group(1) if match else text).strip() + "\n"


def _safe(e: Exception) -> str:
    """A short, one-line error message with any API key removed."""
    msg = f"{type(e).__name__}: {e}"
    for name in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = os.getenv(name)
        if value:
            msg = msg.replace(value, "***")
    return " ".join(msg.split())[:160]


def _fallback(reason: str) -> dict:
    code = (ROOT / "fallback" / "app_fixed.py").read_text(encoding="utf-8")
    return {"code": code, "source": f"fallback ({reason})"}