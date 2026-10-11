import importlib.util
import os

import pytest

ALICE = {"Authorization": "Bearer token-alice"}
BOB = {"Authorization": "Bearer token-bob"}


@pytest.fixture
def client():
    # TARGET_APP tells the tests which app file to attack (original or patched).
    path = os.environ["TARGET_APP"]
    spec = importlib.util.spec_from_file_location("target_app", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    app = mod.create_app()
    app.config["TESTING"] = True
    return app.test_client()
