"""Runs a shop app file as a REAL website on a local port.

Usage: python demo_app/run_shop.py <path-to-app-file> <port> <label>

PatchTrace starts this twice during a demo: once with the vulnerable app,
and later with the verified patched app. The storefront page (shop.html)
is added here, so the file the AI patches stays small.
"""
import importlib.util
import sys
from pathlib import Path

from flask import jsonify, send_file


def main(app_path: str, port: int, label: str) -> None:
    spec = importlib.util.spec_from_file_location("shop_target", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = module.create_app()

    page = Path(__file__).parent / "shop.html"
    app.add_url_rule("/", "patchtrace_home", lambda: send_file(page))
    app.add_url_rule("/__version", "patchtrace_version", lambda: jsonify(version=label))

    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])
